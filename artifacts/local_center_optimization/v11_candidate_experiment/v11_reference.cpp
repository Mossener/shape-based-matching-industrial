#include "v11_reference.hpp"
#define line2Dup localCenterV11FrozenLine2Dup
#define shape_based_matching localCenterV11FrozenShapeBasedMatching
#include "baseline/line2Dup.cpp"
#undef shape_based_matching
#undef line2Dup

namespace local_center_v11 {
struct Matcher::Impl {
    localCenterV11FrozenLine2Dup::Detector detector;
    localCenterV11FrozenLine2Dup::MatchWorkspace workspace;
    Timings timing;
    Impl(int features,std::vector<int> steps,float weak,float strong)
        :detector(features,std::move(steps),weak,strong) {}
};
namespace {
template<class Matches> std::vector<Result> copy(const Matches& values) {
    std::vector<Result> result;result.reserve(values.size());
    for(const auto& m:values)result.push_back({m.x,m.y,m.similarity,m.class_id,m.template_id});
    return result;
}
}
Matcher::Matcher(int features,std::vector<int> steps,float weak,float strong)
    :impl_(new Impl(features,std::move(steps),weak,strong)) {}
Matcher::~Matcher()=default;
Matcher::Matcher(Matcher&&) noexcept=default;
Matcher& Matcher::operator=(Matcher&&) noexcept=default;
void Matcher::loadClass(const std::string& yaml,const std::string& override_id) {
    cv::FileStorage storage(yaml,cv::FileStorage::READ|cv::FileStorage::MEMORY);
    CV_Assert(storage.isOpened());impl_->detector.readClass(storage.root(),override_id);
}
void Matcher::loadClassFile(const std::string& path) {
    cv::FileStorage storage(path,cv::FileStorage::READ);
    CV_Assert(storage.isOpened());impl_->detector.readClass(storage.root());
}
void Matcher::resetWorkspace() {
    impl_->workspace=localCenterV11FrozenLine2Dup::MatchWorkspace();
}
Timings Matcher::lastTimings() const {return impl_->timing;}
std::vector<Result> Matcher::match(cv::Mat image,float threshold,unsigned flags,
        const std::vector<std::string>& ids,cv::Mat mask,bool log) {
    localCenterV11FrozenLine2Dup::MatchOptions options;
    options.separable_spread=(flags&1)!=0;
    options.fused_response=(flags&2)!=0;
    options.reuse_buffers=(flags&4)!=0;
    options.integer_local_max=(flags&8)!=0;
    options.direct_8bit_search=(flags&16)!=0;
    options.reuse_search_buffers=(flags&32)!=0;
    options.fused_local_search=(flags&64)!=0;
    options.log_timing=log;
    localCenterV11FrozenLine2Dup::MatchTimings timing;
    const auto found=impl_->detector.match(image,threshold,impl_->workspace,options,
                                          &timing,ids,mask);
    impl_->timing={timing.pyramid_ms,timing.gradient_ms,timing.spread_ms,timing.response_ms,
                  timing.linearize_ms,timing.preprocess_ms,timing.search_ms,timing.total_ms};
    return copy(found);
}
std::vector<Result> Matcher::legacyMatch(cv::Mat image,float threshold,
        const std::vector<std::string>& ids,cv::Mat mask) {
    return copy(impl_->detector.match(image,threshold,ids,mask));
}
}
