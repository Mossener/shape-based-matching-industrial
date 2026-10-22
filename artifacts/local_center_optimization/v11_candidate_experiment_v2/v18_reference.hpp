#pragma once
#include "v11_reference.hpp"

namespace local_center_v18 {
using Result=local_center_v11::Result;
using Timings=local_center_v11::Timings;
class Matcher;
class Workspace {
public:
    Workspace();~Workspace();
    Workspace(Workspace&&) noexcept;
    Workspace& operator=(Workspace&&) noexcept;
    Workspace(const Workspace&)=delete;
    Workspace& operator=(const Workspace&)=delete;
private:
    friend class Matcher;
    struct Impl;std::unique_ptr<Impl> impl_;
};
class Matcher {
public:
    Matcher(int features,std::vector<int> steps,float weak,float strong);
    ~Matcher();
    Matcher(const Matcher&)=delete;
    Matcher& operator=(const Matcher&)=delete;
    void loadClass(const std::string& yaml,const std::string& override_id="");
    void loadClassFile(const std::string& path);
    std::vector<Result> match(cv::Mat image,float threshold,Workspace& workspace,
        unsigned flags,bool cache,Timings* timing=nullptr,
        const std::vector<std::string>& ids={},cv::Mat mask={},bool log=false) const;
    std::vector<Result> defaultMatch(cv::Mat image,float threshold,Workspace& workspace,
        const std::vector<std::string>& ids={},cv::Mat mask={}) const;
    std::vector<Result> legacyMatch(cv::Mat image,float threshold,
        const std::vector<std::string>& ids={},cv::Mat mask={}) const;
private:
    struct Impl;std::unique_ptr<Impl> impl_;
};
}
