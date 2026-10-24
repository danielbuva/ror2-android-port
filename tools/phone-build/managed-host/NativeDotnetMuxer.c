#define _GNU_SOURCE
#include <dlfcn.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

/* Public hostfxr v8.0.32 ABI; actual enumeration and framework-dependent apps.
 */
typedef void *handle_t;
struct parameters {
  size_t size;
  const char *host_path;
  const char *dotnet_root;
};
struct framework_info {
  size_t size;
  const char *name;
  const char *version;
  const char *path;
};
struct environment_info {
  size_t size;
  const char *hostfxr_version;
  const char *hostfxr_commit;
  size_t sdk_count;
  const void *sdks;
  size_t framework_count;
  const struct framework_info *frameworks;
};
typedef int32_t (*initialize_fn)(int, const char **, const struct parameters *,
                                 handle_t *);
typedef int32_t (*run_fn)(handle_t);
typedef int32_t (*close_fn)(handle_t);
typedef void (*info_callback)(const struct environment_info *, void *);
typedef int32_t (*environment_fn)(const char *, void *, info_callback, void *);
static void enumerate(const struct environment_info *info, void *context) {
  int *called = context;
  if (!info || info->size < sizeof(*info) || info->framework_count > 32)
    return;
  for (size_t i = 0; i < info->framework_count; i++) {
    const struct framework_info *f = &info->frameworks[i];
    if (f->size < sizeof(*f) || !f->name || !f->version || !f->path)
      return;
    printf("%s %s [%s]\n", f->name, f->version, f->path);
  }
  *called = 1;
}
int main(int argc, char **argv) {
  const char *root = getenv("ROR2LAB_BUILD_DOTNET_ROOT"),
             *fxr = getenv("ROR2LAB_BUILD_HOSTFXR");
  if (!root || !fxr || argc < 2)
    return 64;
  char self[4096];
  ssize_t n = readlink("/proc/self/exe", self, sizeof(self) - 1);
  if (n <= 0 || n >= (ssize_t)sizeof(self) - 1)
    return 65;
  self[n] = 0;
  void *library = dlopen(fxr, RTLD_NOW | RTLD_LOCAL);
  if (!library) {
    fprintf(stderr, "DOTNET_DLOPEN=%s\n", dlerror());
    return 66;
  }
  int result;
  if (argc == 2 && !strcmp(argv[1], "--list-runtimes")) {
    environment_fn get =
        (environment_fn)dlsym(library, "hostfxr_get_dotnet_environment_info");
    if (!get)
      return 67;
    int called = 0;
    result = get(root, NULL, enumerate, &called);
    if (!called && result == 0)
      result = 68;
  } else {
    /* Preserve exec: hostfxr recognizes --runtimeconfig only in exec mode. */
    int offset = 1;
    if (argc <= offset || (argc == 2 && !strcmp(argv[1], "exec")))
      return 64;
    initialize_fn initialize = (initialize_fn)dlsym(
        library, "hostfxr_initialize_for_dotnet_command_line");
    run_fn run = (run_fn)dlsym(library, "hostfxr_run_app");
    close_fn close = (close_fn)dlsym(library, "hostfxr_close");
    if (!initialize || !run || !close)
      return 67;
    struct parameters p = {sizeof(p), self, root};
    handle_t handle = NULL;
    result =
        initialize(argc - offset, (const char **)(argv + offset), &p, &handle);
    if (result < 0 || !handle) {
      fprintf(stderr, "DOTNET_INITIALIZE=%d\n", result);
      return 69;
    }
    result = run(handle);
    close(handle);
  }
  fprintf(stderr, "DOTNET_HOST_UID=%d EXIT=%d PID=%d\n", getuid(), result, getpid());
  FILE *context = fopen("/proc/self/attr/current", "r");
  char context_line[1024];
  if (!context || !fgets(context_line, sizeof(context_line), context)) return 71;
  fprintf(stderr, "DOTNET_HOST_CONTEXT=%s\n", context_line); fclose(context);
  FILE *maps = fopen("/proc/self/maps", "r");
  if (!maps)
    return 70;
  char line[8192];
  fputs("DOTNET_MAPS_BEGIN\n", stderr);
  while (fgets(line, sizeof(line), maps))
    fputs(line, stderr);
  fputs("DOTNET_MAPS_END\n", stderr);
  fclose(maps);
  return result;
}
