#define _GNU_SOURCE
#include <dlfcn.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

/* Public CPython 3.14 opaque initialization ABI; no interpreter implementation.
 */
typedef void PyInitConfig;
typedef PyInitConfig *(*create_fn)(void);
typedef void (*free_fn)(PyInitConfig *);
typedef int (*setint_fn)(PyInitConfig *, const char *, int64_t);
typedef int (*setstr_fn)(PyInitConfig *, const char *, const char *);
typedef int (*setlist_fn)(PyInitConfig *, const char *, size_t, char *const *);
typedef int (*initialize_fn)(PyInitConfig *);
typedef int (*error_fn)(PyInitConfig *, const char **);
typedef int (*run_fn)(void);

int main(int argc, char **argv) {
  if (argc < 4)
    return 64;
  char self[4096], standard[4096], dynamic[4096];
  ssize_t n = readlink("/proc/self/exe", self, sizeof(self) - 1);
  if (n <= 0 || n >= (ssize_t)sizeof(self) - 1)
    return 65;
  self[n] = 0;
  if (snprintf(standard, sizeof(standard), "%s/lib/python3.14", argv[2]) >=
          (int)sizeof(standard) ||
      snprintf(dynamic, sizeof(dynamic), "%s/lib/python3.14/lib-dynload",
               argv[2]) >= (int)sizeof(dynamic))
    return 65;
  void *library = dlopen(argv[1], RTLD_NOW | RTLD_GLOBAL);
  if (!library) {
    fprintf(stderr, "PYTHON_DLOPEN=%s\n", dlerror());
    return 66;
  }
  create_fn create = (create_fn)dlsym(library, "PyInitConfig_Create");
  free_fn release = (free_fn)dlsym(library, "PyInitConfig_Free");
  setint_fn setint = (setint_fn)dlsym(library, "PyInitConfig_SetInt");
  setstr_fn setstr = (setstr_fn)dlsym(library, "PyInitConfig_SetStr");
  setlist_fn setlist = (setlist_fn)dlsym(library, "PyInitConfig_SetStrList");
  initialize_fn initialize =
      (initialize_fn)dlsym(library, "Py_InitializeFromInitConfig");
  error_fn error = (error_fn)dlsym(library, "PyInitConfig_GetError");
  run_fn run = (run_fn)dlsym(library, "Py_RunMain");
  if (!create || !release || !setint || !setstr || !setlist || !initialize ||
      !error || !run)
    return 67;
  PyInitConfig *config = create();
  if (!config)
    return 68;
  const char *options[] = {"isolated",
                           "use_environment",
                           "site_import",
                           "write_bytecode",
                           "parse_argv",
                           "safe_path",
                           "module_search_paths_set",
                           "buffered_stdio"};
  int64_t values[] = {1, 0, 0, 0, 0, 1, 1, 0};
  for (size_t i = 0; i < sizeof(values) / sizeof(values[0]); i++)
    if (setint(config, options[i], values[i]) < 0)
      goto failure;
  char *paths[] = {standard, dynamic};
  if (setstr(config, "program_name", self) < 0 ||
      setstr(config, "home", argv[2]) < 0 ||
      setstr(config, "run_filename", argv[3]) < 0 ||
      setlist(config, "module_search_paths", 2, paths) < 0 ||
      setlist(config, "argv", (size_t)(argc - 3), argv + 3) < 0 ||
      initialize(config) < 0)
    goto failure;
  release(config);
  fprintf(stderr, "PYTHON_HOST_UID=%d PID=%d\n", getuid(), getpid());
  FILE *context = fopen("/proc/self/attr/current", "r");
  char context_line[1024];
  if (!context || !fgets(context_line, sizeof(context_line), context)) return 71;
  fprintf(stderr, "PYTHON_HOST_CONTEXT=%s\n", context_line); fclose(context);
  int result = run();
  fprintf(stderr, "PYTHON_HOST_EXIT=%d\n", result);
  FILE *maps = fopen("/proc/self/maps", "r");
  if (!maps)
    return 70;
  char line[8192];
  fputs("PYTHON_MAPS_BEGIN\n", stderr);
  while (fgets(line, sizeof(line), maps))
    fputs(line, stderr);
  fputs("PYTHON_MAPS_END\n", stderr);
  fclose(maps);
  return result;
failure: {
  const char *message = NULL;
  error(config, &message);
  fprintf(stderr, "PYTHON_INIT_ERROR=%s\n", message ? message : "unknown");
  release(config);
  return 69;
}
}
