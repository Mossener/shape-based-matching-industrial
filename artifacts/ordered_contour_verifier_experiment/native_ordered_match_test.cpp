// Handliteral tests written before the native supplied-graph implementation.
// No images, detector, source labels, benchmark, or independent oracle is used.
// The initial coordinated run must retain ordinary failures against the zero
// stub. Each behavior is reported; no assert/abort hides subsequent failures.
#include "native_ordered_match.hpp"

#include <exception>
#include <functional>
#include <iostream>
#include <limits>
#include <sstream>
#include <stdexcept>
#include <string>

using namespace ordered_contour_native;

namespace {

TemplateChain t(std::vector<Id> ids, std::vector<Integer> weights,
                bool closed = false, Id chain_id = 0) {
    return {chain_id, std::move(ids), std::move(weights), closed};
}

SceneChain s(std::vector<Id> ids, std::vector<Edge> edges = {},
             bool closed = false, Id chain_id = 0) {
    return {chain_id, std::move(ids), std::move(edges), closed};
}

std::string witness_text(const std::vector<Edge>& witness) {
    std::ostringstream out;
    out << '[';
    for (std::size_t i = 0; i < witness.size(); ++i) {
        if (i != 0) out << ',';
        out << '(' << witness[i].first << ',' << witness[i].second << ')';
    }
    out << ']';
    return out.str();
}

struct Harness {
    std::size_t tests = 0;
    std::size_t checks = 0;
    std::size_t failures = 0;
    std::size_t errors = 0;
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

    void run(const std::string& name, const std::function<void()>& body) {
        ++tests;
        current = name;
        const auto before = failures + errors;
        try {
            body();
        } catch (const std::exception& exception) {
            ++errors;
            std::cerr << "ERROR " << current << ": unexpected exception: "
                      << exception.what() << '\n';
        } catch (...) {
            ++errors;
            std::cerr << "ERROR " << current << ": unexpected nonstandard exception\n";
        }
        if (failures + errors == before) std::cout << "PASS " << current << '\n';
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
        check(rejected, "expected std::invalid_argument before zero/unused shortcut");
    }

    void result(const MatchResult& actual, Id template_id,
                const Integer& numerator, const Integer& independent,
                const Integer& total, std::optional<MatchCase> selected,
                const std::vector<Edge>& witness) {
        equal(actual.template_chain_id, template_id, "template_chain_id");
        equal(actual.numerator, numerator, "numerator");
        equal(actual.independent_numerator, independent, "independent_numerator");
        equal(actual.total_weight, total, "total_weight");
        equal(actual.selected_case.has_value(), selected.has_value(), "case presence");
        if (actual.selected_case && selected) {
            equal(actual.selected_case->scene_chain_id, selected->scene_chain_id,
                  "case.scene_chain_id");
            equal(actual.selected_case->direction, selected->direction, "case.direction");
            equal(actual.selected_case->template_cut, selected->template_cut,
                  "case.template_cut");
            equal(actual.selected_case->scene_cut, selected->scene_cut, "case.scene_cut");
        }
        check(actual.witness == witness,
              "witness expected=" + witness_text(witness) +
              " actual=" + witness_text(actual.witness));
        check(actual.numerator >= 0 &&
              actual.numerator <= actual.independent_numerator &&
              actual.independent_numerator <= actual.total_weight,
              "require 0 <= B <= A <= total_weight");
    }

    void work(const WorkCounters& actual, const WorkCounters& expected) {
        equal(actual.case_count, expected.case_count, "work.case_count");
        equal(actual.edge_states, expected.edge_states, "work.edge_states");
        equal(actual.fenwick_queries, expected.fenwick_queries, "work.fenwick_queries");
        equal(actual.fenwick_updates, expected.fenwick_updates, "work.fenwick_updates");
        equal(actual.fenwick_query_visits, expected.fenwick_query_visits,
              "work.fenwick_query_visits");
        equal(actual.fenwick_update_visits, expected.fenwick_update_visits,
              "work.fenwick_update_visits");
        equal(actual.maximum_integer_bits, expected.maximum_integer_bits,
              "work.maximum_integer_bits");
    }
};

}  // namespace

