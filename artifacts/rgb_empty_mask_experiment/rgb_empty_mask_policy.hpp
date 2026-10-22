#pragma once

#include <opencv2/core.hpp>
#include <stdexcept>
#include <string>

namespace rgb_empty_mask_experiment {

// The experiment has one algorithmic seam: keep the frozen grayscale RGB
// source and ask the unchanged V11 extractor to select features without an
// object mask.  This wrapper deliberately does not clone, convert or crop the
// source; ROI/affine/warp decisions remain in the frozen training loop.
template <typename Detector>
int add_template(Detector& detector, const cv::Mat& warped_gray,
                 const std::string& class_id) {
    if (warped_gray.empty() || warped_gray.type() != CV_8UC1) {
        throw std::invalid_argument("RGB empty-mask source must be nonempty CV_8UC1");
    }
    return detector.addTemplate(warped_gray, class_id, cv::Mat());
}

}  // namespace rgb_empty_mask_experiment
