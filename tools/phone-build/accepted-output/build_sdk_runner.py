"""Build the current public Android runner for owner-supplied standalone SDK tools."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import time

REVISION = "420eda69ff51ab5d5a7cbc3dee2e70433be3411d"
REPOSITORY = "https://github.com/ptitSeb/box64"


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def quote(path):
    return '"' + str(path).replace("\\", "/").replace('"', '\\"').replace("$", "\\$") + '"'


def build(source, ndk, cmake, archiver, ranlib, stripper, output):
    source, ndk = source.resolve(strict=True), ndk.resolve(strict=True)
    revision = subprocess.check_output(["git", "-C", str(source), "rev-parse", "HEAD"], text=True).strip()
    dirty = subprocess.check_output(["git", "-C", str(source), "status", "--porcelain"], text=True)
    if revision != REVISION or dirty:
        raise ValueError("unchanged pinned public Box64 source required")
    properties = ndk / "source.properties"
    if "Pkg.Revision = 21.3.6528147" not in properties.read_text():
        raise ValueError("the pinned Unity SDK NDK r21d is required")
    # Preserve executable names: LLVM dispatches ranlib/strip through symlinks.
    tools = {name: path.absolute() for name, path in (("cmake", cmake), ("archiver", archiver), ("ranlib", ranlib), ("stripper", stripper))}
    toolchain = ndk / "build/cmake/android.toolchain.cmake"
    compiler = ndk / "toolchains/llvm/prebuilt/darwin-x86_64/bin/clang"
    linker = compiler.with_name("ld.lld")
    inputs = [*tools.values(), properties, toolchain, compiler, linker, Path(__file__).resolve()]
    if output.exists() or output.is_symlink() or output.parent != output.parent.resolve(strict=True):
        raise ValueError("new SDK runner build output required")
    if output.is_relative_to(source) or source.is_relative_to(output) or output.is_relative_to(ndk):
        raise ValueError("SDK runner output must be outside source providers")
    pins = {str(path): sha(path) for path in inputs}
    output.mkdir()
    started = time.monotonic()
    result = {"success": False, "repository": REPOSITORY, "revision": revision, "inputs": pins, "target": "aarch64-linux-android28"}
    try:
        # The SDK's old archiver fails on the current macOS libc++; retain its
        # compiler/sysroot/LLD and select explicit public host archive tools.
        wrapper = output / "android-toolchain.cmake"
        wrapper.write_text(
            f"include({quote(toolchain)})\n"
            f'set(CMAKE_AR {quote(tools["archiver"])} CACHE FILEPATH "" FORCE)\n'
            f'set(CMAKE_RANLIB {quote(tools["ranlib"])} CACHE FILEPATH "" FORCE)\n'
            f"set(CMAKE_AR {quote(tools['archiver'])})\n"
            f"set(CMAKE_RANLIB {quote(tools['ranlib'])})\n"
        )
        commands = [
            [
                str(tools["cmake"]),
                "-S",
                str(source),
                "-B",
                str(output / "build"),
                "-DCMAKE_TOOLCHAIN_FILE=" + str(wrapper),
                "-DANDROID_ABI=arm64-v8a",
                "-DANDROID_PLATFORM=android-28",
                "-DARM_DYNAREC=ON",
                "-DANDROID=ON",
                "-DCMAKE_BUILD_TYPE=Release",
                "-DCMAKE_EXE_LINKER_FLAGS=-fuse-ld=lld",
            ],
            [str(tools["cmake"]), "--build", str(output / "build"), "-j4"],
            [str(tools["stripper"]), "--strip-debug", "-o", str(output / "box64"), str(output / "build/box64")],
        ]
        result["commands"] = commands
        for index, command in enumerate(commands):
            (output / f"{index}-command.json").write_text(json.dumps(command, indent=2) + "\n")
            with (output / f"{index}.stdout").open("xb") as stdout, (output / f"{index}.stderr").open("xb") as stderr:
                child = subprocess.Popen(command, stdout=stdout, stderr=stderr, start_new_session=True)
                try:
                    code = child.wait(timeout=1800)
                except BaseException:
                    os.killpg(child.pid, signal.SIGKILL)
                    child.wait()
                    raise
                if code:
                    raise ValueError(f"SDK runner build step {index} failed with {code}; inspect retained logs")
        if any(sha(Path(path)) != pin for path, pin in pins.items()):
            raise ValueError("SDK runner build tool drift")
        (output / "LICENSE.txt").write_bytes((source / "LICENSE").read_bytes())
        result["output"] = {"path": str(output / "box64"), "bytes": (output / "box64").stat().st_size, "sha256": sha(output / "box64")}
        result["success"] = True
        return result
    except Exception as error:
        result["error"] = type(error).__name__ + ": " + str(error)
        raise
    finally:
        result["seconds"] = time.monotonic() - started
        (output / "result.json").write_text(json.dumps(result, indent=2) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("source", "ndk", "cmake", "archiver", "ranlib", "stripper", "output"):
        parser.add_argument("--" + name, required=True, type=Path)
    args = parser.parse_args()
    args.output = args.output.absolute()
    result = build(**vars(args))
    print(json.dumps({"success": result["success"], "output": result["output"], "seconds": result["seconds"]}))


if __name__ == "__main__":
    main()
