#include "v18_reference.hpp"
#define line2Dup localCenterV18LinearLine2Dup
#define shape_based_matching localCenterV18LinearShapeBasedMatching
#include "linear/line2Dup.cpp"
#undef shape_based_matching
#undef line2Dup

namespace local_center_v18 {
struct Workspace::Impl {localCenterV18LinearLine2Dup::MatchWorkspace workspace;};
struct Matcher::Impl {
    localCenterV18LinearLine2Dup::Detector detector;
    Impl(int features,std::vector<int> steps,float weak,float strong)
        :detector(features,std::move(steps),weak,strong) {}
};
Workspace::Workspace():impl_(new Impl) {}
Workspace::~Workspace()=default;
Workspace::Workspace(Workspace&&) noexcept=default;
Workspace& Workspace::operator=(Workspace&&) noexcept=default;
Matcher::Matcher(int features,std::vector<int> steps,float weak,float strong)
    :impl_(new Impl(features,std::move(steps),weak,strong)) {}
Matcher::~Matcher()=default;
void Matcher::loadClass(const std::string& yaml,const std::string& override_id) {
    cv::FileStorage storage(yaml,cv::FileStorage::READ|cv::FileStorage::MEMORY);
    CV_Assert(storage.isOpened());impl_->detector.readClass(storage.root(),override_id);
}
void Matcher::loadClassFile(const std::string& path) {
    cv::FileStorage storage(path,cv::FileStorage::READ);
    CV_Assert(storage.isOpened());impl_->detector.readClass(storage.root());
}
namespace {
template<class Matches> std::vector<Result> copied(const Matches& found) {
    std::vector<Result> output;output.reserve(found.size());
    for(const auto& m:found)output.push_back({m.x,m.y,m.similarity,m.class_id,m.template_id});
    return output;
}
}
std::vector<Result> Matcher::match(cv::Mat image,float threshold,Workspace& workspace,
        unsigned flags,bool cache,Timings* timing,const std::vector<std::string>& ids,cv::Mat mask,bool log) const {
    if(!workspace.impl_)workspace.impl_.reset(new Workspace::Impl);
    localCenterV18LinearLine2Dup::MatchOptions options;
    options.separable_spread=(flags&1)!=0;options.fused_response=(flags&2)!=0;
    options.reuse_buffers=(flags&4)!=0;options.integer_local_max=(flags&8)!=0;
    options.direct_8bit_search=(flags&16)!=0;options.reuse_search_buffers=(flags&32)!=0;
    options.fused_local_search=(flags&64)!=0;options.reuse_local_centers=cache;options.log_timing=log;
    localCenterV18LinearLine2Dup::MatchTimings local;
    const auto found=impl_->detector.match(image,threshold,workspace.impl_->workspace,options,&local,ids,mask);
    if(timing)*timing={local.pyramid_ms,local.gradient_ms,local.spread_ms,local.response_ms,
        local.linearize_ms,local.preprocess_ms,local.search_ms,local.total_ms};
    return copied(found);
}
std::vector<Result> Matcher::defaultMatch(cv::Mat image,float threshold,Workspace& workspace,
        const std::vector<std::string>& ids,cv::Mat mask) const {
    if(!workspace.impl_)workspace.impl_.reset(new Workspace::Impl);
    return copied(impl_->detector.match(image,threshold,workspace.impl_->workspace,
        localCenterV18LinearLine2Dup::MatchOptions(),nullptr,ids,mask));
}
std::vector<Result> Matcher::legacyMatch(cv::Mat image,float threshold,
        const std::vector<std::string>& ids,cv::Mat mask) const {
    return copied(impl_->detector.match(image,threshold,ids,mask));
}
}
