#include "benchmark_fixtures.hpp"
#include <chrono>
#include <iomanip>

namespace {
struct Measurement {
    Records output;
    local_center_v11::Timings timing;
    double wall_ms;
};
Measurement measure(Fixture& fixture,int which,line2Dup::MatchWorkspace& off,
                    line2Dup::MatchWorkspace& on) {
    Measurement value;
    using Clock=std::chrono::steady_clock;
    if(which==0) {
        const auto start=Clock::now();
        const auto found=fixture.baseline->match(fixture.image,fixture.threshold,127,ids(fixture));
        const auto end=Clock::now();
        value.wall_ms=std::chrono::duration<double,std::milli>(end-start).count();
        value.timing=fixture.baseline->lastTimings();
        value.output=records(found);
    } else {
        line2Dup::MatchTimings timing;
        const auto start=Clock::now();
        const auto found=fixture.candidate->match(fixture.image,fixture.threshold,
            which==1?off:on,options(127,which==2),&timing,ids(fixture));
        const auto end=Clock::now();
        value.wall_ms=std::chrono::duration<double,std::milli>(end-start).count();
        value.timing={timing.pyramid_ms,timing.gradient_ms,timing.spread_ms,timing.response_ms,
            timing.linearize_ms,timing.preprocess_ms,timing.search_ms,timing.total_ms};
        value.output=records(found);
    }
    return value;
}
std::array<int,3> order(int image,int round) {
    std::array<int,3> values{{0,1,2}};
    std::rotate(values.begin(),values.begin()+(image+round)%3,values.end());
    if((image+round)%2)std::reverse(values.begin(),values.end());
    return values;
}
}
int main(int argc,char** argv) {
    try {
        require(argc==3&&std::string(argv[1])=="--output","Explicit fresh --output required");
        std::ifstream prior(argv[2]);require(!prior.good(),"Refusing to overwrite benchmark evidence");
        std::ofstream output(argv[2]);require(bool(output),"Cannot create benchmark CSV");
        output<<"image,image_index,width,height,templates,threshold,phase,round,order_position,case,"
                 "pyramid_ms,gradient_ms,spread_ms,response_ms,linearize_ms,preprocess_ms,search_ms,"
                 "total_ms,adapter_wall_ms,result_count,full_ordered_equal\n"<<std::setprecision(17);
        literal_record_comparison_checks();
        cv::setNumThreads(1);omp_set_dynamic(0);omp_set_num_threads(4);
        auto all=fixtures();require(all.size()==27,"Correctness fixture count changed");
        static const char* names[]={"exact_v11","candidate_off","candidate_on"};
        unsigned calls=0;
        for(int i=0;i<25;++i) {
            auto& fixture=all[i];fixture.baseline->resetWorkspace();
            line2Dup::MatchWorkspace off,on;
            Records oracle;
            auto write=[&](const Measurement& m,const char* phase,int round,int position,int which) {
                const bool equal=m.output==oracle;const auto& t=m.timing;
                output<<fixture.name<<','<<i<<','<<fixture.image.cols<<','<<fixture.image.rows<<','
                    <<fixture.candidate->numTemplates()<<','<<fixture.threshold<<','<<phase<<','<<round
                    <<','<<position<<','<<names[which]<<','<<t.pyramid_ms<<','<<t.gradient_ms<<','
                    <<t.spread_ms<<','<<t.response_ms<<','<<t.linearize_ms<<','<<t.preprocess_ms<<','
                    <<t.search_ms<<','<<t.total_ms<<','<<m.wall_ms<<','<<m.output.size()<<','<<equal<<'\n';
                output.flush();++calls;
                require(equal,"Benchmark full ordered mismatch on "+fixture.name+"/"+phase+"/"+names[which]);
                require(std::isfinite(t.search_ms)&&t.search_ms>=0&&std::isfinite(t.total_ms)&&
                    t.total_ms+1e-8>=t.preprocess_ms+t.search_ms&&std::isfinite(m.wall_ms)&&m.wall_ms>=0,
                    "Invalid benchmark phase timing");
            };
            std::array<Measurement,3> cold;
            const auto coldOrder=order(i,0);
            for(int which:coldOrder)cold[which]=measure(fixture,which,off,on);
            oracle=cold[0].output;
            for(int position=0;position<3;++position) {
                const auto which=coldOrder[position];write(cold[which],"cold",0,position,which);
            }
            for(int round=0;round<2;++round) {
                const auto route=order(i,round+1);
                for(int position=0;position<3;++position) {
                    const auto which=route[position];
                    write(measure(fixture,which,off,on),"warm",round,position,which);
                }
            }
            for(int round=0;round<15;++round) {
                const auto route=order(i,round+3);
                for(int position=0;position<3;++position) {
                    const auto which=route[position];
                    write(measure(fixture,which,off,on),"measured",round,position,which);
                }
            }
            std::cout<<"benchmark image "<<i+1<<"/25 "<<fixture.name<<" calls="<<calls<<std::endl;
        }
        require(calls==1350,"Benchmark call count changed");
        std::cout<<"PASS exact ordered benchmark calls="<<calls<<'\n';return 0;
    } catch(const std::exception& error) {
        std::cerr<<"FAIL V11 center benchmark: "<<error.what()<<'\n';return 1;
    }
}
