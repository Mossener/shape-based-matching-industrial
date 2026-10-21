#include "fixtures.hpp"
#include <cstdint>

namespace {
using Clock=std::chrono::steady_clock;
struct Config {const char* name;unsigned bits;bool reference;};
const std::array<Config,6> configs{{{"v4",0,true},{"all_false",0,false},
    {"integer_only",1,false},{"direct8_only",2,false},{"reuse_only",4,false},{"all",7,false}}};
struct Sample {
    line2Dup::MatchTimings t;
    double wall=0;
    size_t count=0;
    search_experiment::Keys keys;
    int x=0,y=0,templateId=-1;
    float score=0;
};
const char* header="dataset,image,case,phase,round,order,cv_threads,omp_threads,total_ms,api_total_ms,"
    "pyramid_ms,gradient_ms,spread_ms,response_ms,linearize_ms,preprocess_ms,search_ms,"
    "matches,semantic_count,strict_count,semantic_equal,strict_equal,count_equal,best_score,best_x,best_y,best_template_id,width,height,channels,templates,levels,threshold\n";

Sample invoke(const search_experiment::Fixture& f,const Config& c,line2Dup::MatchWorkspace& workspace) {
    Sample result;
    if(c.reference) {
        const auto start=Clock::now();
        const auto matches=f.reference->match(f.image,f.threshold,{f.class_id});
        result.wall=std::chrono::duration<double,std::milli>(Clock::now()-start).count();
        const auto t=f.reference->lastTimings();
        result.t.pyramid_ms=t.pyramid_ms;result.t.gradient_ms=t.gradient_ms;
        result.t.spread_ms=t.spread_ms;result.t.response_ms=t.response_ms;
        result.t.linearize_ms=t.linearize_ms;result.t.preprocess_ms=t.preprocess_ms;
        result.t.search_ms=t.search_ms;result.t.total_ms=t.total_ms;
        result.count=matches.size();result.keys=search_experiment::keys(matches);
        if(!matches.empty()) {const auto& m=matches.front();result.x=m.x;result.y=m.y;result.score=m.similarity;result.templateId=m.template_id;}
    } else {
        const auto start=Clock::now();
        const auto matches=f.detector->match(f.image,f.threshold,workspace,
            search_experiment::options(c.bits),&result.t,{f.class_id});
        result.wall=std::chrono::duration<double,std::milli>(Clock::now()-start).count();
        result.count=matches.size();result.keys=search_experiment::keys(matches);
        if(!matches.empty()) {const auto& m=matches.front();result.x=m.x;result.y=m.y;result.score=m.similarity;result.templateId=m.template_id;}
    }
    return result;
}
void timingFields(std::ostream& out,const Sample& r) {
    const auto& t=r.t;
    out << r.wall << ',' << t.total_ms << ',' << t.pyramid_ms << ',' << t.gradient_ms << ','
        << t.spread_ms << ',' << t.response_ms << ',' << t.linearize_ms << ','
        << t.preprocess_ms << ',' << t.search_ms << ',';
}
void config(std::ostream& out,int repeats,int warmups) {
    out << "{\"baseline\":\"immutable V4 response-optimized implementation\",\n"
        << "\"repeats\":" << repeats << ",\"warmups\":" << warmups << ",\"cv_threads\":1,\"omp_threads\":4,\n"
        << "\"cases\":[\"v4\",\"all_false\",\"integer_only\",\"direct8_only\",\"reuse_only\",\"all\"],\n"
        << "\"images\":{\"LED\":[\"1.bmp\",\"2.bmp\",\"3.bmp\",\"4.bmp\",\"5.bmp\",\"6.bmp\",\"7.bmp\",\"8.bmp\"],\"case1\":[\"case1\"]},\n"
        << "\"preprocessing_options\":\"all three enabled for every case including V4\",\n"
        << "\"LED\":{\"levels\":3,\"steps\":[4,8,8],\"templates\":900,\"threshold\":75,\"channels\":1,\"padding\":64},\n"
        << "\"case1\":{\"levels\":2,\"steps\":[4,8],\"templates\":361,\"threshold\":90,\"channels\":3,\"padding\":250},\n"
        << "\"order\":\"rotate six cases each round and reverse on alternate rounds\",\n"
        << "\"cold\":\"fresh current workspaces and reset V4 workspace per image, not a fresh process/cache\",\n"
        << "\"comparison\":\"exact semantic sets and strict sets plus raw counts; semantic differences fail\",\n"
        << "\"wall_limit\":\"V4 external wall includes Match-to-Result conversion; internal total/search exclude adapter conversion\"}\n";
}
}
int main(int argc,char** argv) {
    try {
        std::string output="artifacts/search_optimization/run";int repeats=15,warmups=2;
        for(int i=1;i<argc;++i) {
            const std::string arg=argv[i];
            if(arg=="--describe") {config(std::cout,repeats,warmups);return 0;}
            if(arg=="--csv-smoke") {
                Sample sample;sample.wall=9;sample.t.total_ms=8;sample.t.pyramid_ms=1;
                sample.t.gradient_ms=2;sample.t.spread_ms=3;sample.t.response_ms=4;
                sample.t.linearize_ms=0;sample.t.preprocess_ms=6;sample.t.search_ms=7;
                std::cout<<header<<"LED,1.bmp,v4,measured,0,0,1,4,";
                timingFields(std::cout,sample);
                std::cout<<"11,12,13,1,1,1,98,100,101,22,896,704,1,900,3,75\n";return 0;
            }
            if(i+1==argc) throw std::runtime_error("Missing argument "+arg);
            const std::string value=argv[++i];
            if(arg=="--output") output=value;
            else if(arg=="--repeats") repeats=std::stoi(value);
            else if(arg=="--warmups") warmups=std::stoi(value);
            else throw std::runtime_error("Unknown argument "+arg);
        }
        if(repeats<7 || warmups<1) throw std::runtime_error("Need >=7 measured calls and >=1 warmup");
        std::ofstream metadata(output+"/config.json"),raw(output+"/raw.csv");
        if(!metadata||!raw) throw std::runtime_error("Create a fresh output directory first");
        config(metadata,repeats,warmups);raw<<header<<std::setprecision(12);
        cv::setNumThreads(1);omp_set_dynamic(0);omp_set_num_threads(4);
        const auto fixtures=search_experiment::loadFixtures();
        int semanticFailures=0,strictDifferences=0,countDifferences=0;
        for(size_t image=0;image<fixtures.size();++image) {
            const auto& f=fixtures[image];f.reference->resetWorkspace();
            std::array<line2Dup::MatchWorkspace,6> workspaces;
            search_experiment::Keys expected;size_t expectedCount=0;
            auto record=[&](int which,const char* phase,int round,int order) {
                const auto result=invoke(f,configs[which],workspaces[which]);
                if(which==0&&std::string(phase)=="cold") {expected=result.keys;expectedCount=result.count;}
                const bool semantic=result.keys.semantic==expected.semantic;
                const bool strict=result.keys.strict==expected.strict;
                const bool count=result.count==expectedCount;
                semanticFailures+=!semantic;strictDifferences+=!strict;countDifferences+=!count;
                raw<<f.dataset<<','<<f.name<<','<<configs[which].name<<','<<phase<<','<<round<<','<<order<<",1,4,";
                timingFields(raw,result);
                raw<<result.count<<','<<result.keys.semantic.size()<<','<<result.keys.strict.size()<<','
                   <<int(semantic)<<','<<int(strict)<<','<<int(count)<<','<<result.score<<','
                   <<result.x<<','<<result.y<<','<<result.templateId<<','<<f.image.cols<<','<<f.image.rows<<','
                   <<f.image.channels()<<','<<f.detector->numTemplates()<<','<<f.detector->pyramidLevels()<<','<<f.threshold<<'\n';
            };
            for(int which=0;which<6;++which) record(which,"cold",-1,which);
            for(int r=0;r<warmups+repeats;++r) {
                const bool warming=r<warmups;
                const int offset=(int(image)+r)%6;
                for(int order=0;order<6;++order)
                    record((offset+(r%2 ? 6-order : order))%6,warming?"warmup":"measured",warming?r:r-warmups,order);
            }
            raw.flush();std::cout<<"completed "<<f.dataset<<'/'<<f.name<<'\n';
        }
        std::ofstream validation(output+"/validation.json");
        validation<<"{\"semantic_failures\":"<<semanticFailures<<",\"strict_set_differences\":"<<strictDifferences
                  <<",\"raw_count_differences\":"<<countDifferences<<"}\n";
        return semanticFailures||countDifferences ? 2 : 0;
    } catch(const std::exception& e) {std::cerr<<e.what()<<'\n';return 1;}
}
