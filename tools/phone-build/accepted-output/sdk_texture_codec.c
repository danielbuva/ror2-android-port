#include <dlfcn.h>
#include <errno.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#ifdef __ANDROID__
/* C-locale GNU ABI entry points absent from Bionic. Errors still abort. */
__attribute__((visibility("default"))) int *__errno_location(void) { return &errno; }
__attribute__((visibility("default"))) char *gettext(const char *message) {
    return (char *)message;
}
__attribute__((visibility("default"), noreturn)) void
__assert_fail(const char *expression, const char *file, unsigned line, const char *function) {
    fprintf(stderr, "%s:%u: %s: Assertion '%s' failed.\n", file, line, function, expression);
    abort();
}
#endif
struct Image {
    void *pixels;
    int type, width, height, stride;
};
int main(int argc, char **argv) {
    if (argc != 6 && argc != 7)
        return 64;
    char *end;
    long w = strtol(argv[2], &end, 10);
    if (*end || w < 1 || w > 8192)
        return 65;
    long h = strtol(argv[3], &end, 10);
    if (*end || h < 1 || h > 8192)
        return 65;
    long fmt = strtol(argv[4], &end, 10);
    if (*end || (fmt != 0 && fmt != 1 && fmt != 2))
        return 65;
    long space = strtol(argv[5], &end, 10);
    if (*end || space < 0 || space > 2)
        return 65;
    long band = h;
    if (argc == 7) {
        band = strtol(argv[6], &end, 10);
        if (*end || band < 4 || band > h || band % 4 || w % 4 || h % 4)
            return 65;
    }
    size_t stride = (size_t)w * 4;
    size_t block_row = ((w + 3) / 4) * (fmt == 2 ? 16 : 8);
    unsigned char *input = malloc(stride * band), *output = malloc(block_row * ((band + 3) / 4));
    if (!input || !output)
        return 66;
    void *lib = dlopen(argv[1], RTLD_NOW | RTLD_LOCAL);
    if (!lib) {
        fprintf(stderr, "dlopen: %s\n", dlerror());
        return 68;
    }
    void (*init)(void) = dlsym(lib, "libetc_init");
    int (*compress)(struct Image, int, int, int, int, void *, size_t *) =
        dlsym(lib, "libetc_compress");
    if (!init || !compress)
        return 69;
    init();
    for (long row = 0; row < h; row += band) {
        long rows = h - row < band ? h - row : band;
        size_t in_size = stride * rows;
        if (fread(input, 1, in_size, stdin) != in_size ||
            (row + rows == h && (fgetc(stdin) != EOF || ferror(stdin))))
            return 67;
        struct Image image = {input, 0, w, rows, stride};
        size_t out_size = block_row * ((rows + 3) / 4);
        size_t actual = out_size;
        int ok = compress(image, 1, fmt, 1, space, output, &actual);
        if (!ok || actual != out_size) {
            fprintf(stderr, "compress: %d %zu/%zu\n", ok, actual, out_size);
            return 70;
        }
        if (fwrite(output, 1, out_size, stdout) != out_size)
            return 71;
    }
    if (fflush(stdout))
        return 71;
    free(input);
    free(output);
    dlclose(lib);
    return 0;
}
