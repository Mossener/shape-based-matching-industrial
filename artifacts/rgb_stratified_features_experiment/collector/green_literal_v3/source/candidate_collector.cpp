#include "candidate_collector.hpp"
#include <opencv2/imgproc.hpp>
#include <cmath>
#include <cstring>
#include <limits>
#include <stdexcept>

namespace {
void validate_map(const cv::Mat& map, int type, const cv::Size& size) {
    if (map.empty() || map.dims != 2 || map.type() != type || map.size() != size)
        throw std::invalid_argument("Collector requires nonempty same-size 2D typed maps");
}
bool valid_one_bit(unsigned char value) {
    return value != 0 && (value & (value-1)) == 0;
}
std::uint32_t float_bits(const float* source) {
    static_assert(sizeof(float)==sizeof(std::uint32_t), "Requires float32");
    std::uint32_t value;
    std::memcpy(&value,source,sizeof(value));
    return value;
}
}

namespace rgb_stratified { namespace collector {

Result collect(const cv::Mat& magnitude, const cv::Mat& quantized_angle,
               const cv::Mat& angle_ori, const cv::Mat& official_mask) {
    // MatSize::operator() itself asserts for >2D, so reject before size().
    if (magnitude.empty() || magnitude.dims != 2 || magnitude.type() != CV_32FC1)
        throw std::invalid_argument("Collector requires nonempty 2D CV32F magnitude");
    validate_map(magnitude,CV_32FC1,magnitude.size());
    validate_map(quantized_angle,CV_8UC1,magnitude.size());
    validate_map(angle_ori,CV_32FC1,magnitude.size());
    validate_map(official_mask,CV_8UC1,magnitude.size());
    for (int y=0;y<magnitude.rows;++y) {
        const float* row=magnitude.ptr<float>(y);
        for (int x=0;x<magnitude.cols;++x)
            if (!std::isfinite(row[x]))
                throw std::invalid_argument("Nonfinite collector magnitude");
    }

    Result result;
    result.actual_mask=official_mask.clone();
    cv::Mat binary;
    cv::compare(official_mask, 0, binary, cv::CMP_NE);
    const cv::Mat kernel=cv::Mat::ones(9,9,CV_8U);
    cv::dilate(binary,result.domain,kernel,cv::Point(-1,-1),1,
               cv::BORDER_CONSTANT,cv::Scalar(0));
    cv::erode(binary,result.interior,kernel,cv::Point(-1,-1),1,
              cv::BORDER_CONSTANT,cv::Scalar(0));
    cv::Mat valid(magnitude.size(), CV_8U, cv::Scalar(255));
    // Fixed two-pixel margin makes every 5x5 neighbor access valid, even on
    // non-contiguous Mats. Tiny maps retain full sidecars but have no scan.
    for (int y=2;y<magnitude.rows-2;++y) {
        const unsigned char* domain_row=result.domain.ptr<unsigned char>(y);
        for (int x=2;x<magnitude.cols-2;++x) {
            if (!domain_row[x] || !valid.at<unsigned char>(y,x)) continue;
            const float score=magnitude.at<float>(y,x);
            bool is_max=true;
            for (int dy=-2;dy<=2;++dy) {
                for (int dx=-2;dx<=2;++dx) {
                    if (dx==0 && dy==0) continue;
                    if (score < magnitude.at<float>(y+dy,x+dx)) {
                        is_max=false;break;
                    }
                }
                if (!is_max) break;
            }
            if (!is_max) continue;
            ++result.nms_maxima;
            // As in V11: suppress before strength / angle acceptance, and
            // compare every neighbor magnitude regardless of mask membership.
            for (int dy=-2;dy<=2;++dy) for (int dx=-2;dx<=2;++dx) {
                if (dx==0 && dy==0) continue;
                valid.at<unsigned char>(y+dy,x+dx)=0;
            }
            const unsigned char angle=quantized_angle.at<unsigned char>(y,x);
            if (score > 1600.0f && angle > 0) {
                if (!valid_one_bit(angle))
                    CV_Error(cv::Error::StsBadArg, "Invalid value of quantized parameter");
                if (result.candidates.size()>std::numeric_limits<std::uint32_t>::max())
                    throw std::overflow_error("Collector ordinal exceeds uint32");
                unsigned char label=0;
                for (unsigned int value=angle;value>1;value>>=1) ++label;
                result.candidates.push_back(Candidate{
                    static_cast<std::uint32_t>(result.candidates.size()),x,y,label,
                    float_bits(magnitude.ptr<float>(y)+x),
                    float_bits(angle_ori.ptr<float>(y)+x),
                    result.interior.at<unsigned char>(y,x)!=0});
            }
        }
    }
    return result;
}

}}
