#pragma once
#include <opencv2/core.hpp>
#include <stdexcept>
#include <string>

namespace rgb_dilated_mask_experiment {
// Preserve the control's exact RGB source and official-mask interface.
// Morphology belongs only to the private core's one-line transformation.
template <typename Detector>
int add_template(Detector& detector, const cv::Mat& warped_gray,
                 const std::string& class_id, const cv::Mat& warped_official_mask) {
    if (warped_gray.empty() || warped_gray.type() != CV_8UC1 ||
        warped_official_mask.empty() || warped_official_mask.type() != CV_8UC1 ||
        warped_gray.size() != warped_official_mask.size()) {
        throw std::invalid_argument("Expected same-size nonempty grayscale RGB and official mask");
    }
    return detector.addTemplate(warped_gray, class_id, warped_official_mask);
}
}
