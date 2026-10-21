#include "../candidate/line2Dup_local_cache.hpp"
#include <array>
#include <cstdint>
#include <cstring>
#include <iostream>
#include <stdexcept>
#include <vector>

namespace {
using line2Dup::detail::LocalCenterCache;
using line2Dup::detail::LocalMaximum;
void require(bool ok, const char* message) {
    if (!ok) throw std::runtime_error(message);
}
std::uint32_t bits(float value) {
    std::uint32_t out;
    static_assert(sizeof(out)==sizeof(value), "Float32 required");
    std::memcpy(&out,&value,sizeof(out));
    return out;
}
float score(std::uint32_t value) {
    float out;std::memcpy(&out,&value,sizeof(out));return out;
}
bool equal(const LocalMaximum& a, const LocalMaximum& b) {
    return a.raw==b.raw && bits(a.score)==bits(b.score) &&
           a.row==b.row && a.col==b.col;
}
void literal_hits_and_keys() {
    LocalCenterCache cache;
    LocalMaximum out{91,score(0x3f800001U),-3,14};
    require(!cache.find(2,3,out), "fresh cache produced a hit");
    require(equal(out,{91,score(0x3f800001U),-3,14}),
            "miss mutated the caller's fallback result");
    cache.insert(2,3,{17,score(0x3f800001U),0,8});
    require(cache.find(2,3,out), "stored result was not retrieved");
    require(equal(out,{17,score(0x3f800001U),0,8}),
            "cache reconstructed score or changed winner fields");
    require(!cache.find(3,2,out), "x/y order was ignored");
    require(equal(out,{17,score(0x3f800001U),0,8}), "nonfresh miss changed output");
    cache.insert(-1,0,{0,score(0x80000000U),-1,-1});
    require(cache.find(-1,0,out) && equal(out,{0,score(0x80000000U),-1,-1}),
            "zero/signed-zero result was treated as empty or reconstructed");
    cache.insert(0,-1,{4,25.f,15,0});
    require(cache.find(0,-1,out) && equal(out,{4,25.f,15,0}),
            "signed key or complete first-winner position was lost");
    cache.insert(0,0,{4,25.f,0,15});
    require(cache.find(0,0,out) && equal(out,{4,25.f,0,15}),
            "same-score keys did not retain their distinct first winners");
}
void reset_and_worker_isolation() {
    LocalCenterCache first,second;
    first.insert(4,7,{32,50.f,1,2});second.insert(4,7,{8,12.5f,3,4});
    first.reset();LocalMaximum out{7,1.f,5,6};
    require(!first.find(4,7,out) && equal(out,{7,1.f,5,6}),
            "template/level reset retained an entry or modified a miss");
    require(second.find(4,7,out) && equal(out,{8,12.5f,3,4}),
            "reset crossed worker ownership");
    first.insert(4,7,{17,score(0x3eaaaaabU),15,15});
    require(first.find(4,7,out) && equal(out,{17,score(0x3eaaaaabU),15,15}),
            "new template/options scope returned stale normalization");
    first.reset();first.reset();
    require(!first.find(4,7,out), "repeated reset failed");
}
void capacity_preserves_complete_ordered_fallback() {
    LocalCenterCache cache;
    for(int i=0;i<16;++i) cache.insert(i,-i,{unsigned(i+1),float(i)+.25f,i,15-i});
    for(int i=16;i<80;++i) cache.insert(i,-i,{unsigned(i+1),float(i)+.25f,i,15-i});
    LocalMaximum out;
    for(int i=0;i<16;++i)
        require(cache.find(i,-i,out) && equal(out,{unsigned(i+1),float(i)+.25f,i,15-i}),
                "overflow evicted or corrupted an earlier stored center");
    require(!cache.find(16,-16,out), "full cache overwrote one of the sixteen entries");
    unsigned computed=0;std::vector<LocalMaximum> emitted;
    for(int pass=0;pass<2;++pass) for(int i=0;i<80;++i) {
        if(!cache.find(i,-i,out)) {
            ++computed;out={unsigned(i+1),float(i)+.25f,i,15-i};
            cache.insert(i,-i,out);
        }
        emitted.push_back(out);
    }
    require(computed==128 && emitted.size()==160,
            "overflow became a search limit or erased retained hits");
    for(int i=0;i<160;++i) {
        const int key=i%80;
        require(equal(emitted[i],{unsigned(key+1),float(key)+.25f,key,15-key}),
                "overflow changed complete emitted fields or candidate order");
    }
}
}
int main() {
    try {
        literal_hits_and_keys();reset_and_worker_isolation();
        capacity_preserves_complete_ordered_fallback();
        std::cout << "PASS cache contract: exact float/winner fields, signed/zero keys, "
                     "reset/worker isolation and 160 ordered overflow results\n";
        return 0;
    } catch(const std::exception& error) {
        std::cerr << "FAIL cache contract: " << error.what() << '\n';return 1;
    }
}