int main() {
    Harness h;

    h.run("empty_template_is_a_retained_zero_chain", [&] {
        const auto r = solve(t({}, {}, false, 17), {s({}, {}, true, 3)});
        h.result(r, 17, 0, 0, 0, std::nullopt, {});
        h.work(r.work, {});
    });

    h.run("no_edges_keep_all_template_weight", [&] {
        const auto r = solve(t({10, 20}, {3, 5}), {s({100, 200, 300})});
        h.result(r, 0, 0, 0, 8, std::nullopt, {});
        h.work(r.work, {0, 0, 0, 0, 0, 0, 4});
    });

    h.run("no_scenes_keep_all_template_weight", [&] {
        const auto r = solve(t({1, 2}, {4, 9}), {});
        h.result(r, 0, 0, 0, 13, std::nullopt, {});
        h.work(r.work, {0, 0, 0, 0, 0, 0, 4});
    });

    h.run("one_edge_has_weight_identity_and_one_direction", [&] {
        const auto r = solve(t({50}, {7}, false, 9),
                             {s({90}, {{50, 90}}, false, 3)});
        h.result(r, 9, 7, 7, 7, MatchCase{3, 1, 0, 0}, {{50, 90}});
        h.work(r.work, {1, 1, 1, 1, 0, 1, 3});
    });

    h.run("open_open_keeps_supplied_topology_not_numeric_id_order", [&] {
        const auto r = solve(t({1, 2}, {2, 5}),
                             {s({30, 10}, {{2, 10}, {1, 30}}, false, 8)});
        h.result(r, 0, 7, 7, 7, MatchCase{8, 1, 0, 0}, {{1, 30}, {2, 10}});
    });

    h.run("open_open_can_require_reverse_scene_direction", [&] {
        const auto r = solve(t({1, 2, 3}, {2, 3, 5}),
                             {s({10, 20, 30}, {{1, 30}, {2, 20}, {3, 10}})});
        h.result(r, 0, 10, 10, 10, MatchCase{0, -1, 0, 0},
                 {{1, 30}, {2, 20}, {3, 10}});
        h.equal(r.work.case_count, 2, "two open-scene directions");
        h.equal(r.work.edge_states, 6, "all cases contribute states");
    });

    h.run("same_template_row_cannot_chain_two_edges", [&] {
        const auto r = solve(t({10}, {7}), {s({100, 200}, {{10, 100}, {10, 200}})});
        h.result(r, 0, 7, 7, 7, MatchCase{0, 1, 0, 0}, {{10, 100}});
        h.work(r.work, {2, 4, 4, 4, 2, 6, 3});
    });

    h.run("strict_scene_prefix_prevents_pixel_reuse", [&] {
        const auto r = solve(t({10, 20}, {3, 7}), {s({100}, {{10, 100}, {20, 100}})});
        h.result(r, 0, 7, 10, 10, MatchCase{0, 1, 0, 0}, {{20, 100}});
    });

    h.run("weight_optimum_can_use_fewer_points_than_count_optimum", [&] {
        const auto r = solve(t({10, 20, 30, 40}, {3, 3, 3, 11}),
                             {s({100, 200, 300},
                                {{10, 100}, {20, 200}, {30, 300}, {40, 200}})});
        h.result(r, 0, 14, 20, 20, MatchCase{0, 1, 0, 0}, {{10, 100}, {40, 200}});
    });

    h.run("open_closed_crosses_canonical_scene_seam_once", [&] {
        const auto r = solve(t({1, 2, 3}, {1, 2, 3}),
                             {s({10, 20, 30}, {{1, 30}, {2, 10}, {3, 20}}, true)});
        h.result(r, 0, 6, 6, 6, MatchCase{0, 1, 0, 2},
                 {{1, 30}, {2, 10}, {3, 20}});
        h.equal(r.work.case_count, 6, "all incident scene cuts in both directions");
        h.equal(r.work.edge_states, 18, "three edges per enumerated case");
    });

    h.run("closed_open_rotates_template_sample_order", [&] {
        const auto r = solve(t({1, 2, 3}, {1, 2, 3}, true),
                             {s({10, 20, 30}, {{3, 10}, {1, 20}, {2, 30}})});
        h.result(r, 0, 6, 6, 6, MatchCase{0, 1, 2, 0},
                 {{3, 10}, {1, 20}, {2, 30}});
        h.equal(r.work.case_count, 6, "all incident template cuts in both directions");
        h.equal(r.work.edge_states, 18, "three edges per enumerated case");
    });

    h.run("closed_closed_fixes_template_cut_zero", [&] {
        const auto r = solve(t({1, 2, 3}, {1, 2, 3}, true),
                             {s({10, 20, 30}, {{3, 10}, {1, 20}, {2, 30}}, true)});
        h.result(r, 0, 6, 6, 6, MatchCase{0, 1, 0, 1},
                 {{1, 20}, {2, 30}, {3, 10}});
        h.equal(r.work.case_count, 6, "closed_closed does not rotate both sides");
        h.equal(r.work.edge_states, 18, "three edges per enumerated case");
    });

    h.run("closed_scene_cannot_supply_two_laps", [&] {
        const auto r = solve(t({1, 2, 3, 4}, {1, 1, 1, 1}),
                             {s({10, 20}, {{1, 10}, {2, 20}, {3, 10}, {4, 20}}, true)});
        h.result(r, 0, 2, 4, 4, MatchCase{0, 1, 0, 0}, {{1, 10}, {2, 20}});
    });

    h.run("cyclic_cut_enumeration_uses_only_incident_nodes", [&] {
        const auto r = solve(t({1}, {5}),
                             {s({10, 20, 30, 40}, {{1, 30}}, true)});
        h.result(r, 0, 5, 5, 5, MatchCase{0, 1, 0, 2}, {{1, 30}});
        h.equal(r.work.case_count, 2, "one incident scene cut times two directions");
        h.equal(r.work.edge_states, 2, "one edge per incident-cut case");
    });

    h.run("one_template_chain_cannot_combine_scene_chains", [&] {
        const auto r = solve(t({1, 2, 3}, {3, 4, 5}),
                             {s({10}, {{1, 10}}, false, 1),
                              s({20, 30}, {{2, 20}, {3, 30}}, false, 2)});
        h.result(r, 0, 9, 12, 12, MatchCase{2, 1, 0, 0}, {{2, 20}, {3, 30}});
    });

    h.run("distinct_template_chains_may_reuse_a_scene_pixel", [&] {
        const auto first = solve(t({1}, {3}, false, 6),
                                 {s({77}, {{1, 77}}, false, 9)});
        const auto second = solve(t({2}, {5}, false, 7),
                                  {s({77}, {{2, 77}}, false, 9)});
        h.result(first, 6, 3, 3, 3, MatchCase{9, 1, 0, 0}, {{1, 77}});
        h.result(second, 7, 5, 5, 5, MatchCase{9, 1, 0, 0}, {{2, 77}});
    });

    h.run("shared_scene_membership_does_not_duplicate_independent_support", [&] {
        const auto r = solve(t({1}, {9}),
                             {s({77}, {{1, 77}}, false, 6),
                              s({77}, {{1, 77}}, false, 7)});
        h.result(r, 0, 9, 9, 9, MatchCase{6, 1, 0, 0}, {{1, 77}});
    });

    h.run("scene_chain_case_tie_precedes_smaller_witness", [&] {
        const auto r = solve(t({1}, {7}),
                             {s({1}, {{1, 1}}, false, 9),
                              s({99}, {{1, 99}}, false, 2)});
        h.result(r, 0, 7, 7, 7, MatchCase{2, 1, 0, 0}, {{1, 99}});
    });

    h.run("positive_direction_case_tie_precedes_smaller_witness", [&] {
        const auto r = solve(t({100, 5}, {1, 1}),
                             {s({90, 10}, {{100, 90}, {100, 10}, {5, 90}, {5, 10}})});
        h.result(r, 0, 2, 2, 2, MatchCase{0, 1, 0, 0}, {{100, 90}, {5, 10}});
    });

    h.run("template_cut_case_tie_precedes_smaller_witness", [&] {
        // At +1 cut2, (10,100),(50,200) has a smaller reversed witness;
        // +1 cut0 still wins because case priority comes first.
        const auto r = solve(t({90, 50, 10}, {1, 1, 1}, true),
                             {s({100, 200}, {{90, 100}, {50, 200}, {10, 100}})});
        h.result(r, 0, 2, 3, 3, MatchCase{0, 1, 0, 0}, {{90, 100}, {50, 200}});
    });

    h.run("scene_cut_case_tie_precedes_smaller_witness", [&] {
        // +1 scene cut1 would end at pixel10, but the equal-score cut0 wins.
        const auto r = solve(t({100, 5}, {1, 1}),
                             {s({10, 90}, {{100, 10}, {100, 90}, {5, 10}, {5, 90}}, true)});
        h.result(r, 0, 2, 2, 2, MatchCase{0, 1, 0, 0}, {{100, 10}, {5, 90}});
    });

    h.run("witness_tie_uses_recursive_reversed_original_edges", [&] {
        const auto r = solve(t({30, 20, 10}, {1, 1, 1}),
                             {s({300, 200}, {{30, 300}, {20, 300}, {10, 200}})});
        h.result(r, 0, 2, 3, 3, MatchCase{0, 1, 0, 0}, {{20, 300}, {10, 200}});
    });

    h.run("witness_final_edge_tie_uses_ids_not_indices", [&] {
        const auto r = solve(t({90, 10}, {1, 1}), {s({100}, {{90, 100}, {10, 100}})});
        h.result(r, 0, 1, 2, 2, MatchCase{0, 1, 0, 0}, {{10, 100}});
    });

    h.run("adjacent_2pow220_weights_remain_exact", [&] {
        const Integer large("1684996666696914987166688442938726917102321526408785780068975640576");
        const Integer larger("1684996666696914987166688442938726917102321526408785780068975640577");
        const Integer total("3369993333393829974333376885877453834204643052817571560137951281153");
        const auto r = solve(t({1, 2}, {large, larger}), {s({10}, {{1, 10}, {2, 10}})});
        h.result(r, 0, larger, total, total, MatchCase{0, 1, 0, 0}, {{2, 10}});
        h.equal(r.work.maximum_integer_bits, 222, "full total weight bit length");
    });

    h.run("edge_and_scene_input_permutation_preserves_canonical_result", [&] {
        const auto a = solve(t({1, 2}, {2, 5}),
                             {s({30, 10}, {{2, 10}, {1, 30}}, false, 8),
                              s({40}, {{1, 40}}, false, 1)});
        const auto b = solve(t({1, 2}, {2, 5}),
                             {s({40}, {{1, 40}}, false, 1),
                              s({30, 10}, {{1, 30}, {2, 10}}, false, 8)});
        h.result(a, 0, 7, 7, 7, MatchCase{8, 1, 0, 0}, {{1, 30}, {2, 10}});
        h.result(b, 0, 7, 7, 7, MatchCase{8, 1, 0, 0}, {{1, 30}, {2, 10}});
        h.equal(a.work.case_count, 3, "all scene cases counted");
        h.equal(a.work.edge_states, 5, "all scene edge states counted");
        h.work(b.work, a.work);
    });

    h.run("uint64_maximum_physical_ids_are_preserved", [&] {
        const Id maximum = std::numeric_limits<Id>::max();
        const auto r = solve(t({maximum}, {4}, false, maximum),
                             {s({maximum}, {{maximum, maximum}}, false, maximum)});
        h.result(r, maximum, 4, 4, 4, MatchCase{maximum, 1, 0, 0},
                 {{maximum, maximum}});
    });

    h.run("reject_zero_scoring_weight_without_scenes", [&] {
        h.invalid([&] { (void)solve(t({1}, {0}), {}); });
    });
    h.run("reject_negative_scoring_weight_without_edges", [&] {
        h.invalid([&] { (void)solve(t({1}, {-1}), {s({10})}); });
    });
    h.run("reject_fewer_weights_than_samples", [&] {
        h.invalid([&] { (void)solve(t({1, 2}, {3}), {}); });
    });
    h.run("reject_more_weights_than_samples", [&] {
        h.invalid([&] { (void)solve(t({1}, {3, 4}), {}); });
    });
    h.run("reject_duplicate_template_physical_ids", [&] {
        h.invalid([&] { (void)solve(t({1, 1}, {2, 3}), {}); });
    });
    h.run("reject_duplicate_scene_physical_ids_even_without_edges", [&] {
        h.invalid([&] { (void)solve(t({1}, {1}), {s({10, 10})}); });
    });
    h.run("reject_closed_scene_repeated_endpoint", [&] {
        h.invalid([&] { (void)solve(t({1}, {1}),
                                  {s({10, 20, 10}, {{1, 10}}, true)}); });
    });
    h.run("reject_duplicate_compatibility_edges", [&] {
        h.invalid([&] { (void)solve(t({1}, {1}),
                                  {s({10}, {{1, 10}, {1, 10}})}); });
    });
    h.run("reject_edge_with_unknown_template_sample", [&] {
        h.invalid([&] { (void)solve(t({1}, {1}), {s({10}, {{2, 10}})}); });
    });
    h.run("reject_edge_with_unknown_scene_pixel", [&] {
        h.invalid([&] { (void)solve(t({1}, {1}), {s({10}, {{1, 20}})}); });
    });
    h.run("reject_duplicate_scene_chain_ids_even_when_empty", [&] {
        h.invalid([&] { (void)solve(t({1}, {1}),
                                  {s({}, {}, false, 3), s({}, {}, true, 3)}); });
    });
    h.run("validate_unused_scene_after_a_valid_matching_scene", [&] {
        h.invalid([&] { (void)solve(t({1}, {1}),
                                  {s({10}, {{1, 10}}, false, 0),
                                   s({20, 20}, {}, false, 1)}); });
    });
    h.run("validate_scene_edges_before_empty_template_shortcut", [&] {
        h.invalid([&] { (void)solve(t({}, {}), {s({10}, {{1, 10}})}); });
    });
    h.run("reject_edge_into_empty_scene_chain", [&] {
        h.invalid([&] { (void)solve(t({1}, {1}), {s({}, {{1, 10}})}); });
    });

    std::cout << "NATIVE_TEST_SUMMARY tests=" << h.tests
              << " checks=" << h.checks << " failures=" << h.failures
              << " errors=" << h.errors << '\n';
    return h.failures == 0 && h.errors == 0 ? 0 : 1;
}
