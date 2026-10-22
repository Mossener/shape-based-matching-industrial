// Literal integration adapter TU; frozen core remains a separate .cpp TU.
#include "shared_training.hpp"
#include "../collector/candidate_collector.cpp"

#include <windows.h>
#include <tlhelp32.h>
#include <algorithm>
#include <array>
#include <cstdint>
#include <cstring>
#include <functional>
#include <iostream>
#include <limits>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

namespace it = rgb_stratified::integration;
namespace cc = rgb_stratified::collector;
namespace ss = industrial_stratified;
namespace {
std::uint64_t assertions=0, pose_calls=0;
void require(bool value,const char* message) {
    ++assertions;
    if (!value) throw std::runtime_error(message);
}
std::uint32_t bits(float value) {
    std::uint32_t result=0;std::memcpy(&result,&value,sizeof(result));return result;
}
std::uint32_t theta_bits(const line2Dup::Feature& feature) {
    std::uint32_t result=0;std::memcpy(&result,&feature.theta,sizeof(result));return result;
}
cv::Mat source() {
    cv::Mat result(49,65,CV_8UC3,cv::Scalar(0,0,0));
    cv::rectangle(result,cv::Rect(8,8,40,28),cv::Scalar(255,255,255),cv::FILLED);
    return result;
}
std::vector<cc::Candidate> candidates(int dx=0,int dy=0) {
    const std::array<std::pair<int,int>,6> xy={{{0,0},{10,0},{0,10},{10,10},{5,5},{20,0}}};
    std::vector<cc::Candidate> pool;
    for (std::uint32_t i=0;i<6;++i)
        pool.push_back(cc::Candidate{i,xy[i].first+dx,xy[i].second+dy,
            static_cast<std::uint8_t>(i),bits(10.0F-static_cast<float>(i)),
            i==0 ? 0x7fc12345U : 0x3f800000U+i,(i%2)==1});
    return pool;
}
cc::Result collection(const cv::Mat& mask,std::vector<cc::Candidate> pool) {
    cc::Result result;
    result.actual_mask=mask.clone();
    result.domain=cv::Mat(mask.size(),CV_8U,cv::Scalar(255));
    result.interior=cv::Mat(mask.size(),CV_8U,cv::Scalar(0));
    result.candidates=std::move(pool);result.nms_maxima=result.candidates.size();
    return result;
}
std::uint64_t digest(const std::vector<ss::Candidate>& pool) {
    std::uint64_t result=14695981039346656037ULL;
    const auto add=[&](std::uint64_t value,unsigned bytes) {
        for (unsigned i=0;i<bytes;++i) { result^=(value>>(8*i))&255U;result*=1099511628211ULL; }
    };
    for (const auto& item:pool) {
        add(item.ordinal,8);add(static_cast<std::uint32_t>(item.x),4);
        add(static_cast<std::uint32_t>(item.y),4);add(item.label,1);
        add(item.magnitude_bits,4);add(item.theta_bits,4);add(static_cast<unsigned>(item.stratum),1);
    }
    return result;
}
void check_counts(const it::PoseResult& result) {
    require(result.counts.gradient_pyramids==1,"exactly one gradient pyramid per pose");
    require(result.counts.pyramid_downs==1,"exactly one transition to L1");
    for (unsigned level=0;level<2;++level) {
        require(result.counts.collector_calls[level]==1,"collector must run once per layer");
        require(result.counts.sampler_calls[level][0]==1 && result.counts.sampler_calls[level][1]==1,
                "both samplers must run once per layer");
    }
}

// Catches returning after failed L0, rebuilding C for P/B, or passing pool copies.
void failed_l0_still_l1_and_shared_pool() {
    auto src=source();cv::Mat mask(src.size(),CV_8U,cv::Scalar(7));
    mask.at<unsigned char>(2,4)=128;mask.at<unsigned char>(4,6)=1;
    const auto before=mask.clone();
    unsigned collected=0,sampled=0,hooked=0;
    std::array<std::array<const void*,2>,2> addresses{};
    std::array<std::array<std::uint64_t,2>,2> hashes{};
    const auto collect=[&](const cv::Mat& magnitude,const cv::Mat& angle,
                           const cv::Mat& theta,const cv::Mat& official) {
        const unsigned level=collected++;
        require(level<2,"unexpected collector invocation");
        require(magnitude.type()==CV_32FC1 && theta.type()==CV_32FC1 && angle.type()==CV_8UC1,
                "collector must receive real frozen gradient maps");
        require(official.size()==(level==0?cv::Size(65,49):cv::Size(32,24)),
                "L1 must use actual floor-half dimensions");
        require(magnitude.size()==official.size(),"gradient and actual mask must agree");
        if (level==1) {
            require(official.at<unsigned char>(1,2)==128,"nearest resize must preserve mask byte128");
            require(official.at<unsigned char>(2,3)==1,"nearest resize must preserve mask byte1");
        }
        auto pool=candidates(2,3);if (level==0)pool.resize(4);
        return collection(official,std::move(pool));
    };
    const auto sample=[&](const std::vector<ss::Candidate>& pool,std::size_t k,ss::Mode mode) {
        const unsigned level=sampled/2,arm=sampled%2;++sampled;
        require(k==(level==0?32U:16U),"requested K must remain frozen per level");
        require(mode==(arm==0?ss::Mode::pooled:ss::Mode::balanced),"arm order must be P then B");
        addresses[level][arm]=&pool;hashes[level][arm]=digest(pool);
        return ss::sample(pool,k,mode);
    };
    const auto hook=[&](std::uint64_t pose,unsigned level,const cc::Result& original,
                        const std::vector<ss::Candidate>& pool,const ss::Result& p,const ss::Result& b) {
        require(pose==37 && level==hooked,"hook must expose stable pose/layer identity");++hooked;
        require(&pool==addresses[level][0] && &pool==addresses[level][1],
                "P/B and serialization hook must share the identical immutable vector");
        require(digest(pool)==hashes[level][0] && hashes[level][0]==hashes[level][1],
                "shared pool digest must remain unchanged across arms and hook");
        require(pool.size()==original.candidates.size(),"hook must retain full accepted pool");
        require(p.status==b.status,"P/B layer success statuses must match");
        require(original.actual_mask.at<unsigned char>(0,0)==7,"hook must see actual nonzero mask bytes");
    };
    ++pose_calls;
    const auto result=it::train_pose_with(src,mask,37,collect,sample,hook);
    require(collected==2 && sampled==4 && hooked==2,"failed L0 must still collect/sample/hook L1");
    check_counts(result);
    require(result.layers[0].pooled.status==ss::Status::insufficient_features &&
            result.layers[1].pooled.status==ss::Status::ok,"both observed layer statuses must survive");
    for (const auto& arm:result.arms) {
        require(!arm.success && arm.cropped.empty(),"failed pose must not produce an injectable template");
        require(arm.uncropped.size()==2 && arm.uncropped[0].features.empty() &&
                arm.uncropped[1].features.size()==6,"uncropped diagnostics must retain successful L1");
        require(arm.uncropped[0].width==-1 && arm.uncropped[0].height==-1 &&
                arm.uncropped[0].tl_x==0 && arm.uncropped[0].tl_y==0,
                "uncropped template metadata must be initialized");
    }
    require(cv::norm(mask,before,cv::NORM_INF)==0,"input official mask changed");
}

// Catches reconstruction that changes labels, theta bits or selected order.
void exact_order_labels_theta_and_pose_crop() {
    auto src=source();cv::Mat mask(src.size(),CV_8U,cv::Scalar(255));
    unsigned calls=0;
    const auto collect=[&](const cv::Mat&,const cv::Mat&,const cv::Mat&,const cv::Mat& actual) {
        const bool first=(calls++==0);
        return collection(actual,candidates(first?5:2,first?7:3));
    };
    const auto sample=[](const std::vector<ss::Candidate>& pool,std::size_t k,ss::Mode mode) {
        return ss::sample(pool,k,mode);
    };
    ++pose_calls;
    const auto result=it::train_pose_with(src,mask,38,collect,sample,it::LayerHook{});
    check_counts(result);
    const std::array<std::array<unsigned,6>,2> ordinals={{{{0,5,3,1,2,4}},{{0,5,2,1,4,3}}}};
    const std::array<std::pair<int,int>,6> xy={{{0,0},{10,0},{0,10},{10,10},{5,5},{20,0}}};
    for (unsigned a=0;a<2;++a) {
        const auto& arm=result.arms[a];
        require(arm.success && arm.cropped.size()==2,"both successful levels must produce one arm pyramid");
        require(arm.crop==cv::Rect(4,6,40,20),"cross-layer pose crop has independent literal bounds");
        for (unsigned level=0;level<2;++level) {
            const auto& before=arm.uncropped[level];const auto& after=arm.cropped[level];
            require(before.width==-1 && before.height==-1 && before.tl_x==0 && before.tl_y==0,
                    "uncropped dimensions/origin must be explicit");
            require(after.width==(level==0?40:20) && after.height==(level==0?20:10) &&
                    after.tl_x==(level==0?4:2) && after.tl_y==(level==0?6:3),
                    "crop dimensions/origin must project common full-resolution bounds");
            require(after.pyramid_level==static_cast<int>(level),"pyramid level changed");
            for (unsigned i=0;i<6;++i) {
                const auto ordinal=ordinals[a][i];const auto& feature=after.features[i];
                require(feature.label==static_cast<int>(ordinal),"template label/order differs from literal");
                require(theta_bits(feature)==(ordinal==0?0x7fc12345U:0x3f800000U+ordinal),
                        "theta payload must survive template conversion and crop");
                require(feature.x==xy[ordinal].first+(level==0?1:0) &&
                        feature.y==xy[ordinal].second+(level==0?1:0),"cropped literal feature coordinates differ");
                require(before.features[i].x==xy[ordinal].first+(level==0?5:2),
                        "cropping must not modify uncropped diagnostic copy");
            }
        }
    }
}

line2Dup::Template templ(int level,std::initializer_list<std::pair<int,int>> points) {
    line2Dup::Template t;t.width=-1;t.height=-1;t.tl_x=0;t.tl_y=0;t.pyramid_level=level;
    for (const auto& point:points) {
        line2Dup::Feature f(point.first,point.second,3);const std::uint32_t theta=0xff800001U;
        std::memcpy(&f.theta,&theta,sizeof(theta));t.features.push_back(f);
    }
    return t;
}
// Catches per-layer crops, missing factor2 projection, or missing even-min adjustment.
void copied_crop_literal_bounds() {
    std::vector<line2Dup::Template> pyramid={templ(0,{{11,9},{23,21}}),templ(1,{{4,3},{15,11}})};
    require(it::crop_templates(pyramid)==cv::Rect(8,6,22,16),"cross-layer literal crop differs");
    require(pyramid[0].width==22 && pyramid[0].height==16 &&
            pyramid[0].tl_x==8 && pyramid[0].tl_y==6,"L0 crop literal metadata differs");
    require(pyramid[1].width==11 && pyramid[1].height==8 &&
            pyramid[1].tl_x==4 && pyramid[1].tl_y==3,"L1 crop literal metadata differs");
    require(pyramid[0].features[0].x==3 && pyramid[0].features[0].y==3 &&
            pyramid[1].features[1].x==11 && pyramid[1].features[1].y==8,"literal crop feature offsets differ");
    require(theta_bits(pyramid[1].features[0])==0xff800001U && pyramid[1].features[0].label==3,
            "crop must preserve opaque theta bits and labels");
    pyramid={templ(0,{{5,7},{13,17}}),templ(1,{{4,5},{12,9}})};
    require(it::crop_templates(pyramid)==cv::Rect(4,6,20,12),"odd minima must round down to even");
}

// Catches partial-pose insertion, sparse IDs, and insertion into original core paths.
void only_successful_two_layers_get_dense_ids() {
    it::SharedDetector detector;
    it::ArmResult failed;
    require(detector.inject("toy",failed)==-1 && detector.numClasses()==0 && detector.numTemplates()==0,
            "failed arm must not create a class or consume a template ID");
    it::ArmResult success;success.success=true;
    success.uncropped={templ(0,{{5,7},{13,17}}),templ(1,{{4,5},{12,9}})};
    success.cropped=success.uncropped;success.crop=it::crop_templates(success.cropped);
    require(detector.inject("toy",success)==0,"first successful bank ID must be zero");
    require(detector.inject("toy",failed)==-1,"failed interleaved arm must remain rejected");
    require(detector.inject("toy",success)==1 && detector.numTemplates("toy")==2,
            "successful IDs must remain dense across failures");
    require(detector.pyramidLevels()==2 && detector.getT(0)==4 && detector.getT(1)==8,
            "injected detector must keep frozen T geometry");
    const auto& saved=detector.getTemplates("toy",1);
    require(saved.size()==2 && theta_bits(saved[1].features[0])==0xff800001U,
            "inject must preserve both layers and in-memory theta bits");
    auto malformed=success;malformed.cropped.pop_back();bool rejected=false;
    try { detector.inject("toy",malformed); } catch (const std::invalid_argument&) { rejected=true; }
    require(rejected && detector.numTemplates("toy")==2,"incomplete success must reject before insertion");
}

// Exercises actual frozen gradient construction and actual collector; no file I/O.
void real_gradient_numeric_mat_toy() {
    cv::Mat src(256,256,CV_8UC3);
    for (int y=0;y<src.rows;++y)for (int x=0;x<src.cols;++x) {
        const auto value=static_cast<unsigned char>(((x/32+y/32)%2)*255);
        src.at<cv::Vec3b>(y,x)=cv::Vec3b(value,value,value);
    }
    cv::Mat mask(src.size(),CV_8U,cv::Scalar(7));unsigned hooks=0;
    const auto hook=[&](std::uint64_t pose,unsigned level,const cc::Result& c,
                        const std::vector<ss::Candidate>& pool,const ss::Result& p,const ss::Result& b) {
        require(pose==39 && level==hooks++,"actual toy hook pose/layer sequence differs");
        require(c.actual_mask.at<unsigned char>(0,0)==7,"actual collector must retain source mask byte");
        std::cout<<"OBS\tactual_gradient_toy\tlevel="<<level<<"\tcandidates="<<pool.size()
                 <<"\tnms_maxima="<<c.nms_maxima<<'\n';
        require(pool.size()==c.candidates.size() && pool.size()>4,"actual gradient toy needs successful full pool");
        require(p.selected.size()==std::min(pool.size(),level==0?std::size_t(32):std::size_t(16)) &&
                p.selected.size()==b.selected.size(),"actual toy must obey exact target for both arms");
    };
    ++pose_calls;
    const auto result=it::train_pose(src,mask,39,hook);
    check_counts(result);
    require(hooks==2 && result.arms[0].success && result.arms[1].success,
            "actual frozen gradient/collector toy must produce both arm pyramids");
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
        {"failed_l0_still_l1_and_shared_pool",failed_l0_still_l1_and_shared_pool},
        {"exact_order_labels_theta_and_pose_crop",exact_order_labels_theta_and_pose_crop},
        {"copied_crop_literal_bounds",copied_crop_literal_bounds},
        {"only_successful_two_layers_get_dense_ids",only_successful_two_layers_get_dense_ids},
        {"real_gradient_numeric_mat_toy",real_gradient_numeric_mat_toy}};
    const std::string only=argc==2?argv[1]:"";int passed=0,failed=0;
    for (const auto& test:tests) {
        if (!only.empty() && only!=test.first)continue;
        try { test.second();++passed;std::cout<<"PASS\t"<<test.first<<'\n'; }
        catch (const std::exception& e) { ++failed;std::cout<<"FAIL\t"<<test.first<<'\t'<<e.what()<<'\n'; }
    }
    if (passed+failed==0) { ++failed;std::cout<<"FAIL\tunknown_test_case\n"; }
    std::cout<<"SUMMARY\tpassed="<<passed<<"\tfailed="<<failed<<"\tassertions="<<assertions
             <<"\tpose_calls="<<pose_calls<<"\timage_decodes=0\tmatcher_calls=0\n";
    try { print_loaded_modules(); } catch (const std::exception& e) { std::cerr<<e.what()<<'\n';return 2; }
    return failed?1:0;
}
