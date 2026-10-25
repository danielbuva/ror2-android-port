"""Build the current ETC texture transforms from a pinned public source provider."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import tarfile
import time

ARCHIVE_SHA = "5fc5cad3e8ccd930a82f38da208f24c35b9a565a622092d0d4a37847000c98d2"
PREFIX = "ETCPACK-14a64d9d19318fb9f81ce339b7103ffa0f1781d7/"
MEMBERS = {"source/etcpack.cxx", "source/etcdec.cxx", "source/image.cxx", "source/image.h", "licence.txt"}
CRUNCH = {
    "crn_decomp.h": "02cfe20541ebf3938c1d7e45e8e152cce6fda7765aae8b3541a6801b958ead44",
    "crn_defs.h": "89ea127682fd999b0b6a4b4f3efefa05e215eb4b3b3396797135314787328d90",
    "crnlib.h": "dd029880dd28bc7d82ddbe9f096dc91285188d8947c8e73d85c8f438f107dee1",
    "LICENSE": "bbc49afbe103d3e4f792ce6609cfa18016073ade1416f87617661452d7c8b470",
}
# Compatibility for the unused upstream CLI's Windows-style timing calls.
TIMEB = """#ifndef AUTHORED_CODEC_TIMEB_H
#define AUTHORED_CODEC_TIMEB_H
#include <time.h>
struct timeb {time_t time; unsigned short millitm; short timezone, dstflag;};
static inline int ftime(struct timeb *value) {
    struct timespec now;
    if (clock_gettime(CLOCK_REALTIME, &now)) return -1;
    value->time=now.tv_sec; value->millitm=now.tv_nsec/1000000;
    value->timezone=0; value->dstflag=0; return 0;
}
#endif
"""


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def build(archive, compiler, output, android_tool_root=None):
    if sha(archive) != ARCHIVE_SHA:
        raise ValueError("public ETC codec source provider drift")
    compiler = compiler.absolute()
    source = Path(__file__).with_name("texture_etc.cpp")
    crunch = source.parent / "third_party/unitycrunch"
    if any(sha(crunch / name) != pin for name, pin in CRUNCH.items()):
        raise ValueError("public Unity Crunch source provider drift")
    inputs = [archive.resolve(), compiler.resolve(), source.resolve(), Path(__file__).resolve(), *(crunch / name for name in CRUNCH)]
    if output.exists() or output.is_symlink() or output.parent != output.parent.resolve(strict=True):
        raise ValueError("new ETC codec build output required")
    if any(p.is_relative_to(output) or output.is_relative_to(p) for p in inputs):
        raise ValueError("ETC codec build overlaps input")
    output.mkdir()
    started = time.monotonic()
    result = {"success": False, "inputs": {str(p): sha(p) for p in inputs}, "commands": []}
    try:
        material = output / "source"
        material.mkdir()
        seen = set()
        with tarfile.open(archive, "r:gz") as provider:
            for member in provider:
                if not member.name.startswith(PREFIX) or member.name[len(PREFIX) :] not in MEMBERS:
                    continue
                key = member.name[len(PREFIX) :]
                if key in seen or not member.isfile() or not 0 < member.size <= 1024**2:
                    raise ValueError("public ETC source archive member differs")
                data = provider.extractfile(member).read()
                if len(data) != member.size:
                    raise ValueError("truncated public ETC source")
                (material / Path(key).name).write_bytes(data)
                seen.add(key)
        if seen != MEMBERS:
            raise ValueError("missing public ETC source")
        (material / source.name).write_bytes(source.read_bytes())
        staged_crunch = material / "third_party/unitycrunch"
        staged_crunch.mkdir(parents=True)
        for name in CRUNCH:
            (staged_crunch / name).write_bytes((crunch / name).read_bytes())
        (material / "malloc.h").write_text(
            "#ifdef __APPLE__\n#include <malloc/malloc.h>\n#define malloc_usable_size malloc_size\n#else\n#include_next <malloc.h>\n#endif\n"
        )
        (material / "sys").mkdir()
        (material / "sys/timeb.h").write_text(TIMEB)
        (output / "LICENSE.txt").write_bytes((material / "licence.txt").read_bytes())
        (output / "CRUNCH-LICENSE.txt").write_bytes((crunch / "LICENSE").read_bytes())
        (output / "NOTICE.txt").write_text(
            "ETCPACK 2.74 sources are unchanged, acquired separately by the owner.\n"
            "Its Software License Agreement is retained in LICENSE.txt.\n"
            "The authored texture_etc.cpp adapter and timing compatibility header are additions.\n"
            "No upstream encoder implementation is distributed by the repository.\n"
            "Unchanged public Unity Crunch decompression headers are separately retained under Zlib.\n"
            "Their full notice is in CRUNCH-LICENSE.txt; malloc.h is an authored platform shim.\n"
        )
        common = [str(compiler), "--driver-mode=g++", "-std=c++11", "-O2", "-ffp-contract=off", "-w", "-D_timeb=timeb", "-D_ftime=ftime", "-I", str(material)]
        if android_tool_root is not None:
            native = android_tool_root.resolve(strict=True) / "usr"
            if compiler.resolve() != (native / "bin/clang-21").resolve(strict=True):
                raise ValueError("Android ETC build requires the selected native Clang 21")
            common[1:1] = [
                "--target=aarch64-linux-android24",
                "--sysroot=" + str(native.parent),
                "-resource-dir=" + str(native / "lib/clang/21"),
                "--ld-path=" + str(native / "bin/ld.lld"),
                "-stdlib=libc++",
                "-isystem",
                str(native / "include/c++/v1"),
                "-L" + str(native / "lib"),
                "-Wl,--dynamic-linker=/system/bin/linker64",
                "-fPIE",
            ]
        objects = []
        for name in ("etcpack.cxx", "etcdec.cxx", "image.cxx", source.name):
            obj = output / (name + ".o")
            command = common + (["-Dmain=etcpack_public_cli_main"] if name == "etcpack.cxx" else []) + ["-c", str(material / name), "-o", str(obj)]
            if name == source.name:
                command.insert(1, "-fno-strict-aliasing")
            result["commands"].append(command)
            objects.append(obj)
        result["commands"].append(common + (["-pie"] if android_tool_root is not None else []) + [*map(str, objects), "-o", str(output / "texture-etc")])
        result["compiler_version"] = subprocess.run([str(compiler), "--version"], capture_output=True, text=True, check=True, timeout=10).stdout
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
                raise ValueError(f"public ETC compilation step {index} failed; inspect retained logs")
        if any(sha(Path(p)) != pin for p, pin in result["inputs"].items()):
            raise ValueError("public ETC source/compiler changed during build")
        result["output_sha256"] = sha(output / "texture-etc")
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
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--compiler", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--android-tool-root", type=Path)
    args = parser.parse_args()
    result = build(args.archive, args.compiler, args.output.absolute(), args.android_tool_root)
    print(json.dumps({"success": result["success"], "output_sha256": result["output_sha256"], "seconds": result["seconds"]}))


if __name__ == "__main__":
    main()
