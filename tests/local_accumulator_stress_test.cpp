#include "line2Dup_local.hpp"
#include <cstring>
#include <iostream>
#include <random>
#include <stdexcept>
#include <vector>

namespace {
void require(bool ok,const char* message){if(!ok)throw std::runtime_error(message);}
unsigned bits(float value){unsigned out;std::memcpy(&out,&value,sizeof(out));return out;}
}
int main() {
    try {
        unsigned char maximum[256];std::fill(maximum,maximum+256,4);
        std::vector<const unsigned char*> same(8191,maximum);
        // Exhaust *every* legal feature count, not only fixture-specific sizes.
        // A constant maximum response has the independent answer raw=4*N,
        // score=100 and the literal first winner (0,0).
        for(int n=1;n<8192;++n) {
            const auto found=line2Dup::detail::localMaximum16x16(same.data(),n,16,n);
            require(found.raw==4u*n&&bits(found.score)==bits(100.f)&&found.row==0&&found.col==0,
                    "legal feature count overflow/widening/winner failure");
        }
        std::size_t scalar_pixels=0;
        for(unsigned seed:{0x17451u,0x738922u,0xa17e0u,0xd013u}) {
            std::mt19937 rng(seed);
            for(int trial=0;trial<256;++trial) {
                // Small counts dominate imported tiny parts; every fourth
                // case samples the entire legal word-accumulator range.
                const int n=1+int(rng()%(trial%4==0?8191:160));
                const int valid=int(rng()%(n+1)),stride=16+int(rng()%97),shift=int(rng()%16);
                std::vector<std::vector<unsigned char>> storage(valid,
                    std::vector<unsigned char>(shift+15*stride+16,211));
                std::vector<const unsigned char*> streams;
                for(auto& buffer:storage) {
                    for(int row=0;row<16;++row)for(int col=0;col<16;++col) {
                        const unsigned char values[]={0,3,4};buffer[shift+row*stride+col]=values[rng()%3];
                    }
                    streams.push_back(buffer.data()+shift);
                }
                unsigned expected_raw=0;float expected_score=0;int ey=-1,ex=-1;
                for(int row=0;row<16;++row)for(int col=0;col<16;++col) {
                    unsigned sum=0;for(const auto* stream:streams)sum+=stream[row*stride+col];
                    const float score=(int(sum)*100.f)/(4*n);
                    if(score>expected_score){expected_raw=sum;expected_score=score;ey=row;ex=col;}
                    ++scalar_pixels;
                }
                const auto found=line2Dup::detail::localMaximum16x16(streams.data(),streams.size(),stride,n);
                if(found.raw!=expected_raw||bits(found.score)!=bits(expected_score)||found.row!=ey||found.col!=ex)
                    throw std::runtime_error("random local mismatch seed="+std::to_string(seed)+" trial="+std::to_string(trial)+" N="+std::to_string(n));
            }
        }
        std::cout<<"PASS accumulator stress: all 8191 legal feature counts + 1024 independent random cases / "
                 <<scalar_pixels<<" scalar patch positions, 4 recorded seeds\n";
        return 0;
    }catch(const std::exception& error){std::cerr<<"FAIL accumulator stress: "<<error.what()<<'\n';return 1;}
}
