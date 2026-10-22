#pragma once
namespace postprocess_fixture_sources { namespace magnet {
struct Point { unsigned flag; float x,y,angle; };
struct Pose { float angle,scale; };
template<class T> T field(const std::vector<unsigned char>& b,std::size_t offset) {
    if(offset>b.size() || sizeof(T)>b.size()-offset) throw std::runtime_error("Truncated SMD field");
    T value;std::memcpy(&value,b.data()+offset,sizeof(value));return value;
}
class MagnetDetector:public line2Dup::Detector {
public:
    std::vector<std::vector<Point>> points;
    std::vector<Pose> poses;
    const float width=414,height=275;
    explicit MagnetDetector(const std::string& path,int levels):Detector(128,steps(levels),20,40) {
        std::ifstream in(path,std::ios::binary);
        std::vector<unsigned char> b((std::istreambuf_iterator<char>(in)),{});
        auto u=[&](std::size_t o){return field<unsigned>(b,o);};
        if(b.size()!=652672 || u(0)!=0x00444d53 || u(4)!=121 || u(8)!=108 || u(12)!=535 || u(16)!=383)
            throw std::runtime_error("Unsupported magnet SMD; run inspection/SHA validation first");
        std::size_t p=20;
        for(int i=0;i<2;++i) {
            if(u(p)!=20161201 || u(p+4)!=640 || u(p+8)!=480 || u(p+12)!=1 || u(p+16)!=640 || u(p+20)!=307200)
                throw std::runtime_error("Unexpected embedded image block");
            p+=24+u(p+20);
        }
        if(p!=614468 || u(p)!=20171201 || u(p+48)!=6) throw std::runtime_error("Unexpected model header");
        p+=52;
        const unsigned widths[]={414,207,104,52,25,13}, heights[]={275,137,69,35,18,9}, counts[]={1214,605,301,149,73,35};
        for(unsigned l=0;l<6;++l) {
            if(u(p)!=2 || u(p+4)!=l || u(p+8)!=widths[l] || u(p+12)!=heights[l] || u(p+16)!=counts[l])
                throw std::runtime_error("Unexpected SMD level header");
            p+=20;std::vector<Point> ps;
            for(unsigned i=0;i<counts[l];++i,p+=16) {
                Point q{u(p),field<float>(b,p+4),field<float>(b,p+8),field<float>(b,p+12)};
                if(q.flag>3 || !std::isfinite(q.x) || !std::isfinite(q.y) || !std::isfinite(q.angle) ||
                   q.x<-.5f || q.y<-.5f || q.x>=widths[l]+.5f || q.y>=heights[l]+.5f || q.angle<0 || q.angle>360)
                    throw std::runtime_error("Invalid contour point");
                ps.push_back(q);
            }
            points.push_back(ps);
        }
        if(p!=b.size()) throw std::runtime_error("Unparsed SMD tail");
    }
    static std::vector<int> steps(int levels) {
        if(levels<2 || levels>4)throw std::runtime_error("Use 2, 3 or 4 pyramid levels");
        std::vector<int> r(levels,8);r[0]=4;return r;
    }
    void addPose(float angle,float scale) {
        std::vector<line2Dup::Template> templates(pyramidLevels());
        const float cs=std::cos(angle*float(CV_PI/180)),sn=std::sin(angle*float(CV_PI/180));
        int minx=100000,miny=100000,maxx=-100000,maxy=-100000;
        for(int l=0;l<pyramidLevels();++l) {
            auto& t=templates[l];t.pyramid_level=l;
            const float cx=width/(2*(1<<l)),cy=height/(2*(1<<l));
            for(const auto& p:points[l]) {
                const float x=(p.x-cx)*scale,y=(p.y-cy)*scale;
                line2Dup::Feature q;
                q.x=cvRound(cs*x+sn*y+cx*scale);q.y=cvRound(-sn*x+cs*y+cy*scale);
                q.theta=std::fmod(720.f-p.angle-angle,360.f);
                q.label=int(q.theta*16.f/360.f+.5f)&7;
                t.features.push_back(q);
                minx=std::min(minx,q.x*(1<<l));miny=std::min(miny,q.y*(1<<l));
                maxx=std::max(maxx,q.x*(1<<l));maxy=std::max(maxy,q.y*(1<<l));
            }
        }
        const int align=1<<(pyramidLevels()-1);
        minx=int(std::floor(minx/double(align)))*align;miny=int(std::floor(miny/double(align)))*align;
        for(int l=0;l<pyramidLevels();++l) {
            auto& t=templates[l];t.width=(maxx-minx)>>l;t.height=(maxy-miny)>>l;
            t.tl_x=int(std::floor(minx/double(1<<l)));t.tl_y=int(std::floor(miny/double(1<<l)));
            for(auto& q:t.features){q.x-=t.tl_x;q.y-=t.tl_y;}
        }
        class_templates["magnet"].push_back(templates);poses.push_back({angle,scale});
    }
};

} }
