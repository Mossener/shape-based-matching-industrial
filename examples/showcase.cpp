// Reproduce the two supplied LED/magnet samples. This is a sample-specific
// contour importer, not a general SMD reader or an accuracy evaluation.
#include "line2Dup.h"
#include <opencv2/imgcodecs.hpp>
#ifdef _OPENMP
#include <omp.h>
#endif
#include <algorithm>
#include <array>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <limits>
#include <sstream>
#include <stdexcept>
#include <string>
#include <sys/stat.h>
#include <vector>

namespace {
constexpr int levels = 3;
constexpr int repeats = 5;
constexpr int warmups = 1;
constexpr float threshold = 75.f;
const std::array<int, levels> steps{{4, 8, 8}};

void require(bool condition, const std::string& message) {
    if (!condition) throw std::runtime_error(message);
}

std::string join(const std::string& directory, const std::string& filename) {
    require(!directory.empty(), "Directory argument is empty");
    const char last = directory.back();
    return directory + ((last == '/' || last == '\\') ? "" : "/") + filename;
}

void existing_directory(const std::string& directory) {
    struct stat info{};
    require(stat(directory.c_str(), &info) == 0 && (info.st_mode & S_IFMT) == S_IFDIR,
            "Output directory must already exist: " + directory);
}

std::ofstream output_file(const std::string& filename) {
    std::ofstream result;
    result.exceptions(std::ios::badbit | std::ios::failbit);
    result.open(filename, std::ios::out | std::ios::trunc);
    result << std::setprecision(std::numeric_limits<double>::max_digits10);
    return result;
}

struct Sample {
    std::string name, model;
    std::size_t model_bytes, model_offset;
    int embedded_width, embedded_height;
    std::array<std::uint32_t, 4> roi;
    std::vector<int> widths, heights, counts;
    int image_width, image_height, image_count, initial_padding, scale_count;
    float first_scale;
    bool half_pixel_extension;
};

const Sample led{"led", "ku.smd", 74552, 67780, 184, 184, {{32, 32, 152, 152}},
    {120, 60, 30, 15}, {120, 60, 30, 15}, {236, 111, 46, 22},
    768, 576, 8, 64, 5, .9f, false};
const Sample magnet{"magnet", "moban.smd", 652672, 614468, 640, 480, {{121, 108, 535, 383}},
    {414, 207, 104, 52, 25, 13}, {275, 137, 69, 35, 18, 9}, {1214, 605, 301, 149, 73, 35},
    640, 480, 7, 128, 17, .6f, true};

template<class T> T field(const std::vector<unsigned char>& bytes, std::size_t offset) {
    require(offset <= bytes.size() && sizeof(T) <= bytes.size() - offset, "Truncated SMD field");
    T value;
    std::memcpy(&value, bytes.data() + offset, sizeof(T));
    return value;
}

std::vector<unsigned char> model_bytes(const std::string& filename, std::size_t expected) {
    static_assert(sizeof(float) == 4 && std::numeric_limits<float>::is_iec559,
                  "The supplied SMD samples require 32-bit IEEE-754 floats");
    const std::uint32_t one = 1;
    require(*reinterpret_cast<const unsigned char*>(&one) == 1, "SMD sample reader requires a little-endian host");
    std::ifstream input(filename, std::ios::binary | std::ios::ate);
    require(input.good() && input.tellg() == static_cast<std::streamoff>(expected),
            "Missing or unexpected-size supplied SMD: " + filename);
    input.seekg(0);
    std::vector<unsigned char> bytes(expected);
    require(static_cast<bool>(input.read(reinterpret_cast<char*>(bytes.data()), static_cast<std::streamsize>(expected))),
            "Cannot read complete SMD sample: " + filename);
    char extra = 0;
    require(!input.get(extra) && input.eof() && !input.bad(), "SMD sample has trailing data/read error");
    return bytes;
}

struct StoredPoint { std::uint32_t flag; float x, y, angle; };
struct Pose { float angle, scale; };

class SampleDetector : public line2Dup::Detector {
public:
    const Sample& sample;
    std::vector<std::vector<StoredPoint>> contours;
    std::vector<Pose> poses;

