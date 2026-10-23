// RED-first compiled-scene regressions. Synthetic supplied labels only.
// Literal expectations supplement complete frozen-v1 parity, including work.
#include "native_candidate_compiled_scene_v2.hpp"

#include <exception>
#include <functional>
#include <iostream>
#include <limits>
#include <string>

namespace n = ordered_contour_native;
namespace e = ordered_contour_native::edge;
namespace c = ordered_contour_native::candidate;
namespace v = ordered_contour_native::candidate_v2;
using e::LabelGrid;
using n::Id;
using n::Integer;

namespace {

constexpr c::Coordinate low = std::numeric_limits<c::Coordinate>::min();
constexpr c::Coordinate high = std::numeric_limits<c::Coordinate>::max();

LabelGrid grid(std::size_t width, std::size_t height, const std::vector<Id>& pixels, int label = 0) {
    LabelGrid result(height, std::vector<int>(width, 255));
    for (Id pixel : pixels) result[static_cast<std::size_t>(pixel / width)]
                                  [static_cast<std::size_t>(pixel % width)] = label;
    return result;
}

bool same_work(const n::WorkCounters& a, const n::WorkCounters& b) {
    return a.case_count == b.case_count && a.edge_states == b.edge_states &&
        a.fenwick_queries == b.fenwick_queries && a.fenwick_updates == b.fenwick_updates &&
        a.fenwick_query_visits == b.fenwick_query_visits &&
        a.fenwick_update_visits == b.fenwick_update_visits &&
        a.maximum_integer_bits == b.maximum_integer_bits;
}

bool same_case(const std::optional<n::MatchCase>& a, const std::optional<n::MatchCase>& b) {
    if (a.has_value() != b.has_value()) return false;
    return !a || (a->scene_chain_id == b->scene_chain_id && a->direction == b->direction &&
                  a->template_cut == b->template_cut && a->scene_cut == b->scene_cut);
}

bool same_match(const n::MatchResult& a, const n::MatchResult& b) {
    return a.template_chain_id == b.template_chain_id && a.numerator == b.numerator &&
        a.independent_numerator == b.independent_numerator && a.total_weight == b.total_weight &&
        same_case(a.selected_case, b.selected_case) && a.witness == b.witness && same_work(a.work, b.work);
}

bool same_score(const c::CandidateScore& a, const c::CandidateScore& b) {
    if (!(a.denominator == b.denominator && a.independent_numerator == b.independent_numerator &&
        a.ordered_numerator == b.ordered_numerator && a.independent_accepted == b.independent_accepted &&
        a.ordered_accepted == b.ordered_accepted && a.samples.size() == b.samples.size() &&
        a.chains.size() == b.chains.size() && a.outside_padded_sample_ids == b.outside_padded_sample_ids &&
        a.outside_original_sample_ids == b.outside_original_sample_ids &&
        a.independent_witness == b.independent_witness &&
        a.cross_chain_reused_pixel_ids == b.cross_chain_reused_pixel_ids)) return false;
    for (std::size_t i = 0; i < a.samples.size(); ++i) {
        const auto& x = a.samples[i];
        const auto& y = b.samples[i];
        if (!(x.sample_id == y.sample_id && x.p_canvas == y.p_canvas && x.relative == y.relative &&
            x.q_padded == y.q_padded && x.q_original == y.q_original &&
            x.padded_in_bounds == y.padded_in_bounds && x.original_in_bounds == y.original_in_bounds &&
            x.compatible_pixel_ids == y.compatible_pixel_ids &&
            x.independent_witness == y.independent_witness)) return false;
    }
    for (std::size_t i = 0; i < a.chains.size(); ++i)
        if (!same_match(a.chains[i], b.chains[i])) return false;
    return true;
}

bool same_scene(const c::SceneEvidence& a, const c::SceneEvidence& b) {
    if (!(a.thinning.width == b.thinning.width && a.thinning.height == b.thinning.height &&
        a.thinning.eligible_labels == b.thinning.eligible_labels && a.thinning.labels == b.thinning.labels &&
        a.thinning.round_deletions == b.thinning.round_deletions && a.chains.size() == b.chains.size() &&
        a.memberships.size() == b.memberships.size())) return false;
    for (std::size_t i = 0; i < a.chains.size(); ++i) {
        const auto& x = a.chains[i];
        const auto& y = b.chains[i];
        if (!(x.chain_id == y.chain_id && x.pixel_ids == y.pixel_ids &&
              x.closed == y.closed && x.returning == y.returning)) return false;
    }
    for (std::size_t i = 0; i < a.memberships.size(); ++i) {
        const auto& x = a.memberships[i];
        const auto& y = b.memberships[i];
        if (x.pixel_id != y.pixel_id || x.members.size() != y.members.size()) return false;
        for (std::size_t j = 0; j < x.members.size(); ++j)
            if (x.members[j].chain_id != y.members[j].chain_id ||
                x.members[j].chain_index != y.members[j].chain_index) return false;
    }
    return true;
}

bool same_index_work(const v::SceneIndexWork& a, const v::SceneIndexWork& b) {
    return a.index_builds == b.index_builds && a.membership_rows_indexed == b.membership_rows_indexed &&
        a.members_indexed == b.members_indexed && a.chains_indexed == b.chains_indexed;
}

struct Harness {
    std::size_t tests = 0, checks = 0, failures = 0, errors = 0;
    std::string current;
    void check(bool value, const std::string& what) {
        ++checks;
        if (!value) { ++failures; std::cerr << "FAIL " << current << ": " << what << '\n'; }
    }
    void run(const std::string& name, const std::function<void()>& body) {
        ++tests; current = name;
        try { body(); }
        catch (const std::exception& error) { ++errors; std::cerr << "ERROR " << current << ": " << error.what() << '\n'; }
        catch (...) { ++errors; std::cerr << "ERROR " << current << ": unknown exception\n"; }
    }
    void invalid(const std::function<void()>& body) {
        bool caught = false;
        try { body(); }
        catch (const std::invalid_argument&) { caught = true; }
        check(caught, "std::invalid_argument required");
    }
    void index(const v::CompiledScene& scene, Id rows, Id members, Id chains) {
        const auto& work = scene.index_work();
        check(work.index_builds == 1, "exactly one pair of scene indexes built");
        check(work.membership_rows_indexed == rows, "each membership row indexed once");
        check(work.members_indexed == members, "all physical memberships retained");
        check(work.chains_indexed == chains, "each complete scene chain indexed once");
    }
    c::CandidateScore parity(const LabelGrid& templ, const LabelGrid& labels,
                             const c::Point& tl = {0,0}, const c::Point& match = {0,0},
                             const c::Padding& padding = {0,0,0,0}) {
        const auto source = e::prepare_template(templ);
        const auto scene = v::prepare_scene(labels);
        const auto baseline = c::prepare_scene(labels);
        check(same_scene(scene.evidence(), baseline), "complete scene factory evidence equals frozen v1");
        const auto before = scene.index_work();
        const auto expected = c::score_candidate(source, baseline, tl, match, padding);
        const auto actual = v::score_candidate(source, scene, tl, match, padding);
        check(same_score(actual, expected), "every CandidateScore field and all solver work equal frozen v1");
        check(same_index_work(before, scene.index_work()), "score does not rebuild or mutate scene indexes");
        return actual;
    }
};

} // namespace

