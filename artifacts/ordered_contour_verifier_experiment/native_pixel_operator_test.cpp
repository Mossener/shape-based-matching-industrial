// Literal RED-first fixtures. Synthetic cv::Mat values only; no file/decode I/O.
// Expectations do not call V11 or an optimized/reference gradient helper.
#include "native_pixel_operator.hpp"

#include <algorithm>
#include <cmath>
#include <exception>
#include <functional>
#include <iostream>
#include <limits>
#include <stdexcept>
#include <string>
#include <vector>

namespace p = ordered_contour_native::pixel;

namespace {

cv::Mat bytes(const std::vector<std::vector<unsigned char>>& rows) {
    cv::Mat result(static_cast<int>(rows.size()), static_cast<int>(rows.at(0).size()), CV_8UC1);
    for (int y = 0; y < result.rows; ++y)
        for (int x = 0; x < result.cols; ++x) result.at<unsigned char>(y, x) = rows[y][x];
    return result;
}

cv::Mat floats(const std::vector<std::vector<float>>& rows) {
    cv::Mat result(static_cast<int>(rows.size()), static_cast<int>(rows.at(0).size()), CV_32FC1);
    for (int y = 0; y < result.rows; ++y)
        for (int x = 0; x < result.cols; ++x) result.at<float>(y, x) = rows[y][x];
    return result;
}

cv::Mat horizontal_ramp(int step) {
    cv::Mat result(15, 21, CV_8UC1);
    for (int y = 0; y < result.rows; ++y)
        for (int x = 0; x < result.cols; ++x)
            result.at<unsigned char>(y, x) = static_cast<unsigned char>(step * x);
    return result;
}

// Hand-derived 7-tap [2,7,14,18,14,7,2]/64 Gaussian, replicate border,
// rounded 8-bit blur, then unnormalised 3-tap Sobel. For gray=6*x the
// blurred row is 3,7,12,18,...,102,108,113,117. These are squared values.
const std::vector<float> ramp_magnitude{
    256,1296,1936,2304,2304,2304,2304,2304,2304,2304,2304,
    2304,2304,2304,2304,2304,2304,2304,1936,1296,256};

p::LabelGrid ramp_labels(bool strong) {
    p::LabelGrid result(15, std::vector<int>(21, 255));
    for (int y = 1; y < 14; ++y)
        for (int x = strong ? 2 : 1; x <= (strong ? 18 : 19); ++x) result[y][x] = 0;
    return result;
}

struct Harness {
    std::size_t tests = 0, checks = 0, failures = 0, errors = 0;
    std::string current;

    void check(bool condition, const std::string& detail) {
        ++checks;
        if (!condition) { ++failures; std::cerr << "FAIL " << current << ": " << detail << '\n'; }
    }

    void run(const std::string& name, const std::function<void()>& body) {
        ++tests; current = name;
        try { body(); }
        catch (const std::exception& error) {
            ++errors; std::cerr << "ERROR " << current << ": " << error.what() << '\n';
        }
        catch (...) { ++errors; std::cerr << "ERROR " << current << ": unknown exception\n"; }
    }

    void invalid(const std::function<void()>& body) {
        bool caught = false;
        try { body(); }
        catch (const std::invalid_argument&) { caught = true; }
        check(caught, "invalid typed/value input must throw std::invalid_argument");
    }

    void labels(const p::LabelGrid& actual, const p::LabelGrid& expected) {
        check(actual == expected, "complete label grid differs from literal expected grid");
    }

    bool shape(const cv::Mat& value, int rows, int cols, int type, const std::string& name) {
        const bool valid = value.dims == 2 && value.rows == rows && value.cols == cols && value.type() == type;
        check(valid, name + " shape/type");
        return valid;
    }

