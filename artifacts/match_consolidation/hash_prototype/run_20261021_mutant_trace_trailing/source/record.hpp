#ifndef HASH_PROTO_RECORD_HPP
#define HASH_PROTO_RECORD_HPP
#include <cstddef>
#include <string>
#include <vector>
namespace hash_proto {
// The complete five-field core Match contract, without its OpenCV dependency.
struct Match {
    int x, y;
    float similarity;
    std::string class_id;
    int template_id;
    bool operator==(const Match& other) const {
        return x==other.x && y==other.y && similarity==other.similarity && class_id==other.class_id;
    }
};
struct Options { bool reserve_input=true; float max_load_factor=1.0f; };
struct Diagnostics {
    std::size_t input_count=0, unique_count=0, bucket_count=0;
    bool zero_score_fallback=false;
};
struct Result { std::vector<Match> matches; Diagnostics diagnostics; };
}
#endif
