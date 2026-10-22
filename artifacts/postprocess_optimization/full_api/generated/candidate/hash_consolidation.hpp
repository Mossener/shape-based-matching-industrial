#ifndef POSTPROCESS_HASH_CONSOLIDATION_HPP
#define POSTPROCESS_HASH_CONSOLIDATION_HPP
#include "line2Dup_matches.hpp"
#include <algorithm>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <functional>
#include <limits>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <vector>

// Isolated candidate A. This header is not included by production sources.
// Prepared after actual_match_contract.cpp; native RED/GREEN review is pending.
namespace postprocess_hash {
static_assert(sizeof(float)==sizeof(std::uint32_t) && std::numeric_limits<float>::is_iec559,
              "Consolidation requires IEEE binary32 scores");
struct DefaultHash {
    static std::size_t mix(std::size_t seed,std::size_t value) {
        return seed^(value+std::size_t(0x9e3779b9u)+(seed<<6)+(seed>>2));
    }
    std::size_t operator()(const std::string& name,int x,int y,float score) const {
        std::uint32_t score_bits=0;
        if(score!=0.0f)std::memcpy(&score_bits,&score,sizeof(score_bits));
        auto value=std::hash<std::string>{}(name);
        value=mix(value,std::hash<int>{}(x));
        value=mix(value,std::hash<int>{}(y));
        return mix(value,std::hash<std::uint32_t>{}(score_bits));
    }
};
namespace detail {
template<class Match,class FieldHasher> struct IndexHash {
    const std::vector<Match>* input;
    FieldHasher fields;
    std::size_t operator()(std::size_t index) const {
        const auto& item=(*input)[index];
        return fields(item.class_id,item.x,item.y,item.similarity);
    }
};
template<class Match> struct IndexEqual {
    const std::vector<Match>* input;
    bool operator()(std::size_t a,std::size_t b) const {
        return (*input)[a]==(*input)[b];
    }
};
template<class Match> bool finalLess(const Match& a,const Match& b) {
    if(a.similarity!=b.similarity)return a.similarity>b.similarity;
    if(a.template_id!=b.template_id)return a.template_id<b.template_id;
    if(a.class_id!=b.class_id)return a.class_id<b.class_id;
    if(a.y!=b.y)return a.y<b.y;
    return a.x<b.x;
}
}

template<class Match,class FieldHasher=DefaultHash>
inline void consolidateMatches(std::vector<Match>& input,FieldHasher hasher={}) {
    bool has_zero=false;
    for(const auto& item:input) {
        if(!std::isfinite(item.similarity))
            throw std::invalid_argument("Consolidation requires finite scores");
        has_zero=has_zero || item.similarity==0.0f;
    }
    if(has_zero) {
        // An equal minimum-template-ID +/-0 group has V11-specific surviving
        // bits. Run the unchanged whole-vector path before any hashing.
        line2Dup::detail::consolidateMatches(input);
        return;
    }
    std::vector<Match> output;
    {
        // Neither input records nor key indices may change while a functor
        // references them. Only the mapped representative index is updated.
        using Hash=detail::IndexHash<Match,FieldHasher>;
        using Equal=detail::IndexEqual<Match>;
        std::unordered_map<std::size_t,std::size_t,Hash,Equal> groups(
            0,Hash{&input,hasher},Equal{&input});
        groups.max_load_factor(1.0f);
        groups.reserve(input.size());
        for(std::size_t i=0;i<input.size();++i) {
            const auto found=groups.find(i);
            if(found==groups.end())groups.emplace(i,i);
            else if(input[i].template_id<input[found->second].template_id)found->second=i;
        }
        output.reserve(groups.size());
        for(const auto& group:groups)output.push_back(input[group.second]);
    } // Destroy all index functors and map allocations before output sorting.
    std::sort(output.begin(),output.end(),detail::finalLess<Match>);
    input.swap(output);
    // output owns the old full input. Its destruction is part of this call,
    // before Detector::match stamps search_ms and total_ms at the call seam.
}
}
#endif
