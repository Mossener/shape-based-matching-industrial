#ifndef INDUSTRIAL_STRATIFIED_SAMPLER_HPP
#define INDUSTRIAL_STRATIFIED_SAMPLER_HPP

#include <algorithm>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <limits>
#include <set>
#include <stdexcept>
#include <vector>

namespace industrial_stratified {

enum class Stratum : std::uint8_t { contour = 0, interior = 1 };
enum class Mode : std::uint8_t { pooled = 0, balanced = 1 };
enum class Status : std::uint8_t { ok = 0, insufficient_features = 1 };

struct Candidate {
    std::uint64_t ordinal;
    std::int32_t x;
    std::int32_t y;
    std::uint8_t label;
    std::uint32_t theta_bits;
    std::uint32_t magnitude_bits;
    Stratum stratum;
};

struct Diagnostics {
    std::size_t input_candidates = 0;
    std::size_t requested_budget = 0;
    std::size_t target = 0;
    std::size_t contour_candidates = 0;
    std::size_t interior_candidates = 0;
    bool empty_contour = true;
    bool empty_interior = true;
    bool quotas_apply = false;
    std::size_t initial_contour_quota = 0;
    std::size_t initial_interior_quota = 0;
    std::size_t final_contour_quota = 0;
    std::size_t final_interior_quota = 0;
    std::size_t borrowed_into_contour = 0;
    std::size_t borrowed_into_interior = 0;
    std::size_t selected_contour = 0;
    std::size_t selected_interior = 0;
};

struct SelectionStep {
    std::uint64_t ordinal;
    Stratum stratum;
    bool has_distance;
    std::uint64_t minimum_squared_distance;
};

struct Result {
    Status status = Status::insufficient_features;
    Diagnostics diagnostics;
    std::vector<std::size_t> selected_indices;
    std::vector<Candidate> selected;
    std::vector<SelectionStep> trace;
};

inline float magnitude(const Candidate& candidate) {
    float value = 0;
    static_assert(sizeof(value) == sizeof(candidate.magnitude_bits), "IEEE float32 storage required");
    static_assert(std::numeric_limits<float>::is_iec559, "IEEE float32 arithmetic required");
    std::memcpy(&value, &candidate.magnitude_bits, sizeof(value));
    return value;
}

// Coordinates are signed int32. Their differences fit int64; squared distances
// use checked uint64 so the full axial int32 range remains representable.
inline std::uint64_t squared_distance(const Candidate& left, const Candidate& right) {
    const std::int64_t dx = static_cast<std::int64_t>(left.x) - static_cast<std::int64_t>(right.x);
    const std::int64_t dy = static_cast<std::int64_t>(left.y) - static_cast<std::int64_t>(right.y);
    const auto ax = static_cast<std::uint64_t>(dx < 0 ? -dx : dx);
    const auto ay = static_cast<std::uint64_t>(dy < 0 ? -dy : dy);
    const auto maximum = std::numeric_limits<std::uint64_t>::max();
    if ((ax != 0 && ax > maximum / ax) || (ay != 0 && ay > maximum / ay))
        throw std::overflow_error("squared coordinate difference exceeds uint64");
    const auto x2 = ax * ax;
    const auto y2 = ay * ay;
    if (x2 > maximum - y2)
        throw std::overflow_error("squared Euclidean distance exceeds uint64");
    return x2 + y2;
}

namespace detail {
inline bool prefer_magnitude_ordinal(const Candidate& left, const Candidate& right) {
    const auto left_magnitude = magnitude(left);
    const auto right_magnitude = magnitude(right);
    if (left_magnitude != right_magnitude) return left_magnitude > right_magnitude;
    return left.ordinal > right.ordinal;
}

inline Stratum other(Stratum stratum) {
    return stratum == Stratum::contour ? Stratum::interior : Stratum::contour;
}
}  // namespace detail

inline Result sample(const std::vector<Candidate>& pool, std::size_t budget, Mode mode) {
    if (budget == 0) throw std::invalid_argument("feature budget must be positive");
    if (mode != Mode::pooled && mode != Mode::balanced) throw std::invalid_argument("unknown sampling mode");

    Result result;
    auto& d = result.diagnostics;
    d.input_candidates = pool.size();
    d.requested_budget = budget;
    d.target = std::min(budget, pool.size());
    d.quotas_apply = mode == Mode::balanced;
    std::set<std::uint64_t> ordinals;
    for (const auto& candidate : pool) {
        if (candidate.stratum != Stratum::contour && candidate.stratum != Stratum::interior)
            throw std::invalid_argument("unknown candidate stratum");
        if (candidate.label > 7) throw std::invalid_argument("candidate label must be in [0,7]");
        if (!std::isfinite(magnitude(candidate))) throw std::invalid_argument("candidate magnitude must be finite");
        if (!ordinals.insert(candidate.ordinal).second) throw std::invalid_argument("candidate ordinal must be unique");
        if (candidate.stratum == Stratum::contour) ++d.contour_candidates;
        else ++d.interior_candidates;
    }
    d.empty_contour = d.contour_candidates == 0;
    d.empty_interior = d.interior_candidates == 0;

    if (mode == Mode::balanced) {
        d.initial_contour_quota = d.target / 2 + d.target % 2;
        d.initial_interior_quota = d.target / 2;
        d.final_contour_quota = d.initial_contour_quota;
        d.final_interior_quota = d.initial_interior_quota;
        if (d.final_contour_quota > d.contour_candidates) {
            d.borrowed_into_interior = d.final_contour_quota - d.contour_candidates;
            d.final_contour_quota = d.contour_candidates;
            d.final_interior_quota += d.borrowed_into_interior;
        }
        if (d.final_interior_quota > d.interior_candidates) {
            d.borrowed_into_contour = d.final_interior_quota - d.interior_candidates;
            d.final_interior_quota = d.interior_candidates;
            d.final_contour_quota += d.borrowed_into_contour;
        }
        if (d.final_contour_quota > d.contour_candidates || d.final_interior_quota > d.interior_candidates ||
            d.final_contour_quota + d.final_interior_quota != d.target)
            throw std::logic_error("quota capacity invariant failed");
    }
    if (pool.size() <= 4) return result;

    result.status = Status::ok;
    result.selected.reserve(d.target);
    result.selected_indices.reserve(d.target);
    result.trace.reserve(d.target);
    std::vector<unsigned char> selected(pool.size(), 0);
    std::vector<std::uint64_t> minimum_distance(pool.size(), std::numeric_limits<std::uint64_t>::max());
    auto next_requested = Stratum::contour;
    while (result.selected.size() < d.target) {
        auto requested = next_requested;
        if (mode == Mode::balanced) {
            const auto fulfilled = [&](Stratum stratum) {
                return stratum == Stratum::contour ? d.selected_contour == d.final_contour_quota
                                                  : d.selected_interior == d.final_interior_quota;
            };
            if (fulfilled(requested)) requested = detail::other(requested);
            if (fulfilled(requested)) throw std::logic_error("no quota remains before target fulfilled");
            next_requested = detail::other(requested);
        }
        auto best = pool.size();
        const bool has_distance = !result.selected.empty();
        for (std::size_t i = 0; i < pool.size(); ++i) {
            if (selected[i] || (mode == Mode::balanced && pool[i].stratum != requested)) continue;
            if (best == pool.size() ||
                (has_distance && minimum_distance[i] > minimum_distance[best]) ||
                ((!has_distance || minimum_distance[i] == minimum_distance[best]) &&
                 detail::prefer_magnitude_ordinal(pool[i], pool[best]))) best = i;
        }
        if (best == pool.size()) throw std::logic_error("candidate capacity invariant failed");
        selected[best] = 1;
        result.selected_indices.push_back(best);
        result.selected.push_back(pool[best]);
        result.trace.push_back(SelectionStep{pool[best].ordinal, pool[best].stratum, has_distance,
                                             has_distance ? minimum_distance[best] : 0});
        if (pool[best].stratum == Stratum::contour) ++d.selected_contour;
        else ++d.selected_interior;
        if (result.selected.size() == d.target) break;
        for (std::size_t i = 0; i < pool.size(); ++i)
            if (!selected[i]) minimum_distance[i] = std::min(minimum_distance[i], squared_distance(pool[i], pool[best]));
    }
    return result;
}

}  // namespace industrial_stratified

#endif
