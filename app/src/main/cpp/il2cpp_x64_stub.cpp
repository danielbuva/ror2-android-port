#include <android/log.h>

#if !defined(__x86_64__)
#error "libil2cpp target must be x86_64!"
#endif

extern "C" int ror2_il2cpp_x64_entry(void) {
    __android_log_print(ANDROID_LOG_INFO, "RoR2_IL2CPP_x64", "libil2cpp.so (x86_64) initialized");
    return 0;
}