    void fields(const p::GradientFields& value, const std::vector<float>& magnitude_row,
                int height, float phase) {
        const int width = static_cast<int>(magnitude_row.size());
        const bool bit_ok = shape(value.unspread, height, width, CV_8UC1, "unspread");
        const bool mag_ok = shape(value.magnitude_squared, height, width, CV_32FC1, "magnitude_squared");
        const bool phase_ok = shape(value.phase_degrees, height, width, CV_32FC1, "phase_degrees");
        for (int y = 0; y < height; ++y) for (int x = 0; x < width; ++x) {
            if (mag_ok) check(value.magnitude_squared.at<float>(y,x) == magnitude_row[x], "each squared-magnitude pixel");
            if (phase_ok) check(value.phase_degrees.at<float>(y,x) == phase, "each phase pixel");
            if (bit_ok) {
                const unsigned char wanted = y > 0 && y + 1 < height && x > 0 && x + 1 < width
                    && magnitude_row[x] > 400 ? static_cast<unsigned char>(1) : static_cast<unsigned char>(0);
                check(value.unspread.at<unsigned char>(y,x) == wanted, "each weak20 unspread pixel");
            }
        }
    }

    void same_mat(const cv::Mat& actual, const cv::Mat& expected, int rows, int cols, int type) {
        const bool a_ok = shape(actual, rows, cols, type, "actual ROI result");
        const bool b_ok = shape(expected, rows, cols, type, "owned-clone result");
        if (!a_ok || !b_ok) return;
        for (int y = 0; y < rows; ++y) for (int x = 0; x < cols; ++x) {
            if (type == CV_8UC1) check(actual.at<unsigned char>(y,x) == expected.at<unsigned char>(y,x), "each ROI byte");
            else check(actual.at<float>(y,x) == expected.at<float>(y,x), "each ROI float");
        }
    }
};

} // namespace

