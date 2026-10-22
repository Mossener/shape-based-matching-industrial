#define main unusedLedDemoMainForV11CenterTests
#include "../../led_match/led_demo.cpp"
#undef main
#include "v11_reference.hpp"
#include <array>
#include <cstdint>
#include <future>
#include <memory>
#include <set>
#include <tuple>
#include <type_traits>

namespace {
using Record=std::tuple<std::string,int,int,std::uint32_t,int>;
using Records=std::vector<Record>;
void require(bool ok,const std::string& message) {
    if(!ok)throw std::runtime_error(message);
}
std::uint32_t bits(float value) {
    std::uint32_t out;static_assert(sizeof(out)==sizeof(value),"Float32 required");
    std::memcpy(&out,&value,sizeof(out));return out;
}
template<class Matches> Records records(const Matches& values) {
    Records out;out.reserve(values.size());
    for(const auto& m:values)out.emplace_back(m.class_id,m.x,m.y,bits(m.similarity),m.template_id);
    return out;
}
void literal_record_comparison_checks() {
    const Records expected={{"A",2,3,0x3f800001U,7},{"B",4,5,0x80000000U,9}};
    require(records(std::vector<local_center_v11::Result>{{2,3,readAt<float>(
        std::vector<unsigned char>{1,0,128,63},0),"A",7},{4,5,-0.f,"B",9}})==expected,
        "record conversion lost an ordered field or float32 bits");
    auto changed=expected;std::swap(changed[0],changed[1]);
    require(changed!=expected,"ordered comparison ignored vector order");
    changed=expected;std::get<0>(changed[0])="B";require(changed!=expected,"class ignored");
    changed=expected;std::get<1>(changed[0])=3;require(changed!=expected,"x ignored");
    changed=expected;std::get<2>(changed[0])=4;require(changed!=expected,"y ignored");
    changed=expected;std::get<3>(changed[0])^=1;require(changed!=expected,"float bit ignored");
    changed=expected;std::get<4>(changed[0])=8;require(changed!=expected,"template ID ignored");
    changed=expected;changed.pop_back();require(changed!=expected,"missing record ignored");
    changed=expected;changed.push_back(expected[0]);require(changed!=expected,"extra duplicate ignored");
}
struct Fixture {
    std::string name,id;cv::Mat image;float threshold;
    std::shared_ptr<line2Dup::Detector> candidate;
    std::shared_ptr<local_center_v11::Matcher> baseline;
};
std::vector<std::string> ids(const Fixture& fixture) {
    return fixture.id.empty()?std::vector<std::string>{}:std::vector<std::string>{fixture.id};
}
std::string exported(const line2Dup::Detector& detector,const std::string& id) {
    cv::FileStorage storage("v11_center_memory.yml",cv::FileStorage::WRITE|cv::FileStorage::MEMORY);
    detector.writeClass(id,storage);return storage.releaseAndGetString();
}
class ZeroDetector : public line2Dup::Detector {
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
std::vector<Fixture> fixtures() {
    std::vector<Fixture> result;
    auto led=std::make_shared<SmdDetector>("LED/ku.smd",3);
    for(int scale=0;scale<5;++scale)for(int angle=0;angle<360;angle+=2)
        led->addPose(float(angle),.9f+.05f*scale);
    require(led->numTemplates()==900,"LED bank must retain all 900 poses");
    auto ledBase=std::make_shared<local_center_v11::Matcher>(128,std::vector<int>{4,8,8},20,40);
    ledBase->loadClass(exported(*led,"LED"));
    for(int i=1;i<=8;++i) {
        const auto image=cv::imread("LED/"+std::to_string(i)+".bmp",cv::IMREAD_GRAYSCALE);
        require(!image.empty(),"Missing LED image");cv::Mat padded;
        cv::copyMakeBorder(image,padded,64,64,64,64,cv::BORDER_CONSTANT,cv::Scalar(0));
        require(padded.rows%32==0&&padded.cols%32==0,"LED dimensions changed");
        result.push_back({"LED_"+std::to_string(i),"LED",padded,75,led,ledBase});
    }
    auto shape=std::make_shared<line2Dup::Detector>(128,std::vector<int>{4,8},30,60);
    cv::FileStorage bank("test/case1/test_templ.yaml",cv::FileStorage::READ);
    require(bank.isOpened(),"Missing case1 bank");shape->readClass(bank.root());
    require(shape->numTemplates()==361,"case1 bank must retain all 361 templates");
    auto shapeBase=std::make_shared<local_center_v11::Matcher>(128,std::vector<int>{4,8},30,60);
    shapeBase->loadClass(exported(*shape,"test"));
    const auto color=cv::imread("test/case1/test.png",cv::IMREAD_COLOR);
    require(!color.empty(),"Missing case1 image");cv::Mat padded;
    cv::copyMakeBorder(color,padded,250,250,250,250,cv::BORDER_CONSTANT,cv::Scalar(0));
    padded=padded(cv::Rect(0,0,padded.cols/16*16,padded.rows/16*16)).clone();
    result.push_back({"case1","test",padded,90,shape,shapeBase});
    const std::string tiny="datasets/tless_tiny",tinyBank="datasets/tless_train_f32/templates_tless_object_1.yml.gz";
    auto target=std::make_shared<line2Dup::Detector>(32,std::vector<int>{4,8},20,40);
    cv::FileStorage source(tinyBank,cv::FileStorage::READ);
    require(source.isOpened(),"Missing fixed tiny bank");target->readClass(source.root());
    require(target->numTemplates()==2212,"Tiny legacy bank changed");
    auto targetBase=std::make_shared<local_center_v11::Matcher>(32,std::vector<int>{4,8},20,40);
    targetBase->loadClassFile(tinyBank);
    cv::FileStorage index(tiny+"/index.json",cv::FileStorage::READ);
    require(index.isOpened(),"Missing tiny index");std::size_t development=0;
    for(const auto& frame:index["test"]) {
        // Filter metadata before constructing a path or decoding an image.
        if(std::string(frame["split"])!="development")continue;
        ++development;
        const auto image=cv::imread(tiny+"/"+std::string(frame["rgb"]),cv::IMREAD_GRAYSCALE);
        require(!image.empty(),"Missing tiny development image");
        cv::copyMakeBorder(image,padded,64,64+(16-(image.rows+128)%16)%16,
            64,64+(16-(image.cols+128)%16)%16,cv::BORDER_CONSTANT,cv::Scalar(0));
        result.push_back({"tiny_s"+std::to_string(int(frame["scene_id"]))+"_i"+
            std::to_string(int(frame["image_id"])),"tless_object_1",padded,85,target,targetBase});
    }
    require(development==16&&result.size()==25,"Fixed 25-case matrix changed");
    // Two classes in one Detector exercise class transitions within one call,
    // using the same immutable contour bank and the original LED image.
    auto multi=std::make_shared<line2Dup::Detector>(128,std::vector<int>{4,8,8},20,40);
    auto multiBase=std::make_shared<local_center_v11::Matcher>(128,std::vector<int>{4,8,8},20,40);
    const auto ledYaml=exported(*led,"LED");
    for(const std::string id:{"LED_A","LED_B"}) {
        cv::FileStorage memory(ledYaml,cv::FileStorage::READ|cv::FileStorage::MEMORY);
        multi->readClass(memory.root(),id);multiBase->loadClass(ledYaml,id);
    }
    require(multi->numTemplates()==1800,"Multi-class fixture lost a template");
    result.push_back({"LED_two_classes","",result[0].image,75,multi,multiBase});
    auto zero=std::make_shared<ZeroDetector>();
    auto zeroBase=std::make_shared<local_center_v11::Matcher>(1,std::vector<int>{4,8},20,40);
    zeroBase->loadClass(exported(*zero,"zero"));
    // A dedicated legal one-feature bank and blank 256x256 image allow actual
    // all-zero LocalMaximum results to survive threshold -1. The existing
    // fixture banks/features/thresholds are unchanged. L0 W=64, and feature0
    // has last logical row59. This feature's 16-byte path reaches offset3835;
    // even a conservative 23-byte read bound3842 fits its 4096-byte plane.
    // This bounded single-feature fixture is not a general safety proof.
    result.push_back({"synthetic_zero_maxima","zero",cv::Mat(256,256,CV_8UC1,cv::Scalar(0)),
                      -1,zero,zeroBase});
    return result;
}
struct Input {std::size_t fixture;cv::Mat mask;float threshold;std::string name;};
line2Dup::MatchOptions options(unsigned flags,bool cache,bool log=false) {
    line2Dup::MatchOptions out;
    out.separable_spread=(flags&1)!=0;out.fused_response=(flags&2)!=0;
    out.reuse_buffers=(flags&4)!=0;out.integer_local_max=(flags&8)!=0;
    out.direct_8bit_search=(flags&16)!=0;out.reuse_search_buffers=(flags&32)!=0;
    out.fused_local_search=(flags&64)!=0;out.reuse_local_centers=cache;out.log_timing=log;
    return out;
}
}
