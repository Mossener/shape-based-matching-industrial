#ifndef ORDERED_CONTOUR_NATIVE_CANDIDATE_COMPILED_SCENE_V2_HPP
#define ORDERED_CONTOUR_NATIVE_CANDIDATE_COMPILED_SCENE_V2_HPP

// Coordinator retained ordinary assertion RED before this implementation.
// Immutable scene lookup indexes are shared across candidates. Frozen v1
// headers and complete CandidateScore/solver-work observables are unchanged.
#include "native_candidate_compatibility.hpp"

#include <memory>

namespace ordered_contour_native::candidate_v2 {

using Coordinate = candidate::Coordinate;
using Point = candidate::Point;
using Padding = candidate::Padding;
using CandidateScore = candidate::CandidateScore;

struct SceneIndexWork {
    Id index_builds = 0;
    Id membership_rows_indexed = 0;
    Id members_indexed = 0;
    Id chains_indexed = 0;
};

namespace detail {
struct SceneStorage {
    candidate::SceneEvidence scene;
    std::map<Id, std::size_t> membership_index_by_pixel;
    std::map<Id, std::size_t> chain_index_by_id;
    SceneIndexWork work;
};
} // namespace detail

class CompiledScene {
public:
    CompiledScene(const CompiledScene&) = default;
    CompiledScene(CompiledScene&&) noexcept = default;
    CompiledScene& operator=(const CompiledScene&) = default;
    CompiledScene& operator=(CompiledScene&&) noexcept = default;

    bool valid() const noexcept { return static_cast<bool>(storage_); }
    bool shares_storage_with(const CompiledScene& other) const noexcept {
        return storage_ && storage_ == other.storage_;
    }
    const candidate::SceneEvidence& evidence() const {
        require_storage();
        return storage_->scene;
    }
    const SceneIndexWork& index_work() const {
        require_storage();
        return storage_->work;
    }

private:
    explicit CompiledScene(std::shared_ptr<const detail::SceneStorage> storage)
        : storage_(std::move(storage)) {}
    void require_storage() const {
        if (!storage_) throw std::invalid_argument("moved-from compiled scene");
    }
    std::shared_ptr<const detail::SceneStorage> storage_;

