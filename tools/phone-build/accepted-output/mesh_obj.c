/* Authored bounded adapter for separately acquired public MikkTSpace/BSD sources. */
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "mikktspace.h"

void p1_qsort(void *, size_t, size_t, int (*)(const void *, const void *));
typedef struct { float *vertices, *output; uint32_t *indices, count; } Input;
static int faces(const SMikkTSpaceContext *c) { return ((Input *)c->m_pUserData)->count / 3; }
static int corners(const SMikkTSpaceContext *c, int face) { (void)c; (void)face; return 3; }
static void attribute(const SMikkTSpaceContext *c, float *out, int face, int corner, int offset, int size) {
    Input *in = c->m_pUserData;
    memcpy(out, in->vertices + in->indices[face * 3 + corner] * 12 + offset, size * sizeof(float));
}
static void position(const SMikkTSpaceContext *c, float *out, int f, int v) { attribute(c, out, f, v, 0, 3); }
static void normal(const SMikkTSpaceContext *c, float *out, int f, int v) { attribute(c, out, f, v, 3, 3); }
static void uv(const SMikkTSpaceContext *c, float *out, int f, int v) { attribute(c, out, f, v, 10, 2); }
static void tangent(const SMikkTSpaceContext *c, const float *value, float sign, int f, int v) {
    float *out = ((Input *)c->m_pUserData)->output + (f * 3 + v) * 4;
    memcpy(out, value, 3 * sizeof(float)); out[3] = sign;
}
/* Preserve the SDK's Boolean area comparator, including its ordering behavior. */
static int area_less(const void *a, const void *b) { return *(const float *)a < *(const float *)b; }
static int read_all(void *p, size_t size, size_t count) { return fread(p, size, count, stdin) == count; }
int main(int argc, char **argv) {
    uint32_t vertices, count, endian = 1;
    if (argc != 2 || sizeof(float) != 4 || *(unsigned char *)&endian != 1) return 2;
    if (strcmp(argv[1], "area-order") == 0) {
        if (!read_all(&count, 4, 1) || count == 0 || count > 2000000) return 3;
        float *values = malloc((size_t)count * 4);
        if (!values) return 4;
        if (!read_all(values, 4, count) || getchar() != EOF) { free(values); return 3; }
        for (uint32_t i = 0; i < count; i++) if (!isfinite(values[i]) || values[i] < 0) { free(values); return 3; }
        p1_qsort(values, count, 4, area_less);
        int result = fwrite(values, 4, count, stdout) == count ? 0 : 5;
        free(values); return result;
    }
    if (strcmp(argv[1], "tangents") != 0 || !read_all(&vertices, 4, 1) || !read_all(&count, 4, 1)
        || vertices == 0 || vertices > 65535 || count == 0 || count > 2000000 || count % 3) return 3;
    Input in = {0}; in.count = count;
    in.vertices = malloc((size_t)vertices * 48); in.indices = malloc((size_t)count * 4); in.output = malloc((size_t)count * 16);
    int result = 4;
    if (!in.vertices || !in.indices || !in.output) goto done;
    result = 3;
    if (!read_all(in.vertices, 48, vertices) || !read_all(in.indices, 4, count) || getchar() != EOF) goto done;
    for (uint32_t i = 0; i < vertices * 12; i++) if (!isfinite(in.vertices[i])) goto done;
    for (uint32_t i = 0; i < count; i++) if (in.indices[i] >= vertices) goto done;
    SMikkTSpaceInterface api = {faces, corners, position, normal, uv, tangent, NULL};
    SMikkTSpaceContext context = {&api, &in};
    if (!genTangSpaceDefault(&context)) { result = 6; goto done; }
    result = fwrite(in.output, 16, count, stdout) == count ? 0 : 5;
done:
    free(in.vertices); free(in.indices); free(in.output); return result;
}