    SampleDetector(const Sample& specification, const std::string& filename)
        : Detector(128, {4, 8, 8}, 20.f, 40.f), sample(specification) {
        const auto bytes = model_bytes(filename, sample.model_bytes);
        const auto u = [&](std::size_t position) { return field<std::uint32_t>(bytes, position); };
        require(u(0) == 0x00444d53, "Unknown SMD sample signature");
        for (std::size_t i = 0; i < sample.roi.size(); ++i)
            require(u(4 + 4 * i) == sample.roi[i], "Unexpected sample SMD ROI header");
        std::size_t offset = 20;
        // Both embedded blocks are validated structurally. Their pixel payloads
        // are not interpreted; no unverified meaning is assigned to block two.
        const std::uint32_t pixels = static_cast<std::uint32_t>(sample.embedded_width * sample.embedded_height);
        for (int block = 0; block < 2; ++block) {
            require(u(offset) == 20161201 && u(offset + 4) == static_cast<std::uint32_t>(sample.embedded_width) &&
                    u(offset + 8) == static_cast<std::uint32_t>(sample.embedded_height) && u(offset + 12) == 1 &&
                    u(offset + 16) == static_cast<std::uint32_t>(sample.embedded_width) && u(offset + 20) == pixels,
                    "Unexpected embedded SMD image block");
            offset += 24 + pixels;
        }
        require(offset == sample.model_offset && u(offset) == 20171201 &&
                u(offset + 48) == sample.widths.size(), "Unexpected SMD model marker/level count");
        offset += 52;
        for (std::size_t level = 0; level < sample.widths.size(); ++level) {
            require(u(offset) == 2 && u(offset + 4) == level &&
                    u(offset + 8) == static_cast<std::uint32_t>(sample.widths[level]) &&
                    u(offset + 12) == static_cast<std::uint32_t>(sample.heights[level]) &&
                    u(offset + 16) == static_cast<std::uint32_t>(sample.counts[level]), "Unexpected SMD layer dimensions/count");
            offset += 20;
            std::vector<StoredPoint> points;
            points.reserve(static_cast<std::size_t>(sample.counts[level]));
            const float margin = sample.half_pixel_extension ? .5f : 0.f;
            for (int i = 0; i < sample.counts[level]; ++i, offset += 16) {
                StoredPoint p{u(offset), field<float>(bytes, offset + 4), field<float>(bytes, offset + 8), field<float>(bytes, offset + 12)};
                require(p.flag <= 3 && std::isfinite(p.x) && std::isfinite(p.y) && std::isfinite(p.angle) &&
                        p.x >= -margin && p.y >= -margin && p.x < sample.widths[level] + margin &&
                        p.y < sample.heights[level] + margin && p.angle >= 0.f && p.angle <= 360.f,
                        "Invalid SMD contour flag/coordinate/angle");
                points.push_back(p); // Preserve flags; their other meanings are not assumed.
            }
            contours.push_back(std::move(points));
        }
        require(offset == bytes.size(), "Unparsed SMD tail");
        for (int s = 0; s < sample.scale_count; ++s)
            for (int angle = 0; angle < 360; angle += 2)
                add_pose(static_cast<float>(angle), sample.first_scale + .05f * s);
        require(poses.size() == static_cast<std::size_t>(sample.scale_count * 180), "Incomplete fixed pose bank");
    }

