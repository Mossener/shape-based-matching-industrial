// Bounded supplied-label candidate validation adapter; no images or detector.
// Full Python-named observable evidence is serialized, excluding work counters.
#include "native_candidate_compatibility.hpp"

#include <fstream>
#include <iostream>
#include <limits>
#include <new>
#include <string>
#include <string_view>

#ifdef _WIN32
#include <cstdio>
#include <fcntl.h>
#include <io.h>
#endif

namespace {

namespace n = ordered_contour_native;
namespace e = ordered_contour_native::edge;
namespace c = ordered_contour_native::candidate;
using n::Id;
using n::Integer;

constexpr std::uint64_t max_file_bytes = 64ULL * 1024 * 1024;
constexpr std::uint64_t max_output_bytes = 64ULL * 1024 * 1024;
constexpr std::uint64_t max_requests = 10000;
constexpr std::size_t max_line_bytes = 131072;
constexpr Id max_dimension = 16;
constexpr Id max_cells = 256;
constexpr std::size_t max_owned_per_chain = 8;
constexpr std::size_t max_scene_chain_pixels = 8;
constexpr std::size_t max_integer_decimal_digits = 128;

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
        ++consumed;
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

c::Coordinate signed_integer(std::string_view token) {
    if (token.empty() || token.size() > 20) throw ProtocolError("INTEGER_TOKEN_LIMIT");
    const bool negative = token.front() == '-';
    const std::size_t start = negative ? 1 : 0;
    if (start == token.size()) throw ProtocolError("SIGNED_DECIMAL");
    const Id positive_limit = static_cast<Id>(std::numeric_limits<c::Coordinate>::max());
    const Id limit = negative ? positive_limit + 1 : positive_limit;
    Id magnitude = 0;
    for (std::size_t index = start; index < token.size(); ++index) {
        const char character = token[index];
        if (character < '0' || character > '9') throw ProtocolError("SIGNED_DECIMAL");
        const Id digit = static_cast<Id>(character - '0');
        if (magnitude > (limit - digit) / 10) throw ProtocolError("SIGNED_OVERFLOW");
        magnitude = magnitude * 10 + digit;
    }
    if (negative && magnitude == positive_limit + 1) return std::numeric_limits<c::Coordinate>::min();
    const auto value = static_cast<c::Coordinate>(magnitude);
    return negative ? -value : value;
}

Id dimension(Tokens& tokens) {
    const Id value = unsigned_integer(tokens.take());
    if (value == 0) throw ProtocolError("DIMENSION_ZERO");
    if (value > max_dimension) throw ProtocolError("DIMENSION_LIMIT");
    return value;
}

e::LabelGrid parse_grid(Tokens& tokens, Id width, Id height) {
    if (height > max_cells / width) throw ProtocolError("CELL_LIMIT");
    e::LabelGrid grid(static_cast<std::size_t>(height));
    for (auto& row : grid) {
        row.resize(static_cast<std::size_t>(width));
        for (int& label : row) {
            const Id value = unsigned_integer(tokens.take());
            if (!(value <= 7 || value == 255)) throw ProtocolError("LABEL_VALUE");
            label = static_cast<int>(value);
        }
    }
    return grid;
}

struct Request {
    Id request_id = 0;
    e::LabelGrid templ;
    e::LabelGrid scene;
    c::Point tl{};
    c::Point match{};
    c::Padding padding{};
};

Request parse_request(const std::string& line, Id& active_request_id) {
    Tokens tokens{line};
    if (tokens.empty()) throw ProtocolError("EMPTY_REQUEST");
    if (tokens.take() != "C1") throw ProtocolError("PROTOCOL_VERSION");
    Request request;
    request.request_id = unsigned_integer(tokens.take());
    active_request_id = request.request_id;
    const Id tw = dimension(tokens), th = dimension(tokens);
    const Id sw = dimension(tokens), sh = dimension(tokens);
    for (auto& coordinate : request.tl) coordinate = signed_integer(tokens.take());
    for (auto& coordinate : request.match) coordinate = signed_integer(tokens.take());
    for (auto& padding : request.padding) padding = signed_integer(tokens.take());
    request.templ = parse_grid(tokens, tw, th);
    request.scene = parse_grid(tokens, sw, sh);
    if (!tokens.empty()) throw ProtocolError("EXTRA_TOKEN");
    for (auto value : request.padding) {
        if (value < 0) throw ProtocolError("PADDING_NEGATIVE");
    }
    constexpr auto coordinate_maximum = std::numeric_limits<c::Coordinate>::max();
    if (request.padding[0] > coordinate_maximum - request.padding[2] ||
        request.padding[1] > coordinate_maximum - request.padding[3]) {
        throw ProtocolError("PADDING_OVERFLOW");
    }
    if (request.padding[0] + request.padding[2] >= static_cast<c::Coordinate>(sw) ||
        request.padding[1] + request.padding[3] >= static_cast<c::Coordinate>(sh)) {
        throw ProtocolError("PADDING_EXTENT");
    }
    return request;
}

c::Coordinate checked_add(c::Coordinate left, c::Coordinate right) {
    constexpr auto low = std::numeric_limits<c::Coordinate>::min();
    constexpr auto high = std::numeric_limits<c::Coordinate>::max();
    if ((right > 0 && left > high - right) || (right < 0 && left < low - right)) {
        throw ProtocolError("COORDINATE_DOMAIN");
    }
    return left + right;
}

c::Coordinate checked_subtract(c::Coordinate left, c::Coordinate right) {
    constexpr auto low = std::numeric_limits<c::Coordinate>::min();
    constexpr auto high = std::numeric_limits<c::Coordinate>::max();
    if ((right > 0 && left < low + right) || (right < 0 && left > high + right)) {
        throw ProtocolError("COORDINATE_DOMAIN");
    }
    return left - right;
}

struct Evidence {
    c::SceneEvidence scene;
    c::CandidateScore score;
};

Evidence evaluate(const Request& request) {
    // Distinguish a legal-label but forbidden empty template from unexpected
    // native factory rejection without weakening failures into successful data.
    const auto thin = e::thin_labels(request.templ);
    bool empty = true;
    for (const auto& row : thin.labels) for (int label : row) if (label != 255) empty = false;
    if (empty) throw ProtocolError("TEMPLATE_EMPTY");
    const auto templ = e::prepare_template(request.templ);
    auto scene = c::prepare_scene(request.scene);
    std::map<Id, std::size_t> owned_counts;
    for (const auto& sample : templ.samples) {
        auto& count = owned_counts[sample.owner_chain_id];
        if (count == max_owned_per_chain) throw ProtocolError("ORACLE_CHAIN_LIMIT");
        ++count;
        const c::Point canvas{static_cast<c::Coordinate>(sample.x), static_cast<c::Coordinate>(sample.y)};
        c::Point relative{}, padded{};
        for (std::size_t axis = 0; axis < 2; ++axis) relative[axis] = checked_subtract(canvas[axis], request.tl[axis]);
        for (std::size_t axis = 0; axis < 2; ++axis) padded[axis] = checked_add(request.match[axis], relative[axis]);
        for (std::size_t axis = 0; axis < 2; ++axis) (void)checked_subtract(padded[axis], request.padding[axis]);
    }
    // Check every scene chain, even if it has no compatibility edge.
    for (const auto& chain : scene.chains) {
        if (chain.pixel_ids.size() > max_scene_chain_pixels) throw ProtocolError("ORACLE_CHAIN_LIMIT");
    }
    auto score = c::score_candidate(templ, scene, request.tl, request.match, request.padding);
    return {std::move(scene), std::move(score)};
}

struct JsonRecord {
    std::string bytes;
    std::size_t limit;
    explicit JsonRecord(std::size_t maximum) : limit(maximum) {
        bytes.reserve(std::min<std::size_t>(4096, maximum));
    }
    void append(std::string_view value) {
        if (limit == 0 || bytes.size() >= limit || value.size() > limit - 1 - bytes.size()) {
            throw ProtocolError("OUTPUT_LIMIT");
        }
        bytes.append(value.data(), value.size());
    }
    void unsigned_value(Id value) { append(std::to_string(value)); }
    void coordinate(c::Coordinate value) { append(std::to_string(value)); }
    void small_integer(int value) { append(std::to_string(value)); }
    void boolean(bool value) { append(value ? "true" : "false"); }
    void integer(const Integer& value) {
        if (mpz_sgn(value.get_mpz_t()) < 0 ||
            mpz_sizeinbase(value.get_mpz_t(), 10) > max_integer_decimal_digits) {
            throw std::overflow_error("candidate integer exceeds bounded serialization domain");
        }
        const std::string decimal = value.get_str(10);
        append(decimal);
    }
    std::string finish() {
        if (bytes.size() >= limit) throw ProtocolError("OUTPUT_LIMIT");
        bytes.push_back('\n');
        return std::move(bytes);
    }
};

template <typename Range, typename Write>
void array(JsonRecord& out, const Range& values, Write write) {
    out.append("[");
    bool first = true;
    for (const auto& value : values) {
        if (!first) out.append(",");
        first = false;
        write(out, value);
    }
    out.append("]");
}

void ids(JsonRecord& out, const std::vector<Id>& values) {
    array(out, values, [](JsonRecord& record, Id value) { record.unsigned_value(value); });
}
void point(JsonRecord& out, const c::Point& value) {
    array(out, value, [](JsonRecord& record, c::Coordinate coordinate) { record.coordinate(coordinate); });
}
void grid(JsonRecord& out, const e::LabelGrid& value) {
    array(out, value, [](JsonRecord& record, const std::vector<int>& row) {
        array(record, row, [](JsonRecord& cell, int label) { cell.small_integer(label); });
    });
}
void thinning(JsonRecord& out, const e::ThinningResult& value) {
    out.append("{\"width\":"); out.unsigned_value(value.width);
    out.append(",\"height\":"); out.unsigned_value(value.height);
    out.append(",\"eligible_labels\":"); grid(out, value.eligible_labels);
    out.append(",\"labels\":"); grid(out, value.labels);
    out.append(",\"round_deletions\":");
    array(out, value.round_deletions, [](JsonRecord& record, const e::DeletionRound& counts) {
        record.append("["); record.unsigned_value(counts.first);
        record.append(","); record.unsigned_value(counts.second); record.append("]");
    });
    out.append("}");
}
void chain(JsonRecord& out, const e::Chain& value) {
    out.append("{\"chain_id\":"); out.unsigned_value(value.chain_id);
    out.append(",\"pixel_ids\":"); ids(out, value.pixel_ids);
    out.append(",\"closed\":"); out.boolean(value.closed);
    out.append(",\"returning\":"); out.boolean(value.returning); out.append("}");
}
void scene(JsonRecord& out, const c::SceneEvidence& value) {
    out.append("{\"thinning\":"); thinning(out, value.thinning);
    out.append(",\"chains\":"); array(out, value.chains, chain);
    out.append(",\"memberships\":");
    array(out, value.memberships, [](JsonRecord& record, const c::ScenePixelMembership& row) {
        record.append("{\"pixel_id\":"); record.unsigned_value(row.pixel_id);
        record.append(",\"members\":");
        array(record, row.members, [](JsonRecord& member_record, const c::SceneChainMember& member) {
            member_record.append("{\"chain_id\":"); member_record.unsigned_value(member.chain_id);
            member_record.append(",\"chain_index\":"); member_record.unsigned_value(member.chain_index);
            member_record.append("}");
        });
        record.append("}");
    });
    out.append("}");
}
void support(JsonRecord& out, const c::SampleSupport& value) {
    out.append("{\"sample_id\":"); out.unsigned_value(value.sample_id);
    out.append(",\"p_canvas\":"); point(out, value.p_canvas);
    out.append(",\"relative\":"); point(out, value.relative);
    out.append(",\"q_padded\":"); point(out, value.q_padded);
    out.append(",\"q_original\":"); point(out, value.q_original);
    out.append(",\"padded_in_bounds\":"); out.boolean(value.padded_in_bounds);
    out.append(",\"original_in_bounds\":"); out.boolean(value.original_in_bounds);
    out.append(",\"compatible_pixel_ids\":"); ids(out, value.compatible_pixel_ids);
    out.append(",\"independent_witness\":");
    if (value.independent_witness) out.unsigned_value(*value.independent_witness);
    else out.append("null");
    out.append("}");
}
void edges(JsonRecord& out, const std::vector<n::Edge>& value) {
    array(out, value, [](JsonRecord& record, const n::Edge& edge) {
        record.append("["); record.unsigned_value(edge.first);
        record.append(","); record.unsigned_value(edge.second); record.append("]");
    });
}
void match_result(JsonRecord& out, const n::MatchResult& value) {
    out.append("{\"template_chain_id\":"); out.unsigned_value(value.template_chain_id);
    out.append(",\"numerator\":"); out.integer(value.numerator);
    out.append(",\"independent_numerator\":"); out.integer(value.independent_numerator);
    out.append(",\"total_weight\":"); out.integer(value.total_weight);
    out.append(",\"case\":");
    if (value.selected_case) {
        const auto& selected = *value.selected_case;
        out.append("{\"scene_chain_id\":"); out.unsigned_value(selected.scene_chain_id);
        out.append(",\"direction\":"); out.small_integer(selected.direction);
        out.append(",\"template_cut\":"); out.unsigned_value(selected.template_cut);
        out.append(",\"scene_cut\":"); out.unsigned_value(selected.scene_cut); out.append("}");
    } else out.append("null");
    out.append(",\"witness\":"); edges(out, value.witness); out.append("}");
}
void score(JsonRecord& out, const c::CandidateScore& value) {
    out.append("{\"denominator\":"); out.integer(value.denominator);
    out.append(",\"independent_numerator\":"); out.integer(value.independent_numerator);
    out.append(",\"ordered_numerator\":"); out.integer(value.ordered_numerator);
    out.append(",\"independent_accepted\":"); out.boolean(value.independent_accepted);
    out.append(",\"ordered_accepted\":"); out.boolean(value.ordered_accepted);
    out.append(",\"samples\":"); array(out, value.samples, support);
    out.append(",\"chains\":"); array(out, value.chains, match_result);
    out.append(",\"outside_padded_sample_ids\":"); ids(out, value.outside_padded_sample_ids);
    out.append(",\"outside_original_sample_ids\":"); ids(out, value.outside_original_sample_ids);
    out.append(",\"independent_witness\":"); edges(out, value.independent_witness);
    out.append(",\"cross_chain_reused_pixel_ids\":"); ids(out, value.cross_chain_reused_pixel_ids);
    out.append("}");
}
std::string response(Id request_id, const Evidence& value, std::size_t limit) {
    JsonRecord out(limit);
    out.append("{\"request_id\":"); out.unsigned_value(request_id);
    out.append(",\"scene\":"); scene(out, value.scene);
    out.append(",\"score\":"); score(out, value.score); out.append("}");
    return out.finish();
}

struct Output {
    std::uint64_t emitted = 0;
    std::size_t remaining() const { return static_cast<std::size_t>(max_output_bytes - emitted); }
    void write(const std::string& record) {
        if (record.size() > remaining()) throw ProtocolError("OUTPUT_LIMIT");
        // Charge the entire attempted write so a partial I/O failure cannot
        // reuse its byte allowance while attempting a subsequent error record.
        emitted += static_cast<std::uint64_t>(record.size());
        std::cout.write(record.data(), static_cast<std::streamsize>(record.size()));
        std::cout.flush();
        if (!std::cout) throw OutputIoError();
    }
    void error(Id request_id, const char* code) noexcept {
        try {
            JsonRecord out(remaining());
            out.append("{\"request_id\":"); out.unsigned_value(request_id);
            out.append(",\"error\":\""); out.append(code); out.append("\"}");
            write(out.finish());
        } catch (...) {
            std::cerr << "native candidate batch could not emit bounded error record\n";
        }
    }
};

}  // namespace

