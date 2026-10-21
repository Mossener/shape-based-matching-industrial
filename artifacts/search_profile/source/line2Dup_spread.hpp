#ifndef SEARCH_PROFILE_LINE2DUP_SPREAD_HPP
#define SEARCH_PROFILE_LINE2DUP_SPREAD_HPP

#include <opencv2/core.hpp>
#include "mipp.h"

#include <algorithm>
#include <cstdint>

namespace profiledLine2Dup {
namespace detail {

// Conservatively reject shared parent allocations, including overlapping ROIs
// and externally backed Mats. Integer address comparisons avoid comparing
// unrelated C++ pointers relationally.
inline bool spreadStorageOverlaps(const cv::Mat& a, const cv::Mat& b) {
    if (a.empty() || b.empty()) return false;
    const std::uintptr_t a_begin = reinterpret_cast<std::uintptr_t>(a.datastart);
    const std::uintptr_t a_end = reinterpret_cast<std::uintptr_t>(a.dataend);
    const std::uintptr_t b_begin = reinterpret_cast<std::uintptr_t>(b.datastart);
    const std::uintptr_t b_end = reinterpret_cast<std::uintptr_t>(b.dataend);
    return a_begin < b_end && b_begin < a_end;
}

inline void spreadOrRow(const unsigned char* src, unsigned char* dst, int width) {
    const int lanes = mipp::N<std::uint8_t>();
    int x = 0;
    for (; x <= width - lanes; x += lanes) {
        mipp::Reg<std::uint8_t> source, target;
        source.loadu(src + x);
        target.loadu(dst + x);
        source.orb(target).storeu(dst + x);
    }
    for (; x < width; ++x) dst[x] |= src[x];
}

// D[y,x] = OR S[y+dy,x+dx], 0 <= dx,dy < T; samples outside
// the source are zero. Values are direction bitmasks, never grayscale maxima.
// Existing dst/scratch allocations (including non-contiguous ROIs) are reused.
// Neither output may share storage with src or with the other output.
inline void spreadSeparable(const cv::Mat& src, cv::Mat& dst,
                            cv::Mat& scratch, int T) {
    CV_Assert(!src.empty() && src.dims == 2 && src.type() == CV_8UC1 && T > 0);
    CV_Assert(&src != &dst && &src != &scratch && &dst != &scratch);
    dst.create(src.size(), CV_8UC1);
    scratch.create(src.size(), CV_8UC1);
    CV_Assert(!spreadStorageOverlaps(src, dst));
    CV_Assert(!spreadStorageOverlaps(src, scratch));
    CV_Assert(!spreadStorageOverlaps(dst, scratch));

    // The offset-zero term initializes every pixel, including the right edge.
    src.copyTo(scratch);
    const int horizontal = std::min(T, src.cols);
    for (int dx = 1; dx < horizontal; ++dx)
        for (int y = 0; y < src.rows; ++y)
            spreadOrRow(src.ptr<unsigned char>(y) + dx,
                        scratch.ptr<unsigned char>(y), src.cols - dx);

    scratch.copyTo(dst);
    const int vertical = std::min(T, src.rows);
    for (int dy = 1; dy < vertical; ++dy)
        for (int y = 0; y < src.rows - dy; ++y)
            spreadOrRow(scratch.ptr<unsigned char>(y + dy),
                        dst.ptr<unsigned char>(y), src.cols);
}

} // namespace detail
} // namespace profiledLine2Dup

#endif // SEARCH_PROFILE_LINE2DUP_SPREAD_HPP
