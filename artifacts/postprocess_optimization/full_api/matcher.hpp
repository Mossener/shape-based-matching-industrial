#pragma once
#include "records.hpp"
#include <opencv2/core.hpp>
#include <memory>

// Same public wrapper surface, compiled on two private core namespaces.
// No raw/private Match type crosses this boundary.
#define POSTPROCESS_DECLARE_WRAPPER(NS) \
namespace NS { \
class Matcher; \
class Workspace { \
public: \
    Workspace(); ~Workspace(); Workspace(Workspace&&); \
    Workspace& operator=(Workspace&&) noexcept; \
    Workspace(const Workspace&)=delete; Workspace& operator=(const Workspace&)=delete; \
    void reset(); \
private: \
    struct Impl; std::unique_ptr<Impl> impl_; friend class Matcher; \
}; \
class Matcher { \
public: \
    Matcher(int features,std::vector<int> steps,float weak,float strong); ~Matcher(); \
    Matcher(const Matcher&)=delete; Matcher& operator=(const Matcher&)=delete; \
    void loadClass(const std::string& yaml,const std::string& override_id=""); \
    void loadClassFile(const std::string& path); int templateCount() const; \
    postprocess_api::CallResult match(const cv::Mat& image,float threshold,Workspace& workspace, \
        unsigned flags,const std::vector<std::string>& ids={},const cv::Mat& mask={},bool log=false) const; \
    postprocess_api::CallResult legacyMatch(const cv::Mat& image,float threshold, \
        const std::vector<std::string>& ids={},const cv::Mat& mask={}) const; \
    postprocess_api::CallResult explicitDefaultMatch(const cv::Mat& image,float threshold,Workspace& workspace, \
        const std::vector<std::string>& ids={},const cv::Mat& mask={}) const; \
private: \
    struct Impl; std::unique_ptr<Impl> impl_; \
}; \
}
POSTPROCESS_DECLARE_WRAPPER(postprocess_exact_v11_api)
POSTPROCESS_DECLARE_WRAPPER(postprocess_hash_v11_api)
#undef POSTPROCESS_DECLARE_WRAPPER