int main(int argc, char** argv) {
    if (argc != 2) {
        std::cerr << "usage: native_candidate_batch_v1 fixture_path\n";
        return 2;
    }
#ifdef _WIN32
    if (_setmode(_fileno(stdout), _O_BINARY) == -1) {
        std::cerr << "native candidate batch could not set binary stdout\n";
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
        if (static_cast<std::uint64_t>(initial_size) > max_file_bytes) throw ProtocolError("INPUT_LIMIT");
        input.seekg(0, std::ios::beg);
        if (!input) throw InputIoError();
        std::uint64_t consumed = 0, requests = 0;
        std::string line;
        line.reserve(4096);
        for (;;) {
            active_request_id = 0;
            if (!read_line(input, line, consumed)) break;
            if (requests == max_requests) throw ProtocolError("REQUEST_LIMIT");
            ++requests;
            const auto request = parse_request(line, active_request_id);
            const auto evidence = evaluate(request);
            output.write(response(request.request_id, evidence, output.remaining()));
        }
        return 0;
    } catch (const ProtocolError& error) {
        output.error(active_request_id, error.code); return 1;
    } catch (const InputIoError&) {
        output.error(active_request_id, "INPUT_IO"); return 2;
    } catch (const OutputIoError&) {
        output.error(active_request_id, "OUTPUT_IO"); return 2;
    } catch (const std::bad_alloc&) {
        output.error(active_request_id, "ALLOCATION_FAILURE"); return 2;
    } catch (const std::invalid_argument&) {
        output.error(active_request_id, "FACTORY_INVALID_EVIDENCE"); return 2;
    } catch (const std::overflow_error&) {
        output.error(active_request_id, "FACTORY_OVERFLOW"); return 2;
    } catch (const std::exception&) {
        output.error(active_request_id, "INTERNAL_ERROR"); return 2;
    } catch (...) {
        output.error(active_request_id, "INTERNAL_ERROR"); return 2;
    }
}
