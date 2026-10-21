#include "reference_matcher.hpp"
#include <iostream>
#include <sstream>
#include <stdexcept>
#define line2Dup referenceLine2Dup
#define shape_based_matching referenceShapeBasedMatching
#include "../artifacts/response_optimization/baseline/line2Dup.cpp"
#undef shape_based_matching
#undef line2Dup

namespace response_reference {
struct Matcher::Impl {
    referenceLine2Dup::Detector detector;
    Timings timings;
    Impl(int n, std::vector<int> t, float weak, float strong)
        : detector(n, std::move(t), weak, strong) {}
};
Matcher::Matcher(int n, std::vector<int> t, float weak, float strong)
    : impl_(new Impl(n, std::move(t), weak, strong)) {}
Matcher::~Matcher() = default;
Matcher::Matcher(Matcher&&) noexcept = default;
Matcher& Matcher::operator=(Matcher&&) noexcept = default;
void Matcher::loadClass(const std::string& yaml, const std::string& override_id) {
    cv::FileStorage fs(yaml, cv::FileStorage::READ | cv::FileStorage::MEMORY);
    if (!fs.isOpened()) throw std::runtime_error("Invalid reference template YAML");
    impl_->detector.readClass(fs.root(), override_id);
}
void Matcher::setWeakThreshold(float value) { impl_->detector.getModalities()->weak_threshold = value; }
Timings Matcher::lastTimings() const { return impl_->timings; }
std::vector<Result> Matcher::match(cv::Mat source, float threshold,
                                 const std::vector<std::string>& ids, cv::Mat mask) const {
    struct Capture {
        std::ostringstream text;
        std::streambuf* old;
        Capture() : old(std::cout.rdbuf(text.rdbuf())) {}
        ~Capture() { std::cout.rdbuf(old); }
    } capture;
    const auto matches = impl_->detector.match(source, threshold, ids, mask);
    impl_->timings = {};
    std::string log = capture.text.str();
    const std::string marker = "elasped time:";
    size_t pos = log.find(marker);
    if (pos != std::string::npos) {
        impl_->timings.preprocess_ms = 1000 * std::stod(log.substr(pos + marker.size()));
        pos = log.find(marker, pos + marker.size());
        if (pos != std::string::npos)
            impl_->timings.search_ms = 1000 * std::stod(log.substr(pos + marker.size()));
    }
    std::vector<Result> result;
    result.reserve(matches.size());
    for (const auto& m : matches)
        result.push_back({m.x, m.y, m.similarity, m.class_id, m.template_id});
    return result;
}
}
