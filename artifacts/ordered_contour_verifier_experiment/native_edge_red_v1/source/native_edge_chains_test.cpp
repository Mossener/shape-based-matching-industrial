// Literal synthetic label/chain regressions, written before native behavior.
// No images, detector, independent oracle, native timing, or production change.
#include "native_edge_chains.hpp"

#include <algorithm>
#include <exception>
#include <functional>
#include <iostream>
#include <limits>
#include <sstream>
#include <stdexcept>
#include <string>

using namespace ordered_contour_native::edge;

namespace {

LabelGrid grid(std::size_t width, std::size_t height,
               const std::vector<Id>& foreground) {
    LabelGrid result(height, std::vector<int>(width, 255));
    for (Id pixel : foreground) {
        result[static_cast<std::size_t>(pixel / width)]
              [static_cast<std::size_t>(pixel % width)] = static_cast<int>(pixel % 8);
    }
    return result;
}

std::string ids_text(const std::vector<Id>& ids) {
    std::ostringstream out;
    out << '[';
    for (std::size_t index = 0; index < ids.size(); ++index) {
        if (index != 0) out << ',';
        out << ids[index];
    }
    out << ']';
    return out.str();
}

std::vector<Id> sample_ids(const TemplateEvidence& value) {
    std::vector<Id> result;
    for (const auto& sample : value.samples) result.push_back(sample.pixel_id);
    return result;
}

std::vector<Integer> sample_weights(const TemplateEvidence& value) {
    std::vector<Integer> result;
    for (const auto& sample : value.samples) result.push_back(sample.weight);
    return result;
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

    void ids(const std::vector<Id>& actual, const std::vector<Id>& expected,
             const std::string& field) {
        check(actual == expected, field + " expected=" + ids_text(expected) +
                                 " actual=" + ids_text(actual));
    }

    void chains(const std::vector<Chain>& actual, const std::vector<Chain>& expected) {
        equal(actual.size(), expected.size(), "chain count");
        for (std::size_t index = 0; index < std::min(actual.size(), expected.size()); ++index) {
            equal(actual[index].chain_id, expected[index].chain_id, "chain ID");
            ids(actual[index].pixel_ids, expected[index].pixel_ids, "chain pixels");
            equal(actual[index].closed, expected[index].closed, "chain closed");
            equal(actual[index].returning, expected[index].returning, "chain returning");
        }
    }

    void sampling(const ChainSampling& actual, Id identity,
                  const std::vector<Id>& pixels, const Integer& arclength) {
        equal(actual.chain_id, identity, "sampling chain ID");
        ids(actual.pixel_ids, pixels, "sampled pixels in chain order");
        equal(actual.arclength, arclength, "sampling arclength");
    }

    void sample(const WeightedSample& actual, const WeightedSample& expected) {
        equal(actual.pixel_id, expected.pixel_id, "sample pixel");
        equal(actual.owner_chain_id, expected.owner_chain_id, "sample owner");
        equal(actual.chain_index, expected.chain_index, "sample original chain index");
        equal(actual.x, expected.x, "sample canvas x");
        equal(actual.y, expected.y, "sample canvas y");
        equal(actual.label, expected.label, "sample original direction label");
        equal(actual.cell, expected.cell, "sample cell");
        equal(actual.weight, expected.weight, "sample exact weight");
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

    h.run("horizontal_labels_zero_through_seven_survive_unchanged", [&] {
        const LabelGrid source{{0, 1, 2, 3, 4, 5, 6, 7}};
        const auto value = thin_labels(source);
        h.equal(value.width, 8, "width");
        h.equal(value.height, 1, "height");
        h.check(value.eligible_labels == source, "eligible snapshot");
        h.check(value.labels == source, "surviving original labels");
        h.check(value.round_deletions == std::vector<DeletionRound>{{0, 0}},
                "retain final no-deletion round");
    });

    h.run("two_synchronous_subiterations_retain_original_center_label", [&] {
        const LabelGrid source{{0, 1, 2}, {3, 4, 5}, {6, 7, 0}};
        const auto value = thin_labels(source);
        h.check(value.eligible_labels == source, "eligible labels preserved");
        h.check(value.labels == LabelGrid{{255, 255, 255}, {255, 4, 255}, {255, 255, 255}},
                "3x3 block must thin to original center label4");
        h.check(value.round_deletions == std::vector<DeletionRound>{{6, 2}, {0, 0}},
                "same-batch deletion counts then terminal round");
    });

    h.run("two_by_two_erasure_is_recorded_not_passed_through", [&] {
        const auto value = thin_labels({{0, 1}, {2, 3}});
        h.check(value.labels == LabelGrid{{255, 255}, {255, 255}}, "whole tiny block erased");
        h.check(value.round_deletions == std::vector<DeletionRound>{{4, 0}, {0, 0}},
                "complete first-subiteration erasure and terminal round");
    });

    h.run("all_invalid_scene_grid_retains_dimensions_and_termination", [&] {
        const LabelGrid source{{255, 255}, {255, 255}};
        const auto value = thin_labels(source);
        h.equal(value.width, 2, "width");
        h.equal(value.height, 2, "height");
        h.check(value.labels == source, "invalid scene remains empty");
        h.check(value.round_deletions == std::vector<DeletionRound>{{0, 0}}, "one terminal round");
        h.chains(extract_chains(source), {});
    });

    h.run("isolated_pixel_is_retained_as_open_singleton", [&] {
        const auto source = grid(3, 3, {4});
        const auto value = thin_labels(source);
        h.check(value.labels == source, "isolated pixel survives");
        h.chains(extract_chains(source), {{0, {4}, false, false}});
    });

    h.run("diagonal_contact_is_an_eight_neighbor_edge", [&] {
        h.chains(extract_chains(grid(2, 2, {0, 3})), {{0, {0, 3}, false, false}});
        h.sampling(sample_chain({0, {0, 3}, false, false}, 2), 0, {0, 3}, 1414);
    });

    h.run("open_trail_has_canonical_forward_reverse_order", [&] {
        h.chains(extract_chains(grid(1, 5, {0, 1, 2, 3, 4})),
                 {{0, {0, 1, 2, 3, 4}, false, false}});
    });

    h.run("pure_diamond_cycle_uses_canonical_rotation_and_no_repeat", [&] {
        h.chains(extract_chains(grid(3, 3, {1, 3, 5, 7})),
                 {{0, {1, 3, 7, 5}, true, false}});
    });

    h.run("right_triangle_is_a_three_vertex_cycle", [&] {
        h.chains(extract_chains(grid(2, 2, {0, 1, 3})),
                 {{0, {0, 1, 3}, true, false}});
        h.sampling(sample_chain({0, {0, 1, 3}, true, false}, 2), 0, {0, 3}, 3414);
    });

    h.run("return_to_same_junction_is_a_closed_returning_trail", [&] {
        const auto source = grid(3, 4, {1, 4, 6, 8, 10});
        h.check(thin_labels(source).labels == source, "returning graph survives thinning");
        h.chains(extract_chains(source),
                 {{0, {1, 4}, false, false}, {1, {4, 6, 10, 8}, true, true}});
    });

    h.run("extract_does_not_rethin_and_each_junction_edge_is_covered_once", [&] {
        h.chains(extract_chains({{0, 1}, {2, 3}}),
                 {{0, {0, 1}, false, false}, {1, {0, 2}, false, false},
                  {2, {0, 3}, false, false}, {3, {1, 2}, false, false},
                  {4, {1, 3}, false, false}, {5, {2, 3}, false, false}});
    });

    h.run("disconnected_chains_get_global_canonical_ids", [&] {
        h.chains(extract_chains(grid(5, 1, {0, 4})),
                 {{0, {0}, false, false}, {1, {4}, false, false}});
    });

    h.run("axial_sampling_uses_1000_steps_2000_markers_and_endpoints", [&] {
        h.sampling(sample_chain({3, {0, 1, 2, 3, 4, 5, 6}, false, false}, 7),
                   3, {0, 2, 4, 6}, 6000);
    });

    h.run("diagonal_sampling_selects_first_node_reached_after_marker", [&] {
        h.sampling(sample_chain({0, {0, 6, 12, 18, 24}, false, false}, 5),
                   0, {0, 12, 18, 24}, 5656);
    });

    h.run("closing_edge_counts_and_reached_first_pixel_is_deduplicated", [&] {
        h.sampling(sample_chain({0, {0, 1, 5, 7, 3}, true, false}, 3),
                   0, {0, 5, 3}, 6242);
    });

    h.run("sample_order_stays_nonmonotonic_chain_order", [&] {
        h.sampling(sample_chain({4, {1, 3, 7, 5}, true, false}, 3),
                   4, {1, 7, 5}, 5656);
    });

    h.run("short_chain_and_singleton_are_not_silently_dropped", [&] {
        h.sampling(sample_chain({8, {4}, false, false}, 3), 8, {4}, 0);
        h.sampling(sample_chain({9, {0, 1}, false, false}, 3), 9, {0, 1}, 1000);
    });

    h.run("uint64_max_ids_remain_physical_ids_not_signed_coordinates", [&] {
        const Id maximum = std::numeric_limits<Id>::max();
        h.sampling(sample_chain({maximum, {maximum - 1, maximum}, false, false}, 1),
                   maximum, {maximum - 1, maximum}, 1000);
    });

    h.run("shared_sample_is_owned_by_lowest_chain_id_once", [&] {
        const auto value = prepare_template(grid(3, 4, {1, 4, 6, 8, 10}));
        h.ids(sample_ids(value), {1, 4, 8, 10}, "physical-ID-sorted owned samples");
        h.equal(value.samplings.size(), 2, "both full chain samplings retained");
        if (value.samplings.size() == 2) {
            h.ids(value.samplings[0].pixel_ids, {1, 4}, "first sampling");
            h.ids(value.samplings[1].pixel_ids, {4, 10, 8}, "second sampling stays in chain order");
        }
        const auto ownership = std::find_if(value.ownership.begin(), value.ownership.end(),
            [](const SampleOwnership& row) { return row.pixel_id == 4; });
        h.check(ownership != value.ownership.end(), "shared physical pixel4 ownership exists");
        if (ownership != value.ownership.end()) {
            h.equal(ownership->owner_chain_id, 0, "lowest chain owns junction");
            h.ids(ownership->member_chain_ids, {0, 1}, "all sampling memberships retained");
        }
        const auto sample = std::find_if(value.samples.begin(), value.samples.end(),
            [](const WeightedSample& row) { return row.pixel_id == 4; });
        h.check(sample != value.samples.end(), "owned shared sample exists");
        if (sample != value.samples.end()) h.sample(*sample, {4, 0, 1, 1, 1, 4, 4, 1});
    });

    h.run("zero_owned_chain_keeps_topology_and_original_sampling", [&] {
        const auto source = grid(6, 5, {0, 5, 7, 10, 14, 15, 19, 22, 24, 29});
        const auto value = prepare_template(source);
        h.check(value.thinning.labels == source, "fixture graph survives thinning");
        const auto chain = std::find_if(value.chains.begin(), value.chains.end(),
            [](const Chain& row) { return row.chain_id == 2; });
        h.check(chain != value.chains.end(), "zero-owned chain2 retained");
        if (chain != value.chains.end()) {
            h.ids(chain->pixel_ids, {14, 15}, "zero-owned full chain");
            h.check(!chain->closed && !chain->returning, "zero-owned chain is open");
        }
        const auto sampling = std::find_if(value.samplings.begin(), value.samplings.end(),
            [](const ChainSampling& row) { return row.chain_id == 2; });
        h.check(sampling != value.samplings.end(), "zero-owned sampling2 retained");
        if (sampling != value.samplings.end()) h.ids(sampling->pixel_ids, {14, 15}, "zero-owned sampling");
        h.check(std::none_of(value.samples.begin(), value.samples.end(),
            [](const WeightedSample& row) { return row.owner_chain_id == 2; }), "chain2 owns no scoring sample");
        h.check(value.denominator > 0, "whole-template denominator remains positive");
    });

    h.run("owned_physical_order_retains_original_nonmonotonic_chain_indices", [&] {
        const auto value = prepare_template(grid(3, 3, {1, 3, 5, 7}));
        h.ids(sample_ids(value), {1, 5, 7}, "physical-ID sample order");
        h.equal(value.samples.size(), 3, "owned sample count");
        if (value.samples.size() == 3) {
            h.sample(value.samples[0], {1, 0, 0, 1, 0, 1, 0, 1});
            h.sample(value.samples[1], {5, 0, 3, 2, 1, 5, 6, 1});
            h.sample(value.samples[2], {7, 0, 2, 1, 2, 7, 8, 1});
        }
        h.equal(value.denominator, Integer(3), "three occupied singleton cells");
    });

    h.run("four_by_four_bbox_weights_use_lcm_of_occupied_cell_counts", [&] {
        const auto value = prepare_template(LabelGrid{std::vector<int>(20, 0)});
        h.ids(sample_ids(value), {0, 2, 4, 6, 8, 10, 12, 14, 16, 18, 19}, "sample IDs");
        h.check(value.cell_counts == std::array<Id, 16>{3, 2, 3, 3, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0},
                "occupied cells have literal counts3,2,3,3");
        h.equal(value.occupied_cells, 4, "occupied cell count");
        h.equal(value.lcm, Integer(6), "exact LCM");
        h.equal(value.denominator, Integer(24), "D=C*L");
        h.check(sample_weights(value) == std::vector<Integer>{2, 2, 2, 3, 3, 2, 2, 2, 2, 2, 2},
                "sample weights agree with actual occupied-cell counts");
        Integer sum = 0;
        for (const auto& sample : value.samples) sum += sample.weight;
        h.equal(sum, Integer(24), "all sample weights sum to unchanged denominator");
    });

    h.run("gmp_lcm_and_denominator_exceed_uint64_without_truncation", [&] {
        // Every point is isolated (spacing2), so no thinning or sampling can
        // discard it. The relocated last point fixes bbox max=(63,63).
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
        const auto value = prepare_template(source);
        h.check(value.cell_counts == counts, "sixteen literal prime occupancy counts");
        h.equal(value.occupied_cells, 16, "all cells occupied");
        h.equal(value.lcm, Integer("32589158477190044730"), "53 primorial exceeds uint64");
        h.equal(value.denominator, Integer("521426535635040715680"), "exact16*LCM");
        const auto first = std::find_if(value.samples.begin(), value.samples.end(),
            [](const WeightedSample& row) { return row.pixel_id == 0; });
        h.check(first != value.samples.end(), "first occupied-cell sample retained");
        if (first != value.samples.end()) {
            h.equal(first->weight, Integer("16294579238595022365"), "first cell weight L/2");
        }
    });

    h.run("singleton_has_unit_weight_and_one_occupied_cell", [&] {
        const auto value = prepare_template(grid(3, 3, {4}));
        h.equal(value.samples.size(), 1, "one owned sample");
        if (value.samples.size() == 1) h.sample(value.samples[0], {4, 0, 0, 1, 1, 4, 0, 1});
        h.equal(value.occupied_cells, 1, "one cell");
        h.equal(value.lcm, Integer(1), "unit LCM");
        h.equal(value.denominator, Integer(1), "unit denominator");
    });

    h.run("input_grid_is_snapshotted_before_caller_mutation", [&] {
        LabelGrid source{{0, 1, 2}};
        const auto value = thin_labels(source);
        source[0][0] = 7;
        h.check(value.eligible_labels == LabelGrid{{0, 1, 2}}, "eligible snapshot is independent");
        h.check(value.labels == LabelGrid{{0, 1, 2}}, "survivor snapshot is independent");
    });

    h.run("whole_empty_template_is_an_input_contract_failure", [&] {
        h.invalid([&] { (void)prepare_template({{255, 255}}); });
    });
    h.run("template_erased_by_thinning_is_an_input_contract_failure", [&] {
        h.invalid([&] { (void)prepare_template({{0, 0}, {0, 0}}); });
    });
    h.run("reject_empty_and_ragged_grids_at_all_factories", [&] {
        const std::vector<LabelGrid> bad{{}, {{}}, {{0}, {0, 1}}};
        for (const auto& source : bad) {
            h.invalid([&] { (void)thin_labels(source); });
            h.invalid([&] { (void)extract_chains(source); });
            h.invalid([&] { (void)prepare_template(source); });
        }
    });
    h.run("reject_numeric_labels_outside_unsigned8_or_invalid255", [&] {
        for (int label : {-1, 8, 254, 256, std::numeric_limits<int>::min(), std::numeric_limits<int>::max()}) {
            const LabelGrid source{{label}};
            h.invalid([&] { (void)thin_labels(source); });
            h.invalid([&] { (void)extract_chains(source); });
            h.invalid([&] { (void)prepare_template(source); });
        }
    });
    h.run("reject_zero_width_before_sampling", [&] {
        h.invalid([&] { (void)sample_chain({0, {0}, false, false}, 0); });
    });
    h.run("reject_empty_chain_before_sampling", [&] {
        h.invalid([&] { (void)sample_chain({0, {}, false, false}, 3); });
    });
    h.run("reject_duplicate_physical_ids_including_closing_endpoint", [&] {
        h.invalid([&] { (void)sample_chain({0, {0, 0}, false, false}, 3); });
        h.invalid([&] { (void)sample_chain({0, {0, 1, 4, 0}, true, false}, 3); });
    });
    h.run("reject_nonadjacent_steps_and_linear_id_row_wrap", [&] {
        h.invalid([&] { (void)sample_chain({0, {0, 2}, false, false}, 3); });
        h.invalid([&] { (void)sample_chain({0, {2, 3}, false, false}, 3); });
        h.invalid([&] { (void)sample_chain({0, {0, std::numeric_limits<Id>::max()}, false, false}, 1); });
    });
    h.run("reject_returning_flag_on_open_chain", [&] {
        h.invalid([&] { (void)sample_chain({0, {0, 1}, false, true}, 3); });
    });
    h.run("reject_closed_chain_with_fewer_than_three_vertices", [&] {
        h.invalid([&] { (void)sample_chain({0, {0, 1}, true, false}, 3); });
    });
    h.run("validate_closing_edge_adjacency_as_well_as_open_steps", [&] {
        h.invalid([&] { (void)sample_chain({0, {0, 1, 2}, true, false}, 3); });
    });

    std::cout << "NATIVE_EDGE_TEST_SUMMARY tests=" << h.tests << " checks=" << h.checks
              << " failures=" << h.failures << " errors=" << h.errors << '\n';
    return h.failures == 0 && h.errors == 0 ? 0 : 1;
}
