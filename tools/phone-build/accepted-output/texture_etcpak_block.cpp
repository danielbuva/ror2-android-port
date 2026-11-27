#include <cstddef>
#include <cstdint>
#include <cstring>

#include "ProcessRGB.hpp"

// The comparison reads one 4x4 BGRA block at a time. Copy to aligned words
// for the public etcpak API and return the little-endian ETC block bytes.
extern "C" void encode_block(const unsigned char* bgra, unsigned char* output, int alpha) {
    uint32_t source[16];
    uint64_t encoded[2] = {};
    std::memcpy(source, bgra, sizeof source);
    if (alpha) {
        CompressEtc2Rgba(source, encoded, 1, 4, false);
    } else {
        CompressEtc1Rgb(source, encoded, 1, 4);
    }
    std::memcpy(output, encoded, alpha ? sizeof encoded : sizeof encoded[0]);
}
