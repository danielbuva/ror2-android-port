import hashlib
import io
import json
import runpy
import sys
import tempfile
import types
from argparse import Namespace
from contextlib import redirect_stdout
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts/lab"))

from session_cleanup_check import (
    SPINE_ID,
    cleanup_contract,
    abandon_contract,
    abandon_control_coordinates,
    abandon_observation_failures,
    ending_contract,
    selection,
    survivor_identity_failures,
    matches_run,
    menu_start_coordinates,
    parse_display_size,
    parse_window_rotation,
    report_errors,
    restart_contract,
    skill_variant_failures,
    combat_output_lifecycle,
    first_ready_observer_contract,
    runtime_stop,
    restart_coordinates,
    selector_action,
)
import session_cleanup_check as runner
from actions import ACTIONS


def live_report(**changes):
    report = {
        "pid": 314,
        "attempt": "attempt-1",
        "id": SPINE_ID,
        "selectedSurvivor": "Commando",
        "developerSurvivorOverride": False,
        "settings": {
            "ready": True,
            "visible": False,
            "canEndRun": False,
            "buttonX": 1167.5,
            "buttonY": 30.0,
            "endRunButtonX": 0.0,
            "endRunButtonY": 0.0,
            "screenWidth": 1280,
            "screenHeight": 800,
        },
        "session": 1,
        "phase": "integrated-world-playing",
        "integratedWorld": True,
        "teleporterLoop": True,
        "stage": {"scene": "lakes"},
        "stageProgress": {"current": "lakes", "transitions": 0, "transporting": False},
        "debugOptions": {
            "invincibility": False,
            "highDamage": False,
            "fastCharge": False,
            "movementBoost": False,
            "jumpBoost": False,
        },
        "debugAcceleration": {
            "everAssisted": True,
            "normalGameAcceptanceEligible": False,
            "active": {
                "invincibility": False,
                "highDamage": False,
                "fastCharge": False,
                "movementBoost": False,
                "jumpBoost": False,
            },
            "events": [{"toggle": "diagnosticInput", "enabled": True}],
        },
        "world": {"seconds": 10.0, "ready": True, "health": 100.0, "diagnosticInputEver": True},
        "profile": {
            "ready": True,
            "appliedRuns": 13,
            "earnedUnlocks": 2,
            "availableEarnedUnlocks": 2,
        },
        "moonMission": False,
    }
    report.update(changes)
    world = report.get("world")
    if isinstance(world, dict) and "maxHealth" not in world and world.get("health", 0) > 0:
        world["maxHealth"] = 100.0
    return report


def completed_report(**overrides):
    report = live_report(
        phase="complete",
        success=True,
        cleanup=True,
        world={"cleaned": True, "diagnosticInputEver": True},
        objective={
            "cleaned": True,
            "nativeHostTeardownObserved": True,
            "nativeHostTeardownServerActive": True,
            "nativeHostTeardownSynchronous": True,
            "nativeHostTeardownPreAwake": False,
            "nativeHostCombatSquads": 1,
            "nativeHostDeathListenersBefore": 1,
            "nativeHostDeathListenersAfter": 0,
            "nativeHostSummonListenersBefore": 1,
            "nativeHostSummonListenersAfter": 0,
        },
        playerDefeat={"deathEvents": 1, "deathEntered": True, "bodyDestroyed": True},
        results={"persisted": True, "clientEnding": True},
        profile={
            "ready": True,
            "assistedExcluded": True,
            "resultApplied": False,
            "appliedRuns": 13,
            "earnedUnlocks": 2,
            "availableEarnedUnlocks": 2,
        },
    )
    report.update(overrides)
    return report


def abandoned_report(survivor="Engi"):
    report = completed_report(
        selectedSurvivor=survivor,
        developerSurvivorOverride=survivor not in runner.FREE_SURVIVORS,
        playerDefeat={"deathEvents": 0, "deathEntered": False, "bodyDestroyed": False},
        results={"ready": True, "serverEnding": False, "clientEnding": False, "reportGenerated": False, "persisted": False},
        settings={"sessionAbandoned": True},
        world={"cleaned": True, "diagnosticInputEver": True, "engiShieldGuardPrepared": survivor == "Engi", "engiShieldGuardReleased": survivor == "Engi"},
        profile={
            "ready": True,
            "resultApplied": False,
            "appliedRuns": 13,
            "earnedUnlocks": 2,
            "availableEarnedUnlocks": 2,
        },
    )
    report["objective"].update(
        {
            "nativeHostTeardownObserved": True,
            "nativeHostTeardownServerActive": True,
            "nativeHostTeardownSynchronous": True,
            "nativeHostTeardownPreAwake": False,
            "nativeHostCombatSquads": 1,
            "nativeHostDeathListenersBefore": 1,
            "nativeHostDeathListenersAfter": 0,
            "nativeHostSummonListenersBefore": 1,
            "nativeHostSummonListenersAfter": 0,
        }
    )
    return report


SYNTHETIC_SERIAL = "synthetic-device"


class FakeDevice:
    serial = SYNTHETIC_SERIAL

    def __init__(self, work, reports, log_error=False, foreign_selector=False, survivor="Commando", ending="loss", completed_override=None):
        self.runtime = "/storage/emulated/0/Android/data/dev.ror2lab.arm64/files"
        self.remote = {}
        self.reports = list(reports)
        self.total_reports = len(self.reports)
        self.log_error = log_error
        self.foreign_selector = foreign_selector
        self.survivor = survivor
        self.ending = ending
        self.completed_override = completed_override
        self.pid = "314"
        self.alive = False
        self.taps = []
        self.tap_report_indices = []
        self.tap_completion_present = []
        self.display_states = []
        self.completed_path = self.runtime + "/movement-completed-session-1.json"
        self.report_path = self.runtime + "/movement-batch-" + SPINE_ID + ".json"
        self.selector_path = self.runtime + "/movement-batch-selection.json"
        self.evidence_root = work / "receipts" / self.serial

    @property
    def settings(self):
        return {"storage_mode": "internal"}

    def owned(self):
        return {
            "storage": {"mode": "internal"},
            "package_path": "/data/app/dev.ror2lab.arm64/base.apk",
            "apk_sha256": self.apk_hash,
        }

    def storage(self):
        return {"mode": "internal"}

    def read_receipt(self, _name):
        return {"persistentDataPath": self.runtime}

    def evidence_directory(self, *components):
        return self.evidence_root.joinpath(*components)

    def cmd(self, *args, **_kwargs):
        if args[0] == "push":
            self.remote[args[2]] = Path(args[1]).read_text()

    def launch(self):
        self.alive = True
        return {"pid": self.pid}

    def display(self, awake):
        self.display_states.append(awake)
        return True

    def sh(self, *args, **_kwargs):
        if args[:2] == ("sh", "-c"):
            path = args[2].split("[ -L ", 1)[1].split(" ];", 1)[0]
            return "file" if path in self.remote else "absent"
        if args[0] == "cat":
            path = args[1]
            if path == self.report_path and self.alive and self.reports:
                report = self.reports.pop(0)
                if self.foreign_selector and report.get("session") == 2:
                    self.remote[self.selector_path] = json.dumps({"id": "foreign", "attempt": "foreign"})
                return json.dumps(report)
            return self.remote.get(path, "")
        if args[:2] == ("rm", "-f"):
            self.remote.pop(args[2], None)
            return ""
        if args[0] == "pidof":
            return self.pid if self.alive else ""
        if args[0] == "am" and args[1] == "force-stop":
            self.alive = False
            return ""
        if args[0] == "input" and args[1] == "tap":
            point = (int(args[2]), int(args[3]))
            self.taps.append(point)
            self.tap_report_indices.append(self.total_reports - len(self.reports))
            self.tap_completion_present.append(self.completed_path in self.remote)
            completes_abandon = self.ending == "abandon" and point == (430, 512)
            completes_loss = self.ending == "loss" and point == (207, 420)
            if completes_abandon or completes_loss:
                if self.completed_override is not None:
                    self.remote[self.completed_path] = self.completed_override
                else:
                    completed = (
                        abandoned_report(self.survivor)
                        if self.ending == "abandon"
                        else completed_report(
                            selectedSurvivor=self.survivor,
                            developerSurvivorOverride=self.survivor not in runner.FREE_SURVIVORS,
                        )
                    )
                    self.remote[self.completed_path] = json.dumps(completed)
            return ""
        if args[:2] == ("wm", "size"):
            return "Physical size: 1280x800\n"
        if args[:3] == ("dumpsys", "window", "displays"):
            return "mDisplayRotation=ROTATION_0\n"
        if args[0] == "logcat":
            return "FINAL" if self.log_error else ""
        return ""


