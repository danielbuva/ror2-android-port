"""Isolated authored C# compiler fixture; outputs still require IL2CPP.

Stages owner SDK compiler/reference bytes, never game files or captured compiler
responses. The SDK runtime configuration is copied unchanged.
"""

from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid

SDK_BINARY_SHA256 = "906123118e45d56c6bcf20f3776ed2373417553042500714023daeb9e53058e8"
FIXTURE = "tools/phone-build/ConverterFixture.cs"
FIXTURE_SHA256 = "cfc41e179d5e22a90e34708d9aee1424218640ec9e2fbe87067d6ec51977c06e"
INPUTS = {
    "compiler/csc.dll": ("DotNetSdkRoslyn/csc.dll", "da60224e49f5a12fffa0245eb9da814d69429dbe5a4f2ce03812956a1c60decb"),
    "compiler/csc.deps.json": ("DotNetSdkRoslyn/csc.deps.json", "cabe4e37c8cbe906e6f35fabfb187f8fd1501c16ff2fc19809c11a37536e2952"),
    "compiler/csc.runtimeconfig.json": ("DotNetSdkRoslyn/csc.runtimeconfig.json", "4492a5550a72f1d8ca54f479419dc9237ef49aca01ff46226c157fdec402046d"),
    "compiler/Microsoft.CodeAnalysis.dll": ("DotNetSdkRoslyn/Microsoft.CodeAnalysis.dll", "4d7844fff601069b65e06e16b099bb5aba3e68dab98b028b012fbaba6b1901d5"),
    "compiler/Microsoft.CodeAnalysis.CSharp.dll": (
        "DotNetSdkRoslyn/Microsoft.CodeAnalysis.CSharp.dll",
        "3f2e11e619f309e78a750208941d75c0b74b1b2862df8193ccaa28fd0d715737",
    ),
    "compiler/LICENSE.txt": ("DotNetSdkRoslyn/LICENSE.txt", "ae48df11a335dc1a615f4f938b69cba73bcf4485c4f97af49b38efb0f216353b"),
    "refs/mscorlib.dll": ("MonoBleedingEdge/lib/mono/unityaot-linux/mscorlib.dll", "da0423f9fba3685ccd90a32e29b483a5fd01add06214ef6ed986e55f1335a452"),
}
SOURCE = "scripts/lab/phone_managed_compile.py"
RUNTIMES = {"sdk": "6.0.21", "android": "8.0.32"}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def safe_path(path, work):
    path, work = Path(path).absolute(), Path(work).absolute()
    if path != path.resolve() or work != work.resolve() or not path.is_relative_to(work / "rebuild/phone-managed-compile"):
        raise ValueError("Select an owned compiler stage without ancestor links")
    return path, work


@contextmanager
def directory(path, work, *, new=False):
    path, work = safe_path(path, work)
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    fd = os.open(path.anchor, flags)
    current = Path(path.anchor)
    try:
        for name in path.parts[1:]:
            current /= name
            if current.is_relative_to(work):
                try:
                    os.mkdir(name, dir_fd=fd)
                except FileExistsError:
                    if new and current == path:
                        raise
            child = os.open(name, flags, dir_fd=fd)
            os.close(fd)
            fd = child
        safe_path(path, work)
        yield fd
    finally:
        os.close(fd)


def write_input(path, data, work):
    path, _ = safe_path(path, work)
    with directory(path.parent, work) as fd:
        file = os.open(path.name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=fd)
        with os.fdopen(file, "wb") as output:
            output.write(data)


def stage(root, sdk, work):
    root, sdk, work = (Path(p).absolute() for p in (root, sdk, work))
    if subprocess.check_output(["git", "status", "--porcelain", "--", SOURCE, FIXTURE], cwd=root):
        raise ValueError("Commit compiler fixture sources before staging")
    if sha(root / SOURCE) != sha(__file__) or sha(sdk / "MacOS/Unity") != SDK_BINARY_SHA256 or sha(root / FIXTURE) != FIXTURE_SHA256:
        raise ValueError("Unknown owner SDK or authored fixture")
    for source, digest in INPUTS.values():
        if sha(sdk / source) != digest:
            raise ValueError("Owner compiler/reference component drift")
    destination = work / "rebuild/phone-managed-compile" / uuid.uuid4().hex
    with directory(destination, work, new=True):
        pass
    files = {name: (sdk / source).read_bytes() for name, (source, _) in INPUTS.items()}
    files.update({"source/ConverterFixture.cs": (root / FIXTURE).read_bytes(), "phone_managed_compile.py": (root / SOURCE).read_bytes()})
    for name, data in files.items():
        write_input(destination / name, data, work)
    if sha(sdk / "MacOS/Unity") != SDK_BINARY_SHA256 or any(sha(sdk / source) != digest for source, digest in INPUTS.values()):
        raise ValueError("SDK/compiler inputs changed while staging")
    receipt = dict(
        schema=1,
        profile="authored-corelib-compiler-v1",
        source_commit=subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip(),
        sdk_binary_sha256=SDK_BINARY_SHA256,
        game_inputs=False,
        inputs={name: sha(destination / name) for name in files},
    )
    write_input(destination / "inputs.json", (json.dumps(receipt, indent=2) + "\n").encode(), work)
    return destination, receipt


