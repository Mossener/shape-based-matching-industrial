#ifndef OBJ8_PADDING_PLAN_HPP
#define OBJ8_PADDING_PLAN_HPP
#include <algorithm>
#include <array>
#include <cstdint>
#include <limits>
#include <map>
#include <set>
#include <stdexcept>
#include <string>
#include <vector>
namespace obj8_padding {
using U=std::uint64_t;
struct Layer {
    std::string class_id;
    int template_id=0,level=0;
    std::int64_t width=0,height=0,min_x=0,min_y=0,max_x=0,max_y=0;
};
struct Limits {
    U axis=2048,pixels=1048576,bytes_per_pixel=512,dynamic_bytes=536870912;
};
struct Plan {
    U width=0,height=0,alignment=0,pixels=0,estimated_bytes=0;
    std::array<U,4> padding{{0,0,0,0}};
};
inline U add(U a,U b) {
    if(b>std::numeric_limits<U>::max()-a)throw std::overflow_error("Padding sum overflow");
    return a+b;
}
inline U multiply(U a,U b) {
    if(a && b>std::numeric_limits<U>::max()/a)throw std::overflow_error("Padding product overflow");
    return a*b;
}
inline U align(U value,U multiple) {
    if(!multiple)throw std::invalid_argument("Positive alignment required");
    return multiply(add(value,multiple-1)/multiple,multiple);
}
inline U gcd(U a,U b) {while(b){const U next=a%b;a=b;b=next;}return a;}
inline Plan make_plan(U source_width,U source_height,const std::array<U,4>& base,
                      const std::vector<Layer>& layers,const std::vector<U>& t,
                      const Limits& limits = Limits()) {
    if(!source_width || !source_height || layers.empty() || t.empty() || t.size()>64)
        throw std::invalid_argument("Nonempty source, full bank and pyramid required");
    std::vector<U> factors;U factor=1,alignment=1;
    for(std::size_t level=0;level<t.size();++level) {
        if(!t[level])throw std::invalid_argument("Positive pyramid T required");
        factors.push_back(factor);const U term=multiply(factor,t[level]);
        alignment=multiply(alignment/gcd(alignment,term),term);
        if(level+1<t.size())factor=multiply(factor,2);
    }
    U required_width=add(source_width,add(base[0],base[2]));
    U required_height=add(source_height,add(base[1],base[3]));
    std::map<std::pair<std::string,int>,std::set<int>> poses;
    for(const auto& row:layers) {
        if(row.class_id.empty() || row.template_id<0 || row.level<0 || std::size_t(row.level)>=t.size() ||
           row.width<=0 || row.height<=0 || row.min_x<0 || row.min_y<0 ||
           row.max_x<row.min_x || row.max_y<row.min_y || row.max_x>row.width || row.max_y>row.height)
            throw std::invalid_argument("Malformed loaded bank layer");
        auto& levels=poses[{row.class_id,row.template_id}];
        if(!levels.insert(row.level).second)throw std::invalid_argument("Duplicate loaded bank layer");
        const auto level=std::size_t(row.level);U width,height;
        if(level+1<t.size()) {
            const U margin=multiply(16,t[level]);
            width=add(U(row.width),margin);height=add(U(row.height),margin);
        }else {
            width=std::max(U(row.width),add(U(row.max_x),1));
            height=std::max(U(row.height),add(U(row.max_y),1));
        }
        required_width=std::max(required_width,multiply(factors[level],width));
        required_height=std::max(required_height,multiply(factors[level],height));
    }
    for(const auto& pose:poses)if(pose.second.empty())throw std::invalid_argument("Incomplete loaded pose pyramid");
    Plan result;result.alignment=alignment;result.width=align(required_width,alignment);result.height=align(required_height,alignment);
    result.pixels=multiply(result.width,result.height);result.estimated_bytes=multiply(result.pixels,limits.bytes_per_pixel);
    if(result.width>limits.axis || result.height>limits.axis || result.pixels>limits.pixels || result.estimated_bytes>limits.dynamic_bytes)
        throw std::length_error("Full-bank padding exceeds declared resource budget");
    result.padding={{base[0],base[1],result.width-source_width-base[0],result.height-source_height-base[1]}};
    return result;
}
}
#endif