    void add_pose(float angle, float scale) {
        std::vector<line2Dup::Template> pyramid(levels);
        const float radians = angle * static_cast<float>(CV_PI / 180.);
        const float cs = std::cos(radians), sn = std::sin(radians);
        int min_x = 100000, min_y = 100000, max_x = -100000, max_y = -100000;
        for (int level = 0; level < levels; ++level) {
            auto& layer = pyramid[static_cast<std::size_t>(level)];
            layer.pyramid_level = level;
            const float cx = sample.widths[0] / (2.f * (1 << level));
            const float cy = sample.heights[0] / (2.f * (1 << level));
            for (const auto& point : contours[static_cast<std::size_t>(level)]) {
                const float x = (point.x - cx) * scale, y = (point.y - cy) * scale;
                line2Dup::Feature feature;
                feature.x = cvRound(cs * x + sn * y + cx * scale);
                feature.y = cvRound(-sn * x + cs * y + cy * scale);
                feature.theta = std::fmod(720.f - point.angle - angle, 360.f);
                feature.label = static_cast<int>(feature.theta * 16.f / 360.f + .5f) & 7;
                layer.features.push_back(feature);
                min_x = std::min(min_x, feature.x * (1 << level));
                min_y = std::min(min_y, feature.y * (1 << level));
                max_x = std::max(max_x, feature.x * (1 << level));
                max_y = std::max(max_y, feature.y * (1 << level));
            }
        }
        // Match the validated importers: a shared L0 origin aligned to four.
        const int alignment = 1 << (levels - 1);
        min_x = static_cast<int>(std::floor(min_x / static_cast<double>(alignment))) * alignment;
        min_y = static_cast<int>(std::floor(min_y / static_cast<double>(alignment))) * alignment;
        for (int level = 0; level < levels; ++level) {
            auto& layer = pyramid[static_cast<std::size_t>(level)];
            layer.width = (max_x - min_x) >> level;
            layer.height = (max_y - min_y) >> level;
            layer.tl_x = static_cast<int>(std::floor(min_x / static_cast<double>(1 << level)));
            layer.tl_y = static_cast<int>(std::floor(min_y / static_cast<double>(1 << level)));
            for (auto& feature : layer.features) { feature.x -= layer.tl_x; feature.y -= layer.tl_y; }
        }
        class_templates[sample.name].push_back(std::move(pyramid));
        poses.push_back({angle, scale});
    }
};

struct Padding { int left, top, width, height; };
int aligned(int value) { const int alignment = 8 * (1 << (levels - 1)); return (value + alignment - 1) / alignment * alignment; }

Padding preflight(const SampleDetector& detector, std::ofstream& output) {
    const auto& sample = detector.sample;
    int width = sample.image_width + 2 * sample.initial_padding;
    int height = sample.image_height + 2 * sample.initial_padding;
    for (std::size_t id = 0; id < detector.poses.size(); ++id) {
        const auto& pyramid = detector.getTemplates(sample.name, static_cast<int>(id));
        for (int level = 0; level < levels - 1; ++level) {
            const int border = 8 * steps[static_cast<std::size_t>(level)];
            width = std::max(width, (pyramid[static_cast<std::size_t>(level)].width + 2 * border) * (1 << level));
            height = std::max(height, (pyramid[static_cast<std::size_t>(level)].height + 2 * border) * (1 << level));
        }
    }
    Padding padding{sample.initial_padding, sample.initial_padding, aligned(width), aligned(height)};
    for (std::size_t id = 0; id < detector.poses.size(); ++id) {
        const auto& pyramid = detector.getTemplates(sample.name, static_cast<int>(id));
        for (int level = 0; level < levels - 1; ++level) {
            const auto& layer = pyramid[static_cast<std::size_t>(level)];
            const int border = 8 * steps[static_cast<std::size_t>(level)];
            const int max_x = (padding.width >> level) - layer.width - border;
            const int max_y = (padding.height >> level) - layer.height - border;
            const bool feasible = max_x >= border && max_y >= border;
            output << sample.name << ',' << id << ',' << level << ',' << layer.width << ',' << layer.height << ','
                   << border << ',' << padding.width << ',' << padding.height << ',' << max_x << ',' << max_y << ',' << feasible << '\n';
            require(feasible, "Full-bank local-refinement clamp interval is infeasible");
        }
    }
    output.flush();
    return padding;
}

struct Geometry { cv::Point2f center; cv::RotatedRect region; cv::Rect2f feature_box; };
Geometry geometry(const SampleDetector& detector, const line2Dup::Match& match, const Padding& padding) {
    require(match.class_id == detector.sample.name && match.template_id >= 0 &&
            static_cast<std::size_t>(match.template_id) < detector.poses.size(), "Unknown returned sample template");
    const auto& pose = detector.poses[static_cast<std::size_t>(match.template_id)];
    const auto& layer = detector.getTemplates(match.class_id, match.template_id)[0];
    const float x = static_cast<float>(match.x - padding.left), y = static_cast<float>(match.y - padding.top);
    const cv::Point2f center(x - layer.tl_x + detector.sample.widths[0] * .5f * pose.scale,
                            y - layer.tl_y + detector.sample.heights[0] * .5f * pose.scale);
    float min_x = 1e9f, min_y = 1e9f, max_x = -1e9f, max_y = -1e9f;
    for (const auto& feature : layer.features) {
        min_x = std::min(min_x, x + feature.x); min_y = std::min(min_y, y + feature.y);
        max_x = std::max(max_x, x + feature.x); max_y = std::max(max_y, y + feature.y);
    }
    return {center, cv::RotatedRect(center,
        {detector.sample.widths[0] * pose.scale, detector.sample.heights[0] * pose.scale}, -pose.angle),
        {min_x, min_y, max_x - min_x, max_y - min_y}};
}

bool same_candidates(const std::vector<line2Dup::Match>& a, const std::vector<line2Dup::Match>& b) {
    if (a.size() != b.size()) return false;
    for (std::size_t i = 0; i < a.size(); ++i)
        if (a[i].x != b[i].x || a[i].y != b[i].y || a[i].similarity != b[i].similarity ||
            a[i].class_id != b[i].class_id || a[i].template_id != b[i].template_id) return false;
    return true;
}

void candidates_csv(std::ofstream& output, const SampleDetector& detector, const std::string& image,
                    int repeat, const Padding& padding, const std::vector<line2Dup::Match>& matches) {
    for (std::size_t rank = 0; rank < matches.size(); ++rank) {
        const auto& match = matches[rank];
        const auto g = geometry(detector, match, padding);
        const auto& pose = detector.poses[static_cast<std::size_t>(match.template_id)];
        const auto box = g.region.boundingRect2f();
        cv::Point2f corners[4]; g.region.points(corners);
        output << detector.sample.name << ',' << image << ',' << repeat << ',' << rank << ',' << match.class_id
               << ',' << match.template_id << ',' << match.similarity << ',' << pose.angle << ',' << pose.scale
               << ',' << match.x - padding.left << ',' << match.y - padding.top << ',' << g.center.x << ',' << g.center.y
               << ',' << box.x << ',' << box.y << ',' << box.width << ',' << box.height;
        for (const auto& corner : corners) output << ',' << corner.x << ',' << corner.y;
        output << ',' << g.feature_box.x << ',' << g.feature_box.y << ',' << g.feature_box.width << ',' << g.feature_box.height << '\n';
    }
}

std::string image_name(const Sample& sample, int index) {
    if (sample.name == "led") return std::to_string(index) + ".png";
    std::ostringstream name; name << 'M' << std::setfill('0') << std::setw(2) << index << ".png"; return name.str();
}

void preview(const cv::Mat& gray, const SampleDetector& detector, const std::vector<line2Dup::Match>& matches,
             const Padding& padding, const std::string& filename) {
    cv::Mat color, result;
    cv::cvtColor(gray, color, cv::COLOR_GRAY2BGR);
    const int banner = 40;
    cv::copyMakeBorder(color, result, banner, 0, 0, 0, cv::BORDER_CONSTANT, cv::Scalar(22, 24, 28));
    std::ostringstream text;
    if (matches.empty()) text << "NO MATCH >= 75";
    else {
        const auto& match = matches.front();
        const auto g = geometry(detector, match, padding);
        const auto& pose = detector.poses[static_cast<std::size_t>(match.template_id)];
        const auto& layer = detector.getTemplates(match.class_id, match.template_id)[0];
        for (const auto& f : layer.features)
            cv::circle(result, {f.x + match.x - padding.left, f.y + match.y - padding.top + banner}, 1, {0, 255, 0}, -1, cv::LINE_AA);
        cv::Point2f corners[4]; g.region.points(corners);
        for (int i = 0; i < 4; ++i)
            cv::line(result, corners[i] + cv::Point2f(0.f, static_cast<float>(banner)),
                corners[(i + 1) % 4] + cv::Point2f(0.f, static_cast<float>(banner)), {0, 210, 255}, 1, cv::LINE_AA);
        cv::drawMarker(result, g.center + cv::Point2f(0.f, static_cast<float>(banner)), {0, 210, 255}, cv::MARKER_CROSS, 15, 1, cv::LINE_AA);
        text << std::fixed << std::setprecision(1) << "Top candidate: " << match.similarity << " | " << pose.angle << " deg | scale " << std::setprecision(2) << pose.scale;
    }
    cv::putText(result, text.str(), {10, 27}, cv::FONT_HERSHEY_SIMPLEX, .58, {235, 235, 235}, 1, cv::LINE_AA);
    require(cv::imwrite(filename, result, {cv::IMWRITE_PNG_COMPRESSION, 9}), "Cannot save preview: " + filename);
}

void run_sample(const Sample& sample, const std::string& data, const std::string& output,
                std::ofstream& timings, std::ofstream& raw, std::ofstream& preflight_csv, std::ofstream& summary) {
    const auto input = join(data, sample.name);
    SampleDetector detector(sample, join(input, sample.model));
    const auto padding = preflight(detector, preflight_csv);
    line2Dup::MatchWorkspace workspace;
    const line2Dup::MatchOptions options;
    for (int index = 1; index <= sample.image_count; ++index) {
        const auto name = image_name(sample, index);
        const cv::Mat gray = cv::imread(join(input, name), cv::IMREAD_GRAYSCALE);
        require(!gray.empty() && gray.type() == CV_8UC1 && gray.size() == cv::Size(sample.image_width, sample.image_height),
                "Cannot decode expected-size sample image: " + join(input, name));
        cv::Mat padded;
        cv::copyMakeBorder(gray, padded, padding.top, padding.height - gray.rows - padding.top,
            padding.left, padding.width - gray.cols - padding.left, cv::BORDER_CONSTANT, cv::Scalar(0));
        std::vector<line2Dup::Match> first;
        bool all_same = true;
        for (int repeat = -warmups; repeat < repeats; ++repeat) {
            line2Dup::MatchTimings timing;
            const auto started = std::chrono::steady_clock::now();
            const auto matches = detector.match(padded, threshold, workspace, options, &timing, {sample.name});
            const double wall_ms = std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now() - started).count();
            if (repeat == 0) first = matches;
            const bool same = repeat <= 0 || same_candidates(first, matches);
            if (repeat >= 0) all_same = all_same && same;
            timings << sample.name << ',' << name << ',' << (repeat < 0 ? "warmup" : "measured") << ',' << repeat
                    << ',' << wall_ms << ',' << timing.preprocess_ms << ',' << timing.search_ms << ',' << timing.total_ms
                    << ',' << matches.size() << ',';
            if (!matches.empty()) timings << matches.front().similarity;
            timings << ',';
            if (repeat >= 0) timings << same;
            timings << '\n';
            if (repeat >= 0) candidates_csv(raw, detector, name, repeat, padding, matches);
        }
        timings.flush(); raw.flush();
        summary << sample.name << ',' << name << ',' << (index == 1 ? "template_source_sample" : "additional_sample")
                << ',' << first.size() << ',' << all_same << ',' << padding.left << ',' << padding.top << ','
                << padding.width << ',' << padding.height << ',';
        if (!first.empty()) {
            const auto& match = first.front();
            const auto g = geometry(detector, match, padding);
            const auto& pose = detector.poses[static_cast<std::size_t>(match.template_id)];
            summary << match.template_id << ',' << match.similarity << ',' << pose.angle << ',' << pose.scale << ',' << g.center.x << ',' << g.center.y;
        } else summary << ",,,,,";
        summary << '\n'; summary.flush();
        const std::string stem = sample.name + "_" + name;
        preview(gray, detector, first, padding, join(output, stem));
        std::cout << sample.name << '/' << name << ": returned_candidates=" << first.size()
                  << " repeats_identical=" << all_same << " (preview uses first measured call)\n";
    }
}
} // namespace

