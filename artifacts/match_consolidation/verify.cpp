#include "../search_optimization/fixtures.hpp"
#include "../local_center_optimization/v10_reference.hpp"
#include <cstdint>
#include <cstring>
#include <map>
#include <sstream>

namespace {
using Semantic=std::tuple<std::string,int,int,std::uint32_t>;
using Record=std::tuple<std::string,int,int,std::uint32_t,int>;
using Records=std::vector<Record>;
struct Case {
    std::string dataset,name,id;
    cv::Mat image;
    float threshold;
    std::shared_ptr<line2Dup::Detector> current;
    std::shared_ptr<search_reference::Matcher> v4;
    std::shared_ptr<local_center_v10::Matcher> v10;
};
std::uint32_t bits(float value){std::uint32_t r;std::memcpy(&r,&value,sizeof(r));return r;}
float value(std::uint32_t bits){float r;std::memcpy(&r,&bits,sizeof(r));return r;}
template<class Matches> Records records(const Matches& matches) {
    Records r;r.reserve(matches.size());
    for(const auto& m:matches)r.emplace_back(m.class_id,m.x,m.y,bits(m.similarity),m.template_id);
    return r;
}
Semantic semantic(const Record& r){return {std::get<0>(r),std::get<1>(r),std::get<2>(r),std::get<3>(r)};}
std::set<Semantic> semantics(const Records& r){std::set<Semantic> s;for(const auto& m:r)s.insert(semantic(m));return s;}
// Independent map-reduction oracle. It does not call the production helper,
// sort by its grouping comparator, or use a current output to choose IDs.
Records canonical(const Records& original) {
    std::map<Semantic,int> minimum;
    for(const auto& r:original){const auto key=semantic(r);auto it=minimum.find(key);
        if(it==minimum.end())minimum.emplace(key,std::get<4>(r));
        else it->second=std::min(it->second,std::get<4>(r));}
    Records result;result.reserve(minimum.size());
    for(const auto& e:minimum)result.emplace_back(std::get<0>(e.first),std::get<1>(e.first),
        std::get<2>(e.first),std::get<3>(e.first),e.second);
    std::sort(result.begin(),result.end(),[](const Record& a,const Record& b){
        const auto ka=std::make_tuple(-value(std::get<3>(a)),std::get<4>(a),std::get<0>(a),std::get<2>(a),std::get<1>(a));
        const auto kb=std::make_tuple(-value(std::get<3>(b)),std::get<4>(b),std::get<0>(b),std::get<2>(b),std::get<1>(b));
        return ka<kb;});
    return result;
}
std::string fingerprint(const Records& records,bool ordered) {
    Records input=records;if(!ordered)std::sort(input.begin(),input.end());
    std::uint64_t h=UINT64_C(14695981039346656037);
    for(const auto& r:input){std::ostringstream s;s<<std::get<0>(r).size()<<':'<<std::get<0>(r)<<':'
        <<std::get<1>(r)<<':'<<std::get<2>(r)<<':'<<std::get<3>(r)<<':'<<std::get<4>(r)<<'\n';
        for(unsigned char b:s.str()){h^=b;h*=UINT64_C(1099511628211);}}
    std::ostringstream out;out<<std::hex<<std::setfill('0')<<std::setw(16)<<h;return out.str();
}
std::string exported(const line2Dup::Detector& detector,const std::string& id) {
    cv::FileStorage storage("memory.yml",cv::FileStorage::WRITE|cv::FileStorage::MEMORY);
    detector.writeClass(id,storage);return storage.releaseAndGetString();
}
std::vector<Case> loadCases(const std::string& bank,const std::string& dataset,bool minimal) {
    std::vector<Case> result;
    if(!minimal)for(const auto& f:search_experiment::loadFixtures()) {
        const bool led=f.dataset=="LED";
        auto reference=std::make_shared<local_center_v10::Matcher>(128,led?std::vector<int>{4,8,8}:std::vector<int>{4,8},led?20:30,led?40:60);
        reference->loadClass(exported(*f.detector,f.class_id));
        result.push_back({f.dataset,f.name,f.class_id,f.image,f.threshold,f.detector,f.reference,reference});
    }
    auto detector=std::make_shared<line2Dup::Detector>(32,std::vector<int>{4,8},20,40);
    cv::FileStorage storage(bank,cv::FileStorage::READ);if(!storage.isOpened())throw std::runtime_error("Missing public bank");
    detector->readClass(storage.root());
    const std::string id="tless_object_1";
    auto v10=std::make_shared<local_center_v10::Matcher>(32,std::vector<int>{4,8},20,40);v10->loadClassFile(bank);
    auto v4=std::make_shared<search_reference::Matcher>(32,std::vector<int>{4,8},20,40);v4->loadClass(exported(*detector,id));
    cv::FileStorage index(dataset+"/index.json",cv::FileStorage::READ);if(!index.isOpened())throw std::runtime_error("Missing dataset index");
    std::size_t development=0;
    for(const auto& n:index["test"]) {
        if(std::string(n["split"])!="development")continue;++development;
        if(minimal&&(int(n["scene_id"])!=5||int(n["image_id"])!=70))continue;
        const auto gray=cv::imread(dataset+"/"+std::string(n["rgb"]),cv::IMREAD_GRAYSCALE);
        if(gray.empty())throw std::runtime_error("Missing public image");
        cv::Mat padded;cv::copyMakeBorder(gray,padded,64,64+(16-(gray.rows+128)%16)%16,
            64,64+(16-(gray.cols+128)%16)%16,cv::BORDER_CONSTANT,cv::Scalar(0));
        result.push_back({"TLESS_dev","s"+std::to_string(int(n["scene_id"]))+"_i"+std::to_string(int(n["image_id"])),
            id,padded,50,detector,v4,v10});
    }
    if(development!=16)throw std::runtime_error("Expected exactly 16 frozen development frames");
    if(result.size()!=(minimal?1u:25u))throw std::runtime_error("Incorrect verification case count");
    return result;
}
}
int main(int argc,char** argv) {
    try {
        std::string output="artifacts/match_consolidation/verification.csv",bank="datasets/tless_train_f32/templates_tless_object_1.yml.gz",dataset="datasets/tless_tiny";
        bool minimal=false;
        for(int i=1;i<argc;++i){const std::string arg=argv[i];if(arg=="--minimal"){minimal=true;continue;}
            if(i+1==argc)throw std::runtime_error("Missing option value");const std::string val=argv[++i];
            if(arg=="--output")output=val;else if(arg=="--bank")bank=val;else if(arg=="--dataset")dataset=val;else throw std::runtime_error("Unknown option "+arg);}
        cv::setNumThreads(1);omp_set_dynamic(0);
        const auto cases=loadCases(bank,dataset,minimal);
        std::ofstream out(output);if(!out)throw std::runtime_error("Cannot create verification CSV");
        out<<"dataset,image,implementation,threads,pass,fused,repeat,original_v10_count,expected_canonical_count,actual_count,semantic_set_equal,canonical_oracle_equal,full_ordered_equal,duplicate_count,ordered_hash,expected_ordered_hash,first_mismatch\n";
        std::size_t failures=0,calls=0;
        for(const auto& f:cases){
            omp_set_num_threads(1);f.v10->resetWorkspace();
            const auto original=records(f.v10->match(f.image,f.threshold,{f.id},{},false));
            const auto expected=canonical(original);const auto expectedSemantic=semantics(original);
            const auto expectedHash=fingerprint(expected,true);
            auto record=[&](const char* name,int threads,int pass,bool fused,int repeat,const Records& actual,bool stableRequired){
                const bool set=semantics(actual)==expectedSemantic;
                const bool oracle=canonical(actual)==expected;
                const bool ordered=actual==expected;
                std::size_t mismatch=0;while(mismatch<std::min(actual.size(),expected.size())&&actual[mismatch]==expected[mismatch])++mismatch;
                out<<f.dataset<<','<<f.name<<','<<name<<','<<threads<<','<<pass<<','<<fused<<','<<repeat<<','<<original.size()<<','<<expected.size()<<','<<actual.size()<<','
                    <<set<<','<<oracle<<','<<ordered<<','<<actual.size()-semantics(actual).size()<<','<<fingerprint(actual,true)<<','<<expectedHash<<',';
                if(!ordered)out<<mismatch;out<<'\n';out.flush();
                failures+=!set||!oracle||(stableRequired&&!ordered);++calls;
            };
            record("v10_reference",1,-1,false,0,original,false);
            record("v10_reference",1,-1,true,0,records(f.v10->match(f.image,f.threshold,{f.id},{},true)),false);
            f.v4->resetWorkspace();record("v4_reference",1,-1,false,0,records(f.v4->match(f.image,f.threshold,{f.id})),false);
            line2Dup::MatchWorkspace workspace;
            const int threadMatrix[]={1,4,2,4};
            for(int pass=0;pass<4;++pass){const int threads=threadMatrix[pass];omp_set_num_threads(threads);
                for(bool fused:{false,true})for(int repeat=0;repeat<2;++repeat){auto options=search_experiment::options(7);options.fused_local_search=fused;
                    const auto actual=records(f.current->match(f.image,f.threshold,workspace,options,nullptr,{f.id}));
                    record("current_stable",threads,pass,fused,repeat,actual,true);}}
            std::cout<<"verified "<<f.dataset<<'/'<<f.name<<" old_count="<<original.size()<<" canonical="<<expected.size()<<" failures="<<failures<<'\n';
        }
        std::cout<<"verification calls="<<calls<<" failures="<<failures<<'\n';return failures?2:0;
    }catch(const std::exception& error){std::cerr<<error.what()<<'\n';return 1;}
}
