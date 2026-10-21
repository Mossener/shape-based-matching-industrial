// Independent synthetic tests; no dataset, matcher or heldout image is opened.
#include "coverage_helper.hpp"
#include "coverage_nms.hpp"
#include <cmath>
#include <cstring>
#include <iostream>
#include <limits>
#include <random>
#include <stdexcept>

using namespace quality_coverage;
namespace {
std::uint64_t checks=0,map_queries=0,coverage_cases=0,nms_cases=0;
void require(bool value,const std::string& message) {
    ++checks;if(!value)throw std::runtime_error(message);
}
void close(double a,double b,const std::string& what) {
    require(std::abs(a-b)<1e-12,what);
}
template<class F> void throws(F f,const std::string& what) {
    bool thrown=false;try{f();}catch(const std::invalid_argument&){thrown=true;}
    require(thrown,what);
}
bool scalar_support(const std::vector<std::uint8_t>& field,int width,int height,
                    std::int64_t x,std::int64_t y,int label,int radius) {
    // Deliberately query scene pixels directly; no dilated helper/map is used.
    if(x<0 || x>=width || y<0 || y>=height || label<0 || label>7)return false;
    for(std::int64_t yy=std::max<std::int64_t>(0,y-radius);yy<=std::min<std::int64_t>(height-1,y+radius);++yy)
        for(std::int64_t xx=std::max<std::int64_t>(0,x-radius);xx<=std::min<std::int64_t>(width-1,x+radius);++xx) {
            const int seen=field[static_cast<std::size_t>(yy)*width+static_cast<std::size_t>(xx)];
            const int difference=std::abs(seen-label);
            if(seen<8 && (difference<=1 || difference==7))return true;
        }
    return false;
}
Coverage scalar_coverage(const std::vector<std::uint8_t>& scene,int width,int height,
                         const std::vector<Point>& raw,int tlx,int tly,int mx,int my,int radius,bool trusted=true) {
    Coverage result;
    if(!trusted){result.reason="untrusted_metadata";return result;}
    if(raw.empty()){result.reason="empty_points";return result;}
    for(const auto& p:raw)if(p.label>7){result.reason="invalid_orientation";return result;}
    // Independent scalar oracle forms its grid from the unshifted canvas;
    // translating by tl has no effect on relative grid membership.
    int xmin=raw.front().x,xmax=xmin,ymin=raw.front().y,ymax=ymin;
    for(const auto& p:raw){xmin=std::min(xmin,p.x);xmax=std::max(xmax,p.x);ymin=std::min(ymin,p.y);ymax=std::max(ymax,p.y);}
    const long double spanx=static_cast<long double>(xmax)-xmin+1;
    const long double spany=static_cast<long double>(ymax)-ymin+1;
    result.verified=true;result.reason="verified";result.points=raw.size();
    for(const auto& p:raw) {
        const int col=static_cast<int>(std::floor((static_cast<long double>(p.x)-xmin)*4/spanx));
        const int row=static_cast<int>(std::floor((static_cast<long double>(p.y)-ymin)*4/spany));
        const int cell=row*4+col;
        ++result.cell_points[cell];
        const std::int64_t x=std::int64_t(mx)+p.x-tlx,y=std::int64_t(my)+p.y-tly;
        const bool inside=x>=0 && x<width && y>=0 && y<height;
        if(inside)++result.in_bounds;
        if(scalar_support(scene,width,height,x,y,p.label,radius)){++result.supported;++result.cell_supported[cell];}
    }
    for(std::size_t i=0;i<16;++i)if(result.cell_points[i]) {
        ++result.occupied_cells;
        result.cell_coverage[i]=double(result.cell_supported[i])/double(result.cell_points[i]);
        result.balanced+=result.cell_coverage[i];
    }
    result.balanced/=double(result.occupied_cells);
    result.unweighted=double(result.supported)/double(result.points);
    result.in_bounds_fraction=double(result.in_bounds)/double(result.points);
    return result;
}
void same_coverage(const Coverage& a,const Coverage& b,const std::string& prefix) {
    require(a.verified==b.verified && a.reason==b.reason,prefix+" status");
    require(a.points==b.points && a.supported==b.supported && a.in_bounds==b.in_bounds && a.occupied_cells==b.occupied_cells,prefix+" counts");
    require(a.cell_points==b.cell_points && a.cell_supported==b.cell_supported,prefix+" cell counts");
    close(a.balanced,b.balanced,prefix+" balanced");close(a.unweighted,b.unweighted,prefix+" unweighted");
    close(a.in_bounds_fraction,b.in_bounds_fraction,prefix+" in bounds");
    for(std::size_t i=0;i<16;++i)close(a.cell_coverage[i],b.cell_coverage[i],prefix+" cell coverage");
}
void check_map(const std::vector<std::uint8_t>& field,int width,int height,int radius) {
    const auto maps=build_support(field,width,height,radius);
    for(int y=-1;y<=height;++y)for(int x=-1;x<=width;++x)for(int k=0;k<8;++k) {
        require(maps.supports(x,y,k)==scalar_support(field,width,height,x,y,k,radius),"support map != direct neighborhood oracle");++map_queries;
    }
}
void check_coverage(const std::vector<std::uint8_t>& field,int width,int height,const std::vector<Point>& points,
                    int tlx,int tly,int mx,int my,int radius=2,bool trusted=true) {
    const auto prepared=prepare_template(points,tlx,tly,trusted);
    const auto actual=evaluate(build_support(field,width,height,radius),prepared,mx,my);
    const auto expected=scalar_coverage(field,width,height,points,tlx,tly,mx,my,radius,trusted);
    same_coverage(actual,expected,"coverage scalar oracle");++coverage_cases;
}
void literal_maps() {
    // Break caught: exact-only, missing modulo wrap, directional or Manhattan dilation.
    std::vector<std::uint8_t> field(9*7,invalid_label);field[3*9+4]=7;
    const auto maps=build_support(field,9,7);
    require(maps.supports(2,1,0),"orientation 7 must support label 0 at radius-2 diagonal");
    require(maps.supports(6,5,6),"adjacent bin and inclusive diagonal radius");
    require(!maps.supports(1,3,0),"radius 3 must be unsupported");
    require(!maps.supports(4,3,1),"orientation distance 2 must be unsupported");
    require(!maps.supports(-1,3,7),"out-of-image query center remains unsupported");
    for(int label=0;label<8;++label) {
        std::fill(field.begin(),field.end(),invalid_label);field[3*9+4]=std::uint8_t(label);
        check_map(field,9,7,2);
    }
    // Radius 0/1/2/9 cover shrinking borders and a window larger than the scene.
    for(int radius:{0,1,2,9}) {
        check_map(std::vector<std::uint8_t>(1,0),1,1,radius);
        check_map(std::vector<std::uint8_t>(17,7),17,1,radius);
        check_map(std::vector<std::uint8_t>(19,3),1,19,radius);
        check_map(std::vector<std::uint8_t>(5*3,invalid_label),5,3,radius);
    }
    std::vector<std::uint8_t> mixed={0,invalid_label,3,7,invalid_label,1,4,6,2,5,invalid_label,0,3,7,4};
    check_map(mixed,5,3,2);
    throws([&]{build_support(mixed,0,3);},"zero scene width rejected");
    throws([&]{build_support(mixed,5,2);},"scene storage mismatch rejected");
    throws([&]{build_support(mixed,5,3,-1);},"negative radius rejected");
    mixed[0]=8;throws([&]{build_support(mixed,5,3);},"ambiguous scene label rejected");
}
void literal_coverage() {
    std::vector<std::uint8_t> field(17*13,invalid_label);field[6*17+8]=0;
    check_coverage(field,17,13,{{18,26,7},{16,24,1},{-4,3,0}},10,20,0,0);
    // Break caught: applying tl twice; negative relative samples are valid.
    const auto pt=prepare_template({{8,6,0},{6,4,7}},10,8);
    const auto cov=evaluate(build_support(field,17,13),pt,10,8);
    require(cov.verified && cov.supported==2 && cov.in_bounds==2,"negative relative points plus nonzero template origin");
    // Equivalent original-image / padded-image coordinates.
    std::vector<std::uint8_t> padded(25*23,invalid_label);
    for(int y=0;y<13;++y)for(int x=0;x<17;++x)padded[(y+5)*25+x+4]=field[y*17+x];
    same_coverage(cov,evaluate(build_support(padded,25,23),pt,14,13),"padding translation");
    // Break caught: discarding OOB denominator, using point-weighted score,
    // or averaging all 16 cells including empty cells.
    std::vector<Point> unequal(100,{0,0,0});unequal.push_back({15,0,4});
    std::vector<std::uint8_t> small(16,invalid_label);small[0]=0;
    const auto balanced=evaluate(build_support(small,16,1),prepare_template(unequal),0,0);
    require(balanced.occupied_cells==2 && balanced.supported==100,"unequal density fixture counts");
    close(balanced.balanced,.5,"occupied-cell equal weighting");close(balanced.unweighted,100.0/101,"point coverage separately reported");
    require(passes(balanced,.5) && !passes(balanced,.65),"inclusive policy threshold");
    const auto oob=evaluate(build_support(small,16,1),prepare_template({{-1,0,0},{0,0,0}}),0,0);
    require(oob.points==2 && oob.supported==1 && oob.in_bounds==1,"out-of-bounds kept in denominator");
    close(oob.balanced,.5,"OOB cell remains unsupported");
    for(const auto& pair:std::vector<std::pair<std::vector<Point>,bool>>{{{},true},{{{0,0,255}},true},{{{0,0,0}},false}}) {
        const auto c=evaluate(build_support(small,16,1),prepare_template(pair.first,0,0,pair.second),0,0);
        require(!c.verified && passes(c,.8),"unverified must pass through");
        check_coverage(small,16,1,pair.first,0,0,0,0,2,pair.second);
    }
    // Wide arithmetic: bbox/canvas subtraction and match addition cannot wrap.
    const int lo=std::numeric_limits<int>::min(),hi=std::numeric_limits<int>::max();
    check_coverage(small,16,1,{{lo,0,0},{hi,0,0}},0,0,hi,0);
    const auto wide=prepare_template({{lo,lo,0},{hi,hi,7}},hi,lo);
    require(wide.points[0].x==std::int64_t(lo)-hi && wide.points[1].y==std::int64_t(hi)-lo,"wide template offsets");
    throws([&]{passes(balanced,-.1);},"negative coverage threshold rejected");
    throws([&]{passes(balanced,std::numeric_limits<double>::quiet_NaN());},"NaN coverage threshold rejected");
    // Same sparse anchor evidence, but omitted dense edge differs.
    std::vector<std::uint8_t> sparse_scene(33*17,invalid_label);sparse_scene[8*33+4]=0;
    const auto support=build_support(sparse_scene,33,17);
    const auto sparse=evaluate(support,prepare_template({{4,8,0}}),0,0);
    const auto dense=evaluate(support,prepare_template({{4,8,0},{28,8,0}}),0,0);
    require(passes(sparse,.8) && !passes(dense,.8),"omitted edges add evidence beyond a sparse anchor");
}
bool equal_bits(float a,float b){return std::memcmp(&a,&b,sizeof(float))==0;}
void same_filter(const FilterResult& a,const FilterResult& b) {
    require(a.kept.size()==b.kept.size(),"full/lazy retained count");
    for(std::size_t i=0;i<a.kept.size();++i) {
        const auto& x=a.kept[i];const auto& y=b.kept[i];
        require(x.input_index==y.input_index,"full/lazy identity and order");
        const auto& p=x.candidate;const auto& q=y.candidate;
        require(p.class_id==q.class_id && p.template_id==q.template_id && p.x==q.x && p.y==q.y && equal_bits(p.score,q.score),"full/lazy exact score/class/template/coordinates");
        require(p.box.x==q.box.x && p.box.y==q.box.y && p.box.w==q.box.w && p.box.h==q.box.h,"full/lazy bbox fields");
        same_coverage(x.coverage,y.coverage,"full/lazy retained coverage");
    }
    ++nms_cases;
}
Candidate candidate(float score,int id,Box box,const std::string& cls="a") {
    Candidate c;c.score=score;c.template_id=id;c.box=box;c.x=id*3;c.y=id*-2;c.class_id=cls;return c;
}
Coverage fixed_coverage(bool good) {
    Coverage c;c.verified=true;c.reason="verified";c.points=10;c.supported=good?10:0;c.in_bounds=10;c.occupied_cells=1;
    c.cell_points[0]=10;c.cell_supported[0]=c.supported;c.cell_coverage[0]=good?1:0;
    c.balanced=c.unweighted=good?1:0;c.in_bounds_fraction=1;return c;
}
void literal_nms() {
    // Break caught: a failed high-score hypothesis suppressing a lower passing one.
    auto input=std::vector<Candidate>{candidate(99,0,{0,0,10,10}),candidate(98,1,{0,0,10,10}),candidate(97,2,{0,0,10,10}),candidate(96,3,{30,0,10,10})};
    auto verify=[](const Candidate& c){return fixed_coverage(c.template_id!=0);};
    const auto full=filter_full(input,verify,.8,.3),lazy=filter_lazy(input,verify,.8,.3);
    same_filter(full,lazy);
    require(lazy.kept.size()==2 && lazy.kept[0].candidate.template_id==1 && lazy.kept[1].candidate.template_id==3,"rejected candidate cannot suppress");
    require(full.attempted==4 && lazy.attempted==3 && lazy.suppressed==1,"lazy accounting");
    require(full.point_queries==40 && lazy.point_queries==30,"actual attempted point-query count");
    require(lazy.audit[2]==Audit::nms_suppressed && lazy.audit[0]==Audit::coverage_rejected,"skip is not verification");
    // Break caught: NMS >= instead of >, cross-class suppression or tie reorder.
    auto boundary=std::vector<Candidate>{candidate(90,2,{0,0,10,10}),candidate(90,1,{5,0,10,10}),candidate(90,1,{0,0,10,10},"b")};
    auto yes=[](const Candidate&){return fixed_coverage(true);};
    const auto result=filter_lazy(boundary,yes,.8,1.0/3.0);
    require(result.kept.size()==3 && result.kept[0].candidate.template_id==1 && result.kept[0].candidate.class_id=="a","strict NMS and canonical ties");
    same_filter(filter_full(boundary,yes,.8,1.0/3.0),result);
    auto unverified=[](const Candidate&){return Coverage{};};
    const auto unknown=filter_lazy(input,unverified,.8,.3);
    require(unknown.kept.size()==2 && !unknown.kept[0].coverage.verified && unknown.point_queries==0,"unverified pass-through before NMS");
    same_filter(filter_full({},yes,.8,.3),filter_lazy({},yes,.8,.3));
    throws([&]{filter_lazy(boundary,yes,.8,1.1);},"invalid NMS threshold rejected");
    auto bad=boundary;bad[0].score=std::numeric_limits<float>::quiet_NaN();
    throws([&]{filter_lazy(bad,yes,.8,.3);},"non-finite candidate score rejected before sorting");
}
void random_oracles() {
    for(unsigned seed:{1u,19u,20261021u,0xdeadbeefu,613u}) {
        std::mt19937 rng(seed);
        for(int iteration=0;iteration<120;++iteration) {
            const int w=1+int(rng()%37),h=1+int(rng()%29),radius=int(rng()%4);
            std::vector<std::uint8_t> field(static_cast<std::size_t>(w)*h,invalid_label);
            for(auto& v:field)if(rng()%4==0)v=std::uint8_t(rng()%8);
            check_map(field,w,h,radius);
            std::vector<Point> ps;const int n=1+int(rng()%150);
            for(int i=0;i<n;++i)ps.push_back({int(rng()%57)-20,int(rng()%49)-17,std::uint8_t(rng()%8)});
            const int tx=int(rng()%31)-15,ty=int(rng()%31)-15,mx=int(rng()%31)-15,my=int(rng()%31)-15;
            check_coverage(field,w,h,ps,tx,ty,mx,my,radius);
        }
        // Distinct random test: NMS paths run the real point/map verifier.
        std::vector<std::uint8_t> scene(31*23,invalid_label);
        for(auto& v:scene)if(rng()%6==0)v=std::uint8_t(rng()%8);
        const auto maps=build_support(scene,31,23);
        std::vector<PreparedTemplate> bank;
        for(int t=0;t<19;++t) {
            std::vector<Point> ps;
            for(int i=0;i<1+int(rng()%93);++i)ps.push_back({int(rng()%41)-20,int(rng()%31)-15,std::uint8_t(rng()%8)});
            bank.push_back(prepare_template(ps,int(rng()%9)-4,int(rng()%9)-4,t!=18));
        }
        for(int trial=0;trial<100;++trial) {
            std::vector<Candidate> input;
            for(int i=0;i<83;++i) {
                auto c=candidate(float(80+rng()%20),int(rng()%bank.size()),{double(rng()%19),double(rng()%17),double(1+rng()%21),double(1+rng()%19)},rng()%2?"a":"b");
                c.x=int(rng()%45)-7;c.y=int(rng()%37)-7;input.push_back(c);
            }
            // Duplicate score/ID/box ties exercise original input-index stability.
            input.push_back(input.front());
            auto verify=[&](const Candidate& c){return evaluate(maps,bank[c.template_id],c.x,c.y);};
            for(double threshold:{.5,.65,.8}) {
                const auto full=filter_full(input,verify,threshold,.3),lazy=filter_lazy(input,verify,threshold,.3);
                same_filter(full,lazy);
                require(lazy.attempted<=full.attempted,"lazy never verifies additional candidates");
            }
        }
    }
}
void large_templates() {
    // Dynamic storage, no point-count or bbox-size exclusion. The dimensions
    // mirror the supplied magnet ROI, without reading any magnetic samples.
    const int w=419,h=281;std::vector<std::uint8_t> field(static_cast<std::size_t>(w)*h,0);
    for(std::size_t n:{std::size_t(5),std::size_t(32),std::size_t(1214),std::size_t(8191)}) {
        std::vector<Point> ps;
        for(std::size_t i=0;i<n;++i)ps.push_back({int(i%414)-3,int((i*47)%275)-2,0});
        check_coverage(field,w,h,ps,-3,-2,0,0);
        const auto c=evaluate(build_support(field,w,h),prepare_template(ps,-3,-2),0,0);
        require(c.verified && c.points==n && c.supported==n && c.balanced==1,"large dynamic template preserves every point");
    }
}
}
int main() {
    try {
        literal_maps();literal_coverage();literal_nms();random_oracles();large_templates();
        std::cout<<"{\"status\":\"PASS\",\"checks\":"<<checks<<",\"map_queries\":"<<map_queries
                 <<",\"coverage_oracle_cases\":"<<coverage_cases<<",\"full_lazy_cases\":"<<nms_cases
                 <<",\"seeds\":[1,19,20261021,3735928559,613],\"dataset_access\":false}\n";
        return 0;
    } catch(const std::exception& e){std::cerr<<"FAIL after "<<checks<<" checks: "<<e.what()<<'\n';return 1;}
}
