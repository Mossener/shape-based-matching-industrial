// Synthetic Mat ownership/input construction only: no decode or Matcher call.
#include "../fixtures.hpp"
#include <iostream>

int main() {
    try {
        using postprocess_fixtures::require;
        std::vector<cv::Mat> old;cv::Mat reused;
        for(int i=0;i<3;++i) {
            const cv::Mat source(16,16,CV_8UC1,cv::Scalar(20+i));
            cv::copyMakeBorder(source,reused,4,4,4,4,cv::BORDER_CONSTANT,cv::Scalar(0));
            old.push_back(reused);
        }
        require(old[0].data==old[1].data && old[0].at<unsigned char>(4,4)==22,
                "Historical reused-destination alias was not reproduced");
        std::vector<cv::Mat> fresh;
        for(int i=0;i<3;++i) {
            const cv::Mat source(16,16,CV_8UC1,cv::Scalar(20+i));
            fresh.push_back(postprocess_fixtures::paddedCopy(source,4,4,4,4));
        }
        for(int i=0;i<3;++i) {
            require(fresh[i].at<unsigned char>(4,4)==20+i && fresh[i].at<unsigned char>(0,0)==0,
                    "Fresh padded destination lost its own input pixels");
            for(int j=0;j<i;++j)require(fresh[i].data!=fresh[j].data,"Fresh padded inputs alias");
        }
        std::vector<postprocess_fixtures::Fixture> fixtures;
        for(int i=0;i<27;++i)fixtures.push_back({"synthetic_"+std::to_string(i),"test",
            cv::Mat(512,672,CV_8UC1,cv::Scalar(i)),75,{},{}});
        const auto original=fixtures[0].image.clone();
        const auto values=postprocess_fixtures::inputs(fixtures);
        require(values.size()==32 && fixtures.size()==28,"Synthetic input matrix cardinality differs");
        require(values[27].name=="LED_zero_mask" && values[28].name=="LED_full_mask" &&
                values[29].name=="LED_partial_mask" && values[30].name=="LED_empty_candidates" &&
                values[31].name=="LED_larger_same_detector","Special input order differs");
        require(cv::countNonZero(values[27].mask)==0 && cv::countNonZero(values[28].mask)==512*672 &&
                cv::countNonZero(values[29].mask)==400*300 && values[30].threshold==101 &&
                values[31].fixture==27 && fixtures[27].image.size()==cv::Size(736,544),
                "Mask/threshold/larger geometry differs");
        require(cv::norm(original,fixtures[0].image,cv::NORM_INF)==0,"Input construction changed the original");
        bool rejected=false;try{postprocess_fixtures::inputs(fixtures);}catch(const std::exception&){rejected=true;}
        require(rejected,"Repeated input construction silently changed fixture scope");
        std::cout<<"PASS fixture ownership, historical alias reproduction, matrix and masks; matcher_calls=0 image_decodes=0\n";
        return 0;
    } catch(const std::exception& error) {
        std::cerr<<"FAIL fixture contract: "<<error.what()<<'\n';return 1;
    }
}
