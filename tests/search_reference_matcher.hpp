#pragma once
#include <opencv2/core.hpp>
#include <memory>
#include <string>
#include <vector>

namespace search_reference {
struct Result { int x,y;float similarity;std::string class_id;int template_id; };
struct Timings {
    double pyramid_ms=0,gradient_ms=0,spread_ms=0,response_ms=0,linearize_ms=0;
    double preprocess_ms=0,search_ms=0,total_ms=0;
};
// Independently compiled immutable V4; persistent preprocessing workspace makes
// its steady-state allocation behavior comparable to the current search cases.
class Matcher {
public:
    Matcher(int features,std::vector<int> steps,float weak,float strong);
    ~Matcher();
    Matcher(Matcher&&) noexcept;
    Matcher& operator=(Matcher&&) noexcept;
    Matcher(const Matcher&)=delete;
    Matcher& operator=(const Matcher&)=delete;
    void loadClass(const std::string& yaml);
    void resetWorkspace();
    std::vector<Result> match(cv::Mat source,float threshold,
        const std::vector<std::string>& ids={},cv::Mat mask={}) const;
    Timings lastTimings() const;
private:
    struct Impl;
    std::unique_ptr<Impl> impl_;
};
}
