#ifndef HASH_PROTO_CONSOLIDATION_HPP
#define HASH_PROTO_CONSOLIDATION_HPP
#include "record.hpp"
#include "line2Dup_matches.hpp"
#include <algorithm>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <functional>
#include <limits>
#include <stdexcept>
#include <unordered_map>
#include <utility>
namespace hash_proto {
static_assert(sizeof(float)==sizeof(std::uint32_t) && std::numeric_limits<float>::is_iec559,"Prototype requires binary32 float");
struct DefaultHash {
    static std::size_t mix(std::size_t seed,std::size_t value){return seed^(value+std::size_t(0x9e3779b9u)+(seed<<6)+(seed>>2));}
    std::size_t operator()(const std::string& name,int x,int y,float score) const {
        std::uint32_t b=0;
        if(score!=0.0f)std::memcpy(&b,&score,sizeof(b));
        auto value=std::hash<std::string>{}(name);
        value=mix(value,std::hash<int>{}(x));value=mix(value,std::hash<int>{}(y));
        return mix(value,std::hash<std::uint32_t>{}(b));
    }
};
namespace detail {
inline bool validate_scores(const std::vector<Match>& input){
    bool has_zero=false;
    for(const auto& d:input){
        if(!std::isfinite(d.similarity))throw std::invalid_argument("Consolidation requires finite scores");
        has_zero=has_zero || d.similarity==0.0f;
    }return has_zero;
}
inline void validate_options(const Options& options){
    if(!(options.max_load_factor>0) || !std::isfinite(options.max_load_factor))throw std::invalid_argument("Positive finite map load factor required");
}
inline bool final_less(const Match& a,const Match& b){
    if(a.similarity!=b.similarity)return a.similarity>b.similarity;
    if(a.template_id!=b.template_id)return a.template_id<b.template_id;
    if(a.class_id!=b.class_id)return a.class_id<b.class_id;
    if(a.y!=b.y)return a.y<b.y;
    return a.x<b.x;
}
struct OwningKey { std::string class_id;int x,y;float similarity; };
struct OwningEqual {
    bool operator()(const OwningKey& a,const OwningKey& b) const {
        return a.class_id==b.class_id && a.x==b.x && a.y==b.y && a.similarity==b.similarity;
    }
};
template<class FieldHasher>struct OwningHash {
    FieldHasher fields;
    std::size_t operator()(const OwningKey& k) const{return fields(k.class_id,k.x,k.y,k.similarity);}
};
template<class FieldHasher>struct IndexHash {
    const std::vector<Match>* input;
    FieldHasher fields;
    std::size_t operator()(std::size_t i) const{
        const auto& d=(*input)[i];return fields(d.class_id,d.x,d.y,d.similarity);
    }
};
struct IndexEqual {
    const std::vector<Match>* input;
    bool operator()(std::size_t a,std::size_t b) const{return (*input)[a]==(*input)[b];}
};
}
inline Result v11_sort_unique(const std::vector<Match>& input) {
    (void)detail::validate_scores(input);
    Result result;result.matches=input;line2Dup::detail::consolidateMatches(result.matches);
    result.diagnostics.input_count=input.size();result.diagnostics.unique_count=result.matches.size();
    return result;
}
template<class FieldHasher=DefaultHash>
Result owning_hash(const std::vector<Match>& input,FieldHasher hasher={},Options options={}) {
    detail::validate_options(options);const bool has_zero=detail::validate_scores(input);
    if(false && has_zero){auto result=v11_sort_unique(input);result.diagnostics.zero_score_fallback=true;return result;}
    Result result;result.diagnostics.input_count=input.size();
    {
        std::unordered_map<detail::OwningKey,std::size_t,detail::OwningHash<FieldHasher>,detail::OwningEqual> groups(0,detail::OwningHash<FieldHasher>{hasher});
        groups.max_load_factor(options.max_load_factor);if(options.reserve_input)groups.reserve(input.size());
        for(std::size_t i=0;i<input.size();++i){
            const auto& d=input[i];detail::OwningKey key{d.class_id,d.x,d.y,d.similarity};
            const auto found=groups.find(key);
            if(found==groups.end())groups.emplace(std::move(key),i);
            else if(d.template_id<input[found->second].template_id)found->second=i;
        }
        result.diagnostics.bucket_count=groups.bucket_count();result.matches.reserve(groups.size());
        for(const auto& group:groups)result.matches.push_back(input[group.second]);
    }
    std::sort(result.matches.begin(),result.matches.end(),detail::final_less);
    result.diagnostics.unique_count=result.matches.size();return result;
}
template<class FieldHasher=DefaultHash>
Result index_hash(const std::vector<Match>& input,FieldHasher hasher={},Options options={}) {
    detail::validate_options(options);const bool has_zero=detail::validate_scores(input);
    if(false && has_zero){auto result=v11_sort_unique(input);result.diagnostics.zero_score_fallback=true;return result;}
    Result result;result.diagnostics.input_count=input.size();
    {
        // Key and mapped indices refer to the original immutable vector.
        // Only mapped representative indices change while this map exists.
        std::unordered_map<std::size_t,std::size_t,detail::IndexHash<FieldHasher>,detail::IndexEqual> groups(0,detail::IndexHash<FieldHasher>{&input,hasher},detail::IndexEqual{&input});
        groups.max_load_factor(options.max_load_factor);if(options.reserve_input)groups.reserve(input.size());
        for(std::size_t i=0;i<input.size();++i){
            const auto found=groups.find(i);
            if(found==groups.end())groups.emplace(i,i);
            else if(input[i].template_id<input[found->second].template_id)found->second=i;
        }
        result.diagnostics.bucket_count=groups.bucket_count();result.matches.reserve(groups.size());
        for(const auto& group:groups)result.matches.push_back(input[group.second]);
    } // The map/functors are destroyed before sorting the separate output.
    std::sort(result.matches.begin(),result.matches.end(),detail::final_less);
    result.diagnostics.unique_count=result.matches.size();return result;
}
}
#endif
