"""Generate the reviewed native-view camera guard from a pinned RoR2 preimage.

This authored producer accepts only the exact module preimages in the
tracked native-view-camera-transform.json recipe. It writes only a new DLL
under work/. It does not stage a Unity project or run the full player-closure
scanner.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import uuid


def repository_root() -> Path:
    for candidate in Path(__file__).resolve().parents:
        if (candidate / "environment/toolchain.json").is_file() and (candidate / "recipe").is_dir():
            return candidate
    raise RuntimeError("could not locate repository root")


ROOT = repository_root()
SOURCE_ROOT = ROOT
PINS_PATH = ROOT / "recipe/native-view-camera-transform.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def ensure_under_work(path: Path) -> Path:
    lexical = Path(os.path.abspath(path.expanduser()))
    work = (ROOT / "work").resolve()
    if lexical == work or work not in lexical.parents:
        raise RuntimeError("generated output must be below ignored work/")
    cursor = work
    for part in lexical.relative_to(work).parts:
        cursor = cursor / part
        if cursor.is_symlink():
            raise RuntimeError("output path contains a symlink: " + str(cursor))
    resolved = lexical.resolve(strict=False)
    if resolved == work or work not in resolved.parents:
        raise RuntimeError("resolved generated output escapes ignored work/")
    if lexical.exists():
        raise RuntimeError("output must be a new file: " + str(lexical))
    return lexical


def exact_input(profile: str, supplied: Path, project: Path, pins: dict) -> tuple[Path, str]:
    entry = pins["profiles"].get(profile)
    if entry is None:
        raise RuntimeError("unknown exact preimage profile: " + profile)
    project_root = project.resolve(strict=True)
    work = (ROOT / "work").resolve(strict=True)
    if project_root == work or not project_root.is_relative_to(work) or not project_root.is_dir():
        raise RuntimeError("transform project must be a canonical project below ignored work/")
    expected_path = (project_root / entry["input_relative_path"]).resolve(strict=True)
    actual_path = supplied.resolve(strict=True)
    if actual_path != expected_path:
        raise RuntimeError("profile input path mismatch: expected " + str(expected_path))
    actual_hash = sha256(actual_path)
    if actual_hash != entry["input_sha256"]:
        raise RuntimeError("profile input hash mismatch: " + actual_hash)
    return actual_path, actual_hash


def exact_resolution_closure(supplied: Path, pins: dict, profile: str, project: Path, editor_contents: Path) -> tuple[Path, dict]:
    """Verify the deterministic current-project/Unity Cecil resolver snapshot."""
    work = (ROOT / "work").resolve(strict=True)
    lexical = Path(os.path.abspath(supplied.expanduser()))
    if not lexical.is_relative_to(work):
        raise RuntimeError("resolver set must be below ignored work/")
    cursor = work
    for part in lexical.relative_to(work).parts:
        cursor /= part
        if cursor.is_symlink():
            raise RuntimeError("resolver set path contains a symlink")
    actual_dir = lexical.resolve(strict=True)
    if not actual_dir.is_dir() or actual_dir.name != "assemblies":
        raise RuntimeError("resolver directory is not a generated assemblies directory")
    manifest_path = actual_dir.parent / "resolver-set.json"
    if manifest_path.is_symlink() or not manifest_path.is_file():
        raise RuntimeError("resolver set generation receipt is missing or unsafe")
    generation = json.loads(manifest_path.read_text(encoding="utf-8"))
    profile_pin = pins["profiles"][profile]
    api_hash = pins["resolver_profiles"][profile]["api_sha256"]
    rows = generation.get("files", [])
    expected_files = {row.get("path"): row for row in rows if isinstance(row, dict)}
    if (
        generation.get("schema") != "native-view-camera-resolver-set-r2"
        or generation.get("profile") != profile
        or generation.get("input_sha256") != profile_pin["input_sha256"]
        or generation.get("api_sha256") != api_hash
        or generation.get("source_inventory_sha256") != hashlib.sha256(json.dumps(rows, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        or generation.get("count") != len(rows)
        or generation.get("count") != len(expected_files)
    ):
        raise RuntimeError("resolver set receipt differs from exact game/API profile")
    resolver_script = SOURCE_ROOT / pins["source_paths"]["resolver"]
    resolver_spec = __import__("importlib.util", fromlist=["spec_from_file_location"])
    spec = resolver_spec.spec_from_file_location("native_view_camera_resolver", resolver_script)
    if spec is None or spec.loader is None:
        raise RuntimeError("tracked resolver source cannot be loaded")
    resolver_module = resolver_spec.module_from_spec(spec)
    spec.loader.exec_module(resolver_module)
    current_rows = resolver_module.source_rows(project, editor_contents, profile_pin["input_sha256"], api_hash)
    if rows != current_rows:
        raise RuntimeError("resolver manifest does not match current project plugin and pinned Unity/Mono sources")
    actual_dlls = {path.name for path in actual_dir.glob("*.dll") if path.is_file() and not path.is_symlink()}
    if actual_dlls != set(expected_files):
        raise RuntimeError("resolver set DLL membership drift")
    for name, row in expected_files.items():
        path = actual_dir / name
        if path.stat().st_size != row.get("size") or sha256(path) != row.get("sha256"):
            raise RuntimeError("resolver set DLL drift: " + str(name))
    if expected_files.get("RoR2.dll", {}).get("sha256") != profile_pin["input_sha256"]:
        raise RuntimeError("resolver set is not bound to the exact camera input RoR2.dll")
    if expected_files.get("AK.Wwise.Unity.API.dll", {}).get("sha256") != api_hash:
        raise RuntimeError("resolver set is not bound to the exact profile API DLL")
    return actual_dir, generation


def exact_audio_resolver_overlay(supplied: Path | None, profile: str, pins: dict) -> tuple[Path | None, str | None]:
    if supplied is not None:
        raise RuntimeError("camera transform accepts one exact resolver set, not an audio overlay")
    return None, None


def pinned_editor(pins: dict) -> tuple[Path, dict[str, Path]]:
    editor_binary = Path(os.environ.get("UNITY_EDITOR", "")).expanduser()
    if not editor_binary.is_absolute() or not editor_binary.is_file():
        raise RuntimeError("UNITY_EDITOR must name the pinned local Unity executable")
    contents = editor_binary.resolve().parent.parent
    expected_version = json.loads((ROOT / "environment/toolchain.json").read_text())["unity_version"]
    if len(contents.parents) < 2 or contents.parents[1].name != expected_version or contents.name != "Contents":
        raise RuntimeError("UNITY_EDITOR does not match environment/toolchain.json")
    paths = {
        "mcs": contents / "MonoBleedingEdge/bin/mcs",
        "mono": contents / "MonoBleedingEdge/bin/mono",
        "cecil": contents / "MonoBleedingEdge/lib/mono/gac/Mono.Cecil/0.11.1.0__0738eb9f132ed756/Mono.Cecil.dll",
        "netstandard": contents / "MonoBleedingEdge/lib/mono/4.7.2-api/Facades/netstandard.dll",
        "bcl_mscorlib": contents / "MonoBleedingEdge/lib/mono/4.7.2-api/mscorlib.dll",
        "bcl_system": contents / "MonoBleedingEdge/lib/mono/4.7.2-api/System.dll",
        "bcl_system_core": contents / "MonoBleedingEdge/lib/mono/4.7.2-api/System.Core.dll",
        "unity_core": contents / "Managed/UnityEngine/UnityEngine.CoreModule.dll",
    }
    for name, path in paths.items():
        expected_hash = pins["unity_tools_sha256"].get(name)
        if not path.is_file() or not expected_hash or sha256(path) != expected_hash:
            raise RuntimeError("pinned Unity tool/reference drift: " + name)
    return contents, paths


def run(command: list[str], cwd: Path) -> str:
    result = subprocess.run(
        command,
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    if result.returncode:
        raise RuntimeError("command failed (" + str(result.returncode) + "): " + " ".join(command) + "\n" + result.stdout)
    return result.stdout


def transform(profile: str, supplied_input: Path, resolution_dir: Path, output_path: Path, project: Path, audio_resolver_overlay: Path | None = None) -> dict:
    if profile in {"post-audio-music-observer-6f96-api-d540", "post-audio-music-observer-r10-1ced"}:
        raise RuntimeError("legacy 27340 camera profiles are restore-only")
    pins = json.loads(PINS_PATH.read_text())
    for role, expected in pins["source_sha256"].items():
        relative = pins["source_paths"][role]
        source = SOURCE_ROOT / relative
        if not source.is_file() or sha256(source) != expected:
            raise RuntimeError("reviewed producer source drift: " + relative)
    input_path, input_hash = exact_input(profile, supplied_input, project, pins)
    expected_output_pin = pins["profiles"][profile].get("output_sha256")
    if not isinstance(expected_output_pin, str) or len(expected_output_pin) != 64:
        raise RuntimeError("camera profile output hash is unmeasured; refusing transformation")
    editor_contents, tools = pinned_editor(pins)
    api_path = project / "Assets/LabLoadingScene/Plugins/AK.Wwise.Unity.API.dll"
    game_path = project / "Assets/LabLoadingScene/Plugins/RoR2.dll"
    expected_api = pins["resolver_profiles"][profile]["api_sha256"]
    if not game_path.is_file() or sha256(game_path) != input_hash or not api_path.is_file() or sha256(api_path) != expected_api:
        raise RuntimeError("current project game/API pair differs from exact transform profile")
    resolution_dir, resolution_receipt = exact_resolution_closure(resolution_dir, pins, profile, project, editor_contents)
    resolver_overlay, resolver_overlay_sha256 = exact_audio_resolver_overlay(audio_resolver_overlay, profile, pins)
    output = ensure_under_work(output_path)
    receipt_path = output.with_name(output.name + ".producer-receipt.json")
    if receipt_path.exists() or receipt_path.is_symlink():
        raise RuntimeError("producer receipt already exists")
    output.parent.mkdir(parents=True, exist_ok=True)
    run_root = output.parent / ("." + output.name + ".native-view-run-" + uuid.uuid4().hex)
    run_root.mkdir()
    marker = SOURCE_ROOT / pins["source_paths"]["marker"]
    transformer = SOURCE_ROOT / pins["source_paths"]["transformer"]
    verifier = SOURCE_ROOT / pins["source_paths"]["verifier"]
    helper_dll = run_root / "NativeViewCameraMarker.Helper.dll"
    transform_exe = run_root / "NativeViewCameraTransform.exe"
    verify_exe = run_root / "VerifyNativeViewCameraTransform.exe"
    generated = run_root / "RoR2.native-view-camera.dll"

    try:
        marker_log = run(
            [
                str(tools["mcs"]),
                "-sdk:4.7.2",
                "-target:library",
                "-out:" + str(helper_dll),
                "-r:" + str(input_path),
                "-r:" + str(tools["unity_core"]),
                "-r:" + str(tools["netstandard"]),
                str(marker),
            ],
            cwd=run_root,
        )
        transform_compile_log = run(
            [
                str(tools["mcs"]),
                "-sdk:4.7.2",
                "-out:" + str(transform_exe),
                "-r:" + str(tools["cecil"]),
                str(transformer),
            ],
            cwd=run_root,
        )
        verify_compile_log = run(
            [
                str(tools["mcs"]),
                "-sdk:4.7.2",
                "-out:" + str(verify_exe),
                "-r:" + str(tools["cecil"]),
                str(verifier),
            ],
            cwd=run_root,
        )
        transform_log = run(
            [
                str(tools["mono"]),
                str(transform_exe),
                str(input_path),
                str(generated),
                str(helper_dll),
                "-",
                str(resolution_dir.resolve()),
            ],
            cwd=run_root,
        )
        verify_log = run(
            [
                str(tools["mono"]),
                str(verify_exe),
                str(input_path),
                str(generated),
                str(helper_dll),
            ],
            cwd=run_root,
        )
        if sha256(input_path) != input_hash:
            raise RuntimeError("input changed during producer execution")
        generated_hash = sha256(generated)
        expected_output_hash = pins["profiles"][profile].get("output_sha256")
        if not expected_output_hash or generated_hash != expected_output_hash:
            raise RuntimeError("generated RoR2 output differs from the reviewed deterministic profile output: " + generated_hash)
        if generated.stat().st_size <= input_path.stat().st_size:
            raise RuntimeError("guard output did not add the expected marker metadata")
        with generated.open("rb") as source, output.open("xb") as destination:
            shutil.copyfileobj(source, destination)
        if sha256(output) != generated_hash:
            output.unlink(missing_ok=True)
            raise RuntimeError("published output copy hash mismatch")
        receipt = {
            "schema": 1,
            "profile": profile,
            "input_relative_path": input_path.relative_to(ROOT).as_posix(),
            "input_sha256": input_hash,
            "resolver_inventory_sha256": hashlib.sha256(json.dumps(resolution_receipt, sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
            "resolver_dll_count": resolution_receipt["count"],
            "resolver_source_contract": "current project plugin DLLs plus pinned Unity engine modules/Mono mscorlib; not a player linker closure",
            "resolver_overlay_sha256": resolver_overlay_sha256,
            "resolver_effective_assembly_identity_count": resolution_receipt["count"],
            "output_relative_path": output.relative_to(ROOT).as_posix(),
            "output_sha256": generated_hash,
            "output_bytes": output.stat().st_size,
            "helper_sha256": sha256(helper_dll),
            "transformer_sha256": sha256(transformer),
            "verifier_sha256": sha256(verifier),
            "unity_tools_sha256": {name: sha256(path) for name, path in tools.items()},
            "logs": {
                "helper_compile": marker_log,
                "transform_compile": transform_compile_log,
                "verify_compile": verify_compile_log,
                "transform": transform_log,
                "verification": verify_log,
            },
            "scope": "one exact RoR2.dll; full player closure scanner remains a separate required gate",
        }
        receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
        return receipt
    except Exception as error:
        (run_root / "failure.txt").write_text(str(error) + "\n")
        raise


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--profile",
        choices=("default-game-3124", "post-audio-r4-1034-api-d540", "post-audio-native-music-results-r23-1ced"),
        required=True,
    )
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--resolution-dir", type=Path, required=True)
    parser.add_argument("--project", type=Path, required=True, help="current canonical whole-catalog project supplying the exact profile DLLs")
    parser.add_argument("--audio-resolver-overlay", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = transform(args.profile, args.input, args.resolution_dir, args.output, args.project, args.audio_resolver_overlay)
    except Exception as error:
        print(str(error), file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
