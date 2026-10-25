"""Build the LZ4 block worker from a separately supplied public v1.9.4 archive."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import tarfile
import time

# https://github.com/lz4/lz4/archive/refs/tags/v1.9.4.tar.gz
LZ4_SHA = "0b0e3aa07c8c063ddf40b082bdf7e37a1562bda40a0ff5272957f3e987e0e54b"
SOURCES = {"lz4.c", "lz4.h", "lz4hc.c", "lz4hc.h", "LICENSE"}


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def build(lz4_archive, compiler, output, android_tool_root=None):
    if sha(lz4_archive) != LZ4_SHA:
        raise ValueError("public LZ4 source provider drift")
    compiler = compiler.absolute()
    output = output.absolute()
    source = Path(__file__).with_name("bundle_lz4.c")
    inputs = [lz4_archive.resolve(), compiler.resolve(), source.resolve(), Path(__file__).resolve()]
    if (
        output.exists()
        or output.is_symlink()
        or output.parent != output.parent.resolve(strict=True)
        or any(p.is_relative_to(output) or output.is_relative_to(p) for p in inputs)
    ):
        raise ValueError("new disjoint LZ4 build output required")
    output.mkdir()
    started = time.monotonic()
    result = {"success": False, "inputs": {str(p): sha(p) for p in inputs}}
    try:
        material = output / "source"
        material.mkdir()
        with tarfile.open(lz4_archive, "r:gz") as archive:
            seen = set()
            for member in archive:
                prefix = "lz4-1.9.4/lib/"
                if not member.name.startswith(prefix) or member.name[len(prefix) :] not in SOURCES:
                    continue
                name = member.name[len(prefix) :]
                if name in seen or not member.isfile() or not 0 < member.size <= 1024 * 1024:
                    raise ValueError("public LZ4 archive member differs")
                data = archive.extractfile(member).read()
                if len(data) != member.size:
                    raise ValueError("truncated public LZ4 source")
                (material / name).write_bytes(data)
                seen.add(name)
        if seen != SOURCES:
            raise ValueError("missing public LZ4 source")
        (material / source.name).write_bytes(source.read_bytes())
        (output / "LZ4-LICENSE.txt").write_bytes((material / "LICENSE").read_bytes())
        (output / "NOTICE.txt").write_text(
            "LZ4 v1.9.4 library sources are unchanged.\n"
            "bundle_lz4.c is an authored block-protocol wrapper.\n"
            "The LZ4 BSD 2-Clause license is retained in LZ4-LICENSE.txt.\n"
        )
        args = [
            str(compiler),
            "-O2",
            "-std=c11",
            "-I",
            str(material),
            str(material / source.name),
            str(material / "lz4.c"),
            str(material / "lz4hc.c"),
            "-o",
            str(output / "bundle-lz4"),
        ]
        if android_tool_root is not None:
            native = android_tool_root.resolve(strict=True) / "usr"
            if compiler.resolve() != (native / "bin/clang-21").resolve(strict=True):
                raise ValueError("Android LZ4 build requires the selected native Clang 21")
            args[1:1] = [
                "--target=aarch64-linux-android24",
                "--sysroot=" + str(native),
                "-resource-dir=" + str(native / "lib/clang/21"),
                "--ld-path=" + str(native / "bin/ld.lld"),
                "-B" + str(native / "lib"),
                "-L/system/lib64",
                "-fPIE",
                "-pie",
            ]
        result["arguments"] = args
        result["compiler_version"] = subprocess.run([str(compiler), "--version"], capture_output=True, text=True, check=True, timeout=10).stdout
        with (output / "compiler.stdout").open("xb") as stdout, (output / "compiler.stderr").open("xb") as stderr:
            child = subprocess.Popen(args, stdout=stdout, stderr=stderr, start_new_session=True)
            try:
                result["returncode"] = child.wait(timeout=300)
            except BaseException:
                os.killpg(child.pid, signal.SIGKILL)
                child.wait()
                raise
        if result["returncode"] != 0:
            raise ValueError("public LZ4 compilation failed; inspect retained logs")
        if any(sha(Path(p)) != expected for p, expected in result["inputs"].items()):
            raise ValueError("public LZ4 source/compiler changed during build")
        result["sources"] = {p.name: sha(p) for p in sorted(material.iterdir())}
        result["output_sha256"] = sha(output / "bundle-lz4")
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
    parser.add_argument("--lz4-archive", type=Path, required=True)
    parser.add_argument("--compiler", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--android-tool-root", type=Path)
    args = parser.parse_args()
    build(args.lz4_archive, args.compiler, args.output, args.android_tool_root)


if __name__ == "__main__":
    main()
