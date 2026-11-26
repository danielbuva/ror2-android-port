"""Acquire and build the pinned Android toolhost Python wheelhouse on the host."""

import argparse
import importlib.metadata
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
from urllib.request import urlopen

from stage import digest, load_metadata

JPEG_URL = "https://www.ijg.org/files/jpegsrc.v9b.tar.gz"
JPEG_SHA = "566241ad815df935390b341a5d3d15a73a4000e5aab40c58505324c2855cbbb8"
CIBW_VERSION = "4.3.4"  # CPython 3.14.8, Android API 24
NDK_VERSION = "27.3.13750724"


def download(url, target, expected):
    with urlopen(url, timeout=90) as response:
        target.write_bytes(response.read())
    if digest(target) != expected:
        raise ValueError("Public Python dependency drift: " + target.name)
    return target


def pypi(directory, project, filename, expected):
    name, version = project.rsplit("-", 1)
    with urlopen(f"https://pypi.org/pypi/{name}/{version}/json", timeout=30) as response:
        files = json.load(response)["urls"]
    record = next(row for row in files if row["filename"] == filename and row["digests"]["sha256"] == expected)
    return download(record["url"], directory / filename, expected)


def build_jpeg(directory, toolchain):
    archive = download(JPEG_URL, directory / "jpegsrc.v9b.tar.gz", JPEG_SHA)
    with tarfile.open(archive) as source:
        source.extractall(directory, filter="data")
    prefix = directory / "jpeg-android"
    tools = toolchain / "bin"
    env = dict(os.environ, CC=str(tools / "aarch64-linux-android24-clang"), AR=str(tools / "llvm-ar"), RANLIB=str(tools / "llvm-ranlib"), CFLAGS="-O2 -fPIC")
    cwd = directory / "jpeg-9b"
    subprocess.run(
        ["./configure", "--host=aarch64-linux-android", "--disable-shared", "--enable-static", "--prefix=" + str(prefix)],
        cwd=cwd,
        env=env,
        check=True,
    )
    subprocess.run(["make", "-j4", "install"], cwd=cwd, check=True)
    return prefix, cwd / "README"


def build(sdk, destination):
    if importlib.metadata.version("cibuildwheel") != CIBW_VERSION:
        raise ValueError("Toolhost wheel build requires cibuildwheel " + CIBW_VERSION)
    ndk = sdk / "ndk" / NDK_VERSION
    if not (ndk / "package.xml").is_file():
        raise ValueError("Install the pinned Android NDK in the supplied SDK: " + NDK_VERSION)
    (toolchain,) = (ndk / "toolchains/llvm/prebuilt").iterdir()
    plan = load_metadata()
    destination.mkdir()
    for name, expected in plan["python_wheels"].items():
        pypi(destination, name.removesuffix("-py3-none-any.whl"), name, expected)
    with tempfile.TemporaryDirectory(prefix="wheel-sources-", dir=destination) as temporary:
        sources = Path(temporary)
        distribution = plan["python_android_distribution"]
        archive = download(distribution["url"], sources / "android-python.tar.gz", distribution["sha256"])
        with tarfile.open(archive) as source:
            for name, expected in distribution["extensions"].items():
                with source.extractfile("./prefix/lib/python3.14/lib-dynload/" + name) as extension:
                    target = destination / name
                    target.write_bytes(extension.read())
                if digest(target) != expected:
                    raise ValueError("Android Python extension drift: " + name)
        for project, source in plan["python_source_wheels"].items():
            archive = pypi(sources, project, project + ".tar.gz", source["sha256"])
            if source.get("pure"):
                command = ["-m", "build", "--wheel", "--outdir", destination, archive]
                env = dict(os.environ, PYYAML_FORCE_LIBYAML="0")
            else:
                command = ["-m", "cibuildwheel", "--platform", "android", "--archs", "arm64_v8a", "--output-dir", destination, archive]
                env = dict(os.environ, ANDROID_HOME=str(sdk), ANDROID_API_LEVEL="24", CIBW_BUILD="cp314-android_arm64_v8a", CIBW_TEST_COMMAND="")
                if project.startswith("lz4-"):
                    env["CIBW_ENVIRONMENT"] = "PYLZ4_USE_SYSTEM_LZ4=False"
                if project.startswith("etcpak-"):
                    # abi3audit mistakes the extension's own PyBC7CompressBlockParamsObject for a CPython API symbol.
                    env["CIBW_AUDIT_COMMAND"] = ""
                if project.startswith("pillow-"):
                    jpeg, notice = build_jpeg(sources, toolchain)
                    name = "IJG-README.txt"
                    if digest(notice) != plan["python_notices"][name]:
                        raise ValueError("IJG license notice drift")
                    shutil.copyfile(notice, destination / name)
                    sysroot = toolchain / "sysroot/usr"
                    env.update(
                        CIBW_BEFORE_ALL="",
                        CIBW_CONFIG_SETTINGS="platform-guessing=disable jpeg=enable zlib=enable",
                        CIBW_ENVIRONMENT=(
                            f"C_INCLUDE_PATH='{jpeg / 'include'}:{sysroot / 'include'}' "
                            f"LIBRARY_PATH='{jpeg / 'lib'}:{sysroot / 'lib/aarch64-linux-android/24'}'"
                        ),
                    )
            subprocess.run([sys.executable, *command], env=env, check=True)
    pins = {path.name: digest(path) for path in sorted(destination.glob("*.whl")) if path.name not in plan["python_wheels"]}
    (destination / "built-wheel-hashes.json").write_text(json.dumps(pins, indent=2) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sdk", type=Path, required=True, help="SDK with the pinned NDK installed")
    parser.add_argument("--output", type=Path, required=True, help="new ignored wheelhouse directory")
    args = parser.parse_args()
    build(args.sdk.resolve(strict=True), args.output.resolve())
