#include "stage_reference.hpp"
#define line2Dup consolidationStageLine2Dup
#define shape_based_matching consolidationStageShapeBasedMatching
#include "build/stage_source/line2Dup.cpp"
#undef shape_based_matching
#undef line2Dup
namespace stage_reference {
struct Matcher::Impl {
    consolidationStageLine2Dup::Detector detector;
    consolidationStageLine2Dup::MatchWorkspace workspace;
    Impl(int n,std::vector<int> steps,float weak,float strong):detector(n,std::move(steps),weak,strong){}
};
Matcher::Matcher(int n,std::vector<int> steps,float weak,float strong):impl_(new Impl(n,std::move(steps),weak,strong)){}
Matcher::~Matcher()=default;
void Matcher::loadClass(const std::string& yaml){cv::FileStorage f(yaml,cv::FileStorage::READ|cv::FileStorage::MEMORY);impl_->detector.readClass(f.root());}
Timing Matcher::match(cv::Mat source,float threshold,const std::vector<std::string>& ids){
    consolidationStageLine2Dup::MatchOptions options;options.log_timing=false;options.fused_local_search=true;
    impl_->detector.match(source,threshold,impl_->workspace,options,nullptr,ids);
    return {diagnostic_last.old_ms,diagnostic_last.new_ms,diagnostic_last.input_count,
        diagnostic_last.old_count,diagnostic_last.new_count,diagnostic_last.old_first};
}
}