def validate(stage_root):
    stage_root = Path(stage_root).absolute()
    if stage_root != stage_root.resolve() or any(p.is_symlink() for p in stage_root.rglob("*")):
        raise ValueError("Compiler stage links are unsupported")
    receipt = json.loads((stage_root / "inputs.json").read_text())
    expected = {name: digest for name, (_, digest) in INPUTS.items()}
    expected.update({"source/ConverterFixture.cs": FIXTURE_SHA256, "phone_managed_compile.py": sha(__file__)})
    if (
        receipt.get("schema") != 1
        or receipt.get("profile") != "authored-corelib-compiler-v1"
        or receipt.get("sdk_binary_sha256") != SDK_BINARY_SHA256
        or receipt.get("game_inputs") is not False
        or receipt.get("inputs") != expected
    ):
        raise ValueError("Compiler fixture input identity/scope differs")
    for name, digest in expected.items():
        if sha(stage_root / name) != digest:
            raise ValueError("Compiler fixture input drift")
    actual = {p.relative_to(stage_root).as_posix() for p in stage_root.rglob("*") if p.is_file()}
    if actual != set(expected) | {"inputs.json"}:
        raise ValueError("Foreign compiler stage files or earlier output")
    return receipt


def arguments(stage_root, launcher):
    return [
        str(launcher),
        "exec",
        "compiler/csc.dll",
        "/nologo",
        "/noconfig",
        "/nostdlib+",
        "/target:library",
        "/platform:anycpu",
        "/langversion:9.0",
        "/deterministic+",
        "/debug:portable",
        "/optimize-",
        "/pathmap:" + str(stage_root) + "=/owner-build",
        "/out:output/CompilerFixture.dll",
        "/pdb:output/CompilerFixture.pdb",
        "/r:refs/mscorlib.dll",
        "source/ConverterFixture.cs",
    ]


def compile_fixture(stage_root, launcher, host):
    stage_root, launcher = Path(stage_root).absolute(), Path(launcher).absolute()
    if host not in RUNTIMES:
        raise ValueError("Select the qualified SDK or Android build-tool profile")
    receipt = validate(stage_root)
    output = stage_root / "output"
    # Keep one fixed relative output path per new input stage for deterministic
    # document/debug paths. Repeat attempts require a fresh generated stage.
    output.mkdir(exist_ok=False)
    started = time.monotonic()
    result = dict(
        schema=1,
        source_commit=receipt["source_commit"],
        inputs_sha256=sha(stage_root / "inputs.json"),
        host=host,
        launcher_sha256=None,
        game_inputs=False,
        player_built=False,
        managed_game_compilation_qualified=False,
        success=False,
    )
    env = dict(
        os.environ, DOTNET_ROOT=str(launcher.parent), DOTNET_CLI_TELEMETRY_OPTOUT="1", DOTNET_SYSTEM_GLOBALIZATION_INVARIANT="1", TMPDIR=str(output / "tmp")
    )
    (output / "tmp").mkdir()
    try:
        result["launcher_sha256"] = sha(launcher)
        runtimes = subprocess.run([str(launcher), "--list-runtimes"], env=env, capture_output=True, text=True, timeout=30)
        (output / "runtimes.log").write_text(runtimes.stdout + runtimes.stderr)
        core = [line.split()[1] for line in runtimes.stdout.splitlines() if line.startswith("Microsoft.NETCore.App ")]
        if runtimes.returncode or core != [RUNTIMES[host]]:
            raise ValueError("Unexpected compiler build-tool runtime closure")
        result["runtime"] = core[0]
        command = arguments(stage_root, launcher)
        result["arguments"] = command
        with (output / "compiler.log").open("w") as log:
            process = subprocess.run(command, cwd=stage_root, env=env, stdout=log, stderr=subprocess.STDOUT, timeout=180)
        result["exit_code"] = process.returncode
        if process.returncode:
            raise RuntimeError("Authored compiler fixture failed; inspect retained log")
        if not (output / "CompilerFixture.dll").read_bytes().startswith(b"MZ") or not (output / "CompilerFixture.pdb").read_bytes().startswith(b"BSJB"):
            raise ValueError("Compiler fixture output formats differ")
        result["outputs"] = {name: sha(output / name) for name in ("CompilerFixture.dll", "CompilerFixture.pdb")}
        if any(sha(stage_root / name) != digest for name, digest in receipt["inputs"].items()):
            raise ValueError("Compiler inputs changed during compilation")
        result["success"] = True
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        result["failure"] = str(error)
    result["elapsed_seconds"] = time.monotonic() - started
    with (output / "result.json").open("x") as stream:
        stream.write(json.dumps(result, indent=2) + "\n")
    return result


if __name__ == "__main__":
    if len(sys.argv) == 5 and sys.argv[1] == "stage":
        destination, receipt = stage(*sys.argv[2:])
        print(json.dumps(dict(stage=str(destination), **receipt)))
    elif len(sys.argv) == 5 and sys.argv[1] == "run":
        result = compile_fixture(*sys.argv[2:])
        print(json.dumps(result))
        raise SystemExit(0 if result["success"] else 1)
    else:
        raise SystemExit("Usage: phone_managed_compile.py stage ROOT OWNER_SDK_CONTENTS WORK | run STAGE DOTNET sdk|android (isolated fixture only)")
