#ifndef ORDERED_CONTOUR_NATIVE_CANDIDATE_COMPATIBILITY_HPP
#define ORDERED_CONTOUR_NATIVE_CANDIDATE_COMPATIBILITY_HPP

// Typed supplied-label factory-evidence interface, intentionally ZERO STUB.
// Keep behavior absent until the coordinating ordinary assertion RED is saved.
// No images, detector, file I/O, benchmark, or production integration.
#include "native_edge_chains.hpp"
#include "native_ordered_match.hpp"

#include <array>
#include <cstdint>
#include <optional>
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

// Typed int64/array fields cannot recover Python bool/float/length provenance.
// A later textual adapter must reject invalid source values before conversion.
// Grid, padding, threshold-domain, and checked intermediate-arithmetic failures
// use std::invalid_argument. Arbitrary forged/mutated evidence is out of scope.
inline SceneEvidence prepare_scene(const edge::LabelGrid& labels) {
    (void)labels;
    return {};
}

inline bool passes_threshold(const Integer& numerator, const Integer& denominator) {
    (void)numerator;
    (void)denominator;
    return false;
}

inline CandidateScore score_candidate(const edge::TemplateEvidence& supplied_template,
                                      const SceneEvidence& supplied_scene,
                                      const Point& tl, const Point& match,
                                      const Padding& padding_ltrb = {0, 0, 0, 0}) {
    (void)supplied_template;
    (void)supplied_scene;
    (void)tl;
    (void)match;
    (void)padding_ltrb;
    return {};
}

}  // namespace ordered_contour_native::candidate

#endif  // ORDERED_CONTOUR_NATIVE_CANDIDATE_COMPATIBILITY_HPP
