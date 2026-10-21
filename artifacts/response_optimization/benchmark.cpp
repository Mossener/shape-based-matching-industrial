// Same-process benchmark; does not execute unless invoked explicitly.
#define main legacyLedMain
#include "../led_match/led_demo.cpp"
#undef main
#include "../../tests/reference_matcher.hpp"

#include <array>
#include <cstdint>
#include <set>
#include <tuple>

namespace {
using Clock = std::chrono::steady_clock;
using Semantic = std::tuple<int,int,uint32_t,std::string>;
using Strict = std::tuple<int,int,uint32_t,std::string,int>;
struct Keys { std::set<Semantic> semantic; std::set<Strict> strict; };
struct Config { const char* name; bool spread, fusion, reuse, original; };
const std::array<Config,6> configs{{
    {"original",false,false,false,true}, {"all_false",false,false,false,false},
    {"spread_only",true,false,false,false}, {"fusion_only",false,true,false,false},
    {"reuse_only",false,false,true,false}, {"all",true,true,true,false}
}};

template<class Matches> Keys keys(const Matches& matches) {
    Keys result;
    for (const auto& m : matches) {
        uint32_t score;
        static_assert(sizeof(score)==sizeof(m.similarity),"Expected float score");
        std::memcpy(&score,&m.similarity,sizeof(score));
        result.semantic.emplace(m.x,m.y,score,m.class_id);
        result.strict.emplace(m.x,m.y,score,m.class_id,m.template_id);
    }
    return result;
}

template<class Set> std::string fingerprint(const Set& values) {
    // A human-readable stable digest supplements actual in-memory set equality.
    std::ostringstream serialized;
    for (const auto& key : values) {
        serialized << std::get<0>(key) << ',' << std::get<1>(key) << ',' << std::get<2>(key)
                   << ',' << std::get<3>(key) << ';';
    }
    uint64_t hash=14695981039346656037ULL;
    for (unsigned char c : serialized.str()) {hash ^= c; hash *= 1099511628211ULL;}
    std::ostringstream out; out << std::hex << hash; return out.str();
}
std::string strictFingerprint(const std::set<Strict>& values) {
    uint64_t hash=14695981039346656037ULL;
    for (const auto& k:values) {
        std::ostringstream s;
        s << std::get<0>(k) << ',' << std::get<1>(k) << ',' << std::get<2>(k) << ','
          << std::get<3>(k) << ',' << std::get<4>(k) << ';';
        for (unsigned char c:s.str()) {hash^=c;hash*=1099511628211ULL;}
    }
    std::ostringstream out;out<<std::hex<<hash;return out.str();
}

struct Invocation {
    double wall;
    line2Dup::MatchTimings timing;
    Keys result;
    size_t matches;
};
const char* csvHeader = "image,cv_threads,omp_threads,mode,case,phase,round,order,total_ms,api_total_ms,"
    "pyramid_ms,gradient_ms,spread_ms,response_ms,linearize_ms,preprocess_ms,search_ms,"
    "match_count,semantic_count,strict_count,semantic_equal,strict_equal,count_equal,semantic_hash,strict_hash,padded_width,padded_height\n";

void writeStageFields(std::ostream& out,const Invocation& result,bool original) {
    const auto& t=result.timing;
    if(original) out << ",,,,,," << t.preprocess_ms << ',' << t.search_ms << ',';
    else out << t.total_ms << ',' << t.pyramid_ms << ',' << t.gradient_ms << ',' << t.spread_ms
             << ',' << t.response_ms << ',' << t.linearize_ms << ',' << t.preprocess_ms << ',' << t.search_ms << ',';
}

Invocation invoke(const Config& config, const line2Dup::Detector& detector,
                  const response_reference::Matcher& reference, const cv::Mat& padded,
                  line2Dup::MatchWorkspace& workspace) {
    Invocation result;
    if(config.original) {
        const auto start=Clock::now();
        const auto found=reference.match(padded,75.f,{"LED"});
        result.wall=std::chrono::duration<double,std::milli>(Clock::now()-start).count();
        result.timing.preprocess_ms=reference.lastTimings().preprocess_ms;
        result.timing.search_ms=reference.lastTimings().search_ms;
        result.result=keys(found);result.matches=found.size();
    } else {
        line2Dup::MatchOptions options;
        options.separable_spread=config.spread;options.fused_response=config.fusion;
        options.reuse_buffers=config.reuse;options.log_timing=false;
        const auto start=Clock::now();
        const auto found=detector.match(padded,75.f,workspace,options,&result.timing,{"LED"});
        result.wall=std::chrono::duration<double,std::milli>(Clock::now()-start).count();
        result.result=keys(found);result.matches=found.size();
    }
    return result;
}

void metadata(std::ostream& out,int repeats,int warmups) {
    out << "{\n  \"benchmark\":\"same-process response construction ablation\",\n"
        << "  \"pyramid_steps\":[4,8,8],\"template_count\":900,\"feature_counts\":[236,111,46],\n"
        << "  \"threshold\":75,\"padding\":64,\"openmp_threads\":4,\"opencv_threads\":[1,2,4],\"images\":[1,2,3,4,5,6,7,8],\n"
        << "  \"repeats\":" << repeats << ",\"warmups_per_image_case_threads_mode\":" << warmups << ",\n"
        << "  \"cases\":[\"original\",\"all_false\",\"spread_only\",\"fusion_only\",\"reuse_only\",\"all\"],\n"
        << "  \"modes\":[\"full\",\"preprocess_only\"],\n"
        << "  \"measured_order\":\"rotate all six cases each round and image; alternate direction each round\",\n"
        << "  \"cold_definition\":\"first call per image/config/thread/mode, fresh workspace; not fresh process or cache flush\",\n"
        << "  \"original_stage_timing\":\"preprocess/search parsed from original log; finer stages unavailable; external total includes adapter log capture overhead\",\n"
        << "  \"semantic_key\":\"set(x,y,float_score_bits,class_id); drops template_id to handle equal-score duplicate pruning\",\n"
        << "  \"strict_key\":\"set(x,y,float_score_bits,class_id,template_id); raw match_count also recorded\",\n"
        << "  \"timing_scope\":\"wall surrounds match call only; key comparison, input I/O, template import, CSV excluded\"\n}\n";
}
}

