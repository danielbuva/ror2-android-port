/* Authored bounded pipe adapter; the separately attributed decoder is unchanged. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <math.h>
#define BCDEC_IMPLEMENTATION
#include "third_party/bcdec/bcdec.h"

/* Linear bytes reduce before normalization; sRGB normalizes RGBA on import. */
static int mips(int width, int height, int gamma, int hdr) {
    size_t bytes = (size_t)width * height * 4;
    unsigned char *pixels = malloc(bytes);
    float *values = malloc(bytes * sizeof(float));
    if (!pixels || !values) return 66;
    if (fread(pixels, 1, bytes, stdin) != bytes || fgetc(stdin) != EOF) return 67;
    for (size_t i = 0; i < bytes; i++) {
        float v = pixels[i];
        if (hdr) {
            v /= 255.f;
            if (i % 4 != 3) {
                v = v < .04045f ? v / 12.92f : powf((v + .055f) / 1.055f, 2.4f);
                v = (float)(_Float16)v;
            }
        } else if (gamma) {
            v *= 1.f / 255.f;
            if (i % 4 != 3)
                v = v <= .04045f ? v / 12.92f : powf((v + .055f) / 1.055f, 2.4f);
        }
        values[i] = v;
    }
    for (int level = 0;; level++) {
        size_t count = (size_t)width * height * 4;
        if (level || hdr) for (size_t i = 0; i < count; i++) {
            float v = values[i];
            if (gamma && i % 4 != 3)
                v = v <= .0031308f ? v * 12.92f : 1.055f * powf(v, .4166667f) - .055f;
            float scale = hdr && i % 4 != 3 ? 127.5f : 255.f;
            pixels[i] = (unsigned char)fminf(255.f, fmaxf(0.f, floorf(v * scale + .5f)));
        }
        if (fwrite(pixels, 1, count, stdout) != count) return 68;
        if (width == 1 && height == 1) break;
        int nw = width > 1 ? width / 2 : 1, nh = height > 1 ? height / 2 : 1;
        for (int y = 0; y < nh; y++) for (int x = 0; x < nw; x++) for (int c = 0; c < 4; c++) {
            int x0 = x * 2, x1 = x0 + 1 < width ? x0 + 1 : x0;
            int y0 = y * 2, y1 = y0 + 1 < height ? y0 + 1 : y0;
            float a = values[(y0 * width + x0) * 4 + c], b = values[(y0 * width + x1) * 4 + c];
            float d = values[(y1 * width + x0) * 4 + c], e = values[(y1 * width + x1) * 4 + c];
            float v = ((a + b) + d + e) * .25f;
            if (level == 0 && !gamma && !hdr) v *= 1.f / 255.f;
            values[(y * nw + x) * 4 + c] = v;
        }
        width = nw; height = nh;
    }
    free(values); free(pixels);
    return fflush(stdout) ? 68 : 0;
}

/* BC4/5's pinned byte-channel decoder uses a one-unit interpolation bias. */
static void bc45_channel(const unsigned char *block, unsigned char *rgba, int channel) {
    unsigned a = block[0], b = block[1], denominator = a > b ? 7 : 5;
    unsigned char palette[8] = {a, b, 0, 0, 0, 0, 0, 255};
    for (unsigned i = 1; i < denominator; i++)
        palette[i + 1] = ((denominator - i) * a + i * b + 1) / denominator;
    uint64_t selectors = 0;
    for (int i = 0; i < 6; i++) selectors |= (uint64_t)block[i + 2] << (i * 8);
    for (int i = 0; i < 16; i++) rgba[i * 4 + channel] = palette[(selectors >> (i * 3)) & 7];
}

static int distance(uint32_t seed, int x, int y, int width) {
    return abs((int)(seed % width) - x) + abs((int)(seed / width) - y);
}

