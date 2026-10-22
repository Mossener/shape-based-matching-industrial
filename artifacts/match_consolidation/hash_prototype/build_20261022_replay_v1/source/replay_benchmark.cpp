// Replay-only timing of already audited immutable complete input traces.
#include "hash_consolidation.hpp"
#include "trace_io.hpp"
#include <array>
#include <chrono>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <limits>
#include <sstream>
#include <stdexcept>

namespace {
using Clock=std::chrono::steady_clock;
using Matches=std::vector<hash_proto::Match>;
const std::array<const char*,5> names{{"v11_sort_unique","owning_hash_reserve",
    "owning_hash_no_reserve","index_hash_reserve","index_hash_no_reserve"}};
void require(bool okay,const char* message){if(!okay)throw std::runtime_error(message);}
std::uint32_t bits(float value){std::uint32_t out;std::memcpy(&out,&value,4);return out;}
bool equal(const Matches& a,const Matches& b){
    if(a.size()!=b.size())return false;
    for(std::size_t i=0;i<a.size();++i)if(a[i].x!=b[i].x || a[i].y!=b[i].y ||
        a[i].template_id!=b[i].template_id || a[i].class_id!=b[i].class_id ||
        bits(a[i].similarity)!=bits(b[i].similarity))return false;
    return true;
}
hash_proto::Diagnostics apply(unsigned method,Matches& input){
    if(method==0){
        hash_proto::Diagnostics info;info.input_count=input.size();
        line2Dup::detail::consolidateMatches(input);info.unique_count=input.size();return info;
    }
    hash_proto::Options options;options.reserve_input=method==1 || method==3;
    // Map/output creation, swap and destruction of the old full input belong
    // inside the measured interval. Every method receives the same mutable copy.
    auto result=method<=2?hash_proto::owning_hash(input,hash_proto::DefaultHash{},options):
                          hash_proto::index_hash(input,hash_proto::DefaultHash{},options);
    input.swap(result.matches);return result.diagnostics;
}
std::size_t batch_size(const Matches& input){
    std::size_t base=input.size()<64?10000:input.size()<4096?128:1;
    std::uint64_t estimated=0;
    for(const auto& match:input){
        const auto bytes=std::uint64_t(sizeof(hash_proto::Match))+64+match.class_id.size();
        require(estimated<=std::numeric_limits<std::uint64_t>::max()-bytes,"Batch estimate overflow");
        estimated+=bytes;
    }
    const auto cap=std::max<std::uint64_t>(1,67108864/std::max<std::uint64_t>(1,estimated));
    return std::min<std::size_t>(base,static_cast<std::size_t>(cap));
}
double milliseconds(Clock::time_point first,Clock::time_point last,std::size_t batch){
    return std::chrono::duration<double,std::milli>(last-first).count()/batch;
}
}
int main(int argc,char** argv){
    try{
        require(argc==4 || (argc==5 && std::string(argv[4])=="--verify-only"),
                "Usage: replay_benchmark TRACE_LIST NEW_CSV NEW_RECEIPT [--verify-only]");
        const bool verify_only=argc==5;
        std::ifstream list(argv[1]);require(bool(list),"Trace-list read failed");
        require(!std::ifstream(argv[2]).good() && !std::ifstream(argv[3]).good(),"Output evidence exists");
        std::ofstream csv(argv[2]);require(bool(csv),"New CSV create failed");
        csv<<"trace_index,case,scenario,phase,round,order,method,input_count,output_count,batch,copy_ms,consolidation_ms,bucket_count,zero_score_fallback\n";
        csv<<std::setprecision(17);
        std::string line;unsigned index=0;std::uint64_t timing_rows=0;
        while(std::getline(list,line)){
            require(!line.empty(),"Empty trace-list row");
            const auto first=line.find('\t'),second=first==std::string::npos?first:line.find('\t',first+1);
            require(first!=std::string::npos && second!=std::string::npos && line.find('\t',second+1)==std::string::npos,
                    "Trace-list requires case/scenario/path fields");
            const auto case_id=line.substr(0,first),scenario=line.substr(first+1,second-first-1),path=line.substr(second+1);
            require(!case_id.empty() && !scenario.empty() && case_id.find(',')==std::string::npos &&
                    scenario.find(',')==std::string::npos,"CSV-safe case/scenario required");
            std::ifstream file(path,std::ios::binary);require(bool(file),"Trace read failed");
            const auto trace=hash_proto::read_trace(file);
            auto oracle=trace.input;line2Dup::detail::consolidateMatches(oracle);
            require(equal(oracle,trace.output),"Exact V11 replay differs from captured ordered output");
            for(unsigned method=0;method<5;++method){auto result=trace.input;apply(method,result);
                require(equal(result,oracle),"Candidate replay differs from complete ordered oracle");}
            if(verify_only){
                std::cout<<"VERIFY COMPLETE "<<case_id<<" N="<<trace.input.size()<<" U="<<oracle.size()<<std::endl;
                ++index;continue;
            }
            const auto batch=batch_size(trace.input);
            for(unsigned phase=0;phase<2;++phase)for(unsigned round=0;round<(phase==0?3U:31U);++round){
                std::array<unsigned,5> order{{0,1,2,3,4}};
                std::rotate(order.begin(),order.begin()+(index+round)%5,order.end());
                if((index+round)%2)std::reverse(order.begin(),order.end());
                for(unsigned position=0;position<5;++position){
                    const unsigned method=order[position];
                    std::vector<Matches> inputs;inputs.reserve(batch);
                    const auto copy_start=Clock::now();
                    for(std::size_t i=0;i<batch;++i)inputs.push_back(trace.input);
                    const auto copy_end=Clock::now();
                    std::vector<hash_proto::Diagnostics> diagnostics(batch);
                    const auto start=Clock::now();
                    for(std::size_t i=0;i<batch;++i)diagnostics[i]=apply(method,inputs[i]);
                    const auto finish=Clock::now();
                    for(std::size_t i=0;i<batch;++i){
                        require(equal(inputs[i],oracle),"Timed replay output differs from ordered oracle");
                        require(diagnostics[i].input_count==trace.input.size() && diagnostics[i].unique_count==oracle.size(),
                                "Replay diagnostics differ");
                    }
                    const auto& info=diagnostics[0];
                    for(const auto& value:diagnostics)require(value.bucket_count==info.bucket_count &&
                        value.zero_score_fallback==info.zero_score_fallback,"Batch diagnostics changed");
                    csv<<index<<','<<case_id<<','<<scenario<<','<<(phase==0?"warmup":"measured")<<','<<round<<','
                       <<position<<','<<names[method]<<','<<trace.input.size()<<','<<oracle.size()<<','<<batch<<','
                       <<milliseconds(copy_start,copy_end,batch)<<','<<milliseconds(start,finish,batch)<<','
                       <<info.bucket_count<<','<<info.zero_score_fallback<<'\n';
                    require(bool(csv),"Timing CSV write failed");++timing_rows;
                }
            }
            csv.flush();std::cout<<"REPLAY COMPLETE "<<case_id<<" N="<<trace.input.size()<<" U="<<oracle.size()
                                  <<" batch="<<batch<<std::endl;++index;
        }
        require(index>0 && list.eof() && bool(csv),"Incomplete trace-list/CSV read");
        csv.close();require(!csv.fail(),"CSV close failed");
        std::ofstream receipt(argv[3]);require(bool(receipt),"New replay receipt create failed");
        receipt<<"{\"passed\":true,\"traces\":"<<index<<",\"timing_rows\":"<<timing_rows
               <<",\"sizeof_match\":"<<sizeof(hash_proto::Match)
               <<",\"matcher_calls\":0,\"image_decodes\":0,\"replay_only\":true,\"verify_only\":"
               <<(verify_only?"true":"false")<<"}\n";
        require(bool(receipt),"Replay receipt write failed");return 0;
    }catch(const std::exception& error){std::cerr<<"REPLAY FAILED: "<<error.what()<<'\n';return 1;}
}
