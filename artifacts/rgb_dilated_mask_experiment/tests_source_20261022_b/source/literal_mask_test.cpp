// Literal synthetic test; no image/bank IO, training loop or matcher calls.
// Expected positions are fixed here before either native implementation runs.
#include "line2Dup.h"
#include <opencv2/imgproc.hpp>
#include <set>
#include <iostream>
#include <stdexcept>
#ifndef EXPECT_DILATION
#define EXPECT_DILATION 1
#endif
using Points=std::set<std::pair<int,int>>;
static void require(bool ok,const char* message){if(!ok)throw std::runtime_error(message);}
static Points points(int x){return {{x,20},{x,26},{x,32},{x,38},{x,44}};}
static void inject(line2Dup::ColorGradientPyramid& p,const Points& fixed){
    p.magnitude=cv::Mat(p.src.size(),CV_32FC1,cv::Scalar(0));
    p.angle=cv::Mat(p.src.size(),CV_8UC1,cv::Scalar(0));
    p.angle_ori=cv::Mat(p.src.size(),CV_32FC1,cv::Scalar(0));
    for(const auto& xy:fixed){p.magnitude.at<float>(xy.second,xy.first)=2500.f;p.angle.at<uchar>(xy.second,xy.first)=1;}
}
static void extractAt(int x,bool empty,bool coarse,bool expected){
    const int side=coarse?128:64;
    cv::Mat src(side,side,CV_8UC1,cv::Scalar(0)),mask;
    if(!empty){mask=cv::Mat(side,side,CV_8UC1,cv::Scalar(0));mask(coarse?cv::Rect(32,32,64,64):cv::Rect(16,16,32,32)).setTo(255);}
    line2Dup::ColorGradientPyramid p(src,mask,20.f,coarse?10:5,40.f);
    if(coarse){p.pyrDown();require(p.src.size()==cv::Size(64,64) && p.num_features==5 && p.pyramid_level==1,"actual coarse sizing changed");
        cv::Mat literal(64,64,CV_8UC1,cv::Scalar(0));literal(cv::Rect(16,16,32,32)).setTo(255);
        require(cv::countNonZero(p.mask!=literal)==0,"mask pyramid is not literal nearest-neighbor rectangle");}
    const auto before=p.mask.clone();const auto fixed=points(x);inject(p,fixed);
    line2Dup::Template t{};const bool actual=p.extractTemplate(t);
    require(actual==expected,"literal morphology acceptance differs");
    if(!p.mask.empty())require(cv::countNonZero(p.mask!=before)==0,"extractTemplate mutated official mask");
    if(expected){Points observed;for(const auto& f:t.features){observed.emplace(f.x,f.y);require(f.label==0 && f.theta==0.f,"orientation changed");}
        require(observed==fixed && t.features.size()==5,"literal feature coordinates/count changed");require(t.pyramid_level==(coarse?1:0),"feature level changed");}
    else require(t.features.empty(),"rejected extraction fabricated features");
}
int main(){try{
    cv::setNumThreads(1);
    // Exactly one layer pixel outside official boundary: treatment yes, control no.
    extractAt(15,false,false,EXPECT_DILATION!=0);
    extractAt(14,false,false,false); // two outside: both reject
    extractAt(20,false,false,true);  // interior: both retain
    extractAt(14,true,false,true);  // empty mask: original unrestricted branch
    extractAt(15,false,true,EXPECT_DILATION!=0); // nearest mask then per-layer op
    extractAt(14,false,true,false);
    // Literal border operator checks complement the byte-exact BORDER_REPLICATE
    // seam; extractor scanning itself intentionally excludes the outer 2 pixels.
    cv::Mat one(1,1,CV_8UC1,cv::Scalar(255)),d,e;
    cv::dilate(one,d,cv::Mat(),cv::Point(-1,-1),1,cv::BORDER_REPLICATE);
    cv::erode(one,e,cv::Mat(),cv::Point(-1,-1),1,cv::BORDER_REPLICATE);
    require(d.at<uchar>(0,0)==255 && e.at<uchar>(0,0)==255,"replicated full mask border changed");
    std::cout<<"PASS literal mask tests expected_dilation="<<EXPECT_DILATION<<" native_matcher_calls=0 dataset_decodes=0\n";return 0;
}catch(const std::exception& e){std::cerr<<"FAIL "<<e.what()<<'\n';return 1;}}
