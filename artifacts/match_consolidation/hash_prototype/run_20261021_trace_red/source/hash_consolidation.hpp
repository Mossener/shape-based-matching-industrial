#ifndef HASH_PROTO_CONSOLIDATION_HPP
#define HASH_PROTO_CONSOLIDATION_HPP
#include "record.hpp"
#include <cstddef>
namespace hash_proto {
struct DefaultHash {
    std::size_t operator()(const std::string&,int,int,float) const { return 0; }
};
inline Result v11_sort_unique(const std::vector<Match>& input) {
    return {input,{input.size(),input.size(),0,false}};
}
template<class FieldHasher=DefaultHash>
Result owning_hash(const std::vector<Match>& input,FieldHasher={},Options={}) {
    return {input,{input.size(),input.size(),0,false}};
}
template<class FieldHasher=DefaultHash>
Result index_hash(const std::vector<Match>& input,FieldHasher={},Options={}) {
    return {input,{input.size(),input.size(),0,false}};
}
}
#endif
