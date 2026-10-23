// Literal supplied-grid regressions written before native adapter behavior.
// No Python/reference oracle, images, detector, native timing, or production.
#include "native_candidate_compatibility.hpp"

#include <algorithm>
#include <exception>
#include <functional>
#include <iostream>
#include <limits>
#include <stdexcept>
#include <string>

namespace n = ordered_contour_native;
namespace e = ordered_contour_native::edge;
namespace c = ordered_contour_native::candidate;
using n::Edge;
using n::Id;
using n::Integer;
using e::LabelGrid;

namespace {

constexpr c::Coordinate minimum = std::numeric_limits<c::Coordinate>::min();
constexpr c::Coordinate maximum = std::numeric_limits<c::Coordinate>::max();

LabelGrid grid(std::size_t width, std::size_t height,
               const std::vector<Id>& foreground, int label = 0) {
    LabelGrid result(height, std::vector<int>(width, 255));
    for (Id pixel : foreground) {
        result[static_cast<std::size_t>(pixel / width)]
              [static_cast<std::size_t>(pixel % width)] = label;
    }
    return result;
}

c::CandidateScore singleton(const LabelGrid& scene = {{0}},
                            const c::Point& tl = {0, 0},
                            const c::Point& match = {0, 0},
                            const c::Padding& padding = {0, 0, 0, 0},
                            const LabelGrid& templ = {{0}}) {
    return c::score_candidate(e::prepare_template(templ), c::prepare_scene(scene),
                              tl, match, padding);
}

struct Harness {
    std::size_t tests = 0, checks = 0, failures = 0, errors = 0;
    std::string current;

    void check(bool condition, const std::string& detail) {
        ++checks;
        if (!condition) {
            ++failures;
            std::cerr << "FAIL " << current << ": " << detail << '\n';
        }
    }

    template<class A, class B>
    void equal(const A& actual, const B& expected, const std::string& field) {
        ++checks;
        const A converted_expected(expected);
        if (actual != converted_expected) {
            ++failures;
            std::cerr << "FAIL " << current << ": " << field
                      << " expected=" << expected << " actual=" << actual << '\n';
        }
    }

    void totals(const c::CandidateScore& value, const Integer& independent,
                const Integer& ordered, const Integer& denominator) {
        equal(value.independent_numerator, independent, "A");
        equal(value.ordered_numerator, ordered, "B");
        equal(value.denominator, denominator, "D");
        check(0 <= value.ordered_numerator &&
              value.ordered_numerator <= value.independent_numerator &&
              value.independent_numerator <= value.denominator, "0<=B<=A<=D");
        equal(value.independent_accepted, 20 * independent >= 13 * denominator,
              "independent exact threshold");
        equal(value.ordered_accepted, 20 * ordered >= 13 * denominator,
              "ordered exact threshold");
    }

    void supports(const std::vector<c::SampleSupport>& actual,
                  const std::vector<c::SampleSupport>& expected) {
        equal(actual.size(), expected.size(), "support row count");
        for (std::size_t index = 0; index < std::min(actual.size(), expected.size()); ++index) {
            const auto& row = actual[index];
            const auto& target = expected[index];
            equal(row.sample_id, target.sample_id, "support sample ID");
            check(row.p_canvas == target.p_canvas, "p_canvas");
            check(row.relative == target.relative, "relative");
            check(row.q_padded == target.q_padded, "q_padded");
            check(row.q_original == target.q_original, "q_original");
            equal(row.padded_in_bounds, target.padded_in_bounds, "padded bounds");
            equal(row.original_in_bounds, target.original_in_bounds, "original bounds");
            check(row.compatible_pixel_ids == target.compatible_pixel_ids, "all compatible IDs");
            check(row.independent_witness == target.independent_witness, "support A witness");
        }
    }

    void memberships(const std::vector<c::ScenePixelMembership>& actual,
                     const std::vector<c::ScenePixelMembership>& expected) {
        equal(actual.size(), expected.size(), "membership physical row count");
        for (std::size_t index = 0; index < std::min(actual.size(), expected.size()); ++index) {
            equal(actual[index].pixel_id, expected[index].pixel_id, "membership pixel");
            equal(actual[index].members.size(), expected[index].members.size(), "membership count");
            for (std::size_t member = 0;
                 member < std::min(actual[index].members.size(), expected[index].members.size()); ++member) {
                equal(actual[index].members[member].chain_id,
                      expected[index].members[member].chain_id, "member chain ID");
                equal(actual[index].members[member].chain_index,
                      expected[index].members[member].chain_index, "member full-chain index");
            }
        }
    }

