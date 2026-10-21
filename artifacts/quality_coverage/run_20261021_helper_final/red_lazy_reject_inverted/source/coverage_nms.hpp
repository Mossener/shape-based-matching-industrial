#ifndef QUALITY_COVERAGE_NMS_HPP
#define QUALITY_COVERAGE_NMS_HPP
#include "coverage_helper.hpp"
namespace quality_coverage {
struct Box {double x=0,y=0,w=0,h=0;};
struct Candidate {float score=0;int template_id=-1,x=0,y=0;std::string class_id;Box box;};
enum class Audit {not_attempted,coverage_rejected,nms_suppressed,retained};
struct Kept {std::size_t input_index=0;Candidate candidate;Coverage coverage;};
struct FilterResult {std::vector<Kept> kept;std::vector<Audit> audit;std::size_t attempted=0,suppressed=0,point_queries=0;};
inline double box_iou(const Box& a,const Box& b) {
    if(a.w<=0 || a.h<=0 || b.w<=0 || b.h<=0)return 0;
    const double w=std::max(0.0,std::min(a.x+a.w,b.x+b.w)-std::max(a.x,b.x));
    const double h=std::max(0.0,std::min(a.y+a.h,b.y+b.h)-std::max(a.y,b.y));
    const double overlap=w*h,total=a.w*a.h+b.w*b.h-overlap;
    return total>0?overlap/total:0;
}
inline bool candidate_less(const Candidate& a,const Candidate& b) {
    if(a.score!=b.score)return a.score>b.score;
    if(a.class_id!=b.class_id)return a.class_id<b.class_id;
    if(a.template_id!=b.template_id)return a.template_id<b.template_id;
    if(a.y!=b.y)return a.y<b.y;
    if(a.x!=b.x)return a.x<b.x;
    if(a.box.y!=b.box.y)return a.box.y<b.box.y;
    if(a.box.x!=b.box.x)return a.box.x<b.box.x;
    if(a.box.w!=b.box.w)return a.box.w<b.box.w;
    return a.box.h<b.box.h;
}
inline std::vector<std::size_t> ordered_indices(const std::vector<Candidate>& input,double threshold,double nms) {
    validate_threshold(threshold,"Coverage threshold must be finite and in [0,1]");
    validate_threshold(nms,"NMS threshold must be finite and in [0,1]");
    std::vector<std::size_t> order;order.reserve(input.size());
    for(std::size_t i=0;i<input.size();++i) {
        const auto& c=input[i];
        if(!std::isfinite(c.score) || !std::isfinite(c.box.x) || !std::isfinite(c.box.y) ||
            !std::isfinite(c.box.w) || !std::isfinite(c.box.h) || c.box.w<0 || c.box.h<0)
            throw std::invalid_argument("NMS requires finite scores/boxes and nonnegative extents");
        order.push_back(i);
    }
    std::stable_sort(order.begin(),order.end(),[&](std::size_t a,std::size_t b){return candidate_less(input[a],input[b]);});
    return order;
}
inline bool overlaps_kept(const Candidate& candidate,const std::vector<Kept>& kept,double nms) {
    for(const auto& k:kept)
        if((candidate.class_id.empty() || k.candidate.class_id.empty() || candidate.class_id==k.candidate.class_id) &&
            box_iou(candidate.box,k.candidate.box)>nms)return true;
    return false;
}
// Both functions require a pure candidate-independent verifier. They retain
// original candidate fields, and sort with the external adapter's tie rules.
template<class Verify> FilterResult filter_full(const std::vector<Candidate>& input,Verify verify,double threshold,double nms) {
    const auto order=ordered_indices(input,threshold,nms);FilterResult result;
    result.audit.assign(input.size(),Audit::not_attempted);
    std::vector<Coverage> coverages(input.size());
    for(auto index:order) {
        coverages[index]=verify(input[index]);++result.attempted;
        if(coverages[index].verified)result.point_queries+=coverages[index].points;
    }
    for(auto index:order) {
        if(!passes(coverages[index],threshold)){result.audit[index]=Audit::coverage_rejected;continue;}
        if(overlaps_kept(input[index],result.kept,nms)) {result.audit[index]=Audit::nms_suppressed;++result.suppressed;continue;}
        result.kept.push_back({index,input[index],coverages[index]});result.audit[index]=Audit::retained;
    }
    return result;
}
template<class Verify> FilterResult filter_lazy(const std::vector<Candidate>& input,Verify verify,double threshold,double nms) {
    const auto order=ordered_indices(input,threshold,nms);FilterResult result;
    result.audit.assign(input.size(),Audit::not_attempted);
    for(auto index:order) {
        // Only a previously verified/pass-through accepted candidate suppresses.
        if(overlaps_kept(input[index],result.kept,nms)) {result.audit[index]=Audit::nms_suppressed;++result.suppressed;continue;}
        const auto coverage=verify(input[index]);++result.attempted;
        if(coverage.verified)result.point_queries+=coverage.points;
        if(passes(coverage,threshold)){result.audit[index]=Audit::coverage_rejected;continue;}
        result.kept.push_back({index,input[index],coverage});result.audit[index]=Audit::retained;
    }
    return result;
}
}
#endif
