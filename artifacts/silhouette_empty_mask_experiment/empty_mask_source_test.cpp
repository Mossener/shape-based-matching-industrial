#include "private_v11/line2Dup.h"
#include "silhouette_source.hpp"
#ifdef EMPTY_MASK_POLICY_RED_TEST
#include "synthetic_fixtures/empty_mask_policy_red.hpp"
#else
#include "empty_mask_policy.hpp"
#endif
#include <opencv2/imgproc.hpp>
#include <fstream>
#include <iostream>
#include <limits>
#include <stdexcept>
#include <string>
#ifdef _OPENMP
#include <omp.h>
#endif
static void need(bool value,const char* message){if(!value)throw std::runtime_error(message);}
struct Spy {
    const unsigned char* expectedSource=nullptr;bool sawEmptyMask=false;int calls=0;
    int addTemplate(const cv::Mat& source,const std::string& id,const cv::Mat& selection) {
        ++calls;need(id=="literal-class","Class identity changed");
        need(source.data==expectedSource,"Wrapper replaced source clone");
        need(source.type()==CV_8UC1 && source.rows==192 && source.cols==192,"Wrapper changed source shape/type");
        sawEmptyMask=selection.empty();need(sawEmptyMask,"Feature-selection mask must be empty cv::Mat()");
        return 37;
    }
};
int main(int argc,char** argv) {
    try {
        need(argc==2,"Pass a fresh output file");std::ifstream old(argv[1]);need(!old.good(),"Output must be new");
        cv::setNumThreads(1);
#ifdef _OPENMP
        omp_set_num_threads(4);omp_set_dynamic(0);
#endif
        cv::Mat official(192,192,CV_8U,cv::Scalar(0));cv::rectangle(official,{48,48,96,96},cv::Scalar(255),cv::FILLED);
        const auto original=official.clone();auto source=silhouette_experiment::training_source(official);
        need(source.data!=official.data && cv::countNonZero(source!=official)==0,"Binary source clone ownership/value changed");
        source.at<unsigned char>(48,48)=0;need(official.at<unsigned char>(48,48)==255,"Source mutation changed official mask");
        official.at<unsigned char>(49,49)=0;need(source.at<unsigned char>(49,49)==255,"Official mask mutation changed source");
        source=silhouette_experiment::training_source(original);
        Spy spy;spy.expectedSource=source.data;
        need(empty_mask_experiment::add_template(spy,source,"literal-class")==37 && spy.calls==1 && spy.sawEmptyMask,"Literal call/return policy differs");
        int rejected=0;
        for(int which=0;which<4;++which) {
            cv::Mat bad;
            if(which==1)bad=cv::Mat(16,16,CV_32F,cv::Scalar(255));
            if(which==2)bad=cv::Mat(16,16,CV_8U,cv::Scalar(127));
            if(which==3)bad=cv::Mat(16,16,CV_8UC3,cv::Scalar(255,255,255));
            try{silhouette_experiment::training_source(bad);}catch(const std::invalid_argument&){++rejected;}
        }
        need(rejected==4,"Invalid original mask accepted");
        cv::FileStorage out(argv[1],cv::FileStorage::WRITE|cv::FileStorage::FORMAT_JSON);
        need(out.isOpened(),"Cannot create synthetic evidence");
        out<<"clone_ownership_passed"<<1<<"selection_mask_empty_spy_passed"<<1<<"invalid_masks_rejected"<<rejected<<"toys"<<"[";
        for(int toy=0;toy<2;++toy) {
            cv::Mat binary=original.clone();
            if(toy==1){binary.setTo(0);std::vector<cv::Point> points{{40,130},{64,40},{136,56},{152,128},{104,152}};cv::fillConvexPoly(binary,points,cv::Scalar(255));}
            const auto before=binary.clone();auto cloned=silhouette_experiment::training_source(binary);const auto sourceBefore=cloned.clone();
            line2Dup::Detector detector(32,{4,8},20,40);int id=-1;std::string error;
            try{id=empty_mask_experiment::add_template(detector,cloned,"toy");if(id<0)error="insufficient_features";}
            catch(const cv::Exception& e){error="opencv_exception";std::cerr<<e.what()<<'\n';}
            need(error!="opencv_exception","Native toy extraction threw OpenCV exception");
            need(cv::countNonZero(binary!=before)==0 && cv::countNonZero(cloned!=sourceBefore)==0,"addTemplate mutated original/source pixels");
            out<<"{"<<"toy"<<(toy==0?"rectangle":"diagonal_polygon")<<"template_id"<<id<<"success"<<int(id>=0)<<"error"<<error<<"layers"<<"[";
            if(id>=0)for(const auto& layer:detector.getTemplates("toy",id)) {
                const int side=192>>layer.pyramid_level;int edge=std::numeric_limits<int>::max();
                for(const auto& f:layer.features) {
                    const int x=f.x+layer.tl_x,y=f.y+layer.tl_y;
                    need(x>=0 && x<side && y>=0 && y<side,"Absolute feature outside actual layer canvas");
                    edge=std::min(edge,std::min(std::min(x,y),std::min(side-1-x,side-1-y)));
                }
                out<<"{"<<"level"<<layer.pyramid_level<<"actual_features"<<int(layer.features.size())<<"tl_x"<<layer.tl_x<<"tl_y"<<layer.tl_y<<"minimum_canvas_edge_distance"<<edge<<"}";
            }
            out<<"]"<<"}";
        }
        out<<"]"<<"passed"<<1<<"dataset_image_reads"<<0<<"matcher_calls"<<0<<"synthetic_image_count"<<2;
        out.release();std::cout<<"empty selection-mask spy, ownership and fixed toy extraction passed/recorded\n";return 0;
    }catch(const std::exception& error){std::cerr<<"EMPTY MASK SYNTHETIC FAILED: "<<error.what()<<'\n';return 1;}
}
