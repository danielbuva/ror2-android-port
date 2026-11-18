"""Coherent synthetic import/build/consent/install/update journey, not device evidence."""

import copy
import json
import unittest
from tests.owner_journey_fixture import owner_journey, F
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
