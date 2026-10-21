import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import hashlib

TEST_PATH = Path(__file__).resolve()
REPO = next(parent for parent in TEST_PATH.parents if (parent / "scripts/lab/original_game_audio_build_hook.py").is_file())
CANDIDATE = TEST_PATH.parents[1] / "candidate/scripts/lab/original_game_audio_build_hook.py"
SOURCE_MODULE = CANDIDATE if CANDIDATE.is_file() else REPO / "scripts/lab/original_game_audio_build_hook.py"
spec = importlib.util.spec_from_file_location("candidate_audio_build_hook", SOURCE_MODULE)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

INPUT_ID = "a" * 64
ASSET_GUID = "e0447f0f885c66f4bb55ba311b31d463"
AUDIO_GUID = "2b6c926553287666f24ffd5af5ba21cb"
SOURCE = """%YAML 1.1
--- !u!1 &1
GameObject:
  m_Component:
  - component: {fileID: 2}
  - component: {fileID: 4}
  - component: {fileID: 3}
  m_Name: SoundEmitter
--- !u!4 &2
Transform:
  m_GameObject: {fileID: 1}
--- !u!54 &4
Rigidbody:
  m_GameObject: {fileID: 1}
--- !u!114 &3
MonoBehaviour:
  m_GameObject: {fileID: 1}
  m_Script: {fileID: -130519023, guid: 2b6c926553287666f24ffd5af5ba21cb, type: 3}
  m_Enabled: 1
"""
STRIPPED = SOURCE.replace("  - component: {fileID: 3}\n", "").replace(
    "--- !u!114 &3\nMonoBehaviour:\n  m_GameObject: {fileID: 1}\n  m_Script: {fileID: -130519023, guid: " + AUDIO_GUID + ", type: 3}\n  m_Enabled: 1\n", ""
)


