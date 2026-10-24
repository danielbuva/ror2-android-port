#!/usr/bin/env python3
"""Rebuild the opt-in original-audio managed transform chain from accepted raw inputs."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import plistlib
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[5]
WORK = ROOT / "work"
HERE = Path(__file__).resolve().parent
EXPECTED = {
    "input_id": "6af7ed94619fe1b4346974b4486afa03a8d1625a7820e92da0ff74d57208fe88",
    "raw_api": "564b74ec232e81af8fa4b65c17537a4d05890d9181281eab0bc28bd441a3a781",
    "adapted_api": "2bd973178c99bfcb4d20510e2d1eac7efa9dd6d698237f2edfa486171bc2f272",
    "observed_api": "a2914ace8e2a7338010f8e9a9515911d68489bf0ad467bc7f73f4de293a19fe9",
    "composed_api": "1cedc89f59f44f91deea8b07fcdf289e5fec9448ba87d4d68519d6658bba942b",
    "raw_game": "a5f7d83c7e6872fdd6099fdc299adb7d4fa03cbf465e526d6f5efcc35c2c281d",
    "guarded_game": "3124a2ed9cf458acee78b1beaf969590b184be452e2b3aa5a8852df82ff95d30",
    "composed_transform_source": "a158d1fea576c87f1b0d71df583861a8c1b5a73731d61bb9315d3f2dc0c84126",
    "composed_game": "30c1cff3c18729bc509b522bb2f23d2a7c54e2f3883b926a29a3cb0fba3cf4a3",
    "point_sound_composed_game": "594282cfa617ac58eda6965e0a48e6958438f345cbb98bfb7cb49b9130efad1d",
    "owner_api_observer_source": "1b23636afe0e5f9bc6fec7a369d045364d940674c52ac3dd0df6b428ba8b878f",
    "owner_api_observer_dll": "f4036a6eae0c6c04ab59072f9f8d5fbb79adfa76b130b112068a946502ae5a36",
    "unity_reference_count": 195,
}


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def require(ok: bool, message: str) -> None:
    if not ok:
        raise RuntimeError(message)


def run(command: list[str], *, cwd: Path, env: dict[str, str], log: Path, timeout: int = 180) -> None:
    result = subprocess.run(
        command,
        cwd=cwd,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=timeout,
    )
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text(result.stdout, encoding="utf-8")
    if result.returncode:
        raise RuntimeError(f"command failed ({result.returncode}); see {log}\n{result.stdout}")


def output_directory(raw: Path) -> Path:
    absolute = Path(os.path.abspath(raw.expanduser()))
    require(
        not absolute.exists() and not absolute.is_symlink(),
        "output directory must be new",
    )
    require(
        absolute.is_relative_to(WORK.resolve()),
        "output directory must be under repository work/",
    )
    parent = absolute.parent.resolve(strict=True)
    require(parent == absolute.parent, "output parent may not traverse symlinks")
    for component in (absolute, *absolute.parents):
        require(not component.is_symlink(), "output path contains a symlink")
        if component == WORK.resolve():
            break
    ignored = subprocess.run(["git", "check-ignore", "--quiet", str(absolute)], cwd=ROOT)
    require(ignored.returncode == 0, "output path is not ignored by Git")
    absolute.mkdir()
    return absolute


def cecil_from_editor(editor: Path) -> Path:
    editor = editor.resolve(strict=True)
    contents = editor.parent.parent if editor.name == "Unity" else editor
    cecil = contents / "MonoBleedingEdge/lib/mono/gac/Mono.Cecil/0.11.1.0__0738eb9f132ed756/Mono.Cecil.dll"
    require(cecil.is_file(), "pinned Unity Mono.Cecil 0.11.1 is missing")
    expected = json.loads((ROOT / "recipe/assembly-transforms.json").read_text(encoding="utf-8"))["cecil_sha256"]
    require(sha(cecil) == expected, "Mono.Cecil differs from the repository's pinned tool")
    return cecil


def validate_editor_identity(editor: Path) -> None:
    require(
        editor.is_file() and editor.name == "Unity",
        "pass the pinned Unity editor executable",
    )
    pin = json.loads((ROOT / "environment/toolchain.json").read_text(encoding="utf-8"))
    with (editor.parent.parent / "Info.plist").open("rb") as stream:
        metadata = plistlib.load(stream)
    require(
        metadata.get("CFBundleVersion") == pin["unity_version"] == "2021.3.45f2",
        "managed producer requires Unity 2021.3.45f2",
    )
    require(
        metadata.get("UnityBuildNumber") == pin["unity_revision"],
        "managed producer Unity revision differs from the toolchain pin",
    )


def unity_compile_references(editor: Path, managed: Path) -> tuple[list[Path], list[str]]:
    contents = editor.parent.parent if editor.name == "Unity" else editor
    roots = [
        contents / "NetStandard/compat/2.1.0/shims/netfx",
        contents / "NetStandard/compat/2.1.0/shims/netstandard",
    ]
    refs: list[Path] = []
    for root in roots:
        require(root.is_dir(), f"Unity reference directory missing: {root}")
        refs.extend(sorted(root.glob("*.dll")))
    netstandard = contents / "NetStandard/ref/2.1.0/netstandard.dll"
    unity_engine = contents / "Managed/UnityEngine"
    require(
        netstandard.is_file() and unity_engine.is_dir(),
        "pinned Unity reference assemblies are incomplete",
    )
    refs.append(netstandard)
    refs.extend(path for path in sorted(unity_engine.glob("*.dll")) if not path.name.startswith("UnityEditor"))
    refs.extend(
        managed / name
        for name in (
            "AK.Wwise.Unity.API.dll",
            "AK.Wwise.Unity.MonoBehaviour.dll",
            "RoR2.dll",
        )
    )
    require(
        len(refs) == EXPECTED["unity_reference_count"] and len(set(refs)) == len(refs),
        "Unity reference set differs from the deterministic 195-reference contract",
    )
    require(
        all(path.is_file() for path in refs),
        "one or more pinned Unity/game compile references are missing",
    )
    return refs, ["-langversion:9"]


def rsp_quote(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def compile_library(
    label: str,
    output: Path,
    sources: list[Path],
    options: list[str],
    extra_refs: list[Path],
    mono: Path,
    csc: Path,
    out: Path,
    env: dict[str, str],
) -> None:
    rsp = out / "compile" / f"{label}.rsp"
    rsp.parent.mkdir(parents=True, exist_ok=True)
    rsp.write_text(
        "\n".join(
            options
            + ["-r:" + rsp_quote(str(p)) for p in extra_refs]
            + ["-target:library", "-out:" + rsp_quote(str(output))]
            + [rsp_quote(str(p)) for p in sources]
        )
        + "\n",
        encoding="utf-8",
    )
    run(
        [str(mono), str(csc), "@" + str(rsp)],
        cwd=ROOT,
        env=env,
        log=out / "logs" / f"{label}.log",
    )


def build_dotnet(
    project: Path,
    output: Path,
    cecil: Path,
    dotnet: Path,
    out: Path,
    env: dict[str, str],
) -> None:
    output.mkdir(parents=True, exist_ok=True)
    # Compile isolated authored copies; generated intermediates never touch
    # the tracked source tree. The observer project maps this source directory
    # to a stable virtual path for reproducible output bytes.
    isolated = out / "authored-projects" / project.stem
    isolated.mkdir(parents=True, exist_ok=False)
    for source in sorted(project.parent.iterdir()):
        if source.is_file() and source.suffix in (".cs", ".csproj"):
            shutil.copyfile(source, isolated / source.name)
    project = isolated / project.name
    obj = project.parent / "obj"
    run(
        [
            str(dotnet),
            "build",
            str(project),
            "--configuration",
            "Release",
            "--output",
            str(output),
            "--nologo",
            "-p:CecilPath=" + str(cecil),
            "-p:BaseIntermediateOutputPath=" + str(obj) + "/",
            "-p:RestoreConfigFile=" + str(out / "NuGet.Config"),
            "-p:UseSharedCompilation=false",
            "-p:EnableSourceLink=false",
        ],
        cwd=ROOT,
        env=env,
        log=out / "logs" / (project.stem + ".build.log"),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--android-source", required=True, type=Path)
    parser.add_argument("--android-os-string-source", required=True, type=Path)
    parser.add_argument("--native-so", required=True, type=Path)
    parser.add_argument("--llvm-nm", required=True, type=Path)
    parser.add_argument(
        "--unity-editor",
        type=Path,
        default=Path(os.environ["UNITY_EDITOR"]) if os.environ.get("UNITY_EDITOR") else None,
    )
    parser.add_argument("--dotnet", type=Path, default=Path(shutil.which("dotnet")) if shutil.which("dotnet") else None)
    parser.add_argument("--netstandard-ref", type=Path, help="explicit NETStandard.Library.Ref 2.1.0 package; default retains the existing host cache")
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()

    accepted = json.loads((WORK / "config/accepted-input.json").read_text(encoding="utf-8"))
    require(accepted.get("input_id") == EXPECTED["input_id"], "accepted input identity changed")
    composed_transform_source = HERE / "tools/composed/ComposedGameCecilTransform.cs"
    lightning_owner_source = ROOT / "tools/unity/runtime/world/LightningStakeSourceCallObserver.cs"
    if not lightning_owner_source.is_file():
        lightning_owner_source = HERE.parents[2] / "runtime/world/LightningStakeSourceCallObserver.cs"
    require(
        sha(composed_transform_source) == EXPECTED["composed_transform_source"],
        "composed Cecil transform source pin changed",
    )
    local = json.loads((WORK / "config/local.json").read_text(encoding="utf-8"))
    managed = Path(local["game_path"]).expanduser().resolve(strict=True) / "Risk of Rain 2_Data/Managed"
    raw_game = managed / "RoR2.dll"
    raw_api = managed / "AK.Wwise.Unity.API.dll"
    require(
        raw_game.is_file() and raw_api.is_file(),
        "configured accepted managed assemblies are missing",
    )
    require(sha(raw_game) == EXPECTED["raw_game"], "accepted raw game assembly hash changed")
    require(sha(raw_api) == EXPECTED["raw_api"], "accepted raw Wwise API hash changed")
    require(
        args.android_source.is_file() and args.android_os_string_source.is_file() and args.native_so.is_file() and args.llvm_nm.is_file(),
        "one or more explicit local Wwise Android ABI inputs are absent",
    )
    require(args.unity_editor is not None, "pass --unity-editor or set UNITY_EDITOR")
    require(args.dotnet is not None, "pass --dotnet or put dotnet on PATH")
    require(args.dotnet.is_file(), "dotnet missing; source scripts/env.sh or pass --dotnet")
    editor = args.unity_editor.resolve(strict=True)
    validate_editor_identity(editor)
    mono_bleeding = editor.parent.parent / "MonoBleedingEdge" if editor.name == "Unity" else editor / "MonoBleedingEdge"
    mono = mono_bleeding / "bin/mono"
    csc = mono_bleeding / "lib/mono/msbuild/Current/bin/Roslyn/csc.exe"
    require(mono.is_file() and csc.is_file(), "pinned Unity Mono/Roslyn compiler is missing")
    cecil = cecil_from_editor(editor)
    unity_refs, compiler_options = unity_compile_references(editor, managed)
    out = output_directory(args.output_dir)

    env = dict(os.environ)
    env.update(
        {
            "UNITY_EDITOR": str(editor),
            "DOTNET_CLI_HOME": str(out / ".dotnet-home"),
            "NUGET_PACKAGES": str(out / ".nuget/packages"),
            "NUGET_HTTP_CACHE_PATH": str(out / ".nuget/http-cache"),
            "NUGET_PLUGINS_CACHE_PATH": str(out / ".nuget/plugins"),
            "DOTNET_CLI_TELEMETRY_OPTOUT": "1",
            "DOTNET_SKIP_FIRST_TIME_EXPERIENCE": "1",
            "DOTNET_CLI_WORKLOAD_UPDATE_NOTIFY_DISABLE": "true",
            "MSBUILDDISABLENODEREUSE": "1",
            "DOTNET_CLI_USE_MSBUILD_SERVER": "0",
            "TMPDIR": str(out / "tmp"),
            "TMP": str(out / "tmp"),
            "TEMP": str(out / "tmp"),
        }
    )
    (out / "tmp").mkdir()
    # The repository's tracked transform loader reads this setting directly
    # from the current Python process environment as well as child processes.
    os.environ["UNITY_EDITOR"] = str(editor)
    # The isolated NuGet cache prevents compiler output from escaping this
    # preview tree. Seed the framework-reference package from explicit owner
    # input or the retained default host cache. Never restore from a network
    # feed during this producer run.
    installed_netstandard = args.netstandard_ref if args.netstandard_ref is not None else Path.home() / ".nuget/packages/netstandard.library.ref/2.1.0"
    isolated_netstandard = out / ".nuget/packages/netstandard.library.ref/2.1.0"
    require(installed_netstandard.is_dir(), "NETStandard.Library.Ref 2.1.0 input is missing")
    isolated_netstandard.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(installed_netstandard, isolated_netstandard)
    nuget = out / "NuGet.Config"
    nuget.write_text(
        "<configuration><packageSources><clear /></packageSources></configuration>\n",
        encoding="utf-8",
    )

    # Generate adapted API bytes directly from the accepted raw installation.
    abi_plan = out / "abi-plan.json"
    adapted_api = out / "api-adapted.dll"
    abi_tool = ROOT / "tools/wwise-android-abi/generate.py"
    run(
        [
            sys.executable,
            str(abi_tool),
            "--android-source",
            str(args.android_source.resolve(strict=True)),
            "--android-os-string-source",
            str(args.android_os_string_source.resolve(strict=True)),
            "--native-so",
            str(args.native_so.resolve(strict=True)),
            "--llvm-nm",
            str(args.llvm_nm.resolve(strict=True)),
            "--cecil",
            str(cecil),
            "--dotnet",
            str(args.dotnet.resolve(strict=True)),
            "--output",
            str(abi_plan),
            "--candidate",
            str(adapted_api),
        ],
        cwd=ROOT,
        env=env,
        log=out / "logs/abi-adapter.log",
    )
    require(
        sha(adapted_api) == EXPECTED["adapted_api"],
        "adapted API output differs from the qualified byte pin",
    )

    # Compile and apply the pre-init observer authored from the accepted API contract.
    owner_observer_source = HERE / "source/owner-api/OriginalOwnerProbeObserver.cs"
    require(sha(owner_observer_source) == EXPECTED["owner_api_observer_source"], "owner API observer source pin changed")
    owner_observer_project = HERE / "source/owner-api/OriginalOwnerProbeObserver.csproj"
    owner_observer_out = out / "compiled/owner-api-observer"
    build_dotnet(
        owner_observer_project,
        owner_observer_out,
        cecil,
        args.dotnet.resolve(strict=True),
        out,
        env,
    )
    owner_observer = owner_observer_out / "OriginalOwnerProbeObserver.dll"
    require(sha(owner_observer) == EXPECTED["owner_api_observer_dll"], "owner API observer helper pin changed")
    owner_tool_project = HERE / "tools/owner-api/OwnerApiCecilTransform.csproj"
    owner_tool_out = out / "compiled/owner-api-transform"
    build_dotnet(
        owner_tool_project,
        owner_tool_out,
        cecil,
        args.dotnet.resolve(strict=True),
        out,
        env,
    )
    observed_api = out / "api-observed.dll"
    run(
        [
            str(args.dotnet.resolve(strict=True)),
            str(owner_tool_out / "OwnerApiCecilTransform.dll"),
            "transform",
            str(adapted_api),
            str(observed_api),
            str(owner_observer),
        ],
        cwd=ROOT,
        env=env,
        log=out / "logs/owner-api-transform.log",
    )
    require(
        sha(observed_api) == EXPECTED["observed_api"],
        "observed API output differs from the qualified byte pin",
    )

    # Compile the runtime core from source. The helper is a distinct assembly from
    # the pre-init observer, preserving the reviewed assembly DAG.
    core_sources = HERE.parent / "core"
    core_dir = out / "compiled/core"
    core_dir.mkdir(parents=True)
    point_sound_build_pin = core_dir / "GameAudioOriginalPointSoundBuildPin.cs"
    point_sound_build_pin.write_text(
        "// Generated by the public managed producer for this exact output variant.\n"
        "internal static class GameAudioOriginalPointSoundBuildPin\n{\n"
        "    internal const bool DiagnosticCallsitesPresent = true;\n"
        "}\n",
        encoding="utf-8",
    )
    core_observer = core_dir / "OriginalOwnerProbeObserver.dll"
    run(
        [
            str(mono),
            str(csc),
            "-target:library",
            "-out:" + str(core_observer),
            str(core_sources / "OriginalOwnerProbeObserver.cs"),
        ],
        cwd=ROOT,
        env=env,
        log=out / "logs/core-observer.log",
    )
    core = core_dir / "GameAudioOriginalCore.dll"
    compile_library(
        "core",
        core,
        [
            core_sources / "GameAudioOriginalReadiness.cs",
            core_sources / "GameAudioOriginalPassivePcmContract.cs",
            core_sources / "GameAudioOriginalOwner.cs",
            core_sources / "PointSoundDiagnosticObserver.cs",
            point_sound_build_pin,
        ],
        compiler_options,
        unity_refs + [core_observer],
        mono,
        csc,
        out,
        env,
    )

    # Rebuild the game's optional-presentation guard from raw accepted Managed
    # assemblies through the tracked recipe. No existing guarded DLL is consumed.
    sys.path.insert(0, str(ROOT / "scripts/lab"))
    import assembly_transforms

    with tempfile.TemporaryDirectory(prefix="raw-game-transform-", dir=out) as tmp:
        regenerated = assembly_transforms.generate(managed, Path(tmp), assembly_transforms.load_recipe())
        guarded_game = out / "game-optional-presentation-guarded.dll"
        shutil.copyfile(regenerated["RoR2.dll"], guarded_game)
    require(
        sha(guarded_game) == EXPECTED["guarded_game"],
        "raw game transform chain differs from the accepted optional-presentation guarded pin",
    )

    # Apply the final audio transform to the raw-derived guarded game and the
    # observed API; assembly dependency resolution reads the accepted Managed dir.
    composed_project = HERE / "tools/composed/ComposedGameCecilTransform.csproj"
    composed_tool_out = out / "compiled/composed-transform"
    build_dotnet(composed_project, composed_tool_out, cecil, args.dotnet.resolve(strict=True), out, env)
    composed_tool = composed_tool_out / "ComposedGameCecilTransform.dll"
    composed_api = out / "api-instrumented-composed.dll"
    run(
        [
            str(args.dotnet.resolve(strict=True)),
            str(composed_tool),
            "api",
            str(observed_api),
            str(core),
            str(composed_api),
            str(editor.parent.parent / "Managed/UnityEngine/UnityEngine.CoreModule.dll"),
        ],
        cwd=ROOT,
        env=env,
        log=out / "logs/composed-api.log",
    )
    require(sha(composed_api) == EXPECTED["composed_api"], "composed API output differs from the qualified byte pin")
    composed_game = out / "game-original-owner-composed.dll"
    run(
        [
            str(args.dotnet.resolve(strict=True)),
            str(composed_tool),
            "game",
            str(guarded_game),
            str(core),
            str(composed_game),
            str(managed),
        ],
        cwd=ROOT,
        env=env,
        log=out / "logs/composed-game.log",
    )

    require(sha(composed_game) == EXPECTED["composed_game"], "composed game output differs from its exact R3 source pin")
    point_sound_game = out / "game-original-owner-point-sound-composed.dll"
    run(
        [
            str(args.dotnet.resolve(strict=True)),
            str(composed_tool),
            "point-sound",
            str(composed_game),
            str(core),
            str(point_sound_game),
            str(managed),
        ],
        cwd=ROOT,
        env=env,
        log=out / "logs/point-sound-composed.log",
    )
    run(
        [str(args.dotnet.resolve(strict=True)), str(composed_tool), "validate-point-sound", str(point_sound_game)],
        cwd=ROOT,
        env=env,
        log=out / "logs/point-sound-validation.log",
    )

    require(sha(point_sound_game) == EXPECTED["point_sound_composed_game"], "point-sound composed output differs from its exact R3 source pin")
    manifest = {
        "schema": "game-audio-original-public-producer-r1",
        "accepted_input_id": accepted["input_id"],
        "source_input_hashes": {
            "raw_game": sha(raw_game),
            "raw_api": sha(raw_api),
            "abi_plan": sha(abi_plan),
            "adapted_api": sha(adapted_api),
            "observed_api": sha(observed_api),
            "composed_api": sha(composed_api),
            "guarded_game": sha(guarded_game),
            "composed_game": sha(composed_game),
            "point_sound_composed_game": sha(point_sound_game),
        },
        "android_abi_input_hashes": {
            "generated_android_source": sha(args.android_source.resolve(strict=True)),
            "handwritten_android_source": sha(args.android_os_string_source.resolve(strict=True)),
            "arm64_release_native_plugin": sha(args.native_so.resolve(strict=True)),
            "llvm_nm": sha(args.llvm_nm.resolve(strict=True)),
        },
        "transformation_source_hashes": {
            (str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else "tools/unity/runtime/world/LightningStakeSourceCallObserver.cs"): sha(path)
            for path in (
                ROOT / "tools/wwise-android-abi/generate.py",
                ROOT / "scripts/lab/assembly_transforms.py",
                ROOT / "recipe/assembly-transforms.json",
                HERE / "produce.py",
                HERE / "source/owner-api/OriginalOwnerProbeObserver.cs",
                HERE / "source/owner-api/OriginalOwnerProbeObserver.csproj",
                HERE.parent / "core/OriginalOwnerProbeObserver.cs",
                HERE.parent / "core/GameAudioOriginalReadiness.cs",
                HERE.parent / "core/GameAudioOriginalPassivePcmContract.cs",
                HERE.parent / "core/GameAudioOriginalOwner.cs",
                HERE.parent / "core/PointSoundDiagnosticObserver.cs",
                HERE / "tools/owner-api/OwnerApiCecilTransform.cs",
                HERE / "tools/owner-api/OwnerApiCecilTransform.csproj",
                lightning_owner_source,
                HERE / "tools/composed/ComposedGameCecilTransform.cs",
                HERE / "tools/composed/ComposedGameCecilTransform.csproj",
            )
        },
        "abi_policy": {
            "mapped_imports": 1269,
            "unavailable_imports": 11,
            "full_enable_ready": False,
        },
        "toolchain_inputs": {
            "unity_editor_executable": sha(editor),
            "unity_mono": sha(mono),
            "unity_roslyn_csc": sha(csc),
            "dotnet": sha(args.dotnet.resolve(strict=True)),
            "cecil": sha(cecil),
            "unity_references": [sha(path) for path in unity_refs],
        },
        "request": {
            "requested": False,
            "stage_to_apk_binding": False,
            "dispatch_ready": False,
        },
        "outputs_relative_to_work": {str(p.relative_to(WORK)): sha(p) for p in sorted(out.rglob("*")) if p.is_file() and p.name != "manifest.json"},
    }
    manifest_path = out / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "output_dir_relative_to_work": str(out.relative_to(WORK)),
                "manifest_sha256": sha(manifest_path),
                "hashes": manifest["source_input_hashes"],
                "full_enable_ready": False,
                "requested": False,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"public producer refused: {type(error).__name__}: {error}", file=sys.stderr)
        raise SystemExit(2)
