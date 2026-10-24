/* Authored bounded pipe adapter; the separately attributed decoder is unchanged. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#define BCDEC_IMPLEMENTATION
#include "third_party/bcdec/bcdec.h"

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
    if (argc == 4 && !is_bc3)
        return strcmp(argv[3], "dilate") ? 65 : dilate((int)width, (int)height);
    unsigned char *rows = malloc(width * 16);
    if (!rows)
        return 66;
    for (int by = 0; by < height; by += 4) {
        for (int bx = 0; bx < width; bx += 4) {
            _Alignas(uint64_t) unsigned char block[16];
            unsigned char decoded[64];
            if (fread(block, 1, 16, stdin) != 16)
                return 67;
            if (is_bc3) bc3(block, decoded);
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
