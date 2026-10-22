#ifndef HASH_PROTO_TRACE_IO_HPP
#define HASH_PROTO_TRACE_IO_HPP
#include "record.hpp"
#include <cstdint>
#include <istream>
#include <ostream>
namespace hash_proto {
struct Trace { std::vector<Match> input,output; };
struct TraceLimits {
    std::uint64_t max_records=10000000,max_class_bytes=1048576,max_total_bytes=1073741824;
};
// Explicit RED stubs: integrity tests must fail before a format implementation.
inline void write_trace(std::ostream&,const Trace&){}
inline Trace read_trace(std::istream&,TraceLimits={}){return {};}
}
#endif
