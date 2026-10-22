// One-off experiment: use the contours stored in LED/ku.smd with this
// repository's current line2Dup matcher. Not a general SMD format reader.
#include "line2Dup.h"
#include <opencv2/imgcodecs.hpp>
#include <omp.h>
#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstring>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <iterator>
#include <sstream>
#include <stdexcept>

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

int benchmarkPaired(const std::string& input, const std::string& output) {
    cv::setNumThreads(1); omp_set_num_threads(4);
    SmdDetector l2(input+"/ku.smd",2), l3(input+"/ku.smd",3);
    for(int s=0;s<5;++s) for(int a=0;a<360;a+=2) {
        l2.addPose(float(a),0.9f+0.05f*s);
        l3.addPose(float(a),0.9f+0.05f*s);
    }
    std::ofstream config(output+"/run_config.json");
    std::ofstream timings(output+"/timings.csv");
    if(!config || !timings) throw std::runtime_error("Cannot open paired benchmark output");
    config << "{\"levels\":[2,3],\"repeats_per_image_per_configuration\":10,\"warmups\":1,"
        << "\"template_count_per_configuration\":900,\"threshold\":75,\"openmp_threads\":4,"
        << "\"opencv_threads\":1,\"padding\":64,\"angle_step_degrees\":2,"
        << "\"scales\":[0.90,0.95,1.0,1.05,1.10],\"T_l2\":[4,8],\"T_l3\":[4,8,8],"
        << "\"order\":\"Even repeats L2,L3; odd repeats L3,L2 in the same process\"}\n";
    timings << "image,repeat,levels,order,match_ms,best_score,candidates,center_x,center_y,angle_deg,scale\n";
    for(int i=1;i<=8;++i) {
        auto gray=cv::imread(input+"/"+std::to_string(i)+".bmp",cv::IMREAD_GRAYSCALE);
        if(gray.empty()) throw std::runtime_error("Cannot read paired benchmark image");
        cv::Mat padded; cv::copyMakeBorder(gray,padded,64,64,64,64,cv::BORDER_CONSTANT,cv::Scalar(0));
        if(padded.cols%32 || padded.rows%32) throw std::runtime_error("Paired input must align to 32");
        l2.match(padded,75.f,{"LED"}); l3.match(padded,75.f,{"LED"});
        for(int r=0;r<10;++r) for(int order=0;order<2;++order) {
            const int levels=((r+order)%2==0)?2:3;
            SmdDetector& detector=levels==2?l2:l3;
            const auto start=std::chrono::steady_clock::now();
            const auto matches=detector.match(padded,75.f,{"LED"});
            const auto end=std::chrono::steady_clock::now();
            const double ms=std::chrono::duration<double,std::milli>(end-start).count();
            timings << i << ".bmp," << r << ',' << levels << ',' << order << ',' << ms << ',';
            if(matches.empty()) {
                timings << ',' << 0 << ",,,,\n";
            } else {
                const auto& m=matches.front();
                const auto& t=detector.getTemplates("LED",m.template_id)[0];
                const auto pose=detector.poses[m.template_id];
                const float cx=m.x-64-t.tl_x+60.f*pose.scale;
                const float cy=m.y-64-t.tl_y+60.f*pose.scale;
                timings << m.similarity << ',' << matches.size() << ',' << cx << ',' << cy
                    << ',' << pose.angle << ',' << pose.scale << '\n';
            }
        }
        std::cout << "PAIRED COMPLETE " << i << '\n';
    }
    return 0;
}

