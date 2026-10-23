#ifndef ORDERED_CONTOUR_NATIVE_EDGE_CHAINS_HPP
#define ORDERED_CONTOUR_NATIVE_EDGE_CHAINS_HPP

// Typed native mathematical interface for supplied legal integer label grids.
// No images, OpenCV, decode, warp, gradient, matcher, file I/O or speed claim.
// The fixed-default stubs' coordinated ordinary RED was retained before this
// implementation. All pixel topology and sampling follow the Python contract.
#include <algorithm>
#include <array>
#include <cstddef>
#include <cstdint>
#include <limits>
#include <map>
#include <set>
#include <stdexcept>
#include <tuple>
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

namespace detail {

inline Id checked_count(std::size_t value) {
    if constexpr (sizeof(std::size_t) > sizeof(Id)) {
        if (value > static_cast<std::size_t>(std::numeric_limits<Id>::max())) {
            throw std::overflow_error("native edge count exceeds uint64");
        }
    }
    return static_cast<Id>(value);
}

inline void increment(Id& value) {
    if (value == std::numeric_limits<Id>::max()) {
        throw std::overflow_error("native edge count exceeds uint64");
    }
    ++value;
}

inline Integer exact_id(Id value) {
    // GMP's unsigned-long constructor is only 32-bit on Windows. Import the
    // complete native uint64 word rather than narrowing through unsigned long.
    Integer result;
    mpz_import(result.get_mpz_t(), 1, 1, sizeof(value), 0, 0, &value);
    return result;
}

struct Grid {
    LabelGrid labels;
    Id width;
    Id height;
};

inline Grid snapshot_grid(const LabelGrid& input) {
    if (input.empty() || input.front().empty()) {
        throw std::invalid_argument("label grid must have nonempty rows");
    }
    const auto row_size = input.front().size();
    for (const auto& row : input) {
        if (row.size() != row_size) throw std::invalid_argument("label grid must be rectangular");
        for (int label : row) {
            if (!((label >= 0 && label <= 7) || label == 255)) {
                throw std::invalid_argument("label must be0..7 or255");
            }
        }
    }
    const Id width = checked_count(row_size);
    const Id height = checked_count(input.size());
    // Check the largest y*width+x without computing an overflowing product.
    if (height - 1 > (std::numeric_limits<Id>::max() - (width - 1)) / width) {
        throw std::overflow_error("physical grid pixel ID exceeds uint64");
    }
    return {input, width, height};
}

inline constexpr std::array<std::pair<int, int>, 8> offsets{{
    {0, -1}, {1, -1}, {1, 0}, {1, 1},
    {0, 1}, {-1, 1}, {-1, 0}, {-1, -1}
}};

// No signed coordinate cast or unsigned negative offset is used at borders.
inline bool neighbor(Id pixel, int dx, int dy, Id width, Id height, Id& result) {
    Id x = pixel % width;
    Id y = pixel / width;
    if (dx < 0) {
        if (x == 0) return false;
        --x;
    } else if (dx > 0) {
        if (x == width - 1) return false;
        ++x;
    }
    if (dy < 0) {
        if (y == 0) return false;
        --y;
    } else if (dy > 0) {
        if (y == height - 1) return false;
        ++y;
    }
    result = y * width + x;
    return true;
}

using Active = std::set<Id>;

inline Active active_pixels(const Grid& grid) {
    Active result;
    for (std::size_t y = 0; y < grid.labels.size(); ++y) {
        for (std::size_t x = 0; x < grid.labels[y].size(); ++x) {
            if (grid.labels[y][x] != 255) {
                result.insert(checked_count(y) * grid.width + checked_count(x));
            }
        }
    }
    return result;
}

inline Active delete_batch(const Active& active, Id width, Id height, bool second) {
    Active deletions;
    for (Id pixel : active) {
        std::array<bool, 8> adjacent{};
        int count = 0;
        for (std::size_t i = 0; i < offsets.size(); ++i) {
            Id next = 0;
            adjacent[i] = neighbor(pixel, offsets[i].first, offsets[i].second,
                                   width, height, next) && active.find(next) != active.end();
            if (adjacent[i]) ++count;
        }
        if (count < 2 || count > 6) continue;
        int transitions = 0;
        for (std::size_t i = 0; i < adjacent.size(); ++i) {
            if (!adjacent[i] && adjacent[(i + 1) % adjacent.size()]) ++transitions;
        }
        if (transitions != 1) continue;
        const bool north = adjacent[0], east = adjacent[2];
        const bool south = adjacent[4], west = adjacent[6];
        const bool removable = second
            ? !(north && east && west) && !(north && south && west)
            : !(north && east && south) && !(east && south && west);
        if (removable) deletions.insert(pixel);
    }
    return deletions;
}

using GraphEdge = std::pair<Id, Id>;
using Adjacency = std::map<Id, std::vector<Id>>;

inline GraphEdge graph_edge(Id left, Id right) {
    return left < right ? GraphEdge{left, right} : GraphEdge{right, left};
}

inline std::vector<Id> canonical(const std::vector<Id>& pixels, bool closed) {
    if (!closed) {
        const std::vector<Id> reverse(pixels.rbegin(), pixels.rend());
        return std::min(pixels, reverse);
    }
    // Unique IDs imply every least rotation starts at the unique smallest ID.
    const auto minimum = std::min_element(pixels.begin(), pixels.end());
    std::vector<Id> forward;
    forward.reserve(pixels.size());
    forward.insert(forward.end(), minimum, pixels.end());
    forward.insert(forward.end(), pixels.begin(), minimum);
    std::vector<Id> backward;
    backward.reserve(pixels.size());
    backward.push_back(forward.front());
    for (std::size_t index = forward.size(); index > 1; --index) {
        backward.push_back(forward[index - 1]);
    }
    return std::min(forward, backward);
}

inline std::pair<std::vector<Id>, bool> walk(
        Id start, Id first_neighbor, const Adjacency& adjacency,
        std::set<GraphEdge>& used) {
    std::vector<Id> pixels{start};
    Id previous = start, current = first_neighbor;
    if (!used.insert(graph_edge(previous, current)).second) {
        throw std::logic_error("walk started on an already decomposed edge");
    }
    while (current != start) {
        pixels.push_back(current);
        const auto& following = adjacency.at(current);
        if (following.size() != 2) return {std::move(pixels), false};
        const Id next = following[1] == previous ? following[0] : following[1];
        if (!used.insert(graph_edge(current, next)).second) {
            throw std::logic_error("degree2 walk encountered an already decomposed edge");
        }
        previous = current;
        current = next;
    }
    // The closing edge is represented by closed, not by a second start ID.
    return {std::move(pixels), true};
}

inline unsigned int step(Id left, Id right, Id width) {
    const Id left_x = left % width, left_y = left / width;
    const Id right_x = right % width, right_y = right / width;
    const Id dx = left_x >= right_x ? left_x - right_x : right_x - left_x;
    const Id dy = left_y >= right_y ? left_y - right_y : right_y - left_y;
    if (dx > 1 || dy > 1 || (dx == 0 && dy == 0)) {
        throw std::invalid_argument("chain steps must be distinct eight-neighbor pixels");
    }
    return dx == 1 && dy == 1 ? 1414U : 1000U;
}

}  // namespace detail

