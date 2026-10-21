#ifndef SEARCH_PROFILE_LINE2DUP_RESPONSE_HPP
#define SEARCH_PROFILE_LINE2DUP_RESPONSE_HPP

#include <opencv2/core.hpp>
#include <algorithm>
#include <array>
#include <limits>
#include <vector>

namespace profiledLine2Dup {
namespace detail {

// Fuse orientation response lookup and the TxT linear-memory permutation.
// Owns a small immutable table; frame-dependent storage belongs to memories.
class ResponseLUT {
public:
    explicit ResponseLUT(const unsigned char* originalLut256) {
        CV_Assert(originalLut256 != nullptr);
        for (int mask = 0; mask < 256; ++mask)
            for (int ori = 0; ori < 8; ++ori)
                lookup_[mask][ori] = std::max(originalLut256[32*ori+(mask&15)],
                    originalLut256[32*ori+16+(mask>>4)]);
    }

    void linearize(const cv::Mat& spread, std::vector<cv::Mat>& memories, int T) const {
        CV_Assert(spread.dims == 2 && !spread.empty() && spread.type() == CV_8UC1);
        CV_Assert(T > 0 && spread.rows % T == 0 && spread.cols % T == 0);
        const size_t memoryRows = size_t(T)*size_t(T);
        const size_t memoryCols = size_t(spread.rows/T)*size_t(spread.cols/T);
        CV_Assert(memoryRows <= size_t(std::numeric_limits<int>::max()) &&
                  memoryCols <= size_t(std::numeric_limits<int>::max()));
        memories.resize(8);
        for (auto& memory : memories)
            memory.create(int(memoryRows), int(memoryCols), CV_8UC1);

        // A destination row is contiguous: retain eight output pointers while
        // gathering its source phase. Each source byte is loaded exactly once.
        int row = 0;
        for (int sy = 0; sy < T; ++sy)
            for (int sx = 0; sx < T; ++sx, ++row) {
                std::array<unsigned char*,8> out;
                for (int ori = 0; ori < 8; ++ori)
                    out[ori] = memories[ori].ptr<unsigned char>(row);
                for (int y = sy; y < spread.rows; y += T) {
                    const unsigned char* src = spread.ptr<unsigned char>(y);
                    for (int x = sx; x < spread.cols; x += T) {
                        const auto& response = lookup_[src[x]];
                        for (int ori = 0; ori < 8; ++ori) *out[ori]++ = response[ori];
                    }
                }
            }
    }

private:
    std::array<std::array<unsigned char,8>,256> lookup_;
};

} // namespace detail
} // namespace profiledLine2Dup

#endif
