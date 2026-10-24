"""Build the current public JPEG transform from pinned offline source providers."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import tarfile
import time

JPEG_SHA = "566241ad815df935390b341a5d3d15a73a4000e5aab40c58505324c2855cbbb8"
STB_SHA = "cbd5f0ad7a9cf4468affb36354a1d2338034f2c12473cf1a8e32053cb6914a05"
LIBRARY = """jaricom jcapimin jcapistd jcarith jccoefct jccolor jcdctmgr jchuff
jcinit jcmainct jcmarker jcmaster jcomapi jcparam jcprepct jcsample jctrans
jdapimin jdapistd jdarith jdatadst jdatasrc jdcoefct jdcolor jddctmgr jdhuff
jdinput jdmainct jdmarker jdmaster jdmerge jdpostct jdsample jdtrans jerror
jfdctflt jfdctfst jfdctint jidctflt jidctfst jidctint jquant1 jquant2 jutils
jmemmgr jmemnobs""".split()
HEADERS = "jerror jmorecfg jpeglib jdct jinclude jmemsys jpegint jversion".split()
CONFIG = """/* Authored configuration: supported 64-bit Unix C11 hosts; no backing store. */
#define HAVE_PROTOTYPES 1
#define HAVE_UNSIGNED_CHAR 1
#define HAVE_UNSIGNED_SHORT 1
#define HAVE_STDDEF_H 1
#define HAVE_STDLIB_H 1
#define HAVE_LOCALE_H 1
#ifdef JPEG_INTERNALS
#define INLINE inline
#endif
"""


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def build(jpeg_archive, stb_header, compiler, output, android_tool_root=None):
    if sha(jpeg_archive) != JPEG_SHA or sha(stb_header) != STB_SHA:
        raise ValueError("public JPEG source provider drift")
    compiler = compiler.absolute()
    source = Path(__file__).with_name("texture_jpeg.c")
    inputs = [jpeg_archive.resolve(), stb_header.resolve(), compiler.resolve(), source.resolve(), Path(__file__).resolve()]
    if (
        output.exists()
        or output.is_symlink()
        or output.parent != output.parent.resolve(strict=True)
        or any(p.is_relative_to(output) or output.is_relative_to(p) for p in inputs)
    ):
        raise ValueError("new disjoint JPEG build output required")
    output.mkdir()
    started = time.monotonic()
    result = {"success": False, "inputs": {str(p): sha(p) for p in inputs}}
    try:
        material = output / "source"
        material.mkdir()
        selected = {name + ".c" for name in LIBRARY} | {name + ".h" for name in HEADERS} | {"README"}
        with tarfile.open(jpeg_archive, "r:gz") as archive:
            seen = set()
            for member in archive:
                if not member.name.startswith("jpeg-9b/") or member.name[8:] not in selected:
                    continue
                name = member.name[8:]
                if name in seen or not member.isfile() or not 0 < member.size <= 512 * 1024:
                    raise ValueError("public JPEG archive member differs")
                data = archive.extractfile(member).read()
                if len(data) != member.size:
                    raise ValueError("truncated public JPEG source")
                (material / name).write_bytes(data)
                seen.add(name)
        if seen != selected:
            raise ValueError("missing public JPEG source")
        (material / "jconfig.h").write_text(CONFIG)
        (material / "stb_image_write.h").write_bytes(stb_header.read_bytes())
        (material / source.name).write_bytes(source.read_bytes())
        (output / "IJG-README.txt").write_bytes((material / "README").read_bytes())
        (output / "NOTICE.txt").write_text(
            "This software is based in part on the work of the Independent JPEG Group.\n"
            "IJG 9b sources are unchanged; jconfig.h and texture_jpeg.c are authored additions.\n"
            "stb_image_write.h is unchanged; its dual MIT/public-domain notice is retained in the source header.\n"
        )
        args = [
            str(compiler),
            "-O2",
            "-ffp-contract=off",
            "-std=c11",
            "-I",
            str(material),
            str(material / source.name),
            *[str(material / (name + ".c")) for name in LIBRARY],
            "-lm",
            "-o",
            str(output / "texture-jpeg"),
        ]
        if android_tool_root is not None:
            native = android_tool_root.resolve(strict=True) / "usr"
            if compiler.resolve() != (native / "bin/clang-21").resolve(strict=True):
                raise ValueError("Android JPEG build requires the selected native Clang 21")
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
            raise ValueError("public JPEG compilation failed; inspect retained logs")
        if any(sha(Path(p)) != expected for p, expected in result["inputs"].items()):
            raise ValueError("public JPEG source/compiler changed during build")
        result["sources"] = {p.name: sha(p) for p in sorted(material.iterdir())}
        result["output_sha256"] = sha(output / "texture-jpeg")
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
    parser.add_argument("--jpeg-archive", type=Path, required=True)
    parser.add_argument("--stb-header", type=Path, required=True)
    parser.add_argument("--compiler", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--android-tool-root", type=Path)
    args = parser.parse_args()
    build(args.jpeg_archive, args.stb_header, args.compiler, args.output.absolute(), args.android_tool_root)


if __name__ == "__main__":
    main()
