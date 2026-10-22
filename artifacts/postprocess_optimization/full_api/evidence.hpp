#pragma once
#include "output_binary.hpp"
#include <algorithm>
#include <cmath>
#include <cstdio>
#include <iomanip>
#include <locale>
#include <sstream>
#include <stdexcept>
#include <utility>

namespace postprocess_evidence {
inline void require(bool ok,const std::string& message) {
    if(!ok)throw std::runtime_error(message);
}
class FreshFile {
    std::FILE* file_;
public:
    explicit FreshFile(const std::string& path):file_(std::fopen(path.c_str(),"wbx")) {
        require(file_!=nullptr,"Cannot exclusively create evidence file: "+path);
    }
    FreshFile(const FreshFile&)=delete;
    FreshFile& operator=(const FreshFile&)=delete;
    ~FreshFile() {if(file_)std::fclose(file_);}
    void bytes(const unsigned char* data,std::size_t size) {
        require(size==0 || std::fwrite(data,1,size,file_)==size,"Evidence write failed");
        require(std::fflush(file_)==0,"Evidence flush failed");
    }
    void text(const std::string& value) {
        bytes(reinterpret_cast<const unsigned char*>(value.data()),value.size());
    }
};
inline std::ostringstream stream() {
    std::ostringstream out;out.imbue(std::locale::classic());out<<std::setprecision(17);return out;
}
inline std::string filename(std::uint64_t id) {
    auto out=stream();out<<"outputs/call_"<<std::setw(6)<<std::setfill('0')<<id<<".bin";return out.str();
}
inline bool safeCsv(const std::string& value) {
    return value.find_first_of(",\r\n\0",0,4)==std::string::npos;
}
struct Saved {std::uint64_t id;postprocess_api::Records records;};
struct Metadata {
    std::string stage,route,variant,input;
    int threads=4;unsigned flags=127;
    int pass=0,repeat=0,worker=-1,step=0;
};
class Correctness {
    std::string directory_;FreshFile calls_,comparisons_;
public:
    std::uint64_t calls=0,comparisons=0;
    explicit Correctness(const std::string& directory):directory_(directory),
        calls_(directory+"/calls.csv"),comparisons_(directory+"/comparisons.csv") {
        calls_.text("call_id,stage,route,variant,input,threads,flags,pass,repeat,worker,step,output_file,output_bytes,record_count,api_wall_ms,has_internal_timing,internal_search_ms,internal_total_ms\n");
        comparisons_.text("comparison_id,actual_call_id,expected_call_id,full_ordered_equal,first_mismatch\n");
    }
    Saved save(postprocess_api::CallResult&& result,const Metadata& meta) {
        require(safeCsv(meta.stage)&&safeCsv(meta.route)&&safeCsv(meta.variant)&&safeCsv(meta.input),
                "Unsafe correctness metadata");
        const auto id=calls;const auto name=filename(id);
        const auto raw=postprocess_api::encodeOutput(id,result.records);
        FreshFile(directory_+"/"+name).bytes(raw.data(),raw.size());
        auto row=stream();row<<id<<','<<meta.stage<<','<<meta.route<<','<<meta.variant<<','<<meta.input
            <<','<<meta.threads<<','<<meta.flags<<','<<meta.pass<<','<<meta.repeat<<','<<meta.worker<<','<<meta.step
            <<','<<name<<','<<raw.size()<<','<<result.records.size()<<','<<result.api_wall_ms<<','
            <<result.has_internal_timing<<','<<result.internal.search_ms<<','<<result.internal.total_ms<<'\n';
        calls_.text(row.str());++calls;return {id,std::move(result.records)};
    }
    void compare(const Saved& actual,const Saved& expected) {
        std::size_t first=0;
        while(first<std::min(actual.records.size(),expected.records.size())&&
              actual.records[first]==expected.records[first])++first;
        const bool equal=actual.records==expected.records;
        auto row=stream();row<<comparisons<<','<<actual.id<<','<<expected.id<<','<<equal<<',';
        if(!equal)row<<first;
        row<<'\n';comparisons_.text(row.str());++comparisons;
        require(equal,"Complete ordered/score-bit mismatch at actual call "+std::to_string(actual.id)+
                      " expected call "+std::to_string(expected.id)+" record "+std::to_string(first));
    }
};
class Benchmark {
    std::string directory_;FreshFile calls_;
public:
    std::uint64_t calls=0;
    explicit Benchmark(const std::string& directory):directory_(directory),calls_(directory+"/calls.csv") {
        calls_.text("call_id,fixture,phase,round,position,variant,output_file,output_bytes,record_count,api_wall_ms,has_internal_timing,internal_search_ms,internal_total_ms\n");
    }
    Saved save(postprocess_api::CallResult&& result,const std::string& fixture,const std::string& phase,
               int round,int position,const std::string& variant) {
        require(safeCsv(fixture)&&safeCsv(phase)&&safeCsv(variant),"Unsafe timing metadata");
        const auto id=calls;const auto name=filename(id);
        const auto raw=postprocess_api::encodeOutput(id,result.records);
        FreshFile(directory_+"/"+name).bytes(raw.data(),raw.size());
        auto row=stream();row<<id<<','<<fixture<<','<<phase<<','<<round<<','<<position<<','<<variant
            <<','<<name<<','<<raw.size()<<','<<result.records.size()<<','<<result.api_wall_ms<<','
            <<result.has_internal_timing<<','<<result.internal.search_ms<<','<<result.internal.total_ms<<'\n';
        calls_.text(row.str());++calls;return {id,std::move(result.records)};
    }
};
inline void literalRecordComparisonChecks() {
    const postprocess_api::Records oracle={{2,3,7,0x3f800001U,"A"},{4,5,9,0x80000000U,std::string("B\0C",3)}};
    auto changed=oracle;std::swap(changed[0],changed[1]);require(changed!=oracle,"Record order ignored");
    changed=oracle;changed[0].x++;require(changed!=oracle,"Record x ignored");
    changed=oracle;changed[0].y++;require(changed!=oracle,"Record y ignored");
    changed=oracle;changed[0].template_id++;require(changed!=oracle,"Template id ignored");
    changed=oracle;changed[0].score_bits^=1;require(changed!=oracle,"Score bit ignored");
    changed=oracle;changed[1].score_bits=0;require(changed!=oracle,"Signed zero bit ignored");
    changed=oracle;changed[1].class_id=std::string("B\0D",3);require(changed!=oracle,"NUL class bytes ignored");
    changed=oracle;changed.pop_back();require(changed!=oracle,"Missing record ignored");
    changed=oracle;changed.push_back(oracle.front());require(changed!=oracle,"Duplicate multiplicity ignored");
}
}
