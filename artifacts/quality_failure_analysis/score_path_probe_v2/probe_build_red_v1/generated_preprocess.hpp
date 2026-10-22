#pragma once
namespace probe_v2 {
using Memories = std::vector<std::vector<std::vector<cv::Mat>>>;
struct Maps { Memories memories;std::vector<cv::Size> sizes; };
static Maps preprocess(const cv::Mat& padded) {
    Maps result;result.memories.resize(2);result.sizes.resize(2);
    cv::Mat input=padded;
    const line2Dup::detail::ResponseLUT lut(line2Dup::SIMILARITY_LUT);
    for(int level=0;level<2;++level){
        if(level){cv::Mat next;cv::pyrDown(input,next,cv::Size(input.cols/2,input.rows/2));input=next;}
        const int T=level?8:4;need(input.cols%T==0 && input.rows%T==0,"Native pyramid grid differs");
        cv::Mat magnitude,angle,original,quantized,spread,scratch;
        line2Dup::GradientScratch gradient;
        line2Dup::quantizedOrientations(input,magnitude,angle,original,20.f,&gradient);
        quantized.create(input.size(),CV_8U);quantized.setTo(0);angle.copyTo(quantized);
        line2Dup::detail::spreadSeparable(quantized,spread,scratch,T);
        result.memories[level].resize(1);lut.linearize(spread,result.memories[level][0],T);
        result.sizes[level]=input.size();
    }return result;
}


}