    void match(const n::MatchResult& actual, Id chain_id, const Integer& numerator,
               const Integer& independent, const Integer& total,
               const std::optional<n::MatchCase>& selected_case,
               const std::vector<Edge>& witness) {
        equal(actual.template_chain_id, chain_id, "match template chain ID");
        equal(actual.numerator, numerator, "match B");
        equal(actual.independent_numerator, independent, "match A");
        equal(actual.total_weight, total, "match denominator contribution");
        check(actual.selected_case.has_value() == selected_case.has_value(), "case presence");
        if (actual.selected_case && selected_case) {
            equal(actual.selected_case->scene_chain_id, selected_case->scene_chain_id, "scene chain ID");
            equal(actual.selected_case->direction, selected_case->direction, "case direction");
            equal(actual.selected_case->template_cut, selected_case->template_cut, "template cut");
            equal(actual.selected_case->scene_cut, selected_case->scene_cut, "scene cut");
        }
        check(actual.witness == witness, "complete original-ID B witness order");
    }

    void zero_work(const n::WorkCounters& work) {
        equal(work.case_count, 0, "zero-owned cases");
        equal(work.edge_states, 0, "zero-owned edge states");
        equal(work.fenwick_queries, 0, "zero-owned queries");
        equal(work.fenwick_updates, 0, "zero-owned updates");
        equal(work.fenwick_query_visits, 0, "zero-owned query visits");
        equal(work.fenwick_update_visits, 0, "zero-owned update visits");
        equal(work.maximum_integer_bits, 0, "zero-owned integer bits");
    }

    void invalid(const std::function<void()>& body) {
        bool rejected = false;
        try {
            body();
        } catch (const std::invalid_argument&) {
            rejected = true;
        } catch (const std::exception& exception) {
            check(false, std::string("wrong exception type: ") + exception.what());
            return;
        } catch (...) {
            check(false, "wrong nonstandard exception type");
            return;
        }
        check(rejected, "expected std::invalid_argument");
    }

    void run(const std::string& name, const std::function<void()>& body) {
        ++tests;
        current = name;
        const auto before = failures + errors;
        try {
            body();
        } catch (const std::exception& exception) {
            ++errors;
            std::cerr << "ERROR " << current << ": " << exception.what() << '\n';
        } catch (...) {
            ++errors;
            std::cerr << "ERROR " << current << ": nonstandard exception\n";
        }
        if (before == failures + errors) std::cout << "PASS " << current << '\n';
    }
};

}  // namespace

