#include "native_pixel_operator.hpp"
#include "line2Dup.h" // Build with -I pointing to the exact frozen control_v11.

#include <cmath>
#include <stdexcept>
#include <string>
#include <utility>

namespace ordered_contour_native {
namespace pixel {

namespace {

void require_matrix(const cv::Mat& value, int type, const char* name) {
    if (value.empty() || value.dims != 2 || value.rows <= 0 || value.cols <= 0 ||
        value.type() != type)
        throw std::invalid_argument(std::string(name) + " must be nonempty 2-D matrix of the required type");
}

void require_size(const cv::Mat& value, const cv::Mat& reference, const char* name) {
    if (value.rows != reference.rows || value.cols != reference.cols)
        throw std::invalid_argument(std::string(name) + " size must match unspread/image size");
}

} // namespace

GradientFields native_gradient(const cv::Mat& grayscale, const cv::Mat& mask) {
    require_matrix(grayscale, CV_8UC1, "grayscale");
    if (!mask.empty()) {
        require_matrix(mask, CV_8UC1, "mask");
        require_size(mask, grayscale, "mask");
    }

    // OpenCV filtering can see the parent of a submatrix unless isolated.
    // Owning the supplied logical rows gives exactly the standalone image's
    // replicate borders and prevents caller mutation through shallow Mat data.
    const cv::Mat owned_image = grayscale.clone();
    const cv::Mat owned_mask = mask.empty() ? cv::Mat() : mask.clone();
    line2Dup::ColorGradientPyramid gradient(owned_image, owned_mask, 20.0f, 32, 40.0f);
    cv::Mat bits;
    gradient.quantize(bits);
    return {bits.clone(), gradient.magnitude.clone(), gradient.angle_ori.clone()};
}

LabelGrid decode_core_bits(const cv::Mat& unspread) {
    require_matrix(unspread, CV_8UC1, "unspread");
    LabelGrid labels(static_cast<std::size_t>(unspread.rows),
                     std::vector<int>(static_cast<std::size_t>(unspread.cols), 255));
    for (int y = 0; y < unspread.rows; ++y) {
        const unsigned char* row = unspread.ptr<unsigned char>(y);
        for (int x = 0; x < unspread.cols; ++x) {
            const unsigned int bits = row[x];
            if (bits == 0) continue;
            if ((bits & (bits - 1)) != 0)
                throw std::invalid_argument("Unspread byte must be zero or exactly one orientation bit");
            int label = 0;
            for (unsigned int remaining = bits; remaining > 1; remaining >>= 1) ++label;
            labels[static_cast<std::size_t>(y)][static_cast<std::size_t>(x)] = label;
        }
    }
    return labels;
}

LabelGrid template_labels(const cv::Mat& unspread, const cv::Mat& magnitude_squared,
                          const cv::Mat& full_mask) {
    require_matrix(unspread, CV_8UC1, "unspread");
    require_matrix(magnitude_squared, CV_32FC1, "magnitude_squared");
    require_matrix(full_mask, CV_8UC1, "full_mask");
    require_size(magnitude_squared, unspread, "magnitude_squared");
    require_size(full_mask, unspread, "full_mask");
    // Decode every byte before applying any mask or threshold. A malformed
    // spread byte may not become valid merely because selection would hide it.
    LabelGrid labels = decode_core_bits(unspread);
    for (int y = 0; y < unspread.rows; ++y) {
        const float* magnitude_row = magnitude_squared.ptr<float>(y);
        const unsigned char* mask_row = full_mask.ptr<unsigned char>(y);
        for (int x = 0; x < unspread.cols; ++x)
            if (mask_row[x] == 0 || !std::isfinite(magnitude_row[x]) || magnitude_row[x] <= 1600.0f)
                labels[static_cast<std::size_t>(y)][static_cast<std::size_t>(x)] = 255;
    }
    return labels;
}

PixelEvidence scene_evidence(const cv::Mat& grayscale) {
    GradientFields gradient = native_gradient(grayscale);
    LabelGrid labels = decode_core_bits(gradient.unspread);
    return {std::move(gradient), std::move(labels)};
}

PixelEvidence template_evidence(const cv::Mat& grayscale, const cv::Mat& full_mask) {
    require_matrix(grayscale, CV_8UC1, "grayscale");
    require_matrix(full_mask, CV_8UC1, "full_mask");
    require_size(full_mask, grayscale, "full_mask");
    GradientFields gradient = native_gradient(grayscale, full_mask);
    LabelGrid labels = template_labels(gradient.unspread, gradient.magnitude_squared, full_mask);
    return {std::move(gradient), std::move(labels)};
}

} // namespace pixel
} // namespace ordered_contour_native
