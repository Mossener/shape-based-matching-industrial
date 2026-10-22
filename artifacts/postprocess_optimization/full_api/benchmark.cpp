// Exact fixed950-call common25 schedule, with full output archives outside clocks.
#include "fixtures.hpp"
#include "evidence.hpp"
#include <array>
#include <iostream>
#include <omp.h>

int main(int argc,char** argv) {
    try {
        using postprocess_evidence::require;
        const std::array<const char*,2> variants{{"exact_v11","index_reserve_copy_actual_match"}};
        std::string root,output;
        for(int i=1;i<argc;++i) {
            const std::string key=argv[i];require(i+1<argc,"Missing argument value");const std::string value=argv[++i];
            if(key=="--root")root=value;else if(key=="--output-directory")output=value;
            else throw std::runtime_error("Unknown argument "+key);
        }
        require(!root.empty()&&!output.empty(),"Explicit root and fresh output directory required");
        postprocess_evidence::literalRecordComparisonChecks();
        // Verify the entire declarative position schedule before any API call.
        for(int i=0;i<25;++i) {
            int counts[2][2]={{0,0},{0,0}};
            for(int r=0;r<16;++r) {
                const int k=i+r+3;std::array<int,2> order{{0,1}};
                if(k%2)std::swap(order[0],order[1]);if((k/2)%2)std::swap(order[0],order[1]);
                for(int p=0;p<2;++p)++counts[order[p]][p];
            }
            require(counts[0][0]==8&&counts[0][1]==8&&counts[1][0]==8&&counts[1][1]==8,
                    "Formal schedule position balance differs");
        }
        cv::setNumThreads(1);omp_set_dynamic(0);omp_set_max_active_levels(1);omp_set_num_threads(4);
        const auto fixtures=postprocess_fixtures::fixtures(root);require(fixtures.size()==27,"Base fixture scope differs");
        postprocess_evidence::Benchmark audit(output);unsigned baselineCalls=0,candidateCalls=0;
        for(int i=0;i<25;++i) {
            const auto& fixture=fixtures[i];
            postprocess_exact_v11_api::Workspace base;postprocess_hash_v11_api::Workspace hash;
            postprocess_api::Records oracle;
            for(int phase=0;phase<3;++phase) {
                const int count=phase==0?1:phase==1?2:16;const int offset=phase==0?0:phase==1?1:3;
                const std::string phaseName=phase==0?"cold":phase==1?"warm":"formal";
                for(int round=0;round<count;++round) {
                    const int k=i+round+offset;std::array<int,2> order{{0,1}};
                    if(k%2)std::swap(order[0],order[1]);if((k/2)%2)std::swap(order[0],order[1]);
                    std::array<postprocess_api::CallResult,2> buffered;
                    for(int position=0;position<2;++position) {
                        const auto variant=order[position];
                        if(variant==0) {
                            ++baselineCalls;
                            buffered[variant]=fixture.baseline->match(fixture.image,fixture.threshold,base,127,postprocess_fixtures::ids(fixture));
                        } else {
                            ++candidateCalls;
                            buffered[variant]=fixture.candidate->match(fixture.image,fixture.threshold,hash,127,postprocess_fixtures::ids(fixture));
                        }
                    }
                    // Only after both actual calls: archive, compare, and free
                    // returned neutral results. No file IO touches API clocks.
                    std::array<postprocess_evidence::Saved,2> saved;
                    for(int position=0;position<2;++position) {
                        const auto variant=order[position];
                        saved[variant]=audit.save(std::move(buffered[variant]),fixture.name,phaseName,round,position,variants[variant]);
                    }
                    if(phase==0)oracle=saved[0].records;
                    require(saved[0].records==oracle&&saved[1].records==oracle&&saved[0].records==saved[1].records,
                            "Timed full ordered output differs at "+fixture.name+"/"+phaseName+"/"+std::to_string(round));
                }
            }
            std::cout<<"timing fixture="<<fixture.name<<" archived_calls="<<audit.calls<<std::endl;
        }
        require(baselineCalls==475&&candidateCalls==475&&audit.calls==950,"Fixed timing matcher budget differs");
        std::cout<<"PASS whole API timing baseline_calls="<<baselineCalls<<" candidate_calls="<<candidateCalls
                 <<" total_calls="<<audit.calls<<" formal_rows=800\n";return 0;
    } catch(const std::exception& error) {
        std::cerr<<"FAIL whole API timing: "<<error.what()<<'\n';return 1;
    }
}
