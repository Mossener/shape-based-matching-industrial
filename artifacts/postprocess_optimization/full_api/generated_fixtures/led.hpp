#pragma once
namespace postprocess_fixture_sources { namespace led {
struct StoredPoint { unsigned flag; float x, y, angle; };
struct Pose { float angle, scale; };

std::vector<int> pyramidSteps(int levels) {
    if (levels < 2 || levels > 3) throw std::runtime_error("Use 2 or 3 pyramid levels");
    std::vector<int> steps(levels, 8);
    steps[0] = 4;
    return steps;
}

template<class T> T readAt(const std::vector<unsigned char>& data, size_t offset) {
    if (offset + sizeof(T) > data.size()) throw std::runtime_error("Truncated SMD");
    T v; std::memcpy(&v, data.data() + offset, sizeof(v)); return v;
}

class SmdDetector : public line2Dup::Detector {
public:
    std::vector<Pose> poses;
    std::vector<std::vector<StoredPoint>> points;
    explicit SmdDetector(const std::string& path, int levels = 2)
        : Detector(128, pyramidSteps(levels), 20, 40) {
        std::ifstream f(path, std::ios::binary);
        std::vector<unsigned char> b((std::istreambuf_iterator<char>(f)), {});
        if (b.size() != 74552 || readAt<unsigned>(b, 0) != 0x00444d53 ||
            readAt<unsigned>(b, 20) != 20161201 || readAt<unsigned>(b, 67780) != 20171201)
            throw std::runtime_error("This experiment only supports the supplied LED/ku.smd");
        size_t offset = 67832;
        for (int level = 0; level < 4; ++level) {
            const unsigned count = readAt<unsigned>(b, offset + 16);
            if (readAt<unsigned>(b, offset) != 2 || readAt<unsigned>(b, offset + 4) != unsigned(level) ||
                readAt<unsigned>(b, offset + 8) != unsigned(120 >> level) ||
                readAt<unsigned>(b, offset + 12) != unsigned(120 >> level) || count > 1000)
                throw std::runtime_error("Unexpected SMD pyramid layout");
            offset += 20;
            std::vector<StoredPoint> ps;
            for (unsigned i = 0; i < count; ++i, offset += 16) {
                StoredPoint p{readAt<unsigned>(b,offset), readAt<float>(b,offset+4),
                    readAt<float>(b,offset+8), readAt<float>(b,offset+12)};
                if (p.flag > 3 || !std::isfinite(p.x) || !std::isfinite(p.y) ||
                    p.x < 0 || p.y < 0 || p.x >= (120 >> level) || p.y >= (120 >> level) ||
                    !std::isfinite(p.angle) || p.angle < 0 || p.angle > 360)
                    throw std::runtime_error("Invalid SMD contour point");
                ps.push_back(p);
            }
            points.push_back(ps);
        }
        if (offset != b.size()) throw std::runtime_error("Unparsed SMD data");
        std::cout << "SMD points:";
        for (const auto& ps:points) std::cout << ' ' << ps.size();
        std::cout << '\n';
    }

    void addPose(float angle, float scale) {
        const int levels = pyramidLevels();
        std::vector<line2Dup::Template> tp(levels);
        const float rad = angle * float(CV_PI / 180.0);
        const float cs = std::cos(rad), sn = std::sin(rad);
        int minx=100000, miny=100000, maxx=-100000, maxy=-100000;
        for (int l=0; l<levels; ++l) {
            auto& t=tp[l]; t.pyramid_level=l;
            const float center=60.f / (1<<l);
            for (const auto& p:points[l]) {
                line2Dup::Feature q;
                const float x=(p.x-center)*scale, y=(p.y-center)*scale;
                // Positive pose angle is counterclockwise in the displayed image.
                q.x=cvRound(cs*x+sn*y+center*scale);
                q.y=cvRound(-sn*x+cs*y+center*scale);
                // SMD angles use the opposite y-axis to the image gradient.
                q.theta=std::fmod(720.f-p.angle-angle,360.f);
                q.label=int(q.theta*16.f/360.f+0.5f)&7;
                t.features.push_back(q);
                minx=std::min(minx,q.x*(1<<l)); miny=std::min(miny,q.y*(1<<l));
                maxx=std::max(maxx,q.x*(1<<l)); maxy=std::max(maxy,q.y*(1<<l));
            }
        }
        // Keep all pyramid levels on the same physical crop origin.
        const int alignment=1<<(levels-1);
        minx=int(std::floor(minx/double(alignment)))*alignment;
        miny=int(std::floor(miny/double(alignment)))*alignment;
        for (int l=0;l<levels;++l) {
            auto& t=tp[l]; t.width=(maxx-minx)>>l; t.height=(maxy-miny)>>l;
            t.tl_x=int(std::floor(minx/double(1<<l))); t.tl_y=int(std::floor(miny/double(1<<l)));
            for(auto& p:t.features) {p.x-=t.tl_x; p.y-=t.tl_y;}
        }
        class_templates["LED"].push_back(tp); poses.push_back({angle,scale});
    }
};


} }
