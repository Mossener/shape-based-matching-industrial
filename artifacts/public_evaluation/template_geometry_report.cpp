#include "line2Dup.h"
#include <algorithm>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <limits>
#include <map>
#include <string>
#include <vector>

namespace fs = std::filesystem;

struct Extent { int min_x=std::numeric_limits<int>::max(),min_y=std::numeric_limits<int>::max(),max_x=std::numeric_limits<int>::min(),max_y=std::numeric_limits<int>::min(); bool empty=true; };
static Extent featureExtent(const line2Dup::Template& t) {
    Extent e;
    for (const auto& f : t.features) {
        e.empty=false; e.min_x=std::min(e.min_x,f.x); e.min_y=std::min(e.min_y,f.y);
        e.max_x=std::max(e.max_x,f.x); e.max_y=std::max(e.max_y,f.y);
    }
    return e;
}
static void jsonString(std::ostream& out,const std::string& s) { out << '"'; for(char c:s) { if(c=='"'||c=='\\') out << '\\'; out << c; } out << '"'; }
int main(int argc,char** argv) {
    try {
        if (argc != 5) throw std::runtime_error("usage: template_geometry_report <class> <templates.yml.gz> <output.json> <input_width>x<input_height>");
        const std::string classId=argv[1]; const fs::path input=argv[2], output=argv[3];
        const auto dims=std::string(argv[4]); const auto x=dims.find('x'); if(x==std::string::npos) throw std::runtime_error("bad dimensions");
        const int rawWidth=std::stoi(dims.substr(0,x)), rawHeight=std::stoi(dims.substr(x+1));
        const int inputWidth=(rawWidth+128+15)/16*16, inputHeight=(rawHeight+128+15)/16*16;
        line2Dup::Detector detector(32,{4,8},20,40); detector.readClasses({classId},input.string());
        std::ofstream out(output); if(!out) throw std::runtime_error("cannot open output");
        size_t invalid=0; std::map<int,int> levelCounts; std::map<int,std::vector<int>> widths,heights,features;
        out << "{\n  \"class_id\":"; jsonString(out,classId); out << ",\n  \"template_count\":" << detector.numTemplates(classId) << ",\n  \"raw_input_size\": [" << rawWidth << ',' << rawHeight << "],\n  \"input_padding\":64,\n  \"input_size\": [" << inputWidth << ',' << inputHeight << "],\n  \"levels\": [";
        for(int id=0; id<detector.numTemplates(classId); ++id) {
            if(id) out << ','; const auto& pyramid=detector.getTemplates(classId,id); out << "\n    {\"template_id\":" << id << ",\"levels\":[";
            for(size_t l=0;l<pyramid.size();++l) {
                if(l) out << ','; const auto& t=pyramid[l]; const auto e=featureExtent(t); ++levelCounts[int(l)]; widths[int(l)].push_back(t.width); heights[int(l)].push_back(t.height); features[int(l)].push_back(int(t.features.size()));
                const int W=inputWidth >> t.pyramid_level, H=inputHeight >> t.pyramid_level;
                const int T=detector.getT(int(l)), border=8*T;
                const int maxCenterX=W-t.width-border, maxCenterY=H-t.height-border;
                const bool coarseFit=(W/T-(t.width-1)/T-1>=0) && (H/T-(t.height-1)/T-1>=0);
                const bool refine=(l+1<pyramid.size());
                const bool interval=!refine || (maxCenterX>=border && maxCenterY>=border);
                const bool declaredGeometryFit=t.width>0 && t.height>0 && !e.empty && coarseFit && interval;
                if(!declaredGeometryFit) ++invalid;
                out << "{\"level\":" << l << ",\"pyramid_level\":" << t.pyramid_level << ",\"width\":" << t.width << ",\"height\":" << t.height << ",\"tl_x\":" << t.tl_x << ",\"tl_y\":" << t.tl_y << ",\"features\":" << t.features.size() << ",\"feature_extent\":[" << (e.empty?0:e.min_x) << ',' << (e.empty?0:e.min_y) << ',' << (e.empty?0:e.max_x) << ',' << (e.empty?0:e.max_y) << "],\"feature_extent_max_plus_one\":[" << (e.empty?0:e.max_x+1) << ',' << (e.empty?0:e.max_y+1) << "],\"input_level_size\":[" << W << ',' << H << "],\"T\":" << T << ",\"refinement_level\":" << (refine?"true":"false") << ",\"refinement_center_interval\":[" << border << ',' << maxCenterX << ',' << border << ',' << maxCenterY << "],\"coarse_fit\":" << (coarseFit?"true":"false") << ",\"refinement_interval_valid\":" << (interval?"true":"false") << ",\"declared_geometry_fit\":" << (declaredGeometryFit?"true":"false") << '}';
            }
            out << "]}";
        }
        out << "\n  ],\n  \"invalid_template_levels\":" << invalid << ",\n  \"level_summary\": [";
        bool first=true; for(const auto& [level,count]:levelCounts) { if(!first) out << ','; first=false; auto mm=[](const std::vector<int>& v){return std::pair<int,int>{*std::min_element(v.begin(),v.end()),*std::max_element(v.begin(),v.end())};}; const auto w=mm(widths[level]),h=mm(heights[level]),f=mm(features[level]); out << "{\"level\":" << level << ",\"templates\":" << count << ",\"width_min\":" << w.first << ",\"width_max\":" << w.second << ",\"height_min\":" << h.first << ",\"height_max\":" << h.second << ",\"features_min\":" << f.first << ",\"features_max\":" << f.second << '}'; }
        out << "]\n}\n"; out.close(); std::cout << "templates=" << detector.numTemplates(classId) << " invalid_template_levels=" << invalid << '\n'; return invalid?2:0;
    } catch(const std::exception& e) { std::cerr << "ERROR " << e.what() << '\n'; return 1; }
}
