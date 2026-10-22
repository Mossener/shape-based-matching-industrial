#include "hash_consolidation.hpp"
#include "line2Dup_matches.hpp"
#include <algorithm>
#include <cmath>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <iostream>
#include <limits>
#include <map>
#include <new>
#include <random>
#include <stdexcept>
#include <tuple>

// Test-only allocation failure injection; none of this enters prototype code.
static long fail_after=-1;
static std::size_t allocations_seen=0;
#if defined(__GNUC__)
#define TEST_ALLOCATION_NOINLINE __attribute__((noinline))
#else
#define TEST_ALLOCATION_NOINLINE
#endif
TEST_ALLOCATION_NOINLINE void* operator new(std::size_t n) {
    if(fail_after>=0 && allocations_seen++==static_cast<std::size_t>(fail_after))throw std::bad_alloc();
    if(void* p=std::malloc(n?n:1))return p;
    throw std::bad_alloc();
}
TEST_ALLOCATION_NOINLINE void* operator new[](std::size_t n){return ::operator new(n);}
TEST_ALLOCATION_NOINLINE void operator delete(void* p) noexcept{std::free(p);}
TEST_ALLOCATION_NOINLINE void operator delete[](void* p) noexcept{std::free(p);}
TEST_ALLOCATION_NOINLINE void operator delete(void* p,std::size_t) noexcept{std::free(p);}
TEST_ALLOCATION_NOINLINE void operator delete[](void* p,std::size_t) noexcept{std::free(p);}

namespace hp=hash_proto;
static std::size_t checks=0,oracle_cases=0,zero_cases=0,collision_cases=0,allocation_failures=0;
static void require(bool value,const char* message){++checks;if(!value)throw std::runtime_error(message);}
static std::uint32_t bits(float f){std::uint32_t b;std::memcpy(&b,&f,sizeof(b));return b;}
static float fromBits(std::uint32_t b){float f;std::memcpy(&f,&b,sizeof(f));return f;}
static bool exact(const hp::Match& a,const hp::Match& b){return a.x==b.x && a.y==b.y && a.template_id==b.template_id && a.class_id==b.class_id && bits(a.similarity)==bits(b.similarity);}
static void same(const std::vector<hp::Match>& a,const std::vector<hp::Match>& b,const char* message){require(a.size()==b.size(),message);for(std::size_t i=0;i<a.size();++i)require(exact(a[i],b[i]),message);}
static std::vector<hp::Match> committed(const std::vector<hp::Match>& input){auto out=input;line2Dup::detail::consolidateMatches(out);return out;}

