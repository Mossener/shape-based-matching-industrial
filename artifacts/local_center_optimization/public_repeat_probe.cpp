#include "v10_reference.hpp"
#include <opencv2/imgcodecs.hpp>
#include <opencv2/imgproc.hpp>
#include <omp.h>
#include <algorithm>
#include <cstdint>
#include <cstring>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <map>
#include <set>
#include <sstream>
#include <stdexcept>
#include <tuple>

namespace {
using Semantic=std::tuple<std::string,int,int,std::uint32_t>;
using Strict=std::tuple<std::string,int,int,std::uint32_t,int>;
struct Keys {
    std::map<Semantic,std::size_t> semantic;
    std::map<Strict,std::size_t> strict;
    std::size_t count=0;
};
std::uint32_t bits(float value) { std::uint32_t b;std::memcpy(&b,&value,sizeof(b));return b; }
Keys keys(const std::vector<local_center_v10::Result>& matches) {
    Keys result; result.count=matches.size();
    for(const auto& m:matches) {
        ++result.semantic[{m.class_id,m.x,m.y,bits(m.similarity)}];
        ++result.strict[{m.class_id,m.x,m.y,bits(m.similarity),m.template_id}];
    }
    return result;
}
void suffix(std::ostream&,const Semantic&) {}
void suffix(std::ostream& s,const Strict& v) {s<<':'<<std::get<4>(v);}
template<class Map> std::string hash(const Map& map,bool multiplicity) {
    std::uint64_t h=UINT64_C(14695981039346656037);
    for(const auto& entry:map) {
        const auto& k=entry.first;std::ostringstream s;
        s<<std::get<0>(k).size()<<':'<<std::get<0>(k)<<':'<<std::get<1>(k)<<':'<<std::get<2>(k)<<':'<<std::get<3>(k);
        suffix(s,k);if(multiplicity)s<<':'<<entry.second;s<<'\n';
        for(unsigned char c:s.str()){h^=c;h*=UINT64_C(1099511628211);}
    }
    std::ostringstream s;s<<std::hex<<std::setfill('0')<<std::setw(16)<<h;return s.str();
}
template<class Map> bool equalSets(const Map& a,const Map& b) {
    if(a.size()!=b.size())return false;
    auto x=a.begin(),y=b.begin();for(;x!=a.end();++x,++y)if(x->first!=y->first)return false;
    return true;
}
template<class Map> void examples(std::ostream& out,const Map& a,const Map& b) {
    int shown=0;
    for(const auto& entry:a) {
        auto found=b.find(entry.first);const auto other=found==b.end()?0:found->second;
        if(entry.second==other)continue;
        const auto& k=entry.first;
        out<<std::get<0>(k)<<'/'<<std::get<1>(k)<<'/'<<std::get<2>(k)<<'/'<<std::get<3>(k);
        suffix(out,k);out<<':'<<entry.second<<"vs"<<other<<';';if(++shown==10)break;
    }
}
void record(std::ostream& out,int threads,const char* variant,int repeat,const Keys& result,const Keys& expected) {
    out<<threads<<','<<variant<<','<<repeat<<','<<result.count<<','<<result.semantic.size()<<','<<result.strict.size()<<','
       <<result.count-result.semantic.size()<<','<<result.count-result.strict.size()<<','
       <<equalSets(result.semantic,expected.semantic)<<','<<equalSets(result.strict,expected.strict)<<','
       <<(result.semantic==expected.semantic)<<','<<(result.strict==expected.strict)<<','<<(result.count==expected.count)<<','
       <<hash(result.semantic,false)<<','<<hash(result.strict,false)<<','<<hash(result.semantic,true)<<','<<hash(result.strict,true)<<',';
    examples(out,result.strict,expected.strict);out<<'\n';out.flush();
}
}

int main(int argc,char** argv) {
    try {
        std::string bank="datasets/tless_train_f32/templates_tless_object_1.yml.gz";
        std::string image="datasets/tless_tiny/test_primesense/000005/rgb/000070.png";
        std::string output="artifacts/local_center_optimization/public_repeat_v10.csv";
        for(int i=1;i<argc;i+=2) {
            if(i+1==argc)throw std::runtime_error("Missing option value");const std::string arg=argv[i];
            if(arg=="--bank")bank=argv[i+1];else if(arg=="--image")image=argv[i+1];
            else if(arg=="--output")output=argv[i+1];else throw std::runtime_error("Unknown option "+arg);
        }
        const auto gray=cv::imread(image,cv::IMREAD_GRAYSCALE);if(gray.empty())throw std::runtime_error("Missing image");
        const int right=64+(16-(gray.cols+128)%16)%16,bottom=64+(16-(gray.rows+128)%16)%16;
        cv::Mat padded;cv::copyMakeBorder(gray,padded,64,bottom,64,right,cv::BORDER_CONSTANT,cv::Scalar(0));
        cv::setNumThreads(1);omp_set_dynamic(0);
        local_center_v10::Matcher matcher(32,{4,8},20,40);matcher.loadClassFile(bank);
        std::ofstream out(output);if(!out)throw std::runtime_error("Cannot create output");
        out<<"threads,variant,repeat,count,semantic_keys,strict_keys,semantic_duplicates,strict_duplicates,semantic_set_equal,strict_set_equal,semantic_multiset_equal,strict_multiset_equal,count_equal,semantic_set_hash,strict_set_hash,semantic_multiset_hash,strict_multiset_hash,first10_strict_count_differences\n";
        Keys expected;bool first=true;
        for(int threads:{1,4}) {
            omp_set_num_threads(threads);
            for(bool fused:{false,true}) {
                matcher.resetWorkspace();
                for(int repeat=0;repeat<2;++repeat) {
                    const auto result=keys(matcher.match(padded,50,{"tless_object_1"},{},fused));
                    if(first){expected=result;first=false;}
                    record(out,threads,fused?"fused":"fallback",repeat,result,expected);
                    std::cout<<"V10 repeat "<<threads<<' '<<(fused?"fused":"fallback")<<' '<<repeat
                             <<" count="<<result.count<<" semantic="<<equalSets(result.semantic,expected.semantic)
                             <<" strict="<<equalSets(result.strict,expected.strict)<<'\n';
                }
            }
        }
        return 0;
    }catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}
}
