// Authored bounded adapter to unchanged, separately supplied public ETCPACK.
#include <cstdio>
#include <cstdlib>
#include <cstring>

extern bool readCompressParams();
extern void setupAlphaTable();
extern void compressBlockAlphaFast(unsigned char *, int, int, int, int, unsigned char *);
extern void compressBlockETC2FastPerceptual(unsigned char *, unsigned char *, int, int, int, int,
                                            unsigned int &, unsigned int &);
extern double compressBlockDiffFlipFast(unsigned char *, unsigned char *, int, int, int, int,
                                        unsigned int &, unsigned int &);
extern void compressBlockDiffFlipFastPerceptual(unsigned char *, unsigned char *, int, int, int,
                                                int, unsigned int &, unsigned int &);

static void words(unsigned char *out, unsigned int first, unsigned int second) {
    for (int i = 0; i < 4; i++) {
        out[i] = (first >> (24 - i * 8)) & 255;
        out[i + 4] = (second >> (24 - i * 8)) & 255;
    }
}

int main(int argc, char **argv) {
    if (argc != 4)
        return 64;
    bool alpha = !std::strcmp(argv[3], "alpha8"), normal = !std::strcmp(argv[3], "normal");
    if (!alpha && !normal && std::strcmp(argv[3], "rgb"))
        return 65;
    char *end;
    long width = std::strtol(argv[1], &end, 10);
    if (*end || width < 4 || width > 8192 || width % 4)
        return 65;
    long height = std::strtol(argv[2], &end, 10);
    if (*end || height < 4 || height > 8192 || height % 4 ||
        width * height * (alpha ? 1 : 3) > 64 * 1024 * 1024)
        return 65;
    size_t pixels = (size_t)width * height, input_size = pixels * (alpha ? 1 : 3);
    size_t output_size = alpha ? pixels : pixels / 2;
    auto *input = static_cast<unsigned char *>(std::malloc(input_size));
    auto *output = static_cast<unsigned char *>(std::malloc(output_size));
    auto *decoded = static_cast<unsigned char *>(std::calloc(alpha ? 48 : input_size, 1));
    if (!input || !output || !decoded)
        return 66;
    if (std::fread(input, 1, input_size, stdin) != input_size || std::fgetc(stdin) != EOF)
        return 67;
    readCompressParams();
    unsigned char black[48] = {0}, colour[8];
    unsigned int first, second;
    if (alpha) {
        setupAlphaTable();
        // The source Alpha8 exporter has zero RGB plus its original A.
        compressBlockETC2FastPerceptual(black, decoded, 4, 4, 0, 0, first, second);
        words(colour, first, second);
    }
    auto *block = output;
    for (int y = 0; y < height; y += 4) {
        for (int x = 0; x < width; x += 4) {
            if (alpha) {
                compressBlockAlphaFast(input, x, y, width, height, block);
                std::memcpy(block + 8, colour, 8);
                block += 16;
            } else {
                if (normal)
                    compressBlockDiffFlipFast(input, decoded, width, height, x, y, first, second);
                else
                    compressBlockDiffFlipFastPerceptual(input, decoded, width, height, x, y, first,
                                                        second);
                words(block, first, second);
                block += 8;
            }
        }
    }
    if (std::fwrite(output, 1, output_size, stdout) != output_size || std::fflush(stdout))
        return 68;
    std::free(input);
    std::free(output);
    std::free(decoded);
    return 0;
}
