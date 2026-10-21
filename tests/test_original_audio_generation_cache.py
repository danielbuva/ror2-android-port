from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

REPO = Path(__file__).resolve().parents[1]
HOOK_PATH = REPO / "scripts/lab/original_game_audio_build_hook.py"
SPEC = importlib.util.spec_from_file_location("original_audio_build_hook_under_test", HOOK_PATH)
assert SPEC and SPEC.loader
hook = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(hook)


def key_for(payload: dict) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


class FakeProducer:
    OWNER_SOURCE_HASHES = {"fixture-owner.cs": "fixture-owner-hash"}

    def __init__(self) -> None:
        self.compile_outputs: list[Path] = []

    @staticmethod
    def reject_symlink_components(path: Path) -> None:
        return None

    @staticmethod
    def validate_toolchain(*args: object) -> dict[str, str]:
        return {"toolchain": "isolated fixture"}

    @staticmethod
    def unity_reference_options(*args: object) -> tuple[list[str], list[Path]]:
        return [], []

    def compile_requested(self, *args: object) -> None:
        output = args[-3]
        assert isinstance(output, Path)
        self.compile_outputs.append(output)
        raise RuntimeError("requested cache miss compiled")


class FakeStager:
    def __init__(self) -> None:
        self.reads = 0
        self.stages = 0

    def read_artifacts(self, *args: object) -> tuple[dict, list, dict]:
        self.reads += 1
        return {}, [], {}

    def stage(self, *args: object) -> dict[str, bool]:
        self.stages += 1
        return {"requested": True}


def make_fake_source_bundle(root: Path) -> None:
    paths = [
        "scripts/lab/original_game_audio.py",
        "scripts/lab/original_game_audio_build_hook.py",
        "scripts/lab/original_game_audio_produce.py",
        "scripts/lab/original_game_audio_stage.py",
        "scripts/lab/assembly_transforms.py",
        "scripts/lab/common.py",
        "environment/toolchain.json",
        "recipe/assembly-transforms.json",
        "recipe/wwise-android-abi.json",
        "tools/unity/support/audio/managed-producer/produce.py",
        "tools/assembly-transforms/pin.cs",
        "tools/wwise-android-abi/pin.csproj",
    ]
    for relative in paths:
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"fixture source {relative}\n", encoding="utf-8")


def make_fixture(root: Path) -> tuple[Path, Path, Path, Path, Path, Path]:
    root = root.resolve()
    work = root / "work"
    work.mkdir()
    project = work / "build/project"
    plugins = project / "Assets/LabLoadingScene/Plugins"
    plugins.mkdir(parents=True)
    (plugins / "AK.Wwise.Unity.API.dll").write_bytes(b"fixture api")
    (plugins / "RoR2.dll").write_bytes(b"fixture game")

    editor = root / "toolchain/Unity.app/Contents/MacOS/Unity"
    editor.parent.mkdir(parents=True)
    editor.write_bytes(b"fixture editor")

    sdk_root = root / "dotnet"
    dotnet = sdk_root / "dotnet"
    sdk_root.mkdir(parents=True)
    marker = root / "dotnet-version-calls.txt"
    dotnet.write_text(f"#!/bin/sh\nprintf '8.0.414\\n' >> '{marker}'\nprintf '8.0.414\\n'\n", encoding="utf-8")
    dotnet.chmod(0o755)
    sdk = sdk_root / "sdk/8.0.414"
    (sdk / "Roslyn/bincore").mkdir(parents=True)
    (sdk / "Roslyn/bincore/csc.dll").write_bytes(b"fixture Roslyn")
    (sdk / "MSBuild.dll").write_bytes(b"fixture MSBuild")
    llvm_nm = editor.parent.parent.parent.parent / "PlaybackEngines/AndroidPlayer/NDK/toolchains/llvm/prebuilt/darwin-x86_64/bin/llvm-nm"
    llvm_nm.parent.mkdir(parents=True)
    llvm_nm.write_bytes(b"fixture llvm-nm")
    llvm_nm.chmod(0o755)

    inputs_root = work / "fixture-inputs"
    inputs_root.mkdir()
    inputs: dict[str, Path] = {}
    for name in hook.REQUESTED_PATHS:
        if name == "stage_root":
            path = inputs_root / name
            path.mkdir()
        else:
            path = inputs_root / f"{name}.bin"
            path.write_bytes(json.dumps({"outputs": []}).encode() if name == "stage_receipt" else name.encode())
        inputs[name] = path
    selection_path = work / "config/original-game-audio/selection.json"
    selection_path.parent.mkdir(parents=True)
    selection = {
        "schema": hook.SELECTION_SCHEMA,
        "requested": True,
        "request_id": "0123456789abcdef0123456789abcdef",
        "inputs": {name: path.relative_to(work).as_posix() for name, path in inputs.items()},
    }
    selection_path.write_text(json.dumps(selection), encoding="utf-8")
    return work, project, editor, dotnet, llvm_nm, selection_path


