#define main unusedLedDemoMainForV11CenterTests
#include "../../../led_match/led_demo.cpp"
#undef main
#include "../v11_reference.hpp"
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
class Audit {
    std::ofstream file_;
    static std::string fresh(const std::string& path) {
        std::ifstream prior(path);
        require(!prior.good(),"Refusing to overwrite existing correctness evidence");
        return path;
    }
public:
    unsigned calls=0;
    explicit Audit(const std::string& path):file_(fresh(path)) {
        require(bool(file_),"Cannot create new correctness CSV");
        file_<<"phase,input,threads,flags,cache,expected_count,actual_count,full_ordered_equal,first_mismatch\n";
    }
    template<class Matches> void compare(const Matches& actual,const Records& expected,
            const std::string& phase,const Input& input,int threads,unsigned flags,int cache) {
        const auto got=records(actual);std::size_t first=0;
        while(first<std::min(got.size(),expected.size())&&got[first]==expected[first])++first;
        const bool equal=got==expected;
        file_<<phase<<','<<input.name<<','<<threads<<','<<flags<<','<<cache<<','
             <<expected.size()<<','<<got.size()<<','<<equal<<',';
        if(!equal)file_<<first;
        file_<<'\n';file_.flush();++calls;
        if(!equal) {
            std::ostringstream error;error<<"Full ordered mismatch "<<phase<<'/'<<input.name
                <<" flags="<<flags<<" threads="<<threads<<" cache="<<cache<<" index="<<first;
            auto describe=[&](const char* label,const Records& values) {
                error<<' '<<label<<'=';
                if(first==values.size())error<<"END";
                else {const auto& r=values[first];error<<std::get<0>(r)<<':'<<std::get<1>(r)<<':'
                    <<std::get<2>(r)<<':'<<std::get<3>(r)<<':'<<std::get<4>(r);}
            };
            describe("expected",expected);describe("actual",got);throw std::runtime_error(error.str());
        }
    }
};
Records expected(const std::vector<Fixture>& fixtures,const Input& input,unsigned flags,bool log=false) {
    const auto& f=fixtures[input.fixture];
    return records(f.baseline->match(f.image,input.threshold,flags,ids(f),input.mask,log));
}
void check(const std::vector<Fixture>& fixtures,const Input& input,const Records& oracle,
        line2Dup::MatchWorkspace& workspace,unsigned flags,bool cache,Audit& audit,
        const std::string& phase,int threads,bool log=false) {
    const auto& f=fixtures[input.fixture];line2Dup::MatchTimings timing;
    const auto found=f.candidate->match(f.image,input.threshold,workspace,options(flags,cache,log),
                                       &timing,ids(f),input.mask);
    audit.compare(found,oracle,phase,input,threads,flags,cache);
    require(std::isfinite(timing.search_ms)&&timing.search_ms>=0&&
        timing.total_ms+1e-8>=timing.preprocess_ms+timing.search_ms,"Invalid internal phase timing");
}
}
int main(int argc,char** argv) {
    try {
        static_assert(!std::is_copy_constructible<line2Dup::MatchWorkspace>::value,"Owned scratch required");
        std::string output,stage="all";
        for(int i=1;i<argc;++i) {
            const std::string key=argv[i];require(i+1<argc,"Missing argument value");
            const std::string value=argv[++i];
            if(key=="--output")output=value;else if(key=="--stage")stage=value;
            else throw std::runtime_error("Unknown argument "+key);
        }
        require(!output.empty(),"Explicit fresh --output required");
        require(stage=="all"||stage=="core"||stage=="flags"||stage=="lifetime","Unknown stage");
        literal_record_comparison_checks();
        cv::setNumThreads(1);omp_set_dynamic(0);omp_set_num_threads(1);
        auto f=fixtures();std::vector<Input> inputs;
        for(std::size_t i=0;i<f.size();++i)inputs.push_back({i,{},f[i].threshold,f[i].name});
        const std::size_t zero=inputs.size();
        cv::Mat zeroMask(f[0].image.size(),CV_8UC1,cv::Scalar(0));
        cv::Mat fullMask(f[0].image.size(),CV_8UC1,cv::Scalar(255));
        cv::Mat partial=zeroMask.clone();partial(cv::Rect(100,100,400,300)).setTo(255);
        inputs.push_back({0,zeroMask,75,"LED_zero_mask"});
        const std::size_t full=inputs.size();inputs.push_back({0,fullMask,75,"LED_full_mask"});
        const std::size_t part=inputs.size();inputs.push_back({0,partial,75,"LED_partial_mask"});
        const std::size_t empty=inputs.size();inputs.push_back({0,{},101,"LED_empty_candidates"});
        cv::Mat larger;cv::copyMakeBorder(f[0].image,larger,0,32,0,64,cv::BORDER_CONSTANT,cv::Scalar(0));
        const auto resized=f.size();f.push_back({"LED_larger_same_detector","LED",larger,75,f[0].candidate,f[0].baseline});
        const std::size_t size=inputs.size();inputs.push_back({resized,{},75,"LED_larger_same_detector"});
        Audit audit(output);line2Dup::MatchWorkspace workspace;
        if(stage=="all"||stage=="core") {
            for(int threads:{1,4,2,4}) {
                omp_set_num_threads(threads);
                for(unsigned flags:{63U,127U})for(const auto& input:inputs) {
                    const auto oracle=expected(f,input,flags);
                    const auto& fixture=f[input.fixture];
                    audit.compare(fixture.baseline->match(fixture.image,input.threshold,flags,ids(fixture),input.mask),
                        oracle,"baseline_repeat",input,threads,flags,-1);
                    for(int repeat=0;repeat<2;++repeat)for(bool cache:{false,true})
                        check(f,input,oracle,workspace,flags,cache,audit,"core",threads);
                }
                std::cout<<"core thread pass "<<threads<<" calls="<<audit.calls<<std::endl;
            }
        }
        if(stage=="all"||stage=="flags") {
            omp_set_num_threads(4);
            for(unsigned flags=0;flags<128;++flags)for(auto i:{std::size_t(0),zero,std::size_t(8),std::size_t(1),std::size_t(26),size}) {
                const auto oracle=expected(f,inputs[i],flags);
                for(bool cache:{false,true})check(f,inputs[i],oracle,workspace,flags,cache,audit,"flags",4);
            }
            for(auto i:{full,part,empty,std::size_t(0)})for(unsigned flags:{0U,55U,127U}) {
                const auto oracle=expected(f,inputs[i],flags);
                for(bool cache:{false,true})check(f,inputs[i],oracle,workspace,flags,cache,audit,"mask_restore",4);
            }
            const auto oracle=expected(f,inputs[0],127,true);
            for(bool cache:{false,true})check(f,inputs[0],oracle,workspace,127,cache,audit,"log_flag",4,true);
            std::cout<<"flags complete calls="<<audit.calls<<std::endl;
        }
        if(stage=="all"||stage=="lifetime") {
            omp_set_num_threads(4);std::vector<Records> oracle;
            for(const auto& input:inputs)oracle.push_back(expected(f,input,127));
            require(oracle[zero].empty()&&oracle[empty].empty(),"Negative baseline input produced output");
            require(oracle[0]==oracle[full],"Full mask differs from empty mask baseline");
            require(!oracle[26].empty(),"Synthetic zero-maxima baseline unexpectedly empty");
            for(const auto& record:oracle[26])require(std::get<3>(record)==0,
                "Synthetic zero-maxima fixture produced a nonzero score");
            check(f,inputs[0],oracle[0],workspace,127,true,audit,"pre_move",4);
            line2Dup::MatchWorkspace moved(std::move(workspace));
            check(f,inputs[8],oracle[8],moved,127,true,audit,"move_constructed",4);
            check(f,inputs[1],oracle[1],workspace,127,true,audit,"moved_from_reused",4);
            line2Dup::MatchWorkspace assigned;
            check(f,inputs[8],oracle[8],assigned,127,true,audit,"assignment_destination_populated",4);
            assigned=std::move(moved);
            check(f,inputs[0],oracle[0],assigned,127,true,audit,"move_assigned",4);
            check(f,inputs[size],oracle[size],moved,127,true,audit,"assignment_source_reused",4);
            require(!line2Dup::MatchOptions().reuse_local_centers,"Experiment default must remain explicit off");
            for(auto i:{std::size_t(0),std::size_t(8),std::size_t(1),std::size_t(0)}) {
                const auto& input=inputs[i];const auto& fixture=f[input.fixture];
                const auto baseline=records(fixture.baseline->legacyMatch(fixture.image,input.threshold,ids(fixture),input.mask));
                audit.compare(fixture.candidate->match(fixture.image,input.threshold,ids(fixture),input.mask),baseline,
                              "legacy_default",input,4,127,0);
                const auto actual=fixture.candidate->match(fixture.image,input.threshold,assigned,
                    line2Dup::MatchOptions(),nullptr,ids(fixture),input.mask);
                audit.compare(actual,baseline,"explicit_default",input,4,127,0);
            }
            const std::array<std::size_t,6> route{{0,8,1,zero,size,0}};
            std::vector<Records> floatOracle;
            for(const auto& input:inputs)floatOracle.push_back(expected(f,input,55));
            auto worker=[&](bool reverse) {
                omp_set_num_threads(1);line2Dup::MatchWorkspace own;
                std::vector<std::tuple<std::size_t,unsigned,std::vector<line2Dup::Match>>> result;
                for(std::size_t step=0;step<route.size();++step) {
                    const auto i=route[reverse?route.size()-1-step:step];const auto& input=inputs[i];const auto& fixture=f[input.fixture];
                    for(unsigned flags:{127U,55U})result.emplace_back(i,flags,fixture.candidate->match(
                        fixture.image,input.threshold,own,options(flags,true),nullptr,ids(fixture),input.mask));
                }
                return result;
            };
            auto a=std::async(std::launch::async,worker,false),b=std::async(std::launch::async,worker,true);
            for(auto result:{a.get(),b.get()})for(const auto& item:result) {
                const auto i=std::get<0>(item);const auto flags=std::get<1>(item);
                audit.compare(std::get<2>(item),flags==127?oracle[i]:floatOracle[i],"concurrent",inputs[i],1,flags,1);
            }
            std::cout<<"lifetime complete calls="<<audit.calls<<std::endl;
        }
        std::cout<<"PASS V11 center ordered matcher contract stage="<<stage<<" calls="<<audit.calls<<'\n';return 0;
    } catch(const std::exception& error) {
        std::cerr<<"FAIL V11 center ordered matcher contract: "<<error.what()<<'\n';return 1;
    }
}
