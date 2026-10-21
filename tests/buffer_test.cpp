#include "line2Dup.h"

#include <algorithm>
#include <atomic>
#include <cstdint>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>
#include <omp.h>

namespace {
void require(bool condition, const std::string& message) {
    if (!condition) throw std::runtime_error(message);
}

struct Counts {
    std::uint64_t primary = 0, secondary = 0, bytes = 0;
    std::uint64_t total() const { return primary + secondary; }
};

// Delegate storage and ownership to the original allocator. In particular,
// UMatData::currAllocator/prevAllocator are never changed to this wrapper.
class CountingAllocator final : public cv::MatAllocator {
public:
    explicit CountingAllocator(cv::MatAllocator* original) : original_(original) {}

    cv::UMatData* allocate(int dims, const int* sizes, int type, void* data,
                          size_t* step, cv::AccessFlag flags,
                          cv::UMatUsageFlags usage) const override {
        cv::UMatData* allocated = original_->allocate(dims, sizes, type, data, step, flags, usage);
        ++primary_;
        if (data == nullptr && allocated != nullptr) bytes_ += allocated->size;
        return allocated;
    }

    bool allocate(cv::UMatData* data, cv::AccessFlag flags,
                  cv::UMatUsageFlags usage) const override {
        const bool result = original_->allocate(data, flags, usage);
        ++secondary_;
        return result;
    }

    void deallocate(cv::UMatData* data) const override { original_->deallocate(data); }

    void reset() { primary_ = 0; secondary_ = 0; bytes_ = 0; }
    Counts counts() const { return {primary_.load(), secondary_.load(), bytes_.load()}; }

private:
    cv::MatAllocator* original_;
    mutable std::atomic<std::uint64_t> primary_{0}, secondary_{0}, bytes_{0};
};

class AllocatorScope {
public:
    explicit AllocatorScope(cv::MatAllocator* replacement)
        : original_(cv::Mat::getDefaultAllocator()) { cv::Mat::setDefaultAllocator(replacement); }
    ~AllocatorScope() { cv::Mat::setDefaultAllocator(original_); }
    AllocatorScope(const AllocatorScope&) = delete;
    AllocatorScope& operator=(const AllocatorScope&) = delete;
private:
    cv::MatAllocator* original_;
};

struct Frame {
    std::string phase;
    int repeat, width, height;
    Counts allocations;
};

struct Scenario {
    int channels;
    bool reuse;
    std::vector<Frame> frames;
};

Scenario run(line2Dup::Detector& detector, CountingAllocator& allocator,
             const cv::Mat& original, const cv::Mat& changed, bool reuse) {
    Scenario result{original.channels(), reuse, {}};
    line2Dup::MatchWorkspace workspace;
    line2Dup::MatchOptions options;
    options.separable_spread = false;
    options.fused_response = false;
    options.reuse_buffers = reuse;
    options.log_timing = false;
    const auto frame = [&](const cv::Mat& source, const std::string& phase, int repeat) {
        allocator.reset();
        const auto matches = detector.match(source, 75, workspace, options);
        const Counts counts = allocator.counts();
        require(matches.empty(), "Empty-template detector returned a match");
        result.frames.push_back({phase, repeat, source.cols, source.rows, counts});
    };
    for (int i = 0; i < 2; ++i) frame(original, "warmup", i);
    for (int i = 0; i < 5; ++i) frame(original, "same_size", i);
    frame(changed, "resize_first", 0);
    for (int i = 0; i < 2; ++i) frame(changed, "resized_same_size", i);
    frame(original, "restore_first", 0);
    for (int i = 0; i < 2; ++i) frame(original, "restored_same_size", i);
    return result;
}

std::vector<Counts> phase(const Scenario& scenario, const std::string& label) {
    std::vector<Counts> result;
    for (const auto& frame : scenario.frames)
        if (frame.phase == label) result.push_back(frame.allocations);
    require(!result.empty(), "Missing phase " + label);
    return result;
}

void stable(const Scenario& scenario, const std::string& label, size_t expected) {
    const auto values = phase(scenario, label);
    require(values.size() == expected, "Wrong sample count in " + label);
    for (const auto& value : values)
        require(value.primary == values.front().primary && value.secondary == values.front().secondary &&
                value.bytes == values.front().bytes,
                "Unstable fixed-size allocation count/bytes in " + label);
}

void validate(const Scenario& baseline, const Scenario& reused) {
    for (const auto* scenario : {&baseline, &reused}) {
        stable(*scenario, "same_size", 5);
        stable(*scenario, "resized_same_size", 2);
        stable(*scenario, "restored_same_size", 2);
    }
    for (const auto& label : {"same_size", "resized_same_size", "restored_same_size"}) {
        const Counts no = phase(baseline, label).front(), yes = phase(reused, label).front();
        require(yes.total() < no.total(), "Warm workspace did not reduce allocation calls in " + std::string(label));
        require(yes.bytes < no.bytes, "Warm workspace did not reduce requested allocation bytes");
    }
    const Counts before = phase(reused, "same_size").front();
    const Counts after = phase(reused, "restored_same_size").front();
    require(before.primary == after.primary && before.secondary == after.secondary && before.bytes == after.bytes,
            "Restored original size did not return to its stable allocation behavior");
}

void write_json(const std::string& path, const std::vector<Scenario>& scenarios) {
    std::ofstream file(path);
    require(bool(file), "Cannot write " + path);
    file << "{\n  \"passed\": true,\n  \"opencv_threads\": 1,\n  \"openmp_threads\": 1,\n"
         << "  \"detector\": {\"num_features\":128,\"T\":[4,8,8],\"weak_threshold\":20,\"strong_threshold\":40,\"templates\":0},\n"
         << "  \"other_options\": {\"separable_spread\":false,\"fused_response\":false,\"log_timing\":false},\n"
         << "  \"measurement\":\"Successful default cv::MatAllocator allocate requests and requested storage bytes during each match; this is not a count of all malloc/new calls. Input generation is excluded. UMatData ownership remains with the original allocator.\",\n"
         << "  \"pixel_correctness\":\"Covered independently by pipeline/workspace tests; empty-template outputs here only verify execution success. No image identity cache is inferred from allocation counts.\",\n"
         << "  \"scenarios\": [\n";
    for (size_t i = 0; i < scenarios.size(); ++i) {
        const auto& scenario = scenarios[i];
        file << "    {\"channels\":" << scenario.channels << ",\"reuse_buffers\":"
             << (scenario.reuse ? "true" : "false") << ",\"frames\":[\n";
        for (size_t j = 0; j < scenario.frames.size(); ++j) {
            const auto& frame = scenario.frames[j];
            file << "      {\"phase\":\"" << frame.phase << "\",\"repeat\":" << frame.repeat
                 << ",\"width\":" << frame.width << ",\"height\":" << frame.height
                 << ",\"allocate_calls\":" << frame.allocations.total()
                 << ",\"primary_allocate_calls\":" << frame.allocations.primary
                 << ",\"secondary_allocate_calls\":" << frame.allocations.secondary
                 << ",\"requested_bytes\":" << frame.allocations.bytes << "}"
                 << (j + 1 == scenario.frames.size() ? "\n" : ",\n");
        }
        file << "    ]}" << (i + 1 == scenarios.size() ? "\n" : ",\n");
    }
    file << "  ]\n}\n";
    require(bool(file), "Could not finish writing " + path);
}
}

