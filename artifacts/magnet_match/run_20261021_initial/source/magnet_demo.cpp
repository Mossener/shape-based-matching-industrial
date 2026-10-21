// Sample-specific import experiment. This does not change the matcher core.
#include "line2Dup.h"
#include <opencv2/imgcodecs.hpp>
#include <omp.h>
#include <algorithm>
#include <cmath>
#include <cstring>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <iterator>
#include <sstream>
#include <stdexcept>

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
int main(int argc,char** argv) {
    try {
        if(argc!=3)throw std::runtime_error("Usage: magnet_demo ASCII_INPUT OUTPUT_DIRECTORY");
        const std::string input=argv[1],output=argv[2];
        cv::setNumThreads(1);omp_set_dynamic(0);omp_set_num_threads(4);
        std::ofstream csv(output+"/results.csv");
        if(!csv)throw std::runtime_error("Cannot create output CSV");
        csv<<"levels,image,role,status,score,angle_deg,scale,center_x,center_y,bbox_x,bbox_y,bbox_w,bbox_h,corner0_x,corner0_y,corner1_x,corner1_y,corner2_x,corner2_y,corner3_x,corner3_y,candidates,preprocess_ms,search_ms,api_total_ms\n";
        csv<<std::setprecision(9);
        for(int levels:{2,3,4}) {
            MagnetDetector detector(input+"/moban.smd",levels);
            for(int s=0;s<5;++s)for(int a=0;a<360;a+=2)detector.addPose(float(a),.90f+.05f*s);
            line2Dup::MatchWorkspace workspace;line2Dup::MatchOptions options;
            for(int n=1;n<=7;++n) {
                std::ostringstream name;name<<'M'<<std::setfill('0')<<std::setw(2)<<n<<".bmp";
                cv::Mat gray=cv::imread(input+"/"+name.str(),cv::IMREAD_GRAYSCALE);
                if(gray.size()!=cv::Size(640,480))throw std::runtime_error("Unexpected image dimensions");
                // Common 768x640 padded input for every configuration, aligned to 4-level T.
                cv::Mat padded;cv::copyMakeBorder(gray,padded,64,96,64,64,cv::BORDER_CONSTANT,cv::Scalar(0));
                line2Dup::MatchTimings timing;
                const auto matches=detector.match(padded,75.f,workspace,options,&timing,{"magnet"});
                cv::Mat result;cv::cvtColor(gray,result,cv::COLOR_GRAY2BGR);
                csv<<levels<<','<<name.str()<<','<<(n==1?"template_source_selfcheck":"non_source_sample")<<',';
                std::ostringstream label;
                if(matches.empty()) {
                    csv<<"no_match_ge75";for(int i=0;i<17;++i)csv<<',';
                    label<<"L"<<levels<<" NO MATCH >=75";
                } else {
                    const auto& m=matches.front();const auto& t=detector.getTemplates("magnet",m.template_id)[0];
                    const auto pose=detector.poses[m.template_id];
                    const float ox=float(m.x-64-t.tl_x),oy=float(m.y-64-t.tl_y);
                    const cv::Point2f center(ox+detector.width*.5f*pose.scale,oy+detector.height*.5f*pose.scale);
                    cv::RotatedRect box(center,{detector.width*pose.scale,detector.height*pose.scale},-pose.angle);
                    cv::Point2f corners[4];box.points(corners);const cv::Rect2f bbox=box.boundingRect2f();
                    csv<<"match"<<','<<m.similarity<<','<<pose.angle<<','<<pose.scale<<','<<center.x<<','<<center.y<<','
                       <<bbox.x<<','<<bbox.y<<','<<bbox.width<<','<<bbox.height;
                    for(const auto& c:corners)csv<<','<<c.x<<','<<c.y;
                    for(const auto& p:t.features)cv::circle(result,{p.x+m.x-64,p.y+m.y-64},1,{0,255,0},-1,cv::LINE_AA);
                    for(int i=0;i<4;++i)cv::line(result,corners[i],corners[(i+1)%4],{0,190,255},1,cv::LINE_AA);
                    cv::drawMarker(result,center,{0,190,255},cv::MARKER_CROSS,15,1,cv::LINE_AA);
                    label<<"L"<<levels<<" score "<<std::fixed<<std::setprecision(1)<<m.similarity<<" | "<<pose.angle<<" deg | "<<pose.scale;
                }
                csv<<','<<matches.size()<<','<<timing.preprocess_ms<<','<<timing.search_ms<<','<<timing.total_ms<<'\n';csv.flush();
                cv::rectangle(result,{0,0,result.cols,35},{22,24,28},-1);
                cv::putText(result,label.str(),{10,24},cv::FONT_HERSHEY_SIMPLEX,.6,{235,235,235},1,cv::LINE_AA);
                const std::string path=output+"/L"+std::to_string(levels)+"_"+name.str()+".png";
                if(!cv::imwrite(path,result))throw std::runtime_error("Cannot write preview");
                std::cout<<"L"<<levels<<' '<<name.str()<<" candidates="<<matches.size()<<" api_ms="<<timing.total_ms<<' '<<label.str()<<'\n';
            }
        }
        return 0;
    } catch(const std::exception& error){std::cerr<<error.what()<<'\n';return 1;}
}
