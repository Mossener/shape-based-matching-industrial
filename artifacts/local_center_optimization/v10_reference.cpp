#include "v10_reference.hpp"
#define line2Dup localCenterV10Line2Dup
#define shape_based_matching localCenterV10ShapeBasedMatching
#include "baseline/line2Dup.cpp"
#undef shape_based_matching
#undef line2Dup

namespace local_center_v10 {
struct Matcher::Impl {
    localCenterV10Line2Dup::Detector detector;
    localCenterV10Line2Dup::MatchWorkspace workspace;
    Timings timing;
    Impl(int n, std::vector<int> steps, float weak, float strong)
        : detector(n, std::move(steps), weak, strong) {}
};
Matcher::Matcher(int n, std::vector<int> steps, float weak, float strong)
    : impl_(new Impl(n, std::move(steps), weak, strong)) {}
Matcher::~Matcher()=default;
Matcher::Matcher(Matcher&&) noexcept=default;
Matcher& Matcher::operator=(Matcher&&) noexcept=default;
void Matcher::loadClass(const std::string& yaml) {
    cv::FileStorage storage(yaml, cv::FileStorage::READ|cv::FileStorage::MEMORY);
    CV_Assert(storage.isOpened());
    impl_->detector.readClass(storage.root());
}
void Matcher::resetWorkspace() { impl_->workspace=localCenterV10Line2Dup::MatchWorkspace(); }
void Matcher::loadClassFile(const std::string& path) {
    cv::FileStorage storage(path, cv::FileStorage::READ);
    CV_Assert(storage.isOpened());
    impl_->detector.readClass(storage.root());
}
Timings Matcher::lastTimings() const { return impl_->timing; }
std::vector<Result> Matcher::match(cv::Mat source, float threshold,
    const std::vector<std::string>& ids, cv::Mat mask, bool fused) const {
    localCenterV10Line2Dup::MatchOptions options;
    options.separable_spread=options.fused_response=options.reuse_buffers=true;
    options.integer_local_max=options.direct_8bit_search=options.reuse_search_buffers=true;
    options.fused_local_search=fused;
    options.log_timing=false;
    localCenterV10Line2Dup::MatchTimings timing;
    const auto found=impl_->detector.match(source, threshold, impl_->workspace, options, &timing, ids, mask);
    impl_->timing={timing.pyramid_ms,timing.gradient_ms,timing.spread_ms,timing.response_ms,
        timing.linearize_ms,timing.preprocess_ms,timing.search_ms,timing.total_ms};
    std::vector<Result> results;
    results.reserve(found.size());
    for(const auto& match:found)
        results.push_back({match.x,match.y,match.similarity,match.class_id,match.template_id});
    return results;
}
}
