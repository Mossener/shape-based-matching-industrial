#ifndef RGB_STRATIFIED_SHARED_TRAINING_HPP
#define RGB_STRATIFIED_SHARED_TRAINING_HPP

// Link control_v11/line2Dup.cpp as its own TU. Never include the core .cpp here.
#include "line2Dup.h"
#include "../collector/candidate_collector.hpp"
#include "../sampler/v2/stratified_sampler.hpp"
#include <array>
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <functional>
#include <limits>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

namespace rgb_stratified { namespace integration {

using CandidatePool = std::vector<industrial_stratified::Candidate>;
using LayerHook = std::function<void(std::uint64_t, unsigned, const collector::Result&,
    const CandidatePool&, const industrial_stratified::Result&, const industrial_stratified::Result&)>;
using CollectorFunction = std::function<collector::Result(const cv::Mat&, const cv::Mat&,
                                                        const cv::Mat&, const cv::Mat&)>;
using SamplerFunction = std::function<industrial_stratified::Result(
    const CandidatePool&, std::size_t, industrial_stratified::Mode)>;

struct Counts {
    std::uint64_t gradient_pyramids = 0;
    std::uint64_t pyramid_downs = 0;
    std::array<std::uint64_t,2> collector_calls{{0,0}};
    // Indexed [level][arm], where 0=P and 1=B.
    std::array<std::array<std::uint64_t,2>,2> sampler_calls{{{{0,0}},{{0,0}}}};
};
struct LayerSelections {
    industrial_stratified::Result pooled;
    industrial_stratified::Result balanced;
};
struct ArmResult {
    bool success = false;
    std::vector<line2Dup::Template> uncropped;
    std::vector<line2Dup::Template> cropped;
    cv::Rect crop;
};
struct PoseResult {
    std::uint64_t pose_id = 0;
    Counts counts;
    std::array<LayerSelections,2> layers;
    std::array<ArmResult,2> arms;
};

// Verbatim function body from frozen V11 control_v11/line2Dup.cpp cropTemplates.
// Only static/name become inline/crop_templates; the runner checks the full text.
// Original source SHA256: 85b5eb328a3b5cae3e161561e261833873d25a9f57c7457c4410dd21e52083ab.
using line2Dup::Template;
using cv::Rect;
inline Rect crop_templates(std::vector<Template> &templates)
{
    int min_x = std::numeric_limits<int>::max();
    int min_y = std::numeric_limits<int>::max();
    int max_x = std::numeric_limits<int>::min();
    int max_y = std::numeric_limits<int>::min();

    // First pass: find min/max feature x,y over all pyramid levels and modalities
    for (int i = 0; i < (int)templates.size(); ++i)
    {
        Template &templ = templates[i];

        for (int j = 0; j < (int)templ.features.size(); ++j)
        {
            int x = templ.features[j].x << templ.pyramid_level;
            int y = templ.features[j].y << templ.pyramid_level;
            min_x = std::min(min_x, x);
            min_y = std::min(min_y, y);
            max_x = std::max(max_x, x);
            max_y = std::max(max_y, y);
        }
    }

    /// @todo Why require even min_x, min_y?
    if (min_x % 2 == 1)
        --min_x;
    if (min_y % 2 == 1)
        --min_y;

    // Second pass: set width/height and shift all feature positions
    for (int i = 0; i < (int)templates.size(); ++i)
    {
        Template &templ = templates[i];
        templ.width = (max_x - min_x) >> templ.pyramid_level;
        templ.height = (max_y - min_y) >> templ.pyramid_level;
        templ.tl_x = min_x >> templ.pyramid_level;
        templ.tl_y = min_y  >> templ.pyramid_level;

        for (int j = 0; j < (int)templ.features.size(); ++j)
        {
            templ.features[j].x -= templ.tl_x;
            templ.features[j].y -= templ.tl_y;
        }
    }

    return Rect(min_x, min_y, max_x - min_x, max_y - min_y);
}

inline CandidatePool sampler_pool(const collector::Result& collected) {
    CandidatePool pool;
    pool.reserve(collected.candidates.size());
    for (const auto& candidate : collected.candidates)
        pool.push_back(industrial_stratified::Candidate{
            candidate.ordinal, candidate.x, candidate.y, candidate.label,
            candidate.theta_bits, candidate.magnitude_bits,
            candidate.interior ? industrial_stratified::Stratum::interior
                               : industrial_stratified::Stratum::contour});
    return pool;
}

inline line2Dup::Template uncropped_template(const industrial_stratified::Result& selection,
                                             unsigned level) {
    line2Dup::Template result;
    result.width = -1;
    result.height = -1;
    result.tl_x = 0;
    result.tl_y = 0;
    result.pyramid_level = static_cast<int>(level);
    result.features.reserve(selection.selected.size());
    for (const auto& candidate : selection.selected) {
        line2Dup::Feature feature(candidate.x, candidate.y, candidate.label);
        static_assert(sizeof(feature.theta) == sizeof(candidate.theta_bits), "float32 theta required");
        std::memcpy(&feature.theta, &candidate.theta_bits, sizeof(feature.theta));
        result.features.push_back(feature);
    }
    return result;
}

// Explicit dependency seam for small literal tests. Production train_pose below
// always supplies the frozen collector and v2 sampler, with fixed parameters.
inline PoseResult train_pose_with(const cv::Mat& source, const cv::Mat& official_mask,
                                 std::uint64_t pose_id, const CollectorFunction& collect,
                                 const SamplerFunction& sample, const LayerHook& hook = LayerHook{}) {
    if (source.empty() || source.dims != 2 || source.depth() != CV_8U ||
        (source.channels() != 1 && source.channels() != 3) || source.cols < 2 || source.rows < 2)
        throw std::invalid_argument("Training source must be a nonempty 2D uint8 one/three-channel image");
    if (official_mask.empty() || official_mask.dims != 2 || official_mask.type() != CV_8UC1 ||
        official_mask.size() != source.size())
        throw std::invalid_argument("Training requires explicit same-size 2D uint8 official mask");
    if (!collect || !sample) throw std::invalid_argument("Missing integration collector or sampler");

    PoseResult result;
    result.pose_id = pose_id;
    ++result.counts.gradient_pyramids;
    line2Dup::ColorGradientPyramid pyramid(source, official_mask, 20.0F, 32, 40.0F);
    for (unsigned level = 0; level < 2; ++level) {
        ++result.counts.collector_calls[level];
        const auto collected = collect(pyramid.magnitude, pyramid.angle, pyramid.angle_ori, pyramid.mask);
        // The complete per-layer pool exists once, and is immutable through both
        // selections and the streaming evidence hook. No pool survives this loop.
        const CandidatePool pool = sampler_pool(collected);
        const std::size_t budget = level == 0 ? 32 : 16;
        ++result.counts.sampler_calls[level][0];
        auto pooled = sample(pool, budget, industrial_stratified::Mode::pooled);
        ++result.counts.sampler_calls[level][1];
        auto balanced = sample(pool, budget, industrial_stratified::Mode::balanced);
        if (pooled.status != balanced.status)
            throw std::logic_error("P/B layer statuses differ on the same immutable pool");
        if (hook) hook(pose_id, level, collected, pool, pooled, balanced);
        result.layers[level].pooled = std::move(pooled);
        result.layers[level].balanced = std::move(balanced);
        // An insufficient L0 is an observed result, not an early-return trigger.
        if (level == 0) pyramid.pyrDown();
        if (level == 0) ++result.counts.pyramid_downs;
    }
    for (unsigned arm = 0; arm < 2; ++arm) {
        auto& output = result.arms[arm];
        output.success = true;
        for (unsigned level = 0; level < 2; ++level) {
            const auto& selected = arm == 0 ? result.layers[level].pooled : result.layers[level].balanced;
            output.success = output.success && selected.status == industrial_stratified::Status::ok;
            output.uncropped.push_back(uncropped_template(selected, level));
        }
        if (output.success) {
            output.cropped = output.uncropped;
            output.crop = crop_templates(output.cropped);
        }
    }
    return result;
}

inline PoseResult train_pose(const cv::Mat& source, const cv::Mat& official_mask,
                            std::uint64_t pose_id, const LayerHook& hook = LayerHook{}) {
    return train_pose_with(source, official_mask, pose_id, collector::collect,
        [](const CandidatePool& pool, std::size_t budget, industrial_stratified::Mode mode) {
            return industrial_stratified::sample(pool, budget, mode);
        }, hook);
}

// The frozen core stays unchanged. Only completed two-layer pyramids are
// injected into its protected bank; rejected attempts consume no template IDs.
class SharedDetector : public line2Dup::Detector {
public:
    SharedDetector() : line2Dup::Detector(32, std::vector<int>{4,8}, 20.0F, 40.0F) {}
    int inject(const std::string& class_id, const ArmResult& arm) {
        if (!arm.success) return -1;
        if (class_id.empty() || arm.cropped.size() != 2)
            throw std::invalid_argument("Successful insertion requires class ID and exactly two cropped layers");
        for (unsigned level = 0; level < 2; ++level) {
            const auto& templ = arm.cropped[level];
            if (templ.pyramid_level != static_cast<int>(level) || templ.features.empty() ||
                templ.width < 0 || templ.height < 0)
                throw std::invalid_argument("Invalid successful cropped template layer");
        }
        const auto found = class_templates.find(class_id);
        const std::size_t next = found == class_templates.end() ? 0 : found->second.size();
        if (next > static_cast<std::size_t>(std::numeric_limits<int>::max()))
            throw std::overflow_error("Dense native template ID exceeds int");
        class_templates[class_id].push_back(arm.cropped);
        return static_cast<int>(next);
    }
};

}}  // namespace rgb_stratified::integration
#endif
