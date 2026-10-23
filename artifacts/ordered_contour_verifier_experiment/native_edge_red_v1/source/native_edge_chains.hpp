#ifndef ORDERED_CONTOUR_NATIVE_EDGE_CHAINS_HPP
#define ORDERED_CONTOUR_NATIVE_EDGE_CHAINS_HPP

// Typed native mathematical interface for supplied legal integer label grids.
// No images, OpenCV, decode, warp, gradient, matcher, file I/O or speed claim.
// This first version contains types and fixed default stubs only. Preserve an
// actual coordinated RED before implementing validation or graph behavior.
#include <array>
#include <cstdint>
#include <utility>
#include <vector>

#include <gmpxx.h>

namespace ordered_contour_native::edge {

using Id = std::uint64_t;
using Integer = mpz_class;
using LabelGrid = std::vector<std::vector<int>>;
using DeletionRound = std::pair<Id, Id>;

struct ThinningResult {
    Id width = 0;
    Id height = 0;
    LabelGrid eligible_labels;
    LabelGrid labels;
    std::vector<DeletionRound> round_deletions;
};

struct Chain {
    Id chain_id = 0;
    std::vector<Id> pixel_ids;
    bool closed = false;
    bool returning = false;
};

struct ChainSampling {
    Id chain_id = 0;
    std::vector<Id> pixel_ids;
    Integer arclength = 0;
};

struct SampleOwnership {
    Id pixel_id = 0;
    Id owner_chain_id = 0;
    std::vector<Id> member_chain_ids;
};

struct WeightedSample {
    Id pixel_id = 0;
    Id owner_chain_id = 0;
    Id chain_index = 0;
    Id x = 0;
    Id y = 0;
    int label = 255;
    int cell = 0;
    Integer weight = 0;
};

struct TemplateEvidence {
    ThinningResult thinning;
    std::vector<Chain> chains;
    std::vector<ChainSampling> samplings;
    std::vector<SampleOwnership> ownership;
    std::vector<WeightedSample> samples;
    std::array<Id, 16> cell_counts{};
    Id occupied_cells = 0;
    Integer lcm = 0;
    Integer denominator = 0;
};

// Intended validation: nonempty rectangular integer grids with labels0..7/255.
// Typed int cannot distinguish an implicit bool/float conversion; an external
// textual parser must validate its own source domain before constructing grids.
inline ThinningResult thin_labels(const LabelGrid&) { return {}; }

// Intended boundary: decompose exactly this supplied graph, without rethinning.
inline std::vector<Chain> extract_chains(const LabelGrid&) { return {}; }

// Intended validation: positive width, nonempty unique physical IDs, adjacent
// consecutive and closing steps, >=3 vertices for closed cycles, returning only
// when closed. Graph maximality and original graph provenance are not inferred.
inline ChainSampling sample_chain(const Chain&, Id) { return {}; }

// Intended boundary: thin/extract/sample/own/weight; no owned samples is an
// invalid_argument contract failure. All source/result vectors are value copies.
inline TemplateEvidence prepare_template(const LabelGrid&) { return {}; }

}  // namespace ordered_contour_native::edge

#endif  // ORDERED_CONTOUR_NATIVE_EDGE_CHAINS_HPP
