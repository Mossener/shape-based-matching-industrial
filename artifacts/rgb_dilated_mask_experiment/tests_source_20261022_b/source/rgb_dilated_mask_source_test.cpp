#include "rgb_dilated_mask_policy.hpp"
#include <iostream>
struct SpyDetector {
    const cv::Mat* source=nullptr;
    const cv::Mat* mask=nullptr;
    int calls=0;
    int addTemplate(const cv::Mat& src,const std::string& cls,const cv::Mat& official) {
        if(cls!="toy")throw std::runtime_error("class changed");
        source=&src;mask=&official;++calls;return 17;
    }
};
static void require(bool ok,const char* message){if(!ok)throw std::runtime_error(message);}
int main(){
    cv::Mat gray(17,23,CV_8UC1,cv::Scalar(42)),mask(17,23,CV_8UC1,cv::Scalar(255));
    SpyDetector spy;
    int id=rgb_dilated_mask_experiment::add_template(spy,gray,"toy",mask);
    require(id == 17,"return ID changed");require(spy.calls == 1,"call count changed");
    require(spy.source == &gray,"RGB source was replaced");require(spy.mask == &mask,"official mask was replaced");
    bool rejected_size=false,rejected_empty=false,rejected_color=false;
    try{cv::Mat bad(3,3,CV_8UC1);rgb_dilated_mask_experiment::add_template(spy,gray,"toy",bad);}catch(const std::invalid_argument&){rejected_size=true;}
    try{cv::Mat bad;rgb_dilated_mask_experiment::add_template(spy,gray,"toy",bad);}catch(const std::invalid_argument&){rejected_empty=true;}
    try{cv::Mat bad(17,23,CV_8UC3);rgb_dilated_mask_experiment::add_template(spy,bad,"toy",mask);}catch(const std::invalid_argument&){rejected_color=true;}
    require(rejected_size && rejected_empty && rejected_color,"invalid source/mask accepted");
    require(spy.calls == 1,"rejected arguments reached detector");
    std::cout<<"PASS same RGB and official mask pointers; calls="<<spy.calls<<"\n";
}
