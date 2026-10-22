#include "../fixtures.hpp"
#include <atomic>
namespace {
struct PairWorkspace {line2Dup::MatchWorkspace direct;local_center_v18::Workspace linear;};
// Correctness harness counters live outside all matcher code/timers. The
// uninstrumented benchmark does not include this test translation unit.
std::atomic<unsigned> baselineCalls{0},linearCalls{0},directCalls{0};
class Audit {
    std::ofstream file_;
    static std::string fresh(const std::string& path) {
        std::ifstream prior(path);
        require(!prior.good(),"Refusing to overwrite existing correctness evidence");
        return path;
    }
public:
    unsigned calls=0;
    explicit Audit(const std::string& path):file_(fresh(path)) {
        require(bool(file_),"Cannot create new correctness CSV");
        file_<<"phase,variant,input,threads,flags,cache,expected_count,actual_count,full_ordered_equal,first_mismatch\n";
    }
    template<class Matches> void compare(const Matches& actual,const Records& expected,
            const std::string& phase,const Input& input,int threads,unsigned flags,int cache,
            const std::string& variant="direct16") {
        const auto got=records(actual);std::size_t first=0;
        while(first<std::min(got.size(),expected.size())&&got[first]==expected[first])++first;
        const bool equal=got==expected;
        file_<<phase<<','<<variant<<','<<input.name<<','<<threads<<','<<flags<<','<<cache<<','
             <<expected.size()<<','<<got.size()<<','<<equal<<',';
        if(!equal)file_<<first;
        file_<<'\n';file_.flush();++calls;
        if(!equal) {
            std::ostringstream error;error<<"Full ordered mismatch "<<phase<<'/'<<variant<<'/'<<input.name
                <<" flags="<<flags<<" threads="<<threads<<" cache="<<cache<<" index="<<first;
            auto describe=[&](const char* label,const Records& values) {
                error<<' '<<label<<'=';
                if(first==values.size())error<<"END";
                else {const auto& r=values[first];error<<std::get<0>(r)<<':'<<std::get<1>(r)<<':'
                    <<std::get<2>(r)<<':'<<std::get<3>(r)<<':'<<std::get<4>(r);}
            };
            describe("expected",expected);describe("actual",got);throw std::runtime_error(error.str());
        }
    }
};
Records expected(const std::vector<Fixture>& fixtures,const Input& input,unsigned flags,bool log=false) {
    const auto& f=fixtures[input.fixture];
    ++baselineCalls;
    return records(f.baseline->match(f.image,input.threshold,flags,ids(f),input.mask,log));
}
void check(const std::vector<Fixture>& fixtures,const Input& input,const Records& oracle,
        PairWorkspace& workspace,unsigned flags,bool cache,Audit& audit,
        const std::string& phase,int threads,bool log=false) {
    const auto& f=fixtures[input.fixture];line2Dup::MatchTimings timing;
    ++directCalls;
    const auto found=f.candidate->match(f.image,input.threshold,workspace.direct,options(flags,cache,log),
                                       &timing,ids(f),input.mask);
    audit.compare(found,oracle,phase,input,threads,flags,cache);
    require(std::isfinite(timing.search_ms)&&timing.search_ms>=0&&
        timing.total_ms+1e-8>=timing.preprocess_ms+timing.search_ms,"Invalid internal phase timing");
    local_center_v18::Timings linearTiming;
    ++linearCalls;
    const auto linear=f.linear->match(f.image,input.threshold,workspace.linear,flags,cache,
                                     &linearTiming,ids(f),input.mask,log);
    audit.compare(linear,oracle,phase,input,threads,flags,cache,"linear16");
    require(std::isfinite(linearTiming.search_ms)&&linearTiming.search_ms>=0&&
        linearTiming.total_ms+1e-8>=linearTiming.preprocess_ms+linearTiming.search_ms,"Invalid linear phase timing");
}
}
int main(int argc,char** argv) {
    try {
        static_assert(!std::is_copy_constructible<PairWorkspace>::value,"Owned scratch required");
        std::string output,stage="all";
        for(int i=1;i<argc;++i) {
            const std::string key=argv[i];require(i+1<argc,"Missing argument value");
            const std::string value=argv[++i];
            if(key=="--output")output=value;else if(key=="--stage")stage=value;
            else throw std::runtime_error("Unknown argument "+key);
        }
        require(!output.empty(),"Explicit fresh --output required");
        require(stage=="all"||stage=="core"||stage=="flags"||stage=="lifetime","Unknown stage");
        literal_record_comparison_checks();
        cv::setNumThreads(1);omp_set_dynamic(0);omp_set_num_threads(1);
        auto f=fixtures();std::vector<Input> inputs;
        for(std::size_t i=0;i<f.size();++i)inputs.push_back({i,{},f[i].threshold,f[i].name});
        const std::size_t zero=inputs.size();
        cv::Mat zeroMask(f[0].image.size(),CV_8UC1,cv::Scalar(0));
        cv::Mat fullMask(f[0].image.size(),CV_8UC1,cv::Scalar(255));
        cv::Mat partial=zeroMask.clone();partial(cv::Rect(100,100,400,300)).setTo(255);
        inputs.push_back({0,zeroMask,75,"LED_zero_mask"});
        const std::size_t full=inputs.size();inputs.push_back({0,fullMask,75,"LED_full_mask"});
        const std::size_t part=inputs.size();inputs.push_back({0,partial,75,"LED_partial_mask"});
        const std::size_t empty=inputs.size();inputs.push_back({0,{},101,"LED_empty_candidates"});
        cv::Mat larger;cv::copyMakeBorder(f[0].image,larger,0,32,0,64,cv::BORDER_CONSTANT,cv::Scalar(0));
        const auto resized=f.size();f.push_back({"LED_larger_same_detector","LED",larger,75,f[0].candidate,f[0].baseline,f[0].linear});
        const std::size_t size=inputs.size();inputs.push_back({resized,{},75,"LED_larger_same_detector"});
        Audit audit(output);PairWorkspace workspace;
        if(stage=="all"||stage=="core") {
            for(int threads:{1,4,2,4}) {
                omp_set_num_threads(threads);
                for(unsigned flags:{63U,127U})for(const auto& input:inputs) {
                    const auto oracle=expected(f,input,flags);
                    const auto& fixture=f[input.fixture];
                    ++baselineCalls;
                    audit.compare(fixture.baseline->match(fixture.image,input.threshold,flags,ids(fixture),input.mask),
                        oracle,"baseline_repeat",input,threads,flags,-1,"exact_v11");
                    for(int repeat=0;repeat<2;++repeat)for(bool cache:{false,true})
                        check(f,input,oracle,workspace,flags,cache,audit,"core",threads);
                }
                std::cout<<"core thread pass "<<threads<<" calls="<<audit.calls<<std::endl;
            }
        }
        if(stage=="all"||stage=="flags") {
            omp_set_num_threads(4);
            for(unsigned flags=0;flags<128;++flags)for(auto i:{std::size_t(0),zero,std::size_t(8),std::size_t(1),std::size_t(26),size}) {
                const auto oracle=expected(f,inputs[i],flags);
                for(bool cache:{false,true})check(f,inputs[i],oracle,workspace,flags,cache,audit,"flags",4);
            }
            for(auto i:{full,part,empty,std::size_t(0)})for(unsigned flags:{0U,55U,127U}) {
                const auto oracle=expected(f,inputs[i],flags);
                for(bool cache:{false,true})check(f,inputs[i],oracle,workspace,flags,cache,audit,"mask_restore",4);
            }
            const auto oracle=expected(f,inputs[0],127,true);
            for(bool cache:{false,true})check(f,inputs[0],oracle,workspace,127,cache,audit,"log_flag",4,true);
            std::cout<<"flags complete calls="<<audit.calls<<std::endl;
        }
        if(stage=="all"||stage=="lifetime") {
            omp_set_num_threads(4);std::vector<Records> oracle;
            for(const auto& input:inputs)oracle.push_back(expected(f,input,127));
            require(oracle[zero].empty()&&oracle[empty].empty(),"Negative baseline input produced output");
            require(oracle[0]==oracle[full],"Full mask differs from empty mask baseline");
            require(!oracle[26].empty(),"Synthetic zero-maxima baseline unexpectedly empty");
            for(const auto& record:oracle[26])require(std::get<3>(record)==0,
                "Synthetic zero-maxima fixture produced a nonzero score");
            check(f,inputs[0],oracle[0],workspace,127,true,audit,"pre_move",4);
            PairWorkspace moved(std::move(workspace));
            check(f,inputs[8],oracle[8],moved,127,true,audit,"move_constructed",4);
            check(f,inputs[1],oracle[1],workspace,127,true,audit,"moved_from_reused",4);
            PairWorkspace assigned;
            check(f,inputs[8],oracle[8],assigned,127,true,audit,"assignment_destination_populated",4);
            assigned=std::move(moved);
            check(f,inputs[0],oracle[0],assigned,127,true,audit,"move_assigned",4);
            check(f,inputs[size],oracle[size],moved,127,true,audit,"assignment_source_reused",4);
            require(!line2Dup::MatchOptions().reuse_local_centers,"Experiment default must remain explicit off");
            for(auto i:{std::size_t(0),std::size_t(8),std::size_t(1),std::size_t(0)}) {
                const auto& input=inputs[i];const auto& fixture=f[input.fixture];
                ++baselineCalls;
                const auto baseline=records(fixture.baseline->legacyMatch(fixture.image,input.threshold,ids(fixture),input.mask));
                ++directCalls;
                audit.compare(fixture.candidate->match(fixture.image,input.threshold,ids(fixture),input.mask),baseline,
                              "legacy_default",input,4,127,0);
                ++linearCalls;
                audit.compare(fixture.linear->legacyMatch(fixture.image,input.threshold,ids(fixture),input.mask),baseline,
                              "legacy_default",input,4,127,0,"linear16");
                ++directCalls;
                const auto actual=fixture.candidate->match(fixture.image,input.threshold,assigned.direct,
                    line2Dup::MatchOptions(),nullptr,ids(fixture),input.mask);
                audit.compare(actual,baseline,"explicit_default",input,4,127,0);
                ++linearCalls;
                audit.compare(fixture.linear->defaultMatch(fixture.image,input.threshold,assigned.linear,ids(fixture),input.mask),
                              baseline,"explicit_default",input,4,127,0,"linear16");
            }
            const std::array<std::size_t,6> route{{0,8,1,zero,size,0}};
            std::vector<Records> floatOracle;
            for(const auto& input:inputs)floatOracle.push_back(expected(f,input,55));
            auto worker=[&](bool reverse) {
                omp_set_num_threads(1);PairWorkspace own;
                std::vector<std::tuple<std::size_t,unsigned,std::vector<line2Dup::Match>,std::vector<local_center_v18::Result>>> result;
                for(std::size_t step=0;step<route.size();++step) {
                    const auto i=route[reverse?route.size()-1-step:step];const auto& input=inputs[i];const auto& fixture=f[input.fixture];
                    for(unsigned flags:{127U,55U}) {
                        ++directCalls;++linearCalls;
                        result.emplace_back(i,flags,fixture.candidate->match(
                        fixture.image,input.threshold,own.direct,options(flags,true),nullptr,ids(fixture),input.mask),
                        fixture.linear->match(fixture.image,input.threshold,own.linear,flags,true,nullptr,ids(fixture),input.mask));
                    }
                }
                return result;
            };
            auto a=std::async(std::launch::async,worker,false),b=std::async(std::launch::async,worker,true);
            for(auto result:{a.get(),b.get()})for(const auto& item:result) {
                const auto i=std::get<0>(item);const auto flags=std::get<1>(item);
                audit.compare(std::get<2>(item),flags==127?oracle[i]:floatOracle[i],"concurrent",inputs[i],1,flags,1);
                audit.compare(std::get<3>(item),flags==127?oracle[i]:floatOracle[i],"concurrent",inputs[i],1,flags,1,"linear16");
            }
            std::cout<<"lifetime complete calls="<<audit.calls<<std::endl;
        }
        std::cout<<"MATCHER_CALLS exact_v11="<<baselineCalls.load()<<" linear16="<<linearCalls.load()
                 <<" direct16="<<directCalls.load()<<" total="<<baselineCalls.load()+linearCalls.load()+directCalls.load()<<'\n';
        std::cout<<"PASS V2 direct16 and frozen linear16 ordered contract stage="<<stage<<" comparisons="<<audit.calls<<'\n';return 0;
    } catch(const std::exception& error) {
        std::cerr<<"FAIL V2 direct16/linear16 ordered contract: "<<error.what()<<'\n';return 1;
    }
}
