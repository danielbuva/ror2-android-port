#!/usr/bin/env python3
"""Build a separate authored SDK-only preload fixture; never installs or runs it.

Requires the pinned installed Editor, committed sources, a free canonical Unity
mutex and 100 GiB free. Use only in a cleared serialized lab slot. No game input,
custom driver, existing Unity project, device or Android setting is touched.
Raw compiler/Editor logs and APK stay in the new ignored output directory.
"""

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
OWNER = "tools/phone-build/owner-apk/graphics/"
SOURCES = (
    "scripts/build-graphics-preload-fixture.py",
    "scripts/inspect-graphics-driver-sdk.py",
    "scripts/lab/build_lock.py",
    "scripts/lab/phone_registry.py",
    OWNER + "native/GraphicsDriverPreload.cpp",
    OWNER + "native/UnityVulkanContract.cpp",
    OWNER + "GraphicsPreloadFixture.cs",
    OWNER + "GraphicsPreloadFixtureBuild.cs",
    "environment/toolchain.json",
)


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def stage(root, output, commit, *, work=None):
    root, output = Path(root).resolve(), Path(output).absolute()
    work = Path(work or root / "work").absolute()
    if work != work.resolve():
        raise ValueError("Canonical owned work root required")
    # The lab runner intentionally links checkout/work to the primary work root.
    # Only that verified root mapping is allowed, not links within the output.
    if output.is_relative_to(root / "work"):
        output = work / output.relative_to(root / "work")
    if not output.is_relative_to(work) or output == work or output != output.resolve() or output.exists():
        raise ValueError("New owned work output required")
    pin = json.loads((root / "environment/toolchain.json").read_text())
    project = output / "project"
    for name in ("Assets/Editor", "Assets/Plugins/Android/arm64-v8a", "Packages", "ProjectSettings"):
        (project / name).mkdir(parents=True)
    for name, target in (("GraphicsPreloadFixture.cs", "Assets"), ("GraphicsPreloadFixtureBuild.cs", "Assets/Editor")):
        shutil.copyfile(root / OWNER / name, project / target / name)
    (project / "Packages/manifest.json").write_text('{"dependencies":{"com.unity.modules.jsonserialize":"1.0.0"}}\n')
    (project / "ProjectSettings/ProjectVersion.txt").write_text(
        "m_EditorVersion: " + pin["unity_version"] + "\nm_EditorVersionWithRevision: " + pin["unity_version"] + " (" + pin["unity_revision"] + ")\n"
    )
    inputs = {"source_commit": commit, "sources": {name: sha(root / name) for name in SOURCES}, "game_inputs": False, "custom_driver_loaded": False}
    (output / "inputs.json").write_text(json.dumps(inputs, sort_keys=True) + "\n")
    return project, inputs


def commands(root, editor, project):
    contents = Path(editor).resolve().parent.parent
    toolchain = contents.parent.parent / "PlaybackEngines/AndroidPlayer/NDK/toolchains/llvm/prebuilt/darwin-x86_64"
    library = project / "Assets/Plugins/Android/arm64-v8a/libGraphicsDriverPreload.so"
    native = [
        str(toolchain / "bin/clang++"),
        "--target=aarch64-linux-android28",
        "--sysroot=" + str(toolchain / "sysroot"),
        "-std=c++11",
        "-shared",
        "-fPIC",
        "-fvisibility=hidden",
        "-static-libstdc++",
        "-Wl,--no-undefined",
        "-I" + str(contents / "PluginAPI"),
        str(root / OWNER / "native/GraphicsDriverPreload.cpp"),
        "-o",
        str(library),
    ]
    player = [
        str(editor),
        "-batchmode",
        "-nographics",
        "-quit",
        "-projectPath",
        str(project),
        "-buildTarget",
        "Android",
        "-executeMethod",
        "GraphicsPreloadFixtureBuild.Build",
        "-logFile",
        str(project.parent / "editor.log"),
    ]
    return native, player


