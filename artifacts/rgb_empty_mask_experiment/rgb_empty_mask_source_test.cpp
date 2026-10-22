#include "rgb_empty_mask_policy.hpp"

#include <opencv2/core.hpp>
#include <iostream>
#include <stdexcept>

struct SpyDetector {
    const cv::Mat* source = nullptr;
    bool saw_empty_mask = false;
    int calls = 0;

    int addTemplate(const cv::Mat& candidate, const std::string&, const cv::Mat& mask) {
        source = &candidate;
        saw_empty_mask = mask.empty();
        ++calls;
        return 17;
    }
};

static void require(bool ok, const char* message) {
    if (!ok) throw std::runtime_error(message);
}

int main() {
    cv::Mat gray(17, 23, CV_8UC1, cv::Scalar(42));
    SpyDetector spy;
    const int id = rgb_empty_mask_experiment::add_template(spy, gray, "toy");
    require(id == 17, "detector return value was changed");
    require(spy.calls == 1, "detector call count changed");
    require(spy.source == &gray, "source was cloned or replaced");
    require(spy.source->type() == CV_8UC1 && spy.source->size() == gray.size(),
            "source type or geometry changed");
    require(spy.saw_empty_mask, "third addTemplate argument was not empty");

    bool rejected_empty = false;
    try {
        cv::Mat empty;
        rgb_empty_mask_experiment::add_template(spy, empty, "toy");
    } catch (const std::invalid_argument&) {
        rejected_empty = true;
    }
    require(rejected_empty, "empty source was not rejected");

    bool rejected_color = false;
    try {
        cv::Mat color(4, 4, CV_8UC3, cv::Scalar(1, 2, 3));
        rgb_empty_mask_experiment::add_template(spy, color, "toy");
    } catch (const std::invalid_argument&) {
        rejected_color = true;
    }
    require(rejected_color, "non-grayscale source was not rejected");
    std::cout << "PASS rgb_empty_mask_source_test calls=" << spy.calls << "\n";
}
