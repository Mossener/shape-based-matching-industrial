#include "line2Dup.h"
#include "reference_matcher.hpp"
#include <algorithm>
#include <cmath>
#include <future>
#include <iomanip>
#include <iostream>
#include <sstream>
#include <stdexcept>
#include <tuple>
#include <type_traits>
#include <omp.h>

namespace {
void require(bool yes, const std::string& message) {
    if (!yes) throw std::runtime_error(message);
}
void requireDisjoint(double inclusive, double parts, const std::string& label) {
    std::ostringstream details;
    details << std::setprecision(17) << label << ": inclusive_ms=" << inclusive
            << " parts_ms=" << parts << " difference_ms=" << inclusive-parts;
    // Durations converted independently to double milliseconds can differ by
    // one ULP when the intervening clock reads share the same tick. One
    // picosecond is below the clock resolution; real phase overlap still fails.
    require(inclusive+1e-9>=parts,details.str());
}
using Key = std::tuple<std::string,int,int,float,int>;
template<class Matches> std::vector<Key> canonical(const Matches& matches) {
    std::vector<Key> keys;
    for (const auto& m : matches)
        keys.emplace_back(m.class_id, m.x, m.y, m.similarity, m.template_id);
    std::sort(keys.begin(), keys.end());
    return keys;
}
cv::Mat richImage(int rows, int cols, int channels, unsigned seed) {
    cv::Mat img(rows, cols, CV_MAKETYPE(CV_8U, channels));
    cv::RNG rng(seed);
    rng.fill(img, cv::RNG::UNIFORM, 0, 80);
    for (int k=0; k<35; ++k) {
        cv::Point a(rng.uniform(8,cols-8),rng.uniform(8,rows-8));
        cv::Point b(rng.uniform(8,cols-8),rng.uniform(8,rows-8));
        cv::line(img,a,b,cv::Scalar(rng.uniform(100,256),rng.uniform(100,256),rng.uniform(100,256)),2);
    }
    return img;
}
struct Input { cv::Mat image, mask; const char* label; };
}
int main() {
    try {
        static_assert(!std::is_copy_constructible<line2Dup::MatchWorkspace>::value,"workspace must not copy");
        static_assert(std::is_move_constructible<line2Dup::MatchWorkspace>::value,"workspace must move");
        static_assert(std::is_copy_constructible<line2Dup::Detector>::value,"Detector remains copyable");
        cv::setNumThreads(1);
        omp_set_dynamic(0);
        omp_set_num_threads(1);
        line2Dup::Detector detector(48,{4,8},20,40);
        cv::Mat a = richImage(160,192,3,541);
        cv::Mat object = a(cv::Rect(32,32,96,96)).clone();
        require(detector.addTemplate(object,"synthetic",cv::Mat(object.size(),CV_8U,cv::Scalar(255)))>=0,
                "synthetic template extraction failed");
        cv::FileStorage fs("reference.yml",cv::FileStorage::WRITE|cv::FileStorage::MEMORY);
        detector.writeClass("synthetic",fs);
        response_reference::Matcher reference(48,{4,8},20,40);
        reference.loadClass(fs.releaseAndGetString());
        const std::vector<std::string> ids{"synthetic"};
        require(!reference.match(a,80,ids).empty(),"test must have a positive original match");
        cv::Mat b = richImage(128,160,1,842);
        cv::Mat large = richImage(192,224,3,671);
        cv::Mat roi = large(cv::Rect(3,5,160,160));
        require(!roi.isContinuous(),"noncontinuous ROI fixture broken");
        cv::Mat zeros(a.size(),CV_8U,cv::Scalar(0));
        cv::Mat full(a.size(),CV_8U,cv::Scalar(255));
        cv::Mat half = zeros.clone(); half(cv::Rect(0,0,96,160)).setTo(255);
        std::vector<Input> inputs{
            {a,{},"A"},{b,{},"B gray size change"},{a,{},"A again"},
            {a,zeros,"zero mask"},{a,full,"full mask"},{a,half,"partial mask"},
            {a,{},"empty after partial mask"},{roi,{},"noncontinuous color ROI"},
            {a,{},"restore A"}};
        std::vector<line2Dup::MatchOptions> options(5);
        for (auto& o:options) { o.separable_spread=false; o.fused_response=false; o.reuse_buffers=false; o.log_timing=false; }
        options[1].separable_spread=true;
        options[2].fused_response=true;
        options[3].reuse_buffers=true;
        options[4].separable_spread=options[4].fused_response=options[4].reuse_buffers=true;
        int compared=0;
        for (size_t mode=0; mode<options.size(); ++mode) {
            line2Dup::MatchWorkspace workspace;
            for (const auto& input:inputs) {
                auto expected=canonical(reference.match(input.image,80,ids,input.mask));
                line2Dup::MatchTimings timing;
                auto actual=detector.match(input.image,80,workspace,options[mode],&timing,ids,input.mask);
                require(canonical(actual)==expected,"mismatch mode="+std::to_string(mode)+" input="+input.label);
                require(std::isfinite(timing.total_ms)&&timing.total_ms>=0,"invalid total timing");
                require(timing.preprocess_ms>=0&&timing.search_ms>=0,"invalid phase timing");
                requireDisjoint(timing.total_ms,timing.preprocess_ms+timing.search_ms,
                                "phase timings overlap total");
                const double stages=timing.pyramid_ms+timing.gradient_ms+timing.spread_ms+
                                    timing.response_ms+timing.linearize_ms;
                requireDisjoint(timing.preprocess_ms,stages,"preprocessing stages overlap");
                if(options[mode].fused_response)
                    require(timing.linearize_ms==0,"fused linearization counted twice");
                ++compared;
            }
            // Same data pointer, changed contents: image identity must not skip work.
            cv::Mat changed=a.clone();
            detector.match(changed,80,workspace,options[mode],nullptr,ids);
            changed.setTo(cv::Scalar::all(0));
            require(canonical(detector.match(changed,80,workspace,options[mode],nullptr,ids))==
                    canonical(reference.match(changed,80,ids)),"stale image contents");
            for(float weak:{250.0f,20.0f}) {
                detector.getModalities()->weak_threshold=weak;
                reference.setWeakThreshold(weak);
                require(canonical(detector.match(a,80,workspace,options[mode],nullptr,ids))==
                        canonical(reference.match(a,80,ids)),"stale weak threshold");
            }
            line2Dup::MatchWorkspace moved(std::move(workspace));
            require(canonical(detector.match(a,80,workspace,options[mode],nullptr,ids))==
                    canonical(reference.match(a,80,ids)),"moved-from workspace cannot be reused");
            require(canonical(detector.match(a,80,moved,options[mode],nullptr,ids))==
                    canonical(reference.match(a,80,ids)),"moved workspace failed");
            line2Dup::MatchWorkspace assigned;
            assigned=std::move(moved);
            require(canonical(detector.match(b,80,assigned,options[mode],nullptr,ids))==
                    canonical(reference.match(b,80,ids)),"move assignment failed");
        }
        auto expected_a=canonical(reference.match(a,80,ids));
        auto expected_b=canonical(reference.match(b,80,ids));
        line2Dup::MatchWorkspace switching;
        for(const auto& option:options)
            require(canonical(detector.match(a,80,switching,option,nullptr,ids))==expected_a,
                    "switching runtime options changes output");
        // A workspace is independent of detector identity, strides and depth.
        line2Dup::Detector other(32,{4,4,4},20,40);
        response_reference::Matcher other_reference(32,{4,4,4},20,40);
        for(const auto& option:options)
            require(canonical(other.match(a,80,switching,option))==
                    canonical(other_reference.match(a,80)),"cross-detector workspace state leaked");
        require(canonical(detector.match(a,80,switching,options.back(),nullptr,ids))==expected_a,
                "workspace failed to restore detector configuration");
        auto worker=[&](cv::Mat image,std::vector<Key> expected) {
            omp_set_num_threads(1);
            line2Dup::MatchWorkspace workspace;
            for(int i=0;i<3;++i)
                require(canonical(detector.match(image,80,workspace,options.back(),nullptr,ids))==expected,
                        "concurrent workspaces differ");
            require(canonical(detector.match(image,80,ids))==expected,"concurrent legacy TLS differs");
        };
        auto first=std::async(std::launch::async,worker,a,expected_a);
        auto second=std::async(std::launch::async,worker,b,expected_b);
        first.get(); second.get();
        // The old signature must remain callable and preserve output.
        require(canonical(detector.match(a,80,ids))==expected_a,"legacy signature changed");
        std::cout<<"PASS workspace: "<<compared<<" matrix cases plus mutation, threshold, move and concurrency checks\n";
        return 0;
    } catch(const std::exception& e) {
        std::cerr<<"FAIL workspace: "<<e.what()<<'\n';
        return 1;
    }
}
