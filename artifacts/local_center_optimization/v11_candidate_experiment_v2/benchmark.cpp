#include "fixtures.hpp"
#include <chrono>
#include <iomanip>

namespace {
struct Measurement {Records output;local_center_v11::Timings timing;double wall_ms=0;};
struct BenchWorkspace {
    std::array<line2Dup::MatchWorkspace,2> direct;
    std::array<local_center_v18::Workspace,2> linear;
};
constexpr std::array<const char*,5> caseNames{{"exact_v11","linear16_off","linear16_on","direct16_off","direct16_on"}};
constexpr std::array<const char*,5> variants{{"exact_v11","linear16","linear16","direct16","direct16"}};
constexpr std::array<int,5> cacheOptions{{-1,0,1,0,1}};
std::array<int,5> order(int image,int phase,int round) {
    static const int offsets[]={0,1,3},parities[]={0,1,0};
    require(phase>=0&&phase<3,"Unknown benchmark phase");
    std::array<int,5> values{{0,1,2,3,4}};
    std::rotate(values.begin(),values.begin()+(image+offsets[phase]+round)%5,values.end());
    if((image+round/5+parities[phase])%2)std::reverse(values.begin(),values.end());
    return values;
}
void literal_order_checks() {
    for(int image=0;image<25;++image) {
        int counts[5][5]={};
        for(int round=0;round<15;++round) {
            const auto route=order(image,2,round);auto sorted=route;
            std::sort(sorted.begin(),sorted.end());
            require(sorted==std::array<int,5>{{0,1,2,3,4}},"Five unique timing cases required");
            for(int position=0;position<5;++position)++counts[route[position]][position];
        }
        for(int which=0;which<5;++which)for(int position=0;position<5;++position)
            require(counts[which][position]==3,"Measured case-position balance differs");
    }
}
Measurement measure(Fixture& fixture,int which,BenchWorkspace& workspace,std::array<unsigned,5>& calls) {
    require(which>=0&&which<5,"Unknown timing case");
    Measurement value;using Clock=std::chrono::steady_clock;
    ++calls[which]; // API call-site count outside all matcher code and clocks.
    if(which==0) {
        const auto start=Clock::now();
        const auto found=fixture.baseline->match(fixture.image,fixture.threshold,127,ids(fixture));
        const auto end=Clock::now();
        value.wall_ms=std::chrono::duration<double,std::milli>(end-start).count();
        value.timing=fixture.baseline->lastTimings();
        value.output=records(found);
    } else if(which==1||which==2) {
        local_center_v18::Timings timing;
        const auto start=Clock::now();
        const auto found=fixture.linear->match(fixture.image,fixture.threshold,workspace.linear[which-1],
                                               127,which==2,&timing,ids(fixture));
        const auto end=Clock::now();
        value.wall_ms=std::chrono::duration<double,std::milli>(end-start).count();
        value.timing=timing;value.output=records(found);
    } else {
        line2Dup::MatchTimings timing;
        const auto start=Clock::now();
        const auto found=fixture.candidate->match(fixture.image,fixture.threshold,workspace.direct[which-3],
                                                  options(127,which==4),&timing,ids(fixture));
        const auto end=Clock::now();
        value.wall_ms=std::chrono::duration<double,std::milli>(end-start).count();
        value.timing={timing.pyramid_ms,timing.gradient_ms,timing.spread_ms,timing.response_ms,
            timing.linearize_ms,timing.preprocess_ms,timing.search_ms,timing.total_ms};
        value.output=records(found);
    }
    return value;
}
}
int main(int argc,char** argv) {
    try {
        require(argc==3&&std::string(argv[1])=="--output","Explicit fresh --output required");
        std::ifstream prior(argv[2]);require(!prior.good(),"Refusing to overwrite benchmark evidence");
        std::ofstream output(argv[2]);require(bool(output),"Cannot create benchmark CSV");
        output<<"image,image_index,width,height,templates,threshold,phase,round,order_position,case,variant,cache,"
                 "pyramid_ms,gradient_ms,spread_ms,response_ms,linearize_ms,preprocess_ms,search_ms,total_ms,"
                 "adapter_wall_ms,result_count,full_ordered_equal\n"<<std::setprecision(17);
        literal_order_checks();literal_record_comparison_checks();
        cv::setNumThreads(1);omp_set_dynamic(0);omp_set_num_threads(4);
        auto all=fixtures();require(all.size()==27,"Correctness fixture count changed");
        std::array<unsigned,5> calls{{0,0,0,0,0}};unsigned rows=0;
        for(int image=0;image<25;++image) {
            auto& fixture=all[image];fixture.baseline->resetWorkspace();BenchWorkspace workspace;
            Records oracle;
            auto write=[&](const Measurement& m,const char* phase,int round,int position,int which) {
                const bool equal=m.output==oracle;const auto& t=m.timing;
                output<<fixture.name<<','<<image<<','<<fixture.image.cols<<','<<fixture.image.rows<<','
                    <<fixture.candidate->numTemplates()<<','<<fixture.threshold<<','<<phase<<','<<round<<','
                    <<position<<','<<caseNames[which]<<','<<variants[which]<<','<<cacheOptions[which]<<','
                    <<t.pyramid_ms<<','<<t.gradient_ms<<','<<t.spread_ms<<','<<t.response_ms<<','<<t.linearize_ms
                    <<','<<t.preprocess_ms<<','<<t.search_ms<<','<<t.total_ms<<','<<m.wall_ms<<','
                    <<m.output.size()<<','<<equal<<'\n';
                output.flush();++rows;
                require(equal,"Benchmark full ordered mismatch on "+fixture.name+"/"+phase+"/"+caseNames[which]);
                require(std::isfinite(t.search_ms)&&t.search_ms>=0&&std::isfinite(t.total_ms)&&
                    t.total_ms+1e-8>=t.preprocess_ms+t.search_ms&&std::isfinite(m.wall_ms)&&m.wall_ms>=0,
                    "Invalid benchmark phase timing");
            };
            // All five cold calls are buffered. Its actual V11 call supplies
            // the oracle after the round, regardless of V11's order position.
            std::array<Measurement,5> cold;const auto coldOrder=order(image,0,0);
            for(int which:coldOrder)cold[which]=measure(fixture,which,workspace,calls);
            oracle=cold[0].output;
            for(int position=0;position<5;++position) {
                const int which=coldOrder[position];write(cold[which],"cold",0,position,which);
            }
            for(int phase=1;phase<3;++phase)for(int round=0;round<(phase==1?2:15);++round) {
                const auto route=order(image,phase,round);
                for(int position=0;position<5;++position) {
                    const int which=route[position];
                    write(measure(fixture,which,workspace,calls),phase==1?"warm":"measured",round,position,which);
                }
            }
            std::cout<<"benchmark image "<<image+1<<"/25 "<<fixture.name<<" rows="<<rows<<std::endl;
        }
        for(unsigned value:calls)require(value==450,"Every timing case must make450 actual API calls");
        require(rows==2250,"Benchmark must retain all2250 calls");
        std::cout<<"MATCHER_CALLS exact_v11="<<calls[0]<<" linear16="<<calls[1]+calls[2]
                 <<" direct16="<<calls[3]+calls[4]<<" total="<<rows<<'\n';
        std::cout<<"PASS V2 five-case ordered benchmark calls="<<rows<<'\n';return 0;
    } catch(const std::exception& error) {
        std::cerr<<"FAIL V2 five-case benchmark: "<<error.what()<<'\n';return 1;
    }
}
