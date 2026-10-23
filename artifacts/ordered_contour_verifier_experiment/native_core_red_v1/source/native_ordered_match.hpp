#ifndef ORDERED_CONTOUR_NATIVE_ORDERED_MATCH_HPP
#define ORDERED_CONTOUR_NATIVE_ORDERED_MATCH_HPP

// Native supplied-graph mathematical interface. No image processing, detector,
// production integration, benchmark, or native-speed claim belongs here.
// This initial header intentionally contains only types and a fixed zero stub.
// Retain a coordinated ordinary RED before adding any validation or algorithm.
#include <cstdint>
#include <optional>
#include <utility>
#include <vector>

#include <gmpxx.h>

namespace ordered_contour_native {

using Id = std::uint64_t;
using Integer = mpz_class;
using Edge = std::pair<Id, Id>;

// Input vector order is topology, even when physical IDs are not numeric order.
// The typed API uses uint64 IDs and bool flags; textual parsers must separately
// reject negative/overflow IDs and illegal textual booleans before construction.
struct TemplateChain {
    Id chain_id = 0;
    std::vector<Id> sample_ids;
    std::vector<Integer> weights;
    bool closed = false;
};

struct SceneChain {
    Id chain_id = 0;
    std::vector<Id> pixel_ids;
    std::vector<Edge> edges;
    bool closed = false;
};

struct MatchCase {
    Id scene_chain_id = 0;
    int direction = 1;
    std::uint64_t template_cut = 0;
    std::uint64_t scene_cut = 0;
};

struct WorkCounters {
    std::uint64_t case_count = 0;
    std::uint64_t edge_states = 0;
    std::uint64_t fenwick_queries = 0;
    std::uint64_t fenwick_updates = 0;
    std::uint64_t fenwick_query_visits = 0;
    std::uint64_t fenwick_update_visits = 0;
    std::uint64_t maximum_integer_bits = 0;
};

struct MatchResult {
    Id template_chain_id = 0;
    Integer numerator = 0;
    Integer independent_numerator = 0;
    Integer total_weight = 0;
    std::optional<MatchCase> selected_case;
    std::vector<Edge> witness;
    WorkCounters work;
};

// The eventual contract is exact weighted ordered matching, one scene chain per
// solve, with std::invalid_argument for malformed graph inputs (including unused
// chains), and checked uint64 work counters. No part is implemented by this stub.
inline MatchResult solve(const TemplateChain&, const std::vector<SceneChain>&) {
    return {};
}

}  // namespace ordered_contour_native

#endif  // ORDERED_CONTOUR_NATIVE_ORDERED_MATCH_HPP
