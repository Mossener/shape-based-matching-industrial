// Standalone kernel benchmark. Compile now; run only when the machine is idle.
// Includes the immutable baseline in a separate namespace, without modifying core.
#define line2Dup referenceLine2Dup
#include "baseline/line2Dup.cpp"
#undef line2Dup

#include "line2Dup_spread.hpp"
#include "line2Dup_response.hpp"
#include <opencv2/core/utils/filesystem.hpp>

#include <algorithm>
#include <chrono>
#include <cstdint>
#include <fstream>
#include <functional>
#include <iomanip>
#include <random>
#include <stdexcept>
#include <string>
#include <vector>

namespace {
using Clock = std::chrono::steady_clock;
volatile std::uint64_t sink = 0;

void require(bool condition, const std::string& message) {
    if (!condition) throw std::runtime_error(message);
}

// Safe original T x T forward OR, including clipped right/bottom borders.
// This scalar implementation is reported separately from the original SIMD
// implementation: scalar comparisons must not be claimed as production speedup.
void spreadScalar(const cv::Mat& src, cv::Mat& dst, int T) {
    dst.create(src.size(), CV_8UC1);
    dst.setTo(0);
    for (int dy = 0; dy < std::min(T, src.rows); ++dy)
        for (int dx = 0; dx < std::min(T, src.cols); ++dx)
            for (int y = 0; y < src.rows - dy; ++y) {
                const auto* source = src.ptr<unsigned char>(y + dy) + dx;
                auto* target = dst.ptr<unsigned char>(y);
                for (int x = 0; x < src.cols - dx; ++x) target[x] |= source[x];
            }
}

double median(std::vector<double> values) {
    require(!values.empty(), "Empty timing group");
    std::sort(values.begin(), values.end());
    const size_t n = values.size();
    return n % 2 ? values[n / 2] : (values[n / 2 - 1] + values[n / 2]) / 2;
}

void same(const cv::Mat& a, const cv::Mat& b, const std::string& label) {
    require(a.size() == b.size() && a.type() == b.type() && cv::countNonZero(a != b) == 0,
            "Byte mismatch: " + label);
}

std::uint64_t sample(const cv::Mat& matrix) {
    return matrix.ptr<unsigned char>(0)[0] +
           257u * matrix.ptr<unsigned char>(matrix.rows - 1)[matrix.cols - 1] +
           65537u * matrix.ptr<unsigned char>(matrix.rows / 2)[matrix.cols / 2];
}

// Approximate cold-cache condition, not a claim that every hardware cache line
// is absent. All eviction work is outside the measured interval.
void evict(const std::vector<unsigned char>& bytes) {
    const volatile unsigned char* source = bytes.data();
    std::uint64_t value = 0;
    for (size_t i = 0; i < bytes.size(); i += 64) value += source[i];
    sink += value;
}

struct Kernel {
    std::string name;
    std::function<void()> run;
    std::function<std::uint64_t()> checksum;
    std::vector<double> times;
};

void measure(std::ofstream& raw, std::ofstream& summary, const std::string& stage,
             int width, int height, int T, int repeats,
             std::vector<Kernel> kernels, const std::vector<unsigned char>& eviction) {
    // All allocations have already been initialized by correctness checks.
    for (auto& kernel : kernels)
        for (int warmup = 0; warmup < 2; ++warmup) kernel.run();
    std::array<std::vector<Kernel>, 2> groups = {{kernels, kernels}};
    const std::array<std::string, 2> caches = {{"warm", "evicted"}};
    for (int repeat = 0; repeat < repeats; ++repeat) {
        std::vector<size_t> order;
        for (size_t i = 0; i < kernels.size(); ++i) order.push_back((repeat + i) % kernels.size());
        if ((repeat / kernels.size()) % 2) std::reverse(order.begin(), order.end());
        // Interleave cache conditions too; do not put all cold samples after warm.
        for (int cachePosition = 0; cachePosition < 2; ++cachePosition) {
            const int mode = (repeat + cachePosition) % 2;
            for (size_t position = 0; position < order.size(); ++position) {
                auto& kernel = groups[mode][order[position]];
                if (mode == 0) kernel.run();
                else evict(eviction);
                const auto begin = Clock::now();
                kernel.run();
                const double ms = std::chrono::duration<double, std::milli>(Clock::now() - begin).count();
                const auto value = kernel.checksum();
                sink += value;
                kernel.times.push_back(ms);
                raw << stage << ',' << width << ',' << height << ',' << T << ',' << caches[mode] << ','
                    << repeat << ',' << kernel.name << ',' << position << ',' << ms << ',' << value << '\n';
            }
        }
    }
    for (int mode = 0; mode < 2; ++mode) {
        for (const auto& kernel : groups[mode]) {
            const double ms = median(kernel.times);
            summary << stage << ',' << width << ',' << height << ',' << T << ',' << caches[mode] << ','
                    << kernel.name << ',' << repeats << ',' << ms << ','
                    << *std::min_element(kernel.times.begin(), kernel.times.end()) << ','
                    << *std::max_element(kernel.times.begin(), kernel.times.end()) << '\n';
            std::cout << stage << ' ' << width << 'x' << height << " T=" << T << ' '
                      << caches[mode] << ' ' << kernel.name << " median_ms=" << ms << '\n';
        }
        const double baseline = median(groups[mode][kernels.size() - 2].times);
        const double optimized = median(groups[mode].back().times);
        std::cout << "  original_simd / optimized = " << baseline / optimized
                  << " (kernel-only, median ratio)\n";
    }
}
}

