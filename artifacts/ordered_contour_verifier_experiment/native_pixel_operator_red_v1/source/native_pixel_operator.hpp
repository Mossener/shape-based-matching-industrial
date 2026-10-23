#pragma once

#include <opencv2/core.hpp>
#include <vector>

namespace ordered_contour_native {
namespace pixel {

using LabelGrid = std::vector<std::vector<int>>;

// Owned full-size matrices. No spread, thinning, sampling or sparse features.
// magnitude_squared and phase_degrees are CV_32FC1; unspread is CV_8UC1.
struct GradientFields {
    cv::Mat unspread;
    cv::Mat magnitude_squared;
    cv::Mat phase_degrees;
};

struct PixelEvidence {
    GradientFields gradient;
    LabelGrid labels;
};

// All matrix inputs must be nonempty two-dimensional matrices of the stated
// type; mask size must match. Invalid input throws std::invalid_argument.
// Noncontinuous views are allowed. native_gradient first owns logical image
// and mask row bytes, so borders belong to the supplied view, not its parent.
// It calls frozen V11 ColorGradientPyramid at weak=20, features=32, strong=40,
// then quantize; optional mask is CV_8UC1 and is never eroded here.
GradientFields native_gradient(const cv::Mat& grayscale,
                               const cv::Mat& mask = cv::Mat());

// Decode every byte before later selection: 0 -> 255 (invalid), 1<<b -> b.
// Every multibit byte is rejected, including pixels a mask would discard.
LabelGrid decode_core_bits(const cv::Mat& unspread);

// Same-size CV_8UC1 bits/full official mask and CV_32FC1 squared magnitude.
// Keep decoded labels only for mask!=0, finite magnitude_squared >1600.
// No mask erosion, local strongest-point selection, or extra border removal.
LabelGrid template_labels(const cv::Mat& unspread,
                          const cv::Mat& magnitude_squared,
                          const cv::Mat& full_mask);

// Full pixel entry points: scene uses only weak20 unspread labels; template
// additionally uses the full official mask and strict finite strong40 gate.
PixelEvidence scene_evidence(const cv::Mat& grayscale);
PixelEvidence template_evidence(const cv::Mat& grayscale,
                                const cv::Mat& full_mask);

} // namespace pixel
} // namespace ordered_contour_native