static int dilate(int width, int height) {
    size_t count = (size_t)width * height, bytes = count * 4;
    unsigned char *pixels = malloc(bytes);
    uint32_t *current = malloc(count * sizeof(uint32_t));
    uint32_t *next = malloc(count * sizeof(uint32_t));
    if (!pixels || !current || !next)
        return 66;
    if (fread(pixels, 1, bytes, stdin) != bytes || fgetc(stdin) != EOF)
        return 67;
    for (size_t i = 0; i < count; i++)
        current[i] = pixels[i * 4 + 3] ? (uint32_t)i : UINT32_MAX;
    for (int jump = 16; jump; jump /= 2) {
        for (int y = 0; y < height; y++) {
            for (int x = 0; x < width; x++) {
                int i = y * width + x;
                uint32_t seed = current[i];
                if (!pixels[i * 4 + 3]) {
                    int best = seed == UINT32_MAX ? (int)count + width + height : distance(seed, x, y, width);
                    int neighbors[4] = {
                        x >= jump ? i - jump : -1,
                        x + jump < width ? i + jump : -1,
                        y >= jump ? i - jump * width : -1,
                        y + jump < height ? i + jump * width : -1,
                    };
                    for (int n = 0; n < 4; n++) {
                        if (neighbors[n] < 0 || current[neighbors[n]] == UINT32_MAX)
                            continue;
                        uint32_t candidate = current[neighbors[n]];
                        int d = distance(candidate, x, y, width);
                        if (d < best) {
                            seed = candidate;
                            best = d;
                        }
                    }
                }
                next[i] = seed;
            }
        }
        uint32_t *swap = current;
        current = next;
        next = swap;
    }
    for (size_t i = 0; i < count; i++)
        if (!pixels[i * 4 + 3] && current[i] != UINT32_MAX)
            memcpy(pixels + i * 4, pixels + current[i] * 4, 3);
    free(current);
    free(next);
    int result = fwrite(pixels, 1, bytes, stdout) == bytes && !fflush(stdout) ? 0 : 68;
    free(pixels);
    return result;
}

/* Same byte expansion and integer interpolation as the qualified Python decoder. */
static void bc3(const unsigned char *block, unsigned char *rgba) {
    unsigned char palette[4][3], alpha[8];
    for (int endpoint = 0; endpoint < 2; endpoint++) {
        unsigned value = block[8 + endpoint * 2] | (unsigned)block[9 + endpoint * 2] << 8;
        unsigned r = value >> 11, g = (value >> 5) & 63, b = value & 31;
        palette[endpoint][0] = (r << 3) | (r >> 2);
        palette[endpoint][1] = (g << 2) | (g >> 4);
        palette[endpoint][2] = (b << 3) | (b >> 2);
    }
    for (int c = 0; c < 3; c++) {
        palette[2][c] = (2 * palette[0][c] + palette[1][c]) / 3;
        palette[3][c] = (palette[0][c] + 2 * palette[1][c]) / 3;
    }
    alpha[0] = block[0]; alpha[1] = block[1];
    if (alpha[0] > alpha[1]) {
        for (int i = 1; i < 7; i++) alpha[i + 1] = ((7 - i) * alpha[0] + i * alpha[1]) / 7;
    } else {
        for (int i = 1; i < 5; i++) alpha[i + 1] = ((5 - i) * alpha[0] + i * alpha[1]) / 5;
        alpha[6] = 0; alpha[7] = 255;
    }
    uint32_t colours = 0;
    uint64_t alphas = 0;
    for (int i = 0; i < 4; i++) colours |= (uint32_t)block[12 + i] << (8 * i);
    for (int i = 0; i < 6; i++) alphas |= (uint64_t)block[2 + i] << (8 * i);
    for (int i = 0; i < 16; i++) {
        memcpy(rgba + i * 4, palette[(colours >> (2 * i)) & 3], 3);
        rgba[i * 4 + 3] = alpha[(alphas >> (3 * i)) & 7];
    }
}