// Typed int cannot distinguish an implicit bool/float conversion; a textual
// parser must validate its source domain before constructing LabelGrid values.
inline ThinningResult thin_labels(const LabelGrid& input) {
    const auto grid = detail::snapshot_grid(input);
    auto active = detail::active_pixels(grid);
    std::vector<DeletionRound> rounds;
    for (;;) {
        const auto first = detail::delete_batch(active, grid.width, grid.height, false);
        for (Id pixel : first) active.erase(pixel);
        const auto second = detail::delete_batch(active, grid.width, grid.height, true);
        for (Id pixel : second) active.erase(pixel);
        rounds.emplace_back(detail::checked_count(first.size()), detail::checked_count(second.size()));
        if (first.empty() && second.empty()) break;
    }
    LabelGrid labels = grid.labels;
    for (std::size_t y = 0; y < labels.size(); ++y) {
        for (std::size_t x = 0; x < labels[y].size(); ++x) {
            const Id pixel = detail::checked_count(y) * grid.width + detail::checked_count(x);
            if (active.find(pixel) == active.end()) labels[y][x] = 255;
        }
    }
    return {grid.width, grid.height, grid.labels, std::move(labels), std::move(rounds)};
}

// Decompose exactly the supplied graph; do not thin it or require a fixed point.
inline std::vector<Chain> extract_chains(const LabelGrid& input) {
    const auto grid = detail::snapshot_grid(input);
    const auto active = detail::active_pixels(grid);
    detail::Adjacency adjacency;
    for (Id pixel : active) {
        auto& adjacent = adjacency[pixel];
        for (const auto& offset : detail::offsets) {
            Id next = 0;
            if (detail::neighbor(pixel, offset.first, offset.second, grid.width, grid.height, next) &&
                active.find(next) != active.end()) {
                adjacent.push_back(next);
            }
        }
        std::sort(adjacent.begin(), adjacent.end());
    }
    std::set<detail::GraphEdge> used;
    std::vector<Chain> raw;
    for (Id start : active) {
        const auto& adjacent = adjacency.at(start);
        if (adjacent.empty()) {
            raw.push_back({0, {start}, false, false});
            continue;
        }
        if (adjacent.size() == 2) continue;
        for (Id next : adjacent) {
            if (used.find(detail::graph_edge(start, next)) != used.end()) continue;
            auto trail = detail::walk(start, next, adjacency, used);
            raw.push_back({0, detail::canonical(trail.first, trail.second), trail.second, trail.second});
        }
    }
    for (Id start : active) {
        const auto& adjacent = adjacency.at(start);
        for (Id next : adjacent) {
            if (used.find(detail::graph_edge(start, next)) != used.end()) continue;
            if (adjacent.size() != 2) {
                throw std::logic_error("unused edge remained incident to a junction");
            }
            auto trail = detail::walk(start, next, adjacency, used);
            if (!trail.second) throw std::logic_error("remaining degree2 component is not cyclic");
            raw.push_back({0, detail::canonical(trail.first, true), true, false});
        }
    }
    std::set<detail::GraphEdge> all_edges;
    for (const auto& row : adjacency) {
        for (Id next : row.second) all_edges.insert(detail::graph_edge(row.first, next));
    }
    if (used != all_edges) throw std::logic_error("chain decomposition lost graph edges");
    std::sort(raw.begin(), raw.end(), [](const Chain& left, const Chain& right) {
        return std::tie(left.pixel_ids, left.closed) < std::tie(right.pixel_ids, right.closed);
    });
    for (std::size_t index = 0; index < raw.size(); ++index) {
        raw[index].chain_id = detail::checked_count(index);
    }
    return raw;
}

