// Bounded counted-token fixture adapter for the independent tiny graph oracle.
// This file reads supplied synthetic graph records only. It performs no image,
// detector, benchmark, subprocess, or production work. See the frozen protocol.
#include "native_ordered_match.hpp"

#include <fstream>
#include <iostream>
#include <limits>
#include <new>
#include <set>
#include <string>
#include <string_view>

#ifdef _WIN32
#include <cstdio>
#include <fcntl.h>
#include <io.h>
#endif

namespace {

using namespace ordered_contour_native;

constexpr std::uint64_t max_file_bytes = 64ULL * 1024 * 1024;
constexpr std::uint64_t max_output_bytes = 64ULL * 1024 * 1024;
constexpr std::uint64_t max_requests = 100000;
constexpr std::size_t max_line_bytes = 65536;  // Excludes LF; includes CR.
constexpr std::size_t max_response_bytes = 8192;  // Includes final LF.
constexpr std::size_t max_samples = 8;
constexpr std::size_t max_pixels = 8;
constexpr std::size_t max_scenes = 16;
constexpr std::size_t max_scene_edges = 64;
constexpr std::size_t max_total_edges = 1024;
constexpr std::size_t max_weight_digits = 512;

struct ProtocolError : std::exception {
    const char* code;
    explicit ProtocolError(const char* value) : code(value) {}
    const char* what() const noexcept override { return code; }
};

struct InputIoError : std::exception {};
struct OutputIoError : std::exception {};

bool separator(char value) {
    return value == ' ' || value == '\t' || value == '\r' ||
           value == '\v' || value == '\f';
}

bool legal_character(unsigned char value) {
    return (value >= 32 && value <= 126) || value == '\t' || value == '\r' ||
           value == '\v' || value == '\f' || value == '\n';
}

// Accumulation is bounded before each push, unlike an unbounded getline.
bool read_line(std::ifstream& input, std::string& line, std::uint64_t& consumed) {
    line.clear();
    for (;;) {
        if (consumed == max_file_bytes) {
            const auto next = input.peek();
            if (next != std::char_traits<char>::eof()) throw ProtocolError("INPUT_LIMIT");
            if (input.bad() || (!input.eof() && input.fail())) throw InputIoError();
            return !line.empty();
        }
        const auto next = input.get();
        if (next == std::char_traits<char>::eof()) {
            if (input.bad() || (!input.eof() && input.fail())) throw InputIoError();
            return !line.empty();
        }
        ++consumed;  // Checked above, and max_file_bytes is far below uint64 max.
        const auto byte = static_cast<unsigned char>(next);
        if (!legal_character(byte)) throw ProtocolError("INPUT_CHARACTER");
        if (byte == '\n') return true;
        if (line.size() == max_line_bytes) throw ProtocolError("LINE_LIMIT");
        line.push_back(static_cast<char>(byte));
    }
}

struct Tokens {
    const std::string& line;
    std::size_t position = 0;

    bool empty() {
        while (position < line.size() && separator(line[position])) ++position;
        return position == line.size();
    }

