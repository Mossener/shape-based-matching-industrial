#include "../search_optimization/fixtures.hpp"
#include <algorithm>
#include <cstdint>
#include <cstring>
#include <sstream>

namespace {
using Clock = std::chrono::steady_clock;
using Semantic = std::tuple<std::string, int, int, std::uint32_t>;
using Strict = std::tuple<std::string, int, int, std::uint32_t, int>;
struct Keys { std::set<Semantic> semantic; std::set<Strict> strict; };
struct Config { const char* name; bool reference, fused, integer; };
const std::array<Config, 3> configs{{
    {"v4", true, false, false}, {"fallback", false, false, true}, {"fused", false, true, true}}};
const Config floatSanity{"fused_requested_float", false, true, false};
struct Sample {
    line2Dup::MatchTimings timing;
    double wall = 0;
    std::size_t count = 0;
    Keys keys;
};

std::uint32_t floatBits(float value) {
    std::uint32_t bits;
    std::memcpy(&bits, &value, sizeof(bits));
    return bits;
}
template<class Matches> void capture(Sample& sample, const Matches& matches) {
    sample.count = matches.size();
    for (const auto& m : matches) {
        const auto bits = floatBits(m.similarity);
        sample.keys.semantic.emplace(m.class_id, m.x, m.y, bits);
        sample.keys.strict.emplace(m.class_id, m.x, m.y, bits, m.template_id);
    }
}
Sample invoke(const search_experiment::Fixture& fixture, const Config& config,
              line2Dup::MatchWorkspace& workspace) {
    Sample sample;
    if (config.reference) {
        const auto start = Clock::now();
        const auto matches = fixture.reference->match(fixture.image, fixture.threshold, {fixture.class_id});
        sample.wall = std::chrono::duration<double, std::milli>(Clock::now() - start).count();
        const auto timing = fixture.reference->lastTimings();
        sample.timing.pyramid_ms = timing.pyramid_ms;
        sample.timing.gradient_ms = timing.gradient_ms;
        sample.timing.spread_ms = timing.spread_ms;
        sample.timing.response_ms = timing.response_ms;
        sample.timing.linearize_ms = timing.linearize_ms;
        sample.timing.preprocess_ms = timing.preprocess_ms;
        sample.timing.search_ms = timing.search_ms;
        sample.timing.total_ms = timing.total_ms;
        capture(sample, matches);
    } else {
        auto options = search_experiment::options(7);
        options.fused_local_search = config.fused;
        options.integer_local_max = config.integer;
        const auto start = Clock::now();
        const auto matches = fixture.detector->match(fixture.image, fixture.threshold, workspace,
            options, &sample.timing, {fixture.class_id});
        sample.wall = std::chrono::duration<double, std::milli>(Clock::now() - start).count();
        capture(sample, matches);
    }
    return sample;
}
void appendTemplate(std::ostream&, const Semantic&) {}
void appendTemplate(std::ostream& out, const Strict& key) { out << ':' << std::get<4>(key); }
// Stable FNV-1a over a canonical textual encoding. Equality above uses the full
// exact key sets; hashes are compact audit evidence and never decide equality.
template<class Set> std::string fingerprint(const Set& values) {
    std::uint64_t hash = UINT64_C(14695981039346656037);
    for (const auto& key : values) {
        std::ostringstream encoded;
        encoded << std::get<0>(key).size() << ':' << std::get<0>(key) << ':'
                << std::get<1>(key) << ':' << std::get<2>(key) << ':' << std::get<3>(key);
        appendTemplate(encoded, key);
        encoded << '\n';
        for (unsigned char byte : encoded.str()) { hash ^= byte; hash *= UINT64_C(1099511628211); }
    }
    std::ostringstream result;
    result << std::hex << std::setfill('0') << std::setw(16) << hash;
    return result.str();
}
const char* header =
    "dataset,image,case,phase,round,order,cv_threads,omp_threads,wall_ms,api_total_ms,"
    "pyramid_ms,gradient_ms,spread_ms,response_ms,linearize_ms,preprocess_ms,search_ms,"
    "matches,semantic_count,strict_count,semantic_equal,strict_equal,count_equal,"
    "semantic_hash,strict_hash,expected_semantic_hash,expected_strict_hash,width,height,channels,templates,levels,threshold\n";
void timingFields(std::ostream& out, const Sample& sample) {
    const auto& t = sample.timing;
    out << sample.wall << ',' << t.total_ms << ',' << t.pyramid_ms << ',' << t.gradient_ms << ','
        << t.spread_ms << ',' << t.response_ms << ',' << t.linearize_ms << ','
        << t.preprocess_ms << ',' << t.search_ms << ',';
}
void configuration(std::ostream& out, int repeats, int warmups) {
    out << "{\n\"baseline\":\"independently compiled immutable V4\",\n"
        << "\"repeats\":" << repeats << ",\"warmups\":" << warmups << ",\"cold\":1,"
        << "\"cv_threads\":1,\"omp_threads\":4,\n"
        << "\"cases\":[\"v4\",\"fallback\",\"fused\"],\n"
        << "\"images\":{\"LED\":[\"1.bmp\",\"2.bmp\",\"3.bmp\",\"4.bmp\",\"5.bmp\",\"6.bmp\",\"7.bmp\",\"8.bmp\"],\"case1\":[\"case1\"]},\n"
        << "\"options\":\"all existing preprocessing/search options enabled; only fused_local_search differs between fallback and fused\",\n"
        << "\"sanity\":\"one final fused_requested_float call per image, integer_local_max=false; current dispatch uses the original float path; excluded from raw timings\",\n"
        << "\"order\":\"rotate three cases by image and round, reverse on alternate rounds\",\n"
        << "\"cold_scope\":\"fresh current workspaces and reset V4 workspace per image; not a fresh process or hardware cache\",\n"
        << "\"comparison\":\"full exact class/x/y/float-bits semantic sets, template-id strict sets, and raw counts against each image's V4 cold output; any mismatch fails\",\n"
        << "\"primary_measure\":\"internal search_ms and api_total_ms; V4 external wall includes adapter conversion\"\n}\n";
}
}

