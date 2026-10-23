#pragma once

#include "line2Dup.h"
#include <opencv2/imgproc.hpp>

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
// RED-only zero stub until coordinator retains actual assertion RED.
inline Warp rebuild_warp(const cv::Mat&, const cv::Mat&, int, double) { return {}; }

// Complete serialized matching representation; theta was never serialized.
inline bool same_saved_layer(const line2Dup::Template&, const line2Dup::Template&) { return false; }

} // namespace ordered_contour_native::replay
