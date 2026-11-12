// Authored compile-only fixture. No plugin is loaded or device API called.
#include "IUnityInterface.h"
#include "IUnityGraphics.h"
#include "IUnityGraphicsVulkan.h"
#include <type_traits>

static PFN_vkGetInstanceProcAddr UNITY_INTERFACE_API DriverResolver(
    PFN_vkGetInstanceProcAddr systemResolver, void*)
{
    return systemResolver;
}

static_assert(std::is_same<UnityVulkanInitCallback, decltype(&DriverResolver)>::value,
    "Unity Vulkan initialization callback ABI differs");
static_assert(std::is_same<decltype(((IUnityGraphicsVulkan*)nullptr)->InterceptInitialization(
    &DriverResolver, nullptr)), bool>::value, "Unity Vulkan intercept result differs");

extern "C" void UNITY_INTERFACE_EXPORT UNITY_INTERFACE_API UnityPluginLoad(IUnityInterfaces* interfaces)
{
    IUnityGraphicsVulkan* vulkan = interfaces->Get<IUnityGraphicsVulkan>();
    if (vulkan) vulkan->InterceptInitialization(&DriverResolver, nullptr);
}
