/* Authored source-RGB JPEG roundtrip. IJG/stb notices accompany the built tool. */
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <setjmp.h>
#include <jpeglib.h>
#define STBI_WRITE_NO_STDIO
#define STB_IMAGE_WRITE_IMPLEMENTATION
#include "stb_image_write.h"

#define LIMIT (64u * 1024u * 1024u)
struct encoded { unsigned char *data; size_t size, capacity; int failed; };
struct errors { struct jpeg_error_mgr manager; jmp_buf jump; };

static void append(void *context, void *data, int bytes) {
    struct encoded *out = context;
    if (out->failed) return;
    if (bytes < 0 || (size_t)bytes > LIMIT - out->size) { out->failed = 1; return; }
    size_t needed = out->size + (size_t)bytes;
    if (needed > out->capacity) {
        size_t capacity = out->capacity ? out->capacity : 4096;
        while (capacity < needed) capacity *= 2;
        unsigned char *grown = realloc(out->data, capacity);
        if (!grown) { out->failed = 1; return; }
        out->data = grown; out->capacity = capacity;
    }
    memcpy(out->data + out->size, data, (size_t)bytes);
    out->size = needed;
}

static void decode_error(j_common_ptr info) {
    struct errors *error = (struct errors *)info->err;
    longjmp(error->jump, 1);
}

static int dimension(const char *text) {
    char *end;
    long value = strtol(text, &end, 10);
    return *text && !*end && value > 0 && value <= 8192 ? (int)value : 0;
}

int main(int argc, char **argv) {
    if (argc != 3) { fputs("usage: texture-jpeg WIDTH HEIGHT < RGB > RGB\n", stderr); return 2; }
    int width = dimension(argv[1]), height = dimension(argv[2]);
    if (!width || !height || (size_t)width * height * 3 > LIMIT) return 2;
    size_t stride = (size_t)width * 3, bytes = stride * height;
    unsigned char *source = malloc(bytes), *top_down = malloc(bytes);
    if (!source || !top_down) return 3;
    if (fread(source, 1, bytes, stdin) != bytes || fgetc(stdin) != EOF) return 4;
    for (int y = 0; y < height; ++y) memcpy(top_down + y * stride, source + (height - y - 1) * stride, stride);
    struct encoded encoded = {0};
    int written = stbi_write_jpg_to_func(append, &encoded, width, height, 3, top_down, 90);
    free(top_down); free(source);
    if (!written || encoded.failed) { free(encoded.data); return 5; }

    struct jpeg_decompress_struct info;
    struct errors error;
    info.err = jpeg_std_error(&error.manager);
    error.manager.error_exit = decode_error;
    if (setjmp(error.jump)) { jpeg_destroy_decompress(&info); free(encoded.data); return 6; }
    jpeg_create_decompress(&info);
    jpeg_mem_src(&info, encoded.data, encoded.size);
    if (jpeg_read_header(&info, TRUE) != JPEG_HEADER_OK) return 6;
    info.out_color_space = JCS_RGB;
    info.dct_method = JDCT_IFAST;
    info.do_fancy_upsampling = FALSE;
    if (!jpeg_start_decompress(&info) || info.output_width != (unsigned)width || info.output_height != (unsigned)height || info.output_components != 3) return 6;
    unsigned char *decoded = malloc(bytes);
    if (!decoded) return 3;
    while (info.output_scanline < info.output_height) {
        unsigned char *row = decoded + info.output_scanline * stride;
        if (jpeg_read_scanlines(&info, &row, 1) != 1) return 6;
    }
    if (!jpeg_finish_decompress(&info)) return 6;
    jpeg_destroy_decompress(&info); free(encoded.data);
    for (int y = height - 1; y >= 0; --y) {
        if (fwrite(decoded + y * stride, 1, stride, stdout) != stride) return 7;
    }
    free(decoded);
    return fflush(stdout) == 0 ? 0 : 7;
}