int main(int argc, char** argv) {
    try {
        const std::string output = argc > 1 ? argv[1] : "artifacts/response_optimization/kernel_bench";
        const int repeats = argc > 2 ? std::stoi(argv[2]) : 15;
        const int evictionMiB = argc > 3 ? std::stoi(argv[3]) : 64;
        require(repeats >= 3 && evictionMiB >= 32, "Use at least 3 repeats and 32 MiB eviction");
        cv::setNumThreads(1);
        cv::utils::fs::createDirectories(output);
        std::ofstream raw(output + "/raw.csv"), summary(output + "/summary.csv"), method(output + "/method.txt");
        require(bool(raw) && bool(summary) && bool(method), "Cannot create output files");
        raw << "stage,width,height,T,cache,repeat,kernel,order,ms,checksum\n" << std::setprecision(10);
        summary << "stage,width,height,T,cache,kernel,samples,median_ms,min_ms,max_ms\n" << std::setprecision(10);
        method << "Standalone microbenchmark; not end-to-end matcher performance.\n"
               << "Sizes: 768x576, 896x704, 1024x768. T=4,8.\n"
               << "Source: fixed-seed sparse orientation masks (87% zero, 12% one bit, 1% arbitrary mask).\n"
               << "Every configuration is byte-checked before measuring.\n"
               << "spread_scalar_t2 uses safe original T*T OR loops (compiler may auto-vectorize).\n"
               << "spread_original_simd is the immutable production baseline, not the scalar reference.\n"
               << "response_original_simd_linearize is original computeResponseMaps plus all eight linearize calls.\n"
               << "response_fused is ResponseLUT::linearize, with the LUT constructed outside timing.\n"
               << "Kernel order rotates each repeat and reverses each rotation block; warm/evicted conditions interleave each repeat and swap which comes first.\n"
               << "Each kernel has two excluded initial warmups. warm: an extra identical untimed call immediately before each sample.\n"
               << "evicted: read one byte per 64-byte line of " << evictionMiB << " MiB before each sample, outside timing. Approximate cache eviction, not a hardware guarantee.\n"
               << "Existing output allocations are reused; original response still allocates its internal lsb4/msb4 buffers as shipped.\n"
               << "Single OpenCV thread. No I/O/checksum/eviction included in timing. Repeats=" << repeats << ".\n"
               << "Compare medians against original_simd; no speedup claim based only on scalar baseline. Raw order/times preserved.\n";
        std::vector<unsigned char> eviction(static_cast<size_t>(evictionMiB) * 1024 * 1024, 0x5a);
        std::mt19937 random(0x19438);
        line2Dup::detail::ResponseLUT fused(referenceLine2Dup::SIMILARITY_LUT);
        for (const auto dimensions : {cv::Size(768, 576), cv::Size(896, 704), cv::Size(1024, 768)}) {
            cv::Mat input(dimensions, CV_8UC1);
            for (int y = 0; y < input.rows; ++y)
                for (int x = 0; x < input.cols; ++x) {
                    const auto value = random() % 100;
                    input.ptr<unsigned char>(y)[x] = value < 87 ? 0 : value < 99
                        ? static_cast<unsigned char>(1u << (random() % 8)) : static_cast<unsigned char>(random());
                }
            for (int T : {4, 8}) {
                cv::Mat scalar, oldSpread, newSpread, scratch;
                spreadScalar(input, scalar, T);
                referenceLine2Dup::spread(input, oldSpread, T);
                line2Dup::detail::spreadSeparable(input, newSpread, scratch, T);
                same(scalar, oldSpread, "scalar vs original SIMD spread");
                same(scalar, newSpread, "scalar vs separable spread");
                std::vector<cv::Mat> response, oldMemory(8), newMemory;
                const auto oldResponse = [&] {
                    referenceLine2Dup::computeResponseMaps(scalar, response);
                    for (int orientation = 0; orientation < 8; ++orientation)
                        referenceLine2Dup::linearize(response[orientation], oldMemory[orientation], T);
                };
                oldResponse();
                fused.linearize(scalar, newMemory, T);
                for (int orientation = 0; orientation < 8; ++orientation)
                    same(oldMemory[orientation], newMemory[orientation], "SIMD vs fused response orientation " + std::to_string(orientation));
                    measure(raw, summary, "spread", input.cols, input.rows, T, repeats,
                        {{"spread_scalar_t2", [&] { spreadScalar(input, scalar, T); }, [&] { return sample(scalar); }, {}},
                         {"spread_original_simd", [&] { referenceLine2Dup::spread(input, oldSpread, T); }, [&] { return sample(oldSpread); }, {}},
                         {"spread_separable", [&] { line2Dup::detail::spreadSeparable(input, newSpread, scratch, T); }, [&] { return sample(newSpread); }, {}}}, eviction);
                    measure(raw, summary, "response_linearize", input.cols, input.rows, T, repeats,
                        {{"response_original_simd_linearize", oldResponse, [&] { std::uint64_t value = 0; for (const auto& memory : oldMemory) value += sample(memory); return value; }, {}},
                         {"response_fused", [&] { fused.linearize(scalar, newMemory, T); }, [&] { std::uint64_t value = 0; for (const auto& memory : newMemory) value += sample(memory); return value; }, {}}}, eviction);
                raw.flush();
                summary.flush();
            }
        }
        std::cout << "Outputs: " << output << "; checksum sink=" << sink << '\n';
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "FAIL: " << error.what() << '\n';
        return 1;
    }
}
