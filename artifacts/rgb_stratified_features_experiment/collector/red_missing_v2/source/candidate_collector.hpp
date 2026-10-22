#ifndef RGB_STRATIFIED_CANDIDATE_COLLECTOR_HPP
#define RGB_STRATIFIED_CANDIDATE_COLLECTOR_HPP

#include <opencv2/core.hpp>
#include <cstdint>
#include <vector>

namespace rgb_stratified { namespace collector {

struct Candidate {
    std::uint32_t ordinal;
    std::int32_t x;
    std::int32_t y;
    std::uint8_t label;
    std::uint32_t magnitude_bits;
    std::uint32_t theta_bits;
    bool interior;
};

struct Result {
    // Full canvas maps; the scan applies its own two-pixel margin.
    cv::Mat actual_mask;
    cv::Mat domain;
    cv::Mat interior;
    std::vector<Candidate> candidates;
    // Includes low-strength / invalid-angle maxima that suppress neighbors.
    std::uint64_t nms_maxima = 0;
};

// Inputs are already-computed maps for exactly one pose/layer. This function
// neither computes gradients nor samples features. The caller owns invocation
// counters and shares one returned immutable pool between both sampler arms.
// Nonfinite magnitude anywhere is rejected. Theta is copied bit-for-bit.
Result collect(const cv::Mat& magnitude, const cv::Mat& quantized_angle,
               const cv::Mat& angle_ori, const cv::Mat& official_mask);

}}  // namespace rgb_stratified::collector
#endif
