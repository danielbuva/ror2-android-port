// Authored bounded adapter to unchanged, separately supplied public ETCPACK.
#include <cstdio>
#include <cstdlib>
#include <cstring>

extern bool readCompressParams();
extern void setupAlphaTable();
extern void compressBlockAlphaFast(unsigned char *, int, int, int, int, unsigned char *);
extern void compressBlockETC2FastPerceptual(unsigned char *, unsigned char *, int, int, int, int,
                                            unsigned int &, unsigned int &);

int main(int argc, char **argv) {
    if (argc != 3)
        return 64;
    char *end;
    long width = std::strtol(argv[1], &end, 10);
    if (*end || width < 4 || width > 8192 || width % 4)
        return 65;
    long height = std::strtol(argv[2], &end, 10);
    if (*end || height < 4 || height > 8192 || height % 4 || width * height > 64 * 1024 * 1024)
        return 65;
    size_t size = (size_t)width * height;
    auto *input = static_cast<unsigned char *>(std::malloc(size));
    auto *output = static_cast<unsigned char *>(std::malloc(size));
    if (!input || !output)
        return 66;
    if (std::fread(input, 1, size, stdin) != size || std::fgetc(stdin) != EOF)
        return 67;
    readCompressParams();
    setupAlphaTable();
    // The pinned source exporter maps Alpha8 to zero RGB plus its original A.
    // RGB dilation preserves zero RGB. Generate the generic black colour block.
    unsigned char black[48] = {0}, decoded[48] = {0}, colour[8];
    unsigned int first, second;
    compressBlockETC2FastPerceptual(black, decoded, 4, 4, 0, 0, first, second);
    for (int i = 0; i < 4; i++) {
        colour[i] = (first >> (24 - i * 8)) & 255;
        colour[i + 4] = (second >> (24 - i * 8)) & 255;
    }
    auto *block = output;
    for (int y = 0; y < height; y += 4) {
        for (int x = 0; x < width; x += 4) {
            compressBlockAlphaFast(input, x, y, width, height, block);
            std::memcpy(block + 8, colour, 8);
            block += 16;
        }
    }
    if (std::fwrite(output, 1, size, stdout) != size || std::fflush(stdout))
        return 68;
    std::free(input);
    std::free(output);
    return 0;
}
