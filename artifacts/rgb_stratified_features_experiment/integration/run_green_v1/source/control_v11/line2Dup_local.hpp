#ifndef LINE2DUP_LOCAL_HPP
#define LINE2DUP_LOCAL_HPP

#include "line2Dup_search.hpp"
#include "mipp.h"
#include <cstddef>

namespace line2Dup {
namespace detail {

// Each stream addresses one valid feature at the patch's top-left position.
// The caller guarantees all 16 columns of all 16 rows are readable. Skipped
// features do not enter streams, but remain in the score denominator.
inline LocalMaximum localMaximum16x16(const unsigned char* const* streams,
                                     std::size_t valid_count,
                                     std::ptrdiff_t row_stride, int total_features) {
    CV_Assert(total_features > 0 && total_features < 8192);
    CV_Assert(valid_count <= static_cast<std::size_t>(total_features) && row_stride > 0);
    CV_Assert(valid_count == 0 || streams != nullptr);
    LocalMaximum best;
    if (valid_count == 0) return best;
    for (int row = 0; row < 16; ++row) {
        unsigned short values[16];
#if defined(MIPP_SSE)
        const __m128i zero = _mm_setzero_si128();
        __m128i low = zero, high = zero;
        if (total_features < 64) {
            for (std::size_t i = 0; i < valid_count; ++i) {
                const __m128i response = _mm_loadu_si128(
                    reinterpret_cast<const __m128i*>(streams[i] + row * row_stride));
                low = _mm_add_epi8(low, response);
            }
            high = _mm_unpackhi_epi8(low, zero);
            low = _mm_unpacklo_epi8(low, zero);
        } else {
            for (std::size_t i = 0; i < valid_count; ++i) {
                const __m128i response = _mm_loadu_si128(
                    reinterpret_cast<const __m128i*>(streams[i] + row * row_stride));
                low = _mm_add_epi16(low, _mm_unpacklo_epi8(response, zero));
                high = _mm_add_epi16(high, _mm_unpackhi_epi8(response, zero));
            }
        }
        _mm_storeu_si128(reinterpret_cast<__m128i*>(values), low);
        _mm_storeu_si128(reinterpret_cast<__m128i*>(values + 8), high);
#else
        // Portable oracle/fallback; production dispatch retains the existing
        // kernel on instruction sets that have not validated this optimization.
        for (int col = 0; col < 16; ++col) {
            unsigned sum = 0;
            for (std::size_t i = 0; i < valid_count; ++i)
                sum += streams[i][row * row_stride + col];
            values[col] = static_cast<unsigned short>(sum);
        }
#endif
        for (int col = 0; col < 16; ++col) {
            if (values[col] > best.raw) {
                best.raw = values[col]; best.row = row; best.col = col;
            }
        }
    }
    if (best.raw != 0) best.score = similarityScore(best.raw, total_features);
    return best;
}

} // namespace detail
} // namespace line2Dup
#endif
