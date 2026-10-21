#ifndef SILHOUETTE_SOURCE_HPP
#define SILHOUETTE_SOURCE_HPP
#include <opencv2/core.hpp>
#include <stdexcept>
namespace silhouette_experiment {
inline cv::Mat training_source(const cv::Mat& mask) {
    if(mask.empty() || mask.type()!=CV_8UC1)
        throw std::invalid_argument("Training mask must be nonempty single-channel uint8");
    cv::Mat invalid=(mask!=0)&(mask!=255);
    if(cv::countNonZero(invalid)!=0)
        throw std::invalid_argument("Training mask must contain only binary 0/255");
    return mask.clone();
}
}
#endif
