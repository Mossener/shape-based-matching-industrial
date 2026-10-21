#include "line2Dup_search.hpp"

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <functional>
#include <iostream>
#include <limits>
#include <random>
#include <stdexcept>
#include <string>
#include <vector>

namespace {
std::uint64_t maps = 0, scores = 0, thresholds = 0, rejected = 0;

void require(bool value, const std::string& message) {
    if (!value) throw std::runtime_error(message);
}

std::uint32_t bits(float value) {
    std::uint32_t result;
    std::memcpy(&result, &value, sizeof(result));
    return result;
}

// Deliberately preserve the V4 arithmetic sequence; a precomputed reciprocal
// or double arithmetic can move a score across a strict float threshold.
float originalScore(unsigned raw, int features) {
    const int score_int = static_cast<int>(raw);
    return (score_int * 100.f) / (4 * features);
}

unsigned read(const cv::Mat& map, int y, int x) {
    return map.type() == CV_8UC1 ? map.ptr<unsigned char>(y)[x] : map.ptr<unsigned short>(y)[x];
}

void write(cv::Mat& map, int y, int x, unsigned value) {
    if (map.type() == CV_8UC1) map.ptr<unsigned char>(y)[x] = static_cast<unsigned char>(value);
    else map.ptr<unsigned short>(y)[x] = static_cast<unsigned short>(value);
}

struct OriginalMaximum { unsigned raw = 0; float score = 0; int row = -1, col = -1; };

// This is the original float-per-pixel row-major strict-> scan, not another
// integer argmax. It independently checks both selection and normalization.
OriginalMaximum originalMaximum(const cv::Mat& map, int features) {
    OriginalMaximum best;
    for (int y = 0; y < map.rows; ++y)
        for (int x = 0; x < map.cols; ++x) {
            const unsigned raw = read(map, y, x);
            const float score = originalScore(raw, features);
            if (score > best.score) best = {raw, score, y, x};
        }
    return best;
}

void checkMap(const cv::Mat& map, int features) {
    const cv::Mat saved = map.clone();
    const auto expected = originalMaximum(map, features);
    const auto actual = line2Dup::detail::localMaximum(map, features);
    require(actual.raw == expected.raw && bits(actual.score) == bits(expected.score) &&
            actual.row == expected.row && actual.col == expected.col,
            "Maximum mismatch: N=" + std::to_string(features) + " type=" + std::to_string(map.type()));
    require(cv::countNonZero(map != saved) == 0, "localMaximum changed input");
    ++maps;
}

void checkScore(unsigned raw, int features) {
    const float expected = originalScore(raw, features);
    const float actual = line2Dup::detail::similarityScore(raw, features);
    require(bits(actual) == bits(expected), "Float score differs at N=" + std::to_string(features) + " raw=" + std::to_string(raw));
    ++scores;
    const float infinity = std::numeric_limits<float>::infinity();
    for (float threshold : {-1.f, 0.f, 75.f, 100.f, expected,
                            std::nextafter(expected, -infinity), std::nextafter(expected, infinity),
                            std::numeric_limits<float>::quiet_NaN()}) {
        require((actual > threshold) == (expected > threshold), "Coarse strict threshold changed");
        require((actual < threshold) == (expected < threshold), "Local removal threshold changed");
        if (threshold == expected) {
            require(!(actual > threshold), "Coarse equality must reject");
            require(!(actual < threshold), "Local equality must survive removal");
        }
        ++thresholds;
    }
}

void expectAssert(const std::function<void()>& action) {
    bool caught = false;
    try { action(); } catch (const cv::Exception&) { caught = true; }
    require(caught, "Invalid helper argument accepted");
    ++rejected;
}
}

int main() {
    try {
        std::mt19937 random(0x6a831u);
        for (int features : {1, 46, 63, 64, 111, 236, 8191}) {
            const unsigned maximum = 4u * features;
            // Exhaust every legal accumulated raw score, including both sides
            // of the 63/64-feature storage transition and 32764 at N=8191.
            for (unsigned raw = 0; raw <= maximum; ++raw) checkScore(raw, features);
            for (int type : {CV_8UC1, CV_16UC1}) {
                const unsigned limit = std::min(maximum, type == CV_8UC1 ? 255u : 65535u);
                for (const auto size : {cv::Size(1, 1), cv::Size(16, 16), cv::Size(17, 9), cv::Size(33, 1)}) {
                    cv::Mat backing(size.height + 4, size.width + 11, type, cv::Scalar(0x55));
                    cv::Mat map = backing(cv::Rect(3, 2, size.width, size.height));
                    map.setTo(0);
                    checkMap(map, features); // All zero must leave both indices at -1.
                    const auto zero = line2Dup::detail::localMaximum(map, features);
                    require(zero.raw == 0 && bits(zero.score) == bits(0.f) && zero.row == -1 && zero.col == -1,
                            "All-zero indices changed");
                    map.setTo(1);
                    checkMap(map, features); // Dense positive ties choose (0,0).
                    map.setTo(0);
                    write(map, size.height - 1, size.width - 1, limit);
                    checkMap(map, features); // Last pixel and maximum legal value.
                    if (size.height > 1 && size.width > 8) {
                        write(map, 1, 0, limit);
                        write(map, 0, 8, limit);
                        checkMap(map, features); // (0,8) precedes (1,0), despite larger x.
                        const auto tie = line2Dup::detail::localMaximum(map, features);
                        require(tie.row == 0 && tie.col == 8, "Row-major tie rule changed");
                    }
                    for (int iteration = 0; iteration < 20; ++iteration) {
                        for (int y = 0; y < map.rows; ++y)
                            for (int x = 0; x < map.cols; ++x)
                                write(map, y, x, random() % (limit + 1));
                        checkMap(map, features);
                        // The old CV8->CV16 conversion must not affect argmax.
                        if (type == CV_8UC1) {
                            cv::Mat expanded;
                            map.convertTo(expanded, CV_16UC1);
                            const auto small = line2Dup::detail::localMaximum(map, features);
                            const auto wide = line2Dup::detail::localMaximum(expanded, features);
                            require(small.raw == wide.raw && bits(small.score) == bits(wide.score) &&
                                    small.row == wide.row && small.col == wide.col, "8/16-bit argmax differs");
                            checkMap(expanded, features);
                        }
                    }
                }
            }
        }
        cv::Mat valid(16, 16, CV_8UC1, cv::Scalar(0));
        for (int features : {0, -1, 8192}) {
            expectAssert([&] { line2Dup::detail::similarityScore(0, features); });
            expectAssert([&] { line2Dup::detail::localMaximum(valid, features); });
        }
        expectAssert([&] { line2Dup::detail::localMaximum(cv::Mat(), 46); });
        expectAssert([&] { line2Dup::detail::localMaximum(cv::Mat(16, 16, CV_32FC1), 46); });
        expectAssert([&] { line2Dup::detail::localMaximum(cv::Mat(16, 16, CV_8UC3), 46); });
        std::cout << "PASS search kernels: " << maps << " maps, " << scores << " bit-exact scores, "
                  << thresholds << " threshold pairs, " << rejected << " invalid arguments rejected\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "FAIL search kernels: " << error.what() << '\n';
        return 1;
    }
}
