// Deliberately included in each wrapper TU with private namespace macros.
#include <chrono>
#include <cstring>
#include <limits>
#include <stdexcept>
#include <type_traits>

namespace POSTPROCESS_WRAPPER {
struct Workspace::Impl {
    POSTPROCESS_CORE::MatchWorkspace value;
    Impl()=default;
    explicit Impl(POSTPROCESS_CORE::MatchWorkspace&& other):value(std::move(other)) {}
};
struct Matcher::Impl {
    POSTPROCESS_CORE::Detector detector;
    Impl(int features,std::vector<int> steps,float weak,float strong)
        :detector(features,std::move(steps),weak,strong) {}
};
static_assert(std::is_nothrow_move_constructible<POSTPROCESS_CORE::MatchWorkspace>::value,
              "The actual core workspace must retain its noexcept move constructor");
static_assert(std::is_nothrow_move_assignable<POSTPROCESS_CORE::MatchWorkspace>::value,
              "The actual core workspace must retain its noexcept move assignment");
namespace {
using Clock=std::chrono::steady_clock;
template<class ActualMatches>
postprocess_api::Records copyRecords(const ActualMatches& raw) {
    static_assert(std::numeric_limits<int>::digits==31,"Actual signed32 Match coordinates required");
    postprocess_api::Records result;result.reserve(raw.size());
    for(const auto& item:raw) {
        std::uint32_t score_bits;
        static_assert(sizeof(score_bits)==sizeof(item.similarity),"Actual binary32 score required");
        std::memcpy(&score_bits,&item.similarity,sizeof(score_bits));
        result.push_back({item.x,item.y,item.template_id,score_bits,item.class_id});
    }
    return result;
}
postprocess_api::Timings copyTimings(const POSTPROCESS_CORE::MatchTimings& timing) {
    return {timing.pyramid_ms,timing.gradient_ms,timing.spread_ms,timing.response_ms,
            timing.linearize_ms,timing.preprocess_ms,timing.search_ms,timing.total_ms};
}
double elapsed(Clock::time_point start,Clock::time_point end) {
    return std::chrono::duration<double,std::milli>(end-start).count();
}
}
Workspace::Workspace():impl_(new Impl) {}
Workspace::~Workspace()=default;
// Allocate the wrapper shell outside all API clocks, then invoke the actual
// core workspace move. Keep the source shell and its moved-from core object so
// a subsequent match exercises real core moved-from reuse, not pointer reuse.
Workspace::Workspace(Workspace&& other):impl_(new Impl(std::move(other.impl_->value))) {}
Workspace& Workspace::operator=(Workspace&& other) noexcept {
    if(this!=&other)impl_->value=std::move(other.impl_->value);
    return *this;
}
void Workspace::reset() { impl_->value=POSTPROCESS_CORE::MatchWorkspace(); }
Matcher::Matcher(int features,std::vector<int> steps,float weak,float strong)
    :impl_(new Impl(features,std::move(steps),weak,strong)) {}
Matcher::~Matcher()=default;
void Matcher::loadClass(const std::string& yaml,const std::string& override_id) {
    cv::FileStorage storage(yaml,cv::FileStorage::READ|cv::FileStorage::MEMORY);
    if(!storage.isOpened())throw std::runtime_error("Template memory could not be opened");
    impl_->detector.readClass(storage.root(),override_id);
}
void Matcher::loadClassFile(const std::string& path) {
    cv::FileStorage storage(path,cv::FileStorage::READ);
    if(!storage.isOpened())throw std::runtime_error("Template file could not be opened");
    impl_->detector.readClass(storage.root());
}
int Matcher::templateCount() const { return impl_->detector.numTemplates(); }
postprocess_api::CallResult Matcher::match(const cv::Mat& image,float threshold,Workspace& workspace,
        unsigned flags,const std::vector<std::string>& ids,const cv::Mat& mask,bool log) const {
    if(flags>127)throw std::invalid_argument("Seven V11 option bits required");
    POSTPROCESS_CORE::MatchOptions options;
    options.separable_spread=(flags&1)!=0;options.fused_response=(flags&2)!=0;
    options.reuse_buffers=(flags&4)!=0;options.integer_local_max=(flags&8)!=0;
    options.direct_8bit_search=(flags&16)!=0;options.reuse_search_buffers=(flags&32)!=0;
    options.fused_local_search=(flags&64)!=0;options.log_timing=log;
    POSTPROCESS_CORE::MatchTimings timing;
    const auto start=Clock::now();
    const auto raw=impl_->detector.match(image,threshold,workspace.impl_->value,options,&timing,ids,mask);
    const auto end=Clock::now();
    postprocess_api::CallResult result;
    result.api_wall_ms=elapsed(start,end);result.has_internal_timing=true;
    result.internal=copyTimings(timing);result.records=copyRecords(raw);
    return result; // Actual returned U-vector destruction stays outside API clock.
}
postprocess_api::CallResult Matcher::legacyMatch(const cv::Mat& image,float threshold,
        const std::vector<std::string>& ids,const cv::Mat& mask) const {
    const auto start=Clock::now();
    const auto raw=impl_->detector.match(image,threshold,ids,mask);
    const auto end=Clock::now();
    postprocess_api::CallResult result;
    result.api_wall_ms=elapsed(start,end);result.records=copyRecords(raw);
    return result;
}
postprocess_api::CallResult Matcher::explicitDefaultMatch(const cv::Mat& image,float threshold,
        Workspace& workspace,const std::vector<std::string>& ids,const cv::Mat& mask) const {
    const POSTPROCESS_CORE::MatchOptions defaults;
    const auto start=Clock::now();
    const auto raw=impl_->detector.match(image,threshold,workspace.impl_->value,defaults,nullptr,ids,mask);
    const auto end=Clock::now();
    postprocess_api::CallResult result;
    result.api_wall_ms=elapsed(start,end);result.records=copyRecords(raw);
    return result;
}
}
