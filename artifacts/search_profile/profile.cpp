#include "../search_optimization/fixtures.hpp"
#include "source/line2Dup.h"
#include <map>

namespace {
using Clock=std::chrono::steady_clock;
struct Totals {
    double coarse=0,collect=0,local=0,argmax=0,filter=0;
    std::uint64_t scanned=0,prefix=0,valid=0,zero_tail=0,wrapped=0;
    std::uint64_t coarse_candidates=0,zero_candidates=0,wrapped_candidates=0,local_calls=0;
};
Totals totals(const search_profile::Call& call) {
    Totals t;
    for(const auto& p:call.templates) {
        t.coarse+=p.coarse_similarity_ms;t.collect+=p.coarse_collect_ms;
        t.scanned+=p.map_positions;t.prefix+=p.accumulated_prefix;t.valid+=p.geometrically_valid;
        t.zero_tail+=p.zero_tail_scanned;t.wrapped+=p.wrapped_prefix_scanned;
        t.coarse_candidates+=p.coarse_candidates;t.zero_candidates+=p.zero_tail_candidates;
        t.wrapped_candidates+=p.wrapped_candidates;
        for(const auto& l:p.levels) {
            t.local+=l.similarity_ms;t.argmax+=l.argmax_ms;t.filter+=l.filter_ms;t.local_calls+=l.local_calls;
        }
    }
    return t;
}
std::shared_ptr<profiledLine2Dup::Detector> clone(const search_experiment::Fixture& f) {
    std::vector<int> steps;
    for(int l=0;l<f.detector->pyramidLevels();++l) steps.push_back(f.detector->getT(l));
    const auto& m=*f.detector->getModalities();
    auto detector=std::make_shared<profiledLine2Dup::Detector>(int(m.num_features),steps,m.weak_threshold,m.strong_threshold);
    cv::FileStorage serialized("profile.yml",cv::FileStorage::WRITE|cv::FileStorage::MEMORY);
    f.detector->writeClass(f.class_id,serialized);
    cv::FileStorage input(serialized.releaseAndGetString(),cv::FileStorage::READ|cv::FileStorage::MEMORY);
    detector->readClass(input.root());
    CV_Assert(detector->numTemplates()==f.detector->numTemplates());
    return detector;
}
profiledLine2Dup::MatchOptions options() {
    profiledLine2Dup::MatchOptions o;
    o.separable_spread=o.fused_response=o.reuse_buffers=true;
    o.integer_local_max=o.direct_8bit_search=o.reuse_search_buffers=true;
    o.log_timing=false;return o;
}
void describe(std::ostream& out,int repeats,int warmups) {
    out<<"{\"purpose\":\"throwaway search composition profile, not an uninstrumented speed benchmark\",\n"
       <<"\"comparison\":\"current V9 vs isolated instrumented current V9, exact semantic/strict sets and raw counts before profile\",\n"
       <<"\"timer\":\"steady_clock; per-template worker elapsed intervals include kernel map zeroing and any conversion; worker sums are not wall or process CPU time\",\n"
       <<"\"cv_threads\":1,\"omp_threads\":4,\"repeats\":"<<repeats<<",\"warmups\":"<<warmups<<",\n"
       <<"\"flags\":\"all preprocessing and all search options true; fixtures/template banks/thresholds unchanged\",\n"
       <<"\"LED\":{\"templates\":900,\"levels\":3,\"steps\":[4,8,8],\"threshold\":75},\n"
       <<"\"case1\":{\"templates\":361,\"levels\":2,\"steps\":[4,8],\"threshold\":90}}\n";
}
}
int main(int argc,char** argv) {
    try {
        std::string output,dataset,image;int repeats=7,warmups=2;bool validateOnly=false;
        for(int i=1;i<argc;++i) {
            const std::string arg=argv[i];
            if(arg=="--describe") {describe(std::cout,repeats,warmups);return 0;}
            if(arg=="--validate-only") {validateOnly=true;continue;}
            if(i+1==argc) throw std::runtime_error("Missing value "+arg);
            const std::string value=argv[++i];
            if(arg=="--output") output=value;
            else if(arg=="--repeats") repeats=std::stoi(value);
            else if(arg=="--warmups") warmups=std::stoi(value);
            else if(arg=="--dataset") dataset=value;
            else if(arg=="--image") image=value;
            else throw std::runtime_error("Unknown argument "+arg);
        }
        if(output.empty()||repeats<1||warmups<0) throw std::runtime_error("Need --output, repeats>=1, warmups>=0");
        std::ofstream config(output+"/config.json"),validation(output+"/validation.csv");
        if(!config||!validation) throw std::runtime_error("Create a fresh output directory first");
        describe(config,repeats,warmups);
        validation<<"dataset,image,current_count,profile_count,current_semantic,profile_semantic,current_strict,profile_strict,semantic_equal,strict_equal,count_equal\n";
        cv::setNumThreads(1);omp_set_dynamic(0);omp_set_num_threads(4);
        const auto all=search_experiment::loadFixtures();
        std::vector<search_experiment::Fixture> fixtures;
        for(const auto& f:all) if((dataset.empty()||f.dataset==dataset)&&(image.empty()||f.name==image)) fixtures.push_back(f);
        if(fixtures.empty()) throw std::runtime_error("No fixtures selected");
        std::map<std::string,std::shared_ptr<profiledLine2Dup::Detector>> detectors;
        std::vector<search_experiment::Keys> expected;
        std::vector<std::size_t> expectedCounts;
        int failures=0,strictDifferences=0;
        for(const auto& f:fixtures) {
            if(!detectors.count(f.dataset)) detectors[f.dataset]=clone(f);
            line2Dup::MatchWorkspace currentWorkspace;line2Dup::MatchTimings currentTimings;
            profiledLine2Dup::MatchWorkspace profileWorkspace;profiledLine2Dup::MatchTimings profileTimings;
            const auto current=f.detector->match(f.image,f.threshold,currentWorkspace,search_experiment::options(7),&currentTimings,{f.class_id});
            const auto profiled=detectors[f.dataset]->match(f.image,f.threshold,profileWorkspace,options(),&profileTimings,{f.class_id});
            const auto a=search_experiment::keys(current),b=search_experiment::keys(profiled);
            const bool semantic=a.semantic==b.semantic,strict=a.strict==b.strict,count=current.size()==profiled.size();
            failures+=!semantic||!count;strictDifferences+=!strict;
            expected.push_back(a);expectedCounts.push_back(current.size());
            validation<<f.dataset<<','<<f.name<<','<<current.size()<<','<<profiled.size()<<','<<a.semantic.size()<<','<<b.semantic.size()<<','
                      <<a.strict.size()<<','<<b.strict.size()<<','<<semantic<<','<<strict<<','<<count<<'\n';
            std::cout<<"validation "<<f.dataset<<'/'<<f.name<<" semantic="<<semantic<<" strict="<<strict<<" count="<<count<<std::endl;
        }
        validation.flush();
        if(failures) throw std::runtime_error("Instrumented/current semantic or count validation failed; no profiles started");
        std::cout<<"All pre-profile correctness checks passed; strict set differences="<<strictDifferences<<std::endl;
        if(validateOnly) return 0;
        std::ofstream calls(output+"/calls.csv"),templates(output+"/templates.csv"),levels(output+"/levels.csv");
        if(!calls||!templates||!levels) throw std::runtime_error("Profile output open failed");
        calls<<"dataset,image,phase,round,wall_ms,api_total_ms,preprocess_ms,search_wall_ms,coarse_similarity_worker_sum_ms,coarse_collect_worker_sum_ms,local_similarity_worker_sum_ms,local_argmax_worker_sum_ms,local_filter_worker_sum_ms,final_sort_wall_ms,final_unique_wall_ms,map_positions,accumulated_prefix,geometrically_valid,zero_tail_scanned,wrapped_prefix_scanned,coarse_candidates,zero_tail_candidates,wrapped_candidates,local_calls,matches_before_sort,matches_after_unique,semantic_equal,strict_equal,count_equal\n";
        templates<<"dataset,image,round,class_id,template_id,worker,coarse_level,coarse_features,coarse_similarity_worker_ms,coarse_collect_worker_ms,map_positions,accumulated_prefix,geometrically_valid,zero_tail_scanned,wrapped_prefix_scanned,coarse_candidates,zero_tail_candidates,wrapped_candidates\n";
        levels<<"dataset,image,round,class_id,template_id,worker,level,kind,features,candidates_in,candidates_out,local_calls,x_clamped,y_clamped,similarity_worker_ms,argmax_worker_ms,filter_worker_ms\n";
        calls<<std::setprecision(12);templates<<std::setprecision(12);levels<<std::setprecision(12);
        for(std::size_t i=0;i<fixtures.size();++i) {
            const auto& f=fixtures[i];profiledLine2Dup::MatchWorkspace workspace;
            for(int r=-warmups-1;r<repeats;++r) {
                const char* phase=r==-warmups-1?"cold":r<0?"warmup":"measured";
                profiledLine2Dup::MatchTimings t;const auto started=Clock::now();
                const auto found=detectors[f.dataset]->match(f.image,f.threshold,workspace,options(),&t,{f.class_id});
                const double wall=std::chrono::duration<double,std::milli>(Clock::now()-started).count();
                const auto actual=search_experiment::keys(found);const bool semantic=actual.semantic==expected[i].semantic;
                const bool strict=actual.strict==expected[i].strict,count=found.size()==expectedCounts[i];
                if(!semantic||!count) throw std::runtime_error("Profile output changed after pre-profile validation");
                const auto s=totals(t.profile);
                calls<<f.dataset<<','<<f.name<<','<<phase<<','<<r<<','<<wall<<','<<t.total_ms<<','<<t.preprocess_ms<<','<<t.search_ms<<','
                     <<s.coarse<<','<<s.collect<<','<<s.local<<','<<s.argmax<<','<<s.filter<<','<<t.profile.final_sort_ms<<','<<t.profile.final_unique_ms<<','
                     <<s.scanned<<','<<s.prefix<<','<<s.valid<<','<<s.zero_tail<<','<<s.wrapped<<','<<s.coarse_candidates<<','<<s.zero_candidates<<','
                     <<s.wrapped_candidates<<','<<s.local_calls<<','<<t.profile.matches_before_sort<<','<<t.profile.matches_after_unique<<','<<semantic<<','<<strict<<','<<count<<'\n';
                if(r>=0) for(const auto& p:t.profile.templates) {
                    templates<<f.dataset<<','<<f.name<<','<<r<<','<<p.class_id<<','<<p.template_id<<','<<p.worker<<','<<p.coarse_level<<','<<p.coarse_feature_count<<','
                             <<p.coarse_similarity_ms<<','<<p.coarse_collect_ms<<','<<p.map_positions<<','<<p.accumulated_prefix<<','<<p.geometrically_valid<<','
                             <<p.zero_tail_scanned<<','<<p.wrapped_prefix_scanned<<','<<p.coarse_candidates<<','<<p.zero_tail_candidates<<','<<p.wrapped_candidates<<'\n';
                    levels<<f.dataset<<','<<f.name<<','<<r<<','<<p.class_id<<','<<p.template_id<<','<<p.worker<<','<<p.coarse_level<<",coarse,"<<p.coarse_feature_count<<','
                          <<p.map_positions<<','<<p.coarse_candidates<<",0,0,0,"<<p.coarse_similarity_ms<<",0,0\n";
                    for(int l=p.coarse_level-1;l>=0;--l) {const auto& a=p.levels[l];
                        levels<<f.dataset<<','<<f.name<<','<<r<<','<<p.class_id<<','<<p.template_id<<','<<p.worker<<','<<l<<",local,"<<a.feature_count<<','
                              <<a.candidates_in<<','<<a.candidates_out<<','<<a.local_calls<<','<<a.x_clamped<<','<<a.y_clamped<<','<<a.similarity_ms<<','<<a.argmax_ms<<','<<a.filter_ms<<'\n';
                    }
                }
            }
            calls.flush();templates.flush();levels.flush();std::cout<<"profile completed "<<f.dataset<<'/'<<f.name<<std::endl;
        }
        return 0;
    } catch(const std::exception& e) {std::cerr<<e.what()<<'\n';return 1;}
}
