#pragma once
#include "records.hpp"
#include <limits>
#include <stdexcept>

namespace postprocess_api {
namespace wire_detail {
inline void u32(std::vector<unsigned char>& out,std::uint32_t value) {
    for(unsigned shift=0;shift<32;shift+=8)out.push_back(static_cast<unsigned char>((value>>shift)&255U));
}
inline void u64(std::vector<unsigned char>& out,std::uint64_t value) {
    for(unsigned shift=0;shift<64;shift+=8)out.push_back(static_cast<unsigned char>((value>>shift)&255U));
}
}
// Clock-free serialization only. The future fresh-directory harness owns IO
// and binds this call_id plus the complete byte hash to one native call row.
inline std::vector<unsigned char> encodeOutput(std::uint64_t call_id,const Records& records) {
    std::vector<unsigned char> out={'H','M','O','U','T','0','0','1'};
    wire_detail::u64(out,call_id);
    wire_detail::u64(out,static_cast<std::uint64_t>(records.size()));
    for(const auto& item:records) {
        wire_detail::u32(out,static_cast<std::uint32_t>(item.x));
        wire_detail::u32(out,static_cast<std::uint32_t>(item.y));
        wire_detail::u32(out,static_cast<std::uint32_t>(item.template_id));
        wire_detail::u32(out,item.score_bits);
        wire_detail::u64(out,static_cast<std::uint64_t>(item.class_id.size()));
        if(item.class_id.size()>out.max_size()-out.size())throw std::length_error("Output archive too large");
        out.insert(out.end(),item.class_id.begin(),item.class_id.end());
    }
    return out;
}
}
