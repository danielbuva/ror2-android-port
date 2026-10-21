#!/usr/bin/env python3
"""Produce the default-off Wwise owner assemblies from authored R7 source pins.

The opt-in branch is intentionally a separate operation because it consumes
licensed native and bank inputs. This producer contains no implicit lookup of
timestamped runs and writes only below the explicit output directory.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import plistlib
import re
import shutil
import subprocess
import sys
import tempfile


def find_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "AGENTS.md").is_file():
            return parent
    raise RuntimeError("repository root not found")


ROOT = find_root()
SOURCE = ROOT / "tools/unity/support/audio"
TOOLS = SOURCE / "generators"
DEFAULT_API_SHA256 = "107295e478a58ef295a83228111f375c536861bc9081f482d638c59899bf495c"
DEFAULT_GAME_SHA256 = "3124a2ed9cf458acee78b1beaf969590b184be452e2b3aa5a8852df82ff95d30"
PREVIOUS_COMPOSED_API_SHA256 = "d540a22693ca7a149cdb2344ce5f61936c2c998a9d82f0bdf66b5492edb18e23"
OLDER_RESTORE_API_SHA256 = "9a3f9911697b4ce28a955dff09f618e0f2662083e56eeb28ff5b6ecc02b588f3"
PREVIOUS_COMPOSED_GAME_SHA256 = "6f96ed83bf6358b9aecc4cdf866d424caf04af9abd34ad368c8db271d27c15cc"
OLDER_PREVIOUS_GAME_SHA256 = "1034a747e31a3b79554b9cb06f941c7acabaa9e0ee82c2a00abc4b24f9327c1c"
LEGACY_RESTORE_API_SHA256 = "793f22866c85bbcf104f20f5c1f619062eaad9f5414a217b602fe758c71e01b9"
LINEAGE = {
    "accepted_input_id": "6af7ed94619fe1b4346974b4486afa03a8d1625a7820e92da0ff74d57208fe88",
    "accepted_game_sha256": "a5f7d83c7e6872fdd6099fdc299adb7d4fa03cbf465e526d6f5efcc35c2c281d",
    "guarded_game_input_sha256": DEFAULT_GAME_SHA256,
    "raw_api_sha256": "564b74ec232e81af8fa4b65c17537a4d05890d9181281eab0bc28bd441a3a781",
    "adapted_api_sha256": "2bd973178c99bfcb4d20510e2d1eac7efa9dd6d698237f2edfa486171bc2f272",
    "observed_api_sha256": "a2914ace8e2a7338010f8e9a9515911d68489bf0ad467bc7f73f4de293a19fe9",
    "composed_api_sha256": "1cedc89f59f44f91deea8b07fcdf289e5fec9448ba87d4d68519d6658bba942b",
    "composed_game_sha256": "6f96ed83bf6358b9aecc4cdf866d424caf04af9abd34ad368c8db271d27c15cc",
    "native_library_sha256": "bb5879b4eb38b81dc3830a1662ba467b60b595e7fedb88a1301d3161f8ab9304",
    "stage_receipt_sha256": "8fe02400a7ab0905ae21b728e702d7ef2c4dcf8646f77f631682a81bda0ab88c",
}
ASSEMBLY_TARGETS = {
    "observer": "Assets/LabLoadingScene/Plugins/OriginalOwnerProbeObserver.dll",
    "core": "Assets/LabLoadingScene/Plugins/GameAudioOriginalCore.dll",
    "bootstrap": "Assets/LabLoadingScene/Plugins/GameAudioOriginalBootstrap.dll",
    "api": "Assets/LabLoadingScene/Plugins/AK.Wwise.Unity.API.dll",
    "game": "Assets/LabLoadingScene/Plugins/RoR2.dll",
}
META_GUIDS = {
    "observer": "d967d2eae3d34f8491d5a0ce4f5a3e01",
    "core": "2cf769e5a4214cb3ab95ab6b08200d1a",
    "bootstrap": "5114289274f246cfad71a6ac7a86a154",
}
NATIVE_META_GUID = "a2a09e81876b46f2a202e62f96644331"
NATIVE_TARGET = "Assets/Plugins/Android/arm64-v8a/libAkSoundEngine.so"
NATIVE_META = "Assets/Plugins/Android/arm64-v8a/libAkSoundEngine.so.meta"
OWNER_ANCESTOR_MANIFEST_SHA256 = "e9a69907676fa02bdeb544b4e711844230578532de38dd812984e70da72d5cc5"
STAGE_PIN_TOOL_SHA256 = "82e9a3dd9ab6057d2fba086337504bc3381f289e13fe29403d3825f0b99e13ce"
REQUEST_PIN_TOOL_SHA256 = "b60ff6013a1e6cecf2e730cdc29a57d5b36e8228a5134c35fce028ed471d5113"
MANAGED_PRODUCER_SHA256 = "12c1aaed5fca694657c2c841c57e6ead399352e58b1cd0e7662dec75e2749421"
ABI_NATIVE_PLUGIN_SHA256 = "cfec01cb3aab87edbde3db38e3c0bbe6a1d18ffea2a1f831a59cf64a5526daca"
ABI_GENERATED_SOURCE_SHA256 = "511f5e1ee552a874850a1fab5f613eeb51e7b6bc706a07bb57418c03e75df242"
ABI_HANDWRITTEN_SOURCE_SHA256 = "7cc79d60937708fd9f34fd67e90a743fe9e03e58c2325bf0f9e9dbbf8be327e6"
ABI_LLVM_NM_SHA256 = "6ffe6bb8699a354c4699a6cdfcebdb9ec6a2c8d0d89beaac978f629a0fc67ae0"
OWNER_SOURCE_HASHES = {
    "../../runtime/session/OriginalMusicControllerContract.cs": "5ce24197048654448e3a5444b883339c86777754521cb638b461399291833212",
    "../../runtime/session/PortSession.cs": "233e40b41b02aa601d110db38bdb738ed35438a91131823d609a2909719e6731",
    "../../runtime/session/PortSessionOriginalAudioOwner.cs": "1c9d79ee1e407c3ad08143722855393dc580565fc7cbef8732a9b6a018161436",
    "../../runtime/session/PortSessionOriginalMusicControllerOwner.cs": "ff15495def16260f11aeea15e2f18509d79091ebb0e57bb6580bf07d672e7304",
    "bootstrap/GameAudioOriginalAcceptedRequestProvider.cs": "72e2fc997ad80ee3e86cee428c3857b7be035070483007b24d929039aa0aa7e1",
    "bootstrap/GameAudioOriginalAndroidNativeBootstrap.cs": "bea349d5c344f43293abeca65508790971305e4d38c60050fc956fa956205d20",
    "bootstrap/GameAudioOriginalGeneratedRequestPin.cs": "24e560195c4350aefe717b3acbc78697871effa88b70e23be07225c6487545d4",
    "bootstrap/GameAudioOriginalGeneratedStagePin.cs": "d54d445d05712432559a5e332457af0b20200c93895bd79374c42b6280bd07a4",
    "bootstrap/GameAudioOriginalPayloadCopy.cs": "1be21165d6ad8b1df1ab7513016da6ad78ad62350977550c376179f44f48e05f",
    "bootstrap/GameAudioOriginalPreparation.cs": "9894781b7ff0b5cde30b4b67ad0fb9f65a037ba0c124a086fe562c181fa41168",
    "bootstrap/GameAudioOriginalRequestBootstrap.cs": "faff62d15e6b1828a814a55af4a9a25d04b315ba5c462cb4bf6c34f569e8657c",
    "bootstrap/NativeWwiseMonitorLease.cs": "79b234526c893902474bf84317638724ae62b440e2395b4451d55f12ec877e72",
    "bootstrap/OriginalGameAudioPassivePcmOwner.cs": "455ee0b6626c890ace15cd6cdff34ee6b6afa506a5f03ee7ed23c89c21f1f42d",
    "bootstrap/PassivePcmCaptureWindow.cs": "dff4ec06fb252bcd3c1eb60ee80c69050411af026a62047133e6e8939525e99c",
    "core/GameAudioOriginalOwner.cs": "66fc16c9948089a09c77ada50a2eaa5a39f917cf943b5357971c73dae0b0e3c6",
    "core/GameAudioOriginalPassivePcmContract.cs": "76a1d54f1b679ce1ed160203196ecc2c589d71b081070e3b1dac3517f0e7978d",
    "core/GameAudioOriginalReadiness.cs": "ab7be883932ce975615676882440c74d43b039fce067a9cab0572d7198c4db19",
    "core/OriginalOwnerProbeObserver.cs": "7a95cfbf3528eaad15a2efe188b896fd1e925a3e5dfa5809d8f7ef5c44d856d8",
    "core/PointSoundDiagnosticObserver.cs": "ebd0b2c0089150c4302c00824ee32e7a8e8b1906f26ad2137bdb0cee4cf1b4c7",
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def reject_symlink_components(path: Path) -> None:
    absolute = Path(os.path.abspath(path))
    cursor = Path(absolute.anchor)
    for part in absolute.parts[1:]:
        cursor /= part
        if cursor.exists() and cursor.is_symlink():
            raise ValueError(f"symlink path component refused: {cursor}")


def validate_owner_source_manifest() -> None:
    """Bind both compile modes to the public owner cohort recipe."""
    manifest = ROOT / "recipe/original-audio-owner-sources.json"
    reject_symlink_components(manifest)
    if not manifest.is_file() or sha256(manifest) != OWNER_ANCESTOR_MANIFEST_SHA256:
        raise ValueError("owner source recipe differs from pinned manifest")
    data = json.loads(manifest.read_text(encoding="utf-8"))
    if data.get("owner_source_hashes") != OWNER_SOURCE_HASHES:
        raise ValueError("owner source recipe differs from producer cohort")


def validate_toolchain(project: Path, unity_contents: Path, mono: Path, csc: Path) -> dict:
    toolchain = json.loads((ROOT / "environment/toolchain.json").read_text(encoding="utf-8"))
    project_version = (project / "ProjectSettings/ProjectVersion.txt").read_text(encoding="utf-8")
    info = plistlib.loads((unity_contents / "Info.plist").read_bytes())
    expected_version = toolchain["unity_version"]
    expected_revision = toolchain["unity_revision"]
    if expected_version != "2021.3.45f2" or expected_revision != "88f88f591b2e":
        raise ValueError("tracked Unity toolchain pin changed; requalify this producer")
    if info.get("CFBundleVersion") != expected_version or info.get("UnityBuildNumber") != expected_revision or f"({expected_revision})" not in project_version:
        raise ValueError("project or exact Unity installation differs from pinned version/revision")
    if platform.machine() not in ("arm64", "aarch64"):
        raise ValueError("Unity host architecture differs from pinned macOS ARM64")
    expected_mono = unity_contents / "MonoBleedingEdge/bin/mono"
    expected_csc = unity_contents / "MonoBleedingEdge/lib/mono/msbuild/Current/bin/Roslyn/csc.exe"
    if mono.resolve(strict=True) != expected_mono.resolve(strict=True) or csc.resolve(strict=True) != expected_csc.resolve(strict=True):
        raise ValueError("Mono/Roslyn must come from this pinned Unity installation")
    cecil = unity_contents / "MonoBleedingEdge/lib/mono/gac/Mono.Cecil/0.11.1.0__0738eb9f132ed756/Mono.Cecil.dll"
    cecil_hash = sha256(cecil)
    if cecil_hash != json.loads((ROOT / "recipe/assembly-transforms.json").read_text())["cecil_sha256"]:
        raise ValueError("Unity Cecil differs from the pinned assembly transform tool")
    return {
        "unity_version": expected_version,
        "unity_revision": expected_revision,
        "architecture": toolchain["architecture"],
        "mono_sha256": sha256(mono),
        "roslyn_sha256": sha256(csc),
        "unity_executable_sha256": sha256(unity_contents / "MacOS/Unity"),
        "cecil_sha256": cecil_hash,
        "unity_contents": str(unity_contents),
    }


def unity_reference_options(unity_contents: Path, project: Path, plugin_overrides: dict[str, Path] | None = None) -> tuple[list[str], list[Path]]:
    """Derive references from the pinned editor and current migrated plugins."""
    engine = unity_contents / "Managed/UnityEngine"
    framework = unity_contents / "NetStandard/ref/2.1.0"
    shims = unity_contents / "NetStandard/compat/2.1.0/shims"
    if not engine.is_dir() or not framework.is_dir() or not shims.is_dir():
        raise ValueError("pinned Unity Contents lacks the UnityEngine/NetStandard reference roots")
    references = list(
        dict.fromkeys(
            sorted((shims / "netfx").glob("*.dll"))
            + sorted((shims / "netstandard").glob("*.dll"))
            + [framework / "netstandard.dll"]
            + sorted(path for path in engine.glob("*.dll") if not path.name.startswith("UnityEditor"))
        )
    )
    plugin = project / "Assets/LabLoadingScene/Plugins"
    for name in (
        "AK.Wwise.Unity.API.dll",
        "AK.Wwise.Unity.MonoBehaviour.dll",
        "RoR2.dll",
    ):
        path = (plugin_overrides or {}).get(name, plugin / name)
        if path.is_file():
            references.append(path)
    if not references or any(not ref.is_file() or ref.is_symlink() for ref in references):
        raise ValueError("Unity reference set contains a missing or unsafe DLL")
    return ["-langversion:9", "-define:UNITY_ANDROID"] + ["-r:" + str(p) for p in references], references


def classify_project_pair(api_sha256: str, game_sha256: str) -> str:
    """Accept only ordinary, declared predecessor, or current composed inputs."""
    current_pair = (LINEAGE["composed_api_sha256"], LINEAGE["composed_game_sha256"])
    if any(not re.fullmatch(r"[0-9a-f]{64}", value) for value in current_pair):
        raise ValueError("current composed API/game pin is unfilled or invalid")
    predecessor_pair = (PREVIOUS_COMPOSED_API_SHA256, PREVIOUS_COMPOSED_GAME_SHA256)
    if current_pair == predecessor_pair:
        raise ValueError("current composed API/game pair still equals its declared predecessor")
    current_api, current_game = current_pair
    pair = (api_sha256, game_sha256)
    if pair == (DEFAULT_API_SHA256, DEFAULT_GAME_SHA256):
        return "ordinary"
    if pair == current_pair:
        return "current-audio"
    if pair == (PREVIOUS_COMPOSED_API_SHA256, PREVIOUS_COMPOSED_GAME_SHA256):
        return "previous-audio"
    if pair == (PREVIOUS_COMPOSED_API_SHA256, OLDER_PREVIOUS_GAME_SHA256):
        return "older-previous-audio"
    if pair == (OLDER_RESTORE_API_SHA256, OLDER_PREVIOUS_GAME_SHA256):
        return "older-restore-only"
    if pair == (LEGACY_RESTORE_API_SHA256, OLDER_PREVIOUS_GAME_SHA256):
        return "legacy-restore-only"
    raise ValueError("project API/game pair is neither ordinary guarded nor a declared current/previous audio pair")


def run(label: str, command: list[str], log: Path) -> None:
    proc = subprocess.run(
        command,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    log.write_text(proc.stdout, encoding="utf-8")
    if proc.returncode:
        raise RuntimeError(f"{label} failed with exit {proc.returncode}; see {log}")


def compile_library(
    label: str,
    mono: Path,
    csc: Path,
    output: Path,
    sources: list[Path],
    options: list[str],
    extra_refs: list[Path],
    out: Path,
) -> None:
    def quoted(value: str) -> str:
        return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'

    rsp = out / f"{label}.rsp"
    arguments = ["-r:" + quoted(option[3:]) if option.startswith("-r:") else option for option in options]
    rsp.write_text(
        "\n".join(
            arguments
            + ["-r:" + quoted(str(p)) for p in extra_refs]
            + [
                "-target:library",
                "-deterministic+",
                "-pathmap:" + quoted(str(ROOT) + "=/_/ror2lab"),
                "-out:" + quoted(str(output)),
            ]
            + [quoted(str(p)) for p in sources]
        )
        + "\n",
        encoding="utf-8",
    )
    run(label, [str(mono), str(csc), "@" + str(rsp)], out / f"{label}.log")


def compile_default_off(project: Path, unity_contents: Path, mono: Path, csc: Path, output: Path) -> dict:
    """Compile only the named owner cohort against ordinary guarded outputs."""
    validate_owner_source_manifest()
    for relative, expected in OWNER_SOURCE_HASHES.items():
        source = SOURCE / relative
        if not source.is_file() or source.is_symlink() or sha256(source) != expected:
            raise ValueError(f"integrated owner source differs from frozen R7 input: {relative}")
    toolchain = validate_toolchain(project, unity_contents, mono, csc)
    reject_symlink_components(output)
    if output.exists() or output.is_symlink() or not output.resolve(strict=False).is_relative_to((ROOT / "work").resolve()):
        raise ValueError("artifact output must be a fresh directory under ignored work/")
    output.mkdir(parents=True)
    plugin = project / "Assets/LabLoadingScene/Plugins"
    api = plugin / "AK.Wwise.Unity.API.dll"
    game = plugin / "RoR2.dll"
    project_api_sha = sha256(api)
    project_game_sha = sha256(game)
    pair_kind = classify_project_pair(project_api_sha, project_game_sha)
    audio_variant = pair_kind in {
        "previous-audio",
        "previous-audio-restore-only",
        "older-restore-only",
        "current-audio",
        "legacy-restore-only",
    }
    restored = rebuild_ordinary_assemblies(project, unity_contents, output) if audio_variant else {}
    if audio_variant and (sha256(restored["AK.Wwise.Unity.API.dll"]) != DEFAULT_API_SHA256 or sha256(restored["RoR2.dll"]) != DEFAULT_GAME_SHA256):
        raise ValueError("replayed migration outputs differ from the exact ordinary guard pins")
    options, references = unity_reference_options(unity_contents, project, restored)
    observer = output / "OriginalOwnerProbeObserver.dll"
    core = output / "GameAudioOriginalCore.dll"
    bootstrap = output / "GameAudioOriginalBootstrap.dll"
    run(
        "compile_observer",
        [
            str(mono),
            str(csc),
            "-target:library",
            "-deterministic+",
            "-out:" + str(observer),
            str(SOURCE / "core/OriginalOwnerProbeObserver.cs"),
        ],
        output / "observer.log",
    )
    point_sound_build_pin = output / "GameAudioOriginalPointSoundBuildPin.cs"
    point_sound_build_pin.write_text(
        "// Default-off artifact: the game assembly has no diagnostic callsites.\n"
        "internal static class GameAudioOriginalPointSoundBuildPin { internal const bool DiagnosticCallsitesPresent = false; }\n",
        encoding="utf-8",
    )
    compile_library(
        "compile_core",
        mono,
        csc,
        core,
        [
            SOURCE / "core/GameAudioOriginalReadiness.cs",
            SOURCE / "core/GameAudioOriginalPassivePcmContract.cs",
            SOURCE / "core/GameAudioOriginalOwner.cs",
            SOURCE / "core/PointSoundDiagnosticObserver.cs",
            point_sound_build_pin,
        ],
        options,
        [observer],
        output,
    )
    bootstrap_sources = sorted((SOURCE / "bootstrap").glob("*.cs"))
    compile_api = restored.get("AK.Wwise.Unity.API.dll", api)
    compile_library(
        "compile_bootstrap",
        mono,
        csc,
        bootstrap,
        bootstrap_sources,
        options,
        [core, compile_api, observer],
        output,
    )
    files = {"observer": observer, "core": core, "bootstrap": bootstrap}
    artifacts = []
    for role, source in files.items():
        artifacts.append(
            {
                "role": role,
                "source": source.name,
                "target": ASSEMBLY_TARGETS[role],
                "sha256": sha256(source),
                "requires_request": False,
            }
        )
        meta = output / (source.name + ".meta")
        meta.write_text(plugin_meta(META_GUIDS[role]), encoding="utf-8")
        artifacts.append(
            {
                "role": "metadata",
                "source": meta.name,
                "target": ASSEMBLY_TARGETS[role] + ".meta",
                "sha256": sha256(meta),
                "requires_request": False,
            }
        )
    if audio_variant:
        for role, source, target, preimage in (
            (
                "restore_api",
                restored["AK.Wwise.Unity.API.dll"],
                ASSEMBLY_TARGETS["api"],
                project_api_sha,
            ),
            (
                "restore_game",
                restored["RoR2.dll"],
                ASSEMBLY_TARGETS["game"],
                project_game_sha,
            ),
        ):
            artifacts.append(
                {
                    "role": role,
                    "source": source.name,
                    "target": target,
                    "sha256": sha256(source),
                    "preimage_sha256": preimage,
                    "requires_request": False,
                }
            )
    manifest = {
        "schema": "original-game-audio-artifact-set-r1",
        "accepted_input_id": LINEAGE["accepted_input_id"],
        "owner_ancestor_manifest_sha256": OWNER_ANCESTOR_MANIFEST_SHA256,
        "owner_source_hashes": OWNER_SOURCE_HASHES,
        "lineage": LINEAGE,
        "artifact_set_id": hashlib.sha256(
            (sha256(observer) + sha256(core) + sha256(bootstrap) + "\n".join(sha256(path) for path in references)).encode()
        ).hexdigest(),
        "variant": "default-off",
        "request": {
            "requested": False,
            "request_id": None,
            "build_input_contract_sha256": None,
            "passive_pcm_capture_requested": False,
        },
        "outputs": artifacts,
        "runtime_accepted": False,
        "audible": False,
    }
    manifest_path = output / "artifact-manifest.json"
    manifest_path.write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return {
        "variant": "default-off",
        "project_api_sha256": project_api_sha,
        "project_game_sha256": project_game_sha,
        "returned_to_ordinary_guard": audio_variant,
        "unity_contents": str(unity_contents),
        "toolchain": toolchain,
        "unity_reference_hashes": {
            str(path.relative_to(unity_contents)) if path.is_relative_to(unity_contents) else path.name: sha256(path) for path in references
        },
        "reference_count": len(references),
        "outputs": {
            "observer": sha256(observer),
            "core": sha256(core),
            "bootstrap": sha256(bootstrap),
        },
        "files": {
            "observer": str(observer),
            "core": str(core),
            "bootstrap": str(bootstrap),
            "manifest": str(manifest_path),
        },
        "runtime_accepted": False,
        "audible": False,
    }


def compile_requested(
    project: Path,
    unity_contents: Path,
    mono: Path,
    csc: Path,
    dotnet: Path,
    managed_producer: Path,
    android_source: Path,
    android_os_string_source: Path,
    native_library: Path,
    abi_native_plugin: Path,
    llvm_nm: Path,
    request_path: Path | None,
    input_contract_path: Path | None,
    stage_receipt_path: Path,
    stage_root: Path,
    prefab: Path,
    bank_index: Path,
    adapted_init: Path,
    init_receipt: Path,
    output: Path,
    request_id: str | None = None,
    passive_pcm_capture_requested: bool = False,
) -> dict:
    """Generate, compile and describe one explicit requested artifact set.

    The managed producer owns the accepted API/game transform chain. This
    adapter owns the request-derived Bootstrap sources, Unity compilation,
    and the complete hash-checked staging manifest.
    """
    validate_owner_source_manifest()
    for relative, expected in OWNER_SOURCE_HASHES.items():
        source = SOURCE / relative
        if not source.is_file() or source.is_symlink() or sha256(source) != expected:
            raise ValueError(f"integrated owner source differs from frozen R7 input: {relative}")
    project_plugin = project / "Assets/LabLoadingScene/Plugins"
    pair_kind = classify_project_pair(
        sha256(project_plugin / "AK.Wwise.Unity.API.dll"),
        sha256(project_plugin / "RoR2.dll"),
    )
    if pair_kind in {
        "legacy-restore-only",
        "older-restore-only",
        "previous-audio-restore-only",
    }:
        raise ValueError("declared predecessor API lineage is restore-only; restore default-off before requesting audio")
    toolchain = validate_toolchain(project, unity_contents, mono, csc)
    for label, path in (
        ("Android generated source", android_source),
        ("Android handwritten source", android_os_string_source),
        ("native ARM64 library", native_library),
        ("Android ABI reference native plugin", abi_native_plugin),
        ("stage receipt", stage_receipt_path),
        ("stage root", stage_root),
        ("accepted Wwise Global prefab", prefab),
        ("accepted bank index", bank_index),
        ("adapted Init", adapted_init),
        ("Init adaptation receipt", init_receipt),
    ):
        resolved = path.resolve(strict=True)
        if path.is_symlink() or not resolved.is_relative_to((ROOT / "work").resolve()):
            raise ValueError(f"{label} must be an explicit non-symlink input under work/")
        if label != "stage root" and not resolved.is_file():
            raise ValueError(f"{label} must be a regular file")
        if label == "stage root" and not resolved.is_dir():
            raise ValueError("stage root must be a directory")
    if sha256(managed_producer) != MANAGED_PRODUCER_SHA256:
        raise ValueError("managed transform producer differs from the reviewed authored source")
    editor_path = (unity_contents / "MacOS/Unity").resolve(strict=True)
    ndk_root = editor_path.parent.parent.parent.parent / "PlaybackEngines/AndroidPlayer/NDK"
    expected_llvm_nm = ndk_root / "toolchains/llvm/prebuilt/darwin-x86_64/bin/llvm-nm"
    if llvm_nm.resolve(strict=True) != expected_llvm_nm.resolve(strict=True) or not os.access(llvm_nm, os.X_OK):
        raise ValueError("llvm-nm must be the executable from the pinned Unity Android NDK")
    if sha256(native_library) != LINEAGE["native_library_sha256"]:
        raise ValueError("native library differs from the exact accepted ARM64 pin")
    if sha256(abi_native_plugin) != ABI_NATIVE_PLUGIN_SHA256:
        raise ValueError("Android ABI reference plugin differs from its exact accepted pin")
    reject_symlink_components(output)
    if output.exists() or output.is_symlink() or not output.resolve(strict=False).is_relative_to((ROOT / "work").resolve()):
        raise ValueError("artifact output must be a fresh directory under ignored work/")
    output.mkdir(parents=True)

    managed_output = output / "managed-chain"
    # The API producer is a separately authored deterministic transform
    # chain. Its manifest is verified below before any generated output is used.
    run(
        "managed_transform_chain",
        [
            sys.executable,
            str(managed_producer),
            "--android-source",
            str(android_source),
            "--android-os-string-source",
            str(android_os_string_source),
            "--native-so",
            str(abi_native_plugin),
            "--llvm-nm",
            str(llvm_nm),
            "--unity-editor",
            str(unity_contents / "MacOS/Unity"),
            "--dotnet",
            str(dotnet),
            "--output-dir",
            str(managed_output),
        ],
        output / "managed-chain.log",
    )
    managed_manifest_path = managed_output / "manifest.json"
    managed_manifest = json.loads(managed_manifest_path.read_text(encoding="utf-8"))
    abi_inputs = managed_manifest.get("android_abi_input_hashes")
    expected_abi_inputs = {
        "arm64_release_native_plugin": ABI_NATIVE_PLUGIN_SHA256,
        "generated_android_source": ABI_GENERATED_SOURCE_SHA256,
        "handwritten_android_source": ABI_HANDWRITTEN_SOURCE_SHA256,
        "llvm_nm": ABI_LLVM_NM_SHA256,
    }
    if abi_inputs != expected_abi_inputs:
        raise ValueError("managed chain was not generated from the exact ABI policy inputs")
    managed_paths = verify_managed_output_manifest(managed_manifest, (ROOT / "work").resolve(strict=True))
    composed_api = next(path for key, path in managed_paths.items() if Path(key).name == "api-instrumented-composed.dll")
    composed_game = next(path for key, path in managed_paths.items() if Path(key).name == "game-original-owner-point-sound-composed.dll")

    stage_pin_tool = TOOLS / "generate_runtime_stage_pin.py"
    request_pin_tool = TOOLS / "generate_accepted_request_pin.py"
    if sha256(stage_pin_tool) != STAGE_PIN_TOOL_SHA256 or sha256(request_pin_tool) != REQUEST_PIN_TOOL_SHA256:
        raise ValueError("request/stage source generators differ from the frozen R5 adapters")
    stage_generator = load_module(stage_pin_tool, "audio_stage_pin")
    request_generator = load_module(request_pin_tool, "audio_request_pin")
    generated = output / "generated"
    generated.mkdir()
    if (request_path is None) != (input_contract_path is None):
        raise ValueError("request and input contract must be supplied together")
    if request_path is None:
        if not isinstance(request_id, str) or not re.fullmatch(r"[0-9a-f]{32}", request_id):
            raise ValueError("generated request requires a compact UUID from explicit opt-in selection")
        request_path, input_contract_path = generate_request_contract(
            output,
            generated,
            request_id,
            managed_manifest,
            managed_paths,
            native_library,
            stage_receipt_path,
            stage_root,
            prefab,
            bank_index,
            adapted_init,
            init_receipt,
            passive_pcm_capture_requested,
        )
    assert request_path is not None and input_contract_path is not None
    for label, path in (
        ("request", request_path),
        ("input contract", input_contract_path),
    ):
        resolved = path.resolve(strict=True)
        if path.is_symlink() or not resolved.is_relative_to((ROOT / "work").resolve()) or not resolved.is_file():
            raise ValueError(f"{label} must be an explicit regular file under work/")
    stage_source = generated / "GameAudioOriginalGeneratedStagePin.cs"
    stage_result = stage_generator.generate(
        stage_receipt_path,
        stage_root,
        stage_source,
        prefab,
        bank_index,
        adapted_init,
        init_receipt,
    )
    request_source = generated / "GameAudioOriginalGeneratedRequestPin.cs"
    request_result = request_generator.emit(request_path, input_contract_path, stage_receipt_path, request_source)
    request_document = json.loads(request_path.read_text(encoding="utf-8"))
    if request_document.get("requested") is not True:
        raise ValueError("requested producer requires an explicit request with requested=true")
    if (
        type(request_document.get("passive_pcm_capture_requested")) is not bool
        or request_document["passive_pcm_capture_requested"] != passive_pcm_capture_requested
    ):
        raise ValueError("passive PCM selection must be an explicit boolean bound by the request and invocation")
    if sha256(native_library) != request_document.get("native_library_sha256"):
        raise ValueError("explicit native input differs from request pin")

    plugin = project / "Assets/LabLoadingScene/Plugins"
    current_api = plugin / "AK.Wwise.Unity.API.dll"
    current_game = plugin / "RoR2.dll"
    current_api_sha = sha256(current_api)
    current_game_sha = sha256(current_game)
    pair_kind = classify_project_pair(current_api_sha, current_game_sha)
    if pair_kind in {"legacy-restore-only", "older-restore-only"}:
        raise ValueError("declared older API lineage is restore-only; restore default-off before requesting audio")
    core_api = next(path for key, path in managed_paths.items() if Path(key).name == "api-adapted.dll")
    guarded_game = next(path for key, path in managed_paths.items() if Path(key).name == "game-optional-presentation-guarded.dll")
    core_options, core_references = unity_reference_options(
        unity_contents,
        project,
        {"AK.Wwise.Unity.API.dll": core_api, "RoR2.dll": guarded_game},
    )
    bootstrap_options, bootstrap_references = unity_reference_options(
        unity_contents,
        project,
        {"AK.Wwise.Unity.API.dll": composed_api, "RoR2.dll": composed_game},
    )
    observer = output / "OriginalOwnerProbeObserver.dll"
    core = output / "GameAudioOriginalCore.dll"
    bootstrap = output / "GameAudioOriginalBootstrap.dll"
    run(
        "compile_observer",
        [
            str(mono),
            str(csc),
            "-target:library",
            "-deterministic+",
            "-out:" + str(observer),
            str(SOURCE / "core/OriginalOwnerProbeObserver.cs"),
        ],
        output / "observer.log",
    )
    point_sound_build_pin = output / "GameAudioOriginalPointSoundBuildPin.cs"
    point_sound_build_pin.write_text(
        "// Requested artifact: the paired RoR2.dll contains the bounded diagnostic callsites.\n"
        "internal static class GameAudioOriginalPointSoundBuildPin { internal const bool DiagnosticCallsitesPresent = true; }\n",
        encoding="utf-8",
    )
    compile_library(
        "compile_core",
        mono,
        csc,
        core,
        [
            SOURCE / "core/GameAudioOriginalReadiness.cs",
            SOURCE / "core/GameAudioOriginalPassivePcmContract.cs",
            SOURCE / "core/GameAudioOriginalOwner.cs",
            SOURCE / "core/PointSoundDiagnosticObserver.cs",
            point_sound_build_pin,
        ],
        core_options,
        [observer],
        output,
    )
    bootstrap_sources = [
        path
        for path in sorted((SOURCE / "bootstrap").glob("*.cs"))
        if path.name
        not in {
            "GameAudioOriginalGeneratedRequestPin.cs",
            "GameAudioOriginalGeneratedStagePin.cs",
        }
    ] + [request_source, stage_source]
    compile_library(
        "compile_bootstrap",
        mono,
        csc,
        bootstrap,
        bootstrap_sources,
        bootstrap_options,
        [core, composed_api, observer],
        output,
    )

    meta_files = {
        "observer": output / (observer.name + ".meta"),
        "core": output / (core.name + ".meta"),
        "bootstrap": output / (bootstrap.name + ".meta"),
        "native": output / (Path(native_library).name + ".meta"),
    }
    for role in ("observer", "core", "bootstrap"):
        meta_files[role].write_text(plugin_meta(META_GUIDS[role]), encoding="utf-8")
    meta_files["native"].write_text(native_plugin_meta(NATIVE_META_GUID), encoding="utf-8")

    outputs = []
    for role, source, target in (
        ("observer", observer, ASSEMBLY_TARGETS["observer"]),
        ("core", core, ASSEMBLY_TARGETS["core"]),
        ("bootstrap", bootstrap, ASSEMBLY_TARGETS["bootstrap"]),
        ("api", composed_api, ASSEMBLY_TARGETS["api"]),
        ("game", composed_game, ASSEMBLY_TARGETS["game"]),
    ):
        row = {
            "role": role,
            "source": str(source.relative_to(ROOT / "work")),
            "target": target,
            "sha256": sha256(source),
            "requires_request": role in {"api", "game"},
        }
        if role in {"api", "game"}:
            row["preimage_sha256"] = current_api_sha if role == "api" else current_game_sha
        outputs.append(row)
    outputs.append(
        {
            "role": "native",
            "source": str(native_library.relative_to(ROOT / "work")),
            "target": NATIVE_TARGET,
            "sha256": sha256(native_library),
            "requires_request": True,
        }
    )
    for role, source, target in (
        ("observer", meta_files["observer"], ASSEMBLY_TARGETS["observer"] + ".meta"),
        ("core", meta_files["core"], ASSEMBLY_TARGETS["core"] + ".meta"),
        ("bootstrap", meta_files["bootstrap"], ASSEMBLY_TARGETS["bootstrap"] + ".meta"),
        ("native", meta_files["native"], NATIVE_META),
    ):
        outputs.append(
            {
                "role": "metadata",
                "source": str(source.relative_to(ROOT / "work")),
                "target": target,
                "sha256": sha256(source),
                "requires_request": True,
            }
        )
    outputs[-4:-1] = [{**row, "requires_request": False} for row in outputs[-4:-1]]
    stage_document = json.loads(stage_receipt_path.read_text(encoding="utf-8"))
    for row in stage_document["outputs"]:
        bank_path = stage_root / stage_document["output_relative_directory"] / row["filename"]
        if not bank_path.is_file() or bank_path.is_symlink() or sha256(bank_path) != row["sha256"]:
            raise ValueError(f"stage payload bytes fail receipt validation: {row['filename']}")
        outputs.append(
            {
                "role": "banks",
                "source": str(bank_path.resolve().relative_to(ROOT / "work")),
                "target": "Assets/StreamingAssets/" + stage_document["output_relative_directory"] + "/" + row["filename"],
                "sha256": row["sha256"],
                "filename": row["filename"],
                "size_bytes": row["size_bytes"],
                "requires_request": True,
            }
        )
    outputs.append(
        {
            "role": "bank_receipt",
            "source": str(stage_receipt_path.resolve().relative_to(ROOT / "work")),
            "target": "Assets/StreamingAssets/stage-receipt.json",
            "sha256": sha256(stage_receipt_path),
            "requires_request": True,
        }
    )
    manifest = {
        "schema": "original-game-audio-artifact-set-r1",
        "accepted_input_id": LINEAGE["accepted_input_id"],
        "owner_ancestor_manifest_sha256": OWNER_ANCESTOR_MANIFEST_SHA256,
        "owner_source_hashes": OWNER_SOURCE_HASHES,
        "request_provenance": {
            "managed_manifest_sha256": sha256(managed_manifest_path),
            "managed_producer_sha256": sha256(managed_producer),
            "request_pin_generator_sha256": REQUEST_PIN_TOOL_SHA256,
            "stage_pin_generator_sha256": STAGE_PIN_TOOL_SHA256,
        },
        "lineage": LINEAGE,
        "artifact_set_id": hashlib.sha256(
            (request_result["source_sha256"] + stage_result["source_sha256"] + "\n".join(row["sha256"] for row in outputs)).encode()
        ).hexdigest(),
        "source_root": ".",
        "variant": "requested",
        "request": {
            "requested": True,
            "request_id": request_document["request_id"],
            "build_input_contract_sha256": request_result["build_input_contract_sha256"],
            "passive_pcm_capture_requested": passive_pcm_capture_requested,
        },
        "outputs": outputs,
        "runtime_accepted": False,
        "audible": False,
    }
    manifest_path = output / "artifact-manifest.json"
    manifest_path.write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return {
        "variant": "requested",
        "toolchain": toolchain,
        "request_id": request_document["request_id"],
        "request_sha256": sha256(request_path),
        "contract_sha256": request_result["build_input_contract_sha256"],
        "stage_receipt_sha256": stage_result["receipt_sha256"],
        "managed_manifest_sha256": sha256(managed_manifest_path),
        "compiled": {
            "observer": sha256(observer),
            "core": sha256(core),
            "bootstrap": sha256(bootstrap),
        },
        "manifest_sha256": sha256(manifest_path),
        "manifest_path": str(manifest_path),
        "runtime_accepted": False,
        "audible": False,
    }


def verify_managed_output_manifest(manifest: dict, work_root: Path) -> dict[str, Path]:
    if (
        manifest.get("schema") != "game-audio-original-public-producer-r1"
        or manifest.get("accepted_input_id") != LINEAGE["accepted_input_id"]
        or manifest.get("request") != {"requested": False, "stage_to_apk_binding": False, "dispatch_ready": False}
    ):
        raise ValueError("managed transform producer returned an unexpected manifest or non-default request state")
    if manifest.get("android_abi_input_hashes") != {
        "arm64_release_native_plugin": ABI_NATIVE_PLUGIN_SHA256,
        "generated_android_source": ABI_GENERATED_SOURCE_SHA256,
        "handwritten_android_source": ABI_HANDWRITTEN_SOURCE_SHA256,
        "llvm_nm": ABI_LLVM_NM_SHA256,
    }:
        raise ValueError("managed transform manifest differs from the exact Android ABI inputs")
    expected = {
        "raw_game": LINEAGE["accepted_game_sha256"],
        "raw_api": LINEAGE["raw_api_sha256"],
        "adapted_api": LINEAGE["adapted_api_sha256"],
        "observed_api": LINEAGE["observed_api_sha256"],
        "composed_api": LINEAGE["composed_api_sha256"],
        "guarded_game": LINEAGE["guarded_game_input_sha256"],
        "composed_game": OLDER_PREVIOUS_GAME_SHA256,
        "point_sound_composed_game": LINEAGE["composed_game_sha256"],
    }
    source_hashes = manifest.get("source_input_hashes")
    if not isinstance(source_hashes, dict) or any(source_hashes.get(key) != value for key, value in expected.items()):
        raise ValueError("managed transform producer input/output hashes differ from the accepted chain")
    files = manifest.get("outputs_relative_to_work")
    if not isinstance(files, dict) or not files:
        raise ValueError("managed transform manifest lacks its work-relative output inventory")
    work_root = work_root.resolve(strict=True)
    paths: dict[str, Path] = {}
    output_names: list[str] = []
    for key, digest in files.items():
        relative = Path(key)
        if relative.is_absolute() or any(part in ("", ".", "..") for part in relative.parts) or "\\" in key:
            raise ValueError("managed transform manifest contains an unsafe output path")
        lexical = work_root / relative
        reject_symlink_components(lexical)
        path = lexical.resolve(strict=True)
        if not path.is_relative_to(work_root) or not path.is_file() or sha256(path) != digest:
            raise ValueError(f"managed transform output failed its manifest hash: {key}")
        paths[key] = path
        output_names.append(Path(key).name)
    required_outputs = {
        "api-adapted.dll",
        "api-observed.dll",
        "api-instrumented-composed.dll",
        "game-optional-presentation-guarded.dll",
        "game-original-owner-composed.dll",
        "game-original-owner-point-sound-composed.dll",
    }
    if not required_outputs.issubset(output_names):
        raise ValueError("managed transform manifest omits a required intermediate in the accepted chain")
    for filename, expected_sha in (
        ("api-instrumented-composed.dll", LINEAGE["composed_api_sha256"]),
        ("game-original-owner-composed.dll", OLDER_PREVIOUS_GAME_SHA256),
        (
            "game-original-owner-point-sound-composed.dll",
            LINEAGE["composed_game_sha256"],
        ),
    ):
        matches = [path for key, path in paths.items() if Path(key).name == filename]
        if len(matches) != 1 or sha256(matches[0]) != expected_sha:
            raise ValueError(f"managed transform output is absent or differs from accepted pin: {filename}")
    return paths


def generate_request_contract(
    output: Path,
    generated: Path,
    request_id: str,
    managed_manifest: dict,
    managed_paths: dict[str, Path],
    native_library: Path,
    stage_receipt_path: Path,
    stage_root: Path,
    prefab: Path,
    bank_index: Path,
    adapted_init: Path,
    init_receipt: Path,
    passive_pcm_capture_requested: bool = False,
) -> tuple[Path, Path]:
    """Create the pre-derivative input contract and same-build request.

    The contract pins its complete pre-bootstrap source set. The request then
    binds the contract and stage receipt; neither document includes its own
    hash, avoiding a circular digest dependency.
    """
    if not re.fullmatch(r"[0-9a-f]{32}", request_id):
        raise ValueError("request identity must be compact lowercase UUID hex")
    local = json.loads((ROOT / "work/config/local.json").read_text(encoding="utf-8"))
    game_root = Path(local["game_path"]).expanduser().resolve(strict=True)
    managed_root = game_root / "Risk of Rain 2_Data/Managed"
    raw_game = managed_root / "RoR2.dll"
    raw_api = managed_root / "AK.Wwise.Unity.API.dll"
    copied_root = generated / "contract-inputs"
    copied_root.mkdir()
    copied_game = copied_root / "accepted-RoR2.dll"
    copied_api = copied_root / "accepted-AK.Wwise.Unity.API.dll"
    for source, destination, expected, label in (
        (
            raw_game,
            copied_game,
            LINEAGE["accepted_game_sha256"],
            "accepted game assembly",
        ),
        (raw_api, copied_api, LINEAGE["raw_api_sha256"], "accepted raw API assembly"),
    ):
        if source.is_symlink() or not source.is_file() or sha256(source) != expected:
            raise ValueError(f"{label} differs from the exact accepted source")
        shutil.copyfile(source, destination)
        if sha256(destination) != expected:
            raise ValueError(f"{label} work snapshot failed its copy hash")

    stage_doc = json.loads(stage_receipt_path.read_text(encoding="utf-8"))
    stage_names = {row.get("filename"): row for row in stage_doc.get("outputs", []) if isinstance(row, dict)}
    if "Global.bnk" not in stage_names or "Init.bnk" not in stage_names:
        raise ValueError("accepted stage receipt must include the Global and Init contract members")
    global_path = stage_root / stage_doc["output_relative_directory"] / "Global.bnk"
    adapted_init_path = stage_root / stage_doc["output_relative_directory"] / "Init.bnk"
    if sha256(global_path) != stage_names["Global.bnk"].get("sha256") or sha256(adapted_init_path) != stage_names["Init.bnk"].get("sha256"):
        raise ValueError("Global/Init work payload differs from the explicit accepted stage receipt")
    named = {Path(key).name: path for key, path in managed_paths.items()}
    members = {
        "game_assembly_sha256": copied_game,
        "composed_game_sha256": next(path for key, path in managed_paths.items() if Path(key).name == "game-original-owner-point-sound-composed.dll"),
        "raw_api_sha256": copied_api,
        "adapted_api_sha256": named["api-adapted.dll"],
        "observed_api_sha256": named["api-observed.dll"],
        "instrumented_api_sha256": named["api-instrumented-composed.dll"],
        "native_library_sha256": native_library,
        "current_bank_index_sha256": bank_index,
        "wwise_global_prefab_sha256": prefab,
        "init_adaptation_receipt_sha256": init_receipt,
        "global_accepted_original_sha256": global_path,
        "adapted_init_sha256": adapted_init,
    }
    request_generator = load_module(TOOLS / "generate_accepted_request_pin.py", "audio_request_pin_contract")
    expected = request_generator.EXPECTED
    rows = []
    work_root = (ROOT / "work").resolve(strict=True)
    for role, path in members.items():
        resolved = path.resolve(strict=True)
        if path.is_symlink() or not resolved.is_file() or not resolved.is_relative_to(work_root):
            raise ValueError(f"contract member must be a regular work/ file: {role}")
        digest = sha256(resolved)
        if digest != expected[role]:
            raise ValueError(f"contract source does not match accepted input pin: {role}")
        rows.append(
            {
                "role": role,
                "path": resolved.relative_to(work_root).as_posix(),
                "sha256": digest,
            }
        )
    contract = {
        "schema": request_generator.CONTRACT_SCHEMA,
        "accepted_input_id": LINEAGE["accepted_input_id"],
        "inputs": rows,
    }
    contract_path = generated / "build-input-contract.json"
    contract_bytes = (json.dumps(contract, sort_keys=True, indent=2) + "\n").encode()
    contract_path.write_bytes(contract_bytes)
    contract_sha = hashlib.sha256(contract_bytes).hexdigest()
    request = {
        "schema": "game-audio-original-runtime-request-r3",
        "requested": True,
        "passive_pcm_capture_requested": bool(passive_pcm_capture_requested),
        "request_id": request_id,
        "build_input_contract_sha256": contract_sha,
        "stage_receipt_sha256": sha256(stage_receipt_path),
        **expected,
    }
    request_path = generated / "request.json"
    request_path.write_text(json.dumps(request, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return request_path, contract_path


def load_module(path: Path, name: str):
    import importlib.util

    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load authored tool: {path.name}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def rebuild_ordinary_assemblies(project: Path, unity_contents: Path, output: Path) -> dict[str, Path]:
    """Replay the tracked migration recipe from the accepted installation."""
    scripts = ROOT / "scripts/lab"
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    import assembly_transforms
    import common

    recipe = assembly_transforms.load_recipe()
    accepted = common.read(ROOT / "work/config/accepted-input.json")
    if accepted.get("input_id") != recipe.get("input_id") or recipe.get("input_id") != LINEAGE["accepted_input_id"]:
        raise ValueError("assembly migration recipe does not bind the current accepted input")
    managed = common.game() / "Risk of Rain 2_Data/Managed"
    with tempfile.TemporaryDirectory(prefix="audio-return-to-off-") as temporary:
        scratch = Path(temporary)
        previous_editor = os.environ.get("UNITY_EDITOR")
        os.environ["UNITY_EDITOR"] = str(unity_contents / "MacOS/Unity")
        try:
            outputs = assembly_transforms.generate(managed, scratch, recipe)
        finally:
            if previous_editor is None:
                os.environ.pop("UNITY_EDITOR", None)
            else:
                os.environ["UNITY_EDITOR"] = previous_editor
        copied = {}
        for name in ("AK.Wwise.Unity.API.dll", "RoR2.dll"):
            target = output / ("ordinary-" + name)
            shutil.copyfile(outputs[name], target)
            copied[name] = target
        # Temporary files are deleted at scope exit, so the stable generated
        # outputs above are copied before cleanup and retain validated hashes.
        return copied


def plugin_meta(guid: str) -> str:
    return (
        "fileFormatVersion: 2\n"
        f"guid: {guid}\n"
        "PluginImporter:\n"
        "  serializedVersion: 2\n"
        "  externalObjects: {}\n"
        "  iconMap: {}\n"
        "  executionOrder: {}\n"
        "  defineConstraints: []\n"
        "  isPreloaded: 0\n"
        "  isOverridable: 0\n"
        "  isExplicitlyReferenced: 0\n"
        "  validateReferences: 0\n"
        "  platformData:\n"
        "  - first:\n"
        "      Any:\n"
        "    second:\n"
        "      enabled: 1\n"
        "      settings: {}\n"
        "  - first:\n"
        "      Editor: Editor\n"
        "    second:\n"
        "      enabled: 0\n"
        "      settings:\n"
        "        DefaultValueInitialized: true\n"
        "  output:\n"
        "    dllType: 0\n"
        "    scriptingRuntimeVersion: 0\n"
        "  userData:\n"
        "  assetBundleName:\n"
        "  assetBundleVariant:\n"
    )


def native_plugin_meta(guid: str) -> str:
    return (
        "fileFormatVersion: 2\n"
        f"guid: {guid}\n"
        "PluginImporter:\n"
        "  externalObjects: {}\n"
        "  serializedVersion: 2\n"
        "  iconMap: {}\n"
        "  executionOrder: {}\n"
        "  defineConstraints: []\n"
        "  isPreloaded: 0\n"
        "  isOverridable: 0\n"
        "  isExplicitlyReferenced: 0\n"
        "  validateReferences: 1\n"
        "  platformData:\n"
        "  - first:\n"
        "      Android: Android\n"
        "    second:\n"
        "      enabled: 1\n"
        "      settings:\n"
        "        CPU: ARM64\n"
        "  - first:\n"
        "      Any: \n"
        "    second:\n"
        "      enabled: 0\n"
        "      settings: {}\n"
        "  - first:\n"
        "      Editor: Editor\n"
        "    second:\n"
        "      enabled: 0\n"
        "      settings:\n"
        "        DefaultValueInitialized: true\n"
        "  userData: \n"
        "  assetBundleName: \n"
        "  assetBundleVariant: \n"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--unity-contents", type=Path, required=True)
    parser.add_argument("--mono", type=Path, required=True)
    parser.add_argument("--csc", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if any(p.is_symlink() or not p.is_file() for p in (args.mono, args.csc)):
        parser.error("Mono and Roslyn must be explicit regular files")
    try:
        result = compile_default_off(
            args.project.resolve(),
            args.unity_contents.resolve(),
            args.mono.resolve(),
            args.csc.resolve(),
            args.output.resolve(),
        )
    except (OSError, ValueError, RuntimeError) as error:
        print(f"audio owner production refused: {error}", file=sys.stderr)
        return 2
    (args.output / "producer-result.json").write_text(json.dumps(result, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