def run_fake_check(
    reports, *, log_error=False, foreign_selector=False, host_deadline_seconds=600, survivor="Commando", ending="loss", clock_step=0.1, completed_override=None
):
    temp = tempfile.TemporaryDirectory()
    base = Path(temp.name)
    work = base / "work"
    apk = base / "current.apk"
    apk.write_bytes(b"synthetic apk artifact")
    apk_hash = hashlib.sha256(apk.read_bytes()).hexdigest()
    (work / "config").mkdir(parents=True)
    config = work / "lab-project/Assets/LabLoadingScene/Resources"
    config.mkdir(parents=True)
    (work / "config/current-build.json").write_text(
        json.dumps(
            {
                "success": True,
                "apk": str(apk),
                "apk_sha256": apk_hash,
            }
        )
    )
    (config / "MovementBatchProbe.json").write_text(json.dumps({"attempt": "mutable-project-attempt"}))
    device = FakeDevice(
        work, reports, log_error=log_error, foreign_selector=foreign_selector, survivor=survivor, ending=ending, completed_override=completed_override
    )
    device.apk_hash = apk_hash
    device.remote[device.report_path] = json.dumps({"attempt": "stale", "session": 1})
    device.remote[device.completed_path] = json.dumps({"attempt": "stale", "session": 1})
    clock = [0.0]

    def monotonic():
        value = clock[0]
        clock[0] += clock_step
        return value

    patches = (
        mock.patch.object(runner, "ROOT", base),
        mock.patch.object(runner, "WORK", work),
        mock.patch.object(runner, "SessionCleanupDevice", return_value=device),
        mock.patch.object(runner, "attempt_from_installed", return_value="attempt-1"),
        mock.patch.object(runner, "now", return_value="synthetic-run"),
        mock.patch.object(runner.time, "monotonic", side_effect=monotonic),
        mock.patch.object(runner.time, "sleep", return_value=None),
        mock.patch.object(runner, "current_errors", side_effect=lambda logs, _pid: ["late log failure"] if logs == "FINAL" else []),
        mock.patch.object(runner, "HOST_DEADLINE_SECONDS", host_deadline_seconds),
    )
    with ExitStack() as stack:
        for patcher in patches:
            stack.enter_context(patcher)
        try:
            result = runner.check_session_cleanup(survivor=survivor, ending=ending)
            error = None
        except RuntimeError as exc:
            result = None
            error = exc
    evidence = work / "receipts" / device.serial / "experiments/session-cleanup/synthetic-run"
    return temp, device, result, error, evidence


def ordinary_start_report():
    report = live_report(
        session=1,
        phase="offline-start-menu",
        integratedWorld=False,
        teleporterLoop=False,
        hud={"menuStartX": 100, "menuStartY": 200, "screenWidth": 1280, "screenHeight": 800},
    )
    report.pop("profile")
    return report


def session2_offline_menu_report():
    report = ordinary_start_report()
    report["session"] = 2
    return report


def session_one_defeat_report():
    return live_report(
        session=1,
        phase="commando-defeated",
        results={"persisted": True, "clientEnding": True},
        hud={"screenWidth": 1280, "screenHeight": 800},
    )


