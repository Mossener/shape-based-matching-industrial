// Bounded validation adapter for supplied integer label grids only.
// No images, OpenCV, detector, benchmark, subprocess, or production work.
// See NATIVE_EDGE_BATCH_PROTOCOL_V1.json for exact framing and limits.
#include "native_edge_chains.hpp"

#include <fstream>
#include <iostream>
#include <limits>
#include <new>
#include <optional>
#include <string>
#include <string_view>

#ifdef _WIN32
#include <cstdio>
#include <fcntl.h>
#include <io.h>
#endif

namespace {

using namespace ordered_contour_native::edge;

constexpr std::uint64_t max_file_bytes = 64ULL * 1024 * 1024;
constexpr std::uint64_t max_output_bytes = 64ULL * 1024 * 1024;
constexpr std::uint64_t max_requests = 10000;
constexpr std::size_t max_line_bytes = 131072;  // Excludes LF; includes CR.
constexpr Id max_dimension = 160;
constexpr Id max_cells = 25600;
// Under the grid cap, LCM <=25600^16, denominator <=16*25600^16,
// and every chain arclength <=1414*25600. This is a loose safe cap.
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

// Each byte is checked against the file/line caps before string growth.
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

Id dimension(Tokens& tokens) {
    const Id value = unsigned_integer(tokens.take());
    if (value == 0) throw ProtocolError("DIMENSION_ZERO");
    if (value > max_dimension) throw ProtocolError("DIMENSION_LIMIT");
    return value;
}

struct Request {
    Id request_id = 0;
    LabelGrid labels;
};

Request parse_request(const std::string& line, Id& active_request_id) {
    Tokens tokens{line};
    if (tokens.empty()) throw ProtocolError("EMPTY_REQUEST");
    if (tokens.take() != "G1") throw ProtocolError("PROTOCOL_VERSION");
    Request request;
    request.request_id = unsigned_integer(tokens.take());
    active_request_id = request.request_id;
    const Id width = dimension(tokens);
    const Id height = dimension(tokens);
    // Validate before multiplication, vector allocation, or label loops.
    if (height > max_cells / width) throw ProtocolError("CELL_LIMIT");
    const Id cells = width * height;
    if (cells > max_cells) throw ProtocolError("CELL_LIMIT");
    request.labels.resize(static_cast<std::size_t>(height));
    for (auto& row : request.labels) {
        row.resize(static_cast<std::size_t>(width));
        for (int& label : row) {
            const Id value = unsigned_integer(tokens.take());
            if (!((value <= 7) || value == 255)) throw ProtocolError("LABEL_VALUE");
            label = static_cast<int>(value);
        }
    }
    if (!tokens.empty()) throw ProtocolError("EXTRA_TOKEN");
    return request;
}

struct Evidence {
    ThinningResult thinning;
    std::vector<Chain> raw_chains;
    std::vector<ChainSampling> raw_samplings;
    std::optional<TemplateEvidence> prepared;
};

Evidence evaluate(const LabelGrid& labels) {
    Evidence result;
    result.thinning = thin_labels(labels);
    result.raw_chains = extract_chains(labels);
    result.raw_samplings.reserve(result.raw_chains.size());
    for (const auto& chain : result.raw_chains) {
        result.raw_samplings.push_back(sample_chain(chain, result.thinning.width));
    }
    bool empty_thinned = true;
    for (const auto& row : result.thinning.labels) {
        for (int label : row) {
            if (label != 255) empty_thinned = false;
        }
    }
    try {
        result.prepared.emplace(prepare_template(labels));
    } catch (const std::invalid_argument&) {
        // The already validated grid has exactly one legal factory rejection:
        // no sample can survive an empty thinned graph. Other rejections fail.
        if (!empty_thinned) throw;
    }
    if (empty_thinned && result.prepared) {
        throw std::logic_error("empty graph unexpectedly produced template evidence");
    }
    return result;
}

// All string fragments are fixed ASCII keys/punctuation or checked integers.
// No JSON library, user string escaping, floating-point conversion, or partial
// normal record writes are involved. Every append reserves room for final LF.
struct JsonRecord {
    std::string bytes;
    std::size_t limit;

    explicit JsonRecord(std::size_t maximum) : limit(maximum) {
        bytes.reserve(std::min<std::size_t>(4096, maximum));
    }

    void append(std::string_view value) {
        if (limit == 0 || bytes.size() >= limit ||
            value.size() > limit - 1 - bytes.size()) {
            throw ProtocolError("OUTPUT_LIMIT");
        }
        bytes.append(value.data(), value.size());
    }

    void unsigned_value(Id value) { append(std::to_string(value)); }
    void small_integer(int value) { append(std::to_string(value)); }
    void boolean(bool value) { append(value ? "true" : "false"); }

