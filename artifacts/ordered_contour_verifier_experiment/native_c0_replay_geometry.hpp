#pragma once

#include "line2Dup.h"
#include <opencv2/imgproc.hpp>
#include <cmath>
#include <limits>
#include <stdexcept>

namespace ordered_contour_native::replay {

struct Warp {
    cv::Rect crop;
    cv::Mat image;
    cv::Mat mask;
    cv::Mat affine;
};

// Exact public C0 train geometry, fixed border16 and align16. Inputs are
// nonempty matching 2D CV_8UC1 matrices; angle=0..330 step30 and scales
// .75/1/1.5/2 only. Full nonzero official mask defines crop. No file I/O.
inline Warp rebuild_warp(const cv::Mat& image, const cv::Mat& mask, int angle, double scale) {
    if (image.empty() || image.dims != 2 || image.type() != CV_8UC1 ||
        mask.empty() || mask.dims != 2 || mask.type() != CV_8UC1 || image.size() != mask.size() ||
        angle < 0 || angle >= 360 || angle % 30 != 0 ||
        !(scale == .75 || scale == 1.0 || scale == 1.5 || scale == 2.0))
        throw std::invalid_argument("Expected fixed C0 grayscale/fullmask/pose");
    std::vector<cv::Point> points;
    cv::findNonZero(mask, points);
    if (points.empty()) throw std::invalid_argument("Full official mask is empty");
    Warp result;
    result.crop = cv::boundingRect(points);
    const auto& roi = result.crop;
    const double extent = std::ceil(std::hypot(roi.width, roi.height) * scale);
    if (!std::isfinite(extent) || extent > std::numeric_limits<int>::max() - 47)
        throw std::overflow_error("C0 canvas extent overflow");
    int side = static_cast<int>(extent) + 32;
    side = (side + 15) / 16 * 16;
    result.affine = cv::getRotationMatrix2D({roi.width/2.f, roi.height/2.f}, angle, scale);
    result.affine.at<double>(0,2) += side/2.0 - roi.width/2.0;
    result.affine.at<double>(1,2) += side/2.0 - roi.height/2.0;
    cv::warpAffine(image(roi), result.image, result.affine, {side,side},
                   cv::INTER_LINEAR, cv::BORDER_CONSTANT, cv::Scalar(0));
    cv::warpAffine(mask(roi), result.mask, result.affine, {side,side},
                   cv::INTER_NEAREST, cv::BORDER_CONSTANT, cv::Scalar(0));
    return result;
}

// Complete serialized matching representation; theta was never serialized.
inline bool same_saved_layer(const line2Dup::Template& a, const line2Dup::Template& b) {
    if (a.width != b.width || a.height != b.height || a.tl_x != b.tl_x || a.tl_y != b.tl_y ||
        a.pyramid_level != b.pyramid_level || a.features.size() != b.features.size()) return false;
    for (std::size_t index = 0; index < a.features.size(); ++index)
        if (a.features[index].x != b.features[index].x || a.features[index].y != b.features[index].y ||
            a.features[index].label != b.features[index].label) return false;
    return true;
}

} // namespace ordered_contour_native::replay