class SessionCleanupCheckTests(unittest.TestCase):
    def test_cli_accepts_skill_variants_for_existing_three_actions(self):
        main_path = Path(__file__).resolve().parents[1] / "scripts/lab/main.py"
        for action in ("survivor-kit-check", "session-cleanup-check", "session-abandon-check"):
            with self.subTest(action=action):
                captured = []
                fake_actions = types.ModuleType("actions")
                fake_actions.dispatch = lambda args: captured.append(args)
                fake_actions.print_actions = lambda: None
                argv = [
                    str(main_path), "prototype", "--action", action, "--target", "Toolbot",
                    "--skill-variants", "/ignored/variants.json",
                ]
                with mock.patch.object(sys, "argv", argv), mock.patch.dict(sys.modules, {"actions": fake_actions}):
                    runpy.run_path(str(main_path), run_name="__main__")
                self.assertEqual(len(captured), 1)
                self.assertEqual(captured[0].skill_variants, "/ignored/variants.json")

    def test_survivor_target_is_base_only_and_locked_choices_are_diagnostic(self):
        self.assertEqual(selection("attempt-1")["selectedSurvivor"], "Commando")
        self.assertFalse(selection("attempt-1")["developerSurvivorOverride"])
        engi = selection("attempt-1", "Engi")
        self.assertEqual(engi["selectedSurvivor"], "Engi")
        self.assertTrue(engi["developerSurvivorOverride"])
        self.assertEqual(set(engi["debugOptions"]) - {"purpose"}, set(runner.DEBUG_ASSISTS))
        self.assertTrue(all(value is False for key, value in engi["debugOptions"].items() if key != "purpose"))
        with self.assertRaises(ValueError):
            selection("attempt-1", "Railgunner")

    def test_survivor_identity_requires_exact_hero_and_override(self):
        report = live_report()
        self.assertEqual(survivor_identity_failures(report, "Commando"), [])
        self.assertTrue(survivor_identity_failures({**report, "selectedSurvivor": "Engi"}, "Commando"))
        self.assertTrue(survivor_identity_failures({**report, "developerSurvivorOverride": True}, "Commando"))
        engi = {**report, "selectedSurvivor": "Engi", "developerSurvivorOverride": True}
        self.assertEqual(survivor_identity_failures(engi, "Engi"), [])
        self.assertTrue(survivor_identity_failures({**engi, "developerSurvivorOverride": False}, "Engi"))

    def test_action_handler_preserves_json_output_and_maps_lab_default(self):
        handler = ACTIONS["session-cleanup-check"].handler
        calls = []

        def fake_check(**kwargs):
            calls.append(kwargs)
            return {"success": True}

        output = io.StringIO()
        with redirect_stdout(output):
            handler(fake_check, {}, Namespace(target="lab"))
        self.assertEqual(calls, [{}])
        self.assertEqual(json.loads(output.getvalue()), {"success": True})
        with redirect_stdout(io.StringIO()):
            handler(fake_check, {}, Namespace(target="Engi"))
        self.assertEqual(calls[-1], {"survivor": "Engi"})
        with redirect_stdout(io.StringIO()):
            ACTIONS["session-abandon-check"].handler(fake_check, dict(ACTIONS["session-abandon-check"].kwargs), Namespace(target="Engi"))
        self.assertEqual(calls[-1], {"ending": "abandon", "survivor": "Engi"})
        with redirect_stdout(io.StringIO()):
            ACTIONS["session-cleanup-check"].handler(
                fake_check, {}, Namespace(target="Toolbot", skill_variants="/ignored/variants.json")
            )
        self.assertEqual(calls[-1], {"survivor": "Toolbot", "skill_variants": "/ignored/variants.json"})

    def test_abandon_action_is_distinct_and_original_action_keeps_loss_default(self):
        self.assertEqual(ACTIONS["session-cleanup-check"].kwargs, {})
        self.assertEqual(ACTIONS["session-abandon-check"].kwargs, {"ending": "abandon"})
        self.assertIn("without an original loss/result", ACTIONS["session-abandon-check"].help)
        self.assertIn("60 s", ACTIONS["session-abandon-check"].help)
        self.assertIn("original first-stage loss", ACTIONS["session-cleanup-check"].help)

    def test_report_identity_requires_process_attempt_and_owner(self):
        report = live_report()
        self.assertTrue(matches_run(report, 314, "attempt-1", 1))
        self.assertFalse(matches_run(report, 315, "attempt-1", 1))
        self.assertFalse(matches_run(report, 314, "other-attempt", 1))
        self.assertFalse(matches_run({**report, "id": "other"}, 314, "attempt-1", 1))

    def test_first_stage_exit_and_runtime_error_stop_immediately(self):
        report = live_report(stage={"scene": "goolake"})
        self.assertEqual(runtime_stop(report, 314, "attempt-1"), "outside-first-stage-contract")
        report = live_report(stage={"scene": None})
        self.assertEqual(runtime_stop(report, 314, "attempt-1"), "outside-first-stage-contract")
        report = live_report(firstFailure="native callback failed")
        self.assertEqual(runtime_stop(report, 314, "attempt-1"), "first-failure")
        self.assertEqual(runtime_stop(live_report(moonMission=True), 314, "attempt-1"), "outside-first-stage-contract")
        self.assertIsNone(runtime_stop(live_report(pid=999), 314, "attempt-1"))

    def test_nested_current_report_errors_fail_closed(self):
        report = live_report(results={"ledgerRecoveryError": "ledger write failed"})
        self.assertEqual(runtime_stop(report, 314, "attempt-1"), "first-failure")
        self.assertIn("results.ledgerRecoveryError: ledger write failed", report_errors(report))
        report = live_report(
            stageProgress={
                "current": "lakes",
                "transitions": 0,
                "transporting": False,
                "sirenEncounters": [{"error": "encounter cleanup failed"}],
            }
        )
        self.assertIn(
            "stageProgress.sirenEncounters[0].error: encounter cleanup failed",
            report_errors(report),
        )

    def test_missing_integrated_teleporter_contract_is_not_counted_as_a_run(self):
        report = live_report(teleporterLoop=False)
        self.assertEqual(runtime_stop(report, 314, "attempt-1"), "outside-first-stage-contract")
        menu = live_report(phase="offline-start-menu", integratedWorld=False, teleporterLoop=False)
        self.assertIsNone(runtime_stop(menu, 314, "attempt-1"))

    def test_skill_variant_selector_is_optional_and_reused_by_launch_selection(self):
        request = {
            "survivor": "Toolbot",
            "entries": [{"componentIndex": 1, "familyCatalogIndex": 41, "variantIndex": 1, "skillCatalogIndex": 102}],
        }
        plain = selection("attempt-1", "Toolbot")
        self.assertNotIn("developerSkillVariantOverride", plain)
        selected = selection("attempt-1", "Toolbot", request)
        self.assertEqual(selected["developerSkillVariantOverride"], request)
        self.assertIn("assisted", selected["debugOptions"]["purpose"])
        self.assertIn("no profile or unlock changes", selected["debugOptions"]["purpose"])

    def test_variant_contract_checks_pre_mutation_identity_effective_vector_live_fields_and_marker(self):
        request = {
            "survivor": "Toolbot",
            "entries": [{"componentIndex": 1, "familyCatalogIndex": 41, "variantIndex": 1, "skillCatalogIndex": 102}],
        }
        pre_rows, live_rows = [], []
        for component in range(5):
            variants = [{"variantIndex": index, "skillCatalogIndex": 100 + component + index, "skillName": ""} for index in range(3)]
            chosen = 1 if component == 1 else 0
            common = {
                "componentIndex": component,
                "familyCatalogIndex": 40 + component,
                "selectedLoadoutVariantIndex": chosen,
                "selectedLoadoutSkillCatalogIndex": 100 + component + chosen,
                "runtimeSkillCatalogIndex": 100 + component + chosen,
                "runtimeDefinitionStatus": "matches-selected-native-loadout",
                "variants": variants,
            }
            before = dict(common, selectedLoadoutVariantIndex=0, selectedLoadoutSkillCatalogIndex=100 + component,
                          runtimeSkillCatalogIndex=-1, runtimeDefinitionStatus="uninitialized-or-unassigned")
            pre_rows.append(before)
            live_rows.append(common)
        inventory = {"status": "available", "bodyIndex": 7, "selectionSource": "native-master-loadout-pre-spawn", "components": pre_rows}
        live_inventory = {"status": "available", "bodyIndex": 7, "selectionSource": "native-master-loadout-live", "components": live_rows}
        report = live_report(
            selectedSurvivor="Toolbot",
            developerSurvivorOverride=True,
            developerSkillVariantOverride=request,
            developerSkillVariantAssisted=True,
            developerSkillVariantOverrideReport={"requested": True, "status": "applied", "applied": True, "assisted": True,
                                                 "effectiveSkillVariants": [0, 1, 0, 0, 0], "skillVariantInventory": inventory},
            survivorSkills={"skillVariantInventory": live_inventory},
        )
        self.assertEqual(skill_variant_failures(report, request), [])
        missing_marker = dict(report, developerSkillVariantAssisted=False)
        self.assertIn("per-run skill-variant assisted session marker is absent", skill_variant_failures(missing_marker, request))
        wrong_effective = dict(report, developerSkillVariantOverrideReport={**report["developerSkillVariantOverrideReport"], "effectiveSkillVariants": [0, 0, 0, 0, 0]})
        self.assertTrue(any("effective native" in failure for failure in skill_variant_failures(wrong_effective, request)))
        wrong_live = dict(live_inventory, components=[dict(row) for row in live_rows])
        wrong_live["components"][1]["runtimeSkillCatalogIndex"] = 101
        wrong_report = dict(report, survivorSkills={"skillVariantInventory": wrong_live})
        self.assertIn("post-spawn setup SkillDef snapshot does not match the requested effective variant", skill_variant_failures(wrong_report, request))

    def test_skill_variant_contract_rejects_wrong_catalog_identity_and_selector(self):
        request = {"survivor": "Toolbot", "entries": [{"componentIndex": 0, "familyCatalogIndex": 40, "variantIndex": 1, "skillCatalogIndex": 101}]}
        report = {"developerSkillVariantOverride": {"survivor": "Toolbot", "entries": []}}
        self.assertIn("per-run skill-variant selector differs", skill_variant_failures(report, request))
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "invalid-variants.json"
            path.write_text(json.dumps(request))
            with mock.patch.object(runner, "SessionCleanupDevice") as device:
                with self.assertRaises(ValueError):
                    runner.check_session_cleanup(survivor="Engi", skill_variants=str(path))
                device.assert_not_called()

    def test_combat_observer_lifecycle_reports_unavailable_or_validates_both_edges(self):
        for malformed in ([], "invalid", None, {"world": [1]}):
            with self.subTest(malformed=malformed):
                state, errors = combat_output_lifecycle(malformed, expect_cleaned=True)
                self.assertEqual(state["status"], "invalid")
                self.assertTrue(errors)
        unavailable, failures = combat_output_lifecycle(live_report(), expect_cleaned=True)
        self.assertEqual(unavailable["status"], "unavailable")
        self.assertEqual(failures, [])
        completed = live_report(world={"survivorCombatOutputs": {"attached": False, "cleaned": True, "inert": False}})
        self.assertEqual(combat_output_lifecycle(completed, expect_cleaned=True)[0]["status"], "valid")
        self.assertTrue(combat_output_lifecycle(live_report(world={"survivorCombatOutputs": {"attached": True, "cleaned": False, "inert": True}}), expect_cleaned=False)[1])
        healthy = live_report(world={"survivorCombatOutputs": {"attached": True, "cleaned": False, "inert": False, "observerError": ""}})
        self.assertEqual(combat_output_lifecycle(healthy, expect_cleaned=False)[0]["status"], "valid")

    def test_first_ready_observer_check_waits_for_body_and_engi_guard_then_refuses_fault(self):
        startup = live_report(
            selectedSurvivor="Engi",
            developerSurvivorOverride=True,
            world={"ready": False, "health": 0, "maxHealth": 0, "diagnosticInputEver": False,
                   "engiShieldGuardPrepared": False,
                   "survivorCombatOutputs": {"attached": False, "cleaned": False, "inert": True, "observerError": "early"}},
        )
        self.assertEqual(first_ready_observer_contract(startup, "Engi"), (None, []))
        ready_fault = live_report(
            selectedSurvivor="Engi",
            developerSurvivorOverride=True,
            world={"ready": True, "health": 130, "maxHealth": 130, "diagnosticInputEver": True,
                   "engiShieldGuardPrepared": True,
                   "survivorCombatOutputs": {"attached": False, "cleaned": True, "inert": True, "observerError": "detach failed"}},
        )
        state, failures = first_ready_observer_contract(ready_fault, "Engi")
        self.assertEqual(state["status"], "invalid")
        self.assertTrue(any("first-ready session combat-output observer" in failure for failure in failures))
        healthy = dict(ready_fault, world={**ready_fault["world"], "survivorCombatOutputs": {
            "attached": True, "cleaned": False, "inert": False, "observerError": ""}})
        self.assertEqual(first_ready_observer_contract(healthy, "Engi")[0]["status"], "valid")

    def test_completed_and_restarted_contracts_gate_variant_marker_and_available_observer(self):
        counts = {"appliedRuns": 13, "earnedUnlocks": 2, "availableEarnedUnlocks": 2}
        request = {
            "survivor": "Commando",
            "entries": [{"componentIndex": 0, "familyCatalogIndex": 40, "variantIndex": 1, "skillCatalogIndex": 101}],
        }
        completed = completed_report()
        completed["world"]["survivorCombatOutputs"] = {
            "attached": False, "cleaned": True, "inert": True, "observerError": "detach failed"
        }
        failures = cleanup_contract(completed, 314, "attempt-1", counts, skill_variant_override=request)
        self.assertTrue(any("assisted session marker is absent" in failure for failure in failures))
        self.assertTrue(any("completed-session combat-output observer" in failure for failure in failures))
        restarted = live_report(session=2, world={"survivorCombatOutputs": {"attached": False, "cleaned": True}})
        failures = restart_contract(restarted, 314, "attempt-1", counts, skill_variant_override=request)
        self.assertTrue(any("assisted session marker is absent" in failure for failure in failures))
        self.assertTrue(any("restarted-session combat-output observer" in failure for failure in failures))

    def test_completed_session_requires_active_native_listener_retirement_and_real_loss(self):
        counts = {"appliedRuns": 13, "earnedUnlocks": 2, "availableEarnedUnlocks": 2}
        self.assertEqual(cleanup_contract(completed_report(), 314, "attempt-1", counts), [])
        report = completed_report()
        report["objective"]["nativeHostSummonListenersAfter"] = 1
        self.assertIn("native summon listener counts did not retire from 1 to 0", cleanup_contract(report, 314, "attempt-1", counts))
        report = completed_report()
        report["objective"]["nativeHostTeardownPreAwake"] = True
        self.assertIn("native teleporter never reached its active lifecycle", cleanup_contract(report, 314, "attempt-1", counts))
        report = completed_report()
        report["playerDefeat"]["deathEvents"] = 0
        self.assertIn("session did not finish one original player death", cleanup_contract(report, 314, "attempt-1", counts))
        report = completed_report()
        report["results"]["error"] = "late save failure"
        self.assertIn("results.error: late save failure", cleanup_contract(report, 314, "attempt-1", counts))
        report = completed_report(firstFailure="primary failure")
        self.assertIn("firstFailure: primary failure", cleanup_contract(report, 314, "attempt-1", counts))
        report = completed_report()
        report["profile"]["assistedExcluded"] = False
        self.assertIn("assisted loss was not excluded from profile result application", cleanup_contract(report, 314, "attempt-1", counts))
        report = completed_report()
        report["profile"]["earnedUnlocks"] += 1
        self.assertIn("applied-run or earned-unlock counts changed/missing", cleanup_contract(report, 314, "attempt-1", counts))

    def test_restart_requires_same_process_second_session_on_lakes(self):
        report = live_report(session=2)
        counts = {"appliedRuns": 13, "earnedUnlocks": 2, "availableEarnedUnlocks": 2}
        self.assertEqual(restart_contract(report, 314, "attempt-1", counts), [])
        self.assertIn("stage geometry identity is not Lakes", restart_contract({**report, "stage": {"scene": "goolake"}}, 314, "attempt-1", counts))

    def test_completed_session_requires_explicit_profile_exclusion_booleans(self):
        counts = {"appliedRuns": 13, "earnedUnlocks": 2, "availableEarnedUnlocks": 2}
        for field, values in (("assistedExcluded", (None, "true", 1)), ("resultApplied", (None, "false", 0))):
            for value in values:
                with self.subTest(field=field, value=value):
                    report = completed_report()
                    report["profile"][field] = value
                    self.assertIn("assisted loss was not excluded from profile result application", cleanup_contract(report, 314, "attempt-1", counts))
            report = completed_report()
            del report["profile"][field]
            self.assertIn("assisted loss was not excluded from profile result application", cleanup_contract(report, 314, "attempt-1", counts))

    def test_restart_requires_a_ready_observed_integrated_tick(self):
        report = live_report(
            session=2,
            world={
                "seconds": 0.0,
                "ready": False,
                "health": 0.0,
                "diagnosticInputEver": False,
            },
        )
        counts = {"appliedRuns": 13, "earnedUnlocks": 2, "availableEarnedUnlocks": 2}
        self.assertFalse(runner.session2_ready(report))
        failures = restart_contract(report, 314, "attempt-1", counts)
        self.assertIn("second session did not reach a ready observed integrated tick", failures)

    def test_restart_tap_requires_reported_display_grid_to_match_android(self):
        report = live_report(hud={"screenWidth": 1280, "screenHeight": 800})
        self.assertEqual(parse_display_size("Physical size: 1280x800\n"), (1280, 800))
        self.assertEqual(parse_window_rotation("mDisplayRotation=ROTATION_0\n"), 0)
        displays = "mDisplayRotation=ROTATION_0\n"
        self.assertEqual(restart_coordinates(report, "Physical size: 1280x800\n", displays), (207, 420))
        self.assertIsNone(restart_coordinates(report, "Physical size: 800x1280\n", displays))
        self.assertIsNone(restart_coordinates(report, "Physical size: 1280x800\n", ""))
        self.assertIsNone(restart_coordinates(report, "Physical size: 1280x800\n", "mDisplayRotation=ROTATION_1\n"))
        self.assertIsNone(restart_coordinates(live_report(), "Physical size: 1280x800\n", displays))

    def test_restart_tap_maps_rotated_physical_portrait_to_logical_landscape(self):
        report = live_report(hud={"screenWidth": 1280, "screenHeight": 960})
        raw_rotation = "mDisplayRotation=ROTATION_90\nmDisplayRotation=ROTATION_90\n"
        mapping = runner.restart_mapping(report, "Physical size: 960x1280\n", raw_rotation)
        self.assertEqual(mapping["rotation_degrees"], 90)
        self.assertEqual(mapping["physical_size"], (960, 1280))
        self.assertEqual(mapping["logical_size"], (1280, 960))
        self.assertEqual(mapping["coordinates"], (207, 420))
        self.assertIsNone(
            runner.restart_mapping(
                report,
                "Physical size: 960x1280\n",
                "mDisplayRotation=ROTATION_90\nmDisplayRotation=ROTATION_0\n",
            )["coordinates"]
        )

    def test_menu_start_uses_only_finite_in_bounds_report_coordinates(self):
        report = live_report(hud={"menuStartX": 100.4, "menuStartY": 200.6, "screenWidth": 1280, "screenHeight": 800})
        self.assertEqual(menu_start_coordinates(report), (100, 201))
        self.assertIsNone(menu_start_coordinates(live_report(hud={"menuStartX": -1, "menuStartY": 2, "screenWidth": 1280, "screenHeight": 800})))

    def test_selector_cleanup_preserves_malformed_or_foreign_data(self):
        owned = json.dumps({"attempt": "attempt-1", "id": SPINE_ID})
        foreign = json.dumps({"attempt": "other", "id": SPINE_ID})
        self.assertEqual(selector_action("absent", "", "attempt-1"), "none")
        self.assertEqual(selector_action("file", owned, "attempt-1"), "remove-owned")
        self.assertEqual(selector_action("file", "{", "attempt-1"), "preserve-malformed")
        self.assertEqual(selector_action("file", foreign, "attempt-1"), "preserve-foreign")
        self.assertEqual(selector_action("symlink", "", "attempt-1"), "preserve-invalid-path")
        self.assertEqual(selector_action("other", "", "attempt-1"), "preserve-invalid-path")

    def test_abandon_contract_requires_real_cleanup_without_native_loss_or_result(self):
        counts = {"appliedRuns": 13, "earnedUnlocks": 2, "availableEarnedUnlocks": 2}
        report = abandoned_report("Engi")
        self.assertEqual(abandon_contract(report, 314, "attempt-1", counts, "Engi"), [])
        bad = dict(report, results={"ready": True, "serverEnding": True, "clientEnding": False, "reportGenerated": True, "persisted": True})
        self.assertTrue(any("no-ending/no-result" in x for x in abandon_contract(bad, 314, "attempt-1", counts, "Engi")))
        bad = dict(report, results={"ready": True, "serverEnding": False, "reportGenerated": False, "persisted": False})
        self.assertTrue(any("no-ending/no-result" in x for x in abandon_contract(bad, 314, "attempt-1", counts, "Engi")))
        bad = dict(report, results={"ready": True, "serverEnding": False, "clientEnding": False, "reportGenerated": False, "persisted": False})
        bad["objective"]["nativeHostDeathListenersAfter"] = 1
        self.assertTrue(any("native death listener counts" in x for x in abandon_contract(bad, 314, "attempt-1", counts, "Engi")))
        bad = dict(report, settings={"sessionAbandoned": False})
        self.assertTrue(any("abandon action" in x for x in abandon_contract(bad, 314, "attempt-1", counts, "Engi")))
        bad = dict(report, world={"cleaned": False})
        self.assertTrue(any("world/template cleanup" in x for x in abandon_contract(bad, 314, "attempt-1", counts, "Engi")))
        bad = dict(report, objective={"cleaned": True, "nativeHostTeardownObserved": False})
        self.assertTrue(any("native teleporter teardown" in x for x in abandon_contract(bad, 314, "attempt-1", counts, "Engi")))
        bad = dict(report, stageProgress={"current": "goolake", "transitions": 1, "transporting": False})
        self.assertTrue(any("stage" in x or "transition" in x for x in abandon_contract(bad, 314, "attempt-1", counts, "Engi")))
        bad = dict(report, playerDefeat={"deathEvents": 1, "deathEntered": True, "bodyDestroyed": True})
        self.assertTrue(any("no-native-death" in x for x in abandon_contract(bad, 314, "attempt-1", counts, "Engi")))
        bad = dict(report, playerDefeat={"deathEvents": 0, "deathEntered": False})
        self.assertTrue(any("no-native-death" in x for x in abandon_contract(bad, 314, "attempt-1", counts, "Engi")))
        bad = dict(report, profile={"ready": True, "resultApplied": True, "appliedRuns": 13, "earnedUnlocks": 2, "availableEarnedUnlocks": 2})
        self.assertTrue(any("no-profile-result" in x for x in abandon_contract(bad, 314, "attempt-1", counts, "Engi")))
        bad = dict(report, profile={"ready": True, "appliedRuns": 13, "earnedUnlocks": 2, "availableEarnedUnlocks": 2})
        self.assertTrue(any("no-profile-result" in x for x in abandon_contract(bad, 314, "attempt-1", counts, "Engi")))

    def test_abandon_waits_for_ready_living_first_stage_and_full_sixty_seconds(self):
        report = live_report(
            session=1,
            selectedSurvivor="Engi",
            developerSurvivorOverride=True,
            world={"seconds": 60.0, "ready": True, "health": 130.0, "diagnosticInputEver": True, "engiShieldGuardPrepared": True},
            stageProgress={"current": "lakes", "transitions": 0, "transporting": False},
        )
        self.assertEqual(abandon_observation_failures(report, "Engi", 60.0, 0.0), [])
        self.assertTrue(
            any("report is shorter" in x for x in abandon_observation_failures({**report, "world": {**report["world"], "seconds": 59.9}}, "Engi", 60.0, 0.0))
        )
        self.assertTrue(any("host did not observe" in x for x in abandon_observation_failures(report, "Engi", 59.9, 0.0)))
        self.assertTrue(
            any("living player" in x for x in abandon_observation_failures({**report, "world": {**report["world"], "health": 0}}, "Engi", 60.0, 0.0))
        )
        self.assertTrue(
            any(
                "waiting for positive player health/maxHealth" in x
                for x in abandon_observation_failures({**report, "world": {**report["world"], "health": 0}}, "Engi", 0.0, None)
            )
        )
        self.assertTrue(
            any("waiting for a ready" in x for x in abandon_observation_failures({**report, "world": {**report["world"], "ready": False}}, "Engi", 0.0, None))
        )
        self.assertTrue(
            any(
                "transition" in x
                for x in abandon_observation_failures(
                    {**report, "stageProgress": {"current": "goolake", "transitions": 1, "transporting": False}}, "Engi", 60.0, 0.0
                )
            )
        )
        self.assertTrue(
            any(
                "Engi shield template guard" in x
                for x in abandon_observation_failures({**report, "world": {**report["world"], "engiShieldGuardPrepared": False}}, "Engi", 60.0, None)
            )
        )
        self.assertTrue(
            any("stopped being ready" in x for x in abandon_observation_failures({**report, "world": {**report["world"], "ready": False}}, "Engi", 60.0, 0.0))
        )
        self.assertTrue(
            any(
                "throughout the live interval" in x
                for x in abandon_observation_failures({**report, "world": {**report["world"], "diagnosticInputEver": False}}, "Engi", 60.0, 0.0)
            )
        )

    def test_abandon_startup_wait_does_not_hide_death_or_ending_evidence(self):
        report = live_report(
            session=1,
            selectedSurvivor="Engi",
            developerSurvivorOverride=True,
            world={"seconds": 0.0, "ready": True, "health": 0.0, "maxHealth": 0.0, "diagnosticInputEver": False, "engiShieldGuardPrepared": False},
            playerDefeat={"deathEvents": 0, "deathEntered": False, "bodyDestroyed": False},
            results={"ready": True, "serverEnding": False, "clientEnding": False, "reportGenerated": False, "persisted": False},
        )
        waiting = abandon_observation_failures(report, "Engi", 0.0, None)
        self.assertTrue(any("waiting for positive player health/maxHealth" in item for item in waiting))
        self.assertFalse(any("death event occurred" in item or "ending or result occurred" in item for item in waiting))
        died = {**report, "playerDefeat": {"deathEvents": 1, "deathEntered": True, "bodyDestroyed": False}}
        self.assertTrue(any("death event occurred" in item for item in abandon_observation_failures(died, "Engi", 0.0, None)))
        ended = {**report, "results": {**report["results"], "clientEnding": True}}
        self.assertTrue(any("ending or result occurred" in item for item in abandon_observation_failures(ended, "Engi", 0.0, None)))

    def test_mocked_abandon_startup_wait_has_a_bounded_deadline_without_tapping(self):
        reports = [
            live_report(
                session=1,
                selectedSurvivor="Engi",
                developerSurvivorOverride=True,
                world={"seconds": 0.0, "ready": True, "health": 0.0, "maxHealth": 0.0, "diagnosticInputEver": False, "engiShieldGuardPrepared": False},
                playerDefeat={"deathEvents": 0, "deathEntered": False, "bodyDestroyed": False},
                results={"ready": True, "serverEnding": False, "clientEnding": False, "reportGenerated": False, "persisted": False},
            )
            for _ in range(20)
        ]
        temp, device, result, error, evidence = run_fake_check(reports, survivor="Engi", ending="abandon", clock_step=5.0)
        try:
            self.assertIsNone(result)
            self.assertIsNotNone(error)
            self.assertEqual(device.taps, [])
            saved = json.loads((evidence / "result.json").read_text())
            self.assertEqual(saved["stop"], "abandon-world-startup-timeout")
        finally:
            temp.cleanup()

    def test_mocked_abandon_waits_for_ready_body_then_refuses_faulted_observer_before_taps(self):
        startup = live_report(
            session=1,
            selectedSurvivor="Engi",
            developerSurvivorOverride=True,
            world={"seconds": 0.0, "ready": False, "health": 0.0, "maxHealth": 0.0,
                   "diagnosticInputEver": False, "engiShieldGuardPrepared": False,
                   "survivorCombatOutputs": {"attached": False, "cleaned": False, "inert": True, "observerError": "early"}},
        )
        first_ready_fault = live_report(
            session=1,
            selectedSurvivor="Engi",
            developerSurvivorOverride=True,
            world={"seconds": 1.0, "ready": True, "health": 130.0, "maxHealth": 130.0,
                   "diagnosticInputEver": True, "engiShieldGuardPrepared": True,
                   "survivorCombatOutputs": {"attached": False, "cleaned": True, "inert": True,
                                              "observerError": "observer fault"}},
        )
        temp, device, result, error, evidence = run_fake_check(
            [startup, first_ready_fault], survivor="Engi", ending="abandon", clock_step=1.0
        )
        try:
            self.assertIsNone(result)
            self.assertIsNotNone(error)
            self.assertEqual(device.taps, [])
            saved = json.loads((evidence / "result.json").read_text())
            self.assertEqual(saved["stop"], "first-live-combat-output-observer-unhealthy")
            self.assertEqual(saved["combat_output_lifecycle"]["first_ready_session_1"]["status"], "invalid")
        finally:
            temp.cleanup()

    def test_abandon_controls_require_reported_matching_android_logical_grid(self):
        report = live_report(
            settings={
                "screenWidth": 1280,
                "screenHeight": 800,
                "buttonX": 1167.5,
                "buttonY": 30.0,
                "endRunButtonX": 430.0,
                "endRunButtonY": 512.5,
            }
        )
        size = "Physical size: 1280x800\n"
        rotation = "mDisplayRotation=ROTATION_0\n"
        self.assertEqual(abandon_control_coordinates(report, "button", size, rotation), (1168, 30))
        self.assertEqual(abandon_control_coordinates(report, "endRunButton", size, rotation), (430, 512))
        self.assertIsNone(abandon_control_coordinates(report, "button", size, ""))
        self.assertIsNone(abandon_control_coordinates(report, "button", "Physical size: 800x1280\n", rotation))
        self.assertIsNone(abandon_control_coordinates(live_report(settings={"buttonX": 10, "buttonY": 10}), "button", size, rotation))
        out_of_bounds = live_report(settings={"screenWidth": 1280, "screenHeight": 800, "buttonX": 1280, "buttonY": 30})
        self.assertIsNone(abandon_control_coordinates(out_of_bounds, "button", size, rotation))

    def test_mocked_abandon_clicks_only_reported_controls_then_observes_direct_same_process_restart(self):
        settings_open = live_report(
            session=1,
            selectedSurvivor="Engi",
            developerSurvivorOverride=True,
            settings={
                "ready": True,
                "visible": True,
                "canEndRun": True,
                "buttonX": 1167.5,
                "buttonY": 30.0,
                "endRunButtonX": 430.0,
                "endRunButtonY": 512.5,
                "screenWidth": 1280,
                "screenHeight": 800,
            },
            world={"seconds": 60.0, "ready": True, "health": 130.0, "diagnosticInputEver": True, "engiShieldGuardPrepared": True},
        )
        reports = [
            live_report(
                session=1,
                selectedSurvivor="Engi",
                developerSurvivorOverride=True,
                world={
                    "seconds": 0.0,
                    "ready": True,
                    "health": 0.0,
                    "maxHealth": 0.0,
                    "diagnosticInputEver": False,
                    "engiShieldGuardPrepared": False,
                },
                playerDefeat={"deathEvents": 0, "deathEntered": False, "bodyDestroyed": False},
                results={"ready": True, "serverEnding": False, "clientEnding": False, "reportGenerated": False, "persisted": False},
            ),
            live_report(
                session=1,
                selectedSurvivor="Engi",
                developerSurvivorOverride=True,
                world={"seconds": 0.0, "ready": False, "health": 0.0, "diagnosticInputEver": False, "engiShieldGuardPrepared": False},
            ),
            live_report(
                session=1,
                selectedSurvivor="Engi",
                developerSurvivorOverride=True,
                world={"seconds": 5.0, "ready": True, "health": 130.0, "diagnosticInputEver": True, "engiShieldGuardPrepared": False},
            ),
            live_report(
                session=1,
                selectedSurvivor="Engi",
                developerSurvivorOverride=True,
                world={"seconds": 10.0, "ready": True, "health": 130.0, "diagnosticInputEver": True, "engiShieldGuardPrepared": True},
            ),
            *[
                live_report(
                    session=1,
                    selectedSurvivor="Engi",
                    developerSurvivorOverride=True,
                    world={"seconds": 60.0, "ready": True, "health": 130.0, "diagnosticInputEver": True, "engiShieldGuardPrepared": True},
                )
                for _ in range(25)
            ],
            settings_open,
            settings_open,
            settings_open,
            live_report(session=2, selectedSurvivor="Engi", developerSurvivorOverride=True),
        ]
        temp, device, result, error, evidence = run_fake_check(reports, survivor="Engi", ending="abandon", clock_step=1.0)
        try:
            self.assertIsNone(error)
            self.assertTrue(result["success"])
            self.assertEqual(device.taps, [(1168, 30), (430, 512)])
            self.assertGreater(device.tap_report_indices[0], 4)
            self.assertFalse(device.alive)
            saved = json.loads((evidence / "result.json").read_text())
            self.assertEqual(saved["ending_mode"], "abandon")
            self.assertEqual(saved["abandon_ui"], {"settings_open_sent": True, "end_run_sent": True})
            self.assertEqual(saved["completed_session"]["settings"]["sessionAbandoned"], True)
            self.assertFalse(saved["completed_session"]["results"]["persisted"])
        finally:
            temp.cleanup()

    def test_mocked_abandon_refuses_selection_mismatch_before_any_ui_tap(self):
        reports = [live_report(session=1, selectedSurvivor="Commando", developerSurvivorOverride=False)]
        temp, device, result, error, evidence = run_fake_check(reports, survivor="Engi", ending="abandon")
        try:
            self.assertIsNone(result)
            self.assertIsNotNone(error)
            self.assertEqual(device.taps, [])
            saved = json.loads((evidence / "result.json").read_text())
            self.assertEqual(saved["stop"], "survivor-selection-mismatch")
        finally:
            temp.cleanup()

    def test_mocked_abandon_rejects_world_readiness_interruption_before_end_run_tap(self):
        reports = [
            live_report(
                session=1,
                selectedSurvivor="Engi",
                developerSurvivorOverride=True,
                world={"seconds": 10.0, "ready": True, "health": 130.0, "diagnosticInputEver": True, "engiShieldGuardPrepared": True},
            ),
            live_report(
                session=1,
                selectedSurvivor="Engi",
                developerSurvivorOverride=True,
                world={"seconds": 60.0, "ready": True, "health": 130.0, "diagnosticInputEver": True, "engiShieldGuardPrepared": True},
            ),
            live_report(
                session=1,
                selectedSurvivor="Engi",
                developerSurvivorOverride=True,
                world={"seconds": 0.0, "ready": False, "health": 0.0, "diagnosticInputEver": False, "engiShieldGuardPrepared": True},
            ),
        ]
        temp, device, result, error, evidence = run_fake_check(reports, survivor="Engi", ending="abandon", clock_step=30.0)
        try:
            self.assertIsNone(result)
            self.assertIsNotNone(error)
            self.assertEqual(device.taps, [(1168, 30)])
            saved = json.loads((evidence / "result.json").read_text())
            self.assertEqual(saved["stop"], "abandon-observation-contract-failed")
            self.assertIn("world stopped being ready", saved["first_failure"])
        finally:
            temp.cleanup()

    def test_free_survivor_abandon_validates_completed_contract_before_session2_menu_tap(self):
        settings_open = live_report(
            session=1,
            settings={
                "ready": True,
                "visible": True,
                "canEndRun": True,
                "buttonX": 1167.5,
                "buttonY": 30.0,
                "endRunButtonX": 430.0,
                "endRunButtonY": 512.5,
                "screenWidth": 1280,
                "screenHeight": 800,
            },
            world={"seconds": 60.0, "ready": True, "health": 100.0, "diagnosticInputEver": True},
        )
        reports = [ordinary_start_report(), live_report(session=1, world={"seconds": 10.0, "ready": True, "health": 100.0, "diagnosticInputEver": True})]
        reports.extend(live_report(session=1, world={"seconds": 60.0, "ready": True, "health": 100.0, "diagnosticInputEver": True}) for _ in range(8))
        reports.extend([settings_open, settings_open, session2_offline_menu_report(), live_report(session=2)])
        temp, device, result, error, evidence = run_fake_check(reports, survivor="Commando", ending="abandon", clock_step=10.0)
        try:
            self.assertIsNone(error)
            self.assertTrue(result["success"])
            self.assertEqual(device.taps, [(100, 200), (1168, 30), (430, 512), (100, 200)])
            self.assertTrue(device.tap_completion_present[-1])
            saved = json.loads((evidence / "result.json").read_text())
            self.assertEqual(saved["session2_menu_ui"], {"observed": True, "start_sent": True})
            menu = json.loads((evidence / "session-2-menu-start.json").read_text())
            self.assertEqual(menu["coordinates"], [100, 200])
            self.assertEqual(menu["completed_session"], 1)
        finally:
            temp.cleanup()

    def test_free_survivor_abandon_refuses_malformed_completion_before_session2_menu_tap(self):
        settings_open = live_report(
            session=1,
            settings={
                "ready": True,
                "visible": True,
                "canEndRun": True,
                "buttonX": 1167.5,
                "buttonY": 30.0,
                "endRunButtonX": 430.0,
                "endRunButtonY": 512.5,
                "screenWidth": 1280,
                "screenHeight": 800,
            },
            world={"seconds": 60.0, "ready": True, "health": 100.0, "diagnosticInputEver": True},
        )
        reports = [ordinary_start_report(), live_report(session=1, world={"seconds": 10.0, "ready": True, "health": 100.0, "diagnosticInputEver": True})]
        reports.extend(live_report(session=1, world={"seconds": 60.0, "ready": True, "health": 100.0, "diagnosticInputEver": True}) for _ in range(8))
        reports.extend([settings_open, settings_open, session2_offline_menu_report()])
        temp, device, result, error, evidence = run_fake_check(
            reports,
            survivor="Commando",
            ending="abandon",
            clock_step=10.0,
            completed_override=json.dumps({"attempt": "malformed-completion"}),
        )
        try:
            self.assertIsNone(result)
            self.assertIsNotNone(error)
            self.assertEqual(device.taps, [(100, 200), (1168, 30), (430, 512)])
            self.assertFalse(device.tap_completion_present[-1])
            saved = json.loads((evidence / "result.json").read_text())
            self.assertEqual(saved["stop"], "completed-session-cleanup-failed-before-session-2-menu")
        finally:
            temp.cleanup()

    def test_mocked_runner_observes_stale_clear_death_restart_and_same_process(self):
        reports = [
            ordinary_start_report(),
            live_report(session=1),
            session_one_defeat_report(),
            live_report(
                session=2,
                world={
                    "seconds": 0.0,
                    "ready": False,
                    "health": 0.0,
                    "diagnosticInputEver": False,
                },
            ),
            live_report(session=2),
        ]
        temp, device, result, error, evidence = run_fake_check(reports)
        try:
            self.assertIsNone(error)
            self.assertTrue(result["success"])
            self.assertEqual(result["stop"], "same-process-restart")
            self.assertEqual(
                result["profile_snapshots"]["first_live_session"],
                {
                    "appliedRuns": 13,
                    "earnedUnlocks": 2,
                    "availableEarnedUnlocks": 2,
                },
            )
            self.assertEqual(len(device.taps), 2)
            self.assertFalse(device.alive)
            self.assertEqual(device.display_states, [True, False])
            self.assertNotIn(device.selector_path, device.remote)
            self.assertEqual(json.loads((evidence / "prior-completed-session-1.json").read_text())["attempt"], "stale")
            self.assertEqual(json.loads((evidence / "restart-display-mapping.json").read_text())["coordinates"], [207, 420])
            self.assertEqual(json.loads((evidence / "first-live-session.json").read_text())["phase"], "integrated-world-playing")
            self.assertEqual(json.loads((evidence / "result.json").read_text())["restarted_session"]["world"]["seconds"], 10.0)
            self.assertTrue(json.loads((evidence / "result.json").read_text())["success"])
        finally:
            temp.cleanup()

    def test_mocked_runner_accepts_base_engi_with_consistent_locked_override(self):
        reports = [
            {**live_report(session=1), "selectedSurvivor": "Engi", "developerSurvivorOverride": True},
            {**session_one_defeat_report(), "selectedSurvivor": "Engi", "developerSurvivorOverride": True},
            {**live_report(session=2), "selectedSurvivor": "Engi", "developerSurvivorOverride": True},
        ]
        temp, _device, result, error, evidence = run_fake_check(reports, survivor="Engi")
        try:
            self.assertIsNone(error)
            self.assertTrue(result["success"])
            self.assertEqual(len(_device.taps), 1)
            saved = json.loads((evidence / "result.json").read_text())
            self.assertEqual(saved["selected_survivor"], "Engi")
            self.assertTrue(saved["developer_survivor_override"])
        finally:
            temp.cleanup()

    def test_locked_diagnostic_target_rejects_ordinary_menu_phase(self):
        reports = [{**ordinary_start_report(), "selectedSurvivor": "Engi", "developerSurvivorOverride": True}]
        temp, device, result, error, evidence = run_fake_check(reports, survivor="Engi")
        try:
            self.assertIsNone(result)
            self.assertIsNotNone(error)
            self.assertEqual(device.taps, [])
            saved = json.loads((evidence / "result.json").read_text())
            self.assertEqual(saved["stop"], "unexpected-menu-for-diagnostic-override")
        finally:
            temp.cleanup()

    def test_free_survivor_requires_ordinary_menu_before_live_input(self):
        reports = [live_report(session=1)]
        temp, device, result, error, evidence = run_fake_check(reports)
        try:
            self.assertIsNone(result)
            self.assertIsNotNone(error)
            self.assertEqual(device.taps, [])
            saved = json.loads((evidence / "result.json").read_text())
            self.assertEqual(saved["stop"], "ordinary-menu-start-not-observed")
        finally:
            temp.cleanup()

    def test_mocked_runner_refuses_first_current_report_for_wrong_hero_before_taps(self):
        reports = [
            {**live_report(session=1), "selectedSurvivor": "Engi", "developerSurvivorOverride": True},
        ]
        temp, device, result, error, evidence = run_fake_check(reports)
        try:
            self.assertIsNone(result)
            self.assertIsNotNone(error)
            self.assertEqual(device.taps, [])
            saved = json.loads((evidence / "result.json").read_text())
            self.assertEqual(saved["stop"], "survivor-selection-mismatch")
            self.assertIn("selected survivor differs", saved["first_failure"])
        finally:
            temp.cleanup()

    def test_mocked_runner_refuses_wrong_hero_before_restart_tap(self):
        reports = [
            ordinary_start_report(),
            live_report(session=1),
            {**session_one_defeat_report(), "selectedSurvivor": "Engi", "developerSurvivorOverride": True},
        ]
        temp, device, result, error, evidence = run_fake_check(reports)
        try:
            self.assertIsNone(result)
            self.assertIsNotNone(error)
            self.assertEqual(device.taps, [(100, 200)])
            saved = json.loads((evidence / "result.json").read_text())
            self.assertEqual(saved["stop"], "survivor-selection-mismatch")
            self.assertIn("restart input was not sent", saved["failures"])
        finally:
            temp.cleanup()

    def test_mocked_runner_final_log_only_error_fails_and_preserves_first_failure(self):
        reports = [
            ordinary_start_report(),
            live_report(session=1),
            session_one_defeat_report(),
            live_report(session=2),
        ]
        temp, _device, result, error, evidence = run_fake_check(reports, log_error=True)
        try:
            self.assertIsNone(result)
            self.assertIsNotNone(error)
            saved = json.loads((evidence / "result.json").read_text())
            self.assertFalse(saved["success"])
            self.assertEqual(saved["first_failure"], "late log failure")
            self.assertTrue(any("current-process runtime errors" in failure for failure in saved["failures"]))
            self.assertIn("late log failure", str(error))
        finally:
            temp.cleanup()

    def test_mocked_runner_missing_observed_restart_never_passes(self):
        reports = [ordinary_start_report(), live_report(session=2)]
        temp, device, result, error, evidence = run_fake_check(reports)
        try:
            self.assertIsNone(result)
            self.assertIsNotNone(error)
            self.assertEqual(device.taps, [(100, 200)])
            saved = json.loads((evidence / "result.json").read_text())
            self.assertFalse(saved["success"])
            self.assertIn("session-1 defeat was not observed", saved["failures"])
            self.assertIn("restart input was not sent", saved["failures"])
        finally:
            temp.cleanup()

    def test_mocked_runner_requires_profile_counts_from_first_live_session(self):
        missing_counts = live_report(session=1, profile={"ready": False})
        reports = [ordinary_start_report(), missing_counts, session_one_defeat_report(), live_report(session=2)]
        temp, device, result, error, evidence = run_fake_check(reports)
        try:
            self.assertIsNone(result)
            self.assertIsNotNone(error)
            self.assertEqual(device.taps, [(100, 200)])
            saved = json.loads((evidence / "result.json").read_text())
            self.assertEqual(saved["stop"], "first-live-profile-baseline-unavailable")
            self.assertIsNone(saved["profile_baseline"])
        finally:
            temp.cleanup()

    def test_mocked_runner_stops_on_unexpected_session_index(self):
        reports = [ordinary_start_report(), live_report(session=3)]
        temp, _device, result, error, evidence = run_fake_check(reports)
        try:
            self.assertIsNone(result)
            self.assertIsNotNone(error)
            saved = json.loads((evidence / "result.json").read_text())
            self.assertEqual(saved["stop"], "unexpected-session-index")
            self.assertFalse(saved["success"])
        finally:
            temp.cleanup()

    def test_mocked_runner_does_not_accept_transient_restart_at_deadline(self):
        transient = live_report(
            session=2,
            world={
                "seconds": 0.0,
                "ready": False,
                "health": 0.0,
                "diagnosticInputEver": False,
            },
        )
        reports = [ordinary_start_report(), live_report(session=1), session_one_defeat_report(), transient]
        temp, _device, result, error, evidence = run_fake_check(
            reports,
            host_deadline_seconds=1.5,
        )
        try:
            self.assertIsNone(result)
            self.assertIsNotNone(error)
            saved = json.loads((evidence / "result.json").read_text())
            self.assertEqual(saved["stop"], "deadline")
            self.assertFalse(saved["success"])
            self.assertTrue(any("ready observed integrated tick" in failure for failure in saved["failures"]))
        finally:
            temp.cleanup()

    def test_mocked_runner_preserves_foreign_selector_during_cleanup(self):
        reports = [
            ordinary_start_report(),
            live_report(session=1),
            session_one_defeat_report(),
            live_report(session=2),
        ]
        temp, device, result, error, evidence = run_fake_check(reports, foreign_selector=True)
        try:
            self.assertIsNone(result)
            self.assertIsNotNone(error)
            self.assertIn(device.selector_path, device.remote)
            self.assertEqual(json.loads(device.remote[device.selector_path])["id"], "foreign")
            saved = json.loads((evidence / "result.json").read_text())
            self.assertFalse(saved["success"])
            self.assertTrue(any("preserved it" in failure for failure in saved["failures"]))
        finally:
            temp.cleanup()


if __name__ == "__main__":
    unittest.main()
