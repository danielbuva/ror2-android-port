"""Coherent synthetic import/build/consent/install/update journey, not device evidence."""

import copy
import json
import unittest
from unittest.mock import patch
from tests.owner_journey_fixture import owner_journey, F, J, U
from tests.owner_journey_android import install


class OwnerJourneyTests(unittest.TestCase):
    def test_import_build_install_and_update(self):
        with owner_journey() as journey:
            self.assertEqual(journey.run("install-prepare")["state"], "INPUTS_REQUIRED")
            original = journey.inputs / "import/files/original.txt"
            original.parent.mkdir(parents=True)
            original.write_bytes(b"authored")
            installed = None
            for version in (2, 3):
                if installed:
                    journey.candidate["release"] = copy.deepcopy(journey.release)
                    journey.candidate["release"].update(version="synthetic-2", version_code=version)
                    state = journey.run("release-check", installed)
                    self.assertEqual(state["state"], "UPDATE_AVAILABLE")
                    self.assertTrue(state["installed_manifest_known"])
                    self.assertEqual(state["changed_entries"], [])
                journey.events.clear()
                ready = journey.run("release-build", installed)
                self.assertEqual(ready["state"], "READY")
                self.assertEqual(ready["pipeline"]["status"], "awaiting_install")
                stages = []
                for event in journey.events:
                    stage = event.get("pipeline", {}).get("current_stage")
                    if stage and (not stages or stages[-1] != stage):
                        stages.append(stage)
                self.assertEqual(stages, list(F.STAGES))
                self.assertEqual((journey.inputs / "attempt-count.txt").read_text().splitlines(), ["attempt", "attempt"])
                previous = installed
                installed = install(journey, previous)
                self.assertTrue(installed["installed_readback_verified"])
                self.assertEqual(installed["release"]["version_code"], version)
                self.assertEqual(installed["profile_retention_verified"], previous is not None)
                if previous:
                    self.assertEqual(json.loads((journey.inputs / "previous-installed-release.json").read_text())["sha256"], previous["sha256"])
                    self.assertGreater(installed["version_code"], previous["version_code"])
                    self.assertEqual(installed["signer_sha256"], previous["signer_sha256"])
                self.assertEqual(original.read_bytes(), b"authored")
            self.assertEqual(journey.run("release-check", installed)["state"], "UP_TO_DATE")

    def test_reconstructed_owner_recovery_matches_uninterrupted_journey(self):
        baseline = None
        for boundary in ("uninterrupted", "after-admission", "mid-conversion", "cancel-conversion", "ready-before-consent"):
            with self.subTest(boundary=boundary), owner_journey() as journey:
                self.assertEqual(journey.run("install-prepare")["state"], "INPUTS_REQUIRED")
                original = journey.inputs / "import/files/original.txt"
                original.parent.mkdir(parents=True)
                original.write_bytes(b"authored")
                profile = journey.inputs / "authored-profile-placeholder.txt"
                profile.write_bytes(b"untouched authored profile")
                if boundary == "after-admission":
                    write = U.write_json
                    interrupted = []

                    def stop_after_admission(path, value):
                        if path.name == "update-state.json" and value.get("pipeline", {}).get("current_stage") == "staging" and not interrupted:
                            interrupted.append(True)
                            raise OSError("synthetic interruption after persisted admission")
                        write(path, value)

                    with patch.object(U, "write_json", side_effect=stop_after_admission), self.assertRaises(OSError):
                        journey.run("release-build")
                    self.assertTrue((journey.inputs / "update-config.json").is_file())
                    self.assertFalse((journey.inputs / "attempt-count.txt").exists())
                    self.assertEqual(json.loads((journey.inputs / "update-state.json").read_text())["state"], "ERROR")
                if boundary in {"mid-conversion", "cancel-conversion"}:
                    execute = J.Dispatcher.execute
                    interrupted = []

                    def stop(dispatcher, name):
                        if name == "recipe/textures.json" and not interrupted:
                            interrupted.append(name)
                            if boundary == "cancel-conversion":
                                raise InterruptedError("synthetic cancellation at producer boundary")
                            raise OSError("synthetic producer interruption")
                        return execute(dispatcher, name)

                    with patch.object(J.Dispatcher, "execute", stop), self.assertRaises(OSError):
                        journey.run("release-build")
                    failed = json.loads((journey.inputs / "update-state.json").read_text())
                    self.assertEqual(failed["state"], "ERROR")
                    self.assertEqual(failed["pipeline"]["first_failure"]["stage"], "textures")
                    self.assertFalse((journey.inputs / "owner-apk-ready.json").exists())
                    self.assertEqual((journey.inputs / "attempt-count.txt").read_text().splitlines(), ["attempt"])
                if boundary == "ready-before-consent":
                    self.assertEqual(journey.run("release-build")["state"], "READY")
                    self.assertFalse((journey.inputs / "installed-release.json").exists())
                # Every invocation reconstructs the actual Pipeline/Dispatcher from
                # persisted state. This is not an OS kill or power-loss simulation.
                self.assertEqual(journey.run("release-build")["state"], "READY")
                self.assertEqual((journey.inputs / "attempt-count.txt").read_text().splitlines(), ["attempt", "attempt"])
                receipt = install(journey)
                identity = {key: receipt[key] for key in ("sha256", "input_sha256", "payload_sha256", "signer_sha256", "source_sha256", "toolchain_sha256")}
                if baseline is None:
                    baseline = identity
                self.assertEqual(identity, baseline)
                self.assertTrue(receipt["installed_readback_verified"])
                self.assertEqual(original.read_bytes(), b"authored")
                self.assertEqual(profile.read_bytes(), b"untouched authored profile")
