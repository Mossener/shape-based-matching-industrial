#pragma once
#include <opencv2/core.hpp>
#include <memory>
#include <string>
#include <vector>
namespace stage_reference {
struct Timing {double old_ms=0,new_ms=0;std::size_t input_count=0,old_count=0,new_count=0;bool old_first=false;};
class Matcher {
public:
    Matcher(int features,std::vector<int> steps,float weak,float strong);
    ~Matcher();
    void loadClass(const std::string& yaml);
    Timing match(cv::Mat source,float threshold,const std::vector<std::string>& ids);
private:
    struct Impl;std::unique_ptr<Impl> impl_;
};
}
