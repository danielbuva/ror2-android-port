import copy
import io
import json
from contextlib import redirect_stdout
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts/lab"))
import survivor_check as check


def report(**updates):
    value = {
        "phase": "integrated-world-playing",
        "selectedSurvivor": "Huntress",
        "developerSurvivorOverride": False,
        "world": {"seconds": 60},
        "stage": {"scene": "lakes"},
        "stageProgress": {"transitions": 0},
        "debugAcceleration": {"everAssisted": True},
        "profile": {"appliedRuns": 13},
        "survivorSkills": {
            "attached": True,
            "cleaned": False,
            "slots": [
                {
                    "slot": name,
                    "authorityActivations": 1,
                    "serverActivations": 1,
                    "suppressesActivationEvents": False,
                }
                for name in check.SLOTS
            ],
        },
    }
    value.update(updates)
    return value


class SurvivorSelectionTests(unittest.TestCase):
    def test_explicit_base_roster_and_native_names(self):
        self.assertEqual(len(check.targets("all")), 11)
        self.assertEqual(check.targets("Engi,Loader"), ("Engi", "Loader"))
        for value in ("lab", "Engineer", "Huntress,Huntress", "", "Railgunner", "Huntress,"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                check.targets(value)

    def test_only_locked_base_survivors_use_diagnostic_override(self):
        for name in check.BASE_SURVIVORS:
            value = check.survivor_selection("owned-attempt", name)
            self.assertEqual(value["selectedSurvivor"], name)
            self.assertEqual(value["attempt"], "owned-attempt")
            self.assertEqual(value["developerSurvivorOverride"], name not in check.FREE_SURVIVORS)
            self.assertFalse(value["goldshoresRoute"])
            self.assertTrue(value["diagnosticSkillCoverage"])
            self.assertEqual([key for key in check.DEBUG_OPTIONS if value["debugOptions"][key]], ["invincibility"])
            self.assertIn("no permanent progression", value["debugOptions"]["purpose"])

    def test_isolated_slot_selector_composes_with_existing_variant_selector(self):
        variants = {"survivor": "Mage", "entries": [{"componentIndex": 2, "familyCatalogIndex": 17, "variantIndex": 4, "skillCatalogIndex": 807}]}
        value = check.survivor_selection("attempt", "Mage", variants, "utility")
        self.assertEqual(value["diagnosticSkillIsolationSlot"], "utility")
        self.assertEqual(value["developerSkillVariantOverride"], variants)
        self.assertIn("Assisted isolated", value["debugOptions"]["purpose"])

    def test_lock_prevents_even_device_discovery(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "coordination").mkdir()
            (root / "coordination/claude-r9.lock").write_text("owned by parallel session")
            with patch.object(check, "WORK", root), patch.object(check.Device, "__init__") as discover:
                with self.assertRaisesRegex(RuntimeError, "coordination lock"):
                    check.SurvivorCheckDevice()
                discover.assert_not_called()

    def test_each_subsequent_device_command_rechecks_lock(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            device = object.__new__(check.SurvivorCheckDevice)
            with patch.object(check, "WORK", root), patch.object(check.Device, "cmd", return_value="sent") as send:
                self.assertEqual(device.cmd("shell", "true"), "sent")
                (root / "coordination").mkdir()
                (root / "coordination/claude-r9.lock").touch()
                with self.assertRaisesRegex(RuntimeError, "coordination lock"):
                    device.cmd("shell", "true")
                self.assertEqual(send.call_count, 1)


class SurvivorStoragePolicyTests(unittest.TestCase):
    def run_selected(self, mode, installed_mode, live, package_path, *, refused=False):
        device = Mock()
        device.settings = {"storage_mode": mode}
        digest = "f" * 64
        installed = {"storage": {"mode": installed_mode}, "package_path": package_path, "apk_sha256": digest}
        device.owned.return_value = installed
        device.storage.return_value = live
        device.read_receipt.return_value = {"persistentDataPath": "/fixture-runtime"}
        with tempfile.TemporaryDirectory() as directory:

            def read(path):
                return {"success": True, "apk_sha256": digest} if path.name == "current-build.json" else {"attempt": "mutable-project-attempt"}

            with (
                patch.object(check, "WORK", Path(directory)),
                patch.object(check, "SurvivorCheckDevice", return_value=device),
                patch.object(check, "read", side_effect=read),
                patch.object(check, "check_one", return_value={"success": True}) as case,
                patch.object(check, "attempt_from_installed", return_value="fixture-attempt") as attempt,
                redirect_stdout(io.StringIO()),
            ):
                if refused:
                    with self.assertRaises(RuntimeError):
                        check.check_survivors("Huntress")
                    case.assert_not_called()
                    device.read_receipt.assert_not_called()
                    attempt.assert_not_called()
                else:
                    self.assertEqual(
                        check.check_survivors("Huntress"),
                        [
                            {
                                "success": True,
                                "apk_sha256": digest,
                                "apk_binding_mode": "current-build-at-start",
                            }
                        ],
                    )
                    case.assert_called_once()
                    attempt.assert_called_once_with(installed)
                    self.assertEqual(case.call_args.args[2], "fixture-attempt")
                    self.assertIs(case.call_args.args[-1], installed)
                    device.storage.assert_called_once()

    def test_selected_internal_and_adopted_devices_reach_the_existing_case_runner(self):
        self.run_selected("internal", "internal", {"mode": "internal"}, "package:/data/app/fixture/base.apk")
        self.run_selected("adopted", "adopted", {"mode": "adopted", "uuid": "live-volume"}, "package:/mnt/expand/live-volume/app/fixture/base.apk")

    def test_explicit_owned_apk_binds_the_whole_batch_without_current_build_reads(self):
        digest = "a" * 64
        device = Mock()
        device.settings = {"storage_mode": "internal"}
        installed = {"storage": {"mode": "internal"}, "package_path": "package:/data/app/fixture/base.apk", "apk_sha256": digest}
        device.owned.return_value = installed
        device.storage.return_value = {"mode": "internal"}
        device.read_receipt.return_value = {"persistentDataPath": "/fixture-runtime"}
        for requested in (digest, "b" * 64):
            with self.subTest(matching=requested == digest), tempfile.TemporaryDirectory() as directory:
                with (
                    patch.object(check, "WORK", Path(directory)),
                    patch.object(check, "SurvivorCheckDevice", return_value=device),
                    patch.object(check, "read", side_effect=AssertionError("no current-build read")),
                    patch.object(check, "attempt_from_installed", return_value="owned-attempt") as attempt,
                    patch.object(check, "check_one", side_effect=lambda *a, **kw: {"success": True}) as case,
                    redirect_stdout(io.StringIO()),
                ):
                    if requested != digest:
                        with self.assertRaisesRegex(RuntimeError, "does not match"):
                            check.check_survivors("Croco,Merc", expected_apk_sha256=requested)
                        attempt.assert_not_called()
                        case.assert_not_called()
                    else:
                        results = check.check_survivors("Croco,Merc", expected_apk_sha256=requested)
                        attempt.assert_called_once_with(installed)
                        self.assertEqual([call.args[1] for call in case.call_args_list], ["Croco", "Merc"])
                        self.assertTrue(all(call.args[2] == "owned-attempt" for call in case.call_args_list))
                        self.assertEqual(results, [{"success": True, "apk_sha256": digest, "apk_binding_mode": "explicit-owned-apk-sha256"}] * 2)

    def test_storage_drift_or_missing_placement_refuses_before_launch(self):
        cases = (
            ("internal", "adopted", {"mode": "internal"}, "package:/data/app/fixture/base.apk"),
            ("internal", "internal", {"mode": "adopted"}, "package:/data/app/fixture/base.apk"),
            ("internal", "internal", {"mode": "internal"}, "package:/mnt/expand/old/app/fixture/base.apk"),
            ("adopted", "adopted", {"mode": "adopted", "uuid": "live-volume"}, "package:/mnt/expand/old/app/fixture/base.apk"),
            ("adopted", "adopted", {"mode": "adopted"}, "package:/mnt/expand/old/app/fixture/base.apk"),
            ("internal", "internal", {"mode": "internal"}, None),
        )
        for values in cases:
            with self.subTest(values=values):
                self.run_selected(*values, refused=True)


def component_rows(count, *, passive_last=False):
    roles = ["Primary", "Secondary", "Utility", "Special"] + ["None"] * max(0, count - 4)
    rows = [{"componentIndex": index, "instanceId": 100 + index, "canonicalSlot": role, "present": True} for index, role in enumerate(roles[:count])]
    if passive_last and rows:
        rows[-1]["enabled"] = False
        rows[-1]["definition"] = ""
        rows[-1]["authorityActivations"] = 0
        rows[-1]["serverActivations"] = 0
    return rows


class SurvivorComponentInventoryTests(unittest.TestCase):
    def test_older_report_without_component_array_is_instrumentation_unavailable(self):
        value = report()
        self.assertEqual(
            check.component_inventory(value, "Toolbot"),
            {"status": "instrumentation-unavailable", "expectedComponents": 5},
        )
        self.assertEqual(check.assess("Huntress", "four-slots-activated", value, value, []), [])

    def test_actual_expected_component_counts_and_native_roles_are_reported(self):
        for survivor, count in (("Croco", 5), ("Toolbot", 5), ("Captain", 6), ("Huntress", 4)):
            with self.subTest(survivor=survivor):
                value = report()
                value["survivorSkills"]["components"] = component_rows(count, passive_last=survivor == "Croco")
                inventory = check.component_inventory(value, survivor)
                self.assertEqual(inventory["status"], "valid")
                self.assertEqual(inventory["observedComponents"], count)
                self.assertEqual(inventory["noncanonicalCount"], count - 4)
                self.assertEqual(inventory["canonicalCounts"]["None"], count - 4)
                if survivor == "Croco":
                    value["selectedSurvivor"] = "Croco"
                    value["developerSurvivorOverride"] = True
                    self.assertEqual(check.assess(survivor, "four-slots-activated", value, value, []), [])

    def test_removed_component_history_does_not_distort_current_body_inventory(self):
        value = report()
        rows = component_rows(5)
        removed = {"componentIndex": -1, "instanceId": 77, "canonicalSlot": "", "present": False}
        value["survivorSkills"]["components"] = rows + [removed]
        inventory = check.component_inventory(value, "Toolbot")
        self.assertEqual(inventory["status"], "valid")
        self.assertEqual(inventory["observedComponents"], 5)
        self.assertEqual(inventory["historicalComponents"], 1)

    def test_present_malformed_inventory_fails_without_changing_four_slot_gate(self):
        for rows, reason in ((component_rows(4), "component-count-mismatch"), (None, "components-not-array")):
            with self.subTest(reason=reason):
                value = report()
                value["survivorSkills"]["components"] = rows
                inventory = check.component_inventory(value, "Toolbot")
                self.assertEqual(inventory["status"], "invalid")
                self.assertEqual(inventory["reason"], reason)

    def test_duplicate_ids_and_bad_indexes_or_roles_fail_inventory(self):
        cases = []
        duplicate = component_rows(5)
        duplicate[-1]["instanceId"] = duplicate[0]["instanceId"]
        cases.append((duplicate, "component-identities-not-unique"))
        bad_index = component_rows(5)
        bad_index[-1]["componentIndex"] = 3
        cases.append((bad_index, "component-indexes-not-contiguous-unique"))
        bad_role = component_rows(5)
        bad_role[-1]["canonicalSlot"] = "aux"
        cases.append((bad_role, "component-native-role-invalid"))
        bad_presence = component_rows(5)
        bad_presence[-1]["present"] = False
        cases.append((bad_presence, "component-count-mismatch"))
        for rows, reason in cases:
            with self.subTest(reason=reason):
                value = report()
                value["survivorSkills"]["components"] = rows
                self.assertEqual(check.component_inventory(value, "Toolbot")["reason"], reason)
                failures = check.assess("Toolbot", "four-slots-activated", report(), value, [])
                self.assertTrue(any("invalid survivor skill component inventory" in failure for failure in failures))


class SurvivorAssessmentTests(unittest.TestCase):
    def test_passing_activation_evidence(self):
        self.assertEqual(check.assess("Huntress", "four-slots-activated", report(), report(), []), [])

    def test_both_authority_and_server_callbacks_are_required_per_slot(self):
        for index in range(4):
            for key in ("authorityActivations", "serverActivations"):
                for count in (0, -1, None, True, "1"):
                    with self.subTest(slot=index, key=key, count=count):
                        value = report()
                        value["survivorSkills"]["slots"][index][key] = count
                        self.assertEqual(check.missing_activations(value), [check.SLOTS[index]])
                        self.assertTrue(check.assess("Huntress", "four-slots-activated", report(), value, []))

    def test_missing_duplicate_or_detached_slots_never_pass(self):
        observations = [None, {}, {"attached": True, "slots": []}, report()["survivorSkills"]]
        observations[-1]["slots"][3]["slot"] = "primary"
        observations += [dict(report()["survivorSkills"], attached=False), dict(report()["survivorSkills"], cleaned=True)]
        for observation in observations:
            with self.subTest(observation=observation):
                self.assertEqual(check.missing_activations(report(survivorSkills=observation)), list(check.SLOTS))

    def test_waits_for_broad_world_play_and_reports_unobserved_skills(self):
        self.assertIsNone(check.stop_reason(report(world={"seconds": 59.9})))
        self.assertEqual(check.stop_reason(report()), "four-slots-activated")
        self.assertEqual(check.stop_reason(report(world={"seconds": 180}, survivorSkills=None)), "unobserved-skills")
        for value in (None, -1, True, "60", float("nan"), float("inf")):
            self.assertIsNone(check.stop_reason(report(world={"seconds": value})))

    def test_suppressed_callbacks_are_classified_with_callback_context_and_never_pass(self):
        value = report()
        slot = value["survivorSkills"]["slots"][1]
        slot["authorityActivations"] = 0
        slot["serverActivations"] = 0
        slot["suppressesActivationEvents"] = True
        context = [{"slot": "secondary", "callbacks": ["authorityActivations", "serverActivations"]}]
        self.assertEqual(check.suppressed_missing_callbacks(value), context)
        self.assertEqual(check.stop_reason(value), "suppressed-activation-events")
        failures = check.assess("Huntress", "suppressed-activation-events", report(), value, [])
        self.assertTrue(any("suppressed activation callbacks: secondary(authorityActivations, serverActivations)" in item for item in failures))
        self.assertTrue(failures)

    def test_only_the_missing_suppressed_callback_is_reported(self):
        value = report()
        slot = value["survivorSkills"]["slots"][2]
        slot["authorityActivations"] = 0
        slot["suppressesActivationEvents"] = True
        self.assertEqual(
            check.suppressed_missing_callbacks(value),
            [{"slot": "utility", "callbacks": ["authorityActivations"]}],
        )
        self.assertEqual(check.stop_reason(value), "suppressed-activation-events")

    def test_unsuppressed_missing_callback_remains_unobserved(self):
        value = report()
        value["survivorSkills"]["slots"][0]["authorityActivations"] = 0
        self.assertEqual(check.suppressed_missing_callbacks(value), [])
        self.assertIsNone(check.stop_reason(value))
        self.assertEqual(check.stop_reason(report(world={"seconds": 180}, survivorSkills=value["survivorSkills"])), "unobserved-skills")

    def test_errors_result_and_transport_take_precedence_over_activations(self):
        for updates, expected in (
            ({"error": "runtime error"}, "first-failure"),
            ({"firstFailure": "runtime error"}, "first-failure"),
            ({"phase": "commando-defeated"}, "ordinary-result"),
            ({"stage": {"scene": "goolake"}}, "left-first-stage"),
            ({"stageProgress": {"transitions": 1}}, "left-first-stage"),
            ({"stageProgress": {"transporting": True}}, "left-first-stage"),
        ):
            with self.subTest(updates=updates):
                self.assertEqual(check.stop_reason(report(**updates)), expected)

    def test_profile_assistance_identity_and_process_errors_are_all_acceptance_gates(self):
        for updates, errors, reason in (
            ({"selectedSurvivor": "Commando"}, [], "survivor selection"),
            ({"developerSurvivorOverride": True}, [], "survivor selection"),
            ({"profile": {"appliedRuns": 14}}, [], "profile run count"),
            ({"profile": {}}, [], "profile run count"),
            ({"debugAcceleration": {}}, [], "not marked assisted"),
            ({}, ["current process error"], "current-process"),
        ):
            with self.subTest(updates=updates, errors=errors):
                failures = check.assess("Huntress", "four-slots-activated", report(), report(**updates), errors)
                self.assertTrue(any(reason in failure for failure in failures), failures)
        self.assertTrue(check.assess("Huntress", "process-exited", None, None, []))
        untouched = report()
        self.assertEqual(check.assess("Huntress", "four-slots-activated", None, copy.deepcopy(untouched), []), ["profile run count changed or missing"])


class IsolatedSkillAssessmentTests(unittest.TestCase):
    def fixture(self, slot="utility"):
        value = report(selectedSurvivor="Mage", developerSkillIsolationAssisted=True, diagnosticSkillIsolationSlot=slot)
        value["survivorSkills"]["slots"] = [
            {
                "slot": name,
                "authorityActivations": 1,
                "serverActivations": 1,
                "definition": "Native" + name.title(),
                "declaredActivationState": "EntityStates.Native.Activate",
                "machineState": "EntityStates.GenericCharacterMain",
            }
            for name in check.SLOTS
        ]
        value["survivorSkills"]["components"] = [
            {"present": True, "canonicalSlot": name.title(), "componentIndex": index, "definition": "Native" + name.title()}
            for index, name in enumerate(check.SLOTS)
        ]
        value["survivorSkills"]["skillVariantInventory"] = {
            "status": "available",
            "bodyIndex": 0,
            "selectionSource": "native-master-loadout-live",
            "components": [
                {
                    "componentIndex": index,
                    "familyCatalogIndex": 100 + index,
                    "selectedLoadoutVariantIndex": 0,
                    "selectedLoadoutSkillCatalogIndex": 200 + index,
                    "runtimeSkillCatalogIndex": 200 + index,
                    "runtimeDefinitionStatus": "matches-selected-native-loadout",
                    "variants": [{"variantIndex": 0, "skillCatalogIndex": 200 + index, "skillName": "Native" + name.title()}],
                }
                for index, name in enumerate(check.SLOTS)
            ],
        }
        value["skillInputCoverage"] = {
            "mode": "isolated-slot",
            "isolationSlot": slot,
            "outcome": "isolated-slot-observation-complete",
            "completed": True,
            "selectedCallbacksObserved": True,
            "elapsedSeconds": check.ISOLATED_SKILL_MAX_SECONDS,
            "slots": [{"slot": slot, "authorityBefore": 0, "serverBefore": 0, "authorityAfter": 1, "serverAfter": 1, "inputBankEdges": 1}],
        }
        value["world"] = {"seconds": check.ISOLATED_SKILL_MAX_SECONDS}
        return value

    def test_isolated_mode_needs_only_selected_edge_and_fresh_callback_pair(self):
        value = self.fixture()
        self.assertTrue(check.isolated_skill_success(value, "utility"))
        self.assertEqual(check.isolated_stop_reason(value, "utility"), "isolated-slot-observation-complete")
        for key, bad in (("inputBankEdges", 0), ("authorityAfter", 0), ("serverAfter", 0)):
            broken = copy.deepcopy(value)
            broken["skillInputCoverage"]["slots"][0][key] = bad
            self.assertFalse(check.isolated_skill_success(broken, "utility"))

    def test_callback_pair_does_not_end_or_pass_60_second_window(self):
        value = self.fixture()
        value["skillInputCoverage"].update(completed=False, outcome="isolated-slot-callbacks-observed")
        value["world"]["seconds"] = check.ISOLATED_SKILL_MAX_SECONDS - 1
        value["skillInputCoverage"]["elapsedSeconds"] = check.ISOLATED_SKILL_MAX_SECONDS - 1
        self.assertIsNone(check.isolated_stop_reason(value, "utility"))
        self.assertFalse(check.isolated_skill_success(value, "utility"))
        value["world"]["seconds"] = check.ISOLATED_SKILL_MAX_SECONDS
        self.assertIsNone(check.isolated_stop_reason(value, "utility"))
        value["skillInputCoverage"].update(completed=True, outcome="isolated-slot-observation-complete")
        value["skillInputCoverage"]["elapsedSeconds"] = check.ISOLATED_SKILL_MAX_SECONDS
        self.assertEqual(check.isolated_stop_reason(value, "utility"), "isolated-slot-observation-complete")

    def test_outer_world_deadline_waits_for_owner_elapsed_bound(self):
        value = self.fixture()
        value["skillInputCoverage"].update(completed=False, outcome="duration-exhausted", elapsedSeconds=check.ISOLATED_SKILL_MAX_SECONDS - 0.01)
        self.assertIsNone(check.isolated_stop_reason(value, "utility"))
        value["skillInputCoverage"]["elapsedSeconds"] = check.ISOLATED_SKILL_MAX_SECONDS
        self.assertEqual(check.isolated_stop_reason(value, "utility"), "isolated-slot-deadline")

    def test_wrong_mode_slot_identity_or_native_variant_refuses_success(self):
        value = self.fixture()
        value["skillInputCoverage"]["mode"] = "all-four-slots"
        self.assertFalse(check.isolated_skill_success(value, "utility"))
        value = self.fixture()
        value["survivorSkills"]["components"].append(copy.deepcopy(value["survivorSkills"]["components"][2]))
        self.assertFalse(check.isolated_skill_success(value, "utility"))
        value = self.fixture()
        self.assertFalse(check.isolated_skill_success(value, "special"))
        value = self.fixture()
        value["survivorSkills"]["skillVariantInventory"]["components"][2]["runtimeDefinitionStatus"] = "differs-from-selected-native-loadout"
        self.assertFalse(check.isolated_skill_success(value, "utility"))

    def test_combined_variant_request_requires_exact_post_spawn_live_contract(self):
        value = self.fixture()
        selector = {"survivor": "Mage", "entries": [{"componentIndex": 2, "familyCatalogIndex": 102, "variantIndex": 1, "skillCatalogIndex": 802}]}
        live = value["survivorSkills"]["skillVariantInventory"]["components"][2]
        live.update(selectedLoadoutVariantIndex=1, selectedLoadoutSkillCatalogIndex=802, runtimeSkillCatalogIndex=802)
        live["variants"].append({"variantIndex": 1, "skillCatalogIndex": 802, "skillName": "MageUtilityAlt"})
        value["survivorSkills"]["slots"][2]["definition"] = "MageUtilityAlt"
        value["survivorSkills"]["components"][2]["definition"] = "MageUtilityAlt"
        value["developerSkillVariantOverride"] = selector
        value["developerSkillVariantAssisted"] = True
        value["developerSkillVariantOverrideReport"] = {"status": "applied", "applied": True, "assisted": True, "effectiveSkillVariants": [0, 0, 1, 0]}
        self.assertEqual(check.assess_isolated_skill("Mage", "utility", "isolated-slot-observation-complete", value, value, [], selector), [])
        value["survivorSkills"]["skillVariantInventory"]["components"][2]["runtimeSkillCatalogIndex"] = 201
        self.assertTrue(check.assess_isolated_skill("Mage", "utility", "isolated-slot-observation-complete", value, value, [], selector))
        value = self.fixture()
        primary_catalog = value["survivorSkills"]["skillVariantInventory"]["components"][0]
        primary_catalog.update(selectedLoadoutVariantIndex=1, selectedLoadoutSkillCatalogIndex=201, runtimeSkillCatalogIndex=201)
        primary_catalog["variants"].append({"variantIndex": 1, "skillCatalogIndex": 201, "skillName": "OtherPrimary"})
        selector = {"survivor": "Mage", "entries": [{"componentIndex": 2, "familyCatalogIndex": 102, "variantIndex": 0, "skillCatalogIndex": 202}]}
        value["developerSkillVariantOverride"] = selector
        value["developerSkillVariantAssisted"] = True
        value["developerSkillVariantOverrideReport"] = {"status": "applied", "applied": True, "assisted": True, "effectiveSkillVariants": [0, 0, 0, 0]}
        self.assertIn(
            "post-spawn effective native loadout differs from selected native variants",
            check.assess_isolated_skill("Mage", "utility", "isolated-slot-observation-complete", value, value, [], selector),
        )

    def test_default_four_slot_contract_remains_separate(self):
        value = self.fixture()
        self.assertEqual(check.stop_reason(report()), "four-slots-activated")
        self.assertFalse(check.isolated_skill_success(report(), "utility"))

    def test_multitarget_isolation_refuses_before_device_discovery(self):
        with patch.object(check, "SurvivorCheckDevice") as device:
            with self.assertRaisesRegex(ValueError, "exactly one"):
                check.check_survivors("Mage,Huntress", skill_slot="utility")
            device.assert_not_called()


class FakeClock:
    def __init__(self):
        self.value = 0.0

    def monotonic(self):
        return self.value

    def sleep(self, seconds):
        self.value += seconds


class SurvivorRunnerTests(unittest.TestCase):
    def run_case(self, *, stale=False, errors=False, capture_error=False, early_error=False, stale_pid_error=False, host_deadline_seconds=420):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        reports = [
            report(pid="old", attempt="fixture", id=check.SPINE_ID),
            report(pid="42", attempt="wrong-attempt", id=check.SPINE_ID),
            report(pid="42", attempt="fixture", id="other-session"),
            report(pid="42", attempt="fixture", id=check.SPINE_ID),
        ]
        if early_error:
            pending = report(pid="42", attempt="fixture", id=check.SPINE_ID, world={"seconds": 10})
            for slot in pending["survivorSkills"]["slots"]:
                slot["authorityActivations"] = 0
                slot["serverActivations"] = 0
            reports = [pending]
        replies = iter(reports if stale else reports[-1:])
        device = Mock()

        def shell(*args, **kwargs):
            if args[0] == "pidof":
                return "42"
            if args[0] == "cat":
                if early_error:
                    return json.dumps(reports[0])
                return json.dumps(next(replies))
            return ""

        device.sh.side_effect = shell
        device.launch.return_value = {"pid": "42"}
        error_pid = "43" if stale_pid_error else "42"
        error_line = "10-19 01:02:03.004 " + error_pid + " 53 E Unity : failure"
        device.cmd.return_value = error_line if errors or early_error or stale_pid_error else ""
        if capture_error:
            device.collect.side_effect = RuntimeError("capture transfer failed")
        clock = FakeClock()
        device.fake_clock = clock
        with (
            patch.object(check, "WORK", root),
            patch.object(check.time, "sleep", side_effect=clock.sleep),
            patch.object(check.time, "monotonic", side_effect=clock.monotonic),
            patch.object(check, "HOST_DEADLINE_SECONDS", host_deadline_seconds),
        ):
            try:
                result = check.check_one(device, "Huntress", "fixture", "/owned/runtime", root / "case", {"apk_sha256": "a" * 64})
            except RuntimeError:
                if not capture_error:
                    raise
                result = None
        return result, device, root

    def test_current_pid_attempt_and_session_are_required_and_stop_precedes_collection(self):
        result, device, root = self.run_case(stale=True)
        self.assertTrue(result["success"], result)
        calls = device.mock_calls
        stop = calls.index(unittest.mock.call.sh("am", "force-stop", check.PACKAGE, check=False))
        logs = next(i for i, call in enumerate(calls) if call[0] == "cmd" and call.args[0] == "logcat")
        self.assertLess(stop, logs)
        self.assertEqual(sum(call[0] == "collect" and call.args[0] == "screenshot" for call in calls), 1)
        self.assertTrue((root / "case/final-report.json").exists())
        device.display.assert_called_with(False)

    def test_current_process_errors_fail_despite_four_activations(self):
        result, device, root = self.run_case(errors=True)
        self.assertFalse(result["success"])
        self.assertIn("unexpected current-process Unity/Android errors", result["failures"])

    def test_logged_error_stops_before_four_callbacks_and_preserves_first_evidence(self):
        result, device, root = self.run_case(early_error=True)
        self.assertFalse(result["success"])
        self.assertEqual(result["stop"], "first-runtime-log-error")
        self.assertEqual(result["runtime_errors"], ["10-19 01:02:03.004 42 53 E Unity : failure"])
        self.assertEqual(result["first_failure"], result["runtime_errors"][0])
        self.assertEqual(device.fake_clock.value, check.LOG_POLL_SECONDS)
        self.assertEqual(result["missing_activations"], list(check.SLOTS))
        self.assertTrue((root / "case/first-report.json").exists())
        self.assertTrue((root / "case/current-process.log").exists())
        self.assertEqual(
            (root / "case/first-error-poll.log").read_text(),
            "10-19 01:02:03.004 42 53 E Unity : failure",
        )
        device.collect.assert_any_call("screenshot", root / "case/first-world-capture")

    def test_late_error_in_final_log_still_fails_and_is_recorded(self):
        result, device, root = self.run_case(errors=True)
        self.assertFalse(result["success"])
        self.assertEqual(result["stop"], "four-slots-activated")
        self.assertIn("current-process", " ".join(result["failures"]))
        self.assertEqual(result["runtime_errors"], ["10-19 01:02:03.004 42 53 E Unity : failure"])
        self.assertEqual(result["first_failure"], result["runtime_errors"][0])

    def test_stale_pid_errors_are_ignored_during_poll_and_final_collection(self):
        result, device, root = self.run_case(early_error=True, stale_pid_error=True, host_deadline_seconds=20)
        self.assertFalse(result["success"])  # No callbacks before the deliberately short host deadline.
        self.assertEqual(result["runtime_errors"], [])
        self.assertIsNone(result["first_failure"])
        self.assertFalse(any("current-process" in failure for failure in result["failures"]))
        self.assertEqual(device.fake_clock.value, 20)
        self.assertEqual(sum(call[0] == "cmd" and call.args[0] == "logcat" for call in device.mock_calls), 2)

    def test_logged_error_finalizers_remove_selector_stop_app_and_sleep_display(self):
        result, device, root = self.run_case(early_error=True)
        self.assertFalse(result["success"])
        device.sh.assert_any_call("rm", "-f", "/owned/runtime/movement-batch-selection.json", check=False)
        device.sh.assert_any_call("am", "force-stop", check.PACKAGE, check=False)
        device.display.assert_called_once_with(False)

    def test_capture_failure_still_removes_selection_stops_app_and_sleeps_display(self):
        result, device, root = self.run_case(capture_error=True)
        self.assertIsNone(result)
        device.sh.assert_any_call("rm", "-f", "/owned/runtime/movement-batch-selection.json", check=False)
        device.sh.assert_any_call("am", "force-stop", check.PACKAGE, check=False)
        device.display.assert_called_once_with(False)


class SkillVariantSelectionTests(unittest.TestCase):
    def valid_catalog_inventory(self):
        return {
            "status": "available",
            "bodyIndex": 7,
            "selectionSource": "native-master-loadout-live",
            "components": [
                {
                    "componentIndex": 0,
                    "familyCatalogIndex": 299,
                    "selectedLoadoutVariantIndex": 0,
                    "selectedLoadoutSkillCatalogIndex": 155,
                    "runtimeSkillCatalogIndex": 155,
                    "runtimeDefinitionStatus": "matches-selected-native-loadout",
                    "skillName": "Primary",
                    "variants": [{"variantIndex": 0, "skillCatalogIndex": 155, "skillName": "PrimaryA", "unlockableName": "", "expansionGated": False}],
                },
                {
                    "componentIndex": 1,
                    "familyCatalogIndex": 300,
                    "selectedLoadoutVariantIndex": 0,
                    "selectedLoadoutSkillCatalogIndex": 160,
                    "runtimeSkillCatalogIndex": -1,
                    "runtimeDefinitionStatus": "uninitialized-or-unassigned",
                    "skillName": "ToolbotBackup",
                    "variants": [{"variantIndex": 0, "skillCatalogIndex": 160, "skillName": "Backup", "unlockableName": "", "expansionGated": False}],
                },
                {
                    "componentIndex": 2,
                    "familyCatalogIndex": 299,
                    "selectedLoadoutVariantIndex": 0,
                    "selectedLoadoutSkillCatalogIndex": 155,
                    "runtimeSkillCatalogIndex": 180,
                    "runtimeDefinitionStatus": "differs-from-selected-native-loadout",
                    "skillName": "ToolbotPrimary",
                    "variants": [{"variantIndex": 0, "skillCatalogIndex": 155, "skillName": "PrimaryA", "unlockableName": "", "expansionGated": False}],
                },
                {
                    "componentIndex": 3,
                    "familyCatalogIndex": 302,
                    "selectedLoadoutVariantIndex": 0,
                    "selectedLoadoutSkillCatalogIndex": 161,
                    "runtimeSkillCatalogIndex": 161,
                    "runtimeDefinitionStatus": "matches-selected-native-loadout",
                    "skillName": "ToolbotUtility",
                    "variants": [{"variantIndex": 0, "skillCatalogIndex": 161, "skillName": "Utility", "unlockableName": "", "expansionGated": False}],
                },
                {
                    "componentIndex": 4,
                    "familyCatalogIndex": 301,
                    "selectedLoadoutVariantIndex": 0,
                    "selectedLoadoutSkillCatalogIndex": 806,
                    "runtimeSkillCatalogIndex": 806,
                    "runtimeDefinitionStatus": "matches-selected-native-loadout",
                    "skillName": "ToolbotArm",
                    "variants": [
                        {"variantIndex": 0, "skillCatalogIndex": 806, "skillName": "ArmA", "unlockableName": "", "expansionGated": False},
                        {"variantIndex": 1, "skillCatalogIndex": 807, "skillName": "ArmB", "unlockableName": "", "expansionGated": False},
                    ],
                },
            ],
        }

    def write_selector(self, directory, value):
        path = Path(directory) / "variants.json"
        path.write_text(json.dumps(value))
        return path

    def valid_selector(self, survivor="Toolbot"):
        return {
            "survivor": survivor,
            "entries": [
                {"componentIndex": 4, "familyCatalogIndex": 301, "variantIndex": 1, "skillCatalogIndex": 807},
                {"componentIndex": 2, "familyCatalogIndex": 299, "variantIndex": 0, "skillCatalogIndex": 155},
            ],
        }

    def matching_live_inventory(self, effective):
        inventory = copy.deepcopy(self.valid_catalog_inventory())
        inventory["selectionSource"] = "native-master-loadout-live"
        for row in inventory["components"]:
            variant = effective[row["componentIndex"]]
            row["selectedLoadoutVariantIndex"] = variant
            row["selectedLoadoutSkillCatalogIndex"] = row["variants"][variant]["skillCatalogIndex"]
            row["runtimeSkillCatalogIndex"] = row["selectedLoadoutSkillCatalogIndex"]
            row["runtimeDefinitionStatus"] = "matches-selected-native-loadout"
        return inventory

    def test_strict_selection_is_per_run_and_assisted(self):
        with tempfile.TemporaryDirectory() as directory:
            selector = self.write_selector(directory, self.valid_selector())
            parsed = check.read_skill_variant_selection(selector, "Toolbot")
        value = check.survivor_selection("variant-attempt", "Toolbot", parsed)
        self.assertEqual(value["developerSkillVariantOverride"], parsed)
        self.assertIn("per-run", value["debugOptions"]["purpose"])
        self.assertNotIn("profile", parsed)
        self.assertNotIn("unlock", parsed)

    def test_strict_schema_rejects_unknown_duplicate_wrong_and_ambiguous_fields(self):
        bad_values = []
        extra = self.valid_selector()
        extra["writeProfile"] = True
        bad_values.append((extra, "exactly"))
        bool_index = self.valid_selector()
        bool_index["entries"][0]["variantIndex"] = True
        bad_values.append((bool_index, "nonnegative"))
        duplicate_component = self.valid_selector()
        duplicate_component["entries"][1]["componentIndex"] = 4
        bad_values.append((duplicate_component, "same GenericSkill"))
        wrong_survivor = self.valid_selector("Engi")
        bad_values.append((wrong_survivor, "single --target"))
        malformed_entry = self.valid_selector()
        malformed_entry["entries"][0]["skillCatalogIndex"] = None
        bad_values.append((malformed_entry, "nonnegative"))
        with tempfile.TemporaryDirectory() as directory:
            for value, message in bad_values:
                with self.subTest(value=value):
                    selector = self.write_selector(directory, value)
                    with self.assertRaisesRegex(ValueError, message):
                        check.read_skill_variant_selection(selector, "Toolbot")

    def test_duplicate_json_keys_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "variants.json"
            path.write_text('{"survivor":"Toolbot","survivor":"Engi","entries":[]}')
            with self.assertRaisesRegex(ValueError, "duplicate property"):
                check.read_skill_variant_selection(path, "Toolbot")

    def test_variant_selector_requires_single_target_before_device_access(self):
        with tempfile.TemporaryDirectory() as directory:
            selector = self.write_selector(directory, self.valid_selector())
            with patch.object(check, "SurvivorCheckDevice") as device:
                with self.assertRaisesRegex(ValueError, "exactly one"):
                    check.check_survivors("Toolbot,Engi", str(selector))
                device.assert_not_called()

    def test_report_requires_applied_assisted_result(self):
        requested = self.valid_selector()
        expected = check.survivor_selection("fixture", "Toolbot", requested)["developerSkillVariantOverride"]
        inventory = self.valid_catalog_inventory()
        inventory["selectionSource"] = "native-master-loadout-pre-spawn"
        effective = [0, 0, 0, 0, 1]
        live_inventory = self.matching_live_inventory(effective)
        final = report(
            selectedSurvivor="Toolbot",
            developerSurvivorOverride=True,
            developerSkillVariantAssisted=True,
            developerSkillVariantOverride=expected,
            developerSkillVariantOverrideReport={
                "requested": True,
                "status": "applied",
                "applied": True,
                "assisted": True,
                "effectiveSkillVariants": effective,
                "skillVariantInventory": inventory,
            },
            survivorSkills={**report()["survivorSkills"], "skillVariantInventory": live_inventory},
        )
        self.assertEqual(check.assess("Toolbot", "four-slots-activated", final, final, [], expected), [])
        final["developerSkillVariantOverrideReport"]["effectiveSkillVariants"][4] = 0
        self.assertIn(
            "per-run effective native loadout differs from the requested skill variants",
            check.assess("Toolbot", "four-slots-activated", final, final, [], expected),
        )
        final["developerSkillVariantOverrideReport"]["effectiveSkillVariants"][4] = 1
        final["developerSkillVariantAssisted"] = False
        self.assertIn("per-run skill-variant assisted session marker is absent", check.assess("Toolbot", "four-slots-activated", final, final, [], expected))
        final["developerSkillVariantAssisted"] = True
        final["developerSkillVariantOverrideReport"] = {"status": "applied", "applied": True, "assisted": False}
        self.assertIn("per-run skill-variant override was not applied as assisted", check.assess("Toolbot", "four-slots-activated", final, final, [], expected))

    def test_full_variant_contract_rejects_wrong_post_spawn_definition(self):
        selector = self.valid_selector()
        expected = check.survivor_selection("fixture", "Toolbot", selector)["developerSkillVariantOverride"]
        effective = [0, 0, 0, 0, 1]
        pre_spawn = copy.deepcopy(self.valid_catalog_inventory())
        pre_spawn["selectionSource"] = "native-master-loadout-pre-spawn"
        live = self.matching_live_inventory(effective)
        final = report(
            selectedSurvivor="Toolbot",
            developerSurvivorOverride=True,
            developerSkillVariantAssisted=True,
            developerSkillVariantOverride=expected,
            developerSkillVariantOverrideReport={
                "requested": True,
                "status": "applied",
                "applied": True,
                "assisted": True,
                "effectiveSkillVariants": effective,
                "skillVariantInventory": pre_spawn,
            },
            survivorSkills={**report()["survivorSkills"], "skillVariantInventory": live},
        )
        # Unrequested component 1 is intentionally unassigned; this contract checks the selected alternates only.
        live["components"][1]["runtimeSkillCatalogIndex"] = -1
        live["components"][1]["runtimeDefinitionStatus"] = "uninitialized-or-unassigned"
        self.assertEqual(check.assess("Toolbot", "four-slots-activated", final, final, [], expected), [])
        live["components"][4]["runtimeSkillCatalogIndex"] = 806
        live["components"][4]["runtimeDefinitionStatus"] = "differs-from-selected-native-loadout"
        failures = check.assess("Toolbot", "four-slots-activated", final, final, [], expected)
        self.assertIn("post-spawn native family/variant/skill identity differs from request", failures)

    def test_full_variant_contract_requires_live_inventory_and_reports_both_snapshots(self):
        selector = self.valid_selector()
        expected = check.survivor_selection("fixture", "Toolbot", selector)["developerSkillVariantOverride"]
        effective = [0, 0, 0, 0, 1]
        pre_spawn = copy.deepcopy(self.valid_catalog_inventory())
        pre_spawn["selectionSource"] = "native-master-loadout-pre-spawn"
        final = report(
            selectedSurvivor="Toolbot",
            developerSurvivorOverride=True,
            developerSkillVariantAssisted=True,
            developerSkillVariantOverride=expected,
            developerSkillVariantOverrideReport={
                "requested": True,
                "status": "applied",
                "applied": True,
                "assisted": True,
                "effectiveSkillVariants": effective,
                "skillVariantInventory": pre_spawn,
            },
            survivorSkills={**report()["survivorSkills"], "skillVariantInventory": self.matching_live_inventory(effective)},
        )
        fields = check.skill_variant_inventory_report_fields(final)
        self.assertEqual(fields["pre_spawn_skill_variant_catalog_inventory"]["selectionSource"], "native-master-loadout-pre-spawn")
        self.assertEqual(fields["post_spawn_skill_variant_catalog_inventory"]["selectionSource"], "native-master-loadout-live")
        self.assertEqual(fields["skill_variant_catalog_inventory"], fields["pre_spawn_skill_variant_catalog_inventory"])
        del final["survivorSkills"]["skillVariantInventory"]
        fields = check.skill_variant_inventory_report_fields(final)
        self.assertEqual(fields["post_spawn_skill_variant_catalog_inventory"]["status"], "unavailable")
        failures = check.assess("Toolbot", "four-slots-activated", final, final, [], expected)
        self.assertIn("post-spawn native skill-variant inventory unavailable or not live", failures)

    def test_catalog_inventory_exposes_exact_indexes_and_refuses_unbounded_or_ambiguous_shapes(self):
        report_value = {"developerSkillVariantOverrideReport": {"requested": True, "skillVariantInventory": self.valid_catalog_inventory()}}
        parsed = check.skill_variant_catalog_inventory(report_value)
        self.assertEqual(parsed["status"], "valid")
        self.assertEqual(parsed["components"][4]["familyCatalogIndex"], 301)
        self.assertEqual(parsed["components"][4]["variants"][1]["skillCatalogIndex"], 807)
        self.assertEqual(parsed["components"][1]["runtimeDefinitionStatus"], "uninitialized-or-unassigned")
        self.assertEqual(parsed["components"][2]["runtimeDefinitionStatus"], "differs-from-selected-native-loadout")
        inventory = self.valid_catalog_inventory()
        inventory["components"].append(copy.deepcopy(inventory["components"][0]))
        report_value["developerSkillVariantOverrideReport"]["skillVariantInventory"] = inventory
        self.assertEqual(check.skill_variant_catalog_inventory(report_value)["status"], "invalid")
        inventory = self.valid_catalog_inventory()
        inventory["components"][4]["variants"] *= 9
        report_value["developerSkillVariantOverrideReport"]["skillVariantInventory"] = inventory
        self.assertEqual(check.skill_variant_catalog_inventory(report_value)["status"], "invalid")

    def test_default_inline_override_report_does_not_hide_live_inventory(self):
        value = {
            "developerSkillVariantOverrideReport": {"requested": False, "skillVariantInventory": {"status": "", "components": []}},
            "survivorSkills": {"skillVariantInventory": self.valid_catalog_inventory()},
        }
        self.assertEqual(check.skill_variant_catalog_inventory(value)["status"], "valid")


if __name__ == "__main__":
    unittest.main()
