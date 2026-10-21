#include "line2Dup_local.hpp"

#include <cstring>
#include <iostream>
#include <random>
#include <stdexcept>
#include <vector>

namespace {
unsigned long long cases = 0;
void require(bool ok, const char* message) {
    if (!ok) throw std::runtime_error(message);
}
unsigned bits(float value) {
    unsigned result;
    std::memcpy(&result, &value, sizeof(result));
    return result;
}
// Independent scalar accumulation followed by the old float-per-pixel scan.
// The denominator includes features skipped at image borders.
void check(const std::vector<const unsigned char*>& streams, int stride, int total) {
    unsigned expected_raw = 0;
    float expected_score = 0;
    int expected_row = -1, expected_col = -1;
    for (int row = 0; row < 16; ++row) for (int col = 0; col < 16; ++col) {
        unsigned sum = 0;
        for (const auto* stream : streams) sum += stream[row * stride + col];
        const float score = (int(sum) * 100.f) / (4 * total);
        if (score > expected_score) {
            expected_raw = sum; expected_score = score;
            expected_row = row; expected_col = col;
        }
    }
    const auto actual = line2Dup::detail::localMaximum16x16(
        streams.data(), streams.size(), stride, total);
    require(actual.raw == expected_raw, "raw sum overflow, widening or skipped-feature mismatch");
    require(bits(actual.score) == bits(expected_score), "float normalization changed");
    require(actual.row == expected_row && actual.col == expected_col,
            "first row-major winner or all-zero indices changed");
    ++cases;
}
}

int main() {
    try {
        // Every output cell must be able to win, including the final load,
        // upper byte/word lanes and the last row; expected answers are literal.
        unsigned char isolated[16 * 16] = {};
        const unsigned char* one[] = {isolated};
        for (int cell = 0; cell < 256; ++cell) {
            isolated[cell] = 4;
            const auto found = line2Dup::detail::localMaximum16x16(one, 1, 16, 1);
            require(found.raw == 4 && bits(found.score) == bits(100.f) &&
                    found.row == cell / 16 && found.col == cell % 16, "a patch cell cannot win");
            isolated[cell] = 0;
            ++cases;
        }
        std::mt19937 rng(0x2210e);
        for (int total : {1, 2, 46, 63, 64, 65, 111, 236, 8191}) {
            for (int stride : {16, 17, 31, 96}) {
                // Offset by one byte and end exactly at the final readable column.
                // Padding differs from all legal response values to expose bad strides.
                const size_t length = 15 * stride + 16;
                std::vector<std::vector<unsigned char>> storage(total,
                    std::vector<unsigned char>(length + 1, 197));
                std::vector<const unsigned char*> streams;
                for (auto& buffer : storage) streams.push_back(buffer.data() + 1);
                auto fill = [&](unsigned value) {
                    for (auto& buffer : storage) for (int row = 0; row < 16; ++row)
                        for (int col = 0; col < 16; ++col) buffer[1 + row * stride + col] = value;
                };
                fill(0); check(streams, stride, total);
                fill(4); check(streams, stride, total); // Maximum sum: 252 / 256 / 32764.
                fill(0);
                for (auto& buffer : storage) {
                    buffer[1 + 15 * stride + 15] = 4;
                    buffer[1 + stride] = 4;
                    buffer[1 + 8] = 4; // (0,8) wins over (1,0).
                }
                check(streams, stride, total);
                auto tie = line2Dup::detail::localMaximum16x16(streams.data(), streams.size(), stride, total);
                require(tie.row == 0 && tie.col == 8, "column/row tie ordering changed");
                for (int repeat = 0; repeat < 3; ++repeat) {
                    for (auto& buffer : storage) for (int row = 0; row < 16; ++row)
                        for (int col = 0; col < 16; ++col) {
                            const unsigned values[] = {0, 3, 4};
                            buffer[1 + row * stride + col] = values[rng() % 3];
                        }
                    check(streams, stride, total);
                }
                // Simulate feature skipping, preserving total-feature denominator.
                streams.resize(total / 2); check(streams, stride, total);
                streams.clear(); check(streams, stride, total);
                const auto zero = line2Dup::detail::localMaximum16x16(nullptr, 0, stride, total);
                require(zero.raw == 0 && bits(zero.score) == bits(0.f) &&
                        zero.row == -1 && zero.col == -1, "zero-feature patch contract changed");
            }
        }
        std::cout << "PASS local accumulator: " << cases
                  << " scalar-oracle cases; byte/word extremes, ties, zero/skipped features and strides\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "FAIL local accumulator: " << error.what() << '\n'; return 1;
    }
}
