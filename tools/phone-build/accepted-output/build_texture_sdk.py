"""Build current SDK pipe/pixel tools from explicit owner and public providers."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import struct
import subprocess
import time

SDK_MAC = "d44cabed1440522efcdf486863176fdea4a0ca26984f43637a611c31dbb518ef"
SDK_LINUX = "4dc31e0bc2591141648b238fa158fe700dd37c13f62fe3f165618ba85c1a2293"
BCDEC = "134520764d96f70a27db814173616c89ad85db95fbd3328417c7a8c77e7ca189"


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def files(root):
    return [p for p in sorted(root.rglob("*")) if p.is_file()]


def build(compiler, linker, library, output, qemu_root=None, sysroot=None, android_tool_root=None):
    compiler = compiler.absolute()
    library = library.resolve(strict=True)
    linux = qemu_root is not None
    if linux != (sysroot is not None) or linux != (linker is not None):
        raise ValueError("Linux SDK requires explicit QEMU root, GNU development sysroot and linker")
    if sha(library) != (SDK_LINUX if linux else SDK_MAC):
        raise ValueError("unqualified standalone SDK codec provider")
    source = Path(__file__).resolve().parent
    header = source / "third_party/bcdec/bcdec.h"
    if sha(header) != BCDEC:
        raise ValueError("public BC7 source provider drift")
    inputs = [compiler.resolve(), library, Path(__file__).resolve(), source / "sdk_texture_codec.c", source / "texture_pixels.c", *files(header.parent)]
    runtime = []
    if linux:
        qemu_root = qemu_root.resolve(strict=True)
        sysroot = sysroot.resolve(strict=True)
        linker = linker.absolute()
        runtime = [qemu_root / "bin/qemu-x86_64", *files(qemu_root / "lib"), *files(qemu_root / "linux")]
        if any(not p.is_file() for p in runtime) or not (qemu_root / "linux/lib64/ld-linux-x86-64.so.2").is_file():
            raise ValueError("incomplete explicit public Linux runtime")
        inputs += [linker.resolve(), *runtime, *files(sysroot)]
    if android_tool_root is not None:
        native = android_tool_root.resolve(strict=True) / "usr"
        if not linux or compiler.resolve() != (native / "bin/clang-21").resolve(strict=True):
            raise ValueError("Android SDK helper build requires the selected native Clang 21")
    inputs = sorted(set(inputs))
    if output.exists() or output.is_symlink() or output.parent != output.parent.resolve(strict=True):
        raise ValueError("new SDK texture build output required")
    if any(p.is_relative_to(output) or output.is_relative_to(p) for p in inputs):
        raise ValueError("SDK texture build overlaps input")
    output.mkdir()
    started = time.monotonic()
    result = {"success": False, "inputs": {str(p): sha(p) for p in inputs}, "commands": []}
    try:
        codec, decoder = output / "texture-sdk-codec", output / "texture-pixels"
        common = [str(compiler), "-std=c11", "-O2", "-ffp-contract=off"]
        native_flags = []
        if android_tool_root is not None:
            common.append("-resource-dir=" + str(native / "lib/clang/21"))
            native_flags = [
                "--target=aarch64-linux-android24",
                "--sysroot=" + str(native.parent),
                "--ld-path=" + str(native / "bin/ld.lld"),
                "-L" + str(native / "lib"),
                "-Wl,--dynamic-linker=/system/bin/linker64",
                "-fPIE",
                "-pie",
            ]
        result["commands"].append([*common, *native_flags, str(source / "texture_pixels.c"), "-o", str(decoder)])
        if linux:
            dev = sysroot / "usr/lib/x86_64-linux-gnu"
            lib = sysroot / "lib/x86_64-linux-gnu"
            command = [
                *common,
                "--target=x86_64-linux-gnu",
                "--sysroot=" + str(sysroot),
                "-fuse-ld=" + str(linker),
                "-nostdlib",
                "-Wl,-e,_start",
                "-Wl,--dynamic-linker=/lib64/ld-linux-x86-64.so.2",
                str(dev / "crt1.o"),
                str(dev / "crti.o"),
                str(source / "sdk_texture_codec.c"),
                str(lib / "libc.so.6"),
                str(dev / "libc_nonshared.a"),
                str(lib / "libdl.so.2"),
                str(dev / "crtn.o"),
                "-o",
                str(codec),
            ]
        else:
            command = [*common, str(source / "sdk_texture_codec.c"), "-o", str(codec)]
        result["commands"].append(command)
        for index, command in enumerate(result["commands"]):
            with (output / f"{index}.stdout").open("xb") as stdout, (output / f"{index}.stderr").open("xb") as stderr:
                child = subprocess.Popen(command, stdout=stdout, stderr=stderr, start_new_session=True)
                try:
                    code = child.wait(timeout=300)
                except BaseException:
                    os.killpg(child.pid, signal.SIGKILL)
                    child.wait()
                    raise
            if code:
                raise ValueError(f"SDK texture compilation step {index} failed; inspect retained logs")
        if linux:
            data = codec.read_bytes()[:20]
            if data[:6] != b"\x7fELF\x02\x01" or struct.unpack_from("<H", data, 18)[0] != 62:
                raise ValueError("SDK wrapper is not Linux x86-64 ELF")
        if any(sha(Path(p)) != pin for p, pin in result["inputs"].items()):
            raise ValueError("SDK texture build input changed")
        command = [str(codec), str(library)]
        environment = {}
        if linux:
            command = [
                str(qemu_root / "bin/qemu-x86_64"),
                "-L",
                str(qemu_root / "linux"),
                "-E",
                "LD_LIBRARY_PATH=" + str(qemu_root / "linux/lib/x86_64-linux-gnu"),
                "-E",
                "LC_ALL=C",
                *command,
            ]
            environment = {"LD_LIBRARY_PATH": str(qemu_root / "lib")}
        toolchain = {
            "command": command,
            "environment": environment,
            "pixels": str(decoder),
            "inputs": {str(p): sha(p) for p in sorted(set([codec, decoder, library, *runtime]))},
        }
        (output / "sdk-tools.json").write_text(json.dumps(toolchain, indent=2) + "\n")
        (output / "BCDEC-LICENSE.txt").write_bytes((header.parent / "LICENSE").read_bytes())
        (output / "NOTICE.txt").write_text(
            "BC7 decoding uses unchanged public bcdec 0.985 under its MIT alternative; retain its license.\n"
            "The SDK is supplied separately by the owner under its provider terms; no SDK is distributed.\n"
            "QEMU/GNU runtime providers retain their separate GPL/LGPL licenses and notices.\n"
            "The pipe adapters and this build recipe are authored additions; no game data is included.\n"
        )
        result["outputs"] = {p.name: sha(p) for p in (codec, decoder, output / "sdk-tools.json")}
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
    for name in ("compiler", "library", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    for name in ("linker", "qemu-root", "sysroot", "android-tool-root"):
        parser.add_argument("--" + name, type=Path)
    args = parser.parse_args()
    result = build(args.compiler, args.linker, args.library, args.output.absolute(), args.qemu_root, args.sysroot, args.android_tool_root)
    print(json.dumps({"success": result["success"], "seconds": result["seconds"], "outputs": result["outputs"]}))


if __name__ == "__main__":
    main()
