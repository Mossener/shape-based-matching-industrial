// Synthetic operational comparison only. No data/image/detector I/O.
// Reuse the frozen parity comparator, but never call its literal-suite entry.
#define main compiled_scene_literal_suite_entry
#include "native_candidate_compiled_scene_v2_test.cpp"
#undef main
#include "baseline_counted_v1.hpp"

#include <chrono>
#include <iomanip>
#include <optional>

namespace {

using Clock = std::chrono::steady_clock;
constexpr std::size_t rounds = 6;
constexpr std::size_t queries_per_round = 256;
constexpr std::size_t side = 256;
constexpr std::size_t tile_side = 8;

double milliseconds(Clock::duration duration) {
    return std::chrono::duration<double,std::milli>(duration).count();
}

void need(bool condition, const char* message) {
    if (!condition) throw std::runtime_error(message);
}

LabelGrid branching_scene() {
    LabelGrid labels(side,std::vector<int>(side,255));
    // 1024 disjoint stem+returning-cycle components, with one shared junction
    // each. Tile spacing keeps all components separate under 8-neighbor rules.
    for(std::size_t y=0;y<side;y+=tile_side) for(std::size_t x=0;x<side;x+=tile_side)
        for(Id pixel:{Id(1),Id(4),Id(6),Id(8),Id(10)})
            labels[y+static_cast<std::size_t>(pixel/3)][x+static_cast<std::size_t>(pixel%3)]=0;
    return labels;
}

std::vector<c::Point> queries() {
    std::vector<c::Point> result;
    result.reserve(queries_per_round);
    for(std::size_t i=0;i<queries_per_round;++i)
        result.push_back({static_cast<c::Coordinate>(tile_side*(i%(side/tile_side))),
                          static_cast<c::Coordinate>(tile_side*(i/(side/tile_side)))});
    return result;
}

struct BaselineMeasurement {
    c::SceneEvidence scene;
    std::vector<c::CandidateScore> results;
    c::BaselineIndexWork counters;
    double prepare_ms, score_ms, total_ms;
};

struct CachedMeasurement {
    v::CompiledScene scene;
    std::vector<c::CandidateScore> results;
    double prepare_including_index_ms, score_ms, total_ms;
};

BaselineMeasurement baseline(const LabelGrid& labels,const e::TemplateEvidence& templ,
                             const std::vector<c::Point>& matches) {
    const auto started=Clock::now();
    auto scene=c::prepare_scene(labels);
    const auto prepared=Clock::now();
    std::vector<c::CandidateScore> results;
    results.reserve(matches.size());
    for(const auto& match:matches)
        results.push_back(c::score_candidate(templ,scene,{0,0},match));
    const auto finished=Clock::now();
    return {std::move(scene),std::move(results),{},milliseconds(prepared-started),
            milliseconds(finished-prepared),milliseconds(finished-started)};
}

CachedMeasurement cached(const LabelGrid& labels,const e::TemplateEvidence& templ,
                         const std::vector<c::Point>& matches) {
    const auto started=Clock::now();
    auto scene=v::prepare_scene(labels);
    const auto prepared=Clock::now();
    std::vector<c::CandidateScore> results;
    results.reserve(matches.size());
    for(const auto& match:matches) results.push_back(v::score_candidate(templ,scene,{0,0},match));
    const auto finished=Clock::now();
    return {std::move(scene),std::move(results),milliseconds(prepared-started),
            milliseconds(finished-prepared),milliseconds(finished-started)};
}

void report(std::size_t round,const BaselineMeasurement& before,const CachedMeasurement& after) {
    const auto& a=before.counters;
    const auto& b=after.scene.index_work();
    std::cout << "{\"round\":" << round << ",\"order\":\""
              << (round%2==0?"baseline_first":"cached_first") << "\",\"baseline\":{"
              << "\"prepare_ms\":" << before.prepare_ms << ",\"score_ms\":" << before.score_ms
              << ",\"total_ms\":" << before.total_ms << ",\"scene_index_ms_untimed\":"
              << static_cast<double>(a.index_nanoseconds)/1000000.0
              << ",\"index_pairs\":" << a.index_builds << ",\"maps_constructed\":" << 2*a.index_builds
              << ",\"membership_rows\":" << a.membership_rows_indexed << ",\"members\":" << a.members_indexed
              << ",\"chains\":" << a.chains_indexed << "},\"cached\":{"
              << "\"prepare_including_index_ms\":" << after.prepare_including_index_ms
              << ",\"score_ms\":" << after.score_ms << ",\"total_ms\":" << after.total_ms
              << ",\"index_pairs\":" << b.index_builds << ",\"maps_constructed\":" << 2*b.index_builds
              << ",\"membership_rows\":" << b.membership_rows_indexed << ",\"members\":" << b.members_indexed
              << ",\"chains\":" << b.chains_indexed << "}}\n";
}

} // namespace

int main() {
    try {
        std::cout << std::setprecision(17);
        const auto labels=branching_scene();
        const auto templ=e::prepare_template(grid(3,4,{1,4,6,8,10}));
        const auto matches=queries();
        std::size_t compared=0;
        for(std::size_t round=0;round<rounds;++round) {
            std::optional<BaselineMeasurement> before;
            std::optional<CachedMeasurement> after;
            if(round%2==0) {before.emplace(baseline(labels,templ,matches));after.emplace(cached(labels,templ,matches));}
            else {after.emplace(cached(labels,templ,matches));before.emplace(baseline(labels,templ,matches));}
            need(same_scene(before->scene,after->scene.evidence()),"prepared scenes differ");
            need(before->scene.memberships.size()==5120 && before->scene.chains.size()==2048,
                 "large branching scene topology changed");
            const auto& b=after->scene.index_work();
            need(b.index_builds==1 && b.membership_rows_indexed==5120 && b.members_indexed==6144 &&
                 b.chains_indexed==2048,"cached scene indexes were not built once");
            need(before->results.size()==matches.size() && after->results.size()==matches.size(),"query output count differs");
            // Counted calls and all complete comparisons are outside timing.
            // Measured baseline results came from the exact frozen function.
            for(std::size_t i=0;i<matches.size();++i) {
                const auto counted=c::score_candidate_counted(
                    templ,before->scene,{0,0},matches[i],{0,0,0,0},before->counters);
                need(same_score(before->results[i],counted),"counted baseline differs from frozen v1");
                need(same_score(after->results[i],counted),"cached result differs from frozen v1");
                ++compared;
            }
            const auto& a=before->counters;
            need(a.index_builds==queries_per_round && a.membership_rows_indexed==queries_per_round*5120 &&
                 a.members_indexed==queries_per_round*6144 && a.chains_indexed==queries_per_round*2048,
                 "actual untimed counted baseline scene-wide map operations differ");
            report(round,*before,*after);
        }
        need(compared==1536,"paired comparison domain incomplete");
        std::cout << "NATIVE_COMPILED_SCENE_BENCHMARK_SUMMARY rounds=" << rounds
                  << " queries_per_round=" << queries_per_round << " complete_comparisons=" << compared
                  << " failures=0 errors=0\n";
        return 0;
    } catch(const std::exception& error) {
        std::cerr << "BENCHMARK_ERROR " << error.what() << '\n';
        return 1;
    }
}