def expected_payload(project: Path, work: Path, selection_path: Path, dotnet: Path, llvm_nm: Path, producer: FakeProducer) -> dict:
    selection, resolved, variant = hook.read_selection(work, selection_path)
    assert variant == "requested"
    return {
        "variant": variant,
        "source_bundle": hook.source_bundle_hashes(),
        "toolchain": producer.validate_toolchain(),
        "unity_references": [],
        "owner_sources": producer.OWNER_SOURCE_HASHES,
        "project_api_sha256": hook.file_sha(project / "Assets/LabLoadingScene/Plugins/AK.Wwise.Unity.API.dll"),
        "project_game_sha256": hook.file_sha(project / "Assets/LabLoadingScene/Plugins/RoR2.dll"),
        "selection_sha256": hook.file_sha(selection_path),
        "requested_tools": hook.requested_tool_identity(dotnet, llvm_nm),
        "managed_producer_sha256": hook.file_sha(hook.ROOT / "tools/unity/support/audio/managed-producer/produce.py"),
        "request_id": selection["request_id"],
        "passive_pcm_capture_requested": selection["passive_pcm_capture_requested"],
        "input_sha256": {name: hook.file_sha(path) for name, path in sorted(resolved.items()) if name != "stage_root"},
        "receipt_bound_payload": json.loads(resolved["stage_receipt"].read_text(encoding="utf-8"))["outputs"],
    }


