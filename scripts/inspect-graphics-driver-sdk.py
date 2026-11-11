#!/usr/bin/env python3
"""Compile-only inspection of the pinned installed SDK; never runs Unity or a phone.

Only fixed classifications and public SDK hashes leave this process. An installed
version/header compile is not proof of the exact editor revision, native plugin
preload order, a driver load, a completed frame, or Android/game readiness.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import plistlib
import subprocess

ROOT = Path(__file__).resolve().parents[1]
HEADERS = ("IUnityInterface.h", "IUnityGraphics.h", "IUnityGraphicsVulkan.h")
SOURCE = ROOT / "tools/phone-build/owner-apk/graphics/native/UnityVulkanContract.cpp"
PRELOAD = SOURCE.with_name("GraphicsDriverPreload.cpp")
LIMIT = 1024 * 1024


class Unavailable(Exception):
    pass


def read(path):
    try:
        with path.open("rb") as stream:
            value = stream.read(LIMIT + 1)
        if len(value) > LIMIT:
            raise Unavailable("sdk-file-too-large")
        return value
    except OSError:
        raise Unavailable("sdk-file-unavailable") from None


def inspect(editor, expected_version, *, runner=subprocess.run):
    result = {
        "scope": "installed-version-header-compile",
        "editor_version_matches_pin": False,
        "revision_verified": False,
        "header_hashes": {},
        "v1_intercept_compile": False,
        "runtime_preload_verified": False,
        "driver_load_verified": False,
        "device_actions": 0,
        "editor_actions": 0,
    }
    try:
        editor = Path(editor)
        if not editor.is_absolute() or not editor.is_file():
            raise Unavailable("editor-unavailable")
        contents = editor.resolve().parent.parent
        metadata = plistlib.loads(read(contents / "Info.plist"))
        if not isinstance(metadata, dict):
            raise Unavailable("editor-metadata-invalid")
        if metadata.get("CFBundleVersion") != expected_version:
            raise Unavailable("editor-version-mismatch")
        result["editor_version_matches_pin"] = True
        api = contents / "PluginAPI"
        for name in HEADERS:
            result["header_hashes"][name] = hashlib.sha256(read(api / name)).hexdigest()
        android = contents.parent.parent / "PlaybackEngines/AndroidPlayer"
        ndk = android / "NDK"
        # The documented SDK is the macOS ARM64 Editor with its bundled NDK.
        toolchain = ndk / "toolchains/llvm/prebuilt/darwin-x86_64"
        compiler = toolchain / "bin/clang++"
        if not compiler.is_file() or not compiler.resolve().is_relative_to(ndk.resolve()):
            raise Unavailable("bundled-compiler-unavailable")
        sysroot = toolchain / "sysroot"
        if not (sysroot / "usr/include/vulkan/vulkan.h").is_file():
            raise Unavailable("bundled-vulkan-header-unavailable")
        # No project, build, temporary source, object, device or Editor invocation.
        command = [
            str(compiler),
            "--target=aarch64-linux-android28",
            "--sysroot=" + str(sysroot),
            "-std=c++11",
            "-fsyntax-only",
            "-I" + str(api),
            str(SOURCE),
            str(PRELOAD),
        ]
        completed = runner(command, capture_output=True, timeout=60, check=False)
        result["v1_intercept_compile"] = completed.returncode == 0
        result["classification"] = "header-contract-passed" if completed.returncode == 0 else "header-contract-compile-failed"
        result["fixture_sha256"] = hashlib.sha256(read(SOURCE)).hexdigest()
        result["preload_fixture_sha256"] = hashlib.sha256(read(PRELOAD)).hexdigest()
    except Unavailable as failure:
        result["classification"] = str(failure)
    except (OSError, ValueError, plistlib.InvalidFileException, subprocess.SubprocessError):
        result["classification"] = "sdk-inspection-failed"
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--editor", type=Path, help="Pinned installed Unity executable; path is never included in output")
    args = parser.parse_args()
    pin = json.loads((ROOT / "environment/toolchain.json").read_text())
    editor = args.editor or Path(os.environ.get("UNITY_EDITOR", "/Applications/Unity/Hub/Editor/" + pin["unity_version"] + "/Unity.app/Contents/MacOS/Unity"))
    result = inspect(editor, pin["unity_version"])
    print(json.dumps(result, sort_keys=True))
    return 0 if result["v1_intercept_compile"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
