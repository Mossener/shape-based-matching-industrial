#ifndef ORDERED_CONTOUR_NATIVE_CANDIDATE_COMPATIBILITY_HPP
#define ORDERED_CONTOUR_NATIVE_CANDIDATE_COMPATIBILITY_HPP

// Typed supplied-label factory-evidence mathematical interface.
// The coordinating ordinary zero-stub assertion RED was retained before this
// implementation; evidence must remain unmodified after its factory call.
// No images, detector, file I/O, benchmark, or production integration.
#include "native_edge_chains.hpp"
#include "native_ordered_match.hpp"

#include <array>
#include <algorithm>
#include <cstddef>
#include <cstdint>
#include <limits>
#include <map>
#include <optional>
#include <set>
#include <stdexcept>
#include <utility>
#include <vector>

namespace ordered_contour_native::candidate {

using Coordinate = std::int64_t;
using Point = std::array<Coordinate, 2>;
using Padding = std::array<Coordinate, 4>;  // left, top, right, bottom

struct SceneChainMember {
    Id chain_id = 0;
    Id chain_index = 0;
};

struct ScenePixelMembership {
    Id pixel_id = 0;
    std::vector<SceneChainMember> members;
};

struct SceneEvidence {
    edge::ThinningResult thinning;
    std::vector<edge::Chain> chains;
    std::vector<ScenePixelMembership> memberships;
};

struct SampleSupport {
    Id sample_id = 0;
    Point p_canvas{};
    Point relative{};
    Point q_padded{};
    Point q_original{};
    bool padded_in_bounds = false;
    bool original_in_bounds = false;
    std::vector<Id> compatible_pixel_ids;
    std::optional<Id> independent_witness;
};

struct CandidateScore {
    Integer denominator = 0;
    Integer independent_numerator = 0;
    Integer ordered_numerator = 0;
    bool independent_accepted = false;
    bool ordered_accepted = false;
    std::vector<SampleSupport> samples;
    std::vector<MatchResult> chains;
    std::vector<Id> outside_padded_sample_ids;
    std::vector<Id> outside_original_sample_ids;
    std::vector<Edge> independent_witness;
    std::vector<Id> cross_chain_reused_pixel_ids;
};

namespace detail {

inline Coordinate coordinate(Id value) {
    if (value > static_cast<Id>(std::numeric_limits<Coordinate>::max())) {
        throw std::invalid_argument("factory coordinate or scene dimension exceeds signed int64");
    }
    return static_cast<Coordinate>(value);
}

inline Id count(std::size_t value) {
    if constexpr (sizeof(std::size_t) > sizeof(Id)) {
        if (value > static_cast<std::size_t>(std::numeric_limits<Id>::max())) {
            throw std::overflow_error("candidate evidence count exceeds uint64");
        }
    }
    return static_cast<Id>(value);
}

inline Coordinate add(Coordinate left, Coordinate right) {
    constexpr Coordinate low = std::numeric_limits<Coordinate>::min();
    constexpr Coordinate high = std::numeric_limits<Coordinate>::max();
    if ((right > 0 && left > high - right) ||
        (right < 0 && left < low - right)) {
        throw std::invalid_argument("candidate coordinate addition exceeds signed int64");
    }
    return left + right;
}

inline Coordinate subtract(Coordinate left, Coordinate right) {
    constexpr Coordinate low = std::numeric_limits<Coordinate>::min();
    constexpr Coordinate high = std::numeric_limits<Coordinate>::max();
    if ((right > 0 && left < low + right) ||
        (right < 0 && left > high + right)) {
        throw std::invalid_argument("candidate coordinate subtraction exceeds signed int64");
    }
    return left - right;
}

inline std::pair<Coordinate, Coordinate> validate_padding(
        const Padding& padding, Id supplied_width, Id supplied_height) {
    const Coordinate width = coordinate(supplied_width);
    const Coordinate height = coordinate(supplied_height);
    for (Coordinate value : padding) {
        if (value < 0) throw std::invalid_argument("padding entries must be nonnegative");
    }
    const Coordinate horizontal = add(padding[0], padding[2]);
    const Coordinate vertical = add(padding[1], padding[3]);
    if (horizontal >= width || vertical >= height) {
        throw std::invalid_argument("padding must leave positive original dimensions");
    }
    return {subtract(width, horizontal), subtract(height, vertical)};
}

inline SampleSupport support(const edge::WeightedSample& sample,
                             const SceneEvidence& scene, const Point& tl,
                             const Point& match, const Padding& padding,
                             Coordinate original_width, Coordinate original_height) {
    SampleSupport result;
    result.sample_id = sample.pixel_id;
    result.p_canvas = {coordinate(sample.x), coordinate(sample.y)};
    // Complete each frame before the next one and before any bounds shortcut.
    // In particular, overflow cannot be hidden by cancellation or an outside
    // center. Never negate an operand, which would overflow at INT64_MIN.
    for (std::size_t axis = 0; axis < 2; ++axis) {
        result.relative[axis] = subtract(result.p_canvas[axis], tl[axis]);
    }
    for (std::size_t axis = 0; axis < 2; ++axis) {
        result.q_padded[axis] = add(match[axis], result.relative[axis]);
    }
    for (std::size_t axis = 0; axis < 2; ++axis) {
        result.q_original[axis] = subtract(result.q_padded[axis], padding[axis]);
    }
    const Id width = scene.thinning.width, height = scene.thinning.height;
    result.padded_in_bounds = result.q_padded[0] >= 0 && result.q_padded[1] >= 0 &&
        result.q_padded[0] < coordinate(width) && result.q_padded[1] < coordinate(height);
    result.original_in_bounds = result.q_original[0] >= 0 && result.q_original[1] >= 0 &&
        result.q_original[0] < original_width && result.q_original[1] < original_height;
    if (!result.padded_in_bounds) return result;

    // A valid in-bounds center is nonnegative. Clip unsigned coordinates by
    // distance from borders; do not compute signed x+3/y+3 near INT64_MAX.
    const Id x = static_cast<Id>(result.q_padded[0]);
    const Id y = static_cast<Id>(result.q_padded[1]);
    const Id xmin = x >= 2 ? x - 2 : 0;
    const Id ymin = y >= 2 ? y - 2 : 0;
    const Id xmax = width - 1 - x >= 2 ? x + 2 : width - 1;
    const Id ymax = height - 1 - y >= 2 ? y + 2 : height - 1;
    for (Id neighbor_y = ymin; neighbor_y <= ymax; ++neighbor_y) {
        for (Id neighbor_x = xmin; neighbor_x <= xmax; ++neighbor_x) {
            const int label = scene.thinning.labels[static_cast<std::size_t>(neighbor_y)]
                                                  [static_cast<std::size_t>(neighbor_x)];
            if (label == 255) continue;
            const int difference = sample.label >= label ? sample.label - label : label - sample.label;
            if (std::min(difference, 8 - difference) <= 1) {
                result.compatible_pixel_ids.push_back(neighbor_y * width + neighbor_x);
            }
        }
    }
    // Row-major enumeration is ascending physical ID, including clipped edges.
    if (!result.compatible_pixel_ids.empty()) {
        result.independent_witness = result.compatible_pixel_ids.front();
    }
    return result;
}

}  // namespace detail

// Typed int64/array fields cannot recover Python bool/float/length provenance.
// A later textual adapter must reject invalid source values before conversion.
// Grid, padding, threshold-domain, and checked intermediate-arithmetic failures
// use std::invalid_argument. Arbitrary forged/mutated evidence is out of scope.
inline SceneEvidence prepare_scene(const edge::LabelGrid& labels) {
    SceneEvidence result;
    result.thinning = edge::thin_labels(labels);
    // All downstream scene bounds use signed-int64 coordinate comparisons.
    (void)detail::coordinate(result.thinning.width);
    (void)detail::coordinate(result.thinning.height);
    result.chains = edge::extract_chains(result.thinning.labels);
    std::map<Id, std::vector<SceneChainMember>> members_by_pixel;
    for (const auto& chain : result.chains) {
        for (std::size_t index = 0; index < chain.pixel_ids.size(); ++index) {
            members_by_pixel[chain.pixel_ids[index]].push_back({chain.chain_id, detail::count(index)});
        }
    }
    result.memberships.reserve(members_by_pixel.size());
    for (auto& row : members_by_pixel) {
        std::sort(row.second.begin(), row.second.end(),
            [](const SceneChainMember& left, const SceneChainMember& right) {
                return left.chain_id < right.chain_id;
            });
        result.memberships.push_back({row.first, std::move(row.second)});
    }
    return result;
}

inline bool passes_threshold(const Integer& numerator, const Integer& denominator) {
    if (denominator <= 0 || numerator < 0 || numerator > denominator) {
        throw std::invalid_argument("score requires 0<=N<=D and D>0");
    }
    return 20 * numerator >= 13 * denominator;
}

inline CandidateScore score_candidate(const edge::TemplateEvidence& supplied_template,
                                      const SceneEvidence& supplied_scene,
                                      const Point& tl, const Point& match,
                                      const Padding& padding_ltrb = {0, 0, 0, 0}) {
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
    std::map<Id, const std::vector<SceneChainMember>*> members_by_pixel;
    for (const auto& row : supplied_scene.memberships) members_by_pixel.emplace(row.pixel_id, &row.members);
    std::map<Id, const edge::Chain*> scene_by_id;
    for (const auto& chain : supplied_scene.chains) scene_by_id.emplace(chain.chain_id, &chain);
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

}  // namespace ordered_contour_native::candidate

#endif  // ORDERED_CONTOUR_NATIVE_CANDIDATE_COMPATIBILITY_HPP