int main(int argc, char** argv) {
    try {
        std::string output;
        int repeats = 15, warmups = 2;
        for (int i = 1; i < argc; ++i) {
            const std::string arg = argv[i];
            if (arg == "--describe") { configuration(std::cout, repeats, warmups); return 0; }
            if (arg == "--csv-smoke") {
                Sample sample; sample.wall = 9; sample.timing.total_ms = 8;
                sample.timing.pyramid_ms = 1; sample.timing.gradient_ms = 2;
                sample.timing.spread_ms = 3; sample.timing.response_ms = 4;
                sample.timing.preprocess_ms = 6; sample.timing.search_ms = 7;
                std::cout << header << "LED,1.bmp,fused,measured,0,0,1,4,";
                timingFields(std::cout, sample);
                std::cout << "11,12,13,1,1,1,aaa,bbb,aaa,bbb,896,704,1,900,3,75\n";
                return 0;
            }
            if (i + 1 == argc) throw std::runtime_error("Missing argument " + arg);
            const std::string value = argv[++i];
            if (arg == "--output") output = value;
            else if (arg == "--repeats") repeats = std::stoi(value);
            else if (arg == "--warmups") warmups = std::stoi(value);
            else throw std::runtime_error("Unknown argument " + arg);
        }
        if (output.empty() || repeats < 7 || warmups < 1)
            throw std::runtime_error("Need --output, >=7 measured calls and >=1 warmup");
        std::ofstream metadata(output + "/config.json"), raw(output + "/raw.csv"),
                      sanity(output + "/float_sanity.csv");
        if (!metadata || !raw || !sanity) throw std::runtime_error("Create a fresh output directory first");
        configuration(metadata, repeats, warmups);
        raw << header << std::setprecision(12);
        sanity << "dataset,image,case,matches,semantic_equal,strict_equal,count_equal,semantic_hash,strict_hash\n";
        cv::setNumThreads(1); omp_set_dynamic(0); omp_set_num_threads(4);
        const auto fixtures = search_experiment::loadFixtures();
        std::size_t semanticFailures = 0, strictDifferences = 0, countDifferences = 0;
        for (std::size_t image = 0; image < fixtures.size(); ++image) {
            const auto& f = fixtures[image];
            f.reference->resetWorkspace();
            std::array<line2Dup::MatchWorkspace, 3> workspaces;
            Keys expected;
            std::size_t expectedCount = 0;
            auto record = [&](int which, const char* phase, int round, int order) {
                const auto result = invoke(f, configs[which], workspaces[which]);
                if (which == 0 && std::string(phase) == "cold") {
                    expected = result.keys; expectedCount = result.count;
                }
                const bool semantic = result.keys.semantic == expected.semantic;
                const bool strict = result.keys.strict == expected.strict;
                const bool count = result.count == expectedCount;
                semanticFailures += !semantic; strictDifferences += !strict; countDifferences += !count;
                raw << f.dataset << ',' << f.name << ',' << configs[which].name << ',' << phase << ','
                    << round << ',' << order << ",1,4,";
                timingFields(raw, result);
                raw << result.count << ',' << result.keys.semantic.size() << ',' << result.keys.strict.size()
                    << ',' << int(semantic) << ',' << int(strict) << ',' << int(count) << ','
                    << fingerprint(result.keys.semantic) << ',' << fingerprint(result.keys.strict) << ','
                    << fingerprint(expected.semantic) << ',' << fingerprint(expected.strict) << ','
                    << f.image.cols << ',' << f.image.rows << ',' << f.image.channels() << ','
                    << f.detector->numTemplates() << ',' << f.detector->pyramidLevels() << ',' << f.threshold << '\n';
            };
            for (int which = 0; which < 3; ++which) record(which, "cold", -1, which);
            for (int r = 0; r < warmups + repeats; ++r) {
                const bool warming = r < warmups;
                const int offset = (int(image) + r) % 3;
                for (int order = 0; order < 3; ++order)
                    record((offset + (r % 2 ? 3 - order : order)) % 3,
                           warming ? "warmup" : "measured", warming ? r : r - warmups, order);
            }
            line2Dup::MatchWorkspace floatWorkspace;
            const auto result = invoke(f, floatSanity, floatWorkspace);
            const bool semantic = result.keys.semantic == expected.semantic;
            const bool strict = result.keys.strict == expected.strict;
            const bool count = result.count == expectedCount;
            semanticFailures += !semantic; strictDifferences += !strict; countDifferences += !count;
            sanity << f.dataset << ',' << f.name << ',' << floatSanity.name << ',' << result.count << ','
                   << int(semantic) << ',' << int(strict) << ',' << int(count) << ','
                   << fingerprint(result.keys.semantic) << ',' << fingerprint(result.keys.strict) << '\n';
            raw.flush(); sanity.flush();
            std::cout << "completed " << f.dataset << '/' << f.name << '\n';
        }
        std::ofstream validation(output + "/validation.json");
        validation << "{\"semantic_failures\":" << semanticFailures << ",\"strict_set_differences\":"
                   << strictDifferences << ",\"raw_count_differences\":" << countDifferences << "}\n";
        return semanticFailures || strictDifferences || countDifferences ? 2 : 0;
    } catch (const std::exception& e) { std::cerr << e.what() << '\n'; return 1; }
}
