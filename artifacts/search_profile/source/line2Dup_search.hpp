#ifndef SEARCH_PROFILE_LINE2DUP_SEARCH_HPP
#define SEARCH_PROFILE_LINE2DUP_SEARCH_HPP

#include <opencv2/core.hpp>

namespace profiledLine2Dup {
namespace detail {

struct LocalMaximum {
    unsigned raw = 0;
    float score = 0;
    int row = -1;
    int col = -1;
};

inline float similarityScore(unsigned raw, int feature_count) {
    CV_Assert(feature_count > 0 && feature_count < 8192);
    // Preserve the original float operations, including threshold rounding.
    return (static_cast<int>(raw) * 100.f) / (4 * feature_count);
}

template<class Pixel>
inline LocalMaximum integerMaximum(const cv::Mat& map, int feature_count) {
    LocalMaximum best;
    for (int row = 0; row < map.rows; ++row) {
        const Pixel* pixels = map.ptr<Pixel>(row);
        for (int col = 0; col < map.cols; ++col) {
            const unsigned raw = pixels[col];
            if (raw > best.raw) { // first row-major winner; zero leaves indices -1
                best.raw = raw;
                best.row = row;
                best.col = col;
            }
        }
    }
    if (best.raw != 0) best.score = similarityScore(best.raw, feature_count);
    return best;
}

inline LocalMaximum localMaximum(const cv::Mat& map, int feature_count) {
    CV_Assert(!map.empty() && map.dims == 2 &&
              (map.type() == CV_8UC1 || map.type() == CV_16UC1));
    CV_Assert(feature_count > 0 && feature_count < 8192);
    return map.type() == CV_8UC1 ? integerMaximum<unsigned char>(map, feature_count)
                                : integerMaximum<unsigned short>(map, feature_count);
}

} // namespace detail
} // namespace profiledLine2Dup
#endif
