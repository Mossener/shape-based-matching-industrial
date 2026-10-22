#ifndef HASH_PROTO_TRACE_IO_HPP
#define HASH_PROTO_TRACE_IO_HPP
#include "record.hpp"
#include <cstdint>
#include <cmath>
#include <cstring>
#include <istream>
#include <limits>
#include <ostream>
#include <stdexcept>
#include <utility>
namespace hash_proto {
struct Trace { std::vector<Match> input,output; };
struct TraceLimits {
    std::uint64_t max_records=10000000,max_class_bytes=1048576,max_total_bytes=1073741824;
};
static_assert(sizeof(float)==4 && std::numeric_limits<float>::is_iec559,"Trace requires binary32 float");
static_assert(sizeof(int)==4 && std::numeric_limits<int>::min()==(-2147483647-1),"Trace requires signed 32-bit core coordinates");
static_assert(sizeof(std::size_t)<=8,"Trace counts are uint64");
namespace trace_detail {
inline void write_bytes(std::ostream& out,const char* data,std::size_t n){
    if(n>std::size_t(std::numeric_limits<std::streamsize>::max()))throw std::runtime_error("Trace write length out of range");
    if(n)out.write(data,static_cast<std::streamsize>(n));
    if(!out)throw std::runtime_error("Trace write failed");
}
inline void write_u32(std::ostream& out,std::uint32_t value){char bytes[4];for(unsigned i=0;i<4;++i)bytes[i]=char((value>>(8*i))&255);write_bytes(out,bytes,4);}
inline void write_u64(std::ostream& out,std::uint64_t value){char bytes[8];for(unsigned i=0;i<8;++i)bytes[i]=char((value>>(8*i))&255);write_bytes(out,bytes,8);}
inline void validate_records(const std::vector<Match>& records){
    for(const auto& d:records){
        if(!std::isfinite(d.similarity))throw std::runtime_error("Nonfinite trace score");
        if(d.class_id.size()>std::size_t(std::numeric_limits<std::streamsize>::max()))throw std::runtime_error("Trace class length out of range");
    }
}
inline void write_records(std::ostream& out,const std::vector<Match>& records){
    for(const auto& d:records){
        std::uint32_t score;std::memcpy(&score,&d.similarity,4);
        write_u32(out,std::uint32_t(d.x));write_u32(out,std::uint32_t(d.y));write_u32(out,std::uint32_t(d.template_id));write_u32(out,score);write_u64(out,d.class_id.size());write_bytes(out,d.class_id.data(),d.class_id.size());
    }
}
class Reader {
    std::istream& in_;
    std::uint64_t consumed_=0,limit_;
public:
    Reader(std::istream& in,std::uint64_t limit):in_(in),limit_(limit){}
    std::uint64_t remaining() const{return limit_-consumed_;}
    void bytes(char* output,std::uint64_t n){
        if(n>remaining() || n>std::uint64_t(std::numeric_limits<std::streamsize>::max()))throw std::runtime_error("Trace byte bound exceeded");
        if(n){in_.read(output,static_cast<std::streamsize>(n));if(in_.gcount()!=static_cast<std::streamsize>(n) || !in_)throw std::runtime_error("Truncated trace");}
        consumed_+=n;
    }
    std::uint32_t u32(){char b[4];bytes(b,4);std::uint32_t value=0;for(unsigned i=0;i<4;++i)value|=std::uint32_t(static_cast<unsigned char>(b[i]))<<(8*i);return value;}
    std::uint64_t u64(){char b[8];bytes(b,8);std::uint64_t value=0;for(unsigned i=0;i<8;++i)value|=std::uint64_t(static_cast<unsigned char>(b[i]))<<(8*i);return value;}
    static int signed_int(std::uint32_t n){return n<=std::uint32_t(std::numeric_limits<int>::max()) ? static_cast<int>(n) : -1-static_cast<int>(std::numeric_limits<std::uint32_t>::max()-n);}
    Match record(const TraceLimits& limits){
        const int x=signed_int(u32()),y=signed_int(u32()),id=signed_int(u32());const auto score_bits=u32();float score;std::memcpy(&score,&score_bits,4);
        if(!std::isfinite(score))throw std::runtime_error("Nonfinite trace score");
        const auto length=u64();
        if(length>limits.max_class_bytes || length>remaining() || length>std::string().max_size() || length>std::uint64_t(std::numeric_limits<std::streamsize>::max()))throw std::runtime_error("Trace class byte bound exceeded");
        std::string name(static_cast<std::size_t>(length),'\0');if(length)bytes(&name[0],length);
        return {x,y,score,std::move(name),id};
    }
    void end(){if(in_.peek()!=std::char_traits<char>::eof() || in_.bad())throw std::runtime_error("Trailing bytes or failed trace stream");}
};
}
inline void write_trace(std::ostream& out,const Trace& trace){
    // Validate both lists before emitting even a header on invalid input.
    trace_detail::validate_records(trace.input);trace_detail::validate_records(trace.output);
    trace_detail::write_bytes(out,"SBMHASH1",8);trace_detail::write_u32(out,1);trace_detail::write_u32(out,0x01020304);trace_detail::write_u64(out,trace.input.size());trace_detail::write_u64(out,trace.output.size());
    trace_detail::write_records(out,trace.input);trace_detail::write_records(out,trace.output);
}
inline Trace read_trace(std::istream& in,TraceLimits limits={}){
    trace_detail::Reader reader(in,limits.max_total_bytes);char magic[8];reader.bytes(magic,8);
    if(std::memcmp(magic,"SBMHASH1",8)!=0 || reader.u32()!=1 || reader.u32()!=0x01020304)throw std::runtime_error("Unknown trace format/version/endian marker");
    const auto input_count=reader.u64(),output_count=reader.u64();
    if(input_count>limits.max_records || output_count>limits.max_records || input_count>std::numeric_limits<std::uint64_t>::max()-output_count)throw std::runtime_error("Trace record count bound exceeded");
    if(input_count+output_count>reader.remaining()/24 || input_count>std::vector<Match>().max_size() || output_count>std::vector<Match>().max_size())throw std::runtime_error("Trace minimum byte/record capacity bound exceeded");
    Trace trace;
    // Do not reserve attacker-declared counts before seeing record bytes.
    for(std::uint64_t i=0;i<input_count;++i)trace.input.push_back(reader.record(limits));
    for(std::uint64_t i=0;i<output_count;++i)trace.output.push_back(reader.record(limits));
    reader.end();return trace;
}
}
#endif
