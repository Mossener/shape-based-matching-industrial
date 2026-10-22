#include "../direct/line2Dup_local_cache.hpp"
#include <array>
#include <climits>
#include <cstdint>
#include <cstring>
#include <iostream>
#include <limits>
#include <stdexcept>
#include <vector>

namespace {
using line2Dup::detail::LocalCenterCache;
using line2Dup::detail::LocalMaximum;
static_assert(CHAR_BIT==8,"Eight-bit bytes required");
static_assert(sizeof(int)==4 && sizeof(unsigned int)==4 && sizeof(std::uint32_t)==4,
              "The fixed unsigned32 hash requires32-bit int and unsigned int");
static_assert(std::numeric_limits<std::uint32_t>::digits==32 &&
              std::numeric_limits<unsigned int>::digits==32,"No unsigned integer promotion beyond32 bits");
void require(bool value,const char* message) {if(!value)throw std::runtime_error(message);}
float score(std::uint32_t value) {float out;std::memcpy(&out,&value,4);return out;}
std::uint32_t bits(float value) {std::uint32_t out;std::memcpy(&out,&value,4);return out;}
bool equal(const LocalMaximum& a,const LocalMaximum& b) {
    return a.raw==b.raw && bits(a.score)==bits(b.score) && a.row==b.row && a.col==b.col;
}
struct Key {int x,y;};
// Independent test-side formula groups deterministic keys; the cache exposes
// no slot API, so collision/full-key/replacement tests observe real behavior.
unsigned reference_slot(Key key) {
    const std::uint32_t ux=static_cast<std::uint32_t>(key.x),uy=static_cast<std::uint32_t>(key.y);
    std::uint32_t h=ux+0x9e3779b9U;
    h^=uy+0x9e3779b9U+(h<<6)+(h>>2);
    h^=h>>16;h*=0x85ebca6bU;
    h^=h>>13;h*=0xc2b2ae35U;
    h^=h>>16;return h&15U;
}
void literal_slot_vectors() {
    // Independently computed unsigned32 golden vectors, not matcher inputs.
    require(reference_slot({0,0})==10 && reference_slot({-1,0})==13 &&
            reference_slot({0,-1})==4 && reference_slot({2,3})==2 && reference_slot({3,2})==1 &&
            reference_slot({INT_MIN,INT_MAX})==7 && reference_slot({INT_MAX,INT_MIN})==6,
            "independent test formula differs from fixed literal slot vectors");
}
std::array<std::vector<Key>,16> buckets() {
    std::array<std::vector<Key>,16> out;
    for(int y=-8;y<=8;++y)for(int x=-64;x<=64;++x)out[reference_slot({x,y})].push_back({x,y});
    for(const auto& bucket:out)require(bucket.size()>=2,"Independent deterministic keys did not cover all16 slots");
    return out;
}
LocalMaximum value(unsigned i) {
    return {1000U+i,score(0x3f800001U+i),int(i%16),15-int(i%16)};
}
void stored_hit_and_preserved_miss() {
    LocalCenterCache cache;LocalMaximum out{91,score(0x3f800001U),-3,14};
    const auto sentinel=out;
    require(!cache.find(2,3,out) && equal(out,sentinel),"fresh miss mutated fallback output");
    cache.insert(2,3,{17,score(0x3f800001U),0,8});
    require(cache.find(2,3,out),"stored result was not retrieved");
    require(equal(out,{17,score(0x3f800001U),0,8}),"hit reconstructed score or changed full winner");
    const auto hit=out;
    require(!cache.find(3,2,out) && equal(out,hit),"swapped key produced hit or miss mutated output");
}
void signed_zero_reset_workers() {
    LocalCenterCache a,b;LocalMaximum out{11,1.f,2,3};
    for(const auto key:std::vector<Key>{{-1,0},{0,-1},{0,0},{INT_MIN,INT_MAX},{INT_MAX,INT_MIN}}) {
        a.reset();a.insert(key.x,key.y,{0,score(0x80000000U),-1,-1});
        require(a.find(key.x,key.y,out) && equal(out,{0,score(0x80000000U),-1,-1}),
                "signed/extreme key or zero/signed-zero complete winner was lost");
    }
    a.reset();a.insert(4,7,value(1));b.insert(4,7,value(2));
    a.reset();const auto before=out;
    require(!a.find(4,7,out) && equal(out,before),"reset retained stale entry or changed miss output");
    require(b.find(4,7,out) && equal(out,value(2)),"reset crossed worker ownership");
    a.insert(4,7,{17,score(0x3eaaaaabU),15,15});
    require(a.find(4,7,out) && equal(out,{17,score(0x3eaaaaabU),15,15}),"new scope retained stale normalization");
    a.reset();a.reset();require(!a.find(4,7,out),"repeated reset failed");
}
void sixteen_slots_and_full_key_collisions() {
    const auto groups=buckets();LocalCenterCache cache;LocalMaximum out;
    for(unsigned i=0;i<16;++i)cache.insert(groups[i][0].x,groups[i][0].y,value(i));
    for(unsigned i=0;i<16;++i) {
        const auto a=groups[i][0],b=groups[i][1];
        require(cache.find(a.x,a.y,out) && equal(out,value(i)),"sixteen distinct slots were not retained");
        const auto before=out;
        require(!cache.find(b.x,b.y,out) && equal(out,before),"slot collision falsely matched partial key or mutated miss");
    }
    for(unsigned i=0;i<16;++i)cache.insert(groups[i][1].x,groups[i][1].y,value(i+16));
    for(unsigned i=0;i<16;++i) {
        const auto a=groups[i][0],b=groups[i][1];const auto before=out;
        require(!cache.find(a.x,a.y,out) && equal(out,before),"replacement retained displaced key or mutated miss");
        require(cache.find(b.x,b.y,out) && equal(out,value(i+16)),"collision replacement was not retrieved completely");
    }
}
void each_axis_is_part_of_collision_key() {
    for(unsigned axis=0;axis<2;++axis) {
        std::array<std::vector<Key>,16> groups;
        for(int i=-16;i<=16;++i) {
            const Key key=axis?Key{0,i}:Key{i,0};
            groups[reference_slot(key)].push_back(key);
        }
        bool exercised=false;
        for(const auto& group:groups)if(group.size()>=2) {
            const auto a=group[0],b=group[1];LocalCenterCache cache;LocalMaximum out=value(90);
            cache.insert(a.x,a.y,value(1));
            require(!cache.find(b.x,b.y,out) && equal(out,value(90)),
                    "same-x or same-y collision ignored the other full-key component");
            cache.insert(b.x,b.y,value(2));
            require(!cache.find(a.x,a.y,out) && equal(out,value(90)),
                    "axis collision replacement retained the displaced key or changed a miss");
            require(cache.find(b.x,b.y,out) && equal(out,value(2)),"axis collision replacement lost complete winner");
            exercised=true;break;
        }
        require(exercised,"independent axis collision was not exercised");
    }
}
void complete_ordered_collision_fallback() {
    const auto groups=buckets();LocalCenterCache cache;LocalMaximum out;
    std::vector<LocalMaximum> emitted,expected;unsigned computed=0;
    for(unsigned round=0;round<3;++round)for(unsigned bucket=0;bucket<16;++bucket)
        for(unsigned choice=0;choice<2;++choice)for(unsigned repeat=0;repeat<2;++repeat) {
            const auto key=groups[bucket][choice];const auto oracle=value(bucket*2+choice);
            if(!cache.find(key.x,key.y,out)) {++computed;out=oracle;cache.insert(key.x,key.y,out);}
            emitted.push_back(out);expected.push_back(oracle);
        }
    require(computed==96 && emitted.size()==192 && expected.size()==192,
            "collision fallback became a limit, lost consecutive hits or skipped computation");
    for(unsigned i=0;i<emitted.size();++i)
        require(equal(emitted[i],expected[i]),"collision fallback changed full emitted winner or candidate order");
}
}
int main() {
    try {
        literal_slot_vectors();stored_hit_and_preserved_miss();signed_zero_reset_workers();
        sixteen_slots_and_full_key_collisions();each_axis_is_part_of_collision_key();complete_ordered_collision_fallback();
        std::cout<<"PASS direct16 contract: full signed key/winner, output-preserving miss, zero/extreme keys, "
                   "reset/worker isolation, all16 slots, collision replacement and192 ordered fallback results\n";
        return 0;
    } catch(const std::exception& error) {
        std::cerr<<"FAIL direct16 contract: "<<error.what()<<'\n';return 1;
    }
}
