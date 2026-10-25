/* Authored launcher for acquired build tools through the JNI Invocation API.
 * No Java VM implementation or game runtime is included here. */
#define _GNU_SOURCE
#include <dlfcn.h>
#include <jni.h>
#include <malloc.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static char *logical_jvm;
// The acquired Android JDK derives its data home from dladdr(libjvm). Android
// installs native libraries in a flat directory. Give this one pathname lookup
// the logical JDK layout; the actual ELF and executable mappings stay read-only.
int dladdr(const void *address, Dl_info *info) {
    int (*platform_dladdr)(const void *, Dl_info *) = dlsym(RTLD_NEXT, "dladdr");
    int result = platform_dladdr(address, info);
    if (result && logical_jvm && info->dli_fname) {
        const char *name = strrchr(info->dli_fname, '/');
        name = name ? name + 1 : info->dli_fname;
        if (!strcmp(name, "libjvm.so"))
            info->dli_fname = logical_jvm;
    }
    return result;
}
int main(int argc, char **argv) {
    // exec starts a fresh allocator, so the parent app's manifest setting does
    // not cover this child. The acquired JDK requires untagged native pointers.
    int (*configure_heap)(int, int) = dlsym(RTLD_DEFAULT, "mallopt");
    if (!configure_heap || !configure_heap(M_BIONIC_SET_HEAP_TAGGING_LEVEL, M_HEAP_TAGGING_LEVEL_NONE)) {
        fprintf(stderr, "JDK child requires Android's API 31 allocator compatibility\n");
        return 2;
    }
    const char *library_path = getenv("ROR2LAB_BUILD_JVM"), *home_path = getenv("ROR2LAB_BUILD_JAVA_HOME");
    if (!library_path || !home_path) {
        fprintf(stderr, "Explicit JVM library and Java home required\n");
        return 2;
    }
    const char *name = strrchr(argv[0], '/');
    name = name ? name + 1 : argv[0];
    char *home = 0, *classpath = 0;
    asprintf(&home, "-Djava.home=%s", home_path);
    JavaVMOption options[argc + 8];
    int n = 0, index = 1, mode = 1;
    if (setenv("JAVA_HOME", home_path, 1) || asprintf(&logical_jvm, "%s/lib/server/libjvm.so", home_path) < 0)
        return 2;
    options[n++] = (JavaVMOption){home, 0};
    options[n++] = (JavaVMOption){"-Xmx512m", 0};
    options[n++] = (JavaVMOption){"-XX:ActiveProcessorCount=2", 0};
    const char *target = 0, *cp = "";
    if (strstr(name, "javac"))
        target = "com.sun.tools.javac.Main";
    else if (strstr(name, "keytool"))
        target = "sun.security.tools.keytool.Main";
    else {
        while (index < argc) {
            if (!strcmp(argv[index], "-cp") || !strcmp(argv[index], "-classpath")) {
                if (++index == argc)
                    return 2;
                cp = argv[index++];
            } else if (!strncmp(argv[index], "-X", 2) || !strncmp(argv[index], "-D", 2)) {
                options[n++] = (JavaVMOption){argv[index++], 0};
            } else
                break;
        }
        if (index == argc)
            return 2;
        if (!strcmp(argv[index], "-jar")) {
            if (++index == argc)
                return 2;
            mode = 2;
            cp = argv[index];
        }
        target = argv[index++];
    }
    asprintf(&classpath, "-Djava.class.path=%s", cp);
    options[n++] = (JavaVMOption){classpath, 0};
    void *library = dlopen(library_path, RTLD_NOW | RTLD_GLOBAL);
    if (!library) {
        fprintf(stderr, "%s\n", dlerror());
        return 3;
    }
    jint (*create)(JavaVM **, void **, void *) = dlsym(library, "JNI_CreateJavaVM");
    if (!create)
        return 3;
    JavaVMInitArgs config = {JNI_VERSION_1_8, n, options, JNI_FALSE};
    JavaVM *vm;
    JNIEnv *env;
    jint result = create(&vm, (void **)&env, &config);
    if (result != JNI_OK) {
        fprintf(stderr, "JVM creation failed: %d\n", result);
        return 3;
    }
    jclass helper = (*env)->FindClass(env, "sun/launcher/LauncherHelper");
    if (!helper)
        goto failed;
    jmethodID load =
        (*env)->GetStaticMethodID(env, helper, "checkAndLoadMain", "(ZILjava/lang/String;)Ljava/lang/Class;");
    if (!load)
        goto failed;
    jstring requested = (*env)->NewStringUTF(env, target);
    if (!requested)
        goto failed;
    jclass klass = (jclass)(*env)->CallStaticObjectMethod(env, helper, load, JNI_TRUE, mode, requested);
    if (!klass || (*env)->ExceptionCheck(env))
        goto failed;
    jclass string = (*env)->FindClass(env, "java/lang/String");
    if (!string)
        goto failed;
    jmethodID method = (*env)->GetStaticMethodID(env, klass, "main", "([Ljava/lang/String;)V");
    if (!method)
        goto failed;
    jobjectArray args = (*env)->NewObjectArray(env, argc - index, string, 0);
    if (!args)
        goto failed;
    for (int i = index; i < argc; i++) {
        jstring value = (*env)->NewStringUTF(env, argv[i]);
        if (!value)
            goto failed;
        (*env)->SetObjectArrayElement(env, args, i - index, value);
        (*env)->DeleteLocalRef(env, value);
        if ((*env)->ExceptionCheck(env))
            goto failed;
    }
    (*env)->CallStaticVoidMethod(env, klass, method, args);
    if ((*env)->ExceptionCheck(env))
        goto failed;
    (*vm)->DestroyJavaVM(vm);
    free(home);
    free(classpath);
    free(logical_jvm);
    return 0;
failed:
    if ((*env)->ExceptionCheck(env)) {
        (*env)->ExceptionDescribe(env);
        (*env)->ExceptionClear(env);
    }
    (*vm)->DestroyJavaVM(vm);
    free(home);
    free(classpath);
    free(logical_jvm);
    return 1;
}
