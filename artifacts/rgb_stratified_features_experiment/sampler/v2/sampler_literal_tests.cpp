#include "stratified_sampler.hpp"

#include <algorithm>
#include <cstdint>
#include <cstring>
#include <functional>
#include <iostream>
#include <limits>
#include <stdexcept>
#include <string>
#include <vector>

namespace ss = industrial_stratified;
namespace {
std::uint64_t assertions = 0;
std::uint64_t cases = 0;

void require(bool condition, const char* message) {
    ++assertions;
    if (!condition) throw std::runtime_error(message);
}

std::uint32_t bits(float value) {
    std::uint32_t result = 0;
    static_assert(sizeof(value) == sizeof(result), "float32 required");
    std::memcpy(&result, &value, sizeof(result));
    return result;
}

ss::Candidate c(std::uint64_t ordinal, std::int32_t x, std::int32_t y,
                float magnitude, ss::Stratum stratum) {
    return ss::Candidate{ordinal, x, y, static_cast<std::uint8_t>(ordinal % 8),
                         static_cast<std::uint32_t>(0x3f800000U + ordinal),
                         bits(magnitude), stratum};
}

std::vector<ss::Candidate> square() {
    return {c(0, 0, 0, 10, ss::Stratum::contour),
            c(1, 10, 0, 9, ss::Stratum::interior),
            c(2, 0, 10, 8, ss::Stratum::contour),
            c(3, 10, 10, 7, ss::Stratum::interior),
            c(4, 5, 5, 6, ss::Stratum::contour),
            c(5, 20, 0, 5, ss::Stratum::interior)};
}

void expected(const ss::Result& result, std::initializer_list<std::uint64_t> ordinals) {
    require(result.status == ss::Status::ok, "successful status required");
    require(result.selected.size() == ordinals.size(), "literal selection length differs");
    std::size_t index = 0;
    for (const auto ordinal : ordinals) {
        require(result.selected[index].ordinal == ordinal, "literal selected ordinal differs");
        ++index;
    }
}

bool equal(const ss::Candidate& a, const ss::Candidate& b) {
    return a.ordinal == b.ordinal && a.x == b.x && a.y == b.y && a.label == b.label &&
           a.theta_bits == b.theta_bits && a.magnitude_bits == b.magnitude_bits && a.stratum == b.stratum;
}

template<class Exception>
void rejected(const std::function<void()>& operation, const char* message) {
    bool rejected_as_expected = false;
    try { operation(); }
    catch (const Exception&) { rejected_as_expected = true; }
    require(rejected_as_expected, message);
}

void insufficient_pools() {
    for (const auto count : {std::size_t(0), std::size_t(1), std::size_t(4)}) {
        auto pool = square();
        pool.resize(count);
        for (const auto mode : {ss::Mode::pooled, ss::Mode::balanced}) {
            const auto result = ss::sample(pool, 32, mode);
            require(result.status == ss::Status::insufficient_features, "N<=4 must retain failure");
            require(result.selected.empty(), "failed layer must serialize no features");
            require(result.diagnostics.target == count, "target must still be recorded on failure");
        }
    }
}

void literal_pooled() {
    expected(ss::sample(square(), 4, ss::Mode::pooled), {0, 5, 3, 1});
}

void literal_balanced() {
    const auto result = ss::sample(square(), 4, ss::Mode::balanced);
    expected(result, {0, 5, 2, 1});
    require(result.diagnostics.initial_contour_quota == 2 && result.diagnostics.initial_interior_quota == 2,
            "balanced quotas must begin half/half");
    require(result.diagnostics.selected_contour == 2 && result.diagnostics.selected_interior == 2,
            "balanced quotas must be fulfilled");
    require(result.trace[1].minimum_squared_distance == 400, "distance must include other stratum's first feature");
    require(!result.trace[0].has_distance && result.trace[1].has_distance, "first step has no distance score");
}

void target_not_requested_budget() {
    auto pool = square(); pool.pop_back();
    const auto result = ss::sample(pool, 32, ss::Mode::balanced);
    expected(result, {0, 3, 2, 1, 4});
    require(result.diagnostics.target == 5, "target must be min(K,N)");
    require(result.diagnostics.initial_contour_quota == 3 && result.diagnostics.initial_interior_quota == 2,
            "small-pool quotas must use target, not requested budget");
}

void interior_shortage() {
    auto pool = square();
    for (auto& item : pool) item.stratum = ss::Stratum::contour;
    pool[1].stratum = ss::Stratum::interior;
    const auto result = ss::sample(pool, 4, ss::Mode::balanced);
    expected(result, {0, 1, 2, 3});
    require(result.diagnostics.final_contour_quota == 3 && result.diagnostics.final_interior_quota == 1,
            "interior deficit must transfer to contour");
    require(result.diagnostics.borrowed_into_contour == 1 && result.diagnostics.borrowed_into_interior == 0,
            "interior shortage diagnostics differ");
}

void contour_shortage() {
    auto pool = square();
    for (auto& item : pool) item.stratum = ss::Stratum::interior;
    pool[0].stratum = ss::Stratum::contour;
    const auto result = ss::sample(pool, 5, ss::Mode::balanced);
    expected(result, {0, 5, 3, 1, 2});
    require(result.diagnostics.final_contour_quota == 1 && result.diagnostics.final_interior_quota == 4,
            "contour deficit must transfer to interior");
    require(result.diagnostics.borrowed_into_interior == 2 && result.diagnostics.borrowed_into_contour == 0,
            "contour shortage diagnostics differ");
}

void empty_stratum_reduces_to_pooled() {
    for (const auto stratum : {ss::Stratum::contour, ss::Stratum::interior}) {
        auto pool = square();
        for (auto& item : pool) item.stratum = stratum;
        const auto result = ss::sample(pool, 4, ss::Mode::balanced);
        expected(result, {0, 5, 3, 1});
        require(result.diagnostics.empty_contour == (stratum == ss::Stratum::interior), "empty contour flag differs");
        require(result.diagnostics.empty_interior == (stratum == ss::Stratum::contour), "empty interior flag differs");
    }
}

void magnitude_ordinal_and_float32_ties() {
    auto pool = std::vector<ss::Candidate>{c(10, 2, 2, 1, ss::Stratum::contour),
        c(3, 2, 2, 1, ss::Stratum::interior), c(2, 2, 2, 1, ss::Stratum::contour),
        c(7, 2, 2, 1, ss::Stratum::interior), c(1, 2, 2, 0, ss::Stratum::contour)};
    pool[1].magnitude_bits = 0x3f800001U;
    pool[3].magnitude_bits = 0x3f7fffffU;
    expected(ss::sample(pool, 5, ss::Mode::pooled), {3, 2, 10, 7, 1});
    for (auto& item : pool) item.magnitude_bits = 0;
    pool[2].magnitude_bits = 0x80000000U;
    expected(ss::sample(pool, 5, ss::Mode::pooled), {1, 2, 3, 7, 10});
}

void immutable_pool_and_exact_bits() {
    auto pool = square();
    pool[0].theta_bits = 0x7fc12345U;  // Opaque theta payload is never reinterpreted or canonicalized.
    const auto before = pool;
    const auto result = ss::sample(pool, 4, ss::Mode::balanced);
    require(pool.size() == before.size(), "input length changed");
    for (std::size_t i = 0; i != pool.size(); ++i) require(equal(pool[i], before[i]), "input bytes changed");
    for (std::size_t i = 0; i != result.selected.size(); ++i)
        require(equal(result.selected[i], pool[result.selected_indices[i]]), "selected fields were not copied exactly");
    require(result.selected[0].theta_bits == 0x7fc12345U, "theta payload must remain opaque bits");
}

void translated_absolute_coordinates() {
    auto pool = square();
    for (auto& item : pool) { item.x -= 1321; item.y += 247; }
    expected(ss::sample(pool, 4, ss::Mode::balanced), {0, 5, 2, 1});
}

void sixteen_literal_and_large_cardinalities() {
    std::vector<ss::Candidate> pool;
    for (std::uint64_t i = 0; i < 16; ++i) pool.push_back(c(i, static_cast<std::int32_t>(i), 0, 1, ss::Stratum::contour));
    std::reverse(pool.begin(), pool.end());
    expected(ss::sample(pool, 16, ss::Mode::pooled), {0,15,7,11,3,5,9,13,1,2,4,6,8,10,12,14});
    for (const auto n : {32, 50}) {
        pool.clear();
        for (int i = 0; i < n; ++i) pool.push_back(c(static_cast<std::uint64_t>(i), i, i % 3, 1, ss::Stratum::interior));
        const auto result = ss::sample(pool, 32, ss::Mode::balanced);
        require(result.selected.size() == 32, "requested32 must not overfill");
        std::vector<std::uint64_t> ordinals;
        for (const auto& item : result.selected) ordinals.push_back(item.ordinal);
        std::sort(ordinals.begin(), ordinals.end());
        require(std::adjacent_find(ordinals.begin(), ordinals.end()) == ordinals.end(), "selection reuses ordinal");
    }
}

void rejects_duplicate_ordinal() {
    auto pool = square(); pool[5].ordinal = pool[0].ordinal;
    rejected<std::invalid_argument>([&] { ss::sample(pool, 4, ss::Mode::pooled); }, "duplicate ordinal accepted");
}

void rejects_nonfinite_magnitude() {
    for (const auto value : {0x7f800000U, 0xff800000U, 0x7fc12345U}) {
        auto pool = square(); pool[2].magnitude_bits = value;
        rejected<std::invalid_argument>([&] { ss::sample(pool, 4, ss::Mode::pooled); }, "nonfinite magnitude accepted");
    }
}

void rejects_invalid_label_stratum_mode_and_budget() {
    auto pool = square(); pool[0].label = 8;
    rejected<std::invalid_argument>([&] { ss::sample(pool, 4, ss::Mode::pooled); }, "invalid label accepted");
    pool = square(); pool[0].stratum = static_cast<ss::Stratum>(2);
    rejected<std::invalid_argument>([&] { ss::sample(pool, 4, ss::Mode::pooled); }, "invalid stratum accepted");
    pool = square();
    rejected<std::invalid_argument>([&] { ss::sample(pool, 0, ss::Mode::pooled); }, "zero budget accepted");
    rejected<std::invalid_argument>([&] { ss::sample(pool, 4, static_cast<ss::Mode>(2)); }, "invalid mode accepted");
}

// Catch replacing the signed-int64 bound with an unsigned-int64 bound.
void checked_signed_axial_bound() {
    const auto low = std::numeric_limits<std::int32_t>::min();
    const auto high = std::numeric_limits<std::int32_t>::max();
    const auto origin = c(0, low, 0, 1, ss::Stratum::contour);
    const auto safe = c(1, 889516851, 0, 1, ss::Stratum::contour);
    // Difference 3037000499; its square is below INT64_MAX.
    require(ss::squared_distance(origin, safe) == 9223372030926249001LL,
            "largest safe axial square differs");
    require(ss::squared_distance(safe, origin) == 9223372030926249001LL,
            "signed distance must be symmetric");
    rejected<std::overflow_error>([&] {
        ss::squared_distance(origin, c(1, high, 0, 1, ss::Stratum::contour));
    }, "full int32 axial distance above INT64_MAX accepted");
    rejected<std::overflow_error>([&] {
        ss::squared_distance(origin, c(1, 889516852, 0, 1, ss::Stratum::contour));
    }, "first unsafe axial square accepted");
}

// Catch checking each component but adding two safe squares without a bound.
void checked_signed_sum_bound() {
    const auto low = std::numeric_limits<std::int32_t>::min();
    const auto high = std::numeric_limits<std::int32_t>::max();
    require(ss::squared_distance(c(0, 0, 0, 1, ss::Stratum::contour),
                                 c(1, high, high, 1, ss::Stratum::contour)) == 9223372028264841218LL,
            "safe diagonal square differs");
    require(ss::squared_distance(c(0, -17, 29, 1, ss::Stratum::contour),
                                 c(1, -17, 29, 1, ss::Stratum::interior)) == 0,
            "duplicate signed coordinates must have zero distance");
    rejected<std::overflow_error>([&] {
        ss::squared_distance(c(0, low, low, 1, ss::Stratum::contour),
                             c(1, 0, 0, 1, ss::Stratum::contour));
    }, "sum exactly INT64_MAX plus one accepted");
    rejected<std::overflow_error>([&] {
        ss::squared_distance(c(0, low, low, 1, ss::Stratum::contour),
                             c(1, high, high, 1, ss::Stratum::contour));
    }, "full int32 diagonal distance above INT64_MAX accepted");
}

// Catch bypassing the checked distance function in the actual sampler.
void checked_selection_distance_overflow() {
    auto pool = square();
    pool[0].x = std::numeric_limits<std::int32_t>::min();
    pool[1].x = std::numeric_limits<std::int32_t>::max();
    rejected<std::overflow_error>([&] { ss::sample(pool, 4, ss::Mode::balanced); },
            "selection signed distance overflow accepted");
}

// Catch imposing canonical-file uint32 limits or nonnegative/theta-finite gates on the pure API.
void opaque_theta_negative_finite_and_wide_ordinals() {
    auto pool = square();
    pool[0].ordinal = std::numeric_limits<std::uint64_t>::max();
    pool[0].magnitude_bits = bits(-1.0F);
    pool[0].theta_bits = 0xff800001U;
    const auto result = ss::sample(pool, 6, ss::Mode::pooled);
    expected(result, {1, 2, 3, 5, std::numeric_limits<std::uint64_t>::max(), 4});
    require(result.selected[4].magnitude_bits == bits(-1.0F), "finite negative magnitude changed");
    require(result.selected[4].theta_bits == 0xff800001U, "opaque theta payload changed");
}

void arbitrary_input_order_preserves_tie_contract() {
    auto pool = square();
    std::rotate(pool.begin(), pool.begin() + 3, pool.end());
    expected(ss::sample(pool, 4, ss::Mode::pooled), {0,5,3,1});
    expected(ss::sample(pool, 4, ss::Mode::balanced), {0,5,2,1});
}

}  // namespace

int main() {
    try {
        for (const auto& test : std::vector<std::function<void()>>{
                 checked_signed_axial_bound, checked_signed_sum_bound, checked_selection_distance_overflow,
                 insufficient_pools, literal_pooled, literal_balanced, target_not_requested_budget,
                 interior_shortage, contour_shortage, empty_stratum_reduces_to_pooled,
                 magnitude_ordinal_and_float32_ties, immutable_pool_and_exact_bits,
                 translated_absolute_coordinates, sixteen_literal_and_large_cardinalities,
                 rejects_duplicate_ordinal, rejects_nonfinite_magnitude,
                 rejects_invalid_label_stratum_mode_and_budget, opaque_theta_negative_finite_and_wide_ordinals,
                 arbitrary_input_order_preserves_tie_contract}) {
            test(); ++cases;
        }
        std::cout << "{\"passed\":true,\"cases\":" << cases << ",\"assertions\":" << assertions
                  << ",\"image_decodes\":0,\"matcher_calls\":0}\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "literal test failure after " << cases << " cases and " << assertions
                  << " assertions: " << error.what() << '\n';
        return 1;
    }
}
