"""Opt-in public .NET 8 build-tool profile; never executes inspected game assemblies."""

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import stat
import subprocess
import tarfile
import zipfile

import assembly_transforms
from common import RECIPE, ROOT, read, sha, write

RECIPE_SHA256 = "1f4b333652fbb38174f8e2f7c54366369171b543789a4fbfe54fd8db4cc2fec1"
GLOBALS = "".join(
    "global using global::" + name + ";\n"
    for name in ("System", "System.Collections.Generic", "System.IO", "System.Linq", "System.Net.Http", "System.Threading", "System.Threading.Tasks")
)


def relative(value):
    path = PurePosixPath(value)
    if not value or not path.parts or path.is_absolute() or ".." in path.parts or "\\" in value or path.as_posix() != value:
        raise RuntimeError("Unsafe public tool member path")
    return path


def load_recipe():
    path = RECIPE / "owner-public-tools.json"
    if sha(path) != RECIPE_SHA256:
        raise RuntimeError("Public tool recipe drift")
    recipe = read(path)
    if recipe["schema"] != 1 or recipe["kind"] != "owner-public-dotnet8-v1":
        raise RuntimeError("Unsupported public tool profile")
    if [row["role"] for row in recipe["artifacts"]] != ["compiler", "cecil", "references"]:
        raise RuntimeError("Public tool archive roles differ")
    paths = set()
    for artifact in recipe["artifacts"]:
        if Path(artifact["filename"]).name != artifact["filename"] or artifact["format"] not in {"zip", "tar.gz"}:
            raise RuntimeError("Invalid public tool archive")
        names = set()
        for row in artifact["members"]:
            relative(row["archive"])
            relative(row["path"])
            if row["path"] in paths or row["archive"] in names or type(row["bytes"]) is not int or not 0 < row["bytes"] <= 8 * 1024**2:
                raise RuntimeError("Duplicate or oversized public tool member")
            paths.add(row["path"])
            names.add(row["archive"])
    for row in [recipe["witness"], *recipe["notices"]]:
        relative(row["path"])
        if sha(ROOT / row["path"]) != row["sha256"]:
            raise RuntimeError("Public tool witness/notice drift")
    return recipe


def archive_state(directory, recipe):
    directory = Path(directory).expanduser().absolute()
    if directory != directory.resolve() or not directory.is_dir():
        raise RuntimeError("Public tool archives require a real directory without ancestor links")
    paths = {}
    for row in recipe["artifacts"]:
        path = directory / row["filename"]
        if path.is_symlink() or not path.is_file() or path.stat().st_size != row["bytes"] or sha(path) != row["sha256"]:
            raise RuntimeError("Public tool archive drift: " + row["role"])
        paths[row["role"]] = path
    return paths


def extract(archives, destination, recipe):
    """Hash all archives before parsing; only predeclared regular members are written."""
    if any(path.stat().st_size != row["bytes"] or sha(path) != row["sha256"] for row in recipe["artifacts"] for path in [archives[row["role"]]]):
        raise RuntimeError("Public tool archive changed before extraction")
    destination.mkdir()
    manifest = []

    def place(content, row):
        relative(row["path"])
        if len(content) != row["bytes"] or hashlib.sha256(content).hexdigest() != row["sha256"]:
            raise RuntimeError("Extracted public tool member drift: " + row["path"])
        if "git_blob" in row and hashlib.sha1(b"blob " + str(len(content)).encode() + b"\0" + content).hexdigest() != row["git_blob"]:
            raise RuntimeError("Public Cecil source Git blob drift")
        path = destination / row["path"]
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("xb") as stream:
            stream.write(content)
        manifest.append(dict(path=row["path"], bytes=len(content), sha256=row["sha256"]))

    for artifact in recipe["artifacts"]:
        selected = {row["archive"]: row for row in artifact["members"]}
        path = archives[artifact["role"]]
        if artifact["format"] == "zip":
            with zipfile.ZipFile(path) as package:
                if len(package.namelist()) != len(set(package.namelist())):
                    raise RuntimeError("Duplicate public ZIP members")
                for name, row in selected.items():
                    info = package.getinfo(name)
                    mode = stat.S_IFMT(info.external_attr >> 16)
                    if info.is_dir() or mode not in {0, stat.S_IFREG} or info.file_size != row["bytes"]:
                        raise RuntimeError("Public ZIP member kind/size drift")
                    place(package.read(name), row)
        else:
            seen = set()
            with tarfile.open(path, "r:gz") as package:
                for member in package:
                    if member.name not in selected:
                        continue
                    row = selected[member.name]
                    if member.name in seen or not member.isfile() or member.size != row["bytes"]:
                        raise RuntimeError("Public tar member kind/size drift")
                    place(package.extractfile(member).read(), row)
                    seen.add(member.name)
            if seen != set(selected):
                raise RuntimeError("Missing public Cecil source members")
    for row in recipe["notices"]:
        relative(row["destination"])
        data = (ROOT / row["path"]).read_bytes()
        place(data, dict(path=row["destination"], bytes=len(data), sha256=row["sha256"]))
    write(destination / "manifest.json", manifest)
    return manifest