int main(int argc, char** argv) {
    try {
        cv::setNumThreads(1);
        omp_set_dynamic(0);
        omp_set_num_threads(1);
        line2Dup::Detector detector(128, {4, 8, 8}, 20, 40);
        std::vector<cv::Mat> originals, changed;
        cv::RNG random(0x5382);
        for (int channels : {1, 3}) {
            originals.emplace_back(704, 896, CV_MAKETYPE(CV_8U, channels));
            changed.emplace_back(768, 1024, CV_MAKETYPE(CV_8U, channels));
            random.fill(originals.back(), cv::RNG::UNIFORM, 0, 256);
            random.fill(changed.back(), cv::RNG::UNIFORM, 0, 256);
        }
        cv::MatAllocator* original_allocator = cv::Mat::getDefaultAllocator();
        CountingAllocator allocator(original_allocator);
        std::vector<Scenario> scenarios;
        {
            AllocatorScope scope(&allocator);
            for (size_t i = 0; i < originals.size(); ++i) {
                scenarios.push_back(run(detector, allocator, originals[i], changed[i], false));
                scenarios.push_back(run(detector, allocator, originals[i], changed[i], true));
            }
        }
        require(cv::Mat::getDefaultAllocator() == original_allocator, "Default allocator was not restored");
        for (size_t i = 0; i < scenarios.size(); i += 2) validate(scenarios[i], scenarios[i + 1]);
        const std::string output = argc > 1 ? argv[1] : "artifacts/response_optimization/buffer_allocations.json";
        write_json(output, scenarios);
        for (const auto& scenario : scenarios) {
            const auto initial = phase(scenario, "same_size").front();
            const auto resize = phase(scenario, "resize_first").front();
            const auto resized = phase(scenario, "resized_same_size").front();
            const auto restore = phase(scenario, "restore_first").front();
            std::cout << "channels=" << scenario.channels << " reuse=" << scenario.reuse
                      << " stable=" << initial.total() << " calls/" << initial.bytes << " bytes"
                      << " resize_first=" << resize.total() << " resized_stable=" << resized.total()
                      << " restore_first=" << restore.total() << '\n';
        }
        std::cout << "PASS buffer allocation counts: 4 scenarios, 52 frames; stable warm reuse reduces calls and bytes; default allocator restored\n"
                  << "Output: " << output << '\n';
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "FAIL buffer allocation counts: " << error.what() << '\n';
        return 1;
    }
}
