// Captured numeric records -> actual frozen Match -> both actual helpers.
// No Detector object, core.cpp link, image decode or template-bank read.
#include "generated/baseline/line2Dup.h"
#include "generated/candidate/hash_consolidation.hpp"
#include "evidence.hpp"
#include <fstream>
#include <iterator>
#include <iostream>

namespace {
using postprocess_evidence::require;
class Reader {
    std::vector<unsigned char> bytes_;std::size_t position_=0;
public:
    explicit Reader(const std::string& path) {
        std::ifstream input(path,std::ios::binary|std::ios::ate);
        require(bool(input),"Cannot open pinned numeric trace");const auto size=input.tellg();
        require(size>=0 && size<=1073741824,"Numeric trace byte bound differs");
        input.seekg(0);bytes_.resize(static_cast<std::size_t>(size));
        if(size)input.read(reinterpret_cast<char*>(bytes_.data()),size);
        require(bool(input),"Numeric trace read failed");
    }
    std::size_t remaining() const {return bytes_.size()-position_;}
    std::uint32_t u32() {
        require(remaining()>=4,"Truncated numeric u32");std::uint32_t value=0;
        for(unsigned i=0;i<4;++i)value|=std::uint32_t(bytes_[position_++])<<(8*i);return value;
    }
    std::uint64_t u64() {
        const auto low=u32();const auto high=u32();return low|(std::uint64_t(high)<<32);
    }
    std::string string(std::size_t size) {
        require(size<=remaining(),"Truncated numeric string");
        const auto result=std::string(reinterpret_cast<const char*>(bytes_.data()+position_),size);
        position_+=size;return result;
    }
    line2Dup::Match match() {
        const auto x=signed32(u32()),y=signed32(u32()),id=signed32(u32());
        const auto scoreBits=u32();float score;std::memcpy(&score,&scoreBits,4);
        require(std::isfinite(score),"Nonfinite captured score");const auto length=u64();
        require(length<=1048576 && length<=remaining(),"Captured class length bound differs");
        return {x,y,score,string(static_cast<std::size_t>(length)),id};
    }
    static int signed32(std::uint32_t value) {
        return value<=std::uint32_t(std::numeric_limits<int>::max())?static_cast<int>(value):
            -1-static_cast<int>(std::numeric_limits<std::uint32_t>::max()-value);
    }
};
postprocess_api::Records records(const std::vector<line2Dup::Match>& input) {
    postprocess_api::Records output;output.reserve(input.size());
    for(const auto& value:input) {
        std::uint32_t scoreBits;std::memcpy(&scoreBits,&value.similarity,4);
        output.push_back({value.x,value.y,value.template_id,scoreBits,value.class_id});
    }
    return output;
}
}
int main(int argc,char** argv) {
    try {
        std::string root,output;
        for(int i=1;i<argc;++i) {
            const std::string key=argv[i];require(i+1<argc,"Missing argument value");const std::string value=argv[++i];
            if(key=="--root")root=value;else if(key=="--output-directory")output=value;
            else throw std::runtime_error("Unknown argument "+key);
        }
        require(!root.empty()&&!output.empty(),"Explicit root and fresh output directory required");
        postprocess_evidence::literalRecordComparisonChecks();
        postprocess_evidence::FreshFile csv(output+"/replay.csv");
        csv.text("fixture,trace_input_count,trace_output_count,v11_output_count,candidate_output_count,full_ordered_equal\n");
        const std::vector<std::string> names={"LED_1","LED_2","LED_3","LED_4","LED_5","LED_6","LED_7","LED_8","case1",
            "tiny_s5_i7","tiny_s5_i70","tiny_s5_i127","tiny_s5_i215","tiny_s5_i293","tiny_s5_i353","tiny_s5_i436","tiny_s5_i493",
            "tiny_s2_i3","tiny_s2_i92","tiny_s2_i153","tiny_s2_i214","tiny_s2_i295","tiny_s2_i374","tiny_s2_i446","tiny_s2_i494"};
        for(std::size_t i=0;i<names.size();++i) {
            Reader reader(root+"/artifacts/match_consolidation/hash_prototype/run_20261022_capture_actual85/"+names[i]+"/capture.bin");
            require(reader.string(8)=="SBMHASH1"&&reader.u32()==1&&reader.u32()==0x01020304,"Captured format differs");
            const auto n=reader.u64(),u=reader.u64();
            require(n<=10000000&&u<=10000000&&n+u<=reader.remaining()/24,"Captured record budget differs");
            std::vector<line2Dup::Match> input,captured;
            for(std::uint64_t j=0;j<n;++j)input.push_back(reader.match());
            for(std::uint64_t j=0;j<u;++j)captured.push_back(reader.match());
            require(reader.remaining()==0,"Trailing captured bytes");
            auto baseline=input,candidate=input;
            line2Dup::detail::consolidateMatches(baseline);postprocess_hash::consolidateMatches(candidate);
            const auto b=records(baseline),c=records(candidate),oracle=records(captured);
            for(int variant=0;variant<2;++variant) {
                const auto id=2*i+variant;
                const auto raw=postprocess_api::encodeOutput(id,variant==0?b:c);
                postprocess_evidence::FreshFile(output+"/"+postprocess_evidence::filename(id)).bytes(raw.data(),raw.size());
            }
            const bool equal=b==oracle&&c==oracle&&b==c;
            auto row=postprocess_evidence::stream();row<<names[i]<<','<<n<<','<<u<<','<<b.size()<<','<<c.size()<<','<<equal<<'\n';
            csv.text(row.str());require(equal,"Actual-Match replay differs on "+names[i]);
        }
        std::cout<<"PASS actual-Match replay traces=25 helper_calls=50 output_archives=50 matcher_calls=0 image_decodes=0\n";
        return 0;
    } catch(const std::exception& error) {
        std::cerr<<"FAIL actual-Match replay: "<<error.what()<<'\n';return 1;
    }
}
