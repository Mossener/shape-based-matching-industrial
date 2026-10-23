// Generated solely from the SHA-gated frozen v1 function.
#include "native_candidate_compatibility.hpp"
#include <chrono>
namespace ordered_contour_native::candidate {
struct BaselineIndexWork {
    Id index_builds=0, membership_rows_indexed=0, members_indexed=0, chains_indexed=0;
    std::int64_t index_nanoseconds=0;
};
inline CandidateScore score_candidate_counted(const edge::TemplateEvidence& supplied_template,
                                      const SceneEvidence& supplied_scene,
                                      const Point& tl, const Point& match,
                                      const Padding& padding_ltrb, BaselineIndexWork& index_work) {
    const auto original = detail::validate_padding(padding_ltrb,
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
        result.samples.push_back(detail::support(sample, supplied_scene, tl, match,
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
    const auto index_started = std::chrono::steady_clock::now();
    ++index_work.index_builds;
    std::map<Id, const std::vector<SceneChainMember>*> members_by_pixel;
    for (const auto& row : supplied_scene.memberships) {
        ++index_work.membership_rows_indexed;
        index_work.members_indexed += detail::count(row.members.size());
        members_by_pixel.emplace(row.pixel_id, &row.members);
    }
    std::map<Id, const edge::Chain*> scene_by_id;
    for (const auto& chain : supplied_scene.chains) {
        ++index_work.chains_indexed;
        scene_by_id.emplace(chain.chain_id, &chain);
    }
    index_work.index_nanoseconds += std::chrono::duration_cast<std::chrono::nanoseconds>(
        std::chrono::steady_clock::now() - index_started).count();
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
                for (const auto& member : *members_by_pixel.at(pixel)) {
                    edges_by_scene[member.chain_id].emplace_back(sample->pixel_id, pixel);
                }
            }
        }
        std::vector<SceneChain> scene_chains;
        scene_chains.reserve(edges_by_scene.size());
        for (auto& row : edges_by_scene) {
            std::sort(row.second.begin(), row.second.end());
            const auto& scene_chain = *scene_by_id.at(row.first);
            scene_chains.push_back({row.first, scene_chain.pixel_ids,
                                   std::move(row.second), scene_chain.closed});
        }
        // Retain every original template chain, including zero-owned chains;
        // only scene chains without an edge are omitted, never their vertices.
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
    result.independent_accepted = passes_threshold(result.independent_numerator, result.denominator);
    result.ordered_accepted = passes_threshold(result.ordered_numerator, result.denominator);
    for (const auto& row : selected_owners_by_pixel) {
        if (row.second.size() > 1) result.cross_chain_reused_pixel_ids.push_back(row.first);
    }
    return result;
}

} // namespace ordered_contour_native::candidate
