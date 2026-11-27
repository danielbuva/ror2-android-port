"""Build the public DXBC translator and SPIR-V validator for Android ARM64 API 24."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
from shutil import copy2, copytree
import shlex
import subprocess
import sys
import tarfile
from tempfile import TemporaryDirectory


SOURCES = {
    "vkd3d-2.0.tar.xz": ("vkd3d-2.0", "9ad29bb236808186a47ec66e853b21e6fca59b9dc62a9474b05d5e3eda2710ef"),
    "spirv-tools.tar.gz": ("SPIRV-Tools-ef96ed763b43b59b33b31b362f09a02b729fa1c9", "82c62146083fd558735a3171cf97cfc47903ca7d368482e87f94bd44883c0f00"),
    "spirv-headers.tar.gz": ("SPIRV-Headers-496543121ce6419f23d6fa5d7194ba66c36212d2", "a9bb9c48713245eacf97cc539b6f1d45405a92d8813f8b82e635f0a085ee9898"),
    "vulkan-headers.tar.gz": ("Vulkan-Headers-vulkan-sdk-1.4.350.1", "6d1bb65e49520344cc0a48af3dc02e993781efff14c7ebdcb8ae9fa23ddf7e83"),
}


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def build(sources, ndk, bison, output, jobs):
    for name, (_, expected) in SOURCES.items():
        if sha(sources / name) != expected:
            raise ValueError(f"shader source archive drift: {name}")
    if not re.search(r"^Pkg\.Revision\s*=\s*21\.3\.6528147\s*$", (ndk / "source.properties").read_text(), re.M):
        raise ValueError("Android shader tools require NDK 21.3.6528147")
    if subprocess.check_output([bison, "--version"], text=True).splitlines()[0] != "bison (GNU Bison) 3.8.2":
        raise ValueError("Android shader tools require GNU Bison 3.8.2")

    host = {"darwin": "darwin-x86_64", "linux": "linux-x86_64"}[sys.platform]
    ndk_bin = ndk / "toolchains/llvm/prebuilt" / host / "bin"
    cc = ndk_bin / "aarch64-linux-android24-clang"
    cxx = ndk_bin / "aarch64-linux-android24-clang++"
    ar, ranlib = ndk_bin / "llvm-ar", ndk_bin / "llvm-ranlib"
    root = Path(__file__).resolve().parent
    translator_source = root.parent / "accepted-output/shader_dxbc.cpp"
    validator_source = root / "spirv_validate.cpp"
    output.mkdir()

    def run(label, argv, **kwargs):
        with (output / f"{label}.log").open("x") as log:
            print(shlex.join(map(str, argv)), file=log, flush=True)
            subprocess.run(argv, stdout=log, stderr=subprocess.STDOUT, check=True, **kwargs)

    translator = output / "libshader-dxbc.so"
    validator = output / "libspirv-val.so"
    material = output / "public-sources"
    material.mkdir()
    with TemporaryDirectory(prefix="shader-build-", dir=output) as temp:
        scratch = Path(temp)
        for name, (_, expected) in SOURCES.items():
            archive_path = material / name
            copy2(sources / name, archive_path)
            if sha(archive_path) != expected:
                raise ValueError(f"shader source archive changed: {name}")
            with tarfile.open(archive_path) as archive:
                archive.extractall(scratch, filter="data")
        vkd3d, spirv, headers, vulkan = (scratch / top for top, _ in SOURCES.values())
        patch = material / "vkd3d-structured-srv.patch"
        copy2(root / patch.name, patch)
        run("vkd3d-patch", ["patch", "-f", "-F", "0", "-p1", "-i", patch], cwd=vkd3d)

        env = dict(
            os.environ,
            AR=str(ar),
            BISON=str(bison),
            CC=str(cc),
            RANLIB=str(ranlib),
            READELF=str(ndk_bin / "llvm-readelf"),
            CFLAGS="-O2",
            CPPFLAGS=shlex.join([f"-I{headers / 'include'}", f"-I{vulkan / 'include'}"]),
        )
        run(
            "vkd3d-configure",
            [
                "./configure",
                "--host=aarch64-linux-android",
                "--disable-shared",
                "--enable-static",
                "--disable-tests",
                "--without-ncurses",
                "--without-opengl",
                "--without-xcb",
                "--without-spirv-tools",
            ],
            cwd=vkd3d,
            env=env,
        )
        run("vkd3d-version", ["make", "include/private/vkd3d_version.h"], cwd=vkd3d)
        run("vkd3d-build", ["make", f"-j{jobs}", "libvkd3d-shader.la"], cwd=vkd3d)

        relink = output / "relink"
        relink.mkdir()
        wrapper = relink / "shader_dxbc.o"
        copy2(translator_source, relink / translator_source.name)
        run("translator-compile", [cxx, "-std=c++17", "-O2", "-fPIE", "-I", vkd3d / "include", "-c", translator_source, "-o", wrapper])
        libraries = ["libvkd3d-shader.a", "libvkd3d-common.a"]
        for name in libraries:
            copy2(vkd3d / ".libs" / name, relink / name)
        link_flags = ["-static-libstdc++", "-pie", "-Wl,-s", wrapper.name, *libraries, "-lm"]
        run("translator-link", [cxx, *link_flags, "-o", translator], cwd=relink)
        (relink / "README.txt").write_text(
            "Relink shader-dxbc with the API 24 ARM64 clang++ from Android NDK 21.3.6528147.\n"
            "Run in this directory, replacing the vkd3d archives with modified versions if desired:\n\n"
            + shlex.join([cxx.name, *link_flags, "-o", translator.name])
            + "\n\nExact upstream source, the vkd3d patch and dependency archives are in ../public-sources.\n"
        )

        cmake_output = scratch / "spirv-build"
        run(
            "validator-configure",
            [
                "cmake",
                "-G",
                "Ninja",
                "-S",
                spirv,
                "-B",
                cmake_output,
                f"-DCMAKE_TOOLCHAIN_FILE={ndk / 'build/cmake/android.toolchain.cmake'}",
                "-DANDROID_ABI=arm64-v8a",
                "-DANDROID_PLATFORM=android-24",
                "-DANDROID_STL=c++_static",
                "-DCMAKE_POLICY_VERSION_MINIMUM=3.5",
                "-DCMAKE_BUILD_TYPE=Release",
                "-DSPIRV_SKIP_TESTS=ON",
                f"-DSPIRV-Headers_SOURCE_DIR={headers}",
                f"-DCMAKE_CXX_ARCHIVE_CREATE={ar} qc <TARGET> <LINK_FLAGS> <OBJECTS>",
                f"-DCMAKE_CXX_ARCHIVE_FINISH={ranlib} <TARGET>",
            ],
        )
        run("validator-build", ["cmake", "--build", cmake_output, "--parallel", str(jobs), "--target", "SPIRV-Tools-static"])
        run(
            "validator-link",
            [
                cxx,
                "-std=c++17",
                "-O2",
                "-fPIE",
                "-pie",
                "-static-libstdc++",
                "-Wl,-s",
                "-I",
                spirv / "include",
                validator_source,
                cmake_output / "source/libSPIRV-Tools.a",
                "-o",
                validator,
            ],
        )
        notices = output / "notices"
        notices.mkdir()
        copy2(vkd3d / "COPYING", notices / "vkd3d-COPYING.txt")
        copy2(vkd3d / "LICENSE", notices / "vkd3d-LICENSE.txt")
        copy2(spirv / "LICENSE", notices / "SPIRV-Tools-LICENSE.txt")
        copy2(headers / "LICENSE", notices / "SPIRV-Headers-LICENSE.txt")
        copytree(vulkan / "LICENSES", notices / "Vulkan-Headers")
        copy2(ndk / "NOTICE.toolchain", notices / "Android-NDK-toolchain-NOTICE.txt")
        copy2(ndk / "sources/cxx-stl/llvm-libc++/NOTICE", notices / "LLVM-libc++-NOTICE.txt")

    natives = {path.name: {"path": str(path), "sha256": sha(path)} for path in (translator, validator)}
    (output / "native-tools.json").write_text(json.dumps({"natives": natives}, indent=2) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sources", type=Path, required=True)
    parser.add_argument("--ndk", type=Path, required=True)
    parser.add_argument("--bison", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--jobs", type=int, default=4)
    args = parser.parse_args()
    build(args.sources.resolve(strict=True), args.ndk.resolve(strict=True), args.bison.resolve(strict=True), args.output.absolute(), args.jobs)


if __name__ == "__main__":
    main()