int main(int argc, char** argv) {
    try {
        if (argc != 3) {
            std::cout << "Usage: showcase_example DATA_DIR OUTPUT_DIR\n"
                         "OUTPUT_DIR must exist. Reads only the supplied led/ and magnet/ PNG/SMD layouts.\n";
            return argc == 2 && std::string(argv[1]) == "--help" ? 0 : 2;
        }
        const std::string data = argv[1], output = argv[2];
        existing_directory(output);
        cv::setNumThreads(1);
        int omp_threads = 0;
#ifdef _OPENMP
        omp_set_dynamic(0);
        omp_set_num_threads(4);
        omp_threads = 4;
#endif
        auto config = output_file(join(output, "run_config.json"));
        config << "{\"scope\":\"two supplied sample-specific SMD layouts only\",\"levels\":3,\"T\":[4,8,8],"
               << "\"threshold\":75,\"angle_step\":2,\"led_poses\":900,\"led_scales\":[0.9,0.95,1,1.05,1.1],"
               << "\"magnet_poses\":3060,\"magnet_scale_first\":0.6,\"magnet_scale_step\":0.05,\"magnet_scale_count\":17,"
               << "\"warmups_per_image\":1,\"measured_calls_per_image\":5,\"opencv_threads\":1,\"openmp_threads\":" << omp_threads
               << ",\"preview_call\":0,\"candidate_semantics\":\"all match API returned candidates for each measured call, before display top1; not object counts or internal intermediate hypotheses\","
               << "\"timing_scope\":\"match call only; excludes image decode, bank construction, padding, CSV, rendering and PNG save\","
               << "\"evaluation\":\"no GT accuracy evaluation or extra NMS; model region is not an annotated object boundary\"}\n";
        config.close();
        auto timings = output_file(join(output, "timings.csv"));
        timings << "sample,image,phase,repeat,match_wall_ms,preprocess_ms,search_ms,api_total_ms,returned_candidates,best_score,identical_to_first_measured\n";
        auto raw = output_file(join(output, "candidates.csv"));
        raw << "sample,image,repeat,rank,class_id,template_id,score,angle_degrees,scale,feature_origin_x,feature_origin_y,center_x,center_y,region_bbox_x,region_bbox_y,region_bbox_w,region_bbox_h,corner0_x,corner0_y,corner1_x,corner1_y,corner2_x,corner2_y,corner3_x,corner3_y,feature_bbox_x,feature_bbox_y,feature_bbox_w_max_minus_min,feature_bbox_h_max_minus_min\n";
        auto preflight_csv = output_file(join(output, "padding_preflight.csv"));
        preflight_csv << "sample,template_id,level,template_width,template_height,refinement_border,padded_width,padded_height,max_x,max_y,feasible\n";
        auto summary = output_file(join(output, "results.csv"));
        summary << "sample,image,role,first_returned_candidates,measured_calls_identical,pad_left,pad_top,padded_width,padded_height,best_template_id,best_score,angle_degrees,scale,center_x,center_y\n";
        run_sample(led, data, output, timings, raw, preflight_csv, summary);
        run_sample(magnet, data, output, timings, raw, preflight_csv, summary);
        timings.close(); raw.close(); preflight_csv.close(); summary.close();
        std::cout << "Done. Empty matches are retained; candidate counts are not object counts. No accuracy claim.\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "Error: " << error.what() << '\n';
        return 1;
    }
}