static void bc1(const unsigned char *block, unsigned char *rgba) {
    unsigned first = block[0] | (unsigned)block[1] << 8;
    unsigned second = block[2] | (unsigned)block[3] << 8;
    unsigned char palette[4][4];
    for (int i = 0; i < 2; i++) {
        unsigned value = i ? second : first;
        unsigned r = value >> 11, g = (value >> 5) & 63, b = value & 31;
        palette[i][0] = (r << 3) | (r >> 2);
        palette[i][1] = (g << 2) | (g >> 4);
        palette[i][2] = (b << 3) | (b >> 2);
        palette[i][3] = 255;
    }
    for (int c = 0; c < 3; c++) {
        palette[2][c] = first > second ? (2 * palette[0][c] + palette[1][c]) / 3 : (palette[0][c] + palette[1][c]) / 2;
        palette[3][c] = first > second ? (palette[0][c] + 2 * palette[1][c]) / 3 : 0;
    }
    palette[2][3] = 255; palette[3][3] = first > second ? 255 : 0;
    uint32_t selectors = 0;
    for (int i = 0; i < 4; i++) selectors |= (uint32_t)block[i + 4] << (i * 8);
    for (int i = 0; i < 16; i++) memcpy(rgba + i * 4, palette[(selectors >> (i * 2)) & 3], 4);
}

int main(int argc, char **argv) {
    if (argc != 3 && argc != 4)
        return 64;
    char *end;
    long width = strtol(argv[1], &end, 10);
    if (*end || width < 1 || width > 8192)
        return 65;
    long height = strtol(argv[2], &end, 10);
    if (*end || height < 1 || height > 8192 || width * height * 4 > 64 * 1024 * 1024)
        return 65;
    int is_bc3 = argc == 4 && !strcmp(argv[3], "bc3");
    int is_bc1 = argc == 4 && !strcmp(argv[3], "bc1");
    int is_bc4 = argc == 4 && !strcmp(argv[3], "bc4");
    int is_bc5 = argc == 4 && !strcmp(argv[3], "bc5");
    int is_bc6 = argc == 4 && !strcmp(argv[3], "bc6");
    if (argc == 4 && !is_bc1 && !is_bc3 && !is_bc4 && !is_bc5 && !is_bc6) {
        if (!strcmp(argv[3], "dilate")) return dilate((int)width, (int)height);
        if (!strcmp(argv[3], "mips-linear")) return mips((int)width, (int)height, 0, 0);
        if (!strcmp(argv[3], "mips-srgb")) return mips((int)width, (int)height, 1, 0);
        if (!strcmp(argv[3], "hdr-mips-linear")) return mips((int)width, (int)height, 0, 1);
        if (!strcmp(argv[3], "hdr-mips-srgb")) return mips((int)width, (int)height, 1, 1);
        return 65;
    }
    unsigned char *rows = malloc(width * 16);
    if (!rows)
        return 66;
    for (int by = 0; by < height; by += 4) {
        for (int bx = 0; bx < width; bx += 4) {
            _Alignas(uint64_t) unsigned char block[16];
            unsigned char decoded[64];
            size_t block_bytes = is_bc1 || is_bc4 ? 8 : 16;
            if (fread(block, 1, block_bytes, stdin) != block_bytes)
                return 67;
            if (is_bc4 || is_bc5) {
                memset(decoded, 0, sizeof(decoded));
                for (int i = 0; i < 16; i++) decoded[i * 4 + 3] = 255;
                bc45_channel(block, decoded, 0);
                if (is_bc5) bc45_channel(block + 8, decoded, 1);
            } else if (is_bc6) {
                float values[16 * 3];
                bcdec_bc6h_float(block, values, 12, 0);
                for (int i = 0; i < 16; i++) {
                    for (int c = 0; c < 3; c++)
                        decoded[i * 4 + c] = (unsigned char)fminf(255.f, fmaxf(0.f, values[i * 3 + c] * 255.f));
                    decoded[i * 4 + 3] = 255;
                }
            } else if (is_bc1) bc1(block, decoded);
            else if (is_bc3) bc3(block, decoded);
            else bcdec_bc7(block, decoded, 16);
            int columns = width - bx < 4 ? width - bx : 4;
            for (int y = 0; y < 4 && by + y < height; y++)
                memcpy(rows + (y * width + bx) * 4, decoded + y * 16, columns * 4);
        }
        int count = height - by < 4 ? height - by : 4;
        if (fwrite(rows, 1, width * count * 4, stdout) != (size_t)width * count * 4)
            return 68;
    }
    if (fgetc(stdin) != EOF)
        return 67;
    free(rows);
    return fflush(stdout) ? 68 : 0;
}