    void integer(const Integer& value) {
        if (mpz_sgn(value.get_mpz_t()) < 0 ||
            mpz_sizeinbase(value.get_mpz_t(), 10) > max_integer_decimal_digits) {
            throw std::overflow_error("native edge integer exceeds bounded serialization domain");
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

void grid(JsonRecord& out, const LabelGrid& labels) {
    array(out, labels, [](JsonRecord& record, const std::vector<int>& row) {
        array(record, row, [](JsonRecord& cell_record, int label) {
            cell_record.small_integer(label);
        });
    });
}

void thinning(JsonRecord& out, const ThinningResult& value) {
    out.append("{\"width\":");
    out.unsigned_value(value.width);
    out.append(",\"height\":");
    out.unsigned_value(value.height);
    out.append(",\"eligible_labels\":");
    grid(out, value.eligible_labels);
    out.append(",\"labels\":");
    grid(out, value.labels);
    out.append(",\"round_deletions\":");
    array(out, value.round_deletions, [](JsonRecord& record, const DeletionRound& counts) {
        record.append("[");
        record.unsigned_value(counts.first);
        record.append(",");
        record.unsigned_value(counts.second);
        record.append("]");
    });
    out.append("}");
}

void chain(JsonRecord& out, const Chain& value) {
    out.append("{\"chain_id\":");
    out.unsigned_value(value.chain_id);
    out.append(",\"pixel_ids\":");
    ids(out, value.pixel_ids);
    out.append(",\"closed\":");
    out.boolean(value.closed);
    out.append(",\"returning\":");
    out.boolean(value.returning);
    out.append("}");
}

void sampling(JsonRecord& out, const ChainSampling& value) {
    out.append("{\"chain_id\":");
    out.unsigned_value(value.chain_id);
    out.append(",\"pixel_ids\":");
    ids(out, value.pixel_ids);
    out.append(",\"arclength\":");
    out.integer(value.arclength);
    out.append("}");
}

void ownership(JsonRecord& out, const SampleOwnership& value) {
    out.append("{\"pixel_id\":");
    out.unsigned_value(value.pixel_id);
    out.append(",\"owner_chain_id\":");
    out.unsigned_value(value.owner_chain_id);
    out.append(",\"member_chain_ids\":");
    ids(out, value.member_chain_ids);
    out.append("}");
}

void sample(JsonRecord& out, const WeightedSample& value) {
    out.append("{\"pixel_id\":");
    out.unsigned_value(value.pixel_id);
    out.append(",\"owner_chain_id\":");
    out.unsigned_value(value.owner_chain_id);
    out.append(",\"chain_index\":");
    out.unsigned_value(value.chain_index);
    out.append(",\"x\":");
    out.unsigned_value(value.x);
    out.append(",\"y\":");
    out.unsigned_value(value.y);
    out.append(",\"label\":");
    out.small_integer(value.label);
    out.append(",\"cell\":");
    out.small_integer(value.cell);
    out.append(",\"weight\":");
    out.integer(value.weight);
    out.append("}");
}

void prepared_template(JsonRecord& out, const TemplateEvidence& value) {
    out.append("{\"thinning\":");
    thinning(out, value.thinning);
    out.append(",\"chains\":");
    array(out, value.chains, chain);
    out.append(",\"samplings\":");
    array(out, value.samplings, sampling);
    out.append(",\"ownership\":");
    array(out, value.ownership, ownership);
    out.append(",\"samples\":");
    array(out, value.samples, sample);
    out.append(",\"cell_counts\":");
    array(out, value.cell_counts, [](JsonRecord& record, Id count) {
        record.unsigned_value(count);
    });
    out.append(",\"occupied_cells\":");
    out.unsigned_value(value.occupied_cells);
    out.append(",\"lcm\":");
    out.integer(value.lcm);
    out.append(",\"denominator\":");
    out.integer(value.denominator);
    out.append("}");
}

std::string response(Id request_id, const Evidence& value, std::size_t limit) {
    JsonRecord out(limit);
    out.append("{\"request_id\":");
    out.unsigned_value(request_id);
    out.append(",\"thinning\":");
    thinning(out, value.thinning);
    out.append(",\"raw_chains\":");
    array(out, value.raw_chains, chain);
    out.append(",\"raw_samplings\":");
    array(out, value.raw_samplings, sampling);
    out.append(",\"template\":");
    if (value.prepared) prepared_template(out, *value.prepared);
    else out.append("null");
    out.append("}");
    return out.finish();
}

struct Output {
    std::uint64_t emitted = 0;

    std::size_t remaining() const {
        return static_cast<std::size_t>(max_output_bytes - emitted);
    }

    void write(const std::string& record) {
        if (record.size() > remaining()) throw ProtocolError("OUTPUT_LIMIT");
        // Reserve the whole attempted write even if the OS later writes only
        // part of it; error handling must never reuse that stdout allowance.
        emitted += static_cast<std::uint64_t>(record.size());
        std::cout.write(record.data(), static_cast<std::streamsize>(record.size()));
        std::cout.flush();
        if (!std::cout) throw OutputIoError();
    }

    void error(Id request_id, const char* code) noexcept {
        try {
            JsonRecord record(remaining());
            record.append("{\"request_id\":");
            record.unsigned_value(request_id);
            record.append(",\"error\":\"");
            record.append(code);  // Only fixed internal ASCII error codes.
            record.append("\"}");
            write(record.finish());
        } catch (...) {
            // An exhausted budget never permits a partial normal response.
            std::cerr << "native edge batch could not emit bounded error record\n";
        }
    }
};

}  // namespace

int main(int argc, char** argv) {
    if (argc != 2) {
        std::cerr << "usage: native_edge_batch_v1 fixture_path\n";
        return 2;
    }
#ifdef _WIN32
    if (_setmode(_fileno(stdout), _O_BINARY) == -1) {
        std::cerr << "native edge batch could not set binary stdout\n";
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
            const auto evidence = evaluate(request.labels);
            output.write(response(request.request_id, evidence, output.remaining()));
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
        output.error(active_request_id, "FACTORY_INVALID_GRID");
        return 2;
    } catch (const std::overflow_error&) {
        output.error(active_request_id, "FACTORY_OVERFLOW");
        return 2;
    } catch (const std::exception&) {
        output.error(active_request_id, "INTERNAL_ERROR");
        return 2;
    } catch (...) {
        output.error(active_request_id, "INTERNAL_ERROR");
        return 2;
    }
}