    std::string_view take() {
        if (empty()) throw ProtocolError("MISSING_TOKEN");
        const auto start = position;
        while (position < line.size() && !separator(line[position])) ++position;
        return std::string_view(line.data() + start, position - start);
    }
};

Id unsigned_integer(std::string_view token) {
    if (token.empty() || token.size() > 20) throw ProtocolError("INTEGER_TOKEN_LIMIT");
    Id value = 0;
    for (char character : token) {
        if (character < '0' || character > '9') throw ProtocolError("UNSIGNED_DECIMAL");
        const Id digit = static_cast<Id>(character - '0');
        if (value > (std::numeric_limits<Id>::max() - digit) / 10) {
            throw ProtocolError("UNSIGNED_OVERFLOW");
        }
        value = value * 10 + digit;
    }
    return value;
}

std::size_t bounded_count(Tokens& tokens, std::size_t maximum) {
    const auto value = unsigned_integer(tokens.take());
    if (value > maximum) throw ProtocolError("COUNT_LIMIT");
    return static_cast<std::size_t>(value);
}

bool closed_flag(Tokens& tokens) {
    const auto token = tokens.take();
    if (token == "0") return false;
    if (token == "1") return true;
    throw ProtocolError("BOOLEAN_TOKEN");
}

Integer positive_weight(Tokens& tokens) {
    const auto token = tokens.take();
    if (token.empty() || token.size() > max_weight_digits) {
        throw ProtocolError("WEIGHT_TOKEN_LIMIT");
    }
    bool nonzero = false;
    for (char character : token) {
        if (character < '0' || character > '9') throw ProtocolError("WEIGHT_DECIMAL");
        nonzero = nonzero || character != '0';
    }
    if (!nonzero) throw ProtocolError("WEIGHT_NOT_POSITIVE");
    // Bound and validate the decimal token before GMP parses or allocates it.
    const std::string digits(token);
    Integer weight;
    if (mpz_set_str(weight.get_mpz_t(), digits.c_str(), 10) != 0) {
        throw ProtocolError("WEIGHT_DECIMAL");
    }
    return weight;
}

struct Request {
    Id request_id = 0;
    TemplateChain template_chain;
    std::vector<SceneChain> scenes;
};

Request parse_request(const std::string& line, Id& active_request_id) {
    Tokens tokens{line};
    if (tokens.empty()) throw ProtocolError("EMPTY_REQUEST");
    if (tokens.take() != "Q1") throw ProtocolError("PROTOCOL_VERSION");
    Request request;
    request.request_id = unsigned_integer(tokens.take());
    active_request_id = request.request_id;
    request.template_chain.chain_id = unsigned_integer(tokens.take());
    request.template_chain.closed = closed_flag(tokens);
    const auto n = bounded_count(tokens, max_samples);
    const auto scene_count = bounded_count(tokens, max_scenes);
    request.template_chain.sample_ids.reserve(n);
    request.template_chain.weights.reserve(n);
    std::set<Id> known_samples;
    for (std::size_t i = 0; i < n; ++i) {
        const Id sample = unsigned_integer(tokens.take());
        Integer weight = positive_weight(tokens);
        if (!known_samples.insert(sample).second) throw ProtocolError("DUPLICATE_SAMPLE");
        request.template_chain.sample_ids.push_back(sample);
        request.template_chain.weights.push_back(std::move(weight));
    }
    request.scenes.reserve(scene_count);
    std::set<Id> known_scene_ids;
    std::size_t total_edges = 0;
    for (std::size_t scene_index = 0; scene_index < scene_count; ++scene_index) {
        SceneChain scene;
        scene.chain_id = unsigned_integer(tokens.take());
        scene.closed = closed_flag(tokens);
        const auto m = bounded_count(tokens, max_pixels);
        const auto edge_count = bounded_count(tokens, max_scene_edges);
        if (edge_count > n * m) throw ProtocolError("EDGE_CAPACITY");
        if (edge_count > max_total_edges - total_edges) {
            throw ProtocolError("TOTAL_EDGE_LIMIT");
        }
        total_edges += edge_count;
        if (!known_scene_ids.insert(scene.chain_id).second) {
            throw ProtocolError("DUPLICATE_SCENE_CHAIN");
        }
        scene.pixel_ids.reserve(m);
        std::set<Id> known_pixels;
        for (std::size_t i = 0; i < m; ++i) {
            const Id pixel = unsigned_integer(tokens.take());
            if (!known_pixels.insert(pixel).second) throw ProtocolError("DUPLICATE_PIXEL");
            scene.pixel_ids.push_back(pixel);
        }
        scene.edges.reserve(edge_count);
        std::set<Edge> known_edges;
        for (std::size_t i = 0; i < edge_count; ++i) {
            const Id sample = unsigned_integer(tokens.take());
            const Id pixel = unsigned_integer(tokens.take());
            if (known_samples.find(sample) == known_samples.end() ||
                known_pixels.find(pixel) == known_pixels.end()) {
                throw ProtocolError("UNKNOWN_EDGE_ENDPOINT");
            }
            const Edge edge{sample, pixel};
            if (!known_edges.insert(edge).second) throw ProtocolError("DUPLICATE_EDGE");
            scene.edges.push_back(edge);
        }
        request.scenes.push_back(std::move(scene));
    }
    if (!tokens.empty()) throw ProtocolError("EXTRA_TOKEN");
    // All structural and graph checks precede solve, including unused scenes.
    return request;
}

struct Record {
    std::string bytes;

    Record() { bytes.reserve(2048); }

    void token(std::string_view value) {
        const std::size_t separator_bytes = bytes.empty() ? 0 : 1;
        // Reserve one byte for LF. Check subtraction before append/allocation.
        if (value.size() > max_response_bytes - 1 - bytes.size() ||
            separator_bytes > max_response_bytes - 1 - bytes.size() - value.size()) {
            throw ProtocolError("RESPONSE_LIMIT");
        }
        if (separator_bytes != 0) bytes.push_back(' ');
        bytes.append(value.data(), value.size());
    }

    void integer(const Integer& value) {
        // A valid result has <=513 decimal digits under the driver input caps.
        // Check before get_str allocates a potentially larger diagnostic value.
        if (mpz_sizeinbase(value.get_mpz_t(), 10) > max_weight_digits + 2) {
            throw ProtocolError("RESPONSE_LIMIT");
        }
        const std::string decimal = value.get_str(10);
        token(decimal);
    }

    void unsigned_value(std::uint64_t value) { token(std::to_string(value)); }

