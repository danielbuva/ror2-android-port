"""Coherent synthetic import/build/consent/install/update journey, not device evidence."""

from contextlib import contextmanager
import copy
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from tests.owner_journey_fixture import owner_journey, F, J, U
from tests.owner_journey_android import install
from tests.test_phone_updates import FakeGitHub, encoded


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

    def test_installed_update_then_forward_version_rollback(self):
        with owner_journey() as journey:
            self.assertEqual(journey.run("install-prepare")["state"], "INPUTS_REQUIRED")
            original = journey.inputs / "import/files/original.txt"
            original.parent.mkdir(parents=True)
            original.write_bytes(b"authored")
            self.assertEqual(journey.run("release-build")["state"], "READY")
            first = install(journey)
            first_bytes = Path(first["apk"]).read_bytes()
            journey.candidate["release"] = copy.deepcopy(journey.release)
            journey.candidate["release"].update(version="synthetic-2", version_code=3)
            self.assertEqual(journey.run("release-check", first)["state"], "UPDATE_AVAILABLE")
            self.assertEqual(journey.run("release-build", first)["state"], "READY")
            current = install(journey, first)
            module = U.module
            reversion_codes = []

            def reversion(source, destination, *, version_code, expected_sha256, **kwargs):
                # Packaging is the same explicit synthetic boundary as the build
                # helper: an authored stream, not Android ZIP/manifest evidence.
                self.assertEqual(F.digest(source), expected_sha256)
                self.assertEqual(Path(source).read_bytes(), first_bytes)
                reversion_codes.append(version_code)
                Path(destination).write_bytes(Path(source).read_bytes())

            def modules(name, path):
                return SimpleNamespace(reversion=reversion) if name == "rollback_owner_apk" else module(name, path)

            def sign(owner, release, signing, output, **context):
                self.assertEqual(release, first["release"])
                self.assertGreater(context["install_version_code"], current["version_code"])
                output.mkdir()
                target = output / "signed.apk"
                target.write_bytes(Path(signing["unsigned"]).read_bytes())
                return {"apk_sha256": F.digest(target), "apk_bytes": target.stat().st_size, "signer_sha256": first["signer_sha256"]}

            with (
                patch.object(U, "module", side_effect=modules),
                patch.object(U, "payload_identity", side_effect=F.digest),
                patch.object(U.public(), "verify_envelope", return_value=first["release"]),
                patch.object(U.RELEASE, "sign_release", side_effect=sign),
            ):
                state = journey.run("release-rollback", current)
            self.assertEqual(state["state"], "READY")
            self.assertTrue(state["rollback"])
            self.assertEqual(json.loads((journey.inputs / "installed-release.json").read_text()), current)
            rolled = install(journey, current)
            self.assertGreater(rolled["version_code"], current["version_code"])
            self.assertEqual(rolled["release"], first["release"])
            self.assertEqual(rolled["payload_sha256"], first["payload_sha256"])
            self.assertEqual(rolled["signer_sha256"], current["signer_sha256"])
            self.assertEqual(reversion_codes, [rolled["version_code"]])
            ledger = json.loads((journey.inputs / "work/releases/issued-versions.json").read_text())
            issue = ledger["issues"][str(rolled["version_code"])]
            self.assertEqual((issue["purpose"], issue["status"], issue["publisher_version_code"]), ("rollback", "signed", 2))
            self.assertEqual(Path(first["apk"]).read_bytes(), first_bytes)
            self.assertEqual(original.read_bytes(), b"authored")
            self.assertEqual((journey.inputs / "attempt-count.txt").read_text().splitlines(), ["attempt", "attempt"])

    def test_loopback_acquisition_interruption_retry_and_update(self):
        with owner_journey(acquisition=True) as journey:
            bundle = journey.bundle()
            with FakeGitHub(journey.release, bundle) as server:
                self.assertEqual(journey.run("release-check", transport=server.transport)["state"], "UPDATE_AVAILABLE")
                self.assertNotIn("/public-tools.zip", server.requests)
                open_asset = server.transport.open
                interrupted = []

                def fail_download(url):
                    if url.endswith("public-tools.zip") and not interrupted:
                        interrupted.append(url)

                        @contextmanager
                        def partial_stream():
                            with open_asset(url) as source:
                                reads = []

                                def read(size):
                                    if reads:
                                        raise OSError("synthetic bundle connection interrupted")
                                    reads.append(True)
                                    data = source.read(min(size, 64))
                                    self.assertTrue(data)
                                    return data

                                yield SimpleNamespace(headers=source.headers, read=read)

                        return partial_stream()
                    return open_asset(url)

                with patch.object(server.transport, "open", side_effect=fail_download), self.assertRaises(OSError):
                    journey.run("install-prepare", transport=server.transport)
                self.assertEqual(json.loads((journey.inputs / "update-state.json").read_text())["state"], "ERROR")
                self.assertEqual(list((journey.inputs / "work/releases/downloads").iterdir()), [])
                self.assertFalse((journey.inputs / "attempt-count.txt").exists())
                self.assertEqual(journey.run("install-prepare", transport=server.transport)["state"], "INPUTS_REQUIRED")
                original = journey.inputs / "import/files/original.txt"
                original.parent.mkdir(parents=True)
                original.write_bytes(b"authored")
                installed = None
                for version in (2, 3):
                    if installed:
                        journey.candidate["release"] = copy.deepcopy(journey.release)
                        journey.candidate["release"].update(version="synthetic-2", version_code=version)
                        server.paths["/release.json"] = encoded(journey.candidate["release"])
                        server.metadata["tag_name"] = "owner-v3"
                        server.paths["/latest"] = encoded(server.metadata)
                        self.assertEqual(journey.run("release-check", installed, transport=server.transport)["state"], "UPDATE_AVAILABLE")
                    journey.events.clear()
                    self.assertEqual(journey.run("release-build", installed, transport=server.transport)["state"], "READY")
                    states = [event["state"] for event in journey.events]
                    self.assertLess(states.index("DOWNLOADING"), states.index("VERIFYING"))
                    self.assertLess(states.index("VERIFYING"), states.index("BUILDING"))
                    installed = install(journey, installed)
                self.assertEqual((journey.inputs / "attempt-count.txt").read_text().splitlines(), ["attempt", "attempt"])
                self.assertFalse(list((journey.inputs / "work/releases/downloads").glob(".download-*")))
                self.assertEqual(original.read_bytes(), b"authored")

    def test_consent_and_result_refusal_rebuilds_without_false_install(self):
        for outcome in ("declined", "failed", "missing", "mismatch"):
            with self.subTest(outcome=outcome), owner_journey() as journey:
                self.assertEqual(journey.run("install-prepare")["state"], "INPUTS_REQUIRED")
                original = journey.inputs / "import/files/original.txt"
                original.parent.mkdir(parents=True)
                original.write_bytes(b"authored")
                self.assertEqual(journey.run("release-build")["state"], "READY")
                first = install(journey)
                prior_receipt = (journey.inputs / "installed-release.json").read_bytes()
                journey.candidate["release"] = copy.deepcopy(journey.release)
                journey.candidate["release"].update(version="synthetic-2", version_code=3)
                journey.run("release-check", first)
                self.assertEqual(journey.run("release-build", first)["state"], "READY")
                refused_code = json.loads((journey.inputs / "owner-apk-ready.json").read_text())["version_code"]
                unchanged = install(journey, first, outcome=outcome)
                self.assertEqual(unchanged, first)
                self.assertEqual(json.loads((journey.inputs / "installed-release.json").read_text()), json.loads(prior_receipt))
                self.assertFalse((journey.inputs / "pending-install.json").exists())
                self.assertEqual(journey.run("release-build", first)["state"], "READY")
                retry = json.loads((journey.inputs / "owner-apk-ready.json").read_text())
                self.assertGreater(retry["version_code"], refused_code)
                installed = install(journey, first)
                self.assertTrue(installed["installed_readback_verified"])
                self.assertEqual(installed["release"]["version_code"], 3)
                self.assertEqual(installed["signer_sha256"], first["signer_sha256"])
                self.assertEqual(original.read_bytes(), b"authored")
                self.assertEqual((journey.inputs / "attempt-count.txt").read_text().splitlines(), ["attempt", "attempt"])