// Validate local chain geometry, not maximality or provenance in a larger graph.
inline ChainSampling sample_chain(const Chain& supplied, Id width) {
    if (width == 0) throw std::invalid_argument("sampling width must be positive");
    const Chain chain = supplied;
    if (chain.returning && !chain.closed) {
        throw std::invalid_argument("a returning trail must be closed");
    }
    if (chain.pixel_ids.empty()) throw std::invalid_argument("chain must contain physical pixels");
    const std::set<Id> unique(chain.pixel_ids.begin(), chain.pixel_ids.end());
    if (unique.size() != chain.pixel_ids.size()) {
        throw std::invalid_argument("chain physical pixel IDs must be unique");
    }
    if (chain.closed && chain.pixel_ids.size() < 3) {
        throw std::invalid_argument("a closed graph cycle needs at least three physical pixels");
    }
    std::vector<Integer> cumulative;
    cumulative.reserve(chain.pixel_ids.size());
    cumulative.emplace_back(0);
    for (std::size_t index = 1; index < chain.pixel_ids.size(); ++index) {
        Integer next = cumulative.back() + detail::step(chain.pixel_ids[index - 1], chain.pixel_ids[index], width);
        cumulative.push_back(std::move(next));
    }
    Integer total = cumulative.back();
    if (chain.closed) total += detail::step(chain.pixel_ids.back(), chain.pixel_ids.front(), width);
    std::vector<bool> selected(chain.pixel_ids.size(), false);
    selected[0] = true;
    if (!chain.closed) selected.back() = true;
    std::size_t position = 1;
    for (Integer marker = 2000; marker < total; marker += 2000) {
        while (position < cumulative.size() && cumulative[position] < marker) ++position;
        selected[position < cumulative.size() ? position : 0] = true;
    }
    std::vector<Id> samples;
    for (std::size_t index = 0; index < chain.pixel_ids.size(); ++index) {
        if (selected[index]) samples.push_back(chain.pixel_ids[index]);
    }
    return {chain.chain_id, std::move(samples), std::move(total)};
}

