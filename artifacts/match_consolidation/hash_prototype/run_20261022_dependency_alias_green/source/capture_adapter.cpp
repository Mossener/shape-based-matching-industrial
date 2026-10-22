// Private exact-V11 capture/reference adapter. No timing is evidence here.
#ifndef SBM_CAPTURE
#error Build with explicit SBM_CAPTURE=0 or 1
#endif
#define main unusedLedDemoMainForPrivateTraceCapture
#include "led_demo.cpp"
#undef main
#include "trace_io.hpp"
#if SBM_CAPTURE
#include "capture_hook.hpp"
#endif
#include <filesystem>
#include <regex>
#include <fcntl.h>
#include <sys/stat.h>
#ifdef _WIN32
#include <io.h>
#else
#include <unistd.h>
#endif

namespace fs=std::filesystem;
namespace {
void need(bool value,const char* message){if(!value)throw std::runtime_error(message);}
std::uint32_t score_bits(float value){std::uint32_t out;std::memcpy(&out,&value,4);return out;}
template<class Matches>std::vector<hash_proto::Match> copied(const Matches& matches){
    std::vector<hash_proto::Match> out;out.reserve(matches.size());
    for(const auto& m:matches)out.push_back({m.x,m.y,m.similarity,m.class_id,m.template_id});
    return out;
}
bool same(const std::vector<hash_proto::Match>& a,const std::vector<hash_proto::Match>& b){
    if(a.size()!=b.size())return false;
    for(std::size_t i=0;i<a.size();++i)if(a[i].x!=b[i].x || a[i].y!=b[i].y ||
        a[i].class_id!=b[i].class_id || a[i].template_id!=b[i].template_id ||
        score_bits(a[i].similarity)!=score_bits(b[i].similarity))return false;
    return true;
}
void write_new(const fs::path& path,const hash_proto::Trace& trace){
    // Serialize before reserving a new file; invalid data emits no trace.
    std::ostringstream bytes(std::ios::binary);hash_proto::write_trace(bytes,trace);
    const std::string data=bytes.str();
#ifdef _WIN32
    const int fd=_wopen(path.c_str(),_O_CREAT|_O_EXCL|_O_WRONLY|_O_BINARY,_S_IREAD|_S_IWRITE);
#else
    const int fd=::open(path.c_str(),O_CREAT|O_EXCL|O_WRONLY,0600);
#endif
    need(fd>=0,"Trace output must be new and writable");
    bool okay=true;std::size_t position=0;
    while(position<data.size()){
        const unsigned count=static_cast<unsigned>(std::min<std::size_t>(data.size()-position,1U<<24));
#ifdef _WIN32
        const int written=_write(fd,data.data()+position,count);
#else
        const auto written=::write(fd,data.data()+position,count);
#endif
        if(written<=0){okay=false;break;}position+=static_cast<std::size_t>(written);
    }
#ifdef _WIN32
    if(_close(fd)!=0)okay=false;
#else
    if(::close(fd)!=0)okay=false;
#endif
    need(okay,"Trace write/close failed; preserve partial evidence");
}
struct Input {
    fs::path root,image,bank;std::string dataset,case_id,scenario,class_id;
    float threshold;int features;std::vector<int> steps;float weak,strong;
};
Input read_config(const fs::path& path){
    cv::FileStorage file(path.string(),cv::FileStorage::READ);need(file.isOpened(),"Config missing");
    need(int(file["schema_version"])==1 && int(file["flags"])==127 &&
         int(file["cv_threads"])==1 && int(file["omp_threads"])==4,"Unsupported config constants");
    Input in;in.root=fs::canonical(std::string(file["repo_root"]));
    need(in.root.is_absolute(),"Absolute repository required");
    in.dataset=std::string(file["dataset"]);in.case_id=std::string(file["case_id"]);
    in.scenario=std::string(file["scenario"]);in.threshold=float(file["matcher_threshold"]);
    const auto split=std::string(file["split"]);
    std::string expected_image,expected_bank;
    if(in.dataset=="LED"){
        need(std::regex_match(in.case_id,std::regex("LED_[1-8]")) && split=="legacy" &&
             in.scenario=="legacy" && in.threshold==75,"LED scope differs");
        expected_image="LED/"+in.case_id.substr(4)+".bmp";expected_bank="LED/ku.smd";
        in.class_id="LED";in.features=128;in.steps={4,8,8};in.weak=20;in.strong=40;
    }else if(in.dataset=="case1"){
        need(in.case_id=="case1" && split=="legacy" && in.scenario=="legacy" &&
             in.threshold==90,"case1 scope differs");
        expected_image="test/case1/test.png";expected_bank="test/case1/test_templ.yaml";
        in.class_id="test";in.features=128;in.steps={4,8};in.weak=30;in.strong=60;
    }else{
        std::smatch matched;
        need(in.dataset=="tless_tiny" && split=="development" && int(file["object_id"])==1 &&
             std::regex_match(in.case_id,matched,std::regex("tiny_s([0-9]+)_i([0-9]+)")) &&
             ((in.scenario=="quality_actual85" && in.threshold==85) ||
              (in.scenario=="stress_coarse50" && in.threshold==50)),"Tiny scope differs");
        const int scene=std::stoi(matched[1].str()),image=std::stoi(matched[2].str());
        cv::FileStorage index((in.root/"datasets/tless_tiny/index.json").string(),cv::FileStorage::READ);
        need(index.isOpened(),"Tiny index missing");int found=0;
        for(const auto& frame:index["test"]){
            // Never construct an RGB path until development metadata matches.
            if(std::string(frame["split"])!="development" || int(frame["scene_id"])!=scene ||
               int(frame["image_id"])!=image)continue;
            ++found;expected_image="datasets/tless_tiny/"+std::string(frame["rgb"]);
        }
        need(found==1,"Tiny development identity absent/duplicated");
        expected_bank="datasets/tless_train_f32/templates_tless_object_1.yml.gz";
        in.class_id="tless_object_1";in.features=32;in.steps={4,8};in.weak=20;in.strong=40;
    }
    need(std::string(file["image"])==expected_image && std::string(file["bank"])==expected_bank,
         "Config image/bank identity differs from frozen scope");
    in.image=fs::canonical(in.root/expected_image);in.bank=fs::canonical(in.root/expected_bank);
    need(in.image.generic_string().compare(0,in.root.generic_string().size()+1,
         in.root.generic_string()+"/")==0 && in.bank.generic_string().compare(0,
         in.root.generic_string().size()+1,in.root.generic_string()+"/")==0,"Input escapes repository");
    return in;
}
}
int main(int argc,char** argv){
    try{
        if(argc==3 && std::string(argv[1])=="--validate-config"){
            (void)read_config(fs::absolute(argv[2]));
            std::cout<<"{\"passed\":true,\"scope_validation_only\":true,\"image_decodes\":0,\"matcher_calls\":0}\n";
            return 0;
        }
        need(argc==5 && std::string(argv[1])=="--config" && std::string(argv[3])=="--output",
             "Usage: capture_adapter --config CONFIG --output NEW_TRACE");
        const fs::path output=fs::absolute(argv[4]);need(!fs::exists(output),"Trace output exists");
        const auto in=read_config(fs::absolute(argv[2]));
        cv::setNumThreads(1);omp_set_dynamic(0);omp_set_num_threads(4);
        // Detector has no virtual destructor. Shared ownership preserves the
        // derived SMD deleter when converting to the base-facing handle.
        std::shared_ptr<line2Dup::Detector> detector;
        if(in.dataset=="LED"){
            auto smd=std::make_shared<SmdDetector>(in.bank.string(),3);
            for(int s=0;s<5;++s)for(int a=0;a<360;a+=2)smd->addPose(float(a),.9f+.05f*s);
            need(smd->numTemplates()==900,"LED bank count changed");detector=smd;
        }else{
            detector.reset(new line2Dup::Detector(in.features,in.steps,in.weak,in.strong));
            cv::FileStorage bank(in.bank.string(),cv::FileStorage::READ);need(bank.isOpened(),"Bank missing");
            detector->readClass(bank.root());
            need(detector->numTemplates()==(in.dataset=="case1"?361:2212),"Frozen bank count changed");
        }
        const auto image=cv::imread(in.image.string(),in.dataset=="case1"?cv::IMREAD_COLOR:cv::IMREAD_GRAYSCALE);
        need(!image.empty(),"Image decode failed");cv::Mat padded;
        if(in.dataset=="case1"){
            cv::copyMakeBorder(image,padded,250,250,250,250,cv::BORDER_CONSTANT,cv::Scalar(0));
            padded=padded(cv::Rect(0,0,padded.cols/16*16,padded.rows/16*16)).clone();
        }else{
            const int bottom=64+(in.dataset=="LED"?0:(16-(image.rows+128)%16)%16);
            const int right=64+(in.dataset=="LED"?0:(16-(image.cols+128)%16)%16);
            cv::copyMakeBorder(image,padded,64,bottom,64,right,cv::BORDER_CONSTANT,cv::Scalar(0));
            const int alignment=in.dataset=="LED"?32:16;
            need(padded.rows%alignment==0 && padded.cols%alignment==0,"Image alignment differs");
        }
        line2Dup::MatchWorkspace workspace;line2Dup::MatchOptions options;
        options.log_timing=false;hash_proto::Trace trace;
#if SBM_CAPTURE
        capture_trace::arm();
#endif
        const auto matches=detector->match(padded,in.threshold,workspace,options,nullptr,{in.class_id});
#if SBM_CAPTURE
        trace=capture_trace::take();need(same(trace.output,copied(matches)),"Captured/returned full output differs");
#else
        trace.output=copied(matches);
#endif
        write_new(output,trace);
        std::cout<<"{\"passed\":true,\"capture\":"<<(SBM_CAPTURE?"true":"false")
                 <<",\"input_count\":"<<trace.input.size()<<",\"output_count\":"<<trace.output.size()
                 <<",\"matcher_calls\":1,\"performance_measurement\":false}\n";
        return 0;
    }catch(const std::exception& error){
#if SBM_CAPTURE
        capture_trace::cancel();
#endif
        std::cerr<<"CAPTURE FAILED: "<<error.what()<<'\n';return 1;
    }
}