def generate(managed, temporary, transforms, *, archives, launcher, host):
    """Keep a persistent attempt; caller must supply a fresh disposable directory."""
    managed, temporary = Path(managed).resolve(), Path(temporary).absolute()
    recipe = load_recipe()
    if host not in recipe["runtimes"]:
        raise RuntimeError("Select a qualified public build-tool host")
    runtime = recipe["runtimes"][host]
    launcher = Path(launcher).expanduser().absolute()
    if launcher != launcher.resolve() or not launcher.is_file():
        raise RuntimeError("Public tool launcher must be a real file without ancestor links")
    if temporary != temporary.resolve() or not temporary.is_dir() or any(temporary.iterdir()):
        raise RuntimeError("Public transform attempt must be a new empty real directory")
    if temporary == managed or temporary.is_relative_to(managed) or managed.is_relative_to(temporary):
        raise RuntimeError("Public transform attempt overlaps original input")
    if transforms != assembly_transforms.load_recipe():
        raise RuntimeError("Public transform contract drift")
    paths = archive_state(archives, recipe)
    if any(path.is_relative_to(temporary) for path in paths.values()):
        raise RuntimeError("Public archive cache overlaps output")
    sources = {name: sha(ROOT / name) for name in transforms["tool_sources"]}
    original_hashes = {path.name: sha(path) for path in managed.glob("*.dll") if path.is_file()}
    inputs = {name: value for step in transforms["steps"] for name, value in step["inputs"].items()}
    if any(original_hashes.get(name) != expected for name, expected in inputs.items()):
        raise RuntimeError("Public transform original input drift")
    state = dict(
        schema=1,
        profile="public-dotnet8",
        success=False,
        phase="preparing",
        host=host,
        recipe_sha256=sha(RECIPE / "owner-public-tools.json"),
        source_hashes=sources,
        archives={role: sha(path) for role, path in paths.items()},
        launcher_sha256=sha(launcher),
        sdk_cecil_used=False,
        sdk_framework_references_used=False,
        game_assemblies_executed=False,
        full_project_qualified=False,
        phone_build_qualified=False,
        runtime_qualified=False,
    )
    receipt = temporary / "public-tools-receipt.json"
    write(receipt, state)
    try:
        material = temporary / "materials"
        manifest = extract(paths, material, recipe)
        src, original, provider, tool = (temporary / name for name in ("src", "original", "provider", "tool"))
        for path in (src, original, provider, tool):
            path.mkdir()
        for name in sources:
            shutil.copyfile(ROOT / name, src / Path(name).name)
        if any(sha(src / Path(name).name) != expected for name, expected in sources.items()):
            raise RuntimeError("Copied authored transform source drift")
        for path in managed.glob("*.dll"):
            if path.is_symlink():
                raise RuntimeError("Original Managed links are unsupported")
            shutil.copyfile(path, original / path.name)
        if {path.name: sha(path) for path in original.glob("*.dll")} != original_hashes:
            raise RuntimeError("Copied public transform references drifted")
        imports = temporary / "GlobalUsings.cs"
        imports.write_text(GLOBALS)
        witness = temporary / "PublicProviderWitness.cs"
        shutil.copyfile(ROOT / recipe["witness"]["path"], witness)
        environment = {key: value for key, value in os.environ.items() if not key.startswith(("DOTNET_", "NUGET_", "COMPlus_", "CORECLR_"))}
        environment.update(
            DOTNET_ROOT=str(launcher.parent),
            DOTNET_MULTILEVEL_LOOKUP="0",
            DOTNET_CLI_HOME=str(temporary / "dotnet-home"),
            DOTNET_CLI_TELEMETRY_OPTOUT="1",
            DOTNET_SKIP_FIRST_TIME_EXPERIENCE="1",
            DOTNET_SYSTEM_GLOBALIZATION_INVARIANT="1",
            TMPDIR=str(temporary / "tmp"),
            TMP=str(temporary / "tmp"),
            TEMP=str(temporary / "tmp"),
        )
        (temporary / "tmp").mkdir()

        def execute(arguments, label):
            write(temporary / (label + "-arguments.json"), arguments)
            result = subprocess.run(arguments, cwd=temporary, env=environment, capture_output=True, timeout=180)
            (temporary / (label + ".stdout.log")).write_bytes(result.stdout)
            (temporary / (label + ".stderr.log")).write_bytes(result.stderr)
            if result.returncode:
                raise RuntimeError(label + " failed; inspect retained log (exit " + str(result.returncode) + ")")
            return result

        versions = execute([str(launcher), "--list-runtimes"], "runtimes")
        core = [line.split()[1] for line in versions.stdout.decode().splitlines() if line.startswith("Microsoft.NETCore.App ")]
        if core != [runtime["version"]]:
            raise RuntimeError("Public build-tool runtime closure differs")
        compiler = material / "compiler/csc.dll"
        version = execute([str(launcher), "exec", str(compiler), "-version"], "compiler-version")
        if version.stdout.decode().strip() != recipe["compiler_version"]:
            raise RuntimeError("Public compiler version differs")
        flags = [str(launcher), "exec", str(compiler), "-noconfig", "-nostdlib+", "-langversion:latest", "-deterministic+", "-debug:portable"]
        refs = ["-r:" + str(material / row["path"]) for row in manifest if row["path"].startswith("refs/") and row["path"].endswith(".dll")]
        cecil = [str(material / row["path"]) for row in manifest if row["path"].startswith("cecil-source/") and row["path"].endswith(".cs")]
        if len(refs) != 163 or len(cecil) != 132:
            raise RuntimeError("Public reference/source compilation membership differs")
        execute(
            flags
            + [
                "-target:library",
                "-nullable:disable",
                "-optimize+",
                "-define:NET_CORE",
                "-pathmap:" + str(material / "cecil-source") + "=/_/public-cecil",
                "-out:" + str(provider / "Mono.Cecil.dll"),
                *refs,
                *cecil,
            ],
            "provider-compile",
        )
        execute(
            flags
            + [
                "-target:exe",
                "-nullable:enable",
                "-pathmap:" + str(temporary) + "=/_/owner-tools",
                "-out:" + str(tool / "AssemblyProbe.dll"),
                "-r:" + str(provider / "Mono.Cecil.dll"),
                *refs,
                *map(str, sorted(src.glob("*.cs"))),
                str(imports),
                str(witness),
            ],
            "tool-compile",
        )
        shutil.copyfile(provider / "Mono.Cecil.dll", tool / "Mono.Cecil.dll")
        write(
            tool / "AssemblyProbe.runtimeconfig.json",
            {"runtimeOptions": {"tfm": "net8.0", "framework": {"name": "Microsoft.NETCore.App", "version": "8.0.32"}, "rollForward": runtime["roll_forward"]}},
        )
        environment["ROR2LAB_CECIL_SHA256"] = sha(provider / "Mono.Cecil.dll")
        state.update(phase="transforming", provider_sha256=environment["ROR2LAB_CECIL_SHA256"], provider_witnesses=[], outputs={})
        write(receipt, state)
        checked = 0
        for index, step in enumerate(transforms["steps"]):
            tokens = {"{managed}": str(original)}
            for name, expected in step["inputs"].items():
                tokens.update(
                    {"{original:" + name + "}": str(original / name), "{output:" + name + "}": str(temporary / name), "{sha256:" + name + "}": expected}
                )
            process = execute(
                [str(launcher), "exec", str(tool / "AssemblyProbe.dll"), step["mode"], *[tokens[token] for token in step["arguments"]]],
                "transform-" + str(index),
            )
            witnesses = [
                json.loads(line.removeprefix("CECIL_PROVIDER_WITNESS "))
                for line in process.stderr.decode().splitlines()
                if line.startswith("CECIL_PROVIDER_WITNESS ")
            ]
            expected_witness = dict(
                path=str(tool / "Mono.Cecil.dll"),
                sha256=state["provider_sha256"],
                identity="Mono.Cecil, Version=0.11.1.0, Culture=neutral, PublicKeyToken=null",
                runtime_version=runtime["version"],
            )
            if witnesses != [expected_witness]:
                raise RuntimeError("Loaded public provider/runtime witness differs")
            state["provider_witnesses"].extend(witnesses)
            for name, expected in step["outputs"].items():
                actual = sha(temporary / name)
                checked += 1
                if actual != expected:
                    raise assembly_transforms.RebuiltAssemblyDrift(name, expected, actual, checked)
                state["outputs"][name] = actual
        if {path.name: sha(path) for path in managed.glob("*.dll")} != original_hashes or {
            path.name: sha(path) for path in original.glob("*.dll")
        } != original_hashes:
            raise RuntimeError("Original or copied Managed inputs changed")
        if any(sha(ROOT / name) != expected for name, expected in sources.items()):
            raise RuntimeError("Authored transform sources changed")
        if any(sha(src / Path(name).name) != expected for name, expected in sources.items()) or load_recipe() != recipe:
            raise RuntimeError("Copied sources or public tool contract changed")
        if any(sha(material / row["path"]) != row["sha256"] for row in manifest):
            raise RuntimeError("Extracted public dependencies changed")
        archive_state(archives, recipe)
        state.update(phase="complete", success=True, material_files=len(manifest), input_files=len(original_hashes))
        write(receipt, state)
        return {name: temporary / name for name in state["outputs"]}
    except BaseException as error:
        state.update(phase="failed", error_type=type(error).__name__, error=str(error))
        try:
            write(receipt, state)
        except Exception as receipt_error:
            raise RuntimeError(str(error) + "; failed to record public tool failure: " + str(receipt_error)) from error
        raise


def main():
    parser = argparse.ArgumentParser(description="Experimental public transform component only; no game/player build or accepted-inventory qualification.")
    parser.add_argument("--managed", required=True)
    parser.add_argument("--dest", required=True, help="New directory under this checkout's ignored work/rebuild/")
    parser.add_argument("--archives", required=True, help="Read-only cache of the three exact public archives")
    parser.add_argument("--launcher", required=True)
    parser.add_argument("--host", required=True, choices=("host10", "android8"))
    args = parser.parse_args()
    destination = Path(args.dest).expanduser().absolute()
    if not destination.is_relative_to(ROOT / "work/rebuild") or destination != destination.resolve():
        parser.error("--dest must be a new real directory under this checkout's work/rebuild/")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.mkdir(mode=0o700)
    generated = generate(args.managed, destination, assembly_transforms.load_recipe(), archives=args.archives, launcher=args.launcher, host=args.host)
    print(json.dumps(dict(outputs={name: sha(path) for name, path in generated.items()}, receipt=str(destination / "public-tools-receipt.json")), indent=2))


if __name__ == "__main__":
    main()