class GenerationCacheTests(unittest.TestCase):
    def test_actual_r1_requested_selection_defaults_passive_pcm_to_false(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            work, _, _, _, _, selection_path = make_fixture(Path(temp_name))
            selection = json.loads(selection_path.read_text(encoding="utf-8"))
            selection["schema"] = hook.LEGACY_SELECTION_SCHEMA
            selection_path.write_text(json.dumps(selection), encoding="utf-8")
            selection, _, variant = hook.read_selection(work, selection_path)
            self.assertEqual("requested", variant)
            self.assertEqual(hook.LEGACY_SELECTION_SCHEMA, selection["schema"])
            self.assertIs(selection["passive_pcm_capture_requested"], False)

    def test_r2_requested_selection_without_flag_remains_default_off(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            work, _, _, _, _, selection_path = make_fixture(Path(temp_name))
            selection, _, variant = hook.read_selection(work, selection_path)
            self.assertEqual("requested", variant)
            self.assertEqual(hook.SELECTION_SCHEMA, selection["schema"])
            self.assertIs(selection["passive_pcm_capture_requested"], False)

    def test_r1_rejects_diagnostic_field_and_unknown_schema(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            work, _, _, _, _, selection_path = make_fixture(Path(temp_name))
            selection = json.loads(selection_path.read_text(encoding="utf-8"))
            selection["schema"] = hook.LEGACY_SELECTION_SCHEMA
            selection["passive_pcm_capture_requested"] = False
            selection_path.write_text(json.dumps(selection), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "unexpected fields"):
                hook.read_selection(work, selection_path)

            selection.pop("passive_pcm_capture_requested")
            selection["schema"] = "original-game-audio-build-selection-r999"
            selection_path.write_text(json.dumps(selection), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "schema/request flag"):
                hook.read_selection(work, selection_path)

    def test_passive_pcm_selection_requires_bool_and_rejects_unknown_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            work, _, _, _, _, selection_path = make_fixture(Path(temp_name))
            selection = json.loads(selection_path.read_text(encoding="utf-8"))
            selection["passive_pcm_capture_requested"] = True
            selection_path.write_text(json.dumps(selection), encoding="utf-8")
            migrated, _, _ = hook.read_selection(work, selection_path)
            self.assertIs(migrated["passive_pcm_capture_requested"], True)
            selection["passive_pcm_capture_requested"] = 1
            selection_path.write_text(json.dumps(selection), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "boolean"):
                hook.read_selection(work, selection_path)
            selection["passive_pcm_capture_requested"] = False
            selection["unrecognized"] = False
            selection_path.write_text(json.dumps(selection), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "unexpected fields"):
                hook.read_selection(work, selection_path)

    def test_source_bundle_lists_public_audio_and_transform_inputs(self) -> None:
        bundle = hook.source_bundle_hashes()
        required = {
            "scripts/lab/original_game_audio.py",
            "scripts/lab/original_game_audio_build_hook.py",
            "scripts/lab/original_game_audio_produce.py",
            "scripts/lab/original_game_audio_stage.py",
            "scripts/lab/assembly_transforms.py",
            "scripts/lab/common.py",
            "environment/toolchain.json",
            "recipe/assembly-transforms.json",
            "recipe/wwise-android-abi.json",
            "tools/unity/support/audio/generators/generate_accepted_request_pin.py",
        }
        self.assertTrue(required.issubset(bundle))
        for relative in required:
            self.assertEqual(hook.file_sha(REPO / relative), bundle[relative])

    def test_requested_cache_hit_resolves_tools_and_tool_byte_changes_miss_cache(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            make_fake_source_bundle(root)
            work, project, editor, dotnet, llvm_nm, selection_path = make_fixture(root)
            producer, stager = FakeProducer(), FakeStager()
            marker = root / "dotnet-version-calls.txt"
            with mock.patch.object(hook, "ROOT", root):
                payload = expected_payload(project, work, selection_path, dotnet, llvm_nm, producer)
                key = key_for(payload)
                output = project.parent / "original-game-audio-owner" / key
                generated = output / "generated"
                generated.mkdir(parents=True)
                (output / "artifact-manifest.json").write_text("{}\n", encoding="utf-8")
                (generated / "request.json").write_text("{}\n", encoding="utf-8")
                (output / "generation.json").write_text(json.dumps({"schema": 1, "generation_key": key, "inputs": payload}, sort_keys=True), encoding="utf-8")

                def invoke() -> dict:
                    with (
                        mock.patch.dict(os.environ, {"UNITY_EDITOR": str(editor)}),
                        mock.patch.object(hook, "load", side_effect=[producer, stager]),
                        mock.patch.object(hook.shutil, "which", return_value=str(dotnet)),
                        mock.patch.object(hook, "synchronize_sound_emitter", return_value={"fixture": True}),
                    ):
                        return hook.stage_for_build(project, work, selection_path=selection_path)

                result = invoke()
                self.assertTrue(result["producer"]["cached"])
                self.assertEqual(1, stager.stages)
                self.assertEqual("8.0.414\n8.0.414\n", marker.read_text(encoding="utf-8"))

                sdk = dotnet.parent / "sdk/8.0.414"
                mutable_tools = (dotnet, sdk / "Roslyn/bincore/csc.dll", sdk / "MSBuild.dll", llvm_nm)
                for index, tool in enumerate(mutable_tools, start=1):
                    tool.write_bytes(tool.read_bytes() + f"\n# mutation {index}\n".encode())
                    with self.assertRaisesRegex(RuntimeError, "requested cache miss compiled"):
                        invoke()
                    self.assertEqual(index, len(producer.compile_outputs))
                    self.assertNotEqual(output, producer.compile_outputs[-1])
                self.assertEqual(1, stager.stages)

    def test_cache_receipt_must_match_current_key_and_payload(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            make_fake_source_bundle(root)
            work, project, editor, dotnet, llvm_nm, selection_path = make_fixture(root)
            producer, stager = FakeProducer(), FakeStager()
            with mock.patch.object(hook, "ROOT", root):
                payload = expected_payload(project, work, selection_path, dotnet, llvm_nm, producer)
                key = key_for(payload)
                output = project.parent / "original-game-audio-owner" / key
                generated = output / "generated"
                generated.mkdir(parents=True)
                (output / "artifact-manifest.json").write_text("{}\n", encoding="utf-8")
                (generated / "request.json").write_text("{}\n", encoding="utf-8")
                altered = {**payload, "source_bundle": {"stale.py": "0" * 64}}
                (output / "generation.json").write_text(json.dumps({"schema": 1, "generation_key": key, "inputs": altered}), encoding="utf-8")
                with (
                    mock.patch.dict(os.environ, {"UNITY_EDITOR": str(editor)}),
                    mock.patch.object(hook, "load", side_effect=[producer, stager]),
                    mock.patch.object(hook.shutil, "which", return_value=str(dotnet)),
                    mock.patch.object(hook, "synchronize_sound_emitter", return_value={"fixture": True}),
                ):
                    with self.assertRaisesRegex(ValueError, "differs from current source/input identity"):
                        hook.stage_for_build(project, work, selection_path=selection_path)
                self.assertEqual(0, stager.stages)
                self.assertEqual([], producer.compile_outputs)


if __name__ == "__main__":
    unittest.main()
