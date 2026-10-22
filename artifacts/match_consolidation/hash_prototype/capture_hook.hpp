#ifndef HASH_PROTO_CAPTURE_HOOK_HPP
#define HASH_PROTO_CAPTURE_HOOK_HPP
#include "trace_io.hpp"
#include "line2Dup_matches.hpp"
#include <cmath>
#include <stdexcept>
#include <utility>
namespace capture_trace {
namespace detail {
enum class Phase { idle,armed,ready,failed };
struct Store { Phase phase=Phase::idle;hash_proto::Trace trace; };
// An inline function's local static is one shared entity across translation
// units. The adapter and core wrapper run on the same calling thread, outside
// the template OpenMP region. Separate callers retain separate trace state.
inline Store& store(){static thread_local Store value;return value;}
template<class Match>std::vector<hash_proto::Match> copy(const std::vector<Match>& input){
    std::vector<hash_proto::Match> output;output.reserve(input.size());
    for(const auto& m:input)output.push_back({m.x,m.y,m.similarity,m.class_id,m.template_id});
    return output;
}
}
inline void arm() {
    auto& state=detail::store();
    if(state.phase!=detail::Phase::idle)throw std::logic_error("Capture must be taken/cancelled before arming");
    state.trace={};state.phase=detail::Phase::armed;
}
inline void cancel() {auto& state=detail::store();state.trace={};state.phase=detail::Phase::idle;}
inline hash_proto::Trace take() {
    auto& state=detail::store();
    if(state.phase!=detail::Phase::ready)throw std::logic_error("No complete capture ready");
    auto trace=std::move(state.trace);state.phase=detail::Phase::idle;return trace;
}
template<class Match> void consolidate(std::vector<Match>& matches) {
    auto& state=detail::store();
    if(state.phase==detail::Phase::idle){line2Dup::detail::consolidateMatches(matches);return;}
    if(state.phase!=detail::Phase::armed)throw std::logic_error("Capture wrapper permits exactly one call per arm");
    try {
        for(const auto& m:matches)if(!std::isfinite(m.similarity))throw std::invalid_argument("Nonfinite capture score");
        hash_proto::Trace staged;staged.input=detail::copy(matches);
        line2Dup::detail::consolidateMatches(matches);
        staged.output=detail::copy(matches);
        state.trace=std::move(staged);state.phase=detail::Phase::ready;
    }catch(...){state.trace={};state.phase=detail::Phase::failed;throw;}
}
}
#endif
