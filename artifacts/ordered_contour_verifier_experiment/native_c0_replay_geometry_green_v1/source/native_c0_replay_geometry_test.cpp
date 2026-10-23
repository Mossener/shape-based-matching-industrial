#include "native_c0_replay_geometry.hpp"
#include <cmath>
#include <exception>
#include <functional>
#include <iostream>
#include <stdexcept>
#include <string>
#include <utility>

namespace r=ordered_contour_native::replay;
namespace {
struct Harness {
    int tests=0,checks=0,failures=0,errors=0;
    std::string current;
    void check(bool ok,const char* text){++checks;if(!ok){++failures;std::cerr<<"FAIL "<<current<<": "<<text<<'\n';}}
    void run(const char* name,const std::function<void()>& body){++tests;current=name;try{body();}catch(const std::exception& e){++errors;std::cerr<<"ERROR "<<name<<": "<<e.what()<<'\n';}}
    void invalid(const std::function<void()>& body){bool caught=false;try{body();}catch(const std::invalid_argument&){caught=true;}check(caught,"reject invalid input");}
};
cv::Mat image(){cv::Mat out(11,15,CV_8UC1,cv::Scalar(0));for(int y=0;y<11;++y)for(int x=0;x<15;++x)out.at<unsigned char>(y,x)=static_cast<unsigned char>(10*y+x);return out;}
cv::Mat mask(){cv::Mat out(11,15,CV_8UC1,cv::Scalar(0));out(cv::Rect(2,1,9,7)).setTo(1);return out;}
bool shape(const cv::Mat& m,int side,int type){return m.dims==2&&m.rows==side&&m.cols==side&&m.type()==type;}
}
int main(){Harness h;
    h.run("nonzero_fullmask_bbox_and_hypot_ceil_border16_align16",[&]{
        for(const auto pair:{std::pair<double,int>{.75,48},{1,48},{1.5,64},{2,64}}){const auto value=r::rebuild_warp(image(),mask(),0,pair.first);h.check(value.crop==cv::Rect(2,1,9,7),"fullmask asymmetric crop");h.check(shape(value.image,pair.second,CV_8UC1),"literal aligned image canvas");h.check(shape(value.mask,pair.second,CV_8UC1),"literal aligned mask canvas");}
    });
    h.run("zero_angle_odd_crop_center_affine_and_linear_constant0_pixels",[&]{
        const auto value=r::rebuild_warp(image(),mask(),0,1);
        const bool a=value.affine.rows==2&&value.affine.cols==3&&value.affine.type()==CV_64FC1;h.check(a,"double 2x3 affine");
        if(a){const double expected[]={1,0,19.5,0,1,20.5};for(int i=0;i<6;++i)h.check(value.affine.at<double>(i/3,i%3)==expected[i],"literal six double affine values");}
        if(shape(value.image,48,CV_8UC1)){h.check(value.image.at<unsigned char>(21,19)==9,"bilinear at crop upper-left half pixel includes constant zero");h.check(value.image.at<unsigned char>(22,21)==29,"bilinear interior logical crop pixel");h.check(value.image.at<unsigned char>(0,0)==0,"constant0 outer canvas");}
        if(shape(value.mask,48,CV_8UC1)){h.check(value.mask.at<unsigned char>(21,20)==1,"nearest mask is not image interpolation");h.check(value.mask.at<unsigned char>(0,0)==0,"constant0 mask canvas");}
    });
    h.run("ninety_degree_float_center_double_affine_geometry",[&]{
        const auto value=r::rebuild_warp(image(),mask(),90,1);const bool a=value.affine.rows==2&&value.affine.cols==3&&value.affine.type()==CV_64FC1;h.check(a,"double 2x3 affine");
        if(a){const double expected[]={0,1,20.5,-1,0,28.5};for(int i=0;i<6;++i)h.check(std::abs(value.affine.at<double>(i/3,i%3)-expected[i])<1e-12,"literal rotation matrix within roundoff");}
    });
    h.run("strided_parent_poison_roi_replays_only_logical_crop",[&]{
        cv::Mat ip(15,21,CV_8UC1,cv::Scalar(255)),mp(15,21,CV_8UC1,cv::Scalar(255));cv::Mat i=ip(cv::Rect(3,2,15,11)),m=mp(cv::Rect(3,2,15,11));image().copyTo(i);mask().copyTo(m);
        const auto a=r::rebuild_warp(i,m,0,1),b=r::rebuild_warp(i.clone(),m.clone(),0,1);h.check(!i.isContinuous()&&!m.isContinuous(),"strided fixtures");h.check(shape(a.image,48,CV_8UC1)&&shape(b.image,48,CV_8UC1),"complete output shape");
        h.check(shape(a.mask,48,CV_8UC1)&&shape(b.mask,48,CV_8UC1),"complete mask shape");
        if(shape(a.image,48,CV_8UC1)&&shape(b.image,48,CV_8UC1)&&shape(a.mask,48,CV_8UC1)&&shape(b.mask,48,CV_8UC1))for(int y=0;y<48;++y)for(int x=0;x<48;++x){h.check(a.image.at<unsigned char>(y,x)==b.image.at<unsigned char>(y,x),"each logical warp image byte");h.check(a.mask.at<unsigned char>(y,x)==b.mask.at<unsigned char>(y,x),"each logical warp mask byte");}
    });
    h.run("warp_rejects_empty_wrong_type_size_empty_mask_and_pose",[&]{
        h.invalid([&]{(void)r::rebuild_warp(cv::Mat(),mask(),0,1);});h.invalid([&]{(void)r::rebuild_warp(image(),cv::Mat(11,15,CV_8UC1,cv::Scalar(0)),0,1);});h.invalid([&]{(void)r::rebuild_warp(cv::Mat(11,15,CV_8UC3),mask(),0,1);});h.invalid([&]{(void)r::rebuild_warp(image(),cv::Mat(15,11,CV_8UC1),0,1);});h.invalid([&]{(void)r::rebuild_warp(image(),mask(),15,1);});h.invalid([&]{(void)r::rebuild_warp(image(),mask(),360,1);});h.invalid([&]{(void)r::rebuild_warp(image(),mask(),0,1.25);});
    });
    h.run("saved_layer_equal_excludes_only_unsaved_theta",[&]{
        line2Dup::Template a;a.width=11;a.height=9;a.tl_x=-2;a.tl_y=4;a.pyramid_level=1;a.features={{1,2,3},{4,5,6}};for(auto& f:a.features)f.theta=0;line2Dup::Template b=a;a.features[0].theta=7;b.features[0].theta=99;h.check(r::same_saved_layer(a,b),"theta is not a matching serialized field");
    });
    h.run("saved_layer_compares_each_scalar_and_ordered_xyz_feature",[&]{
        line2Dup::Template a;a.width=11;a.height=9;a.tl_x=-2;a.tl_y=4;a.pyramid_level=1;a.features={{1,2,3},{4,5,6}};for(auto& f:a.features)f.theta=0;
        for(int field=0;field<10;++field){auto b=a;switch(field){case 0:++b.width;break;case 1:++b.height;break;case 2:++b.tl_x;break;case 3:++b.tl_y;break;case 4:++b.pyramid_level;break;case 5:b.features.pop_back();break;case 6:++b.features[0].x;break;case 7:++b.features[0].y;break;case 8:++b.features[0].label;break;case 9:std::swap(b.features[0],b.features[1]);break;}h.check(!r::same_saved_layer(a,b),"each saved field/order mutation rejected");}
    });
    std::cout<<"NATIVE_C0_REPLAY_GEOMETRY_TEST_SUMMARY tests="<<h.tests<<" checks="<<h.checks<<" failures="<<h.failures<<" errors="<<h.errors<<'\n';return h.failures==0&&h.errors==0?0:1;
}
