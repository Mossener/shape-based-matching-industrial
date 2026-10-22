// Fixed 2722-call actual-API matrix. Source only until separately authorized.
#include "fixtures.hpp"
#include "evidence.hpp"
#include <array>
#include <atomic>
#include <future>
#include <iostream>
#include <omp.h>

namespace {
using postprocess_fixtures::Fixture;
using postprocess_fixtures::Input;
using postprocess_fixtures::ids;
using postprocess_evidence::require;
using postprocess_evidence::Saved;
using postprocess_evidence::Metadata;
using postprocess_evidence::Correctness;
using BaseWorkspace=postprocess_exact_v11_api::Workspace;
using HashWorkspace=postprocess_hash_v11_api::Workspace;
std::atomic<unsigned> baselineCalls{0},candidateCalls{0};
const char* BASE="exact_v11";
const char* HASH="index_reserve_copy_actual_match";

void validTiming(const postprocess_api::CallResult& result) {
    require(result.has_internal_timing && std::isfinite(result.api_wall_ms) && result.api_wall_ms>=0 &&
            std::isfinite(result.internal.search_ms) && result.internal.search_ms>=0 &&
            std::isfinite(result.internal.total_ms) && result.internal.total_ms>=0 &&
            result.internal.total_ms+1e-8>=result.internal.preprocess_ms+result.internal.search_ms,
            "Invalid flagged-call timing");
}
Saved baseline(const std::vector<Fixture>& fixtures,const Input& input,unsigned flags,BaseWorkspace& workspace,
               Correctness& audit,Metadata meta,bool log=false) {
    const auto& fixture=fixtures[input.fixture];++baselineCalls;
    auto result=fixture.baseline->match(fixture.image,input.threshold,workspace,flags,ids(fixture),input.mask,log);
    validTiming(result);meta.variant=BASE;return audit.save(std::move(result),meta);
}
Saved candidate(const std::vector<Fixture>& fixtures,const Input& input,unsigned flags,HashWorkspace& workspace,
                Correctness& audit,Metadata meta,bool log=false) {
    const auto& fixture=fixtures[input.fixture];++candidateCalls;
    auto result=fixture.candidate->match(fixture.image,input.threshold,workspace,flags,ids(fixture),input.mask,log);
    validTiming(result);meta.variant=HASH;return audit.save(std::move(result),meta);
}
Metadata meta(const std::string& stage,const std::string& route,const Input& input,int threads,unsigned flags,
              int pass=0,int repeat=0,int worker=-1,int step=0) {
    Metadata value;value.stage=stage;value.route=route;value.input=input.name;value.threads=threads;
    value.flags=flags;value.pass=pass;value.repeat=repeat;value.worker=worker;value.step=step;return value;
}
void core(const std::vector<Fixture>& f,const std::vector<Input>& inputs,Correctness& audit,
          BaseWorkspace& base,HashWorkspace& hash) {
    const std::array<int,4> threads{{1,4,2,4}};
    for(int pass=0;pass<4;++pass) {
        omp_set_num_threads(threads[pass]);
        for(unsigned flags:{63U,127U})for(const auto& input:inputs) {
            const auto oracle=baseline(f,input,flags,base,audit,meta("core","oracle",input,threads[pass],flags,pass));
            const auto repeat=baseline(f,input,flags,base,audit,meta("core","baseline_repeat",input,threads[pass],flags,pass,1));
            audit.compare(repeat,oracle);
            for(int r=0;r<2;++r) {
                const auto actual=candidate(f,input,flags,hash,audit,meta("core","candidate",input,threads[pass],flags,pass,r));
                audit.compare(actual,oracle);
            }
        }
        std::cout<<"core pass="<<pass<<" omp="<<threads[pass]<<" archived_calls="<<audit.calls<<std::endl;
    }
}
void allFlags(const std::vector<Fixture>& f,const std::vector<Input>& inputs,Correctness& audit,
              BaseWorkspace& base,HashWorkspace& hash) {
    omp_set_num_threads(4);
    for(unsigned flags=0;flags<128;++flags)for(std::size_t index:{0U,27U,8U,1U,26U,31U}) {
        const auto& input=inputs[index];
        const auto oracle=baseline(f,input,flags,base,audit,meta("flags","all_flags",input,4,flags));
        const auto actual=candidate(f,input,flags,hash,audit,meta("flags","all_flags",input,4,flags));
        audit.compare(actual,oracle);
    }
    for(std::size_t index:{28U,29U,30U,0U})for(unsigned flags:{0U,55U,127U}) {
        const auto& input=inputs[index];
        const auto oracle=baseline(f,input,flags,base,audit,meta("flags","mask_restore",input,4,flags));
        const auto actual=candidate(f,input,flags,hash,audit,meta("flags","mask_restore",input,4,flags));
        audit.compare(actual,oracle);
    }
    const auto oracle=baseline(f,inputs[0],127,base,audit,meta("flags","log_flag",inputs[0],4,127),true);
    const auto actual=candidate(f,inputs[0],127,hash,audit,meta("flags","log_flag",inputs[0],4,127),true);
    audit.compare(actual,oracle);std::cout<<"flags complete archived_calls="<<audit.calls<<std::endl;
}
void lifetime(const std::vector<Fixture>& f,const std::vector<Input>& inputs,Correctness& audit,
              BaseWorkspace& base,HashWorkspace& hash) {
    omp_set_num_threads(4);std::vector<Saved> oracle127,oracle55;
    for(const auto& input:inputs)
        oracle127.push_back(baseline(f,input,127,base,audit,meta("lifetime","oracle",input,4,127)));
    require(oracle127[27].records.empty() && oracle127[30].records.empty(),"Negative baseline has matches");
    require(oracle127[0].records==oracle127[28].records,"Full-mask baseline differs");
    require(!oracle127[26].records.empty(),"Actual zero-maxima fixture is empty");
    for(const auto& record:oracle127[26].records)require(record.score_bits==0,"Actual zero-maxima score differs");
    auto check=[&](std::size_t index,HashWorkspace& workspace,const char* route) {
        const auto actual=candidate(f,inputs[index],127,workspace,audit,meta("lifetime",route,inputs[index],4,127));
        audit.compare(actual,oracle127[index]);
    };
    check(0,hash,"pre_move");HashWorkspace moved(std::move(hash));
    check(8,moved,"move_constructed");check(1,hash,"moved_from_reused");
    HashWorkspace assigned;check(8,assigned,"assignment_destination_populated");
    assigned=std::move(moved);check(0,assigned,"move_assigned");check(31,moved,"assignment_source_reused");
    const std::array<std::size_t,4> legacyRoute{{0,8,1,0}};
    for(int step=0;step<4;++step) {
        const auto& input=inputs[legacyRoute[step]];const auto& fixture=f[input.fixture];
        auto info=meta("lifetime","legacy_default",input,4,127,0,0,-1,step);info.variant=BASE;
        ++baselineCalls;auto old=fixture.baseline->legacyMatch(fixture.image,input.threshold,ids(fixture),input.mask);
        require(!old.has_internal_timing,"Legacy baseline fabricated internal timing");
        const auto oracle=audit.save(std::move(old),info);
        info.variant=HASH;++candidateCalls;
        auto result=fixture.candidate->legacyMatch(fixture.image,input.threshold,ids(fixture),input.mask);
        require(!result.has_internal_timing,"Legacy candidate fabricated internal timing");
        const auto legacy=audit.save(std::move(result),info);audit.compare(legacy,oracle);
        info.route="explicit_default";++candidateCalls;
        auto explicitResult=fixture.candidate->explicitDefaultMatch(fixture.image,input.threshold,assigned,ids(fixture),input.mask);
        require(!explicitResult.has_internal_timing,"Nullptr/default route fabricated internal timing");
        const auto defaults=audit.save(std::move(explicitResult),info);audit.compare(defaults,oracle);
    }
    for(const auto& input:inputs)
        oracle55.push_back(baseline(f,input,55,base,audit,meta("lifetime","oracle",input,4,55)));
    const std::array<std::size_t,6> route{{0,8,1,27,31,0}};
    struct Buffered {std::size_t index;unsigned flags;int step;postprocess_api::CallResult result;};
    auto worker=[&](bool reverse) {
        omp_set_num_threads(1);HashWorkspace own;std::vector<Buffered> results;
        for(int step=0;step<6;++step) {
            const auto index=route[reverse?5-step:step];const auto& input=inputs[index];const auto& fixture=f[input.fixture];
            for(unsigned flags:{127U,55U}) {
                ++candidateCalls;
                auto result=fixture.candidate->match(fixture.image,input.threshold,own,flags,ids(fixture),input.mask);
                validTiming(result);results.push_back({index,flags,step,std::move(result)});
            }
        }
        return results;
    };
    auto a=std::async(std::launch::async,worker,false),b=std::async(std::launch::async,worker,true);
    // Concurrent call IDs enumerate the deterministic archive order, not wall
    // execution order. Worker results are buffered; only this thread does IO.
    std::array<std::vector<Buffered>,2> buffered{{a.get(),b.get()}};
    for(int worker=0;worker<2;++worker)for(auto& item:buffered[worker]) {
        auto info=meta("lifetime","concurrent",inputs[item.index],1,item.flags,0,0,worker,item.step);info.variant=HASH;
        const auto actual=audit.save(std::move(item.result),info);
        audit.compare(actual,item.flags==127?oracle127[item.index]:oracle55[item.index]);
    }
    std::cout<<"lifetime complete archived_calls="<<audit.calls<<std::endl;
}
void classFilters(const std::vector<Fixture>& f,Correctness& audit) {
    omp_set_num_threads(4);BaseWorkspace base;HashWorkspace hash;
    const auto& fixture=f[25];
    const std::vector<std::vector<std::string>> filters={{},{"LED_A"},{"LED_B"},{"LED_B","LED_A"},
        {"LED_A","LED_B"},{"missing"},{"missing","LED_A"},{"LED_A","LED_A"}};
    for(int step=0;step<8;++step) {
        Input input{25,{},75,"LED_two_classes"};auto info=meta("class_filter","filter",input,4,127,0,0,-1,step);
        info.variant=BASE;++baselineCalls;
        auto b=fixture.baseline->match(fixture.image,75,base,127,filters[step]);validTiming(b);
        const auto oracle=audit.save(std::move(b),info);
        info.variant=HASH;++candidateCalls;
        auto c=fixture.candidate->match(fixture.image,75,hash,127,filters[step]);validTiming(c);
        const auto actual=audit.save(std::move(c),info);audit.compare(actual,oracle);
    }
}
void magnets(const std::string& root,const std::string& output,Correctness& audit) {
    std::vector<postprocess_fixture_banks::Refinement> preflight;
    const auto f=postprocess_fixtures::magnetFixtures(root,&preflight);
    require(preflight.size()==6120,"Complete magnet refinement preflight required");
    postprocess_evidence::FreshFile file(output+"/magnet_preflight.csv");
    file.text("template_id,level,width,height,border,required_width,required_height,max_x,max_y\n");
    for(const auto& p:preflight) {
        auto row=postprocess_evidence::stream();row<<p.template_id<<','<<p.level<<','<<p.width<<','<<p.height<<','
            <<p.border<<','<<p.required_width<<','<<p.required_height<<','<<p.max_x<<','<<p.max_y<<'\n';file.text(row.str());
    }
    omp_set_num_threads(4);BaseWorkspace base;HashWorkspace hash;
    for(std::size_t i=0;i<f.size();++i) {
        Input input{i,{},75,f[i].name};
        const auto oracle=baseline(f,input,127,base,audit,meta("magnet_local","regression",input,4,127));
        const auto actual=candidate(f,input,127,hash,audit,meta("magnet_local","regression",input,4,127));
        audit.compare(actual,oracle);
    }
}
}
int main(int argc,char** argv) {
    try {
        std::string root,output;
        for(int i=1;i<argc;++i) {
            const std::string key=argv[i];require(i+1<argc,"Missing argument value");const std::string value=argv[++i];
            if(key=="--root")root=value;else if(key=="--output-directory")output=value;
            else throw std::runtime_error("Unknown argument "+key);
        }
        require(!root.empty()&&!output.empty(),"Explicit root and fresh output directory required");
        postprocess_evidence::literalRecordComparisonChecks();
        cv::setNumThreads(1);omp_set_dynamic(0);omp_set_max_active_levels(1);omp_set_num_threads(1);
        auto f=postprocess_fixtures::fixtures(root);const auto inputs=postprocess_fixtures::inputs(f);
        Correctness audit(output);BaseWorkspace base;HashWorkspace hash;
        core(f,inputs,audit,base,hash);allFlags(f,inputs,audit,base,hash);lifetime(f,inputs,audit,base,hash);
        classFilters(f,audit);magnets(root,output,audit);
        require(baselineCalls==1376 && candidateCalls==1346 && audit.calls==2722 && audit.comparisons==1602,
                "Fixed complete matcher/comparison budget differs");
        std::cout<<"PASS whole API ordered contract baseline_calls="<<baselineCalls<<" candidate_calls="<<candidateCalls
                 <<" total_calls="<<audit.calls<<" comparisons="<<audit.comparisons<<'\n';return 0;
    } catch(const std::exception& error) {
        std::cerr<<"FAIL whole API ordered contract: "<<error.what()<<'\n';return 1;
    }
}
