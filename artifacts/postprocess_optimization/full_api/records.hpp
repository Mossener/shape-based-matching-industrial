#pragma once
#include <cstdint>
#include <string>
#include <vector>

namespace postprocess_api {
struct Record {
    std::int32_t x,y,template_id;
    std::uint32_t score_bits;
    std::string class_id;
};
inline bool operator==(const Record& a,const Record& b) {
    return a.x==b.x && a.y==b.y && a.template_id==b.template_id &&
           a.score_bits==b.score_bits && a.class_id==b.class_id;
}
using Records=std::vector<Record>;
struct Timings {
    double pyramid_ms=0,gradient_ms=0,spread_ms=0,response_ms=0,linearize_ms=0;
    double preprocess_ms=0,search_ms=0,total_ms=0;
};
struct CallResult {
    Records records;
    Timings internal;
    double api_wall_ms=0;
    bool has_internal_timing=false;
};
}