    std::string finish() {
        bytes.push_back('\n');
        return std::move(bytes);
    }
};

std::string response(Id request_id, const MatchResult& result) {
    if (result.witness.size() > max_samples) throw ProtocolError("RESPONSE_LIMIT");
    Record out;
    out.token("R1");
    out.unsigned_value(request_id);
    out.unsigned_value(result.template_chain_id);
    out.integer(result.numerator);
    out.integer(result.independent_numerator);
    out.integer(result.total_weight);
    out.token(result.selected_case ? "1" : "0");
    if (result.selected_case) {
        out.unsigned_value(result.selected_case->scene_chain_id);
        out.token(std::to_string(result.selected_case->direction));
        out.unsigned_value(result.selected_case->template_cut);
        out.unsigned_value(result.selected_case->scene_cut);
    }
    out.unsigned_value(static_cast<std::uint64_t>(result.witness.size()));
    for (const Edge& edge : result.witness) {
        out.unsigned_value(edge.first);
        out.unsigned_value(edge.second);
    }
    const auto& work = result.work;
    out.unsigned_value(work.case_count);
    out.unsigned_value(work.edge_states);
    out.unsigned_value(work.fenwick_queries);
    out.unsigned_value(work.fenwick_updates);
    out.unsigned_value(work.fenwick_query_visits);
    out.unsigned_value(work.fenwick_update_visits);
    out.unsigned_value(work.maximum_integer_bits);
    return out.finish();
}

struct Output {
    std::uint64_t emitted = 0;

    void write(const std::string& record) {
        if (record.size() > max_response_bytes) throw ProtocolError("RESPONSE_LIMIT");
        if (record.size() > max_output_bytes - emitted) throw ProtocolError("OUTPUT_LIMIT");
        std::cout.write(record.data(), static_cast<std::streamsize>(record.size()));
        std::cout.flush();
        if (!std::cout) throw OutputIoError();
        emitted += static_cast<std::uint64_t>(record.size());
    }

    void error(Id request_id, const char* code) noexcept {
        try {
            Record record;
            record.token("E1");
            record.unsigned_value(request_id);
            record.token(code);
            write(record.finish());
        } catch (...) {
            // Never emit a partial normal response to make room for an error.
            // If even E1 cannot fit, stdout ends at the last complete record.
            std::cerr << "native batch could not emit bounded error record\n";
        }
    }
};

}  // namespace

int main(int argc, char** argv) {
    if (argc != 2) {
        std::cerr << "usage: native_ordered_match_batch_v1 fixture_path\n";
        return 2;
    }
#ifdef _WIN32
    // Keep stdout caps and LF framing tied to physical bytes on Windows too.
    if (_setmode(_fileno(stdout), _O_BINARY) == -1) {
        std::cerr << "native batch could not set binary stdout\n";
        return 2;
    }
#endif
    std::ios::sync_with_stdio(false);
    Output output;
    Id active_request_id = 0;
    try {
        std::ifstream input(argv[1], std::ios::binary);
        if (!input) throw InputIoError();
        input.seekg(0, std::ios::end);
        const std::streamoff initial_size = input.tellg();
        if (initial_size < 0) throw InputIoError();
        if (static_cast<std::uint64_t>(initial_size) > max_file_bytes) {
            throw ProtocolError("INPUT_LIMIT");
        }
        input.seekg(0, std::ios::beg);
        if (!input) throw InputIoError();
        std::uint64_t consumed = 0;
        std::uint64_t requests = 0;
        std::string line;
        line.reserve(4096);
        for (;;) {
            active_request_id = 0;
            if (!read_line(input, line, consumed)) break;
            if (requests == max_requests) throw ProtocolError("REQUEST_LIMIT");
            ++requests;
            const Request request = parse_request(line, active_request_id);
            const auto result = solve(request.template_chain, request.scenes);
            const auto record = response(request.request_id, result);
            output.write(record);
        }
        return 0;
    } catch (const ProtocolError& error) {
        output.error(active_request_id, error.code);
        return 1;
    } catch (const InputIoError&) {
        output.error(active_request_id, "INPUT_IO");
        return 2;
    } catch (const OutputIoError&) {
        output.error(active_request_id, "OUTPUT_IO");
        return 2;
    } catch (const std::bad_alloc&) {
        output.error(active_request_id, "ALLOCATION_FAILURE");
        return 2;
    } catch (const std::invalid_argument&) {
        // The parser independently validated every graph before solve. A core
        // disagreement is an internal failure, never a successful rejection.
        output.error(active_request_id, "SOLVER_INVALID_GRAPH");
        return 2;
    } catch (const std::overflow_error&) {
        output.error(active_request_id, "WORK_COUNTER_OVERFLOW");
        return 2;
    } catch (const std::exception&) {
        output.error(active_request_id, "INTERNAL_ERROR");
        return 2;
    } catch (...) {
        output.error(active_request_id, "INTERNAL_ERROR");
        return 2;
    }
}