// Factory evidence owns all vectors. An empty whole template is a contract
// failure; individual chains with zero owned samples keep their full records.
inline TemplateEvidence prepare_template(const LabelGrid& input) {
    auto thinning = thin_labels(input);
    auto chains = extract_chains(thinning.labels);
    std::vector<ChainSampling> samplings;
    samplings.reserve(chains.size());
    std::map<Id, std::vector<Id>> memberships;
    std::map<std::pair<Id, Id>, Id> positions;
    for (const auto& chain : chains) {
        samplings.push_back(sample_chain(chain, thinning.width));
        for (Id pixel : samplings.back().pixel_ids) memberships[pixel].push_back(chain.chain_id);
        for (std::size_t index = 0; index < chain.pixel_ids.size(); ++index) {
            positions.emplace(std::make_pair(chain.chain_id, chain.pixel_ids[index]),
                              detail::checked_count(index));
        }
    }
    if (memberships.empty()) throw std::invalid_argument("template has no owned samples after thinning");
    std::vector<SampleOwnership> ownership;
    ownership.reserve(memberships.size());
    for (auto& row : memberships) {
        std::sort(row.second.begin(), row.second.end());
        ownership.push_back({row.first, row.second.front(), row.second});
    }
    Id xmin = std::numeric_limits<Id>::max(), ymin = std::numeric_limits<Id>::max();
    Id xmax = 0, ymax = 0;
    for (const auto& row : ownership) {
        const Id x = row.pixel_id % thinning.width, y = row.pixel_id / thinning.width;
        xmin = std::min(xmin, x); xmax = std::max(xmax, x);
        ymin = std::min(ymin, y); ymax = std::max(ymax, y);
    }
    // Coordinates are smaller than their positive uint64 grid dimensions, so
    // these inclusive spans cannot wrap. The multiplication by4 uses GMP.
    const Id span_x = xmax - xmin + 1, span_y = ymax - ymin + 1;
    std::array<Id, 16> cell_counts{};
    std::map<Id, int> cells;
    for (const auto& row : ownership) {
        const Id x = row.pixel_id % thinning.width, y = row.pixel_id / thinning.width;
        const Integer col = (detail::exact_id(x - xmin) * 4) / detail::exact_id(span_x);
        const Integer cell_row = (detail::exact_id(y - ymin) * 4) / detail::exact_id(span_y);
        const int cell = static_cast<int>(cell_row.get_ui()) * 4 + static_cast<int>(col.get_ui());
        cells.emplace(row.pixel_id, cell);
        detail::increment(cell_counts[static_cast<std::size_t>(cell)]);
    }
    Integer common = 1;
    Id occupied = 0;
    for (Id count : cell_counts) {
        if (count == 0) continue;
        detail::increment(occupied);
        const Integer divisor = detail::exact_id(count);
        mpz_lcm(common.get_mpz_t(), common.get_mpz_t(), divisor.get_mpz_t());
    }
    std::vector<WeightedSample> samples;
    samples.reserve(ownership.size());
    Integer sum = 0;
    for (const auto& row : ownership) {
        const Id x = row.pixel_id % thinning.width, y = row.pixel_id / thinning.width;
        const int cell = cells.at(row.pixel_id);
        Integer weight = common / detail::exact_id(cell_counts[static_cast<std::size_t>(cell)]);
        sum += weight;
        samples.push_back({row.pixel_id, row.owner_chain_id,
            positions.at(std::make_pair(row.owner_chain_id, row.pixel_id)), x, y,
            thinning.labels[static_cast<std::size_t>(y)][static_cast<std::size_t>(x)],
            cell, std::move(weight)});
    }
    Integer denominator = common * detail::exact_id(occupied);
    if (sum != denominator) throw std::logic_error("exact cell weights do not sum to denominator");
    return {std::move(thinning), std::move(chains), std::move(samplings),
            std::move(ownership), std::move(samples), cell_counts, occupied,
            std::move(common), std::move(denominator)};
}

}  // namespace ordered_contour_native::edge

#endif  // ORDERED_CONTOUR_NATIVE_EDGE_CHAINS_HPP
