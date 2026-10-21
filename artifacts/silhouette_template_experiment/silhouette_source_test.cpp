#include "private_v11/line2Dup.h"
#include "silhouette_source.hpp"
#include <opencv2/imgproc.hpp>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <string>
#ifdef _OPENMP
#include <omp.h>
#endif
static void need(bool value,const char* message){if(!value)throw std::runtime_error(message);}
int main(int argc,char** argv) {
    try {
        need(argc==2,"Pass a fresh output file");
        std::ifstream previous(argv[1]);need(!previous.good(),"Output must be new");
        cv::setNumThreads(1);
#ifdef _OPENMP
        omp_set_num_threads(4);omp_set_dynamic(0);
#endif
        cv::Mat mask(192,192,CV_8U,cv::Scalar(0));
        cv::rectangle(mask,{48,48,96,96},cv::Scalar(255),cv::FILLED);
        const auto original=mask.clone();auto source=silhouette_experiment::training_source(mask);
        need(source.type()==CV_8U && source.size()==mask.size(),"Source type/size changed");
        need(source.data!=mask.data && cv::countNonZero(source!=mask)==0,"Training source must clone binary mask");
        source.at<unsigned char>(48,48)=0;
        need(mask.at<unsigned char>(48,48)==255,"Source mutation changed mask");
        mask.at<unsigned char>(49,49)=0;
        need(source.at<unsigned char>(49,49)==255,"Mask mutation changed source");
        int rejected=0;
        for(int which=0;which<4;++which) {
            cv::Mat bad;
            if(which==1)bad=cv::Mat(32,32,CV_32F,cv::Scalar(255));
            if(which==2)bad=cv::Mat(32,32,CV_8U,cv::Scalar(127));
            if(which==3)bad=cv::Mat(32,32,CV_8UC3,cv::Scalar(255,255,255));
            try{silhouette_experiment::training_source(bad);}
            catch(const std::invalid_argument&){++rejected;}
        }
        need(rejected==4,"Invalid source mask must be rejected");
        cv::FileStorage out(argv[1],cv::FileStorage::WRITE|cv::FileStorage::FORMAT_JSON);
        out<<"clone_ownership_passed"<<1<<"invalid_masks_rejected"<<rejected<<"toys"<<"[";
        for(int toy=0;toy<2;++toy) {
            cv::Mat binary=original.clone();
            if(toy==1){binary.setTo(0);std::vector<cv::Point> points{{40,130},{64,40},{136,56},{152,128},{104,152}};cv::fillConvexPoly(binary,points,cv::Scalar(255));}
            line2Dup::Detector detector(32,{4,8},20,40);
            auto training=silhouette_experiment::training_source(binary);
            const auto maskBefore=binary.clone();int id=-1;std::string error;
            try{id=detector.addTemplate(training,"toy",binary);if(id<0)error="insufficient_features";}
            catch(const cv::Exception& e){error="opencv_exception";std::cerr<<e.what()<<'\n';}
            need(cv::countNonZero(maskBefore!=binary)==0,"addTemplate changed original object mask");
            out<<"{"<<"toy"<<(toy==0?"rectangle":"diagonal_polygon")<<"success"<<int(id>=0)<<"template_id"<<id<<"error"<<error<<"actual_features"<<"[";
            if(id>=0)for(const auto& layer:detector.getTemplates("toy",id))out<<int(layer.features.size());
            out<<"]"<<"}";
        }
        out<<"]"<<"passed"<<1<<"dataset_image_reads"<<0<<"matcher_calls"<<0<<"synthetic_image_count"<<2;
        std::cout<<"source policy and fixed toy extraction recorded\n";
        return 0;
    }catch(const std::exception& e){std::cerr<<"SILHOUETTE SOURCE TEST FAILED: "<<e.what()<<'\n';return 1;}
}