// Independently group by ordered numeric key, then sort an independently
// expressed tuple. Never use a candidate comparator/hash/equality helper.
static std::vector<hp::Match> mapOracle(const std::vector<hp::Match>& input){
    using Key=std::tuple<std::string,int,int,float>;
    std::map<Key,std::size_t> groups;
    for(std::size_t i=0;i<input.size();++i){
        const auto& v=input[i];if(!std::isfinite(v.similarity))throw std::invalid_argument("oracle nonfinite");
        auto item=groups.emplace(Key(v.class_id,v.x,v.y,v.similarity),i);
        if(!item.second && v.template_id<input[item.first->second].template_id)item.first->second=i;
    }
    std::vector<hp::Match> out;for(const auto& item:groups)out.push_back(input[item.second]);
    std::sort(out.begin(),out.end(),[](const hp::Match& a,const hp::Match& b){
        return std::make_tuple(-a.similarity,a.template_id,a.class_id,a.y,a.x)<std::make_tuple(-b.similarity,b.template_id,b.class_id,b.y,b.x);
    });return out;
}
struct ConstantHash { std::size_t operator()(const std::string&,int,int,float) const{return 7;} };
struct ThrowHash {
    std::size_t* calls;
    std::size_t throw_at;
    std::size_t operator()(const std::string&,int,int,float) const{
        if((*calls)++==throw_at)throw std::runtime_error("injected hash failure");
        return 3;
    }
};
static void normalCase(const std::vector<hp::Match>& input,bool collision=false){
    const auto original=input,expected=mapOracle(input),v11=committed(input);same(expected,v11,"map oracle / V11 mismatch");
    for(bool reserve:{false,true}){
        hp::Options opts;opts.reserve_input=reserve;
        const auto own=hp::owning_hash(input,hp::DefaultHash{},opts),idx=hp::index_hash(input,hp::DefaultHash{},opts),sort=hp::v11_sort_unique(input);
        same(own.matches,expected,"owning exact ordered output mismatch");same(idx.matches,expected,"index exact ordered output mismatch");same(sort.matches,v11,"V11 wrapper mismatch");
        same(input,original,"input mutated on success");
        for(const auto* result:{&own,&idx}){
            require(result->diagnostics.input_count==input.size() && result->diagnostics.unique_count==expected.size(),"N/U diagnostics mismatch");
            require(!result->diagnostics.zero_score_fallback,"nonzero vector used zero fallback");
        }
        same(hp::owning_hash(own.matches).matches,own.matches,"owning not idempotent");same(hp::index_hash(idx.matches).matches,idx.matches,"index not idempotent");
        if(collision){same(hp::owning_hash(input,ConstantHash{},opts).matches,expected,"owning forced collision mismatch");same(hp::index_hash(input,ConstantHash{},opts).matches,expected,"index forced collision mismatch");++collision_cases;}
    }++oracle_cases;
}
static void zeroCase(const std::vector<hp::Match>& input,bool unique_minimum=true){
    const auto before=input,expected=committed(input);
    if(unique_minimum)same(mapOracle(input),expected,"unique-minimum zero map oracle mismatch");
    same(hp::v11_sort_unique(input).matches,expected,"zero V11 wrapper mismatch");
    const auto own=hp::owning_hash(input),idx=hp::index_hash(input);
    same(own.matches,expected,"owning zero fallback must match exact V11 representative bits");same(idx.matches,expected,"index zero fallback must match exact V11 representative bits");
    require(own.diagnostics.zero_score_fallback && idx.diagnostics.zero_score_fallback,"zero fallback not recorded");require(own.diagnostics.bucket_count==0 && idx.diagnostics.bucket_count==0,"zero fallback built a map");
    require(own.diagnostics.unique_count==expected.size() && idx.diagnostics.unique_count==expected.size(),"zero fallback U wrong");
    std::size_t calls=0;same(hp::owning_hash(input,ThrowHash{&calls,0}).matches,expected,"owning zero fallback invoked hash");same(hp::index_hash(input,ThrowHash{&calls,0}).matches,expected,"index zero fallback invoked hash");require(calls==0,"zero fallback must precede hash operations");
    same(input,before,"zero input mutated");++zero_cases;
}
static void finiteAndExceptionCases(){
    for(float score:{std::numeric_limits<float>::infinity(),-std::numeric_limits<float>::infinity(),std::numeric_limits<float>::quiet_NaN(),fromBits(0x7f800001)})for(float first:{86.0f,-0.0f}){
        std::vector<hp::Match> input={{2,3,first,"a",8},{2,3,85,"b",7},{2,3,score,"bad",6}},before=input;
        for(int which=0;which<3;++which){bool threw=false;std::size_t calls=0;try{
            if(which==0)(void)hp::owning_hash(input,ThrowHash{&calls,0});
            else if(which==1)(void)hp::index_hash(input,ThrowHash{&calls,0});else(void)hp::v11_sort_unique(input);
        }catch(const std::invalid_argument&){threw=true;}
        require(threw,"nonfinite input not rejected by finite pre-scan");require(calls==0,"hash called before finite validation completed");same(input,before,"nonfinite rejection mutated input");}
    }
    std::vector<hp::Match> input;for(int i=0;i<24;++i)input.push_back({i%7,i%4,85.5f,std::string(256,'a'+i%5),30-i});const auto before=input;
    for(float load:{0.25f,2.0f})for(bool reserve:{false,true}){
        hp::Options opts;opts.max_load_factor=load;opts.reserve_input=reserve;
        same(hp::owning_hash(input,hp::DefaultHash{},opts).matches,mapOracle(input),"valid owning load factor changed output");same(hp::index_hash(input,hp::DefaultHash{},opts).matches,mapOracle(input),"valid index load factor changed output");same(input,before,"valid options mutated input");
    }
    for(float load:{0.0f,-1.0f,std::numeric_limits<float>::infinity(),std::numeric_limits<float>::quiet_NaN()})for(int which=0;which<2;++which){
        hp::Options opts;opts.max_load_factor=load;bool threw=false;try{if(which==0)(void)hp::owning_hash(input,hp::DefaultHash{},opts);else(void)hp::index_hash(input,hp::DefaultHash{},opts);}catch(const std::invalid_argument&){threw=true;}
        require(threw,"invalid map load factor accepted");same(input,before,"invalid options mutated input");
    }
    for(int which=0;which<2;++which)for(std::size_t at:{std::size_t(0),std::size_t(3),std::size_t(11)}){
        bool threw=false;std::size_t calls=0;try{if(which==0)(void)hp::owning_hash(input,ThrowHash{&calls,at});else(void)hp::index_hash(input,ThrowHash{&calls,at});}catch(const std::runtime_error&){threw=true;}
        require(threw,"injected hash failure not reached");require(calls==at+1,"throwing hash did not fail at declared call");same(input,before,"hash exception mutated input");
    }
    // Throw on every actual allocation ordinal, covering buckets, nodes,
    // owning-key strings and complete output copies, until the call succeeds.
    for(int which=0;which<3;++which)for(bool reserve:{false,true}){if(which==2 && !reserve)continue;bool completed=false;hp::Options opts;opts.reserve_input=reserve;for(long n=0;n<400;++n){
        allocations_seen=0;fail_after=n;bool threw=false;try{if(which==0)(void)hp::owning_hash(input,hp::DefaultHash{},opts);else if(which==1)(void)hp::index_hash(input,hp::DefaultHash{},opts);else(void)hp::v11_sort_unique(input);}catch(const std::bad_alloc&){threw=true;}catch(...){fail_after=-1;throw;}fail_after=-1;
        same(input,before,"allocation failure mutated input");if(threw)++allocation_failures;else{completed=true;break;}
    }require(completed,"allocation fault sweep did not reach success");}
}
int main(){try{
    // First RED must fail here if grouping/minimum-ID behavior is missing.
    normalCase({{4,9,91,"alpha",30},{4,9,91,"alpha",2},{4,9,91,"alpha",17}},true);
    normalCase({},true);normalCase({{1,2,90,"",4}},true);
    const float high=std::numeric_limits<float>::max(),next=std::nextafter(85.0f,86.0f),sub=std::numeric_limits<float>::denorm_min();
    normalCase({{0,0,85,"a",2},{0,0,next,"a",2},{0,1,85,"a",2},{1,0,85,"a",2},{0,0,85,"b",1},{0,0,high,"a",0},{0,0,std::nextafter(high,0.0f),"a",0},{0,0,sub,"a",8},{0,0,-sub,"a",8},{std::numeric_limits<int>::min(),std::numeric_limits<int>::max(),-high,"a",-3}},true);
    std::vector<hp::Match> ties={{1,2,87,"z",3},{1,2,87,"a",4},{2,1,87,"a",3},{1,1,87,"a",3},{0,1,87,"a",3},{2,1,87,"a",8}};normalCase(ties,true);
    for(std::size_t length:{std::size_t(0),std::size_t(1),std::size_t(15),std::size_t(16),std::size_t(22),std::size_t(23),std::size_t(64),std::size_t(256),std::size_t(4096)}){
        std::string a(length,'q'),b=a;if(b.empty())b="x";else b.back()='r';normalCase({{1,1,88,a,9},{1,1,88,a,1},{1,1,88,b,3}},true);
    }
    normalCase({{1,1,88,std::string("a\0b",3),9},{1,1,88,std::string("a\0b",3),1},{1,1,88,std::string("a\0c",3),2}},true);
    std::mt19937 rng(20261021);std::vector<hp::Match> base;for(int i=0;i<90;++i){const int k=i%15;base.push_back({k%7,k%5,80.0f+float(k%4),"class"+std::to_string(k%3),89-i});}
    for(int i=0;i<400;++i){std::shuffle(base.begin(),base.end(),rng);normalCase(base,i<10);}
    require(hp::DefaultHash{}("zero",1,2,0.0f)==hp::DefaultHash{}("zero",1,2,-0.0f),"equal signed-zero keys must hash identically");
    zeroCase({{1,2,0.0f,"zero",9},{1,2,-0.0f,"zero",1}});
    zeroCase({{1,2,-0.0f,"zero",1},{1,2,0.0f,"zero",9}});
    // Same-ID sign ambiguity: strict bitwise comparison to the actual V11 path.
    std::vector<hp::Match> zeros;for(int i=0;i<97;++i)zeros.push_back({i%3,i%2,(i%5<2)?-0.0f:0.0f,"zero",i%4});
    for(int i=0;i<400;++i){std::shuffle(zeros.begin(),zeros.end(),rng);zeroCase(zeros,false);}
    finiteAndExceptionCases();
    for(std::size_t n:{std::size_t(16),std::size_t(21),std::size_t(32),std::size_t(64),std::size_t(128),std::size_t(187),std::size_t(486),std::size_t(1024),std::size_t(8192),std::size_t(32768),std::size_t(131072)}){
        for(std::size_t divisor:{std::size_t(1),std::size_t(2),std::size_t(10),std::size_t(1000)}){
            const std::size_t u=std::max(std::size_t(1),n/divisor);std::vector<hp::Match> values;values.reserve(n);
            for(std::size_t i=0;i<n;++i){const auto k=i%u;values.push_back({int(k%32767),int(k/32767),85.0f+float(k%4),"realistic_class_name_"+std::to_string(k%2),int(n-i)});}
            normalCase(values,n<=128);std::shuffle(values.begin(),values.end(),rng);normalCase(values,n<=128);
        }
    }
    // Synthetic pressure at recorded V11 stage counts; these are not real
    // captured traces and cannot establish measured image speed/quality.
    for(std::size_t n:{std::size_t(230077),std::size_t(352556),std::size_t(398112),std::size_t(486045)}){
        const auto u=n/10;std::vector<hp::Match> pressure;pressure.reserve(n);
        for(std::size_t i=0;i<n;++i){const auto k=i%u;pressure.push_back({int(k%32767),int(k/32767),85.0f+float(k%4),"large_pressure_class",int(n-i)});}
        std::shuffle(pressure.begin(),pressure.end(),rng);normalCase(pressure);
    }
    std::cout<<"{\"status\":\"PASS\",\"checks\":"<<checks<<",\"map_oracle_cases\":"<<oracle_cases<<",\"signed_zero_cases\":"<<zero_cases<<",\"forced_collision_cases\":"<<collision_cases<<",\"allocation_failures\":"<<allocation_failures<<",\"seed\":20261021,\"dataset_access\":false}\n";
    return 0;
}catch(const std::exception& e){fail_after=-1;std::cerr<<"FAIL after "<<checks<<" checks: "<<e.what()<<'\n';return 1;}}
