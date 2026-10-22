#ifndef LINE2DUP_MATCHES_HPP
#define LINE2DUP_MATCHES_HPP
#include <algorithm>
#include <vector>
namespace line2Dup {
namespace detail {
template<class Match>
inline void consolidateMatches(std::vector<Match>& matches) {
    // Group the existing equality key; the smallest template ID represents
    // every identical class/position/score. Scores produced by matching are
    // finite, so direct comparisons preserve their exact float values.
    std::sort(matches.begin(), matches.end(), [](const Match& a, const Match& b) {
        if (a.similarity != b.similarity) return a.similarity > b.similarity;
        if (a.class_id != b.class_id) return a.class_id < b.class_id;
        if (a.y != b.y) return a.y < b.y;
        if (a.x != b.x) return a.x < b.x;
        return a.template_id < b.template_id;
    });
    matches.erase(std::unique(matches.begin(), matches.end()), matches.end());
    // Preserve score/template-ID priority, adding a deterministic spatial and
    // class tie order instead of depending on the OpenMP merge permutation.
    std::sort(matches.begin(), matches.end(), [](const Match& a, const Match& b) {
        if (a.similarity != b.similarity) return a.similarity > b.similarity;
        if (a.template_id != b.template_id) return a.template_id < b.template_id;
        if (a.class_id != b.class_id) return a.class_id < b.class_id;
        if (a.y != b.y) return a.y < b.y;
        return a.x < b.x;
    });
}
}
}
#endif
