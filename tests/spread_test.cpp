#include "line2Dup_spread.hpp"

#include <climits>
#include <cstdint>
#include <functional>
#include <iostream>
#include <random>
#include <stdexcept>
#include <string>
#include <vector>

namespace {
int checks = 0;

void require(bool condition, const std::string& message) {
    if (!condition) throw std::runtime_error(message);
}

cv::Mat oracle(const cv::Mat& src, int T) {
    cv::Mat result(src.size(), CV_8UC1, cv::Scalar(0));
    for (int y = 0; y < src.rows; ++y)
        for (int x = 0; x < src.cols; ++x) {
            unsigned char bits = 0;
            const int height = std::min(T, src.rows - y);
            const int width = std::min(T, src.cols - x);
            for (int dy = 0; dy < height; ++dy)
                for (int dx = 0; dx < width; ++dx)
                    bits |= src.ptr<unsigned char>(y + dy)[x + dx];
            result.ptr<unsigned char>(y)[x] = bits;
        }
    return result;
}

void check_guard(const cv::Mat& arena, const cv::Rect& roi, unsigned char value) {
    for (int y = 0; y < arena.rows; ++y)
        for (int x = 0; x < arena.cols; ++x)
            if (!roi.contains(cv::Point(x, y)))
                require(arena.ptr<unsigned char>(y)[x] == value, "output ROI guard modified");
}

void check_case(const cv::Mat& src, int T) {
    const cv::Mat expected = oracle(src, T), saved = src.clone();
    cv::Mat dst_arena(src.rows + 4, src.cols + 9, CV_8UC1, cv::Scalar(0xa6));
    cv::Mat tmp_arena(src.rows + 6, src.cols + 13, CV_8UC1, cv::Scalar(0x5a));
    const cv::Rect dst_roi(3, 2, src.cols, src.rows), tmp_roi(5, 3, src.cols, src.rows);
    cv::Mat dst = dst_arena(dst_roi), scratch = tmp_arena(tmp_roi);
    const unsigned char* dst_data = dst.data;
    const unsigned char* scratch_data = scratch.data;
    for (int pass = 0; pass < 2; ++pass) {
        dst.setTo(0x83);
        scratch.setTo(0x46);
        line2Dup::detail::spreadSeparable(src, dst, scratch, T);
        require(dst.data == dst_data && scratch.data == scratch_data, "same-sized output allocation not reused");
        require(cv::countNonZero(dst != expected) == 0,
                "oracle mismatch: " + std::to_string(src.cols) + "x" + std::to_string(src.rows) + " T=" + std::to_string(T));
        require(cv::countNonZero(src != saved) == 0, "source changed");
        check_guard(dst_arena, dst_roi, 0xa6);
        check_guard(tmp_arena, tmp_roi, 0x5a);
        ++checks;
    }
    cv::Mat fresh_dst, fresh_scratch;
    line2Dup::detail::spreadSeparable(src, fresh_dst, fresh_scratch, T);
    require(cv::countNonZero(fresh_dst != expected) == 0, "fresh allocation mismatch");
    ++checks;
}

void expect_assert(const std::function<void()>& action) {
    bool caught = false;
    try { action(); } catch (const cv::Exception&) { caught = true; }
    require(caught, "invalid/aliased arguments were not rejected");
    ++checks;
}
}

int main() {
    try {
        std::mt19937 random(0x5e9a2u);
        for (int width : {1, 2, 7, 15, 16, 17, 31, 32, 33, 63, 64, 65})
            for (int height : {1, 2, 5, 9})
                for (int pattern = 0; pattern < 3; ++pattern) {
                    cv::Mat arena(height + 3, width + 11, CV_8UC1, cv::Scalar(0xe7));
                    cv::Mat input = arena(cv::Rect(3, 1, width, height));
                    for (int y = 0; y < height; ++y)
                        for (int x = 0; x < width; ++x)
                            input.ptr<unsigned char>(y)[x] = pattern == 0 ? 0 : pattern == 1 ? 255 : static_cast<unsigned char>(random());
                    for (int T : {1, 4, 8, 80}) check_case(input, T);
                }
        for (int bit = 0; bit < 8; ++bit)
            for (int y : {0, 4, 8})
                for (int x : {0, 8, 16}) {
                    cv::Mat input(9, 17, CV_8UC1, cv::Scalar(0));
                    input.ptr<unsigned char>(y)[x] = static_cast<unsigned char>(1u << bit);
                    for (int T : {1, 4, 8, 25}) check_case(input, T);
                }
        cv::Mat mixed(2, 3, CV_8UC1, cv::Scalar(0));
        mixed.at<unsigned char>(0, 0) = 1;
        mixed.at<unsigned char>(0, 1) = 2;
        mixed.at<unsigned char>(1, 0) = 128;
        check_case(mixed, 4);  // OR must produce 131, not grayscale maximum 128.
        check_case(mixed, INT_MAX);  // Clipping must avoid arithmetic overflow.
        for (int iteration = 0; iteration < 200; ++iteration) {
            const int width = 1 + random() % 100, height = 1 + random() % 35;
            // Tightly packed external memory, unaligned start, including the final row.
            std::vector<unsigned char> bytes(static_cast<size_t>(width) * height + 2, 0xb7);
            cv::Mat input(height, width, CV_8UC1, bytes.data() + 1);
            for (int y = 0; y < height; ++y)
                for (int x = 0; x < width; ++x) input.ptr<unsigned char>(y)[x] = static_cast<unsigned char>(random());
            check_case(input, 1 + random() % 30);
            require(bytes.front() == 0xb7 && bytes.back() == 0xb7, "external source guard modified");
        }
        cv::Mat input(4, 5, CV_8UC1, cv::Scalar(1)), dst, scratch;
        expect_assert([&] { line2Dup::detail::spreadSeparable(input, dst, scratch, 0); });
        expect_assert([&] { line2Dup::detail::spreadSeparable(input, dst, scratch, -1); });
        expect_assert([&] { cv::Mat empty; line2Dup::detail::spreadSeparable(empty, dst, scratch, 4); });
        expect_assert([&] { cv::Mat wrong(4, 5, CV_16UC1); line2Dup::detail::spreadSeparable(wrong, dst, scratch, 4); });
        expect_assert([&] { line2Dup::detail::spreadSeparable(input, input, scratch, 4); });
        expect_assert([&] { line2Dup::detail::spreadSeparable(input, dst, input, 4); });
        expect_assert([&] { cv::Mat alias = input; line2Dup::detail::spreadSeparable(input, alias, scratch, 4); });
        expect_assert([&] { cv::Mat alias = input; line2Dup::detail::spreadSeparable(input, dst, alias, 4); });
        expect_assert([&] { line2Dup::detail::spreadSeparable(input, dst, dst, 4); });
        expect_assert([&] { cv::Mat a(input.size(), CV_8UC1), b = a; line2Dup::detail::spreadSeparable(input, a, b, 4); });
        std::cout << "PASS " << checks << " correctness checks (scalar oracle, ROI guards, reuse, aliases)\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "FAIL after " << checks << " checks: " << error.what() << '\n';
        return 1;
    }
}
