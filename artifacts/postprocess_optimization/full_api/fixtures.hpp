#pragma once
#include "matcher.hpp"
#include "fixture_banks.hpp"
#include <opencv2/imgcodecs.hpp>
#include <opencv2/imgproc.hpp>
#include <array>
#include <iomanip>
#include <memory>
#include <sstream>
#include <stdexcept>
#include <utility>

namespace postprocess_fixtures {
struct Fixture {
    std::string name,id;
    cv::Mat image;
    float threshold;
    std::shared_ptr<postprocess_exact_v11_api::Matcher> baseline;
    std::shared_ptr<postprocess_hash_v11_api::Matcher> candidate;
};
struct Input {std::size_t fixture;cv::Mat mask;float threshold;std::string name;};
inline void require(bool value,const std::string& message) {
    if(!value)throw std::runtime_error(message);
}
inline std::string path(const std::string& root,const std::string& relative) {
    return root+"/"+relative;
}
inline std::vector<std::string> ids(const Fixture& fixture) {
    return fixture.id.empty()?std::vector<std::string>{}:std::vector<std::string>{fixture.id};
}
using MatcherPair=std::pair<std::shared_ptr<postprocess_exact_v11_api::Matcher>,
                            std::shared_ptr<postprocess_hash_v11_api::Matcher>>;
inline MatcherPair matchers(int features,const std::vector<int>& steps,float weak,float strong) {
    return {std::make_shared<postprocess_exact_v11_api::Matcher>(features,steps,weak,strong),
            std::make_shared<postprocess_hash_v11_api::Matcher>(features,steps,weak,strong)};
}
inline void load(const MatcherPair& pair,const std::string& yaml,const std::string& override_id="") {
    pair.first->loadClass(yaml,override_id);pair.second->loadClass(yaml,override_id);
}
inline void loadFile(const MatcherPair& pair,const std::string& file) {
    pair.first->loadClassFile(file);pair.second->loadClassFile(file);
}
inline void count(const MatcherPair& pair,int expected) {
    require(pair.first->templateCount()==expected && pair.second->templateCount()==expected,
            "Fixture template count differs");
}
inline cv::Mat decode(const std::string& file,int mode) {
    const auto image=cv::imread(file,mode);require(!image.empty(),"Cannot decode fixed fixture: "+file);return image;
}
inline cv::Mat paddedCopy(const cv::Mat& image,int top,int bottom,int left,int right) {
    cv::Mat output;
    cv::copyMakeBorder(image,output,top,bottom,left,right,cv::BORDER_CONSTANT,cv::Scalar(0));
    return output;
}
// Only the fixed development scene/frame pairs are ever turned into paths.
// No heldout image or training-image path is constructed or decoded.
inline std::vector<Fixture> fixtures(const std::string& root=".") {
    std::vector<Fixture> result;
    const auto ledBank=postprocess_fixture_banks::led(path(root,"LED/ku.smd"));
    auto led=matchers(128,{4,8,8},20,40);load(led,ledBank.yaml);count(led,900);
    for(int i=1;i<=8;++i) {
        const auto image=decode(path(root,"LED/"+std::to_string(i)+".bmp"),cv::IMREAD_GRAYSCALE);
        cv::Mat padded;cv::copyMakeBorder(image,padded,64,64,64,64,cv::BORDER_CONSTANT,cv::Scalar(0));
        require(padded.rows%32==0 && padded.cols%32==0,"LED alignment changed");
        result.push_back({"LED_"+std::to_string(i),"LED",padded,75,led.first,led.second});
    }
    auto shape=matchers(128,{4,8},30,60);loadFile(shape,path(root,"test/case1/test_templ.yaml"));count(shape,361);
    const auto color=decode(path(root,"test/case1/test.png"),cv::IMREAD_COLOR);
    cv::Mat padded;cv::copyMakeBorder(color,padded,250,250,250,250,cv::BORDER_CONSTANT,cv::Scalar(0));
    padded=padded(cv::Rect(0,0,padded.cols/16*16,padded.rows/16*16)).clone();
    result.push_back({"case1","test",padded,90,shape.first,shape.second});
    auto tiny=matchers(32,{4,8},20,40);
    loadFile(tiny,path(root,"datasets/tless_train_f32/templates_tless_object_1.yml.gz"));count(tiny,2212);
    const std::array<std::pair<int,int>,16> pairs={{{5,7},{5,70},{5,127},{5,215},{5,293},{5,353},{5,436},{5,493},
                                                 {2,3},{2,92},{2,153},{2,214},{2,295},{2,374},{2,446},{2,494}}};
    for(const auto& pair:pairs) {
        std::ostringstream relative;relative<<"datasets/tless_tiny/test_primesense/"<<std::setw(6)<<std::setfill('0')
            <<pair.first<<"/rgb/"<<std::setw(6)<<pair.second<<".png";
        const auto image=decode(path(root,relative.str()),cv::IMREAD_GRAYSCALE);
        const auto tinyPadded=paddedCopy(image,64,64+(16-(image.rows+128)%16)%16,
                                       64,64+(16-(image.cols+128)%16)%16);
        result.push_back({"tiny_s"+std::to_string(pair.first)+"_i"+std::to_string(pair.second),
                          "tless_object_1",tinyPadded,85,tiny.first,tiny.second});
    }
    require(result.size()==25,"Common25 fixture count changed");
    for(std::size_t i=0;i<25;++i)for(std::size_t j=0;j<i;++j)
        require(result[i].image.data!=result[j].image.data,"Common fixture images share a mutable destination allocation");
    auto multi=matchers(128,{4,8,8},20,40);
    for(const std::string id:{"LED_A","LED_B"})load(multi,ledBank.yaml,id);
    count(multi,1800);
    result.push_back({"LED_two_classes","",result[0].image,75,multi.first,multi.second});
    const auto zeroBank=postprocess_fixture_banks::zero();auto zero=matchers(1,{4,8},20,40);
    load(zero,zeroBank.yaml);count(zero,1);
    // Identical legal one-feature/blank-image fixture to the prior contract.
    // This bounds the tested fixture only; it is not general memory-safety proof.
    result.push_back({"synthetic_zero_maxima","zero",cv::Mat(256,256,CV_8UC1,cv::Scalar(0)),
                      -1,zero.first,zero.second});
    require(result.size()==27,"Base correctness fixture count changed");return result;
}
inline std::vector<Input> inputs(std::vector<Fixture>& all) {
    require(all.size()==27,"Build correctness inputs once from the base27 fixtures");
    std::vector<Input> result;
    for(std::size_t i=0;i<all.size();++i)result.push_back({i,{},all[i].threshold,all[i].name});
    cv::Mat zero(all[0].image.size(),CV_8UC1,cv::Scalar(0));
    cv::Mat full(all[0].image.size(),CV_8UC1,cv::Scalar(255));
    auto partial=zero.clone();partial(cv::Rect(100,100,400,300)).setTo(255);
    result.push_back({0,zero,75,"LED_zero_mask"});
    result.push_back({0,full,75,"LED_full_mask"});
    result.push_back({0,partial,75,"LED_partial_mask"});
    result.push_back({0,{},101,"LED_empty_candidates"});
    cv::Mat larger;cv::copyMakeBorder(all[0].image,larger,0,32,0,64,cv::BORDER_CONSTANT,cv::Scalar(0));
    all.push_back({"LED_larger_same_detector","LED",larger,75,all[0].baseline,all[0].candidate});
    result.push_back({27,{},75,"LED_larger_same_detector"});
    require(result.size()==32 && all.size()==28,"Correctness input count changed");return result;
}
inline std::vector<Fixture> magnetFixtures(const std::string& root=".",
        std::vector<postprocess_fixture_banks::Refinement>* preflight=nullptr) {
    // Runner must first verify both original private and existing ASCII copies.
    const std::string ascii="artifacts/magnet_match/build/input";
    const auto bank=postprocess_fixture_banks::magnet(path(root,ascii+"/moban.smd"));
    auto pair=matchers(128,{4,8,8},20,40);load(pair,bank.yaml);count(pair,3060);
    if(preflight)*preflight=bank.refinements;
    std::vector<Fixture> result;
    for(int i=1;i<=7;++i) {
        std::ostringstream name;name<<'M'<<std::setw(2)<<std::setfill('0')<<i;
        const auto image=decode(path(root,ascii+"/"+name.str()+".bmp"),cv::IMREAD_GRAYSCALE);
        require(image.size()==cv::Size(640,480),"Private magnet dimensions changed");
        cv::Mat padded;cv::copyMakeBorder(image,padded,128,bank.padded_height-image.rows-128,
            128,bank.padded_width-image.cols-128,cv::BORDER_CONSTANT,cv::Scalar(0));
        result.push_back({name.str(),"magnet",padded,75,pair.first,pair.second});
    }
    require(result.size()==7,"Private magnet regression scope changed");return result;
}
}