int main() {
    Harness h;
    h.run("singleton_factory_preserves_full_literal_scene_and_one_index_build", [&] {
        const auto scene = v::prepare_scene({{0}});
        h.check(scene.valid(), "factory handle is valid");
        h.check(same_scene(scene.evidence(), c::prepare_scene({{0}})), "singleton complete scene");
        h.index(scene,1,1,1);
    });
    h.run("factory_rejects_empty_ragged_and_all_illegal_label_classes", [&] {
        for (const LabelGrid& labels : std::vector<LabelGrid>{{},{ {} },{{0},{0,0}},{{-1}},{{8}},{{254}},{{256}}})
            h.invalid([&] { (void)v::prepare_scene(labels); });
    });
    h.run("full_straight_chain_indexes_unsampled_scene_vertices", [&] {
        const auto scene=v::prepare_scene({{0,0,0,0,0}});
        h.index(scene,5,5,1);
        h.check(same_scene(scene.evidence(),c::prepare_scene({{0,0,0,0,0}})), "all five vertices and chain order");
    });
    h.run("returning_junction_indexes_both_members_of_shared_physical_pixel", [&] {
        const auto labels=grid(3,4,{1,4,6,8,10});
        const auto scene=v::prepare_scene(labels);
        h.index(scene,5,6,2);
        h.check(same_scene(scene.evidence(),c::prepare_scene(labels)), "complete returning/cycle topology");
    });
    h.run("synchronous_thinning_precedes_index_construction", [&] {
        const auto scene=v::prepare_scene({{0,0},{0,0}});
        h.index(scene,0,0,0);
        h.check(same_scene(scene.evidence(),c::prepare_scene({{0,0},{0,0}})), "erased component retains eligible field");
    });
    h.run("empty_scene_retains_dimensions_and_a_single_empty_index_build", [&] {
        const auto scene=v::prepare_scene({{255,255,255},{255,255,255}});
        h.index(scene,0,0,0);
        h.check(scene.evidence().thinning.width==3 && scene.evidence().thinning.height==2, "literal empty dimensions");
        (void)h.parity({{0}},{{255,255,255},{255,255,255}});
    });
    h.run("copy_constructor_shares_immutable_storage_without_rebuilding", [&] {
        const auto scene=v::prepare_scene({{0,0,0}});
        const auto copied=scene;
        h.check(copied.shares_storage_with(scene), "copy shares ownership");
        h.check(&copied.evidence()==&scene.evidence(), "copy uses same immutable evidence object");
        h.index(copied,3,3,1);
    });
    h.run("move_constructor_preserves_storage_and_rejects_moved_from_access", [&] {
        auto source=v::prepare_scene({{0}});
        const auto retained=source;
        auto moved=std::move(source);
        h.check(moved.shares_storage_with(retained) && !source.valid(), "move transfers shared owner");
        h.invalid([&] { (void)source.evidence(); });
        h.invalid([&] { (void)source.index_work(); });
        h.invalid([&] { (void)v::score_candidate(e::prepare_template({{0}}),source,{0,0},{0,0}); });
        h.check(same_score(v::score_candidate(e::prepare_template({{0}}),moved,{0,0},{0,0}),
                           c::score_candidate(e::prepare_template({{0}}),c::prepare_scene({{0}}),{0,0},{0,0})), "moved owner scores");
    });
    h.run("copy_assignment_replaces_owner_without_aliasing_original_mutable_input", [&] {
        LabelGrid labels{{0,0,0}};
        const auto source=v::prepare_scene(labels);
        auto assigned=v::prepare_scene({{255}});
        assigned=source; labels[0][0]=7;
        h.check(assigned.shares_storage_with(source), "copy assignment shares owner");
        h.check(assigned.evidence().thinning.eligible_labels==LabelGrid{{0,0,0}}, "caller mutation cannot alter snapshot");
        h.index(assigned,3,3,1);
    });
    h.run("move_assignment_keeps_shared_ownership_after_original_handle_destruction", [&] {
        auto assigned=v::prepare_scene({{255}});
        { auto temporary=v::prepare_scene({{0,0,0}}); const auto retained=temporary;
          assigned=std::move(temporary); h.check(assigned.shares_storage_with(retained), "move assignment shares retained owner");
          h.check(!temporary.valid(), "move assignment empties source"); }
        h.index(assigned,3,3,1);
        h.check(same_scene(assigned.evidence(),c::prepare_scene({{0,0,0}})), "storage survives old handles");
    });
    h.run("caller_grid_mutation_does_not_change_later_candidate_results", [&] {
        LabelGrid labels{{0,0,0}};
        const auto scene=v::prepare_scene(labels);
        const auto templ=e::prepare_template({{0}});
        const auto expected=c::score_candidate(templ,c::prepare_scene(labels),{0,0},{0,0});
        labels={{255}};
        h.check(same_score(v::score_candidate(templ,scene,{0,0},{0,0}),expected), "owned labels and indexes remain valid");
    });
    h.run("singleton_score_has_literal_totals_and_witness_plus_full_work_parity", [&] {
        const auto score=h.parity({{0}},{{0}});
        h.check(score.denominator==1 && score.independent_numerator==1 && score.ordered_numerator==1, "literal 1/1 totals");
        h.check(score.independent_accepted && score.ordered_accepted, "literal inclusive accept");
        h.check(score.independent_witness==std::vector<n::Edge>{{0,0}}, "literal singleton A witness");
        h.check(score.chains.size()==1 && score.chains[0].witness==std::vector<n::Edge>{{0,0}}, "literal singleton B witness");
    });
    h.run("unsigned_direction_wrap_is_preserved_for_every_label", [&] {
        for(int label=0;label<8;++label) for(int other=0;other<8;++other)
            (void)h.parity({{label}},{{other}});
    });
    h.run("radius_two_clipping_and_outside_centers_preserve_support_rows", [&] {
        for(const c::Point& match:{c::Point{0,0},c::Point{2,2},c::Point{3,3},c::Point{-1,0},c::Point{5,0}})
            (void)h.parity({{0}},grid(5,5,{12}),{0,0},match);
    });
    h.run("disconnected_scene_chain_choice_and_ties_keep_full_observables", [&] {
        const auto score=h.parity({{0,0,0,0,0,0,0,0,0}},grid(9,1,{0,8}));
        h.check(score.denominator==8 && score.independent_numerator==6 && score.ordered_numerator==2, "literal disconnected A/B/D");
    });
    h.run("separate_template_chains_may_reuse_one_physical_scene_pixel", [&] {
        const auto score=h.parity(grid(3,1,{0,2}),grid(3,1,{1}));
        h.check(score.cross_chain_reused_pixel_ids==std::vector<Id>{1}, "literal physical reuse diagnostic");
    });
    h.run("zero_owned_original_template_chain_is_kept_with_full_zero_work", [&] {
        const auto labels=grid(6,5,{0,5,7,10,14,15,19,22,24,29});
        const auto score=h.parity(labels,labels);
        const auto row=std::find_if(score.chains.begin(),score.chains.end(),[](const n::MatchResult& x){return x.template_chain_id==2;});
        h.check(row!=score.chains.end(), "zero-owned chain2 survives");
        if(row!=score.chains.end()) h.check(same_work(row->work,n::WorkCounters{}), "zero-owned counters remain zero");
    });
    h.run("closed_template_and_returning_scene_keep_nonmonotonic_order", [&] {
        const auto score=h.parity(grid(3,3,{1,3,5,7}),grid(8,3,{1,8,10,17,15}));
        h.check(score.denominator==3 && score.ordered_numerator==3, "literal cycle score");
        h.check(score.chains.size()==1 && score.chains[0].witness==std::vector<n::Edge>{{1,1},{7,8},{5,10}}, "literal original-ID witness order");
    });
    h.run("nonzero_origin_negative_relative_and_asymmetric_padding_preserve_frames", [&] {
        (void)h.parity({{0}},grid(7,6,{16}),{4,5},{6,7},{1,2,3,1});
        (void)h.parity({{0}},grid(5,4,{0}),{0,0},{0,0},{1,1,1,1});
    });
    h.run("signed64_extremes_keep_each_checked_coordinate_frame", [&] {
        for(const auto& pair:std::vector<std::pair<c::Point,c::Point>>{
            {{high,0},{high,0}},{{0,0},{low,0}},{{0,high},{0,high}},{{0,0},{high,high}}})
            (void)h.parity({{0}},{{0}},pair.first,pair.second);
    });
    h.run("relative_overflow_throws_before_cancellation_and_preserves_cache", [&] {
        const auto scene=v::prepare_scene({{0}}); const auto templ=e::prepare_template({{0}});
        for(const c::Point& tl:{c::Point{low,0},c::Point{0,low}})
            h.invalid([&]{(void)v::score_candidate(templ,scene,tl,tl);});
        h.index(scene,1,1,1);
    });
    h.run("padded_addition_overflow_on_either_axis_or_sign_matches_v1", [&] {
        const auto scene=v::prepare_scene({{0}}); const auto templ=e::prepare_template({{0}});
        for(const auto& pair:std::vector<std::pair<c::Point,c::Point>>{
            {{-1,0},{high,0}},{{1,0},{low,0}},{{0,-1},{0,high}},{{0,1},{0,low}}}) {
            h.invalid([&]{(void)c::score_candidate(templ,c::prepare_scene({{0}}),pair.first,pair.second);});
            h.invalid([&]{(void)v::score_candidate(templ,scene,pair.first,pair.second);});
        }
    });
    h.run("original_coordinate_overflow_is_checked_even_outside_padded_canvas", [&] {
        const auto scene=v::prepare_scene(grid(3,3,{0})); const auto templ=e::prepare_template({{0}});
        h.invalid([&]{(void)v::score_candidate(templ,scene,{0,0},{low,0},{1,0,0,0});});
        h.invalid([&]{(void)v::score_candidate(templ,scene,{0,0},{0,low},{0,1,0,0});});
    });
    h.run("padding_negative_empty_original_and_sum_overflow_are_rejected", [&] {
        const auto labels=grid(3,3,{0}); const auto scene=v::prepare_scene(labels); const auto templ=e::prepare_template({{0}});
        for(const c::Padding& padding:std::vector<c::Padding>{{-1,0,0,0},{0,-1,0,0},{0,0,-1,0},{0,0,0,-1},
            {3,0,0,0},{1,0,2,0},{0,3,0,0},{0,1,0,2},{high,0,1,0},{0,high,0,1}}) {
            h.invalid([&]{(void)c::score_candidate(templ,c::prepare_scene(labels),{0,0},{0,0},padding);});
            h.invalid([&]{(void)v::score_candidate(templ,scene,{0,0},{0,0},padding);});
        }
    });
    h.run("result_mutation_and_rejected_candidate_do_not_poison_shared_scene", [&] {
        const auto scene=v::prepare_scene({{0}}); const auto alias=scene; const auto templ=e::prepare_template({{0}});
        const auto expected=c::score_candidate(templ,c::prepare_scene({{0}}),{0,0},{0,0});
        auto first=v::score_candidate(templ,scene,{0,0},{0,0});
        first.samples.clear(); first.chains.clear(); first.independent_witness.clear(); first.denominator=99;
        h.invalid([&]{(void)v::score_candidate(templ,scene,{low,0},{low,0});});
        h.check(same_score(v::score_candidate(templ,alias,{0,0},{0,0}),expected), "later result is independent and cache reusable");
        h.index(alias,1,1,1);
    });
    h.run("GMP_full_candidate_weights_and_aggregates_remain_exact_above_uint64", [&] {
        const std::array<Id,16> counts{2,3,5,7,11,13,17,19,23,29,31,37,41,43,47,53};
        LabelGrid labels(64,std::vector<int>(64,255));
        for(std::size_t cell=0;cell<counts.size();++cell) for(Id point=0;point<counts[cell];++point) {
            std::size_t x=16*(cell%4)+2*static_cast<std::size_t>(point%8);
            std::size_t y=16*(cell/4)+2*static_cast<std::size_t>(point/8);
            if(cell==15 && point==52) {x=63;y=63;} labels[y][x]=0;
        }
        const auto score=h.parity(labels,labels);
        const Integer expected("521426535635040715680");
        h.check(score.denominator==expected && score.ordered_numerator==expected, "literal >uint64 candidate totals");
    });
    h.run("parity_comparator_observes_all_seven_solver_work_fields", [&] {
        const n::WorkCounters zero{};
        const std::array<std::uint64_t n::WorkCounters::*,7> fields{{&n::WorkCounters::case_count,
            &n::WorkCounters::edge_states,&n::WorkCounters::fenwick_queries,&n::WorkCounters::fenwick_updates,
            &n::WorkCounters::fenwick_query_visits,&n::WorkCounters::fenwick_update_visits,&n::WorkCounters::maximum_integer_bits}};
        for(auto field:fields) {auto changed=zero;changed.*field=1;h.check(!same_work(zero,changed), "changed work field detected");}
    });
    h.run("all_6144_frozen_candidate_domains_preserve_scene_score_and_full_work", [&] {
        const std::array<LabelGrid,3> templates{{grid(3,3,{4}),{{0,0,0,0,0}},grid(3,3,{1,3,5,7})}};
        const std::array<std::array<int,9>,2> profiles{{{{0,0,0,0,0,0,0,0,0}},{{0,7,2,6,4,1,5,3,0}}}};
        std::size_t compared=0;
        for(unsigned mask=0;mask<512;++mask) for(const auto& profile:profiles) {
            LabelGrid labels(3,std::vector<int>(3,255));
            for(unsigned pixel=0;pixel<9;++pixel) if(mask&(1u<<pixel)) labels[pixel/3][pixel%3]=profile[pixel];
            const auto scene=v::prepare_scene(labels); const auto baseline=c::prepare_scene(labels);
            h.check(same_scene(scene.evidence(),baseline), "complete scene in exhaustive domain");
            const auto before=scene.index_work();
            for(const auto& template_labels:templates) for(int transform=0;transform<2;++transform) {
                const auto templ=e::prepare_template(template_labels);
                const c::Point tl=transform?c::Point{2,1}:c::Point{0,0};
                const c::Point match=transform?c::Point{1,2}:c::Point{0,0};
                const c::Padding padding=transform?c::Padding{1,0,0,1}:c::Padding{0,0,0,0};
                h.check(same_score(v::score_candidate(templ,scene,tl,match,padding),
                                   c::score_candidate(templ,baseline,tl,match,padding)), "full v1/v2 score+work parity");
                ++compared;
            }
            h.check(before.index_builds==1 && same_index_work(before,scene.index_work()), "six scores reuse one index pair");
        }
        h.check(compared==6144, "no exhaustive candidate skipped");
    });
    std::cout << "NATIVE_COMPILED_SCENE_TEST_SUMMARY tests=" << h.tests << " checks=" << h.checks
              << " failures=" << h.failures << " errors=" << h.errors << '\n';
    return h.failures==0 && h.errors==0 ? 0 : 1;
}