int main(int argc,char** argv) {
    try {
        std::string input="LED",output="artifacts/response_optimization/run";
        int repeats=7,warmups=1;
        for(int arg=1;arg<argc;++arg) {
            const std::string option=argv[arg];
            if(option=="--describe") {metadata(std::cout,repeats,warmups);return 0;}
            if(option=="--csv-smoke") {
                Invocation sample{};
                sample.timing.total_ms=9;sample.timing.pyramid_ms=1;sample.timing.gradient_ms=2;
                sample.timing.spread_ms=3;sample.timing.response_ms=4;sample.timing.linearize_ms=5;
                sample.timing.preprocess_ms=6;sample.timing.search_ms=7;
                std::cout << csvHeader;
                for(bool original : {true,false}) {
                    std::cout << "1.bmp,1,4,full," << (original?"original":"all_false") << ",measured,0,0,10,";
                    writeStageFields(std::cout,sample,original);
                    std::cout << "11,12,13,1,1,1,abc,def,896,704\n";
                }
                return 0;
            }
            if(arg+1==argc) throw std::runtime_error("Missing argument for "+option);
            const std::string value=argv[++arg];
            if(option=="--input") input=value;
            else if(option=="--output") output=value;
            else if(option=="--repeats") repeats=std::stoi(value);
            else if(option=="--warmups") warmups=std::stoi(value);
            else throw std::runtime_error("Unknown option: "+option);
        }
        if(repeats<7 || warmups<1) throw std::runtime_error("Use >=7 measured calls and >=1 warmup");
        std::ofstream config(output+"/config.json"),raw(output+"/raw.csv");
        if(!config || !raw) throw std::runtime_error("Create benchmark output directory first");
        metadata(config,repeats,warmups);
        raw << csvHeader;
        raw << std::setprecision(12);
        omp_set_dynamic(0);omp_set_num_threads(4);
        SmdDetector full(input+"/ku.smd",3);
        for(int s=0;s<5;++s) for(int a=0;a<360;a+=2) full.addPose(float(a),0.9f+0.05f*s);
        line2Dup::Detector empty(128,{4,8,8},20,40);
        cv::FileStorage fs("",cv::FileStorage::WRITE|cv::FileStorage::MEMORY);
        full.writeClass("LED",fs);
        response_reference::Matcher reference(128,{4,8,8},20,40),emptyReference(128,{4,8,8},20,40);
        reference.loadClass(fs.releaseAndGetString());
        int semanticFailures=0,strictDifferences=0;
        for(int cvThreads : {1,2,4}) {
            cv::setNumThreads(cvThreads);
            for(int image=1;image<=8;++image) {
                const auto gray=cv::imread(input+"/"+std::to_string(image)+".bmp",cv::IMREAD_GRAYSCALE);
                if(gray.empty()) throw std::runtime_error("Cannot read LED image");
                cv::Mat padded;cv::copyMakeBorder(gray,padded,64,64,64,64,cv::BORDER_CONSTANT,cv::Scalar(0));
                if(padded.rows%32 || padded.cols%32) throw std::runtime_error("Expected input dimensions divisible by 32");
                for(int mode=0;mode<2;++mode) {
                    const auto& detector=mode ? empty : static_cast<const line2Dup::Detector&>(full);
                    const auto& baseline=mode ? emptyReference : reference;
                    const char* modeName=mode ? "preprocess_only" : "full";
                    std::array<line2Dup::MatchWorkspace,6> workspaces;
                    Keys expected;size_t expectedCount=0;
                    auto record=[&](int which,const char* phase,int round,int order) {
                        const auto result=invoke(configs[which],detector,baseline,padded,workspaces[which]);
                        if(which==0 && std::string(phase)=="cold") {
                            expected=result.result;expectedCount=result.matches;
                            if(!mode && expected.semantic.empty())
                                throw std::runtime_error("Original matcher produced no positive LED match");
                        }
                        const bool semantic=result.result.semantic==expected.semantic;
                        const bool strict=result.result.strict==expected.strict;
                        if(!semantic) ++semanticFailures;
                        if(!strict) ++strictDifferences;
                        raw << image << ".bmp," << cvThreads << ",4," << modeName << ',' << configs[which].name
                            << ',' << phase << ',' << round << ',' << order << ',' << result.wall << ',';
                        writeStageFields(raw,result,configs[which].original);
                        raw << result.matches << ',' << result.result.semantic.size() << ',' << result.result.strict.size()
                            << ',' << int(semantic) << ',' << int(strict) << ',' << int(result.matches==expectedCount)
                            << ',' << fingerprint(result.result.semantic) << ',' << strictFingerprint(result.result.strict)
                            << ',' << padded.cols << ',' << padded.rows << '\n';
                    };
                    // First reference call doubles as this image/thread/mode's correctness oracle.
                    record(0,"cold",-1,0);
                    for(int n=1;n<6;++n) record(n,"cold",-1,n);
                    for(int r=0;r<warmups+repeats;++r) {
                        const bool warming=r<warmups;
                        const int offset=(r+image+cvThreads+mode)%6;
                        for(int order=0;order<6;++order) {
                            const int which=(offset+(r%2 ? 6-order : order))%6;
                            record(which,warming?"warmup":"measured",warming?r:r-warmups,order);
                        }
                    }
                    raw.flush();
                    std::cout << "completed threads=" << cvThreads << " image=" << image << " mode=" << modeName << '\n';
                }
            }
        }
        std::ofstream validation(output+"/validation.json");
        validation << "{\"semantic_failures\":" << semanticFailures << ",\"strict_set_differences\":"
                   << strictDifferences << ",\"strict_differences_alone_are_not_failures\":true}\n";
        return semanticFailures ? 2 : 0;
    } catch(const std::exception& e) {std::cerr<<e.what()<<'\n';return 1;}
}
