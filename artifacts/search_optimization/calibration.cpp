// Compare two unchanged workloads on the immutable original matcher.
#define main calibrationUnusedLedMain
#include "../led_match/led_demo.cpp"
#undef main
#include "../../tests/reference_matcher.hpp"
#include <memory>

namespace {
using CalibrationClock=std::chrono::steady_clock;
struct Workload {
    std::string name;
    cv::Mat input;
    response_reference::Matcher* matcher;
    std::string id;
    float threshold;
};
std::string readText(const std::string& path) {
    std::ifstream stream(path);
    if(!stream) throw std::runtime_error("Cannot read "+path);
    return std::string(std::istreambuf_iterator<char>(stream),{});
}
void requireImage(const cv::Mat& image,const std::string& name) {
    if(image.empty()) throw std::runtime_error("Missing image "+name);
}
}
int main(int argc,char** argv) {
    try {
        if(argc==2 && std::string(argv[1])=="--describe") {
            std::cout<<"Immutable-original calibration: case1 (361 templates, 2 levels, threshold90)"
                     <<" and LED 1..8 (900 templates, 3 levels, threshold75); CV1/OMP4;"
                     <<" 2 warmup + 15 measured rounds, interleaved/reversed workload order.\n";
            return 0;
        }
        if(argc!=2) throw std::runtime_error("Usage: calibration.exe OUTPUT_DIRECTORY | --describe");
        const std::string output=argv[1];
        cv::setNumThreads(1); omp_set_dynamic(0); omp_set_num_threads(4);
        response_reference::Matcher case1(128,{4,8},30,60);
        case1.loadClass(readText("test/case1/test_templ.yaml"));
        line2Dup::Detector countCase1(128,{4,8});
        cv::FileStorage caseStorage("test/case1/test_templ.yaml",cv::FileStorage::READ);
        countCase1.readClass(caseStorage.root());
        if(countCase1.numTemplates("test")!=361) throw std::runtime_error("case1 template count changed");
        cv::Mat original=cv::imread("test/case1/test.png",cv::IMREAD_COLOR);
        requireImage(original,"case1");
        cv::Mat padded;
        cv::copyMakeBorder(original,padded,250,250,250,250,cv::BORDER_CONSTANT,cv::Scalar::all(0));
        cv::Mat caseInput=padded(cv::Rect(0,0,padded.cols/16*16,padded.rows/16*16)).clone();
        SmdDetector led("LED/ku.smd",3);
        for(int scale=0;scale<5;++scale) for(int angle=0;angle<360;angle+=2)
            led.addPose(float(angle),0.9f+0.05f*scale);
        cv::FileStorage ledStorage("",cv::FileStorage::WRITE|cv::FileStorage::MEMORY);
        led.writeClass("LED",ledStorage);
        response_reference::Matcher ledReference(128,{4,8,8},20,40);
        ledReference.loadClass(ledStorage.releaseAndGetString());
        std::vector<Workload> workloads{{"case1",caseInput,&case1,"test",90}};
        for(int image=1;image<=8;++image) {
            auto gray=cv::imread("LED/"+std::to_string(image)+".bmp",cv::IMREAD_GRAYSCALE);
            requireImage(gray,"LED"+std::to_string(image));
            cv::Mat ledInput;
            cv::copyMakeBorder(gray,ledInput,64,64,64,64,cv::BORDER_CONSTANT,cv::Scalar(0));
            workloads.push_back({"LED"+std::to_string(image),ledInput,&ledReference,"LED",75});
        }
        cv::FileStorage metadata(output+"/config.json",cv::FileStorage::WRITE|cv::FileStorage::FORMAT_JSON);
        metadata<<"opencv_threads"<<1<<"openmp_threads"<<4<<"warmups"<<2<<"measured_rounds"<<15
                <<"implementation"<<"immutable original in both workloads"
                <<"timing_scope"<<"match only; total includes reference adapter log capture and Result conversion"
                <<"ordering"<<"rotate start and alternate direction each round; nine interleaved workloads"
                <<"workloads"<<"[";
        for(const auto& w:workloads) {
            const auto& d=w.id=="test"?countCase1:static_cast<const line2Dup::Detector&>(led);
            metadata<<"{"<<"name"<<w.name<<"width"<<w.input.cols<<"height"<<w.input.rows
                    <<"channels"<<w.input.channels()<<"templates"<<d.numTemplates(w.id)
                    <<"threshold"<<w.threshold<<"features"<<"[";
            for(const auto& templ:d.getTemplates(w.id,0)) metadata<<int(templ.features.size());
            metadata<<"]"<<"strides"<<"[";
            for(int level=0;level<d.pyramidLevels();++level) metadata<<d.getT(level);
            metadata<<"]"<<"}";
        }
        metadata<<"]"; metadata.release();
        std::ofstream raw(output+"/raw.csv");
        if(!raw) throw std::runtime_error("Create output directory first");
        raw<<"workload,phase,round,order,preprocess_ms,search_ms,total_ms,matches\n"<<std::setprecision(12);
        for(int round=0;round<17;++round) for(int order=0;order<int(workloads.size());++order) {
            const int n=int(workloads.size());
            const int index=(round+(round%2?n-order:order))%n;
            const auto& w=workloads[index];
            const auto start=CalibrationClock::now();
            auto result=w.matcher->match(w.input,w.threshold,{w.id});
            const auto total=std::chrono::duration<double,std::milli>(CalibrationClock::now()-start).count();
            const auto t=w.matcher->lastTimings();
            if(result.empty()) throw std::runtime_error("No positive match for "+w.name);
            raw<<w.name<<','<<(round<2?"warmup":"measured")<<','<<(round<2?round:round-2)
               <<','<<order<<','<<t.preprocess_ms<<','<<t.search_ms<<','<<total<<','<<result.size()<<'\n';
        }
        std::cout<<"Calibration complete: 153 original calls; CSV at "<<output<<"/raw.csv\n";
        return 0;
    } catch(const std::exception& e) {std::cerr<<e.what()<<'\n';return 1;}
}