int main(int argc,char** argv) {
    try {
        if(argc>1 && std::string(argv[1])=="--paired") {
            if(argc!=4) throw std::runtime_error("Usage: led_demo --paired INPUT OUTPUT");
            return benchmarkPaired(argv[2],argv[3]);
        }
        const std::string input=argc>1?argv[1]:"LED";
        const std::string output=argc>2?argv[2]:"artifacts/led_match";
        const int repeats=argc>3?std::max(1,std::atoi(argv[3])):1;
        const int levels=argc>4?std::atoi(argv[4]):2;
        const int warmups=argc>5?std::max(0,std::atoi(argv[5])):0;
        cv::setNumThreads(1); omp_set_num_threads(4);
        SmdDetector detector(input+"/ku.smd",levels);
        for (int s=0;s<5;++s) for(int a=0;a<360;a+=2) detector.addPose(float(a),0.9f+0.05f*s);
        std::cout << "Templates " << detector.numTemplates() << ", levels " << levels
            << ", threads 4, OpenCV threads 1, repeats " << repeats << ", warmups " << warmups << '\n';
        std::ofstream config(output+"/run_config.json");
        config << "{\"levels\":" << levels << ",\"repeats\":" << repeats << ",\"warmups\":" << warmups
            << ",\"template_count\":" << detector.numTemplates()
            << ",\"threshold\":75,\"openmp_threads\":4,\"opencv_threads\":1,\"padding\":64,"
            << "\"angle_step_degrees\":2,\"scales\":[0.90,0.95,1.0,1.05,1.10],\"T\":[4,8"
            << (levels==3?",8":"") << "]}\n";
        std::ofstream csv(output+"/results.csv");
        std::ofstream timings(output+"/timings.csv");
        if (!config || !csv || !timings) throw std::runtime_error("Cannot open experiment output files");
        csv << "image,score,angle_deg,scale,center_x,center_y,match_ms,candidates\n";
        timings << "image,repeat,match_ms,best_score,candidates\n";
        std::ofstream featureCsv(output+"/smd_contours.csv");
        featureCsv << "level,flag,x,y,smd_angle_deg\n";
        for(size_t l=0;l<detector.points.size();++l) for(const auto& p:detector.points[l])
            featureCsv << l << ',' << p.flag << ',' << p.x << ',' << p.y << ',' << p.angle << '\n';
        for(int i=1;i<=8;++i) {
            auto gray=cv::imread(input+"/"+std::to_string(i)+".bmp",cv::IMREAD_GRAYSCALE);
            if(gray.empty()) throw std::runtime_error("Cannot read LED image");
            // Extra border keeps the detector's local refinement safe at image edges.
            const int padding=64;
            cv::Mat padded; cv::copyMakeBorder(gray,padded,padding,padding,padding,padding,cv::BORDER_CONSTANT,cv::Scalar(0));
            const int inputAlignment=8*(1<<(levels-1));
            if(padded.cols%inputAlignment || padded.rows%inputAlignment)
                throw std::runtime_error("Image does not align to the coarsest pyramid step");
            for(int r=0;r<warmups;++r) detector.match(padded,75.f,{"LED"});
            std::vector<line2Dup::Match> matches;
            std::vector<double> times;
            for(int r=0;r<repeats;++r) {
                const auto start=std::chrono::steady_clock::now();
                auto next=detector.match(padded,75.f,{"LED"});
                const auto end=std::chrono::steady_clock::now();
                const double duration=std::chrono::duration<double,std::milli>(end-start).count();
                times.push_back(duration);
                timings << i << ".bmp," << r << ',' << duration << ',';
                if(!next.empty()) timings << next.front().similarity;
                timings << ',' << next.size() << '\n';
                if(r==0) matches=std::move(next);
            }
            std::sort(times.begin(),times.end()); const double ms=times[times.size()/2];
            cv::Mat result; cv::cvtColor(gray,result,cv::COLOR_GRAY2BGR);
            if(matches.empty()) {
                csv << i << ".bmp,,,,,," << ms << ",0\n";
                cv::putText(result,"NO MATCH >= 75",{20,35},cv::FONT_HERSHEY_SIMPLEX,0.8,{0,0,255},2);
                std::cout << "RESULT " << i << " no match " << ms << " ms\n";
            } else {
                const auto& m=matches.front(); const auto& t=detector.getTemplates("LED",m.template_id)[0];
                const auto pose=detector.poses[m.template_id];
                const float originx=float(m.x-padding-t.tl_x), originy=float(m.y-padding-t.tl_y);
                const cv::Point2f center(originx+60.f*pose.scale,originy+60.f*pose.scale);
                csv << i << ".bmp," << m.similarity << ',' << pose.angle << ',' << pose.scale << ','
                    << center.x << ',' << center.y << ',' << ms << ',' << matches.size() << '\n';
                for(const auto& p:t.features) cv::circle(result,{p.x+m.x-padding,p.y+m.y-padding},1,{0,255,0},-1,cv::LINE_AA);
                cv::drawMarker(result,center,{0,190,255},cv::MARKER_CROSS,18,1,cv::LINE_AA);
                cv::RotatedRect box(center,{120.f*pose.scale,120.f*pose.scale},-pose.angle);
                cv::Point2f corners[4]; box.points(corners);
                for(int k=0;k<4;++k) cv::line(result,corners[k],corners[(k+1)%4],{0,190,255},1,cv::LINE_AA);
                std::ostringstream label; label << std::fixed << std::setprecision(1) << "score " << m.similarity
                    << " | " << pose.angle << " deg | scale " << pose.scale;
                cv::rectangle(result,{0,0,result.cols,48},{22,24,28},-1);
                cv::putText(result,label.str(),{12,31},cv::FONT_HERSHEY_SIMPLEX,0.65,{235,235,235},1,cv::LINE_AA);
                std::cout << "RESULT " << i << " score " << m.similarity << " angle " << pose.angle << " scale " << pose.scale
                    << " center " << center << " " << ms << " ms candidates " << matches.size() << '\n';
            }
            if(!cv::imwrite(output+"/"+std::to_string(i)+"_result.png",result)) throw std::runtime_error("Cannot write result");
        }
        return 0;
    } catch(const std::exception& e) {std::cerr << e.what() << '\n';return 1;}
}
