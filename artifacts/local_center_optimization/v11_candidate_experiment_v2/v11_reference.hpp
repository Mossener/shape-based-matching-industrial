#pragma once
#include <opencv2/core.hpp>
#include <memory>
#include <string>
#include <vector>

namespace local_center_v11 {
struct Result {int x,y;float similarity;std::string class_id;int template_id;};
struct Timings {
    double pyramid_ms=0,gradient_ms=0,spread_ms=0,response_ms=0,linearize_ms=0;
    double preprocess_ms=0,search_ms=0,total_ms=0;
};
// Bits 0..6 select spread, response, workspace, integer maximum, direct byte,
// search scratch and fused local search, respectively. No cache exists here.
class Matcher {
public:
    Matcher(int features,std::vector<int> steps,float weak,float strong);
    ~Matcher();
    Matcher(Matcher&&) noexcept;
    Matcher& operator=(Matcher&&) noexcept;
    Matcher(const Matcher&)=delete;
    Matcher& operator=(const Matcher&)=delete;
    void loadClass(const std::string& yaml,const std::string& override_id="");
    void loadClassFile(const std::string& path);
    void resetWorkspace();
    std::vector<Result> match(cv::Mat image,float threshold,unsigned flags,
        const std::vector<std::string>& ids={},cv::Mat mask={},bool log=false);
    std::vector<Result> legacyMatch(cv::Mat image,float threshold,
        const std::vector<std::string>& ids={},cv::Mat mask={});
    Timings lastTimings() const;
private:
    struct Impl;
    std::unique_ptr<Impl> impl_;
};
}
