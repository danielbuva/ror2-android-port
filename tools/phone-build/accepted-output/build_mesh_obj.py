"""Build the current source OBJ helper from separately acquired pinned public C."""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import time

MIKK_COMMIT = "3e895b49d05ea07e4c2133156cfa94369e19e409"
LIBC_COMMIT = "71bbe350ab79eef58113991d817ccc6165061a64"
PROVIDERS = {
    "mikktspace.c": "de87e74107df766ce68108801262bd8d53899414236b59810509a8fc2a51e288",
    "mikktspace.h": "17fc433894f24c73753d548086cc4d8c5c0379f4a6edfb98b5da243e4f0bc3d0",
    "qsort.c": "0f4692a3a9177e1dcd35f5a73552359e644ff13489896fe2309840048b7f575e",
    "heapsort.c": "3db2b12564c2c6e44e45487142beeafaf0d06cd0670419bb217451842ef40214",
}
COMPAT = """#include <stdlib.h>
#include <strings.h>
#ifndef __FBSDID
#define __FBSDID(x)
#endif
#ifndef __unused
#define __unused __attribute__((__unused__))
#endif
#ifndef __APPLE__
static inline int flsl(long x) { return x ? (int)(8*sizeof(long)-__builtin_clzl((unsigned long)x)) : 0; }
#endif
int p1_heapsort(void *, size_t, size_t, int (*)(const void *, const void *));
"""


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def build(mikk, libc, compiler, output, android_tool_root=None):
    """Keep public notices, bound compiler execution, and record source/binary pins."""
    mikk, libc, compiler = (Path(p).resolve(strict=True) for p in (mikk, libc, compiler))
    output = Path(output).absolute()
    source = Path(__file__).with_name("mesh_obj.c")
    paths = {name: (mikk if name.startswith("mikk") else libc) / name for name in PROVIDERS}
    if any(sha(path) != PROVIDERS[name] for name, path in paths.items()):
        raise ValueError("public OBJ helper source provider drift")
    if output.exists() or output.is_symlink() or output.parent != output.parent.resolve(strict=True):
        raise ValueError("new OBJ helper build directory required")
    if any(path.is_relative_to(output) or output.is_relative_to(path) for path in (mikk, libc, compiler, source.resolve())):
        raise ValueError("OBJ helper build overlaps source inputs")
    output.mkdir()
    started = time.monotonic()
    inputs = {str(path): sha(path) for path in (*paths.values(), source, compiler, Path(__file__))}
    result = {"success": False, "source_sha256": sha(source), "providers": PROVIDERS, "inputs": inputs, "commands": []}
    try:
        material = output / "source"
        material.mkdir()
        for name, path in paths.items():
            (material / name).write_bytes(path.read_bytes())
        (material / source.name).write_bytes(source.read_bytes())
        (material / "compat.h").write_text(COMPAT)
        # Both public providers carry their complete licenses in the source headers.
        for name in PROVIDERS:
            text = (material / name).read_text()
            end = text.find("*/")
            if end < 0:
                raise ValueError("public source license notice absent")
            (output / (name + ".NOTICE")).write_text(text[: end + 2] + "\n")
        (output / "NOTICE.txt").write_text(
            "Public MikkTSpace sources are unchanged, acquired separately from mmikk/MikkTSpace at " + MIKK_COMMIT + ".\n"
            "Public qsort/heapsort sources are unchanged, acquired separately from apple-oss-distributions/Libc at " + LIBC_COMMIT + ".\n"
            "Complete source-header notices are retained alongside this file. mesh_obj.c and compat.h are authored adapters.\n"
            "No SDK implementation or game data is supplied.\n"
        )
        common = [str(compiler), "-std=gnu11", "-O2", "-ffp-contract=off", "-fno-strict-aliasing", "-I", str(material)]
        if android_tool_root is not None:
            native = Path(android_tool_root).resolve(strict=True) / "usr"
            if compiler != (native / "bin/clang-21").resolve(strict=True):
                raise ValueError("Android OBJ helper requires the selected native Clang 21")
            common[1:1] = [
                "--target=aarch64-linux-android24",
                "--sysroot=" + str(native.parent),
                "-resource-dir=" + str(native / "lib/clang/21"),
                "--ld-path=" + str(native / "bin/ld.lld"),
                "-L" + str(native / "lib"),
                "-Wl,--dynamic-linker=/system/bin/linker64",
                "-fPIE",
            ]
        objects = []
        for name in ("mikktspace.c", "qsort.c", "heapsort.c", source.name):
            obj = output / (name + ".o")
            extra = ["-include", str(material / "compat.h"), "-Dheapsort=p1_heapsort", "-Dqsort=p1_qsort"] if name in ("qsort.c", "heapsort.c") else []
            result["commands"].append(common + extra + ["-c", str(material / name), "-o", str(obj)])
            objects.append(str(obj))
        result["commands"].append(common + (["-pie"] if android_tool_root is not None else []) + objects + ["-lm", "-o", str(output / "mesh-obj")])
        for index, command in enumerate(result["commands"]):
            with (output / f"{index}.stdout").open("xb") as out, (output / f"{index}.stderr").open("xb") as err:
                subprocess.run(command, stdout=out, stderr=err, check=True, timeout=300)
        if any(sha(path) != pin for path, pin in inputs.items()):
            raise ValueError("OBJ helper source/compiler changed during build")
        result.update(success=True, output_sha256=sha(output / "mesh-obj"))
        return result
    except Exception as error:
        result["error"] = type(error).__name__ + ": " + str(error)
        raise
    finally:
        result["seconds"] = time.monotonic() - started
        (output / "result.json").write_text(json.dumps(result, indent=2) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mikk", type=Path, required=True)
    parser.add_argument("--libc", type=Path, required=True)
    parser.add_argument("--compiler", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--android-tool-root", type=Path)
    args = parser.parse_args()
    print(json.dumps(build(args.mikk, args.libc, args.compiler, args.output, args.android_tool_root)))


if __name__ == "__main__":
    main()
