#ifndef OBJ8_PADDING_PLAN_HPP
#define OBJ8_PADDING_PLAN_HPP
#include <array>
#include <cstdint>
#include <limits>
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
inline U add(U,U) {throw std::runtime_error("Planner arithmetic not implemented");}
inline U multiply(U,U) {throw std::runtime_error("Planner arithmetic not implemented");}
inline U align(U,U) {throw std::runtime_error("Planner arithmetic not implemented");}
inline Plan make_plan(U,U,const std::array<U,4>&,const std::vector<Layer>&,
                      const std::vector<U>&,const Limits& = Limits()) {
    throw std::runtime_error("Full-bank padding planner not implemented");
}
}
#endif
