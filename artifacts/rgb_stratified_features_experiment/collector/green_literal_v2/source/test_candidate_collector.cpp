#include "candidate_collector.hpp"
#include <opencv2/imgproc.hpp>
#include <windows.h>
#include <tlhelp32.h>
#include <cmath>
#include <cstring>
#include <functional>
#include <iostream>
#include <limits>
#include <stdexcept>
#include <string>
#include <utility>

using rgb_stratified::collector::Candidate;
using rgb_stratified::collector::Result;
namespace {
std::uint64_t calls = 0;
void require(bool ok, const std::string& what) {
    if (!ok) throw std::runtime_error(what);
}
std::uint32_t bits(float value) {
    std::uint32_t out;
    std::memcpy(&out, &value, sizeof(out));
    return out;
}
float from_bits(std::uint32_t value) {
    float out;
    std::memcpy(&out, &value, sizeof(out));
    return out;
}
struct Maps {
    cv::Mat mag, angle, theta, mask;
    explicit Maps(int h=19, int w=19, unsigned char mask_value=255)
        : mag(h,w,CV_32F,cv::Scalar(0)),
          angle(h,w,CV_8U,cv::Scalar(1)),
          theta(h,w,CV_32F,cv::Scalar(0)),
          mask(h,w,CV_8U,cv::Scalar(mask_value)) {}
};
Result run(const Maps& m) {
    ++calls;
    return rgb_stratified::collector::collect(m.mag,m.angle,m.theta,m.mask);
}
bool object_at(const cv::Mat& m, int x, int y) {
    return x>=0 && y>=0 && x<m.cols && y<m.rows && m.at<unsigned char>(y,x)!=0;
}
// Independent exhaustive literal oracle: no OpenCV morphology, valid bitmap,
// collector import/helpers, per-arm pool or sampler. Precompute all local
// maxima, then test each center against the list of earlier chosen suppressors.
Result oracle(const Maps& m) {
    Result r;
    r.actual_mask=m.mask.clone();
    r.domain=cv::Mat::zeros(m.mask.size(),CV_8U);
    r.interior=cv::Mat::zeros(m.mask.size(),CV_8U);
    for (int y=0;y<m.mask.rows;++y) for (int x=0;x<m.mask.cols;++x) {
        bool any=false, all=true;
        for (int dy=-4;dy<=4;++dy) for (int dx=-4;dx<=4;++dx) {
            const bool v=object_at(m.mask,x+dx,y+dy);
            any=any||v;all=all&&v;
        }
        r.domain.at<unsigned char>(y,x)=any?255:0;
        r.interior.at<unsigned char>(y,x)=all?255:0;
    }
    std::vector<cv::Point> local_maxima;
    for (int y=2;y<m.mag.rows-2;++y) for (int x=2;x<m.mag.cols-2;++x) {
        if (!r.domain.at<unsigned char>(y,x)) continue;
        bool greatest=true;
        const float v=m.mag.at<float>(y,x);
        for (int yy=y-2;yy<=y+2;++yy) for (int xx=x-2;xx<=x+2;++xx)
            if (m.mag.at<float>(yy,xx)>v) greatest=false;
        if (greatest) local_maxima.emplace_back(x,y);
    }
    std::vector<cv::Point> suppressors;
    for (const auto& p:local_maxima) {
        bool suppressed=false;
        for (const auto& earlier:suppressors)
            if (std::abs(earlier.x-p.x)<=2 && std::abs(earlier.y-p.y)<=2)
                suppressed=true;
        if (suppressed) continue;
        suppressors.push_back(p);++r.nms_maxima;
        const auto a=m.angle.at<unsigned char>(p.y,p.x);
        if (!(m.mag.at<float>(p.y,p.x)>1600.0f) || !a) continue;
        if (a&(a-1)) throw std::domain_error("Oracle reached an invalid positive quantized angle");
        unsigned char label=0;
        for (unsigned int v=a;v>1;v/=2) ++label;
        r.candidates.push_back(Candidate{static_cast<std::uint32_t>(r.candidates.size()),
            p.x,p.y,label,bits(m.mag.at<float>(p.y,p.x)),bits(m.theta.at<float>(p.y,p.x)),
            r.interior.at<unsigned char>(p.y,p.x)!=0});
    }
    return r;
}
void compare_map(const cv::Mat& got,const cv::Mat& want,const std::string& name) {
    require(got.type()==CV_8UC1 && got.size()==want.size(),name+" shape/type");
    for (int y=0;y<want.rows;++y) for (int x=0;x<want.cols;++x)
        require(got.at<unsigned char>(y,x)==want.at<unsigned char>(y,x),
                name+" byte at "+std::to_string(x)+","+std::to_string(y));
}
void compare(const Result& got,const Result& want) {
    require(got.candidates.size()==want.candidates.size(),"candidate count: got "+
        std::to_string(got.candidates.size())+" expected "+std::to_string(want.candidates.size()));
    for (std::size_t i=0;i<want.candidates.size();++i) {
        const auto& a=got.candidates[i];const auto& b=want.candidates[i];
        require(a.ordinal==b.ordinal && a.x==b.x && a.y==b.y && a.label==b.label &&
            a.magnitude_bits==b.magnitude_bits && a.theta_bits==b.theta_bits &&
            a.interior==b.interior,"candidate fields/order at "+std::to_string(i));
    }
    require(got.nms_maxima==want.nms_maxima,"all NMS maxima, including low/invalid centers");
    compare_map(got.actual_mask,want.actual_mask,"actual_mask");
    compare_map(got.domain,want.domain,"domain");
    compare_map(got.interior,want.interior,"interior");
}
void coords(const Result& r,std::initializer_list<std::pair<int,int>> want) {
    require(r.candidates.size()==want.size(),"literal candidate count: got "+
        std::to_string(r.candidates.size())+" expected "+std::to_string(want.size()));
    std::size_t i=0;
    for (const auto& p:want) {
        require(r.candidates[i].x==p.first && r.candidates[i].y==p.second,
                "literal row-major coordinate at "+std::to_string(i));++i;
    }
}
void dense_rowmajor() {
    Maps m;
    m.mag.at<float>(3,3)=2500;m.theta.at<float>(3,3)=from_bits(0x80000000U);
    m.mag.at<float>(3,11)=3600;m.angle.at<unsigned char>(3,11)=128;
    m.theta.at<float>(3,11)=from_bits(0x7fc01234U);
    m.mag.at<float>(11,8)=4900;m.angle.at<unsigned char>(11,8)=8;
    auto r=run(m);coords(r,{{3,3},{11,3},{8,11}});compare(r,oracle(m));
    require(r.candidates[0].theta_bits==0x80000000U &&
        r.candidates[1].theta_bits==0x7fc01234U,"theta bit preservation");
    require(!r.candidates[0].interior && !r.candidates[1].interior &&
        r.candidates[2].interior,"stratum by actual mask support");
}
void shared_pool_nms() {
    Maps m(15,15);
    m.mag.at<float>(7,3)=2500;m.mag.at<float>(7,5)=2500;
    // (3,7) is support; (5,7) is interior. Equal maxima share suppression.
    auto r=run(m);coords(r,{{3,7}});compare(r,oracle(m));
    require(!r.candidates[0].interior,"earlier support maximum retained");
}
void mask_before_nms() {
    Maps m(25,25,0);m.mask.at<unsigned char>(10,15)=7;
    m.mag.at<float>(10,10)=3600;m.mag.at<float>(10,12)=3600;
    auto r=run(m);coords(r,{{12,10}});compare(r,oracle(m));
}
void invalid_angles_still_suppress() {
    Maps m(15,15);m.mag.at<float>(7,3)=3600;m.angle.at<unsigned char>(7,3)=0;
    m.mag.at<float>(7,5)=3600;m.mag.at<float>(7,10)=2500;
    auto r=run(m);coords(r,{{10,7}});compare(r,oracle(m));
}
void strong_multibit_rejection() {
    for (unsigned char invalid:std::vector<unsigned char>{3,5,127,255}) {
        Maps m(15,15);m.mag.at<float>(7,3)=2500;
        m.angle.at<unsigned char>(7,3)=invalid;
        bool rejected=false;
        try { run(m); } catch (const cv::Exception& e) {
            require(e.code==cv::Error::StsBadArg,"multi-bit error code matches V11 getLabel");
            rejected=true;
        }
        require(rejected,"accepted strong multi-bit angle must throw cv::Exception");
    }
    Maps weak(9,9);weak.mag.setTo(1600.0f);weak.angle.setTo(3);
    auto r=run(weak);coords(r,{});compare(r,oracle(weak));
    Maps suppressed(15,15);suppressed.mag.at<float>(7,3)=3600;
    suppressed.mag.at<float>(7,5)=3600;suppressed.angle.at<unsigned char>(7,5)=3;
    r=run(suppressed);coords(r,{{3,7}});compare(r,oracle(suppressed));
    Maps not_max(15,15);not_max.mag.at<float>(7,3)=2500;
    not_max.angle.at<unsigned char>(7,3)=255;not_max.mag.at<float>(7,4)=3600;
    r=run(not_max);coords(r,{{4,7}});compare(r,oracle(not_max));
}
void strict_strength_and_low_maxima() {
    Maps m(9,9);m.mag.setTo(1600.0f);
    auto r=run(m);coords(r,{});compare(r,oracle(m));
    require(r.nms_maxima==4,"low-strength maxima must suppress: literal four centers");
    m.mag.setTo(1600.25f);r=run(m);
    coords(r,{{2,2},{5,2},{2,5},{5,5}});compare(r,oracle(m));
}
void full_maps_nonzero_and_zero_exterior() {
    for (unsigned char v:std::vector<unsigned char>{1,7,128,255}) {
        Maps m(15,15,0);m.mask.at<unsigned char>(7,7)=v;
        m.mag.at<float>(7,7)=2500;auto r=run(m);coords(r,{{7,7}});compare(r,oracle(m));
        require(r.domain.at<unsigned char>(3,3)==255 &&
            r.domain.at<unsigned char>(2,3)==0,"literal radius-4 dilation");
        require(cv::countNonZero(r.interior)==0,"single pixel has no interior");
    }
    Maps m(13,15);auto r=run(m);compare(r,oracle(m));
    require(r.interior.at<unsigned char>(4,4)==255 && r.interior.at<unsigned char>(3,4)==0 &&
        r.interior.at<unsigned char>(8,10)==255 && r.interior.at<unsigned char>(9,10)==0,
        "constant-zero exterior erosion, not replicate/default morphology border");
    m.mask.setTo(0);r=run(m);compare(r,oracle(m));coords(r,{});
}
void holes_thin_and_concave() {
    Maps m(21,23,0);
    for (int y=1;y<20;++y) for (int x=1;x<22;++x)
        if (x<12 || y>10) m.mask.at<unsigned char>(y,x)=1;
    m.mask.at<unsigned char>(7,7)=0;
    for (int y=0;y<m.mag.rows;++y) for (int x=0;x<m.mag.cols;++x)
        m.mag.at<float>(y,x)=static_cast<float>((x*37+y*71)%8)*625;
    compare(run(m),oracle(m));
    m.mask.setTo(0);for(int y=0;y<m.mask.rows;++y)m.mask.at<unsigned char>(y,11)=128;
    auto r=run(m);compare(r,oracle(m));require(cv::countNonZero(r.interior)==0,"thin object interior");
}
void margin_and_border_comparators() {
    Maps m(15,15);m.mag.at<float>(7,1)=5000;m.mag.at<float>(7,3)=4000;
    m.mag.at<float>(7,6)=4900;
    auto r=run(m);coords(r,{{6,7}});compare(r,oracle(m));
    for (const auto& c:r.candidates)
        require(c.x>=2 && c.y>=2 && c.x<m.mag.cols-2 && c.y<m.mag.rows-2,"two-pixel scan margin");
    for (int h=1;h<=5;++h) for (int w=1;w<=5;++w) {
        Maps tiny(h,w);tiny.mag.setTo(2500);compare(run(tiny),oracle(tiny));
    }
}
void no_mutation_alias_and_noncontinuous() {
    Maps m(17,19,7);m.mag.at<float>(8,8)=2500;
    cv::Rect roi(1,1,15,13);m.mag=m.mag(roi);m.angle=m.angle(roi);
    m.theta=m.theta(roi);m.mask=m.mask(roi);
    require(!m.mag.isContinuous() && !m.mask.isContinuous(),"fixture is strided");
    Maps before;before.mag=m.mag.clone();before.angle=m.angle.clone();
    before.theta=m.theta.clone();before.mask=m.mask.clone();
    auto expected=oracle(m);auto r=run(m);compare(r,expected);
    require(cv::norm(m.mag,before.mag,cv::NORM_INF)==0 &&
        cv::norm(m.angle,before.angle,cv::NORM_INF)==0 &&
        cv::norm(m.theta,before.theta,cv::NORM_INF)==0 &&
        cv::norm(m.mask,before.mask,cv::NORM_INF)==0,"input maps unmodified");
    m.mask.setTo(0);compare(r,expected);
}
void floor_half_resize_fixture() {
    cv::Mat source(5,7,CV_8U);
    for (int y=0;y<5;++y) for (int x=0;x<7;++x)
        source.at<unsigned char>(y,x)=static_cast<unsigned char>(1+y*7+x);
    cv::Mat resized;
    cv::resize(source,resized,cv::Size(source.cols/2,source.rows/2),0,0,cv::INTER_NEAREST);
    const unsigned char expected[2][3]={{1,3,5},{15,17,19}};
    for (int y=0;y<2;++y) for (int x=0;x<3;++x)
        require(resized.at<unsigned char>(y,x)==expected[y][x],"actual odd floor-half nearest bytes");
    Maps m(2,3);m.mask=resized;compare(run(m),oracle(m));
    // Every-second indexing is equivalent here; never label it a RED mutation.
}
void bad_inputs_and_nonfinite_magnitude() {
    auto rejects=[](const Maps& m) {
        bool rejected=false;try { run(m); } catch (const std::invalid_argument&) { rejected=true; }
        require(rejected,"bad map/shape/nonfinite magnitude must reject as invalid_argument");
    };
    Maps m;m.mag.release();rejects(m);
    m=Maps();m.mag=cv::Mat(19,19,CV_64F);rejects(m);
    m=Maps();m.angle=cv::Mat(19,19,CV_8UC2);rejects(m);
    m=Maps();m.theta=cv::Mat(18,19,CV_32F);rejects(m);
    m=Maps();m.mask=cv::Mat(19,19,CV_32F);rejects(m);
    int sizes[]={2,3,4};m=Maps();m.mask=cv::Mat(3,sizes,CV_8U);rejects(m);
    m=Maps();m.mag=cv::Mat(3,sizes,CV_32F);rejects(m);
    for (float v:std::vector<float>{std::numeric_limits<float>::infinity(),
            -std::numeric_limits<float>::infinity(),std::numeric_limits<float>::quiet_NaN()}) {
        m=Maps();m.mask.setTo(0);m.mag.at<float>(0,0)=v;rejects(m); // outside both scan and object domain
    }
}
void exhaustive_numeric_maps() {
    std::uint32_t state=0x31415926U;
    for (int seed=0;seed<32;++seed) {
        Maps m(9+seed%7,11+seed%5,0);
        for (int y=0;y<m.mag.rows;++y) for (int x=0;x<m.mag.cols;++x) {
            state=state*1664525U+1013904223U;
            m.mag.at<float>(y,x)=static_cast<float>((state>>24)%9)*400;
            m.mask.at<unsigned char>(y,x)=((state>>16)%7==0)?7:0;
            const unsigned int a=(state>>8)%11;
            m.angle.at<unsigned char>(y,x)=a<8?static_cast<unsigned char>(1U<<a):static_cast<unsigned char>(a==8?0:3);
            m.theta.at<float>(y,x)=from_bits(state);
        }
        bool oracle_rejected=false;
        Result expected;
        try { expected=oracle(m); } catch(const std::domain_error&) { oracle_rejected=true; }
        bool actual_rejected=false;
        Result actual;
        try { actual=run(m); } catch(const cv::Exception& e) {
            require(e.code==cv::Error::StsBadArg,"exhaustive invalid-angle rejection code");
            actual_rejected=true;
        }
        require(actual_rejected==oracle_rejected,"exhaustive NMS-dependent angle rejection");
        if (!oracle_rejected) compare(actual,expected);
    }
}
void print_loaded_modules() {
    HANDLE snap=CreateToolhelp32Snapshot(TH32CS_SNAPMODULE|TH32CS_SNAPMODULE32,GetCurrentProcessId());
    require(snap!=INVALID_HANDLE_VALUE,"module snapshot");
    MODULEENTRY32W entry{};entry.dwSize=sizeof(entry);
    require(Module32FirstW(snap,&entry)!=0,"first loaded module");
    do {
        char path[4*MAX_PATH];
        require(WideCharToMultiByte(CP_UTF8,0,entry.szExePath,-1,path,sizeof(path),nullptr,nullptr)>0,
                "loaded module UTF-8 path");
        std::cout<<"MODULE\t"<<path<<'\n';
    } while (Module32NextW(snap,&entry));
    CloseHandle(snap);
}
}
int main(int argc,char** argv) {
    cv::setNumThreads(1);
    const std::vector<std::pair<std::string,std::function<void()>>> tests={
        {"dense_rowmajor",dense_rowmajor},{"shared_pool_nms",shared_pool_nms},
        {"mask_before_nms",mask_before_nms},{"invalid_angles_still_suppress",invalid_angles_still_suppress},
        {"strong_multibit_rejection",strong_multibit_rejection},
        {"strict_strength_and_low_maxima",strict_strength_and_low_maxima},
        {"full_maps_nonzero_and_zero_exterior",full_maps_nonzero_and_zero_exterior},
        {"holes_thin_and_concave",holes_thin_and_concave},
        {"margin_and_border_comparators",margin_and_border_comparators},
        {"no_mutation_alias_and_noncontinuous",no_mutation_alias_and_noncontinuous},
        {"floor_half_resize_fixture",floor_half_resize_fixture},
        {"bad_inputs_and_nonfinite_magnitude",bad_inputs_and_nonfinite_magnitude},
        {"exhaustive_numeric_maps",exhaustive_numeric_maps}};
    const std::string only=argc==2?argv[1]:"";
    int passed=0,failed=0;
    for(const auto& t:tests) {
        if(!only.empty() && only!=t.first)continue;
        try { t.second();++passed;std::cout<<"PASS\t"<<t.first<<'\n'; }
        catch(const std::exception& e) { ++failed;std::cout<<"FAIL\t"<<t.first<<'\t'<<e.what()<<'\n'; }
    }
    if(passed+failed==0) { ++failed;std::cout<<"FAIL\tunknown_test_case\n"; }
    std::cout<<"SUMMARY\tpassed="<<passed<<"\tfailed="<<failed
        <<"\tcollector_invocations="<<calls<<"\timage_decodes=0\tmatcher_calls=0\n";
    try { print_loaded_modules(); } catch(const std::exception& e) {
        std::cerr<<e.what()<<'\n';return 2;
    }
    return failed?1:0;
}
