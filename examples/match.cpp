#include "line2Dup.h"
#include <opencv2/imgcodecs.hpp>
#include <algorithm>
#include <cmath>
#include <iostream>
#include <stdexcept>
#include <string>

namespace {
int align16(int value) { return (value + 15) / 16 * 16; }

cv::Mat padded(const cv::Mat& image, int border) {
    cv::Mat result;
    cv::copyMakeBorder(image, result, border,
        align16(image.rows + 2 * border) - image.rows - border,
        border, align16(image.cols + 2 * border) - image.cols - border,
        cv::BORDER_CONSTANT, cv::Scalar::all(0));
    return result;
}

cv::Mat syntheticTemplate() {
    cv::Mat image(160, 160, CV_8UC1, cv::Scalar(0));
    std::vector<cv::Point> polygon{{28, 28}, {112, 28}, {132, 56},
        {104, 76}, {132, 132}, {28, 132}};
    cv::fillPoly(image, std::vector<std::vector<cv::Point>>{polygon}, cv::Scalar(210));
    cv::circle(image, {60, 62}, 14, cv::Scalar(0), -1);
    cv::rectangle(image, {52, 98, 36, 12}, cv::Scalar(30), -1);
    return image;
}
}

int main(int argc, char** argv) {
    try {
        const bool synthetic = argc == 2 && std::string(argv[1]) == "--synthetic";
        if (!synthetic && (argc < 3 || argc > 5)) {
            std::cout << "Usage: match_example --synthetic\n"
                         "       match_example TEMPLATE SCENE [THRESHOLD=85] [OUTPUT]\n"
                         "Uses one angle/scale; rows are raw feature-box candidates.\n";
            return argc == 2 && std::string(argv[1]) == "--help" ? 0 : 2;
        }
        float threshold = 85.f;
        if (!synthetic && argc >= 4) {
            std::size_t used = 0;
            threshold = std::stof(argv[3], &used);
            if (used != std::string(argv[3]).size() || !std::isfinite(threshold) ||
                threshold < 0.f || threshold > 100.f)
                throw std::runtime_error("Threshold must be a finite number in [0,100]");
        }
        cv::Mat templ = synthetic ? syntheticTemplate() : cv::imread(argv[1], cv::IMREAD_GRAYSCALE);
        cv::Mat scene;
        const cv::Point known_origin(176, 192);
        if (synthetic) {
            scene = cv::Mat::zeros(512, 512, CV_8UC1);
            templ.copyTo(scene(cv::Rect(known_origin, templ.size())));
        } else {
            scene = cv::imread(argv[2], cv::IMREAD_GRAYSCALE);
        }
        if (templ.empty() || scene.empty())
            throw std::runtime_error("Could not decode template or scene image");
        // T={4,8} requires alignment to 16. Leave room for edge refinement too.
        const int border = align16(std::max(templ.cols, templ.rows) + 32);
        cv::Mat train = padded(templ, 32);
        cv::Mat mask = cv::Mat::zeros(train.size(), CV_8UC1);
        mask(cv::Rect(32, 32, templ.cols, templ.rows)).setTo(255);
        line2Dup::Detector detector(64, {4, 8}, 20.f, 40.f);
        const int id = detector.addTemplate(train, "object", mask);
        if (id < 0)
            throw std::runtime_error("Not enough usable gradient features to train the template");
        const auto& layer = detector.getTemplates("object", id).front();
        cv::Mat input = padded(scene, border);
        line2Dup::MatchWorkspace workspace;
        line2Dup::MatchTimings timing;
        const auto matches = detector.match(input, threshold, workspace,
            line2Dup::MatchOptions(), &timing, {"object"});
        std::cout << "class,template_id,score,feature_x,feature_y,feature_width,feature_height,template_x,template_y\n";
        bool located = false;
        cv::Mat annotated;
        if (!synthetic && argc == 5)
            cv::cvtColor(scene, annotated, cv::COLOR_GRAY2BGR);
        for (const auto& match : matches) {
            const int x = match.x - border, y = match.y - border;
            const int tx = x - layer.tl_x + 32, ty = y - layer.tl_y + 32;
            std::cout << match.class_id << ',' << match.template_id << ',' << match.similarity
                << ',' << x << ',' << y << ',' << layer.width + 1 << ',' << layer.height + 1
                << ',' << tx << ',' << ty << '\n';
            if (synthetic && std::abs(tx - known_origin.x) <= 4 && std::abs(ty - known_origin.y) <= 4)
                located = true;
            if (!annotated.empty())
                cv::rectangle(annotated, {x, y, layer.width + 1, layer.height + 1}, {0, 220, 0}, 1);
        }
        std::cerr << "matches=" << matches.size() << " preprocess_ms=" << timing.preprocess_ms
                  << " search_ms=" << timing.search_ms << '\n';
        if (!annotated.empty() && !cv::imwrite(argv[4], annotated))
            throw std::runtime_error("Could not write the output image");
        if (synthetic) {
            if (!located) throw std::runtime_error("Synthetic target was not located within 4 pixels");
            std::cout << "PASS synthetic localization\n";
        }
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "Error: " << error.what() << '\n';
        return 1;
    }
}
