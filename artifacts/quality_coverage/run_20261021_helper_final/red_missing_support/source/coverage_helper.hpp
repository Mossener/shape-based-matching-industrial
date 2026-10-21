#ifndef QUALITY_COVERAGE_HELPER_HPP
#define QUALITY_COVERAGE_HELPER_HPP
#include <algorithm>
#include <array>
#include <cstdint>
#include <stdexcept>
#include <string>
#include <vector>
namespace quality_coverage {
constexpr std::uint8_t invalid_label=255;
struct Point {int x=0,y=0;std::uint8_t label=invalid_label;};
struct RelativePoint {std::int64_t x=0,y=0;std::uint8_t label=invalid_label;};
struct PreparedTemplate {bool verified=false;std::string reason;std::vector<RelativePoint> points;};
struct Coverage {
    bool verified=false;std::string reason;
    std::size_t points=0,supported=0,in_bounds=0,occupied_cells=0;
    std::array<std::size_t,16> cell_points{},cell_supported{};
    std::array<double,16> cell_coverage{};
    double balanced=0,unweighted=0,in_bounds_fraction=0;
};
struct SupportMaps {bool supports(std::int64_t,std::int64_t,int)const{return false;}};
inline SupportMaps build_support(const std::vector<std::uint8_t>&,int,int,int=2){return {};}
inline PreparedTemplate prepare_template(const std::vector<Point>&,int=0,int=0,bool=true){return {};}
inline Coverage evaluate(const SupportMaps&,const PreparedTemplate&,int,int){return {};}
inline bool passes(const Coverage&,double){return true;}
}
#endif
