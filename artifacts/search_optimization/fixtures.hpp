#pragma once
#define main legacyLedMainForSearchExperiments
#include "../led_match/led_demo.cpp"
#undef main
#include "../../tests/search_reference_matcher.hpp"
#include <array>
#include <memory>
#include <set>
#include <tuple>

namespace search_experiment {
using Semantic=std::tuple<std::string,int,int,float>;
using Strict=std::tuple<std::string,int,int,float,int>;
struct Keys {
    std::set<Semantic> semantic;
    std::set<Strict> strict;
};
template<class Matches> Keys keys(const Matches& matches) {
    Keys result;
    for(const auto& m:matches) {
        result.semantic.emplace(m.class_id,m.x,m.y,m.similarity);
        result.strict.emplace(m.class_id,m.x,m.y,m.similarity,m.template_id);
    }
    return result;
}
struct Fixture {
    std::string name,dataset,class_id;
    cv::Mat image;
    float threshold;
    std::shared_ptr<line2Dup::Detector> detector;
    std::shared_ptr<search_reference::Matcher> reference;
};
inline void exportClass(const line2Dup::Detector& detector,const std::string& id,
                        search_reference::Matcher& reference) {
    cv::FileStorage fs("reference.yml",cv::FileStorage::WRITE|cv::FileStorage::MEMORY);
    detector.writeClass(id,fs);reference.loadClass(fs.releaseAndGetString());
}
inline std::vector<Fixture> loadFixtures() {
    std::vector<Fixture> fixtures;
    auto led=std::make_shared<SmdDetector>("LED/ku.smd",3);
    for(int scale=0;scale<5;++scale) for(int angle=0;angle<360;angle+=2)
        led->addPose(float(angle),0.9f+0.05f*scale);
    auto reference=std::make_shared<search_reference::Matcher>(128,std::vector<int>{4,8,8},20,40);
    exportClass(*led,"LED",*reference);
    CV_Assert(led->numTemplates()==900);
    for(int i=1;i<=8;++i) {
        const auto gray=cv::imread("LED/"+std::to_string(i)+".bmp",cv::IMREAD_GRAYSCALE);
        CV_Assert(!gray.empty());cv::Mat padded;
        cv::copyMakeBorder(gray,padded,64,64,64,64,cv::BORDER_CONSTANT,cv::Scalar(0));
        CV_Assert(padded.rows%32==0&&padded.cols%32==0);
        fixtures.push_back({std::to_string(i)+".bmp","LED","LED",padded,75.f,led,reference});
    }
    auto case1=std::make_shared<line2Dup::Detector>(128,std::vector<int>{4,8},30,60);
    cv::FileStorage fs("test/case1/test_templ.yaml",cv::FileStorage::READ);
    CV_Assert(fs.isOpened());case1->readClass(fs.root());
    auto caseReference=std::make_shared<search_reference::Matcher>(128,std::vector<int>{4,8},30,60);
    exportClass(*case1,"test",*caseReference);
    CV_Assert(case1->numTemplates()==361);
    const auto color=cv::imread("test/case1/test.png",cv::IMREAD_COLOR);
    CV_Assert(!color.empty());cv::Mat padded;
    cv::copyMakeBorder(color,padded,250,250,250,250,cv::BORDER_CONSTANT,cv::Scalar(0));
    padded=padded(cv::Rect(0,0,padded.cols/16*16,padded.rows/16*16)).clone();
    fixtures.push_back({"case1","case1","test",padded,90.f,case1,caseReference});
    return fixtures;
}
inline line2Dup::MatchOptions options(unsigned bits) {
    line2Dup::MatchOptions result;
    result.separable_spread=result.fused_response=result.reuse_buffers=true;
    result.log_timing=false;
    result.integer_local_max=(bits&1)!=0;
    result.direct_8bit_search=(bits&2)!=0;
    result.reuse_search_buffers=(bits&4)!=0;
    // Freeze the historical three-option experiment when later options appear.
    result.fused_local_search=false;
    return result;
}
}
