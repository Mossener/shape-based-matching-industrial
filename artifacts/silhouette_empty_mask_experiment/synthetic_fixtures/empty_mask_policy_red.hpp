// Deliberately wrong source-only mask policy. Native RED compiles this exact
// fixture instead of the implementation; it must fail the empty-mask spy.
#ifndef EMPTY_MASK_POLICY_RED_HPP
#define EMPTY_MASK_POLICY_RED_HPP
#include <opencv2/core.hpp>
#include <string>
namespace empty_mask_experiment {
template<class Detector>
int add_template(Detector& detector,const cv::Mat& binary_source_clone,const std::string& class_id) {
    return detector.addTemplate(binary_source_clone,class_id,binary_source_clone);
}
}
#endif
