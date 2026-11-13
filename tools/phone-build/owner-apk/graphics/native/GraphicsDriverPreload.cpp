// Isolated qualification observer. Retains Unity's resolver; opens no driver.
#include "IUnityInterface.h"
#include "IUnityGraphics.h"
#include "IUnityGraphicsVulkan.h"
#include <atomic>
#include <cstdint>

namespace {
enum Status : uint32_t {
    Loaded = 1, VulkanInterface = 2, Registered = 4, Callback = 8,
    Initialized = 16, CallbackBeforeInitialize = 32, OriginalResolver = 64,
    InvalidOrder = 128, Unloaded = 256
};
std::atomic<uint32_t> status(0);
IUnityGraphics* graphics = nullptr;

void UNITY_INTERFACE_API OnGraphicsEvent(UnityGfxDeviceEventType event)
{
    if (event != kUnityGfxDeviceEventInitialize) return;
    const uint32_t before = status.fetch_or(Initialized);
    if (!(before & Callback) || (before & (Initialized | Unloaded)))
        status.fetch_or(InvalidOrder);
}

PFN_vkGetInstanceProcAddr UNITY_INTERFACE_API ObserveResolver(
    PFN_vkGetInstanceProcAddr original, void*)
{
    const uint32_t before = status.fetch_or(Callback);
    if (before & (Callback | Initialized | Unloaded)) status.fetch_or(InvalidOrder);
    else status.fetch_or(CallbackBeforeInitialize);
    if (original) status.fetch_or(OriginalResolver);
    else status.fetch_or(InvalidOrder);
    return original;
}
}

extern "C" void UNITY_INTERFACE_EXPORT UNITY_INTERFACE_API UnityPluginLoad(IUnityInterfaces* interfaces)
{
    if (status.fetch_or(Loaded) != 0) {
        status.fetch_or(InvalidOrder);
        return;
    }
    if (!interfaces) return;
    graphics = interfaces->Get<IUnityGraphics>();
    if (graphics) graphics->RegisterDeviceEventCallback(OnGraphicsEvent);
    IUnityGraphicsVulkan* vulkan = interfaces->Get<IUnityGraphicsVulkan>();
    if (!vulkan) return;
    status.fetch_or(VulkanInterface);
    if (vulkan->InterceptInitialization(ObserveResolver, nullptr)) status.fetch_or(Registered);
}

extern "C" void UNITY_INTERFACE_EXPORT UNITY_INTERFACE_API UnityPluginUnload()
{
    status.fetch_or(Unloaded);
    if (graphics) graphics->UnregisterDeviceEventCallback(OnGraphicsEvent);
    graphics = nullptr;
}

extern "C" uint32_t UNITY_INTERFACE_EXPORT UNITY_INTERFACE_API GraphicsDriverPreloadStatus()
{
    return status.load();
}
