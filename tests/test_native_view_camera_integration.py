from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

CANDIDATE = Path(__file__).resolve().parents[1]
REPOSITORY = CANDIDATE


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to load copied tracked module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class NativeViewCameraIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=CANDIDATE.parent)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "repo"
        (self.root / "environment").mkdir(parents=True)
        (self.root / "recipe").mkdir()
        shutil.copy2(REPOSITORY / "environment/toolchain.json", self.root / "environment/toolchain.json")
        pins = json.loads((CANDIDATE / "recipe/native-view-camera-transform.json").read_text())
        self.pins = pins
        for relative in pins["source_paths"].values():
            source = CANDIDATE / relative
            target = self.root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
        shutil.copy2(CANDIDATE / "recipe/native-view-camera-transform.json", self.root / "recipe/native-view-camera-transform.json")
        self.hook = load("camera_hook_copy", self.root / "scripts/lab/native_view_camera_build_hook.py")

    def test_production_paths_have_no_preview_or_dated_capture_selection(self):
        production = [
            self.root / "scripts/lab/native_view_camera_build_hook.py",
            self.root / "scripts/lab/native_view_camera_transform.py",
            self.root / "scripts/lab/native_view_camera_resolver.py",
            self.root / "recipe/native-view-camera-transform.json",
        ]
        joined = "\n".join(path.read_text() for path in production)
        for forbidden in ("PREVIEW_ROOT", "IN_PREVIEW", "20261021T021320", "capture_relative_path", "candidate/recipe"):
            self.assertNotIn(forbidden, joined)
        self.assertFalse((self.root / "tools/assembly-transforms/native-view-camera-producer-pins.json").exists())
        self.assertEqual(set(self.pins["source_paths"]), set(self.pins["source_sha256"]))
        for role, relative in self.pins["source_paths"].items():
            path = self.root / relative
            self.assertTrue(path.is_file(), role)
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), self.pins["source_sha256"][role], role)

    def test_complete_target_hash_set_matches_and_same_count_mutants_refuse(self):
        project = self.root / "work/project"
        rows = []
        for index in range(165):
            target = f"Assets/StreamingAssets/Fixture/{index:03d}.bin"
            content = f"payload:{index}".encode()
            path = project / target
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
            rows.append({"target": target, "sha256": hashlib.sha256(content).hexdigest(), "status": "staged"})
        manifest_rows = [{"target": row["target"], "sha256": row["sha256"], "role": "fixture"} for row in rows]
        self.hook._verify_stage_manifest_rows({"outputs": rows}, {"outputs": manifest_rows}, project)

        mutants = []
        removed_added = [dict(row) for row in rows]
        removed_added[-1] = {**removed_added[-1], "target": "Assets/StreamingAssets/Fixture/new.bin"}
        mutants.append(removed_added)
        duplicate = [dict(row) for row in rows]
        duplicate[-1] = dict(duplicate[0])
        mutants.append(duplicate)
        substituted_hash = [dict(row) for row in rows]
        substituted_hash[-1]["sha256"] = "0" * 64
        mutants.append(substituted_hash)
        missing = [dict(row) for row in rows[:-1]]
        mutants.append(missing)
        for mutant in mutants:
            with self.subTest(rows=len(mutant)), self.assertRaises(ValueError):
                self.hook._verify_stage_manifest_rows({"outputs": mutant}, {"outputs": manifest_rows}, project)

    def test_actual_current_audio_stage_matches_all_165_artifact_rows(self):
        project = REPOSITORY / "work/lab-project"
        stage_path = project / "Assets/StreamingAssets/Lab/OriginalGameAudioStageReceipt.json"
        if not stage_path.is_file():
            self.skipTest("actual local audio-stage receipt is unavailable")
        stage = json.loads(stage_path.read_text())
        manifest_hash = stage.get("artifact_manifest_sha256")
        owner_root = REPOSITORY / "work/original-game-audio-owner"
        matches = [
            path for path in owner_root.glob("*/artifact-manifest.json") if path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() == manifest_hash
        ]
        if len(matches) != 1:
            self.skipTest("matching immutable artifact manifest is unavailable")
        manifest = json.loads(matches[0].read_text())
        camera_receipt = project / self.hook.CAMERA_STAGE_RELATIVE
        if camera_receipt.is_file():
            # Validate the audio stage before its later, receipt-owned camera
            # overlay, using scratch copies only. The live project stays intact.
            camera = json.loads(camera_receipt.read_text())
            music_receipt_relative = Path("Assets/StreamingAssets/Lab/OriginalMusicOutputObserverStageReceipt.json")
            music_receipt = project / music_receipt_relative
            music_profiles = {
                "post-audio-music-observer-6f96-api-d540",
                "post-audio-music-observer-r10-1ced",
            }
            music_receipt_required = camera.get("profile") in music_profiles
            if music_receipt.is_file():
                self.hook._reject_symlinks(music_receipt)
            if music_receipt_required and not music_receipt.is_file():
                self.skipTest("current camera stage has no local music-observer receipt to restore")
            work_copy = self.root / "work"
            project_copy = work_copy / "project-stage"
            project_files = [row["target"] for row in stage["outputs"]] + [
                self.hook.CAMERA_STAGE_RELATIVE.as_posix(),
                stage_path.relative_to(project).as_posix(),
            ]
            if music_receipt.is_file():
                project_files.append(music_receipt_relative.as_posix())
            for relative in project_files:
                target = project_copy / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(project / relative, target)

            if music_receipt.is_file():
                music = json.loads(music_receipt.read_text())
                music_snapshot = music.get("preimage_snapshot")
                self.assertIsInstance(music_snapshot, str)
                music_snapshot_path = Path(music_snapshot)
                self.assertFalse(music_snapshot_path.is_absolute())
                self.assertNotIn("..", music_snapshot_path.parts)
                self.assertNotIn("\\", music_snapshot)
                self.assertEqual(music_snapshot_path.as_posix(), music_snapshot)
                source = REPOSITORY / "work" / music_snapshot
                if not source.is_file():
                    self.skipTest("local music-observer preimage snapshot is unavailable")
                self.hook._reject_symlinks(source)
                target = work_copy / music_snapshot
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)

            snapshot = camera["preimage_snapshot"]
            snapshot_path = Path(snapshot)
            self.assertFalse(snapshot_path.is_absolute())
            self.assertNotIn("..", snapshot_path.parts)
            target = work_copy / snapshot
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(REPOSITORY / "work" / snapshot, target)
            self.hook.restore_previous_camera(project_copy, work_copy)
            project = project_copy
        self.hook._verify_stage_manifest_rows(stage, manifest, project)
        self.assertEqual(len(stage["outputs"]), 165)
        self.assertFalse(stage["runtime_accepted"])
        self.assertFalse(stage["audible"])
        for mutate in ("missing", "duplicate", "hash"):
            mutant = [dict(row) for row in stage["outputs"]]
            if mutate == "missing":
                mutant.pop()
            elif mutate == "duplicate":
                mutant[-1] = dict(mutant[0])
            else:
                mutant[-1]["sha256"] = "0" * 64
            with self.subTest(mutate=mutate), self.assertRaises(ValueError):
                self.hook._verify_stage_manifest_rows({"outputs": mutant}, manifest, project)

    def test_exact_current_plugin_unity_mono_resolver_needs_no_player_capture(self):
        project = REPOSITORY / "work/lab-project"
        input_path = project / "Assets/LabLoadingScene/Plugins/RoR2.dll"
        api = project / "Assets/LabLoadingScene/Plugins/AK.Wwise.Unity.API.dll"
        editor = Path("/Applications/Unity/Hub/Editor/2021.3.45f2/Unity.app/Contents")
        if not (project.is_dir() and input_path.is_file() and api.is_file() and editor.is_dir()):
            self.skipTest("exact local current staged project and pinned Unity editor are unavailable")
        if hashlib.sha256(input_path.read_bytes()).hexdigest() != self.pins["profiles"]["post-audio-r4-1034-api-d540"]["input_sha256"]:
            self.skipTest("current staged game profile differs from the pinned test input")
        if hashlib.sha256(api.read_bytes()).hexdigest() != self.pins["resolver_profiles"]["post-audio-r4-1034-api-d540"]["api_sha256"]:
            self.skipTest("current staged API profile differs from the pinned test input")
        project_copy = self.root / "work/project-input"
        shutil.copytree(project / "Assets/LabLoadingScene/Plugins", project_copy / "Assets/LabLoadingScene/Plugins")
        shutil.copytree(project / "Assets/Plugins", project_copy / "Assets/Plugins")
        resolver = load("camera_resolver_copy", self.root / "scripts/lab/native_view_camera_resolver.py")
        transform = load("camera_transform_copy", self.root / "scripts/lab/native_view_camera_transform.py")
        output = self.root / "work/generated/resolver-current"
        receipt = resolver.materialize(
            "post-audio-r4-1034-api-d540",
            project_copy,
            input_path,
            editor,
            output,
            self.pins["profiles"]["post-audio-r4-1034-api-d540"]["input_sha256"],
            self.pins["resolver_profiles"]["post-audio-r4-1034-api-d540"]["api_sha256"],
        )
        self.assertEqual(receipt["schema"], "native-view-camera-resolver-set-r2")
        self.assertFalse(receipt["player_linker_closure_verified"])
        self.assertFalse(receipt["il2cpp_closure_verified"])
        self.assertFalse(receipt["stage_to_apk_binding"])
        self.assertEqual(receipt["count"], len(list((output / "assemblies").glob("*.dll"))))
        self.assertEqual(hashlib.sha256((output / "assemblies/RoR2.dll").read_bytes()).hexdigest(), receipt["input_sha256"])
        directory, checked = transform.exact_resolution_closure(output / "assemblies", self.pins, "post-audio-r4-1034-api-d540", project_copy, editor)
        self.assertEqual(checked["source_inventory_sha256"], receipt["source_inventory_sha256"])
        drifted = project_copy / "Assets/LabLoadingScene/Plugins/AK.Wwise.Unity.API.dll"
        drifted.write_bytes(drifted.read_bytes() + b"drift")
        with self.assertRaises((RuntimeError, ValueError)):
            transform.exact_resolution_closure(directory, self.pins, "post-audio-r4-1034-api-d540", project_copy, editor)

    def test_exact_point_sound_6f96_profile_transform_when_local_artifact_exists(self):
        project = REPOSITORY / "work/lab-project"
        point_sound = REPOSITORY / "work/coordination/original-game-audio-point-sound-repair/r3/host/RoR2-point-sound-diagnostic.dll"
        editor = Path("/Applications/Unity/Hub/Editor/2021.3.45f2/Unity.app/Contents")
        profile = "post-audio-point-sound-6f96-api-d540"
        game_hash = self.pins["profiles"][profile]["input_sha256"]
        expected_output = self.pins["profiles"][profile]["output_sha256"]
        api_hash = self.pins["resolver_profiles"][profile]["api_sha256"]
        if not (project.is_dir() and point_sound.is_file() and editor.is_dir()):
            self.skipTest("local PointSound transform input or pinned Unity toolchain is unavailable")
        if hashlib.sha256(point_sound.read_bytes()).hexdigest() != game_hash:
            self.skipTest("local PointSound DLL does not match the exact profile input")
        if hashlib.sha256((project / "Assets/LabLoadingScene/Plugins/AK.Wwise.Unity.API.dll").read_bytes()).hexdigest() != api_hash:
            self.skipTest("current local Wwise API does not match the exact PointSound profile")
        project_copy = self.root / "work/point-sound-project"
        shutil.copytree(project / "Assets/LabLoadingScene/Plugins", project_copy / "Assets/LabLoadingScene/Plugins")
        shutil.copytree(project / "Assets/Plugins", project_copy / "Assets/Plugins")
        shutil.copy2(point_sound, project_copy / "Assets/LabLoadingScene/Plugins/RoR2.dll")
        resolver = load("point_sound_camera_resolver", self.root / "scripts/lab/native_view_camera_resolver.py")
        transform = load("point_sound_camera_transform", self.root / "scripts/lab/native_view_camera_transform.py")
        resolver_root = self.root / "work/generated/point-sound-resolver"
        resolver_receipt = resolver.materialize(
            profile,
            project_copy,
            project_copy / "Assets/LabLoadingScene/Plugins/RoR2.dll",
            editor,
            resolver_root,
            game_hash,
            api_hash,
        )
        output = self.root / "work/generated/point-sound-camera.dll"
        with patch.dict(os.environ, {"UNITY_EDITOR": str(editor / "MacOS/Unity")}):
            receipt = transform.transform(
                profile,
                project_copy / "Assets/LabLoadingScene/Plugins/RoR2.dll",
                resolver_root / "assemblies",
                output,
                project_copy,
            )
        self.assertEqual(receipt["input_sha256"], game_hash)
        self.assertEqual(receipt["output_sha256"], expected_output)
        self.assertEqual(
            receipt["resolver_inventory_sha256"], hashlib.sha256(json.dumps(resolver_receipt, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        )
        self.assertFalse(resolver_receipt["player_linker_closure_verified"])
        self.assertFalse(resolver_receipt["il2cpp_closure_verified"])
        self.assertFalse(resolver_receipt["stage_to_apk_binding"])


if __name__ == "__main__":
    unittest.main()
