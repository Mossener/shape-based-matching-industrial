#ifndef ORDERED_CONTOUR_NATIVE_ORDERED_MATCH_HPP
#define ORDERED_CONTOUR_NATIVE_ORDERED_MATCH_HPP

// Native supplied-graph mathematical interface. No image processing, detector,
// production integration, benchmark, or native-speed claim belongs here.
// Exact sparse weighted ordered matching on supplied canonical chain graphs.
// The coordinated zero-stub RED was retained before this implementation.
#include <algorithm>
#include <cstddef>
#include <cstdint>
#include <limits>
#include <map>
#include <optional>
#include <set>
#include <stdexcept>
#include <tuple>
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

namespace detail {

inline std::uint64_t count_value(std::size_t value) {
    if constexpr (sizeof(std::size_t) > sizeof(std::uint64_t)) {
        if (value > static_cast<std::size_t>(
                        std::numeric_limits<std::uint64_t>::max())) {
            throw std::overflow_error("native count exceeds uint64");
        }
    }
    return static_cast<std::uint64_t>(value);
}

inline void increment(std::uint64_t& value) {
    if (value == std::numeric_limits<std::uint64_t>::max()) {
        throw std::overflow_error("native work counter exceeds uint64");
    }
    ++value;
}

inline std::uint64_t integer_bits(const Integer& value) {
    // GMP defines sizeinbase(0,2)=1; the Python contract defines bit_length(0)=0.
    return value == 0 ? 0 : count_value(mpz_sizeinbase(value.get_mpz_t(), 2));
}

struct Validated {
    TemplateChain template_chain;
    std::vector<SceneChain> scene_chains;
};

inline Validated validate(const TemplateChain& supplied_template,
                          const std::vector<SceneChain>& supplied_scenes) {
    Validated result{supplied_template, supplied_scenes};
    const auto& template_chain = result.template_chain;
    if (template_chain.weights.size() != template_chain.sample_ids.size()) {
        throw std::invalid_argument("weights and template sample IDs must have equal length");
    }
    std::set<Id> known_samples;
    for (Id sample : template_chain.sample_ids) {
        if (!known_samples.insert(sample).second) {
            throw std::invalid_argument("template physical sample IDs must be unique");
        }
    }
    for (const Integer& weight : template_chain.weights) {
        if (weight <= 0) {
            throw std::invalid_argument("template scoring weights must be strictly positive");
        }
    }
    std::set<Id> scene_ids;
    // Validate every chain before returning any zero/no-edge result.
    for (auto& scene : result.scene_chains) {
        if (!scene_ids.insert(scene.chain_id).second) {
            throw std::invalid_argument("scene chain IDs must be unique");
        }
        std::set<Id> known_pixels;
        for (Id pixel : scene.pixel_ids) {
            if (!known_pixels.insert(pixel).second) {
                throw std::invalid_argument("scene physical pixel IDs must be unique");
            }
        }
        std::set<Edge> known_edges;
        for (const Edge& edge : scene.edges) {
            if (known_samples.find(edge.first) == known_samples.end() ||
                known_pixels.find(edge.second) == known_pixels.end()) {
                throw std::invalid_argument("compatibility edge refers to an unknown physical ID");
            }
            if (!known_edges.insert(edge).second) {
                throw std::invalid_argument("compatibility edges within a scene chain must be unique");
            }
        }
        // Sorting edges changes no supplied template or scene topology.
        std::sort(scene.edges.begin(), scene.edges.end());
    }
    std::sort(result.scene_chains.begin(), result.scene_chains.end(),
              [](const SceneChain& left, const SceneChain& right) {
                  return left.chain_id < right.chain_id;
              });
    return result;
}

// Both operands are indices in [0,modulus). This avoids overflow in the usual
// (position + modulus - cut) % modulus expression, including uint64 boundaries.
inline std::size_t cyclic_difference(std::size_t position, std::size_t cut,
                                     std::size_t modulus) {
    return position >= cut ? position - cut : modulus - (cut - position);
}

struct State {
    Integer score;
    Edge edge;
    std::size_t predecessor = 0;
};

inline std::size_t better(std::size_t left, std::size_t right,
                          const std::vector<State>& states) {
    if (left == right) return left;
    if (states[left].score != states[right].score) {
        return states[left].score > states[right].score ? left : right;
    }
    if (left == 0) return right;
    if (right == 0) return left;
    // Original edges are unique within this case, and each edge creates exactly
    // one state. Different terminal edges decide the reversed witness order at
    // its first element. The chosen predecessor is already canonical by the
    // same rule. Positive weights prevent a nonempty state tying the sentinel.
    return states[left].edge < states[right].edge ? left : right;
}

struct TransformedEdge {
    std::size_t row;
    std::size_t column;
    Edge edge;
};

inline std::pair<Integer, std::vector<Edge>> run_case(
        const TemplateChain& template_chain, const SceneChain& scene,
        const MatchCase& match_case,
        const std::map<Id, std::size_t>& template_positions,
        const std::map<Id, std::size_t>& scene_positions,
        WorkCounters& work) {
    const auto n = template_chain.sample_ids.size();
    const auto m = scene.pixel_ids.size();
    // Cuts are made from real size_t positions in solve, then range-checked on
    // conversion to the public uint64 fields. These casts restore those values.
    const auto template_cut = static_cast<std::size_t>(match_case.template_cut);
    const auto scene_cut = static_cast<std::size_t>(match_case.scene_cut);
    std::vector<TransformedEdge> transformed;
    transformed.reserve(scene.edges.size());
    for (const Edge& edge : scene.edges) {
        auto row = template_positions.at(edge.first);
        auto column = scene_positions.at(edge.second);
        if (template_chain.closed) row = cyclic_difference(row, template_cut, n);
        if (scene.closed) {
            column = match_case.direction == 1
                ? cyclic_difference(column, scene_cut, m)
                : cyclic_difference(scene_cut, column, m);
        } else if (match_case.direction == -1) {
            column = m - 1 - column;
        }
        transformed.push_back({row, column, edge});
    }
    std::sort(transformed.begin(), transformed.end(),
              [](const TransformedEdge& left, const TransformedEdge& right) {
                  return std::tie(left.row, left.column, left.edge) <
                         std::tie(right.row, right.column, right.edge);
              });
    std::vector<std::size_t> columns;
    columns.reserve(transformed.size());
    for (const auto& edge : transformed) columns.push_back(edge.column);
    std::sort(columns.begin(), columns.end());
    columns.erase(std::unique(columns.begin(), columns.end()), columns.end());
    if (columns.size() == std::numeric_limits<std::size_t>::max()) {
        throw std::overflow_error("Fenwick tree size exceeds size_t");
    }
    std::map<std::size_t, std::size_t> ranks;
    for (std::size_t rank = 0; rank < columns.size(); ++rank) {
        ranks.emplace(columns[rank], rank);
    }
    std::vector<std::size_t> tree(columns.size() + 1, 0);
    std::vector<State> states;
    states.push_back({Integer(0), Edge{0, 0}, 0});
    std::size_t best = 0;
    std::size_t cursor = 0;
    increment(work.case_count);
    while (cursor < transformed.size()) {
        std::size_t end = cursor + 1;
        const auto row = transformed[cursor].row;
        while (end < transformed.size() && transformed[end].row == row) ++end;
        std::vector<std::pair<std::size_t, std::size_t>> pending;
        pending.reserve(end - cursor);
        // Query every edge in this template row before publishing any state
        // from the row. A strict prefix excludes the current scene rank too.
        for (std::size_t edge_index = cursor; edge_index < end; ++edge_index) {
            const auto& edge = transformed[edge_index];
            const auto rank = ranks.at(edge.column);
            auto index = rank;  // Current column lives at rank+1 in the tree.
            std::size_t prefix = 0;
            increment(work.fenwick_queries);
            while (index != 0) {
                prefix = better(prefix, tree[index], states);
                increment(work.fenwick_query_visits);
                index -= index & (std::size_t{0} - index);
            }
            const auto weight_index = template_positions.at(edge.edge.first);
            // Materialize GMP expressions before states may reallocate.
            Integer score = states[prefix].score + template_chain.weights[weight_index];
            states.push_back({std::move(score), edge.edge, prefix});
            const auto state_index = states.size() - 1;
            increment(work.edge_states);
            work.maximum_integer_bits = std::max(
                work.maximum_integer_bits, integer_bits(states[state_index].score));
            pending.emplace_back(rank + 1, state_index);
            best = better(best, state_index, states);
        }
        for (const auto& update : pending) {
            auto index = update.first;
            increment(work.fenwick_updates);
            while (index < tree.size()) {
                tree[index] = better(tree[index], update.second, states);
                increment(work.fenwick_update_visits);
                const auto step = index & (std::size_t{0} - index);
                // The next position would leave the tree. Avoid even computing
                // an overflowing unsigned sum on extremely large index types.
                if (step >= tree.size() - index) break;
                index += step;
            }
        }
        cursor = end;
    }
    std::vector<Edge> witness;
    for (auto index = best; index != 0; index = states[index].predecessor) {
        witness.push_back(states[index].edge);
    }
    std::reverse(witness.begin(), witness.end());
    return {states[best].score, std::move(witness)};
}

}  // namespace detail