class SoundEmitterRestoreTests(unittest.TestCase):
    def fixture(self):
        accepted_synthetic_sha = hashlib.sha256(SOURCE.encode()).hexdigest()
        pin = patch.object(module, "SOUND_EMITTER_ACCEPTED_SOURCE_SHA256", accepted_synthetic_sha)
        pin.start()
        self.addCleanup(pin.stop)
        input_pin = patch.object(module, "SOUND_EMITTER_ACCEPTED_INPUT_ID", INPUT_ID)
        input_pin.start()
        self.addCleanup(input_pin.stop)
        temp = tempfile.TemporaryDirectory()
        root = Path(temp.name)
        work = root / "work"
        project = work / "lab-project"
        export = work / "input/ExportedProject"
        source = export / module.SOUND_EMITTER_ASSET
        target = project / "Assets/WholeGame/RoR2/Base/Utility/SoundEmitter.prefab"
        source.parent.mkdir(parents=True)
        target.parent.mkdir(parents=True)
        (work / "config").mkdir()
        (project / "Assets/LabLoadingScene/Plugins").mkdir(parents=True)
        (work / "config/accepted-input.json").write_text(json.dumps({"input_id": INPUT_ID}))
        (work / "config/reconstruction.json").write_text(json.dumps({"input_id": INPUT_ID, "success": True, "projects": ["work/input/ExportedProject"]}))
        (project / ".port-input.json").write_text(json.dumps({"input_id": INPUT_ID}))
        source.write_text(SOURCE)
        target.write_text(STRIPPED)
        source.with_name(source.name + ".meta").write_text("fileFormatVersion: 2\nguid: " + ASSET_GUID + "\n")
        target.with_name(target.name + ".meta").write_text("fileFormatVersion: 2\nguid: " + ASSET_GUID + "\n")
        (project / "Assets/LabLoadingScene/Plugins/AK.Wwise.Unity.MonoBehaviour.dll.meta").write_text("fileFormatVersion: 2\nguid: " + AUDIO_GUID + "\n")
        wwise = export / module.SOUND_EMITTER_WWISE_PATH
        wwise.parent.mkdir(parents=True)
        wwise.write_text("synthetic accepted WwiseGlobal prefab\n")
        resolved = {"prefab": wwise}
        return temp, work, project, resolved

    def test_requested_restores_accepted_source_and_is_idempotent(self):
        temp, work, project, resolved = self.fixture()
        with temp:
            first = module.synchronize_sound_emitter(project, work, requested=True, resolved=resolved)
            target = project / "Assets/WholeGame/RoR2/Base/Utility/SoundEmitter.prefab"
            self.assertTrue(first["component_restored"])
            self.assertEqual(target.read_text(), SOURCE)
            second = module.synchronize_sound_emitter(project, work, requested=True, resolved=resolved)
            self.assertEqual(second["after_sha256"], second["before_sha256"])

    def test_default_off_removes_only_the_exact_source_component(self):
        temp, work, project, resolved = self.fixture()
        with temp:
            target = project / "Assets/WholeGame/RoR2/Base/Utility/SoundEmitter.prefab"
            target.write_text(SOURCE)
            result = module.synchronize_sound_emitter(project, work, requested=False)
            self.assertFalse(result["component_restored"])
            self.assertEqual(target.read_text(), STRIPPED)

    def test_requested_mode_refuses_wrong_source_prefab(self):
        temp, work, project, resolved = self.fixture()
        with temp:
            resolved["prefab"] = project / "wrong.prefab"
            with self.assertRaisesRegex(ValueError, "not the accepted WwiseGlobal"):
                module.synchronize_sound_emitter(project, work, requested=True, resolved=resolved)

    def test_refuses_unrelated_project_drift_before_write(self):
        temp, work, project, resolved = self.fixture()
        with temp:
            target = project / "Assets/WholeGame/RoR2/Base/Utility/SoundEmitter.prefab"
            target.write_text(STRIPPED.replace("m_Name: SoundEmitter", "m_Name: drift"))
            before = target.read_bytes()
            with self.assertRaisesRegex(ValueError, "differs beyond"):
                module.synchronize_sound_emitter(project, work, requested=True, resolved=resolved)
            self.assertEqual(target.read_bytes(), before)

    def test_refuses_unpinned_accepted_input_before_target_write(self):
        temp, work, project, resolved = self.fixture()
        with temp:
            target = project / "Assets/WholeGame/RoR2/Base/Utility/SoundEmitter.prefab"
            before = target.read_bytes()
            (work / "config/accepted-input.json").write_text(json.dumps({"input_id": "b" * 64}))
            with self.assertRaisesRegex(ValueError, "accepted input does not match"):
                module.synchronize_sound_emitter(project, work, requested=True, resolved=resolved)
            self.assertEqual(target.read_bytes(), before)

    def test_refuses_source_component_mutation_before_target_write(self):
        temp, work, project, resolved = self.fixture()
        with temp:
            source = work / "input/ExportedProject" / module.SOUND_EMITTER_ASSET
            target = project / "Assets/WholeGame/RoR2/Base/Utility/SoundEmitter.prefab"
            mutated = SOURCE.replace("  m_Enabled: 1", "  m_Enabled: 0")
            self.assertNotEqual(mutated, SOURCE)
            source.write_text(mutated)
            before = target.read_bytes()
            with self.assertRaisesRegex(ValueError, "pinned import receipt"):
                module.synchronize_sound_emitter(project, work, requested=True, resolved=resolved)
            self.assertEqual(target.read_bytes(), before)

    def test_refuses_missing_component_reference(self):
        temp, work, project, resolved = self.fixture()
        with temp:
            source = work / "input/ExportedProject" / module.SOUND_EMITTER_ASSET
            target = project / "Assets/WholeGame/RoR2/Base/Utility/SoundEmitter.prefab"
            malformed = SOURCE.replace("  - component: {fileID: 3}\n", "")
            module.SOUND_EMITTER_ACCEPTED_SOURCE_SHA256 = hashlib.sha256(malformed.encode()).hexdigest()
            source.write_text(malformed)
            before = target.read_bytes()
            with self.assertRaisesRegex(ValueError, "not uniquely listed"):
                module.synchronize_sound_emitter(project, work, requested=True, resolved=resolved)
            self.assertEqual(target.read_bytes(), before)

    def test_refuses_duplicate_component_reference(self):
        temp, work, project, resolved = self.fixture()
        with temp:
            source = work / "input/ExportedProject" / module.SOUND_EMITTER_ASSET
            target = project / "Assets/WholeGame/RoR2/Base/Utility/SoundEmitter.prefab"
            malformed = SOURCE.replace(
                "  - component: {fileID: 3}\n",
                "  - component: {fileID: 3}\n  - component: {fileID: 3}\n",
            )
            module.SOUND_EMITTER_ACCEPTED_SOURCE_SHA256 = hashlib.sha256(malformed.encode()).hexdigest()
            source.write_text(malformed)
            before = target.read_bytes()
            with self.assertRaisesRegex(ValueError, "not uniquely listed"):
                module.synchronize_sound_emitter(project, work, requested=True, resolved=resolved)
            self.assertEqual(target.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
