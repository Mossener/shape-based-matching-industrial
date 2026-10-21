#pragma once
#include <chrono>
#include <cstdint>
#include <map>
#include <utility>
#include <string>
#include <vector>

// Throwaway diagnostic data. Worker intervals are elapsed time, not CPU time;
// their sum across OpenMP workers must not be compared directly with call wall time.
namespace search_profile {
using Clock = std::chrono::steady_clock;
inline double elapsedMs(Clock::time_point start) {
    return std::chrono::duration<double, std::milli>(Clock::now()-start).count();
}
struct Level {
    int feature_count=0;
    std::map<std::pair<int,int>,std::uint64_t> centers;
    std::uint64_t candidates_in=0,candidates_out=0,local_calls=0;
    std::uint64_t x_clamped=0,y_clamped=0;
    double similarity_ms=0,argmax_ms=0,filter_ms=0;
};
struct Template {
    std::string class_id;
    int template_id=-1,worker=-1,coarse_level=-1,coarse_feature_count=0;
    std::uint64_t map_positions=0,accumulated_prefix=0,geometrically_valid=0;
    std::uint64_t zero_tail_scanned=0,wrapped_prefix_scanned=0;
    std::uint64_t coarse_candidates=0,zero_tail_candidates=0,wrapped_candidates=0;
    double coarse_similarity_ms=0,coarse_collect_ms=0;
    std::vector<Level> levels;
};
struct Call {
    std::vector<Template> templates;
    std::uint64_t matches_before_sort=0,matches_after_unique=0;
    double final_sort_ms=0,final_unique_ms=0;
};
}