int main() {
    Harness h;

    h.run("decode_zero_and_all_eight_single_bits_without_spreading", [&] {
        h.labels(p::decode_core_bits(bytes({{0,1,2,4,8,16,32,64,128}})), {{255,0,1,2,3,4,5,6,7}});
    });

    h.run("decode_rejects_every_multibit_byte", [&] {
        for (int value = 1; value < 256; ++value)
            if ((value & (value - 1)) != 0)
                h.invalid([&] { (void)p::decode_core_bits(bytes({{static_cast<unsigned char>(value)}})); });
    });

    h.run("decode_requires_nonempty_2D_unsigned_eight_bit_single_channel", [&] {
        h.invalid([&] { (void)p::decode_core_bits(cv::Mat()); });
        for (int type : {CV_8SC1, CV_16UC1, CV_32FC1, CV_8UC3})
            h.invalid([&] { (void)p::decode_core_bits(cv::Mat(2,3,type)); });
        const int sizes[] = {2,2,2};
        h.invalid([&] { (void)p::decode_core_bits(cv::Mat(3,sizes,CV_8UC1)); });
    });

    h.run("decode_odd_width_noncontinuous_ROI_uses_rows_not_flat_storage", [&] {
        cv::Mat parent(4,9,CV_8UC1,cv::Scalar(3));
        cv::Mat roi = parent(cv::Rect(2,1,5,2));
        bytes({{1,2,0,64,128},{32,16,8,4,0}}).copyTo(roi);
        h.check(!roi.isContinuous(), "fixture is strided");
        h.labels(p::decode_core_bits(roi), {{0,1,255,6,7},{5,4,3,2,255}});
    });

    h.run("template_strict_finite_squared_magnitude_and_full_nonzero_mask", [&] {
        const float nan = std::numeric_limits<float>::quiet_NaN();
        const float inf = std::numeric_limits<float>::infinity();
        h.labels(p::template_labels(bytes({{1,2,4,8,16,32,64,128,0}}),
                 floats({{1600,1600.0001220703125f,2000,nan,inf,-inf,0,2000,3000}}),
                 bytes({{255,1,0,255,255,255,255,128,255}})),
                 {{255,1,255,255,255,255,255,7,255}});
    });

    h.run("template_full_mask_is_not_eroded_or_reduced_to_local_strongest", [&] {
        h.labels(p::template_labels(bytes({{1,2,4},{8,16,32},{64,128,1}}),
                 floats({{1601,1602,1603},{1604,1605,1606},{1607,1608,1609}}),
                 bytes({{1,0,255},{0,2,0},{128,0,255}})),
                 {{0,255,2},{255,4,255},{6,255,0}});
    });

    h.run("template_decodes_invalid_bits_even_outside_mask_or_below_threshold", [&] {
        h.invalid([&] { (void)p::template_labels(bytes({{1,3}}),floats({{2000,0}}),bytes({{255,0}})); });
    });

    h.run("template_rejects_missing_wrong_type_or_mismatched_fields", [&] {
        const cv::Mat bit(2,3,CV_8UC1,cv::Scalar(1)), mag(2,3,CV_32FC1,cv::Scalar(2000));
        const cv::Mat mask(2,3,CV_8UC1,cv::Scalar(255));
        h.invalid([&] { (void)p::template_labels(bit,mag,cv::Mat()); });
        h.invalid([&] { (void)p::template_labels(bit,cv::Mat(2,3,CV_64FC1),mask); });
        h.invalid([&] { (void)p::template_labels(bit,mag,cv::Mat(2,3,CV_8SC1)); });
        h.invalid([&] { (void)p::template_labels(bit,cv::Mat(3,2,CV_32FC1),mask); });
        h.invalid([&] { (void)p::template_labels(bit,mag,cv::Mat(3,2,CV_8UC1)); });
    });

    h.run("template_selection_handles_three_independently_strided_views", [&] {
        cv::Mat bit_parent(4,9,CV_8UC1,cv::Scalar(3));
        cv::Mat mag_parent(5,10,CV_32FC1,cv::Scalar(-999));
        cv::Mat mask_parent(6,11,CV_8UC1,cv::Scalar(0));
        cv::Mat bit = bit_parent(cv::Rect(2,1,3,2));
        cv::Mat mag = mag_parent(cv::Rect(3,2,3,2));
        cv::Mat mask = mask_parent(cv::Rect(4,3,3,2));
        bytes({{1,2,4},{8,16,32}}).copyTo(bit);
        floats({{1600,1601,2000},{2001,3000,4000}}).copyTo(mag);
        bytes({{255,2,0},{128,0,1}}).copyTo(mask);
        h.labels(p::template_labels(bit,mag,mask), {{255,1,255},{3,255,5}});
    });

    h.run("native_constant_gray_has_complete_zero_magnitude_and_invalid_labels", [&] {
        const cv::Mat image(7,9,CV_8UC1,cv::Scalar(73));
        const auto value = p::scene_evidence(image);
        h.fields(value.gradient, std::vector<float>(9,0), 7, 0);
        h.labels(value.labels, p::LabelGrid(7,std::vector<int>(9,255)));
    });

    h.run("native_blur7_Sobel_squared_magnitude_replicate_borders_full_ramp", [&] {
        const auto value = p::native_gradient(horizontal_ramp(6));
        h.fields(value,ramp_magnitude,15,0);
    });

    h.run("native_scene_weak20_and_template_strong40_have_complete_distinct_grids", [&] {
        const cv::Mat image = horizontal_ramp(6);
        const auto scene = p::scene_evidence(image);
        const auto templ = p::template_evidence(image,cv::Mat(15,21,CV_8UC1,cv::Scalar(255)));
        h.labels(scene.labels,ramp_labels(false));
        h.labels(templ.labels,ramp_labels(true));
        h.fields(templ.gradient,ramp_magnitude,15,0);
    });

    h.run("native_exact_weak_squared_400_is_rejected", [&] {
        cv::Mat image(15,21,CV_8UC1);
        for (int y = 0; y < 15; ++y) for (int x = 0; x < 21; ++x)
            image.at<unsigned char>(y,x) = static_cast<unsigned char>(2*x+x/2);
        const auto value = p::scene_evidence(image);
        if (h.shape(value.gradient.magnitude_squared,15,21,CV_32FC1,"weak equality magnitude"))
            h.check(value.gradient.magnitude_squared.at<float>(7,10) == 400, "literal squared weak threshold");
        if (h.shape(value.gradient.unspread,15,21,CV_8UC1,"weak equality bits"))
            h.check(value.gradient.unspread.at<unsigned char>(7,10) == 0, "weak equality is unsupported");
        h.check(value.labels.size() == 15 && value.labels[7].size() == 21 && value.labels[7][10] == 255,
                "scene label invalid at weak equality");
    });

    h.run("native_exact_strong_squared_1600_retains_scene_but_rejects_template", [&] {
        const cv::Mat image = horizontal_ramp(5);
        const auto scene = p::scene_evidence(image);
        const auto templ = p::template_evidence(image,cv::Mat(15,21,CV_8UC1,cv::Scalar(255)));
        if (h.shape(scene.gradient.magnitude_squared,15,21,CV_32FC1,"strong equality magnitude"))
            h.check(scene.gradient.magnitude_squared.at<float>(7,10) == 1600, "literal squared strong threshold");
        h.check(scene.labels.size() == 15 && scene.labels[7].size() == 21 && scene.labels[7][10] == 0,
                "scene does not apply strong threshold");
        h.check(templ.labels.size() == 15 && templ.labels[7].size() == 21 && templ.labels[7][10] == 255,
                "template strong equality is unsupported");
    });

    h.run("native_vertical_gradient_and_zeroed_raw_border_histogram_votes", [&] {
        cv::Mat image(21,15,CV_8UC1);
        for (int y = 0; y < 21; ++y) for (int x = 0; x < 15; ++x) image.at<unsigned char>(y,x)=static_cast<unsigned char>(6*y);
        const auto value = p::scene_evidence(image);
        const bool mag_ok = h.shape(value.gradient.magnitude_squared,21,15,CV_32FC1,"vertical magnitude");
        const bool phase_ok = h.shape(value.gradient.phase_degrees,21,15,CV_32FC1,"vertical phase");
        const bool bits_ok = h.shape(value.gradient.unspread,21,15,CV_8UC1,"vertical unspread");
        p::LabelGrid wanted(21,std::vector<int>(15,255));
        for (int y = 0; y < 21; ++y) for (int x = 0; x < 15; ++x) {
            if (mag_ok) h.check(value.gradient.magnitude_squared.at<float>(y,x)==ramp_magnitude[y], "each vertical magnitude");
            if (phase_ok) h.check(value.gradient.phase_degrees.at<float>(y,x)==90, "each vertical phase");
            const bool eligible = y>0 && y<20 && x>0 && x<14;
            // The four inner corners see five forced-zero raw border bins,
            // which outvote the four bin4 neighbors despite a 90-degree center.
            const bool inner_corner = eligible && (y==1 || y==19) && (x==1 || x==13);
            const int bit = !eligible ? 0 : (inner_corner ? 1 : 16);
            if (bits_ok) h.check(value.gradient.unspread.at<unsigned char>(y,x)==bit, "each vertical histogram single bit");
            if (eligible) wanted[y][x]=inner_corner ? 0 : 4;
        }
        h.labels(value.labels,wanted);
    });

    h.run("native_opposite_horizontal_gradient_folds_180_degrees_to_bin_zero", [&] {
        cv::Mat image = horizontal_ramp(6);
        for (int y=0;y<15;++y) for(int x=0;x<21;++x) image.at<unsigned char>(y,x)=static_cast<unsigned char>(120-6*x);
        const auto value=p::scene_evidence(image);
        h.fields(value.gradient,ramp_magnitude,15,180);
        h.labels(value.labels,ramp_labels(false));
    });

    h.run("native_noncontinuous_ROI_owns_logical_border_and_ignores_parent_poison", [&] {
        cv::Mat parent_a(19,27,CV_8UC1,cv::Scalar(255)), parent_b(19,27,CV_8UC1,cv::Scalar(0));
        cv::Mat roi_a=parent_a(cv::Rect(3,2,21,15)), roi_b=parent_b(cv::Rect(3,2,21,15));
        horizontal_ramp(6).copyTo(roi_a); horizontal_ramp(6).copyTo(roi_b);
        h.check(!roi_a.isContinuous() && !roi_b.isContinuous(),"odd-width views are strided");
        const auto a=p::native_gradient(roi_a), b=p::native_gradient(roi_b), owned=p::native_gradient(roi_a.clone());
        h.fields(a,ramp_magnitude,15,0);
        h.same_mat(a.unspread,b.unspread,15,21,CV_8UC1);
        h.same_mat(a.magnitude_squared,b.magnitude_squared,15,21,CV_32FC1);
        h.same_mat(a.phase_degrees,b.phase_degrees,15,21,CV_32FC1);
        h.same_mat(a.unspread,owned.unspread,15,21,CV_8UC1);
        h.same_mat(a.magnitude_squared,owned.magnitude_squared,15,21,CV_32FC1);
        h.same_mat(a.phase_degrees,owned.phase_degrees,15,21,CV_32FC1);
    });

    h.run("native_full_official_mask_keeps_a_single_pixel_without_erosion", [&] {
        cv::Mat image=horizontal_ramp(6), mask_parent(19,27,CV_8UC1,cv::Scalar(255));
        cv::Mat mask=mask_parent(cv::Rect(3,2,21,15)); mask.setTo(0); mask.at<unsigned char>(7,10)=1;
        const auto value=p::template_evidence(image,mask);
        p::LabelGrid wanted(15,std::vector<int>(21,255)); wanted[7][10]=0;
        h.labels(value.labels,wanted);
        const bool bit_ok=h.shape(value.gradient.unspread,15,21,CV_8UC1,"full-mask bits");
        const bool mag_ok=h.shape(value.gradient.magnitude_squared,15,21,CV_32FC1,"full-mask magnitude");
        for(int y=0;y<15;++y) for(int x=0;x<21;++x) {
            if(bit_ok) h.check(value.gradient.unspread.at<unsigned char>(y,x)==((y==7&&x==10)?1:0),"each full-mask bit");
            if(mag_ok) h.check(value.gradient.magnitude_squared.at<float>(y,x)==ramp_magnitude[x],"mask does not alter gradient");
        }
    });

    h.run("native_rejects_empty_non_2D_and_non_CV_8UC1_input", [&] {
        h.invalid([&]{(void)p::native_gradient(cv::Mat());});
        for(int type:{CV_8SC1,CV_16UC1,CV_32FC1,CV_8UC3})
            h.invalid([&]{(void)p::native_gradient(cv::Mat(3,5,type));});
        const int sizes[]={2,2,2};
        h.invalid([&]{(void)p::native_gradient(cv::Mat(3,sizes,CV_8UC1));});
        h.invalid([&]{(void)p::scene_evidence(cv::Mat(3,5,CV_8UC3));});
        h.invalid([&]{(void)p::template_evidence(cv::Mat(3,5,CV_32FC1),cv::Mat(3,5,CV_8UC1));});
    });

    h.run("native_optional_mask_and_required_template_mask_have_typed_size_checks", [&] {
        const cv::Mat image(3,5,CV_8UC1,cv::Scalar(0));
        h.invalid([&]{(void)p::native_gradient(image,cv::Mat(5,3,CV_8UC1));});
        h.invalid([&]{(void)p::native_gradient(image,cv::Mat(3,5,CV_8UC3));});
        h.invalid([&]{(void)p::template_evidence(image,cv::Mat());});
        h.invalid([&]{(void)p::template_evidence(image,cv::Mat(3,5,CV_32FC1));});
        const int sizes[]={1,3,5};
        h.invalid([&]{(void)p::native_gradient(image,cv::Mat(3,sizes,CV_8UC1));});
    });

    h.run("native_tiny_images_have_valid_complete_fields_and_no_border_labels", [&] {
        for(const cv::Size size:{cv::Size(1,1),cv::Size(1,5),cv::Size(5,1),cv::Size(2,2)}) {
            const auto value=p::scene_evidence(cv::Mat(size,CV_8UC1,cv::Scalar(99)));
            h.fields(value.gradient,std::vector<float>(size.width,0),size.height,0);
            h.labels(value.labels,p::LabelGrid(size.height,std::vector<int>(size.width,255)));
        }
    });

    h.run("native_operations_do_not_mutate_caller_image_or_full_mask", [&] {
        cv::Mat image=horizontal_ramp(6), mask(15,21,CV_8UC1,cv::Scalar(128));
        auto value=p::template_evidence(image,mask);
        if(h.shape(value.gradient.unspread,15,21,CV_8UC1,"owned returned bits")) value.gradient.unspread.setTo(255);
        for(int y=0;y<15;++y) for(int x=0;x<21;++x) {
            h.check(image.at<unsigned char>(y,x)==6*x,"caller image unchanged");
            h.check(mask.at<unsigned char>(y,x)==128,"caller full mask unchanged");
        }
    });

    std::cout << "NATIVE_PIXEL_OPERATOR_TEST_SUMMARY tests=" << h.tests << " checks=" << h.checks
              << " failures=" << h.failures << " errors=" << h.errors << '\n';
    return h.failures==0 && h.errors==0 ? 0 : 1;
}