// Validate all supplied graph inputs before any empty/no-edge shortcut. IDs and
// bool flags have the declared C++ types; positive GMP weights, unique physical
// IDs and scene-chain IDs, unique edges and known endpoints are checked here.
// Each template chain chooses at most one complete scene chain. Independent
// support counts a template sample once across all scenes. Separate calls may
// reuse scene pixels, as the full-template contract permits. All arithmetic is
// exact; all diagnostic counter increments throw overflow_error on uint64 wrap.
inline MatchResult solve(const TemplateChain& supplied_template,
                         const std::vector<SceneChain>& supplied_scenes) {
    const auto validated = detail::validate(supplied_template, supplied_scenes);
    const auto& template_chain = validated.template_chain;
    const auto& scenes = validated.scene_chains;
    std::map<Id, std::size_t> template_positions;
    for (std::size_t index = 0; index < template_chain.sample_ids.size(); ++index) {
        template_positions.emplace(template_chain.sample_ids[index], index);
    }
    Integer total_weight = 0;
    for (const auto& weight : template_chain.weights) total_weight += weight;
    std::set<Id> supported;
    for (const auto& scene : scenes) {
        for (const Edge& edge : scene.edges) supported.insert(edge.first);
    }
    Integer independent = 0;
    for (Id sample : supported) {
        independent += template_chain.weights[template_positions.at(sample)];
    }
    WorkCounters work;
    work.maximum_integer_bits = detail::integer_bits(total_weight);
    Integer best_score = 0;
    std::optional<MatchCase> best_case;
    std::vector<Edge> best_witness;
    for (const auto& scene : scenes) {
        if (scene.edges.empty()) continue;
        std::map<Id, std::size_t> scene_positions;
        for (std::size_t index = 0; index < scene.pixel_ids.size(); ++index) {
            scene_positions.emplace(scene.pixel_ids[index], index);
        }
        std::vector<std::size_t> template_cuts{0};
        if (template_chain.closed && !scene.closed) {
            std::set<std::size_t> incident;
            for (const Edge& edge : scene.edges) {
                incident.insert(template_positions.at(edge.first));
            }
            template_cuts.assign(incident.begin(), incident.end());
        }
        std::vector<std::size_t> scene_cuts{0};
        if (scene.closed) {
            std::set<std::size_t> incident;
            for (const Edge& edge : scene.edges) {
                incident.insert(scene_positions.at(edge.second));
            }
            scene_cuts.assign(incident.begin(), incident.end());
        }
        const std::vector<int> directions = scene.pixel_ids.size() == 1
            ? std::vector<int>{1} : std::vector<int>{1, -1};
        // This is the declared case priority: scene ID, positive direction
        // first, template cut, scene cut. Equal scores never replace the first
        // winning case, even when a later case has a smaller witness.
        for (int direction : directions) {
            for (std::size_t template_cut : template_cuts) {
                for (std::size_t scene_cut : scene_cuts) {
                    const MatchCase match_case{
                        scene.chain_id, direction, detail::count_value(template_cut),
                        detail::count_value(scene_cut)};
                    auto candidate = detail::run_case(
                        template_chain, scene, match_case, template_positions,
                        scene_positions, work);
                    if (candidate.first > best_score) {
                        best_score = std::move(candidate.first);
                        best_case = match_case;
                        best_witness = std::move(candidate.second);
                    }
                }
            }
        }
    }
    return {template_chain.chain_id, std::move(best_score), std::move(independent),
            std::move(total_weight), best_case, std::move(best_witness), work};
}

}  // namespace ordered_contour_native

#endif  // ORDERED_CONTOUR_NATIVE_ORDERED_MATCH_HPP