    friend CompiledScene prepare_scene(const edge::LabelGrid&);
    friend CandidateScore score_candidate(const edge::TemplateEvidence&, const CompiledScene&,
                                         const Point&, const Point&, const Padding&);
};

// Own an immutable scene snapshot and both complete scene lookup indexes once.
// Copy/move preserve shared storage; accessing a moved-from handle is invalid.
inline CompiledScene prepare_scene(const edge::LabelGrid& labels) {
    auto storage = std::make_shared<detail::SceneStorage>();
    storage->scene = candidate::prepare_scene(labels);
    storage->work.index_builds = 1;
    for (std::size_t index = 0; index < storage->scene.memberships.size(); ++index) {
        const auto& row = storage->scene.memberships[index];
        storage->membership_index_by_pixel.emplace(row.pixel_id, index);
        edge::detail::increment(storage->work.membership_rows_indexed);
        const Id members = candidate::detail::count(row.members.size());
        if (members > std::numeric_limits<Id>::max() - storage->work.members_indexed) {
            throw std::overflow_error("compiled scene member count exceeds uint64");
        }
        storage->work.members_indexed += members;
    }
    for (std::size_t index = 0; index < storage->scene.chains.size(); ++index) {
        storage->chain_index_by_id.emplace(storage->scene.chains[index].chain_id, index);
        edge::detail::increment(storage->work.chains_indexed);
    }
    return CompiledScene(std::move(storage));
}

// Full frozen v1 CandidateScore observables, including every solver work field.
// Per-score candidate-local maps are allowed; no scene-wide scan/map build.
inline CandidateScore score_candidate(const edge::TemplateEvidence& supplied_template,
                                      const CompiledScene& compiled_scene,
                                      const Point& tl, const Point& match,
                                      const Padding& padding_ltrb = {0, 0, 0, 0}) {
    compiled_scene.require_storage();
    const auto& storage = *compiled_scene.storage_;
    const auto& supplied_scene = storage.scene;
    const auto original = candidate::detail::validate_padding(padding_ltrb,
        supplied_scene.thinning.width, supplied_scene.thinning.height);
    CandidateScore result;
    result.denominator = supplied_template.denominator;
    result.samples.reserve(supplied_template.samples.size());
    std::map<Id, std::size_t> support_by_sample;
    std::map<Id, std::vector<const edge::WeightedSample*>> samples_by_owner;
    for (const auto& chain : supplied_template.chains) samples_by_owner.emplace(chain.chain_id,
        std::vector<const edge::WeightedSample*>{});
    for (const auto& sample : supplied_template.samples) {
        support_by_sample.emplace(sample.pixel_id, result.samples.size());
        result.samples.push_back(candidate::detail::support(sample, supplied_scene, tl, match,
            padding_ltrb, original.first, original.second));
        const auto& support = result.samples.back();
        samples_by_owner.at(sample.owner_chain_id).push_back(&sample);
        if (!support.compatible_pixel_ids.empty()) result.independent_numerator += sample.weight;
        if (!support.padded_in_bounds) result.outside_padded_sample_ids.push_back(sample.pixel_id);
        if (!support.original_in_bounds) result.outside_original_sample_ids.push_back(sample.pixel_id);
        if (support.independent_witness) {
            result.independent_witness.emplace_back(sample.pixel_id, *support.independent_witness);
        }
    }
    // Both complete scene indexes were built by prepare_scene. Only incident
    // memberships/chains are read below; no scene-wide iteration/map build.
    std::map<Id, std::set<Id>> selected_owners_by_pixel;
    Integer independent_chain_sum = 0;
    result.chains.reserve(supplied_template.chains.size());
    for (const auto& chain : supplied_template.chains) {
        auto& owned = samples_by_owner.at(chain.chain_id);
        std::sort(owned.begin(), owned.end(),
            [](const edge::WeightedSample* left, const edge::WeightedSample* right) {
                return left->chain_index < right->chain_index;
            });
        TemplateChain template_chain;
        template_chain.chain_id = chain.chain_id;
        template_chain.closed = chain.closed;
        template_chain.sample_ids.reserve(owned.size());
        template_chain.weights.reserve(owned.size());
        std::map<Id, std::vector<Edge>> edges_by_scene;
        for (const auto* sample : owned) {
            template_chain.sample_ids.push_back(sample->pixel_id);
            template_chain.weights.push_back(sample->weight);
            const auto& support = result.samples.at(support_by_sample.at(sample->pixel_id));
            for (Id pixel : support.compatible_pixel_ids) {
                const auto& members = supplied_scene.memberships.at(
                    storage.membership_index_by_pixel.at(pixel)).members;
                for (const auto& member : members) {
                    edges_by_scene[member.chain_id].emplace_back(sample->pixel_id, pixel);
                }
            }
        }
        std::vector<SceneChain> scene_chains;
        scene_chains.reserve(edges_by_scene.size());
        for (auto& row : edges_by_scene) {
            std::sort(row.second.begin(), row.second.end());
            const auto& scene_chain = supplied_scene.chains.at(storage.chain_index_by_id.at(row.first));
            scene_chains.push_back({row.first, scene_chain.pixel_ids,
                                   std::move(row.second), scene_chain.closed});
        }
        auto solved = ordered_contour_native::solve(template_chain, scene_chains);
        result.ordered_numerator += solved.numerator;
        independent_chain_sum += solved.independent_numerator;
        for (const auto& edge : solved.witness) {
            selected_owners_by_pixel[edge.second].insert(chain.chain_id);
        }
        result.chains.push_back(std::move(solved));
    }
    if (result.ordered_numerator < 0 || result.ordered_numerator > result.independent_numerator ||
        result.independent_numerator > result.denominator) {
        throw std::logic_error("factory candidate scores violate 0<=B<=A<=D");
    }
    if (independent_chain_sum != result.independent_numerator) {
        throw std::logic_error("scene memberships lost independent sample support");
    }
    result.independent_accepted = candidate::passes_threshold(result.independent_numerator, result.denominator);
    result.ordered_accepted = candidate::passes_threshold(result.ordered_numerator, result.denominator);
    for (const auto& row : selected_owners_by_pixel) {
        if (row.second.size() > 1) result.cross_chain_reused_pixel_ids.push_back(row.first);
    }
    return result;
}

} // namespace ordered_contour_native::candidate_v2

#endif // ORDERED_CONTOUR_NATIVE_CANDIDATE_COMPILED_SCENE_V2_HPP
