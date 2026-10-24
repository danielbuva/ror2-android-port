/* Authored GNU host-tool adapters for the explicit Android QEMU runner.
 * No SDK patch or global binfmt handler. Not linked into the game player.
 */
#define _GNU_SOURCE
#include <stddef.h>
#include <stdint.h>
extern void *dlsym(void *, const char *);
extern int *__errno_location(void);
static void *(*next_mmap)(void *, size_t, int, int, int, long);
static uintptr_t next_hint = 0x10000000;
__attribute__((constructor)) static void setup_mappings(void) { next_mmap = dlsym((void *)-1, "mmap"); }
void *mmap(void *address, size_t length, int prot, int flags, int fd, long offset) {
    if (!next_mmap)
        next_mmap = dlsym((void *)-1, "mmap");
    if ((flags & 0x40) && !(flags & (0x10 | 0x100000))) {
        size_t span = (length + 65535) & ~(size_t)65535;
        for (;;) {
            uintptr_t hint = __atomic_fetch_add(&next_hint, span, __ATOMIC_RELAXED);
            if (hint + length > 0x80000000 || hint + length < hint) {
                *__errno_location() = 12;
                return (void *)-1;
            }
            void *result = next_mmap((void *)hint, length, prot, (flags & ~0x40) | 0x100000, fd, offset);
            if (result != (void *)-1)
                return result;
            if (*__errno_location() != 17)
                return result;
        }
    }
    return next_mmap(address, length, prot, flags, fd, offset);
}
void *mmap64(void *address, size_t length, int prot, int flags, int fd, long offset) {
    return mmap(address, length, prot, flags, fd, offset);
}

extern char *getenv(const char *);
extern void *malloc(size_t);
extern size_t strlen(const char *);
extern void *memcpy(void *, const void *, size_t);
extern int open(const char *, int, ...);
extern long read(int, void *, size_t);
extern int close(int);
extern char **environ;
static int (*next_execve)(const char *, char *const[], char *const[]);
static int (*next_execvp)(const char *, char *const[]);
static int (*next_spawn)(int *, const char *, const void *, const void *, char *const[], char *const[]);
static int (*next_spawnp)(int *, const char *, const void *, const void *, char *const[], char *const[]);
static char *runner, *loader, *native_libraries;
static int starts(const char *s, const char *prefix) {
    while (*prefix)
        if (*s++ != *prefix++)
            return 0;
    return 1;
}
__attribute__((constructor)) static void setup_children(void) {
    next_execve = dlsym((void *)-1, "execve");
    next_execvp = dlsym((void *)-1, "execvp");
    next_spawn = dlsym((void *)-1, "posix_spawn");
    next_spawnp = dlsym((void *)-1, "posix_spawnp");
    runner = getenv("ROR2_GNU_RUNNER");
    loader = getenv("ROR2_GNU_LOADER_ROOT");
    char *libs = getenv("ROR2_GNU_NATIVE_LIBRARY_PATH");
    if (libs) {
        native_libraries = malloc(strlen(libs) + 17);
        memcpy(native_libraries, "LD_LIBRARY_PATH=", 16);
        memcpy(native_libraries + 16, libs, strlen(libs) + 1);
    }
}
static size_t count(char *const values[]) {
    size_t n = 0;
    while (values[n])
        n++;
    return n;
}
static int prepare(const char *path, char *const argv[], char *const envp[], char **args, char **env) {
    unsigned char h[20];
    int fd = open(path, 0);
    long n = fd < 0 ? -1 : read(fd, h, 20);
    if (fd >= 0)
        close(fd);
    if (n != 20 || h[0] != 127 || h[1] != 'E' || h[2] != 'L' || h[3] != 'F' || h[4] != 2 || h[5] != 1 || h[19] != 0)
        return 0;
    if (h[18] == 183) {
        size_t j = 0;
        for (size_t k = 0; envp[k]; k++)
            if (!starts(envp[k], "LD_LIBRARY_PATH=") && !starts(envp[k], "LD_PRELOAD="))
                env[j++] = envp[k];
        if (native_libraries)
            env[j++] = native_libraries;
        env[j] = 0;
        return 2;
    }
    if (h[18] != 62)
        return 0;
    if (!runner || !loader || !native_libraries)
        return -1;
    size_t i = 0, j = 0;
    args[i++] = runner;
    args[i++] = "-L";
    args[i++] = loader;
    args[i++] = "-0";
    args[i++] = argv[0];
    for (size_t k = 0; envp[k]; k++) {
        if (starts(envp[k], "LD_LIBRARY_PATH=") || starts(envp[k], "LD_PRELOAD=")) {
            args[i++] = "-E";
            args[i++] = envp[k];
        } else
            env[j++] = envp[k];
    }
    env[j++] = native_libraries;
    env[j] = 0;
    args[i++] = (char *)path;
    for (size_t k = 1; argv[k]; k++)
        args[i++] = argv[k];
    args[i] = 0;
    return 1;
}
int execve(const char *path, char *const argv[], char *const envp[]) {
    char *args[count(argv) + 16], *env[count(envp) + 2];
    int route = prepare(path, argv, envp, args, env);
    if (route < 0) {
        *__errno_location() = 8;
        return -1;
    }
    return route == 1 ? next_execve(runner, args, env) : next_execve(path, argv, route == 2 ? env : envp);
}
int execv(const char *path, char *const argv[]) { return execve(path, argv, environ); }
int execvp(const char *path, char *const argv[]) {
    for (const char *p = path; *p; p++)
        if (*p == '/')
            return execve(path, argv, environ);
    return next_execvp(path, argv);
}
int posix_spawn(int *pid, const char *path, const void *actions, const void *attrs, char *const argv[],
                char *const envp[]) {
    char *args[count(argv) + 16], *env[count(envp) + 2];
    int route = prepare(path, argv, envp, args, env);
    if (route < 0)
        return 8;
    return route == 1 ? next_spawn(pid, runner, actions, attrs, args, env)
                      : next_spawn(pid, path, actions, attrs, argv, route == 2 ? env : envp);
}
int posix_spawnp(int *pid, const char *path, const void *actions, const void *attrs, char *const argv[],
                 char *const envp[]) {
    char *args[count(argv) + 16], *env[count(envp) + 2];
    int route = prepare(path, argv, envp, args, env);
    if (route < 0)
        return 8;
    return route == 1 ? next_spawn(pid, runner, actions, attrs, args, env)
                      : next_spawnp(pid, path, actions, attrs, argv, route == 2 ? env : envp);
}

extern int waitpid(int, int *, int);
int system(const char *command) {
    if (!command)
        return 1;
    char *args[] = {"sh", "-c", (char *)command, 0};
    char *env[count(environ) + 2];
    size_t n = 0;
    for (size_t i = 0; environ[i]; i++)
        if (!starts(environ[i], "LD_LIBRARY_PATH=") && !starts(environ[i], "LD_PRELOAD="))
            env[n++] = environ[i];
    if (native_libraries)
        env[n++] = native_libraries;
    env[n] = 0;
    int pid, status, err = next_spawn(&pid, "/system/bin/sh", 0, 0, args, env);
    if (err) {
        *__errno_location() = err;
        return -1;
    }
    while (waitpid(pid, &status, 0) < 0) {
        if (*__errno_location() != 4)
            return -1;
    }
    return status;
}
