#pragma once
#include <opencv2/core.hpp>
#include <memory>
#include <string>
#include <vector>

namespace response_reference {
struct Result {
    int x, y;
    float similarity;
    std::string class_id;
    int template_id;
};
struct Timings { double preprocess_ms = 0, search_ms = 0; };
// Independent immutable implementation. Its captured legacy stdout requires
// serial calls, including with respect to unrelated writes to std::cout.
class Matcher {
public:
    Matcher(int num_features = 128, std::vector<int> strides = {4, 8},
            float weak_threshold = 30, float strong_threshold = 60);
    ~Matcher();
    Matcher(Matcher&&) noexcept;
    Matcher& operator=(Matcher&&) noexcept;
    Matcher(const Matcher&) = delete;
    Matcher& operator=(const Matcher&) = delete;
    // YAML document contents, not a file path. Use Detector::writeClass(id, fs)
    // with FileStorage WRITE | MEMORY, then fs.releaseAndGetString().
    void loadClass(const std::string& yaml, const std::string& class_id_override = "");
    void setWeakThreshold(float value);
    std::vector<Result> match(cv::Mat source, float threshold,
                             const std::vector<std::string>& ids = {}, cv::Mat mask = {}) const;
    Timings lastTimings() const;
private:
    struct Impl;
    std::unique_ptr<Impl> impl_;
};
}
