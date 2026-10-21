#include "../search_optimization/fixtures.hpp"
#define main consolidationVerificationMain
#include "verify.cpp"
#undef main
#include "stage_reference.hpp"

int main(int argc,char** argv){
    try{
        std::string output="artifacts/match_consolidation/timing";
        if(argc==3&&std::string(argv[1])=="--output")output=argv[2];else if(argc!=1)throw std::runtime_error("Expected --output prefix");
        const auto all=loadCases("datasets/tless_train_f32/templates_tless_object_1.yml.gz","datasets/tless_tiny",false);
        std::vector<Case> selected;
        for(const auto& f:all)if(f.dataset!="TLESS_dev"||f.name=="s5_i7"||f.name=="s5_i70"||f.name=="s2_i3"||f.name=="s2_i92")selected.push_back(f);
        if(selected.size()!=13)throw std::runtime_error("Expected nine existing plus four public cases");
        cv::setNumThreads(1);omp_set_dynamic(0);omp_set_num_threads(4);
        std::ofstream total(output+"_total.csv"),stage(output+"_stage.csv");
        if(!total||!stage)throw std::runtime_error("Cannot create timing outputs");
        total<<std::setprecision(12)<<"dataset,image,phase,round,order,implementation,api_total_ms,search_ms,count,canonical_equal\n";
        stage<<std::setprecision(12)<<"dataset,image,phase,round,old_first,input_count,old_count,new_count,old_ms,new_ms,extra_ms\n";
        std::size_t failures=0;
        for(std::size_t image=0;image<selected.size();++image){const auto& f=selected[image];
            const auto expected=canonical(records(f.v10->match(f.image,f.threshold,{f.id})));
            f.v10->resetWorkspace();line2Dup::MatchWorkspace workspace;
            for(int r=-3;r<7;++r){const char* phase=r==-3?"cold":r<0?"warmup":"measured";
                for(int order=0;order<2;++order){const bool current=(order+int(image)+r+3)%2;
                    double api=0,search=0;Records actual;
                    if(current){auto options=search_experiment::options(7);options.fused_local_search=true;line2Dup::MatchTimings t;
                        actual=records(f.current->match(f.image,f.threshold,workspace,options,&t,{f.id}));api=t.total_ms;search=t.search_ms;
                    }else{actual=records(f.v10->match(f.image,f.threshold,{f.id}));const auto t=f.v10->lastTimings();api=t.total_ms;search=t.search_ms;}
                    const bool equal=canonical(actual)==expected;failures+=!equal;
                    total<<f.dataset<<','<<f.name<<','<<phase<<','<<r<<','<<order<<','<<(current?"current_stable":"v10_reference")<<','<<api<<','<<search<<','<<actual.size()<<','<<equal<<'\n';
                }
            }
            const bool led=f.dataset=="LED",part=f.dataset=="TLESS_dev";
            stage_reference::Matcher diagnostic(part?32:128,led?std::vector<int>{4,8,8}:std::vector<int>{4,8},part||led?20:30,part||led?40:60);
            diagnostic.loadClass(exported(*f.current,f.id));
            for(int r=-3;r<7;++r){const char* phase=r==-3?"cold":r<0?"warmup":"measured";
                const auto t=diagnostic.match(f.image,f.threshold,{f.id});
                failures+=t.new_count!=expected.size();
                stage<<f.dataset<<','<<f.name<<','<<phase<<','<<r<<','<<t.old_first<<','<<t.input_count<<','<<t.old_count<<','<<t.new_count<<','<<t.old_ms<<','<<t.new_ms<<','<<t.new_ms-t.old_ms<<'\n';
            }
            total.flush();stage.flush();std::cout<<"timed "<<f.dataset<<'/'<<f.name<<" failures="<<failures<<'\n';
        }
        return failures?2:0;
    }catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}
}
