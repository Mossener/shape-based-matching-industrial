// Included once with the exact-wrapper's private line2Dup macro still active.
// Historical adapters are exact source blocks with namespace wrappers only.
#include "fixture_banks.hpp"
#include <algorithm>
#include <cmath>
#include <cstring>
#include <fstream>
#include <iostream>
#include <iterator>
#include <stdexcept>
#include "generated_fixtures/led.hpp"
#include "generated_fixtures/magnet.hpp"

namespace postprocess_fixture_banks {
namespace {
void requireBank(bool value,const char* message) {
    if(!value)throw std::runtime_error(message);
}
std::string exported(const line2Dup::Detector& detector,const std::string& id) {
    cv::FileStorage storage("postprocess_fixture_memory.yml",cv::FileStorage::WRITE|cv::FileStorage::MEMORY);
    requireBank(storage.isOpened(),"Cannot create fixture-bank memory storage");
    detector.writeClass(id,storage);
    return storage.releaseAndGetString();
}
class ZeroDetector:public line2Dup::Detector {
public:
    ZeroDetector():Detector(1,{4,8},20,40) {
        std::vector<line2Dup::Template> levels(2);
        for(int l=0;l<2;++l) {
            auto& t=levels[l];t.width=16>>l;t.height=16>>l;
            t.tl_x=t.tl_y=0;t.pyramid_level=l;
            t.features.push_back(line2Dup::Feature(0,0,0));
            t.features.back().theta=0;
        }
        class_templates["zero"].push_back(levels);
    }
};
}
Bank led(const std::string& smd_path) {
    postprocess_fixture_sources::led::SmdDetector detector(smd_path,3);
    for(int s=0;s<5;++s)for(int a=0;a<360;a+=2)
        detector.addPose(float(a),.9f+.05f*s);
    requireBank(detector.numTemplates()==900 && detector.poses.size()==900,"Fixed LED pose bank changed");
    Bank result;result.templates=900;result.yaml=exported(detector,"LED");return result;
}
Bank zero() {
    const ZeroDetector detector;Bank result;
    result.templates=1;result.yaml=exported(detector,"zero");return result;
}
Bank magnet(const std::string& smd_path) {
    postprocess_fixture_sources::magnet::MagnetDetector detector(smd_path,3);
    for(int s=0;s<17;++s)for(int a=0;a<360;a+=2)
        detector.addPose(float(a),.60f+.05f*s);
    requireBank(detector.numTemplates()==3060 && detector.poses.size()==3060,"Fixed magnet pose bank changed");
    Bank result;result.templates=3060;int requiredW=0,requiredH=0;
    for(int id=0;id<result.templates;++id) {
        const auto& levels=detector.getTemplates("magnet",id);
        requireBank(levels.size()==3,"Magnet pyramid count changed");
        for(int l=0;l<2;++l) {
            const auto& t=levels[l];const int border=8*(l==0?4:8);
            requiredW=std::max(requiredW,(t.width+2*border)*(1<<l));
            requiredH=std::max(requiredH,(t.height+2*border)*(1<<l));
        }
    }
    requireBank(requiredW==816 && requiredH==816,"Historical magnet bank padding requirement changed");
    result.padded_width=((std::max(640+256,requiredW)+31)/32)*32;
    result.padded_height=((std::max(480+256,requiredH)+31)/32)*32;
    requireBank(result.padded_width==896 && result.padded_height==832,"Fixed magnet padded size changed");
    for(int id=0;id<result.templates;++id)for(int l=0;l<2;++l) {
        const auto& t=detector.getTemplates("magnet",id)[l];const int border=8*(l==0?4:8);
        const int maxx=(result.padded_width>>l)-t.width-border;
        const int maxy=(result.padded_height>>l)-t.height-border;
        requireBank(maxx>=border && maxy>=border,"Magnet local-refinement interval is infeasible");
        result.refinements.push_back({id,l,t.width,t.height,border,
            (t.width+2*border)*(1<<l),(t.height+2*border)*(1<<l),maxx,maxy});
    }
    requireBank(result.refinements.size()==6120,"Magnet refinement coverage changed");
    result.yaml=exported(detector,"magnet");return result;
}
}
