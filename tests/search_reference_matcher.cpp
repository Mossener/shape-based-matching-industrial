#include "search_reference_matcher.hpp"
#define line2Dup searchReferenceLine2Dup
#define shape_based_matching searchReferenceShapeBasedMatching
#include "../artifacts/search_optimization/baseline/line2Dup.cpp"
#undef shape_based_matching
#undef line2Dup

namespace search_reference {
struct Matcher::Impl {
    searchReferenceLine2Dup::Detector detector;
    searchReferenceLine2Dup::MatchWorkspace workspace;
    Timings timing;
    Impl(int n,std::vector<int> steps,float weak,float strong)
        :detector(n,std::move(steps),weak,strong) {}
};
Matcher::Matcher(int n,std::vector<int> steps,float weak,float strong)
    :impl_(new Impl(n,std::move(steps),weak,strong)) {}
Matcher::~Matcher()=default;
Matcher::Matcher(Matcher&&) noexcept=default;
Matcher& Matcher::operator=(Matcher&&) noexcept=default;
void Matcher::loadClass(const std::string& yaml) {
    cv::FileStorage fs(yaml,cv::FileStorage::READ|cv::FileStorage::MEMORY);
    CV_Assert(fs.isOpened());impl_->detector.readClass(fs.root());
}
void Matcher::resetWorkspace() { impl_->workspace=searchReferenceLine2Dup::MatchWorkspace(); }
Timings Matcher::lastTimings() const { return impl_->timing; }
std::vector<Result> Matcher::match(cv::Mat source,float threshold,
        const std::vector<std::string>& ids,cv::Mat mask) const {
    searchReferenceLine2Dup::MatchOptions options;
    options.separable_spread=options.fused_response=options.reuse_buffers=true;
    options.log_timing=false;
    searchReferenceLine2Dup::MatchTimings timing;
    const auto found=impl_->detector.match(source,threshold,impl_->workspace,options,&timing,ids,mask);
    impl_->timing={timing.pyramid_ms,timing.gradient_ms,timing.spread_ms,timing.response_ms,
        timing.linearize_ms,timing.preprocess_ms,timing.search_ms,timing.total_ms};
    std::vector<Result> result;result.reserve(found.size());
    for(const auto& m:found) result.push_back({m.x,m.y,m.similarity,m.class_id,m.template_id});
    return result;
}
}
