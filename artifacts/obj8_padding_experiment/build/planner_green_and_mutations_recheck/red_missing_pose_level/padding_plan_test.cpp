#include "padding_plan.hpp"
#include <functional>
#include <iostream>
#include <set>
using namespace obj8_padding;
static std::size_t assertions=0,rejections=0;
static void check(bool value,const char* reason) {++assertions;if(!value)throw std::runtime_error(reason);}
static void rejects(const std::function<void()>& call,const char* reason) {
    bool rejected=false;try{call();}catch(const std::exception&){rejected=true;}
    check(rejected,reason);++rejections;
}
static Layer layer(int id,int level,std::int64_t w,std::int64_t h,std::int64_t x,std::int64_t y,const std::string& c="object") {
    Layer out;out.class_id=c;out.template_id=id;out.level=level;
    out.width=w;out.height=h;out.max_x=x;out.max_y=y;return out;
}
int main() {
    try {
        const std::array<U,4> base{{64,64,64,68}},zero{{0,0,0,0}};
        const std::vector<Layer> bank={layer(1,0,734,700,734,700),layer(1,1,367,350,367,350),layer(2,0,700,734,700,734),layer(2,1,350,367,350,367)};
        const auto actual=make_plan(720,540,base,bank,{4,8});
        check(actual.width==848 && actual.height==800 && actual.alignment==16,"Literal full-bank dimension failure");
        check(actual.padding==std::array<U,4>{{64,64,64,196}},"Source origin or extra bottom moved");
        check(actual.pixels==678400 && actual.estimated_bytes==347340800,"Pixel/memory estimate failure");
        // Pose A binds width and pose B binds height; neither may be omitted.
        const auto independent=make_plan(1,1,zero,bank,{4,8});
        check(independent.width==800 && independent.height==800,"Cross-pose max failure");
        // A feature at coordinate==declared extent needs extent+1 coarse pixels.
        const auto coarse=make_plan(100,99,zero,{layer(0,0,100,100,100,100)},{4});
        check(coarse.width==104 && coarse.height==104,"Actual feature +1 omitted");
        const auto mixed=make_plan(641,479,{{64,64,64,64}},
            {layer(0,0,100,90,100,90),layer(0,1,60,50,60,50),layer(0,2,30,25,30,25)},{3,5,7});
        check(mixed.width==840 && mixed.height==840 && mixed.alignment==420,"LCM or odd source rounding failure");
        check(mixed.padding==std::array<U,4>{{64,64,135,297}},"Nonsquare coordinate padding failure");
        // Literal below/equal/above bounds; planner is compared to brute force,
        // whose predicate examines every individual layer rather than maxima.
        for(int width=1;width<=17;++width)for(int height=1;height<=13;++height) {
            const std::vector<Layer> objects={layer(0,0,width,height,width,height),layer(0,1,(width+1)/2,(height+1)/2,(width+1)/2,(height+1)/2)};
            const auto result=make_plan(3,5,zero,objects,{4,8});
            U bx=0,by=0;
            for(U d=16;d<=256;d+=16) {
                if(!bx && d>=3 && d>=U(width+64) && d/2>=U((width+1)/2+1))bx=d;
                if(!by && d>=5 && d>=U(height+64) && d/2>=U((height+1)/2+1))by=d;
            }
            check(result.width==bx && result.height==by,"Brute-force minimum dimension mismatch");
            check(result.padding[0]==0 && result.padding[1]==0 && result.padding[2]==bx-3 && result.padding[3]==by-5,"Brute-force origin transform mismatch");
        }
        const auto max=std::numeric_limits<U>::max();
        rejects([&]{add(max,1);},"Unchecked sum");
        rejects([&]{multiply(U(1)<<40,U(1)<<40);},"Unchecked product");
        rejects([&]{align(max,16);},"Unchecked alignment");
        rejects([&]{align(1,0);},"Zero alignment accepted");
        rejects([&]{make_plan(720,540,base,{},{});},"Empty bank accepted");
        rejects([&]{make_plan(0,540,base,bank,{4,8});},"Empty source accepted");
        rejects([&]{make_plan(720,540,base,bank,{4,0});},"Zero T accepted");
        const std::vector<Layer> incomplete(1,bank.front());
        rejects([&]{make_plan(720,540,base,incomplete,{4,8});},"Missing pose level accepted");
        auto duplicate=bank;duplicate.push_back(bank[0]);
        rejects([&]{make_plan(720,540,base,duplicate,{4,8});},"Duplicate layer accepted");
        auto malformed=bank;malformed[0].min_x=-1;
        rejects([&]{make_plan(720,540,base,malformed,{4,8});},"Negative loaded point accepted");
        malformed=bank;malformed[0].max_y=malformed[0].height+1;
        rejects([&]{make_plan(720,540,base,malformed,{4,8});},"Feature above metadata extent accepted");
        malformed=bank;malformed[0].level=2;
        rejects([&]{make_plan(720,540,base,malformed,{4,8});},"Out of range level accepted");
        Limits limited;limited.pixels=678399;
        rejects([&]{make_plan(720,540,base,bank,{4,8},limited);},"Pixel budget ignored");
        limited=Limits();limited.dynamic_bytes=347340799;
        rejects([&]{make_plan(720,540,base,bank,{4,8},limited);},"Memory estimate budget ignored");
        rejects([&]{make_plan(max,1,base,bank,{4,8});},"Dimension sum overflow accepted");
        // Class identity participates in the pose key.
        auto classes=bank;for(auto row:bank){row.class_id="other";classes.push_back(row);}
        const auto multi=make_plan(720,540,base,classes,{4,8});
        check(multi.width==actual.width && multi.height==actual.height,"Class key aliasing");
        std::cout<<"PASS planner assertions="<<assertions<<" rejected="<<rejections<<"\n";
        return 0;
    }catch(const std::exception& error){std::cerr<<"FAIL planner: "<<error.what()<<"\n";return 1;}
}
