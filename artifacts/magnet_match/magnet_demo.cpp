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
cv::Rect2f featureBox(const line2Dup::Template& t,const line2Dup::Match& m,int padding) {
    float x0=1e9f,y0=1e9f,x1=-1e9f,y1=-1e9f;
    for(const auto& f:t.features){const float x=float(f.x+m.x-padding),y=float(f.y+m.y-padding);x0=std::min(x0,x);y0=std::min(y0,y);x1=std::max(x1,x);y1=std::max(y1,y);}
    return {x0,y0,x1-x0,y1-y0};
}
int diagnose(const std::string& input,const std::string& output) {
    struct Config {const char* name;int levels,image,padding;float scale;bool onePose;};
    const Config cases[]={{"L4_source_pad64",4,1,64,1,true},{"L4_source_pad256",4,1,256,1,true},
                          {"L3_M04_scale070",3,4,128,.7f,false},{"L3_M06_scale125",3,6,128,1.25f,false}};
    std::ofstream csv(output+"/diagnostic_results.csv"),geometry(output+"/template_geometry.csv");
    if(!csv || !geometry)throw std::runtime_error("Cannot open diagnostic CSV");
    csv<<"case,levels,image,padding,padded_width,padded_height,scale,poses,status,score,angle_deg,center_x,center_y,candidates,preprocess_ms,search_ms,api_total_ms\n";
    geometry<<"case,level,template_width,template_height,tl_x,tl_y,features,input_width,input_height,border,min_center_x,max_center_x,min_center_y,max_center_y,clamp_interval_feasible\n";
    for(const auto& c:cases) {
        MagnetDetector detector(input+"/moban.smd",c.levels);
        for(int a=0;a<(c.onePose?1:360);a+=2)detector.addPose(float(a),c.scale);
        std::ostringstream name;name<<'M'<<std::setfill('0')<<std::setw(2)<<c.image<<".bmp";
        cv::Mat gray=cv::imread(input+"/"+name.str(),cv::IMREAD_GRAYSCALE),padded;
        if(gray.empty())throw std::runtime_error("Missing diagnostic image");
        const int alignment=8*(1<<(c.levels-1));
        const int pw=((gray.cols+2*c.padding+alignment-1)/alignment)*alignment;
        const int ph=((gray.rows+2*c.padding+alignment-1)/alignment)*alignment;
        cv::copyMakeBorder(gray,padded,c.padding,ph-gray.rows-c.padding,c.padding,pw-gray.cols-c.padding,cv::BORDER_CONSTANT,cv::Scalar(0));
        const auto& zero=detector.getTemplates("magnet",0);
        for(int l=0;l<c.levels-1;++l) {
            const auto& t=zero[l];const int border=8*(l==0?4:8),iw=pw>>l,ih=ph>>l;
            const int maxx=iw-t.width-border,maxy=ih-t.height-border;
            geometry<<c.name<<','<<l<<','<<t.width<<','<<t.height<<','<<t.tl_x<<','<<t.tl_y<<','<<t.features.size()<<','
                    <<iw<<','<<ih<<','<<border<<','<<border<<','<<maxx<<','<<border<<','<<maxy<<','<<(maxx>=border&&maxy>=border)<<'\n';
        }
        line2Dup::MatchWorkspace workspace;line2Dup::MatchOptions options;line2Dup::MatchTimings timing;
        const auto matches=detector.match(padded,75.f,workspace,options,&timing,{"magnet"});
        cv::Mat result;cv::cvtColor(gray,result,cv::COLOR_GRAY2BGR);
        csv<<c.name<<','<<c.levels<<','<<name.str()<<','<<c.padding<<','<<pw<<','<<ph<<','<<c.scale<<','<<detector.poses.size()<<',';
        std::ostringstream text;text<<c.name;
        if(matches.empty()) {csv<<"no_match_ge75,,,,";text<<" NO MATCH >=75";}
        else {
            const auto& m=matches.front();const auto& t=detector.getTemplates("magnet",m.template_id)[0];const auto pose=detector.poses[m.template_id];
            const cv::Point2f center(m.x-c.padding-t.tl_x+detector.width*.5f*pose.scale,m.y-c.padding-t.tl_y+detector.height*.5f*pose.scale);
            csv<<"match,"<<m.similarity<<','<<pose.angle<<','<<center.x<<','<<center.y;
            for(const auto& f:t.features)cv::circle(result,{f.x+m.x-c.padding,f.y+m.y-c.padding},1,{0,255,0},-1,cv::LINE_AA);
            cv::RotatedRect box(center,{detector.width*pose.scale,detector.height*pose.scale},-pose.angle);cv::Point2f corners[4];box.points(corners);
            for(int k=0;k<4;++k)cv::line(result,corners[k],corners[(k+1)%4],{0,190,255},1,cv::LINE_AA);
            text<<" score "<<std::fixed<<std::setprecision(1)<<m.similarity<<" a="<<pose.angle;
        }
        csv<<','<<matches.size()<<','<<timing.preprocess_ms<<','<<timing.search_ms<<','<<timing.total_ms<<'\n';
        cv::rectangle(result,{0,0,result.cols,35},{22,24,28},-1);cv::putText(result,text.str(),{8,24},cv::FONT_HERSHEY_SIMPLEX,.53,{235,235,235},1,cv::LINE_AA);
        if(!cv::imwrite(output+"/"+c.name+".png",result))throw std::runtime_error("Cannot write diagnostic preview");
        std::cout<<text.str()<<" candidates="<<matches.size()<<'\n';
    }
    return 0;
}
int main(int argc,char** argv) {
    try {
        if(argc!=3 && argc!=4)throw std::runtime_error("Usage: magnet_demo ASCII_INPUT OUTPUT_DIRECTORY [--diagnose]");
        const std::string input=argv[1],output=argv[2];
        cv::setNumThreads(1);omp_set_dynamic(0);omp_set_num_threads(4);
        const bool validation=argc==4 && std::string(argv[3])=="--validate";
        if(argc==4 && !validation){if(std::string(argv[3])!="--diagnose")throw std::runtime_error("Unknown mode");return diagnose(input,output);}
        std::ofstream csv(output+"/results.csv");
        std::ofstream raw(output+"/matcher_candidates.csv");
        if(!csv || !raw)throw std::runtime_error("Cannot create output CSV");
        csv<<"levels,image,role,status,score,angle_deg,scale,center_x,center_y,bbox_x,bbox_y,bbox_w,bbox_h,corner0_x,corner0_y,corner1_x,corner1_y,corner2_x,corner2_y,corner3_x,corner3_y,candidates,preprocess_ms,search_ms,api_total_ms,template_id,feature_bbox_x,feature_bbox_y,feature_bbox_w,feature_bbox_h\n";
        raw<<"levels,image,rank,template_id,match_x,match_y,score,angle_deg,scale,feature_bbox_x,feature_bbox_y,feature_bbox_w,feature_bbox_h\n";raw<<std::setprecision(9);
        csv<<std::setprecision(9);
        std::ofstream geometry(output+"/padding_preflight.csv"),actual(output+"/actual_padding.json");
        if(!geometry || !actual)throw std::runtime_error("Cannot create preflight files");
        geometry<<"levels,template_id,level,template_width,template_height,border,required_full_width,required_full_height,padded_width,padded_height,max_x,max_y,feasible\n";
        actual<<"[\n";bool firstGeometry=true;
        const std::vector<int> levelList=validation?std::vector<int>{3}:std::vector<int>{2,3,4};
        for(int levels:levelList) {
            MagnetDetector detector(input+"/moban.smd",levels);
            const int scales=validation?17:5;const float firstScale=validation?.60f:.90f;
            for(int s=0;s<scales;++s)for(int a=0;a<360;a+=2)detector.addPose(float(a),firstScale+.05f*s);
            const int padding=validation?128:64,alignment=8*(1<<(levels-1));
            int pw=640+2*padding,ph=validation?480+2*padding:640,requiredW=0,requiredH=0;
            for(std::size_t id=0;id<detector.poses.size();++id) {
                const auto& tp=detector.getTemplates("magnet",int(id));
                for(int l=0;l<levels-1;++l){const int border=8*(l==0?4:8);requiredW=std::max(requiredW,(tp[l].width+2*border)*(1<<l));requiredH=std::max(requiredH,(tp[l].height+2*border)*(1<<l));}
            }
            if(validation){pw=std::max(pw,requiredW);ph=std::max(ph,requiredH);pw=((pw+alignment-1)/alignment)*alignment;ph=((ph+alignment-1)/alignment)*alignment;}
            if(!firstGeometry)actual<<",\n";firstGeometry=false;
            actual<<"  {\"levels\":"<<levels<<",\"poses\":"<<detector.poses.size()<<",\"required_width\":"<<requiredW<<",\"required_height\":"<<requiredH<<",\"padded_width\":"<<pw<<",\"padded_height\":"<<ph<<",\"left\":"<<padding<<",\"top\":"<<padding<<",\"right\":"<<pw-640-padding<<",\"bottom\":"<<ph-480-padding<<",\"alignment\":"<<alignment<<",\"adaptive\":"<<(validation?"true":"false")<<"}";
            for(std::size_t id=0;id<detector.poses.size();++id) {
                const auto& tp=detector.getTemplates("magnet",int(id));
                for(int l=0;l<levels-1;++l) {
                    const auto& t=tp[l];const int border=8*(l==0?4:8),maxx=(pw>>l)-t.width-border,maxy=(ph>>l)-t.height-border;
                    const bool feasible=maxx>=border && maxy>=border;
                    if(validation && !feasible)throw std::runtime_error("Expanded bank has infeasible local clamp interval");
                    geometry<<levels<<','<<id<<','<<l<<','<<t.width<<','<<t.height<<','<<border<<','<<(t.width+2*border)*(1<<l)<<','<<(t.height+2*border)*(1<<l)<<','<<pw<<','<<ph<<','<<maxx<<','<<maxy<<','<<feasible<<'\n';
                }
            }
            geometry.flush();actual.flush();
            line2Dup::MatchWorkspace workspace;line2Dup::MatchOptions options;
            for(int n=1;n<=7;++n) {
                std::ostringstream name;name<<'M'<<std::setfill('0')<<std::setw(2)<<n<<".bmp";
                cv::Mat gray=cv::imread(input+"/"+name.str(),cv::IMREAD_GRAYSCALE);
                if(gray.size()!=cv::Size(640,480))throw std::runtime_error("Unexpected image dimensions");
                // Preflight covers every bank pose; only right/bottom grow.
                cv::Mat padded;cv::copyMakeBorder(gray,padded,padding,ph-gray.rows-padding,padding,pw-gray.cols-padding,cv::BORDER_CONSTANT,cv::Scalar(0));
                line2Dup::MatchTimings timing;
                const auto matches=detector.match(padded,75.f,workspace,options,&timing,{"magnet"});
                for(std::size_t rank=0;rank<matches.size();++rank) {
                    const auto& m=matches[rank];const auto& t=detector.getTemplates("magnet",m.template_id)[0];const auto p=detector.poses[m.template_id];const auto b=featureBox(t,m,padding);
                    raw<<levels<<','<<name.str()<<','<<rank<<','<<m.template_id<<','<<m.x-padding<<','<<m.y-padding<<','<<m.similarity<<','<<p.angle<<','<<p.scale<<','<<b.x<<','<<b.y<<','<<b.width<<','<<b.height<<'\n';
                }
                raw.flush();
                cv::Mat result;cv::cvtColor(gray,result,cv::COLOR_GRAY2BGR);
                csv<<levels<<','<<name.str()<<','<<(n==1?"template_source_selfcheck":"non_source_sample")<<',';
                std::ostringstream label;
                if(matches.empty()) {
                    csv<<"no_match_ge75";for(int i=0;i<17;++i)csv<<',';
                    label<<"L"<<levels<<" NO MATCH >=75";
                } else {
                    const auto& m=matches.front();const auto& t=detector.getTemplates("magnet",m.template_id)[0];
                    const auto pose=detector.poses[m.template_id];
                    const float ox=float(m.x-padding-t.tl_x),oy=float(m.y-padding-t.tl_y);
                    const cv::Point2f center(ox+detector.width*.5f*pose.scale,oy+detector.height*.5f*pose.scale);
                    cv::RotatedRect box(center,{detector.width*pose.scale,detector.height*pose.scale},-pose.angle);
                    cv::Point2f corners[4];box.points(corners);const cv::Rect2f bbox=box.boundingRect2f();
                    csv<<"match"<<','<<m.similarity<<','<<pose.angle<<','<<pose.scale<<','<<center.x<<','<<center.y<<','
                       <<bbox.x<<','<<bbox.y<<','<<bbox.width<<','<<bbox.height;
                    for(const auto& c:corners)csv<<','<<c.x<<','<<c.y;
                    for(const auto& p:t.features)cv::circle(result,{p.x+m.x-padding,p.y+m.y-padding},1,{0,255,0},-1,cv::LINE_AA);
                    for(int i=0;i<4;++i)cv::line(result,corners[i],corners[(i+1)%4],{0,190,255},1,cv::LINE_AA);
                    cv::drawMarker(result,center,{0,190,255},cv::MARKER_CROSS,15,1,cv::LINE_AA);
                    label<<"L"<<levels<<" score "<<std::fixed<<std::setprecision(1)<<m.similarity<<" | "<<pose.angle<<" deg | "<<pose.scale;
                }
                csv<<','<<matches.size()<<','<<timing.preprocess_ms<<','<<timing.search_ms<<','<<timing.total_ms;
                if(matches.empty())csv<<",,,,,";
                else {const auto& m=matches.front();const auto b=featureBox(detector.getTemplates("magnet",m.template_id)[0],m,padding);csv<<','<<m.template_id<<','<<b.x<<','<<b.y<<','<<b.width<<','<<b.height;}
                csv<<'\n';csv.flush();
                cv::rectangle(result,{0,0,result.cols,35},{22,24,28},-1);
                cv::putText(result,label.str(),{10,24},cv::FONT_HERSHEY_SIMPLEX,.6,{235,235,235},1,cv::LINE_AA);
                const std::string path=output+"/L"+std::to_string(levels)+"_"+name.str()+".png";
                if(!cv::imwrite(path,result))throw std::runtime_error("Cannot write preview");
                std::cout<<"L"<<levels<<' '<<name.str()<<" candidates="<<matches.size()<<" api_ms="<<timing.total_ms<<' '<<label.str()<<'\n';
            }
        }
        actual<<"\n]\n";
        return 0;
    } catch(const std::exception& error){std::cerr<<error.what()<<'\n';return 1;}
}
