#define _GNU_SOURCE
#include <dlfcn.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>

/* Authored ABI declarations checked against dotnet/runtime v8.0.32 hostfxr.h. */
typedef void *host_handle;
struct initialize_parameters { size_t size; const char *host_path; const char *dotnet_root; };
typedef int32_t (*initialize_fn)(int, const char **, const struct initialize_parameters *, host_handle *);
typedef int32_t (*run_fn)(host_handle);
typedef int32_t (*close_fn)(host_handle);

int main(int argc, char **argv) {
    if (argc < 4) { fputs("usage: host HOSTFXR DOTNET_ROOT APP [ARG...]\n", stderr); return 64; }
    char self[4096];
    ssize_t n = readlink("/proc/self/exe", self, sizeof(self)-1);
    if (n <= 0 || n >= (ssize_t)sizeof(self)-1) return 65;
    self[n] = 0;
    printf("HOST_PID=%d HOST_UID=%d\n", getpid(), getuid()); fflush(stdout);
    FILE *context = fopen("/proc/self/attr/current", "r");
    char context_line[1024];
    if (!context || !fgets(context_line, sizeof(context_line), context)) return 70;
    printf("HOST_CONTEXT=%s\n", context_line); fclose(context); fflush(stdout);
    void *library = dlopen(argv[1], RTLD_NOW | RTLD_LOCAL);
    if (!library) { fprintf(stderr, "dlopen hostfxr: %s\n", dlerror()); return 66; }
    initialize_fn initialize = (initialize_fn)dlsym(library, "hostfxr_initialize_for_dotnet_command_line");
    run_fn run = (run_fn)dlsym(library, "hostfxr_run_app");
    close_fn close_host = (close_fn)dlsym(library, "hostfxr_close");
    if (!initialize || !run || !close_host) { fputs("hostfxr ABI unavailable\n", stderr); return 67; }
    struct initialize_parameters parameters = {sizeof(parameters), self, argv[2]};
    host_handle handle = NULL;
    int32_t result = initialize(argc-3, (const char **)(argv+3), &parameters, &handle);
    printf("HOST_INITIALIZE=%d\n", result); fflush(stdout);
    if (result < 0 || !handle) return 68;
    result = run(handle);
    printf("HOST_RUN=%d\n", result);
    close_host(handle);
    FILE *maps = fopen("/proc/self/maps", "r");
    if (!maps) return 69;
    char line[8192];
    puts("HOST_MAPS_BEGIN");
    while (fgets(line, sizeof(line), maps)) fputs(line, stdout);
    puts("HOST_MAPS_END"); fclose(maps);
    return result;
}
