/* Authored bounded LZ4 block worker. The build retains the upstream license. */
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include "lz4.h"
#include "lz4hc.h"

#define LIMIT (64u * 1024u * 1024u)

static uint32_t little32(const unsigned char *bytes) {
    return (uint32_t)bytes[0] | (uint32_t)bytes[1] << 8 |
           (uint32_t)bytes[2] << 16 | (uint32_t)bytes[3] << 24;
}

static int fail(const char *message) {
    fprintf(stderr, "bundle-lz4: %s\n", message);
    return 1;
}

int main(int argc, char **argv) {
    (void)argv;
    if (argc != 1) return fail("no arguments expected");
    for (;;) {
        unsigned char header[8];
        size_t read = fread(header, 1, sizeof(header), stdin);
        if (read == 0 && feof(stdin) && !ferror(stdin)) return 0;
        if (read != sizeof(header)) return fail("incomplete request header");
        uint32_t size = little32(header), method = little32(header + 4);
        /* 2/3 retain UnityFS fast/HC12. 9 selects shader-segment default HC9;
           it is a worker request, not a UnityFS compression-format flag. */
        if (size > LIMIT || (method != 2 && method != 3 && method != 9))
            return fail("invalid size or method");
        int bound = LZ4_compressBound((int)size);
        if (bound <= 0) return fail("invalid compression bound");
        char *source = malloc(size ? (size_t)size : 1);
        char *output = malloc((size_t)bound);
        if (!source || !output) {
            free(source); free(output);
            return fail("allocation failed");
        }
        if (fread(source, 1, size, stdin) != size) {
            free(source); free(output);
            return fail("incomplete request payload");
        }
        int compressed = method == 2
            ? LZ4_compress_default(source, output, (int)size, bound)
            : LZ4_compress_HC(source, output, (int)size, bound,
                              method == 9 ? LZ4HC_CLEVEL_DEFAULT : 12);
        free(source);
        if (compressed <= 0 || compressed > bound) {
            free(output);
            return fail("compression failed");
        }
        uint32_t length = (uint32_t)compressed;
        unsigned char reply[4] = {
            (unsigned char)length, (unsigned char)(length >> 8),
            (unsigned char)(length >> 16), (unsigned char)(length >> 24)
        };
        int written = fwrite(reply, 1, sizeof(reply), stdout) == sizeof(reply) &&
                      fwrite(output, 1, (size_t)compressed, stdout) == (size_t)compressed;
        free(output);
        if (!written || fflush(stdout) != 0) return fail("reply write failed");
    }
}
