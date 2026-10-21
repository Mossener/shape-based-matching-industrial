// Compare internal stages with the frozen original, in separate namespaces.
#define line2Dup referenceLine2Dup
#define shape_based_matching referenceShapeBasedMatching
#define Timer ReferenceTimer
#include "../artifacts/response_optimization/baseline/line2Dup.cpp"
#undef Timer
#undef line2Dup
#undef shape_based_matching
#undef CXXLINEMOD_H
#define Timer OptimizedTimer
#include "../line2Dup.cpp"
#undef Timer

#include <stdexcept>

static int checks = 0;
static void equal(const cv::Mat& a, const cv::Mat& b) {
    if (a.size() != b.size() || a.type() != b.type())
        throw std::runtime_error("Intermediate data differs from immutable original");
    for(int row=0; row<a.rows; ++row)
        if(std::memcmp(a.ptr(row),b.ptr(row),a.cols*a.elemSize())!=0)
            throw std::runtime_error("Intermediate bytes differ from immutable original");
    ++checks;
}

int main() {
    try {
        cv::setNumThreads(1);
        cv::RNG random(0x5829);
        line2Dup::GradientScratch scratch;
        cv::Mat mag, angle, original_angle, quantized, spread, horizontal;
        std::vector<cv::Mat> response(8), memories(8);
        const line2Dup::detail::ResponseLUT lut(line2Dup::SIMILARITY_LUT);
        for (int sequence=0; sequence<24; ++sequence) {
            const int type = sequence%3 == 0 ? CV_8UC3 : CV_8UC1;
            const int width = sequence%2 ? 128 : 192;
            const int height = sequence%4 ? 128 : 192;
            cv::Mat parent(height+9,width+13,type);
            random.fill(parent,cv::RNG::UNIFORM,0,256);
            cv::Mat src = parent(cv::Rect(3,4,width,height));
            cv::Mat mask(height,width,CV_8U,cv::Scalar(0));
            if (sequence%4 == 1) mask.setTo(255);
            if (sequence%4 == 2) mask(cv::Rect(0,0,width/2,height)).setTo(255);
            if (sequence%4 == 3) mask.release();
            const float weak = sequence%2 ? 20.f : 50.f;
            for (int level=0; level<3; ++level) {
                cv::Mat expected_mag, expected_angle, expected_original_angle;
                referenceLine2Dup::quantizedOrientations(src,expected_mag,expected_angle,expected_original_angle,weak);
                line2Dup::quantizedOrientations(src,mag,angle,original_angle,weak,&scratch);
                equal(mag,expected_mag); equal(angle,expected_angle); equal(original_angle,expected_original_angle);
                cv::Mat expected_quantized = cv::Mat::zeros(angle.size(),CV_8U);
                expected_angle.copyTo(expected_quantized,mask);
                quantized.create(angle.size(),CV_8U); quantized.setTo(0); angle.copyTo(quantized,mask);
                equal(quantized,expected_quantized);
                const int T = level ? 8 : 4;
                cv::Mat expected_spread;
                referenceLine2Dup::spread(expected_quantized,expected_spread,T);
                line2Dup::detail::spreadSeparable(quantized,spread,horizontal,T);
                equal(spread,expected_spread);
                std::vector<cv::Mat> expected_response(8), expected_memories(8);
                referenceLine2Dup::computeResponseMaps(expected_spread,expected_response);
                for(int ori=0;ori<8;++ori) referenceLine2Dup::linearize(expected_response[ori],expected_memories[ori],T);
                line2Dup::computeResponseMaps(spread,response,&scratch.response_low,&scratch.response_high);
                for(int ori=0;ori<8;++ori) equal(response[ori],expected_response[ori]);
                lut.linearize(spread,memories,T);
                for(int ori=0;ori<8;++ori) equal(memories[ori],expected_memories[ori]);
                cv::Mat next;
                cv::pyrDown(src,next,cv::Size(src.cols/2,src.rows/2)); src=next;
                if(!mask.empty()) { cv::Mat next_mask; cv::resize(mask,next_mask,src.size(),0,0,cv::INTER_NEAREST); mask=next_mask; }
            }
        }
        // An identical warm frame keeps the gradient temporary allocations.
        cv::Mat source(128,128,CV_8UC1); random.fill(source,cv::RNG::UNIFORM,0,256);
        line2Dup::quantizedOrientations(source,mag,angle,original_angle,20,&scratch);
        const auto* blur_allocation=scratch.smoothed.data;
        const auto* dx_allocation=scratch.sobel_dx.data;
        const auto* unfiltered_allocation=scratch.quantized_unfiltered.data;
        line2Dup::quantizedOrientations(source,mag,angle,original_angle,20,&scratch);
        if(blur_allocation!=scratch.smoothed.data || dx_allocation!=scratch.sobel_dx.data ||
           unfiltered_allocation!=scratch.quantized_unfiltered.data)
            throw std::runtime_error("Warm gradient buffers were not retained");
        std::cout << "PASS pipeline: " << checks << " exact intermediate comparisons; warm allocations retained\n";
        return 0;
    } catch(const std::exception& e) { std::cerr << e.what() << '\n'; return 1; }
}
