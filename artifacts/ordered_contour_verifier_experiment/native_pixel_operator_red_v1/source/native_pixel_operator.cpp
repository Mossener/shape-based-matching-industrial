// RED-only zero stubs. Do not implement before the coordinator's actual RED.
#include "native_pixel_operator.hpp"
#include "line2Dup.h" // Build with -I pointing to the exact frozen control_v11.

namespace ordered_contour_native {
namespace pixel {

GradientFields native_gradient(const cv::Mat&, const cv::Mat&) { return {}; }
LabelGrid decode_core_bits(const cv::Mat&) { return {}; }
LabelGrid template_labels(const cv::Mat&, const cv::Mat&, const cv::Mat&) { return {}; }
PixelEvidence scene_evidence(const cv::Mat&) { return {}; }
PixelEvidence template_evidence(const cv::Mat&, const cv::Mat&) { return {}; }

} // namespace pixel
} // namespace ordered_contour_native