def validate_result(output, commit):
    result = json.loads((output / "build-result.json").read_text())
    if (
        result.get("success") is not True
        or result.get("preloaded") is not True
        or result.get("editor_compatible") is not False
        or result.get("custom_driver_loaded") is not False
        or result.get("source_commit") != commit
        or result.get("failure")
    ):
        raise ValueError("Build receipt did not prove explicit preload configuration")
    apk = output / "graphics-preload-fixture.apk"
    if not apk.is_file() or apk.stat().st_size == 0:
        raise ValueError("Fixture APK missing")
    member = "lib/arm64-v8a/libGraphicsDriverPreload.so"
    library = output / "project/Assets/Plugins/Android/arm64-v8a/libGraphicsDriverPreload.so"
    try:
        with zipfile.ZipFile(apk) as archive:
            if archive.namelist().count(member) != 1 or archive.getinfo(member).file_size > 16 * 1024**2:
                raise ValueError("Packaged fixture plugin missing or ambiguous")
            with archive.open(member) as stream:
                if hashlib.file_digest(stream, "sha256").hexdigest() != sha(library):
                    raise ValueError("Packaged fixture plugin differs from compiled source")
    except zipfile.BadZipFile as error:
        raise ValueError("Fixture APK is not a ZIP") from error
    return sha(apk)


def invoke(command, log, timeout, env):
    """Keep timeout cleanup inside the Unity mutex and kill only our child group."""
    process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT, env=env, start_new_session=True)
    try:
        code = process.wait(timeout=timeout)
        if code:
            raise subprocess.CalledProcessError(code, command)
    except BaseException:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait()
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="New directory under this checkout's ignored work/")
    parser.add_argument("--editor", type=Path, help="Pinned installed Editor executable")
    args = parser.parse_args()
    result = {"success": False, "device_actions": 0, "runtime_preload_verified": False, "driver_load_verified": False, "completed_frame_verified": False}
    phase = "pinned-editor-unavailable"
    try:
        pin = json.loads((ROOT / "environment/toolchain.json").read_text())
        editor = args.editor or Path(
            os.environ.get("UNITY_EDITOR", "/Applications/Unity/Hub/Editor/" + pin["unity_version"] + "/Unity.app/Contents/MacOS/Unity")
        )
        sys.path.insert(0, str(ROOT / "scripts/lab"))
        from build_lock import host_build_lock
        from phone_registry import BINARY_SHA256

        if not editor.is_file() or sha(editor) != BINARY_SHA256:
            raise ValueError("Pinned Editor unavailable")
        phase = "fixture-source-uncommitted"
        if subprocess.check_output(["git", "status", "--porcelain", "--", *SOURCES], cwd=ROOT):
            raise ValueError("Committed fixture source required")
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
        common = Path(subprocess.check_output(["git", "rev-parse", "--path-format=absolute", "--git-common-dir"], cwd=ROOT, text=True).strip())
        phase = "host-build-admission-failed"
        if common.name != ".git" or shutil.disk_usage(common.parent).free < 100 * 1024**3:
            raise ValueError("Canonical checkout and 100 GiB free required")
        work = (common.parent / "work").resolve()
        if (ROOT / "work").resolve() != work:
            raise ValueError("Canonical lab work binding required")
        spec = importlib.util.spec_from_file_location("graphics_sdk", ROOT / "scripts/inspect-graphics-driver-sdk.py")
        sdk = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(sdk)
        phase = "sdk-header-qualification-failed"
        if sdk.inspect(editor, pin["unity_version"])["v1_intercept_compile"] is not True:
            raise ValueError("SDK header qualification failed")
        phase = "fixture-staging-failed"
        project, inputs = stage(ROOT, args.output, commit, work=work)
        gradle = project.parent / "gradle-user"
        gradle.mkdir()
        (gradle / "gradle.properties").write_text("org.gradle.daemon=false\n")
        env = dict(os.environ, ROR2_GRAPHICS_PRELOAD_COMMIT=commit, GRADLE_USER_HOME=str(gradle))
        native, player = commands(ROOT, editor, project)
        phase = "unity-mutex-unavailable"
        with host_build_lock(common.parent / "work/coordination/unity-build.lock", operation="isolated graphics preload fixture", timeout=1):
            for command, name, timeout in ((native, "native.log", 120), (player, "launch.log", 1800)):
                phase = "native-build-failed" if name == "native.log" else "player-build-failed"
                with (project.parent / name).open("wb") as log:
                    invoke(command, log, timeout, env)
        phase = "source-or-build-receipt-differs"
        if any(sha(ROOT / name) != digest for name, digest in inputs["sources"].items()):
            raise ValueError("Authored source changed during build")
        result.update(success=True, classification="fixture-built-not-run", source_commit=commit, apk_sha256=validate_result(project.parent, commit))
    except (OSError, ValueError, KeyError, RuntimeError, subprocess.SubprocessError):
        result["classification"] = phase
    print(json.dumps(result, sort_keys=True))
    return 0 if result["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
