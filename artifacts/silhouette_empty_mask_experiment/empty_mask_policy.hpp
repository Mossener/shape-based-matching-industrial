#ifndef EMPTY_MASK_POLICY_HPP
#define EMPTY_MASK_POLICY_HPP
#include <opencv2/core.hpp>
#include <string>
namespace empty_mask_experiment {
// Only the selection mask differs from the source-only predecessor. The
// caller supplies the same ownership-separated binary source clone; the
// unchanged official mask remains in the caller's pose/bbox evidence.
template<class Detector>
int add_template(Detector& detector,const cv::Mat& binary_source_clone,const std::string& class_id) {
    return detector.addTemplate(binary_source_clone,class_id,cv::Mat());
}
}
#endif
