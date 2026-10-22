#ifndef HASH_PROTO_CAPTURE_HOOK_HPP
#define HASH_PROTO_CAPTURE_HOOK_HPP
#include "trace_io.hpp"
#include "line2Dup_matches.hpp"
namespace capture_trace {
// API stub for genuine hook semantic RED. No production file includes this.
inline void arm() {}
inline void cancel() {}
inline hash_proto::Trace take() { return {}; }
template<class Match> void consolidate(std::vector<Match>& matches) {
    line2Dup::detail::consolidateMatches(matches);
}
}
#endif
