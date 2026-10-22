#include "trace_io.hpp"
#include "line2Dup_matches.hpp"
#include <cstdint>
#include <cstring>
#include <iostream>
#include <limits>
#include <sstream>
#include <stdexcept>

namespace hp=hash_proto;
static std::size_t checks=0,rejected=0;
static void require(bool value,const char* message){++checks;if(!value)throw std::runtime_error(message);}
static std::uint32_t bits(float f){std::uint32_t v;std::memcpy(&v,&f,sizeof(v));return v;}
static float score(std::uint32_t b){float v;std::memcpy(&v,&b,sizeof(v));return v;}
static void same(const std::vector<hp::Match>& a,const std::vector<hp::Match>& b){
    require(a.size()==b.size(),"trace complete record count mismatch");for(std::size_t i=0;i<a.size();++i)require(a[i].x==b[i].x && a[i].y==b[i].y && a[i].template_id==b[i].template_id && bits(a[i].similarity)==bits(b[i].similarity) && a[i].class_id==b[i].class_id,"trace complete field/scorebits/order mismatch");
}
static std::string encode(const hp::Trace& trace){std::ostringstream out(std::ios::binary);hp::write_trace(out,trace);return out.str();}
static hp::Trace decode(const std::string& data,hp::TraceLimits limits={}){std::istringstream in(data,std::ios::binary);return hp::read_trace(in,limits);}
static void rejects(const std::string& data,hp::TraceLimits limits={}){bool threw=false;try{(void)decode(data,limits);}catch(const std::runtime_error&){threw=true;}require(threw,"malformed/unbounded trace accepted");++rejected;}
// Fixture builder is independent of the implementation's serializer.
static void u32(std::string& s,std::uint32_t n){for(int i=0;i<4;++i)s.push_back(char((n>>(8*i))&255));}
static void u64(std::string& s,std::uint64_t n){for(int i=0;i<8;++i)s.push_back(char((n>>(8*i))&255));}
static std::string header(std::uint64_t inputs,std::uint64_t outputs){std::string s="SBMHASH1";u32(s,1);u32(s,0x01020304);u64(s,inputs);u64(s,outputs);return s;}
static void record(std::string& s,std::uint32_t x,std::uint32_t y,std::uint32_t id,std::uint32_t f,const std::string& name){u32(s,x);u32(s,y);u32(s,id);u32(s,f);u64(s,name.size());s+=name;}
int main(){try{
    hp::Trace example;example.input={{7,-9,score(0x42aa0001),std::string("a\0z",3),-4},{7,-9,score(0x42aa0001),std::string("a\0z",3),-7}};example.output=example.input;line2Dup::detail::consolidateMatches(example.output);
    // First RED must fail semantically on the no-op writer/empty reader.
    auto decoded=decode(encode(example));same(decoded.input,example.input);same(decoded.output,example.output);
    std::string literal=header(1,1);record(literal,7,0xfffffff7,0xfffffffc,0x42aa0001,std::string("a\0z",3));record(literal,7,0xfffffff7,0xfffffffc,0x42aa0001,std::string("a\0z",3));
    auto hand=decode(literal);same(hand.input,{example.input[0]});same(hand.output,{example.input[0]});require(encode(hand)==literal,"trace differs from explicit little-endian format");
    hp::Trace empty;require(encode(empty)==header(0,0),"empty trace header mismatch");auto no=decode(encode(empty));same(no.input,{});same(no.output,{});
    hp::Trace extremes;extremes.input={{std::numeric_limits<int>::min(),std::numeric_limits<int>::max(),-0.0f,std::string(4096,'q'),std::numeric_limits<int>::min()},{0,0,0.0f,"",0},{0,0,std::numeric_limits<float>::max(),std::string("\xc3\xa9",2),9},{0,0,std::numeric_limits<float>::denorm_min(),"sub",2}};extremes.output=extremes.input;
    auto e=decode(encode(extremes));same(e.input,extremes.input);same(e.output,extremes.output);
    for(std::size_t cut=0;cut<literal.size();++cut)rejects(literal.substr(0,cut));
    rejects(literal+"x");
    auto bad=literal;bad[0]='?';rejects(bad);bad=literal;bad[8]=2;rejects(bad);bad=literal;bad[12]=0;rejects(bad);
    rejects(header(std::numeric_limits<std::uint64_t>::max(),1));rejects(header(10000001,0));
    hp::TraceLimits unbounded;unbounded.max_records=std::numeric_limits<std::uint64_t>::max();unbounded.max_class_bytes=std::numeric_limits<std::uint64_t>::max();unbounded.max_total_bytes=std::numeric_limits<std::uint64_t>::max();rejects(header(std::numeric_limits<std::uint64_t>::max(),1),unbounded);
    bad=header(1,0);u32(bad,0);u32(bad,0);u32(bad,0);u32(bad,0x42aa0000);u64(bad,std::numeric_limits<std::uint64_t>::max());rejects(bad);rejects(bad,unbounded);
    hp::TraceLimits tiny;tiny.max_records=1;rejects(encode(example),tiny);tiny={};tiny.max_class_bytes=2;rejects(literal,tiny);tiny={};tiny.max_total_bytes=literal.size()-1;rejects(literal,tiny);
    for(std::uint32_t f:{std::uint32_t(0x7f800000),std::uint32_t(0xff800000),std::uint32_t(0x7fc00001),std::uint32_t(0x7f800001)}){
        for(bool input_side:{false,true}){
            bad=header(input_side?1:0,input_side?0:1);record(bad,0,0,0,f,"bad");rejects(bad);
            hp::Trace invalid;(input_side?invalid.input:invalid.output).push_back({0,0,score(f),"bad",0});std::ostringstream out(std::ios::binary);bool threw=false;try{hp::write_trace(out,invalid);}catch(const std::runtime_error&){threw=true;}require(threw && out.str().empty(),"invalid-score writer must reject before partial output");
        }
    }
    auto replay=decoded.input;line2Dup::detail::consolidateMatches(replay);same(replay,decoded.output);
    std::cout<<"{\"status\":\"PASS\",\"checks\":"<<checks<<",\"malformed_cases_rejected\":"<<rejected<<",\"dataset_access\":false,\"matcher_calls\":0}\n";return 0;
}catch(const std::exception& e){std::cerr<<"FAIL after "<<checks<<" checks: "<<e.what()<<'\n';return 1;}}
