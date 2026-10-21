#ifndef QUALITY_COVERAGE_NMS_HPP
#define QUALITY_COVERAGE_NMS_HPP
#include "coverage_helper.hpp"
namespace quality_coverage {
struct Box {double x=0,y=0,w=0,h=0;};
struct Candidate {float score=0;int template_id=-1,x=0,y=0;std::string class_id;Box box;};
enum class Audit {not_attempted,coverage_rejected,nms_suppressed,retained};
struct Kept {std::size_t input_index=0;Candidate candidate;Coverage coverage;};
struct FilterResult {std::vector<Kept> kept;std::vector<Audit> audit;std::size_t attempted=0,suppressed=0,point_queries=0;};
template<class Verify> FilterResult filter_full(const std::vector<Candidate>&,Verify,double,double){return {};}
template<class Verify> FilterResult filter_lazy(const std::vector<Candidate>&,Verify,double,double){return {};}
}
#endif
