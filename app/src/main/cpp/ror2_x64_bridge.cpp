#include <jni.h>
#include <android/log.h>
#include <sys/utsname.h>
#include <string>

#define LOG_TAG "RoR2_x64_Bridge"

#if !defined(__x86_64__)
#error "Target architecture must be x86_64!"
#endif

extern "C" JNIEXPORT jstring JNICALL
Java_dev_ror2owner_bootstrap_PayloadBootstrapActivity_getNativeArchInfo(JNIEnv* env, jclass) {
    struct utsname buffer{};
    uname(&buffer);
    std::string info = std::string("ABI=x86_64; machine=") + buffer.machine + "; release=" + buffer.release;
    __android_log_print(ANDROID_LOG_INFO, LOG_TAG, "Native x64 bridge active: %s", info.c_str());
    return env->NewStringUTF(info.c_str());
}
