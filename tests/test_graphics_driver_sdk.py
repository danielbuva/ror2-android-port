"""Authored SDK layouts exercise bounded inspection and the actual C++ fixture."""

import importlib.util
import json
from pathlib import Path
import plistlib
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("graphics_driver_sdk", ROOT / "scripts/inspect-graphics-driver-sdk.py")
SDK = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SDK)


class GraphicsDriverSdkTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.contents = self.root / "Editor/2021.3.45f2/Unity.app/Contents"
        self.editor = self.contents / "MacOS/Unity"
        self.editor.parent.mkdir(parents=True)
        self.editor.write_bytes(b"not executable")
        self.info = self.contents / "Info.plist"
        self.info.write_bytes(plistlib.dumps({"CFBundleVersion": "2021.3.45f2"}))
        self.api = self.contents / "PluginAPI"
        self.api.mkdir()
        for name in SDK.HEADERS:
            (self.api / name).write_text("// authored header fixture\n")
        self.toolchain = self.contents.parent.parent / "PlaybackEngines/AndroidPlayer/NDK/toolchains/llvm/prebuilt/darwin-x86_64"
        compiler = self.toolchain / "bin/clang++"
        compiler.parent.mkdir(parents=True)
        compiler.write_bytes(b"not executable")
        header = self.toolchain / "sysroot/usr/include/vulkan/vulkan.h"
        header.parent.mkdir(parents=True)
        header.write_text("// authored Vulkan fixture\n")

    def test_compiles_only_fixed_source_and_emits_no_paths_or_logs(self):
        commands = []

        def runner(command, **kwargs):
            commands.append(command)
            self.assertEqual(kwargs, {"capture_output": True, "timeout": 60, "check": False})
            return subprocess.CompletedProcess(command, 0, stdout=b"private SDK details", stderr=b"private compiler details")

        result = SDK.inspect(self.editor, "2021.3.45f2", runner=runner)
        self.assertEqual(result["classification"], "header-contract-passed")
        self.assertTrue(result["editor_version_matches_pin"])
        self.assertEqual(set(result["header_hashes"]), set(SDK.HEADERS))
        self.assertEqual(len(commands), 1)
        self.assertIn("-fsyntax-only", commands[0])
        self.assertIn("--target=aarch64-linux-android28", commands[0])
        self.assertNotIn("-o", commands[0])
        self.assertEqual(commands[0][-2:], [str(SDK.SOURCE), str(SDK.PRELOAD)])
        for field in ("revision_verified", "runtime_preload_verified", "driver_load_verified", "device_actions", "editor_actions"):
            self.assertFalse(result[field])
        text = json.dumps(result)
        self.assertNotIn(str(self.root), text)
        self.assertNotIn("private", text)

    def test_missing_or_wrong_version_never_invokes_a_compiler(self):
        def forbidden(*args, **kwargs):
            self.fail("compiler must not run")

        self.assertEqual(SDK.inspect(self.root / "missing", "2021.3.45f2", runner=forbidden)["classification"], "editor-unavailable")
        self.assertEqual(SDK.inspect(self.editor, "2021.3.33f1", runner=forbidden)["classification"], "editor-version-mismatch")
        (self.api / SDK.HEADERS[0]).unlink()
        self.assertEqual(SDK.inspect(self.editor, "2021.3.45f2", runner=forbidden)["classification"], "sdk-file-unavailable")

    def test_compiler_failure_is_fixed_classification(self):
        result = SDK.inspect(self.editor, "2021.3.45f2", runner=lambda *args, **kwargs: subprocess.CompletedProcess(args, 1, stderr=b"private path"))
        self.assertEqual(result["classification"], "header-contract-compile-failed")
        self.assertFalse(result["v1_intercept_compile"])
        self.assertNotIn("private path", json.dumps(result))

    def test_bounded_header_and_compiler_escape(self):
        (self.api / SDK.HEADERS[0]).write_bytes(b"x" * (SDK.LIMIT + 1))
        self.assertEqual(SDK.inspect(self.editor, "2021.3.45f2")["classification"], "sdk-file-too-large")
        (self.api / SDK.HEADERS[0]).write_bytes(b"fixture")
        compiler = self.toolchain / "bin/clang++"
        compiler.unlink()
        compiler.symlink_to(self.editor)
        self.assertEqual(SDK.inspect(self.editor, "2021.3.45f2")["classification"], "bundled-compiler-unavailable")

    @unittest.skipUnless(shutil.which("c++"), "C++ compiler absent")
    def test_actual_fixture_checks_callback_signature(self):
        (self.api / "IUnityInterface.h").write_text(
            "#pragma once\n#define UNITY_INTERFACE_API\n#define UNITY_INTERFACE_EXPORT\nstruct IUnityInterfaces {template<class T> T* Get();};\n"
        )
        (self.api / "IUnityGraphics.h").write_text("#pragma once\n")
        (self.api / "IUnityGraphicsVulkan.h").write_text(
            "#pragma once\nusing PFN_vkGetInstanceProcAddr=void*(*)();\nusing UnityVulkanInitCallback=PFN_vkGetInstanceProcAddr(*)(PFN_vkGetInstanceProcAddr,void*);\nstruct IUnityGraphicsVulkan{bool(*InterceptInitialization)(UnityVulkanInitCallback,void*);};\n"
        )
        command = [shutil.which("c++"), "-std=c++11", "-fsyntax-only", "-I" + str(self.api), str(SDK.SOURCE)]
        result = subprocess.run(command, capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        header = self.api / "IUnityGraphicsVulkan.h"
        header.write_text(header.read_text().replace("bool(*InterceptInitialization)", "void(*InterceptInitialization)"))
        result = subprocess.run(command, capture_output=True, text=True, timeout=30)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Unity Vulkan intercept result differs", result.stderr)