int main() {
    Harness h;

    h.run("scene_factory_thins_before_extracting_and_supporting", [&] {
        const auto scene = c::prepare_scene({{0, 0}, {0, 0}});
        h.check(scene.thinning.eligible_labels == LabelGrid{{0, 0}, {0, 0}}, "eligible labels retained");
        h.check(scene.thinning.labels == LabelGrid{{255, 255}, {255, 255}}, "tiny component erased");
        h.check(scene.chains.empty(), "no erased scene chain");
        h.check(scene.memberships.empty(), "no erased membership");
        h.totals(singleton({{0, 0}, {0, 0}}), 0, 0, 1);
    });

    h.run("scene_memberships_index_all_vertices_including_unsampled_ones", [&] {
        const auto scene = c::prepare_scene({{0, 0, 0, 0, 0}});
        h.equal(scene.chains.size(), 1, "one full scene chain");
        if (!scene.chains.empty()) {
            h.check(scene.chains[0].pixel_ids == std::vector<Id>{0, 1, 2, 3, 4}, "complete scene topology");
        }
        h.memberships(scene.memberships, {{0, {{0, 0}}}, {1, {{0, 1}}}, {2, {{0, 2}}},
                                         {3, {{0, 3}}}, {4, {{0, 4}}}});
    });

    h.run("shared_scene_junction_retains_all_chain_indices_and_returning_flag", [&] {
        const auto scene = c::prepare_scene(grid(3, 4, {1, 4, 6, 8, 10}));
        h.equal(scene.chains.size(), 2, "junction graph chain count");
        if (scene.chains.size() == 2) {
            h.check(scene.chains[0].pixel_ids == std::vector<Id>{1, 4}, "open stem");
            h.check(scene.chains[1].pixel_ids == std::vector<Id>{4, 6, 10, 8}, "returning canonical cycle");
            h.check(scene.chains[1].closed && scene.chains[1].returning, "preserve returning closed flag");
        }
        h.memberships(scene.memberships, {{1, {{0, 0}}}, {4, {{0, 1}, {1, 0}}},
                                         {6, {{1, 1}}}, {8, {{1, 3}}}, {10, {{1, 2}}}});
    });

    h.run("scene_factory_owns_snapshot_independent_of_input_mutation", [&] {
        LabelGrid source{{0, 0, 0}};
        const auto scene = c::prepare_scene(source);
        source[0][0] = 7;
        h.check(scene.thinning.eligible_labels == LabelGrid{{0, 0, 0}}, "eligible value snapshot");
        h.check(scene.thinning.labels == LabelGrid{{0, 0, 0}}, "surviving value snapshot");
        h.equal(scene.memberships.size(), 3, "snapshot memberships retained");
    });

    h.run("empty_scene_is_legal_and_retains_dimensions_and_full_zero_result", [&] {
        const LabelGrid source{{255, 255, 255}, {255, 255, 255}};
        const auto scene = c::prepare_scene(source);
        h.equal(scene.thinning.width, 3, "empty scene width");
        h.equal(scene.thinning.height, 2, "empty scene height");
        h.check(scene.chains.empty() && scene.memberships.empty(), "empty scene evidence");
        const auto value = singleton(source);
        h.totals(value, 0, 0, 1);
        h.equal(value.chains.size(), 1, "empty scene retains template chain result");
        if (!value.chains.empty()) {
            h.match(value.chains[0], 0, 0, 0, 1, std::nullopt, {});
        }
    });

    h.run("scene_factory_rejects_empty_ragged_and_illegal_integer_labels", [&] {
        const std::vector<LabelGrid> invalid{{}, {{}}, {{0}, {0, 0}},
            {{-1}}, {{8}}, {{254}}, {{256}}, {{std::numeric_limits<int>::min()}}};
        for (const auto& labels : invalid) h.invalid([&] { (void)c::prepare_scene(labels); });
    });

    h.run("same_singleton_produces_full_exact_support_case_and_witness", [&] {
        const auto value = singleton();
        h.totals(value, 1, 1, 1);
        h.supports(value.samples, {{0, {0, 0}, {0, 0}, {0, 0}, {0, 0}, true, true, {0}, 0}});
        h.check(value.independent_witness == std::vector<Edge>{{0, 0}}, "A singleton witness");
        h.check(value.outside_padded_sample_ids.empty() && value.outside_original_sample_ids.empty(), "inside both frames");
        h.check(value.cross_chain_reused_pixel_ids.empty(), "no cross-chain reuse");
        h.equal(value.chains.size(), 1, "one chain result");
        if (!value.chains.empty()) {
            h.match(value.chains[0], 0, 1, 1, 1, n::MatchCase{0, 1, 0, 0}, {{0, 0}});
            h.check(value.chains[0].work.edge_states > 0, "native ordered solver executed");
        }
    });

    h.run("radius_two_includes_diagonal_boundary", [&] {
        const auto value = singleton(grid(6, 6, {14}));
        h.totals(value, 1, 1, 1);
        h.supports(value.samples, {{0, {0, 0}, {0, 0}, {0, 0}, {0, 0}, true, true, {14}, 14}});
    });

    h.run("distance_three_on_either_axis_never_supports", [&] {
        for (Id pixel : {Id{3}, Id{18}, Id{21}}) {
            const auto value = singleton(grid(6, 6, {pixel}));
            h.totals(value, 0, 0, 1);
            h.supports(value.samples, {{0, {0, 0}, {0, 0}, {0, 0}, {0, 0}, true, true, {}, std::nullopt}});
            h.check(value.independent_witness.empty(), "no distance-three A witness");
        }
    });

    h.run("outside_centers_cannot_be_clamped_or_rescued", [&] {
        for (const c::Point& match : {c::Point{-1, 0}, c::Point{3, 0}, c::Point{0, -1}, c::Point{0, 3}}) {
            const auto value = singleton(grid(3, 3, {0, 2, 6, 8}), {0, 0}, match);
            h.totals(value, 0, 0, 1);
            h.supports(value.samples, {{0, {0, 0}, {0, 0}, match, match, false, false, {}, std::nullopt}});
            h.check(value.outside_padded_sample_ids == std::vector<Id>{0}, "outside padded sample");
            h.check(value.outside_original_sample_ids == std::vector<Id>{0}, "outside original sample");
        }
    });

    h.run("circular_unsigned_direction_labels_wrap_at_seven", [&] {
        const std::array<std::array<int, 3>, 8> cases{{
            {{0, 7, 1}}, {{7, 0, 1}}, {{0, 1, 1}}, {{7, 6, 1}},
            {{0, 2, 0}}, {{7, 5, 0}}, {{0, 4, 0}}, {{0, 255, 0}}
        }};
        for (const auto& row : cases) {
            const auto value = singleton({{row[1]}}, {0, 0}, {0, 0}, {0, 0, 0, 0}, {{row[0]}});
            h.totals(value, row[2], row[2], 1);
        }
    });

    h.run("A_witness_is_smallest_compatible_physical_ID", [&] {
        const auto value = singleton(grid(5, 1, {0, 4}), {0, 0}, {2, 0});
        h.totals(value, 1, 1, 1);
        h.supports(value.samples, {{0, {0, 0}, {0, 0}, {2, 0}, {2, 0}, true, true, {0, 4}, 0}});
        h.check(value.independent_witness == std::vector<Edge>{{0, 0}}, "smallest A witness");
        h.equal(value.chains.size(), 1, "one template chain");
        if (!value.chains.empty()) {
            h.match(value.chains[0], 0, 1, 1, 1, n::MatchCase{0, 1, 0, 0}, {{0, 0}});
        }
    });

    h.run("B_cannot_join_disconnected_scene_chains", [&] {
        const auto templ = e::prepare_template(LabelGrid{std::vector<int>(9, 0)});
        const auto value = c::score_candidate(templ, c::prepare_scene(grid(9, 1, {0, 8})), {0, 0}, {0, 0});
        h.totals(value, 6, 2, 8);
        h.check(value.independent_witness == std::vector<Edge>{{0, 0}, {2, 0}, {6, 8}, {8, 8}}, "A can cover disconnected chains");
        h.equal(value.chains.size(), 1, "one original template chain");
        if (!value.chains.empty()) {
            h.match(value.chains[0], 0, 2, 6, 8, n::MatchCase{1, 1, 0, 0}, {{6, 8}});
        }
    });

    h.run("one_scene_pixel_cannot_repeat_inside_a_template_chain", [&] {
        const auto value = c::score_candidate(e::prepare_template({{0, 0, 0, 0, 0}}),
            c::prepare_scene(grid(5, 1, {2})), {0, 0}, {0, 0});
        h.totals(value, 3, 1, 3);
        h.check(value.independent_witness == std::vector<Edge>{{0, 2}, {2, 2}, {4, 2}}, "all independent supports retained");
        h.equal(value.chains.size(), 1, "one constrained chain");
        if (!value.chains.empty()) {
            h.match(value.chains[0], 0, 1, 3, 3, n::MatchCase{0, 1, 0, 0}, {{0, 2}});
        }
        h.check(value.cross_chain_reused_pixel_ids.empty(), "A reuse does not become B cross-chain reuse");
    });

    h.run("U_shape_has_full_independent_support_but_loses_ordered_weight", [&] {
        std::vector<Id> foreground{0, 1, 2, 3, 4, 5, 6, 7, 8, 20, 32, 42, 52,
                                   44, 45, 46, 47, 48, 49, 50, 51};
        std::vector<Id> scene_pixels;
        for (Id pixel = 30; pixel < 45; ++pixel) scene_pixels.push_back(pixel);
        const auto value = c::score_candidate(e::prepare_template(grid(11, 5, foreground)),
            c::prepare_scene(grid(15, 5, scene_pixels)), {0, 0}, {0, 0});
        h.equal(value.denominator, Integer(16), "literal template denominator");
        h.equal(value.independent_numerator, Integer(16), "complete U-shape A");
        h.check(value.ordered_numerator > 0 && value.ordered_numerator < 16, "ordered false line is penalized");
        h.check(value.independent_accepted, "full A is accepted");
    });

    h.run("shared_scene_memberships_never_duplicate_physical_support", [&] {
        auto labels = grid(3, 4, {1, 4, 6, 8, 10}, 4);
        labels[1][1] = 0;
        const auto value = c::score_candidate(e::prepare_template({{0, 0, 0}}),
            c::prepare_scene(labels), {0, 0}, {0, 1});
        h.totals(value, 2, 1, 2);
        h.check(value.independent_witness == std::vector<Edge>{{0, 4}, {2, 4}}, "one physical junction supports A");
        h.equal(value.chains.size(), 1, "one original template chain");
        if (!value.chains.empty()) {
            h.match(value.chains[0], 0, 1, 2, 2, n::MatchCase{0, 1, 0, 0}, {{0, 4}});
        }
        h.check(value.cross_chain_reused_pixel_ids.empty(), "membership reuse is not cross-template reuse");
    });

    h.run("different_template_chains_may_reuse_one_scene_pixel", [&] {
        const auto value = c::score_candidate(e::prepare_template(grid(3, 1, {0, 2})),
            c::prepare_scene(grid(3, 1, {1})), {0, 0}, {0, 0});
        h.totals(value, 2, 2, 2);
        h.check(value.independent_witness == std::vector<Edge>{{0, 1}, {2, 1}}, "A witnesses in physical sample order");
        h.check(value.cross_chain_reused_pixel_ids == std::vector<Id>{1}, "report distinct-chain B reuse");
        h.equal(value.chains.size(), 2, "both original template chain results");
        if (value.chains.size() == 2) {
            h.match(value.chains[0], 0, 1, 1, 1, n::MatchCase{0, 1, 0, 0}, {{0, 1}});
            h.match(value.chains[1], 1, 1, 1, 1, n::MatchCase{0, 1, 0, 0}, {{2, 1}});
        }
    });

    h.run("zero_owned_template_chain_keeps_full_zero_MatchResult", [&] {
        const auto source = grid(6, 5, {0, 5, 7, 10, 14, 15, 19, 22, 24, 29});
        const auto templ = e::prepare_template(source);
        const auto value = c::score_candidate(templ, c::prepare_scene(source), {0, 0}, {0, 0});
        h.totals(value, templ.denominator, templ.denominator, templ.denominator);
        h.equal(value.chains.size(), templ.chains.size(), "retain every original template chain");
        const auto zero = std::find_if(value.chains.begin(), value.chains.end(),
            [](const n::MatchResult& row) { return row.template_chain_id == 2; });
        h.check(zero != value.chains.end(), "zero-owned chain2 result present");
        if (zero != value.chains.end()) {
            h.match(*zero, 2, 0, 0, 0, std::nullopt, {});
            h.zero_work(zero->work);
        }
    });

    h.run("owned_samples_restore_nonmonotonic_chain_order_and_scene_cycle", [&] {
        const auto value = c::score_candidate(e::prepare_template(grid(3, 3, {1, 3, 5, 7})),
            c::prepare_scene(grid(8, 3, {1, 8, 10, 17, 15})), {0, 0}, {0, 0});
        h.totals(value, 3, 3, 3);
        h.equal(value.samples.size(), 3, "three physical-order support rows");
        if (value.samples.size() == 3) {
            h.equal(value.samples[0].sample_id, 1, "first physical sample");
            h.equal(value.samples[1].sample_id, 5, "second physical sample");
            h.equal(value.samples[2].sample_id, 7, "third physical sample");
            for (const auto& sample : value.samples) {
                h.check(sample.compatible_pixel_ids == std::vector<Id>{1, 8, 10, 17}, "far singleton omitted from support");
            }
        }
        h.equal(value.chains.size(), 1, "one closed template result");
        if (!value.chains.empty()) {
            h.match(value.chains[0], 0, 3, 3, 3, n::MatchCase{0, 1, 0, 0}, {{1, 1}, {7, 8}, {5, 10}});
        }
    });

    h.run("nonzero_tl_negative_relative_and_asymmetric_padding_keep_frames", [&] {
        const auto value = singleton(grid(7, 6, {16}), {4, 5}, {6, 7}, {1, 2, 3, 1});
        h.totals(value, 1, 1, 1);
        h.supports(value.samples, {{0, {0, 0}, {-4, -5}, {2, 2}, {1, 0}, true, true, {16}, 16}});
    });

    h.run("template_canvas_pixel_is_used_without_second_origin_adjustment", [&] {
        const auto value = singleton(grid(7, 6, {25}), {1, 2}, {3, 4}, {0, 0, 0, 0}, grid(5, 3, {7}));
        h.totals(value, 1, 1, 1);
        h.supports(value.samples, {{7, {2, 1}, {1, -1}, {4, 3}, {4, 3}, true, true, {25}, 25}});
    });

    h.run("padding_only_support_remains_legal_and_outside_original", [&] {
        const auto value = singleton(grid(7, 6, {7}), {0, 0}, {0, 1}, {1, 2, 3, 1});
        h.totals(value, 1, 1, 1);
        h.supports(value.samples, {{0, {0, 0}, {0, 0}, {0, 1}, {-1, -1}, true, false, {7}, 7}});
        h.check(value.outside_padded_sample_ids.empty(), "padding support center is inside padded frame");
        h.check(value.outside_original_sample_ids == std::vector<Id>{0}, "outside original remains diagnostic");
    });

    h.run("outside_rows_are_sample_sorted_and_never_shrink_denominator", [&] {
        const auto value = c::score_candidate(e::prepare_template({{0, 0, 0, 0, 0}}),
            c::prepare_scene({{0, 0, 0}}), {0, 0}, {-1, 0});
        h.totals(value, 1, 1, 3);
        h.supports(value.samples, {
            {0, {0, 0}, {0, 0}, {-1, 0}, {-1, 0}, false, false, {}, std::nullopt},
            {2, {2, 0}, {2, 0}, {1, 0}, {1, 0}, true, true, {0, 1, 2}, 0},
            {4, {4, 0}, {4, 0}, {3, 0}, {3, 0}, false, false, {}, std::nullopt}});
        h.check(value.outside_padded_sample_ids == std::vector<Id>{0, 4}, "physical sorted outside padded IDs");
        h.check(value.outside_original_sample_ids == std::vector<Id>{0, 4}, "physical sorted outside original IDs");
        h.check(value.independent_witness == std::vector<Edge>{{2, 0}}, "only middle sample receives A support");
    });

    h.run("signed64_boundaries_remain_exact_when_each_stage_fits", [&] {
        const std::array<c::Point, 4> tls{{{maximum, 0}, {0, 0}, {0, maximum}, {0, 0}}};
        const std::array<c::Point, 4> matches{{{maximum, 0}, {minimum, 0}, {0, maximum}, {maximum, maximum}}};
        const std::array<c::Point, 4> expected{{{0, 0}, {minimum, 0}, {0, 0}, {maximum, maximum}}};
        for (std::size_t index = 0; index < tls.size(); ++index) {
            const auto value = singleton({{0}}, tls[index], matches[index]);
            h.equal(value.samples.size(), 1, "boundary support row exists");
            if (!value.samples.empty()) {
                h.check(value.samples[0].q_padded == expected[index], "exact boundary padded coordinate");
                h.check(value.samples[0].q_original == expected[index], "exact boundary original coordinate");
            }
            h.equal(value.denominator, Integer(1), "outside boundary retains denominator");
        }
    });

    h.run("relative_subtraction_overflow_rejected_before_later_cancellation", [&] {
        h.invalid([&] { (void)singleton({{0}}, {minimum, 0}, {minimum, 0}); });
        h.invalid([&] { (void)singleton({{0}}, {0, minimum}, {0, minimum}); });
    });

    h.run("padded_addition_overflow_checked_on_both_axes_and_signs", [&] {
        h.invalid([&] { (void)singleton({{0}}, {-1, 0}, {maximum, 0}); });
        h.invalid([&] { (void)singleton({{0}}, {1, 0}, {minimum, 0}); });
        h.invalid([&] { (void)singleton({{0}}, {0, -1}, {0, maximum}); });
        h.invalid([&] { (void)singleton({{0}}, {0, 1}, {0, minimum}); });
    });

    h.run("original_subtraction_checked_even_when_padded_center_is_outside", [&] {
        h.invalid([&] { (void)singleton(grid(3, 3, {0}), {0, 0}, {minimum, 0}, {1, 0, 0, 0}); });
        h.invalid([&] { (void)singleton(grid(3, 3, {0}), {0, 0}, {0, minimum}, {0, 1, 0, 0}); });
    });

    h.run("padding_entries_must_be_nonnegative", [&] {
        for (const c::Padding& padding : {c::Padding{-1, 0, 0, 0}, c::Padding{0, -1, 0, 0},
                                        c::Padding{0, 0, -1, 0}, c::Padding{0, 0, 0, -1}}) {
            h.invalid([&] { (void)singleton(grid(3, 3, {0}), {0, 0}, {0, 0}, padding); });
        }
    });

    h.run("padding_must_leave_positive_original_dimensions", [&] {
        for (const c::Padding& padding : {c::Padding{3, 0, 0, 0}, c::Padding{1, 0, 2, 0},
                                        c::Padding{0, 3, 0, 0}, c::Padding{0, 1, 0, 2}}) {
            h.invalid([&] { (void)singleton(grid(3, 3, {0}), {0, 0}, {0, 0}, padding); });
        }
    });

    h.run("opposing_padding_sums_checked_before_dimension_comparison", [&] {
        h.invalid([&] { (void)singleton(grid(3, 3, {0}), {0, 0}, {0, 0}, {maximum, 0, 1, 0}); });
        h.invalid([&] { (void)singleton(grid(3, 3, {0}), {0, 0}, {0, 0}, {0, maximum, 0, 1}); });
    });

    h.run("candidate_result_vectors_are_independent_value_snapshots", [&] {
        auto first = singleton();
        const auto saved = first;
        first.samples.clear();
        first.chains.clear();
        first.independent_witness.clear();
        h.equal(saved.samples.size(), 1, "copied support records remain owned");
        h.equal(saved.chains.size(), 1, "copied chain results remain owned");
        h.check(saved.independent_witness == std::vector<Edge>{{0, 0}}, "copied witness retained");
    });

    h.run("inclusive_threshold_uses_exact_literal_ratios", [&] {
        h.check(c::passes_threshold(13, 20), "13/20 accepted inclusively");
        h.check(!c::passes_threshold(12, 20), "12/20 rejected");
        h.check(!c::passes_threshold(0, 20), "zero fraction rejected");
        h.check(c::passes_threshold(20, 20), "unit fraction accepted");
        h.check(c::passes_threshold(65, 100), "equivalent inclusive fraction accepted");
        h.check(!c::passes_threshold(64, 100), "adjacent fraction rejected");
    });

    h.run("threshold_GMP_boundary_distinguishes_one_integer_below", [&] {
        Integer factor = 1;
        factor <<= 220;
        const Integer denominator = 20 * factor;
        const Integer inclusive = 13 * factor;
        const Integer below = inclusive - 1;
        h.check(c::passes_threshold(inclusive, denominator), "exact13*2^220 over20*2^220 accepted");
        h.check(!c::passes_threshold(below, denominator), "one GMP unit below exact threshold rejected");
        h.check(c::passes_threshold(denominator, denominator), "large unit score accepted");
    });

    h.run("threshold_rejects_nonpositive_D_or_N_outside_closed_interval", [&] {
        for (const std::pair<Integer, Integer>& values : {
                std::pair<Integer, Integer>{0, 0}, {1, -1}, {-1, 20}, {21, 20}}) {
            h.invalid([&] { (void)c::passes_threshold(values.first, values.second); });
        }
    });

    h.run("full_candidate_GMP_weights_and_aggregates_exceed_uint64", [&] {
        const std::array<Id, 16> counts{2, 3, 5, 7, 11, 13, 17, 19,
                                       23, 29, 31, 37, 41, 43, 47, 53};
        LabelGrid source(64, std::vector<int>(64, 255));
        for (std::size_t cell = 0; cell < counts.size(); ++cell) {
            for (Id point = 0; point < counts[cell]; ++point) {
                std::size_t x = 16 * (cell % 4) + 2 * static_cast<std::size_t>(point % 8);
                std::size_t y = 16 * (cell / 4) + 2 * static_cast<std::size_t>(point / 8);
                if (cell == 15 && point == 52) { x = 63; y = 63; }
                source[y][x] = 0;
            }
        }
        const auto value = c::score_candidate(e::prepare_template(source), c::prepare_scene(source), {0, 0}, {0, 0});
        const Integer denominator("521426535635040715680");
        h.totals(value, denominator, denominator, denominator);
        h.equal(value.chains.size(), 381, "all isolated original chains retained");
    });

    std::cout << "NATIVE_CANDIDATE_TEST_SUMMARY tests=" << h.tests << " checks=" << h.checks
              << " failures=" << h.failures << " errors=" << h.errors << '\n';
    return h.failures == 0 && h.errors == 0 ? 0 : 1;
}
