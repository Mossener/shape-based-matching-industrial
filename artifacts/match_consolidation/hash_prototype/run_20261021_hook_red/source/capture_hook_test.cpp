#include "capture_hook.hpp"
#include <climits>
#include <cstdint>
#include <cstring>
#include <iostream>
#include <sstream>
#include <stdexcept>
void bridge_consolidate(std::vector<hash_proto::Match>&);
namespace {
using hash_proto::Match;
unsigned checks=0;
void require(bool ok,const char* what){++checks;if(!ok)throw std::runtime_error(what);}
std::uint32_t bits(float value){std::uint32_t result;std::memcpy(&result,&value,4);return result;}
float value(std::uint32_t b){float result;std::memcpy(&result,&b,4);return result;}
bool same(const std::vector<Match>& a,const std::vector<Match>& b){
    if(a.size()!=b.size())return false;
    for(std::size_t i=0;i<a.size();++i){
        if(a[i].x!=b[i].x || a[i].y!=b[i].y || a[i].template_id!=b[i].template_id ||
            a[i].class_id!=b[i].class_id || bits(a[i].similarity)!=bits(b[i].similarity))return false;
    }return true;
}
template<class F>void rejects(F action,const char* what){
    bool caught=false;try{action();}catch(const std::logic_error&){caught=true;}
    require(caught,what);
}
}
int main(){
    try {
        const std::vector<Match> original={{7,-8,90.f,"part",19},{7,-8,90.f,"part",3},
            {INT_MAX,INT_MIN,95.f,std::string("N\0U",3),7}};
        const std::vector<Match> expected={original[2],original[1]};
        auto matches=original;
        capture_trace::arm();bridge_consolidate(matches);auto captured=capture_trace::take();
        require(same(captured.input,original),"complete ordered pre-input capture missing");
        require(same(captured.output,expected),"literal complete ordered captured output differs");
        require(same(matches,expected),"capture changed V11 caller output");
        rejects([]{(void)capture_trace::take();},"capture take must be one-shot");
        for(const auto& input:std::vector<std::vector<Match>>{
            {},{{0,0,1.f,"",0}},
            {{-1,2,value(0x80000000u),std::string(4096,'x'),7},
             {-1,2,0.f,std::string(4096,'x'),7},
             {INT_MIN,INT_MAX,value(1u),std::string("\xff\0z",3),-1}}}) {
            auto baseline=input;line2Dup::detail::consolidateMatches(baseline);
            matches=input;bridge_consolidate(matches);
            require(same(matches,baseline),"unarmed wrapper did not pass through exact V11");
            rejects([]{(void)capture_trace::take();},"unarmed pass-through created capture");
            capture_trace::arm();matches=input;bridge_consolidate(matches);
            captured=capture_trace::take();
            require(same(captured.input,input),"captured fields/bits/input order differ");
            require(same(captured.output,baseline)&&same(matches,baseline),"armed V11 bits differ");
            std::ostringstream out(std::ios::binary);hash_proto::write_trace(out,captured);
            std::istringstream in(out.str(),std::ios::binary);auto decoded=hash_proto::read_trace(in);
            require(same(decoded.input,input)&&same(decoded.output,baseline),"taken capture lost serialization bits");
        }
        capture_trace::arm();rejects([]{capture_trace::arm();},"double arm accepted");
        matches=original;bridge_consolidate(matches);const auto first=matches;
        rejects([&]{bridge_consolidate(matches);},"second consolidation overwrote first capture");
        require(same(matches,first),"second consolidation modified caller before rejection");
        captured=capture_trace::take();require(same(captured.input,original),"double-use corrupted captured input");
        capture_trace::arm();capture_trace::cancel();
        rejects([]{(void)capture_trace::take();},"cancel without call retained capture");
        capture_trace::arm();matches=original;bridge_consolidate(matches);capture_trace::cancel();
        rejects([]{(void)capture_trace::take();},"cancel after call retained capture");
        for(auto b:{0x7fc00001u,0x7f800000u,0xff800000u}) {
            matches=original;matches.push_back({0,0,value(b),"invalid",0});const auto preserved=matches;
            capture_trace::arm();bool caught=false;
            try{bridge_consolidate(matches);}catch(const std::invalid_argument&){caught=true;}
            require(caught,"armed capture accepted nonfinite score");
            require(same(matches,preserved),"invalid capture modified caller input");
            rejects([]{(void)capture_trace::take();},"failed capture became ready");
            capture_trace::cancel();
        }
        for(int i=0;i<10;++i){
            capture_trace::arm();matches=original;bridge_consolidate(matches);captured=capture_trace::take();
            require(same(captured.input,original)&&same(captured.output,expected),"rearmed state lost identity");
        }
        std::cout<<"{\"status\":\"PASS\",\"checks\":"<<checks
                 <<",\"translation_units\":2,\"image_decodes\":0,\"matcher_calls\":0,\"performance_measurement\":false}\n";
        return 0;
    }catch(const std::exception& e){std::cerr<<"FAIL after "<<checks<<" checks: "<<e.what()<<'\n';return 1;}
}
