#include "line2Dup_response.hpp"

#include <array>
#include <fstream>
#include <iostream>
#include <iterator>
#include <random>
#include <sstream>
#include <stdexcept>
#include <string>

namespace {
int cases = 0;
size_t compared = 0;
void require(bool value, const std::string& message) {
    if (!value) throw std::runtime_error(message);
}

std::array<unsigned char, 256> originalLut() {
    std::ifstream f("artifacts/response_optimization/baseline/line2Dup.cpp");
    require(bool(f), "Cannot open immutable original LUT fixture");
    std::string source((std::istreambuf_iterator<char>(f)), {});
    const auto declaration = source.find("SIMILARITY_LUT[256] = {");
    require(declaration != std::string::npos, "Original LUT declaration missing");
    const auto begin = source.find('{', declaration), end = source.find('}', begin);
    std::string entries = source.substr(begin + 1, end - begin - 1);
    size_t pos;
    while ((pos = entries.find("LUT3")) != std::string::npos) entries.replace(pos, 4, "3");
    for (auto& c : entries) if (c == ',') c = ' ';
    std::istringstream stream(entries);
    std::array<unsigned char, 256> result;
    for (auto& v : result) {
        unsigned n;
        require(bool(stream >> n) && n <= 255, "Invalid original LUT fixture");
        v = static_cast<unsigned char>(n);
    }
    unsigned extra;
    require(!(stream >> extra), "Original LUT has too many entries");
    return result;
}

// Deliberately retain the original two-stage response-map + linearize layout.
std::vector<cv::Mat> oracle(const cv::Mat& src, int T, const unsigned char* lut) {
    std::vector<cv::Mat> result(8);
    for (int ori = 0; ori < 8; ++ori) {
        cv::Mat response(src.size(), CV_8UC1);
        for (int y = 0; y < src.rows; ++y)
            for (int x = 0; x < src.cols; ++x) {
                const unsigned char mask = src.at<unsigned char>(y, x);
                response.at<unsigned char>(y, x) = std::max(lut[32*ori+(mask&15)],
                    lut[32*ori+16+(mask>>4)]);
            }
        result[ori].create(T*T, (src.cols/T)*(src.rows/T), CV_8UC1);
        int row = 0;
        for (int sy = 0; sy < T; ++sy)
            for (int sx = 0; sx < T; ++sx) {
                unsigned char* dst = result[ori].ptr<unsigned char>(row++);
                for (int y = sy; y < src.rows; y += T)
                    for (int x = sx; x < src.cols; x += T)
                        *dst++ = response.at<unsigned char>(y, x);
            }
    }
    return result;
}

void check(const line2Dup::detail::ResponseLUT& fused, const unsigned char* lut,
           const cv::Mat& src, int T, std::vector<cv::Mat>& actual) {
    const cv::Mat saved = src.clone();
    const auto expected = oracle(src, T, lut);
    fused.linearize(src, actual, T);
    require(actual.size() == 8, "Expected eight orientations");
    for (int ori = 0; ori < 8; ++ori) {
        require(actual[ori].size() == expected[ori].size() && actual[ori].type() == CV_8UC1,
            "Wrong memory dimensions/type");
        for (int row = 0; row < expected[ori].rows; ++row)
            for (int col = 0; col < expected[ori].cols; ++col) {
                require(actual[ori].at<unsigned char>(row,col) == expected[ori].at<unsigned char>(row,col),
                    "Response differs from original two-stage oracle");
                ++compared;
            }
    }
    require(cv::countNonZero(src != saved) == 0, "Input changed");
    ++cases;
}
}

int main() {
    try {
        auto lut = originalLut();
        line2Dup::detail::ResponseLUT fused(lut.data());
        std::vector<cv::Mat> memories;
        cv::Mat masks(16,16,CV_8UC1);
        for (int i=0; i<256; ++i) masks.at<unsigned char>(i/16,i%16) = static_cast<unsigned char>(i);
        for (int T : {1,4,8}) check(fused,lut.data(),masks,T,memories);

        std::mt19937 rng(0x419a);
        for (int T : {1,4,8})
            for (int iteration=0; iteration<20; ++iteration) {
                const int rows=T*(1+rng()%12), cols=T*(1+rng()%15);
                cv::Mat backing(rows+3,cols+9,CV_8UC1);
                for (int y=0; y<backing.rows; ++y)
                    for (int x=0; x<backing.cols; ++x) backing.at<unsigned char>(y,x)=rng()%256;
                auto roi=backing(cv::Rect(3,1,cols,rows));
                require(!roi.isContinuous() || rows==1, "ROI should have a row stride");
                check(fused,lut.data(),roi,T,memories);
                std::array<unsigned char*,8> allocations;
                for (int ori=0; ori<8; ++ori) allocations[ori]=memories[ori].data;
                check(fused,lut.data(),roi,T,memories);
                for (int ori=0; ori<8; ++ori)
                    require(allocations[ori]==memories[ori].data, "Same-size buffers were not reused");
            }

        // Output ROIs ensure the implementation respects existing Mat row strides too.
        std::vector<cv::Mat> arenas(8);
        for (int ori=0; ori<8; ++ori) {
            arenas[ori]=cv::Mat(18,21,CV_8UC1,cv::Scalar(0xa5));
            memories[ori]=arenas[ori](cv::Rect(2,1,16,16));
        }
        check(fused,lut.data(),masks,4,memories);
        for (const auto& arena : arenas)
            for (int y=0; y<arena.rows; ++y)
                for (int x=0; x<arena.cols; ++x)
                    if (!cv::Rect(2,1,16,16).contains(cv::Point(x,y)))
                        require(arena.at<unsigned char>(y,x)==0xa5,"Output ROI guard changed");

        // An unrelated LUT catches accidental assumptions about the original score values.
        std::array<unsigned char,256> custom;
        for (auto& v:custom) v=rng()%256;
        const auto savedCustom=custom;
        line2Dup::detail::ResponseLUT arbitrary(custom.data());
        custom.fill(0); // Constructor must own its precomputed lookup.
        for (int T : {1,4,8}) check(arbitrary,savedCustom.data(),masks,T,memories);

        for (int badT : {0,-1,3}) {
            bool rejected=false;
            try { fused.linearize(masks,memories,badT); } catch(const cv::Exception&) { rejected=true; }
            require(rejected,"Invalid T was accepted");
        }
        bool rejected=false;
        try { fused.linearize(cv::Mat(16,16,CV_8UC3),memories,4); }
        catch(const cv::Exception&) { rejected=true; }
        require(rejected,"Wrong image type was accepted");
        std::cout << "PASS " << cases << " cases, " << compared
                  << " byte comparisons; invalid arguments rejected\n";
        return 0;
    } catch (const std::exception& e) { std::cerr << "FAIL: " << e.what() << '\n'; return 1; }
}
