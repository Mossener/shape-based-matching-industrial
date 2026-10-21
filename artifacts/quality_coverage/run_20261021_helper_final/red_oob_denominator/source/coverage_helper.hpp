#ifndef QUALITY_COVERAGE_HELPER_HPP
#define QUALITY_COVERAGE_HELPER_HPP
#include <algorithm>
#include <array>
#include <cstdint>
#include <cmath>
#include <limits>
#include <stdexcept>
#include <string>
#include <vector>
namespace quality_coverage {
constexpr std::uint8_t invalid_label=255;
struct Point {int x=0,y=0;std::uint8_t label=invalid_label;};
struct RelativePoint {std::int64_t x=0,y=0;std::uint8_t label=invalid_label;};
struct PreparedTemplate {
    bool verified=false;std::string reason;
    std::vector<RelativePoint> points;
    std::vector<std::uint8_t> cells;
    std::array<std::size_t,16> cell_points{};
};
struct Coverage {
    bool verified=false;std::string reason;
    std::size_t points=0,supported=0,in_bounds=0,occupied_cells=0;
    std::array<std::size_t,16> cell_points{},cell_supported{};
    std::array<double,16> cell_coverage{};
    double balanced=0,unweighted=0,in_bounds_fraction=0;
};
class SupportMaps {
    int width_=0,height_=0;
    std::array<std::vector<std::uint8_t>,8> maps_;
    friend SupportMaps build_support(const std::vector<std::uint8_t>&,int,int,int);
public:
    int width()const{return width_;}
    int height()const{return height_;}
    bool supports(std::int64_t x,std::int64_t y,int label)const {
        // An out-of-image sample stays unsupported even if a nearby border
        // pixel would be compatible. Its denominator is retained by evaluate.
        return label>=0 && label<8 && x>=0 && x<width_ && y>=0 && y<height_ &&
            maps_[label][static_cast<std::size_t>(y)*static_cast<std::size_t>(width_)+static_cast<std::size_t>(x)]!=0;
    }
};
// A one-label field: exactly 0..7 or invalid_label (255), never a bit mask.
// Eight binary maps share the scene. A separable rolling-count max filter
// provides Chebyshev support in O(8*width*height) time, independent of radius.
inline SupportMaps build_support(const std::vector<std::uint8_t>& scene,int width,int height,int radius=2) {
    if(width<=0 || height<=0 || radius<0)throw std::invalid_argument("Invalid scene dimensions/radius");
    const std::uint64_t count=std::uint64_t(width)*std::uint64_t(height);
    if(count>std::numeric_limits<std::size_t>::max() || scene.size()!=static_cast<std::size_t>(count))
        throw std::invalid_argument("Scene field storage does not match dimensions");
    for(auto label:scene)if(label>=8 && label!=invalid_label)throw std::invalid_argument("Scene requires one-label orientations");
    SupportMaps result;result.width_=width;result.height_=height;
    std::vector<std::uint8_t> base(scene.size()),horizontal(scene.size());
    const int effective_radius=radius;
    for(int label=0;label<8;++label) {
        for(std::size_t i=0;i<scene.size();++i) {
            const int distance=std::abs(int(scene[i])-label);
            base[i]=scene[i]<8 && (distance<=1 || distance==7);
        }
        for(int y=0;y<height;++y) {
            const std::size_t row=static_cast<std::size_t>(y)*static_cast<std::size_t>(width);
            std::size_t active=0;
            for(int x=0;x<width && x<=effective_radius;++x)active+=base[row+x];
            for(int x=0;x<width;++x) {
                horizontal[row+x]=active!=0;
                const std::int64_t leaving=std::int64_t(x)-effective_radius;
                const std::int64_t entering=std::int64_t(x)+effective_radius+1;
                if(leaving>=0)active-=base[row+static_cast<std::size_t>(leaving)];
                if(entering<width)active+=base[row+static_cast<std::size_t>(entering)];
            }
        }
        auto& output=result.maps_[label];output.resize(scene.size());
        for(int x=0;x<width;++x) {
            std::size_t active=0;
            for(int y=0;y<height && y<=effective_radius;++y)active+=horizontal[static_cast<std::size_t>(y)*width+x];
            for(int y=0;y<height;++y) {
                output[static_cast<std::size_t>(y)*width+x]=active!=0;
                const std::int64_t leaving=std::int64_t(y)-effective_radius;
                const std::int64_t entering=std::int64_t(y)+effective_radius+1;
                if(leaving>=0)active-=horizontal[static_cast<std::size_t>(leaving)*width+x];
                if(entering<height)active+=horizontal[static_cast<std::size_t>(entering)*width+x];
            }
        }
    }
    return result;
}
// Input points are integer canvas coordinates. Subtract template.tl_x/tl_y
// exactly once here; evaluate adds only the core match coordinate afterwards.
// Floating SMD rounding and gradient sampling belong to a separate adapter.
inline PreparedTemplate prepare_template(const std::vector<Point>& canvas,int tl_x=0,int tl_y=0,bool trusted=true) {
    PreparedTemplate result;
    if(!trusted){result.reason="untrusted_metadata";return result;}
    if(canvas.empty()){result.reason="empty_points";return result;}
    for(const auto& p:canvas)if(p.label>7){result.reason="invalid_orientation";return result;}
    int xmin=canvas.front().x,xmax=xmin,ymin=canvas.front().y,ymax=ymin;
    for(const auto& p:canvas){xmin=std::min(xmin,p.x);xmax=std::max(xmax,p.x);ymin=std::min(ymin,p.y);ymax=std::max(ymax,p.y);}
    const std::int64_t span_x=std::int64_t(xmax)-xmin+1,span_y=std::int64_t(ymax)-ymin+1;
    result.points.reserve(canvas.size());result.cells.reserve(canvas.size());
    for(const auto& p:canvas) {
        const int col=int((std::int64_t(p.x)-xmin)*4/span_x),row=int((std::int64_t(p.y)-ymin)*4/span_y);
        const auto cell=static_cast<std::uint8_t>(row*4+col);
        result.points.push_back({std::int64_t(p.x)-tl_x,std::int64_t(p.y)-tl_y,p.label});
        result.cells.push_back(cell);++result.cell_points[cell];
    }
    result.verified=true;result.reason="verified";return result;
}
inline Coverage evaluate(const SupportMaps& maps,const PreparedTemplate& object,int match_x,int match_y) {
    Coverage result;result.reason=object.reason;
    if(!object.verified)return result;
    if(maps.width()<=0 || maps.height()<=0 || object.points.empty() || object.points.size()!=object.cells.size())
        throw std::invalid_argument("Use built support maps and a prepared template");
    result.verified=true;result.points=object.points.size();result.cell_points=object.cell_points;
    for(std::size_t i=0;i<object.points.size();++i) {
        const auto& p=object.points[i];const std::int64_t x=std::int64_t(match_x)+p.x,y=std::int64_t(match_y)+p.y;
        if(x>=0 && x<maps.width() && y>=0 && y<maps.height())++result.in_bounds;
        if(maps.supports(x,y,p.label)){++result.supported;++result.cell_supported[object.cells[i]];}
    }
    for(std::size_t cell=0;cell<16;++cell)if(result.cell_points[cell]) {
        ++result.occupied_cells;
        result.cell_coverage[cell]=double(result.cell_supported[cell])/double(result.cell_points[cell]);
        result.balanced+=result.cell_coverage[cell];
    }
    result.balanced/=double(result.occupied_cells);
    result.unweighted=double(result.supported)/double(std::max(std::size_t(1),result.in_bounds));
    result.in_bounds_fraction=double(result.in_bounds)/double(result.points);
    return result;
}
inline void validate_threshold(double value,const char* what) {
    if(!std::isfinite(value) || value<0 || value>1)throw std::invalid_argument(what);
}
inline bool passes(const Coverage& value,double threshold) {
    validate_threshold(threshold,"Coverage threshold must be finite and in [0,1]");
    return !value.verified || value.balanced>=threshold;
}
}
#endif
