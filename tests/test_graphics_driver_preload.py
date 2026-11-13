"""Execute the authored ordering observer, not Unity/Vulkan or a custom driver."""

from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "tools/phone-build/owner-apk/graphics/native/GraphicsDriverPreload.cpp"


class GraphicsDriverPreloadTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("c++"), "C++ compiler absent")
    def test_ordering_and_original_resolver_contract(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "IUnityInterface.h").write_text(
                "#pragma once\n#define UNITY_INTERFACE_API\n#define UNITY_INTERFACE_EXPORT\nstruct IUnityInterfaces {template<class T> T* Get();};\n"
            )
            (root / "IUnityGraphics.h").write_text(
                "#pragma once\nenum UnityGfxDeviceEventType {kUnityGfxDeviceEventInitialize,kUnityGfxDeviceEventShutdown};\n"
                "using EventCallback=void(*)(UnityGfxDeviceEventType);\n"
                "struct IUnityGraphics {void(*RegisterDeviceEventCallback)(EventCallback);void(*UnregisterDeviceEventCallback)(EventCallback);};\n"
            )
            (root / "IUnityGraphicsVulkan.h").write_text(
                "#pragma once\nusing PFN_vkGetInstanceProcAddr=void*(*)();\n"
                "using UnityVulkanInitCallback=PFN_vkGetInstanceProcAddr(*)(PFN_vkGetInstanceProcAddr,void*);\n"
                "struct IUnityGraphicsVulkan {bool(*InterceptInitialization)(UnityVulkanInitCallback,void*);};\n"
            )
            (root / "harness.cpp").write_text(
                r"""#include "IUnityInterface.h"
#include "IUnityGraphics.h"
#include "IUnityGraphicsVulkan.h"
#include <cassert>
#include <cstdint>
#include <string>
extern "C" void UnityPluginLoad(IUnityInterfaces*);
extern "C" void UnityPluginUnload();
extern "C" uint32_t GraphicsDriverPreloadStatus();
static EventCallback eventCallback = nullptr;
static UnityVulkanInitCallback resolverCallback = nullptr;
static bool hasGraphics = true, hasVulkan = true, accepts = true;
static int registrations = 0, removals = 0;
static void Register(EventCallback callback) { registrations++; eventCallback = callback; }
static void Unregister(EventCallback callback) { assert(callback == eventCallback); removals++; eventCallback = nullptr; }
static bool Intercept(UnityVulkanInitCallback callback, void*) { resolverCallback = callback; return accepts; }
static IUnityGraphics graphics = {Register, Unregister};
static IUnityGraphicsVulkan vulkan = {Intercept};
template<> IUnityGraphics* IUnityInterfaces::Get<IUnityGraphics>() {return hasGraphics ? &graphics : nullptr;}
template<> IUnityGraphicsVulkan* IUnityInterfaces::Get<IUnityGraphicsVulkan>() {return hasVulkan ? &vulkan : nullptr;}
static void* Original() {return nullptr;}
int main(int argc, char** argv) {
    assert(argc == 2);
    std::string mode(argv[1]);
    hasGraphics = mode != "no-graphics"; hasVulkan = mode != "no-vulkan"; accepts = mode != "rejected";
    IUnityInterfaces interfaces;
    UnityPluginLoad(&interfaces);
    assert(GraphicsDriverPreloadStatus() & 1);
    if (mode == "no-vulkan") {assert(GraphicsDriverPreloadStatus() == 1); return 0;}
    if (mode == "rejected") {assert(GraphicsDriverPreloadStatus() == 3); return 0;}
    if (mode == "late") eventCallback(kUnityGfxDeviceEventInitialize);
    if (mode == "null-resolver") {
        assert(resolverCallback(nullptr, nullptr) == nullptr);
        eventCallback(kUnityGfxDeviceEventInitialize);
        assert((GraphicsDriverPreloadStatus() & 128) && !(GraphicsDriverPreloadStatus() & 64)); return 0;
    }
    assert(resolverCallback(Original, nullptr) == Original);
    if (mode == "repeated") assert(resolverCallback(Original, nullptr) == Original);
    if (eventCallback) eventCallback(kUnityGfxDeviceEventInitialize);
    uint32_t flags = GraphicsDriverPreloadStatus();
    if (mode == "no-graphics") {assert(!(flags & 16) && flags != 127); return 0;}
    if (mode == "late" || mode == "repeated") {assert(flags & 128); return 0;}
    assert(flags == 127);
    UnityPluginUnload(); assert(GraphicsDriverPreloadStatus() == (127 | 256)); assert(removals == 1);
    if (mode == "reload") {UnityPluginLoad(&interfaces); assert(GraphicsDriverPreloadStatus() & 128); assert(registrations == 1);}
    return 0;
}
"""
            )
            compiled = subprocess.run(
                [shutil.which("c++"), "-std=c++11", "-I" + str(root), str(SOURCE), str(root / "harness.cpp"), "-o", str(root / "observer")],
                capture_output=True,
                text=True,
                timeout=30,
            )
            self.assertEqual(compiled.returncode, 0, compiled.stderr)
            for mode in ("normal", "late", "rejected", "no-vulkan", "no-graphics", "null-resolver", "repeated", "reload"):
                with self.subTest(mode=mode):
                    result = subprocess.run([str(root / "observer"), mode], capture_output=True, text=True, timeout=10)
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
