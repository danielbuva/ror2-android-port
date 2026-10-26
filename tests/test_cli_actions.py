"""Prototype dispatch contracts frozen from the pre-registry main.py AST.

The synthetic call/effect fixture is independent of the registry. Every target
module is replaced, so these tests cannot build, start an editor or use a device.
"""

import contextlib
from copy import deepcopy
import io
import json
from pathlib import Path
import runpy
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts/lab"))
import actions
import common

EXPECTED = json.loads((ROOT / "tests/fixtures/prototype_calls.json").read_text())
FIXTURE_ROOT = Path("/fixture-root")
FIXTURE_WORK = FIXTURE_ROOT / "work"


class PrototypeActionTests(unittest.TestCase):
    def setUp(self):
        self.calls = []
        self.effects = []
        self.modules = {}
        self.equal = True
        self.returncode = 7
        for row in EXPECTED.values():
            for call in row["calls"]:
                module, function = call["module"], call["function"]
                if module not in self.modules:
                    self.modules[module] = ModuleType(module)
                setattr(self.modules[module], function, Mock(side_effect=self.record(module, function)))
        self.modules["source_scene_candidate"].SCENES = {"lakes": {}, "fixture-stage": {}}
        # CLI cleanup must never construct a replacement device.
        device = ModuleType("device")
        device.Device = Mock()
        device.Device.sleep_awakened.return_value = []
        self.modules["device"] = device
        patcher = patch.dict(sys.modules, self.modules)
        patcher.start()
        self.addCleanup(patcher.stop)
        patcher = patch.multiple(common, ROOT=FIXTURE_ROOT, WORK=FIXTURE_WORK, read=self.read, write=self.write, now=lambda: "fixture-time")
        patcher.start()
        self.addCleanup(patcher.stop)

    def record(self, module, function):
        def call(*args, **kwargs):
            self.calls.append(dict(module=module, function=function, args=deepcopy(args), kwargs=deepcopy(kwargs)))
            if module == "subprocess":
                return self.returncode
            return {"equal": self.equal, "synthetic": module + "." + function}

        return call

    def read(self, path):
        self.effects.append(["read", str(path)])
        if str(path).endswith("current.json"):
            return {"path": "work/fixture-attempt"}
        if str(path).endswith("attempt.json"):
            return {"preserved": "fixture"}
        return {"receipt": str(path)}

    def write(self, path, value):
        self.effects.append(["write", str(path), deepcopy(value)])

    def args(self, name, **options):
        return SimpleNamespace(**dict(dict(action=name, target="lab", debug_options=None, compare=["a.json", "b.json"]), **options))

    def dispatch(self, name, **options):
        output = io.StringIO()
        code = None
        with contextlib.redirect_stdout(output), patch.object(actions, "import_module", side_effect=self.modules.__getitem__) as load:
            try:
                actions.dispatch(self.args(name, **options))
            except SystemExit as ended:
                code = ended.code
        spec = actions.ACTIONS.get(name, actions.DEFAULT_ACTION)
        load.assert_called_once_with(spec.module)
        return code, output.getvalue()

    def expected_calls(self, name):
        calls = deepcopy(EXPECTED[name]["calls"])
        for call in calls:
            args = call["args"]
            target = (call["module"], call["function"])
            if target == ("project_manifest", "capture"):
                args[0] = Path(args[0])
            elif target == ("source_scene_candidate", "prepare"):
                args[0] = tuple(args[0])
            elif target == ("subprocess", "call"):
                args[0][0] = sys.executable
            call["args"] = tuple(args)
        return calls

    def assert_contract(self, name):
        code, output = self.dispatch(name)
        self.assertEqual(self.calls, self.expected_calls(name))
        self.assertEqual(self.effects, EXPECTED[name]["effects"])
        self.assertEqual(output, EXPECTED[name]["stdout"])
        self.assertEqual(code, EXPECTED[name]["exit"])

    def test_survivor_variant_selector_is_forwarded_only_when_explicit(self):
        self.dispatch("survivor-kit-check", target="Engi", skill_variants="work/config/variants.json")
        self.assertEqual(
            self.calls, [dict(module="survivor_check", function="check_survivors", args=("Engi",), kwargs=dict(skill_variants="work/config/variants.json"))]
        )

    def test_survivor_slot_and_variant_selectors_compose_only_when_explicit(self):
        self.dispatch("survivor-kit-check", target="Mage", skill_variants="work/config/mage.json", skill_slot="utility")
        self.assertEqual(
            self.calls,
            [
                dict(
                    module="survivor_check",
                    function="check_survivors",
                    args=("Mage",),
                    kwargs=dict(skill_variants="work/config/mage.json", skill_slot="utility"),
                )
            ],
        )

    def cli(self, *options):
        output, errors = io.StringIO(), io.StringIO()
        code = 0
        with patch.object(sys, "argv", ["dev", "prototype", *options]), contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
            try:
                runpy.run_path(str(ROOT / "scripts/lab/main.py"), run_name="__main__")
            except SystemExit as ended:
                code = ended.code
        return code, output.getvalue(), errors.getvalue()

    def test_shader_candidate_dispatch_preserves_target_and_prints_result(self):
        for name, module_name, target, expected_args, expected_kwargs in (
            ("shader-outline-candidate", "shader_outline", "outline-highlight", ("outline-highlight",), {}),
            ("shader-ramp-fog", "shader_ramp_fog", "lab", (), {"target": "ramp-fog"}),
            ("shader-ramp-fog", "shader_ramp_fog", "sobel-buffer", (), {"target": "sobel-buffer"}),
            ("shader-ramp-fog", "shader_ramp_fog", "sobel-outline", (), {"target": "sobel-outline"}),
        ):
            with self.subTest(action=name):
                module = ModuleType(module_name)
                module.generate = Mock(return_value={"success": True, "unity_compiled": False})
                self.modules[module_name] = module
                code, output = self.dispatch(name, target=target)
                module.generate.assert_called_once_with(*expected_args, **expected_kwargs)
                self.assertEqual(json.loads(output), {"success": True, "unity_compiled": False})
                self.assertIsNone(code)

    def test_screen_damage_dispatch_keeps_the_fixed_native_target(self):
        module = ModuleType("shader_ramp_fog")
        module.generate = Mock(return_value={"success": True, "unity_compiled": False})
        self.modules["shader_ramp_fog"] = module
        code, output = self.dispatch("shader-screen-damage")
        module.generate.assert_called_once_with(target="screen-damage")
        self.assertEqual(json.loads(output), {"success": True, "unity_compiled": False})
        self.assertIsNone(code)

    def test_shared_build_full_and_capture_options_are_explicit(self):
        module = ModuleType("shared_checkout_build")
        module.build_shared_checkout = Mock(return_value={"success": True})
        self.modules["shared_checkout_build"] = module
        self.dispatch("shared-catalog-code-build", full=True, capture_player_linker_inputs=True)
        module.build_shared_checkout.assert_called_once_with(code_only=False, capture_player_linker_inputs=True)

    def test_uncompressed_flag_requires_a_lane_full_build_before_dispatch(self):
        for lane, action in (({}, "whole-catalog-build"), ({"name": "fixture"}, "whole-catalog-code-build")):
            with self.subTest(lane=lane, action=action), patch.object(common, "lane_config", return_value=lane):
                code, _, error = self.cli("--action", action, "--bundle-compression", "uncompressed")
                self.assertEqual(code, 2)
                self.assertIn("requires whole-catalog-build in an isolated LAB_LANE", error)
                self.assertEqual(self.calls, [])

    def test_uncompressed_flag_reaches_only_the_selected_lane_full_build(self):
        with patch.object(common, "lane_config", return_value={"name": "fixture"}):
            code, _, _ = self.cli("--action", "whole-catalog-build", "--bundle-compression", "uncompressed")
        self.assertEqual(code, 0)
        self.assertEqual(self.calls, [dict(module="whole_catalog", function="build_integration", args=(), kwargs={"bundle_compression": "uncompressed"})])

    def test_touch_gesture_keeps_explicit_request_apk_and_receipt_tree(self):
        module = ModuleType("touch_gesture")
        module.run = Mock(return_value={"success": True})
        self.modules["touch_gesture"] = module
        with patch.dict(sys.modules, {"touch_gesture": module}):
            code, output, error = self.cli(
                "--action", "touch-gesture", "--target", "gesture.json", "--expected-apk-sha256", "a" * 64, "--work-dir", str(FIXTURE_WORK)
            )
        self.assertEqual((code, error), (0, ""))
        module.run.assert_called_once_with(target="gesture.json", expected_apk_sha256="a" * 64)
        self.assertEqual(json.loads(output), {"success": True})

    def test_long_memory_series_is_explicit_and_keeps_apk_and_root_walk_binding(self):
        code, _, _ = self.cli("--action", "session-memory-root-check", "--sessions", "12", "--expected-apk-sha256", "a" * 64)
        self.assertEqual(code, 0)
        self.assertEqual(
            self.calls,
            [
                dict(
                    module="session_memory_check",
                    function="check_session_memory",
                    args=(),
                    kwargs=dict(root_walk=True, sessions=12, expected_apk_sha256="a" * 64),
                )
            ],
        )

    def test_native_heap_capture_is_explicit_and_bound_to_the_base_memory_action(self):
        code, _, _ = self.cli("--action", "session-memory-check", "--sessions", "3", "--memory-snapshots", "--expected-apk-sha256", "a" * 64)
        self.assertEqual(code, 0)
        self.assertEqual(
            self.calls,
            [
                dict(
                    module="session_memory_check",
                    function="check_session_memory",
                    args=(),
                    kwargs=dict(sessions=3, memory_snapshots=True, expected_apk_sha256="a" * 64),
                )
            ],
        )

    def test_native_heap_capture_cannot_change_other_actions_or_the_static_root_walk(self):
        for action in ("session-memory-root-check", "session-abandon-check", "touch-gesture"):
            with self.subTest(action=action):
                code, _, error = self.cli("--action", action, "--memory-snapshots")
                self.assertEqual(code, 2)
                self.assertIn("--memory-snapshots requires", error)
                self.assertEqual(self.calls, [])

    def test_series_count_cannot_silently_change_an_unrelated_action(self):
        code, _, error = self.cli("--action", "session-abandon-check", "--sessions", "12")
        self.assertEqual(code, 2)
        self.assertIn("--sessions requires", error)
        self.assertEqual(self.calls, [])

    def test_translucent_candidate_dispatch_is_host_only_and_prints_result(self):
        module = ModuleType("shader_translucent")
        module.main = Mock(return_value={"unity_compiled": False, "android_accepted": False})
        self.modules["shader_translucent"] = module
        code, output = self.dispatch("shader-translucent")
        module.main.assert_called_once_with()
        self.assertEqual(json.loads(output), {"unity_compiled": False, "android_accepted": False})
        self.assertIsNone(code)

    def test_interrupted_save_dispatch_binds_apk_and_selected_receipt_tree(self):
        module = ModuleType("settings_write_interrupt_check")
        module.check_settings_write_interrupt = Mock(return_value={"success": True})
        with patch.dict(sys.modules, {"settings_write_interrupt_check": module}):
            code, output, error = self.cli("--action", "settings-write-interrupt-check", "--expected-apk-sha256", "a" * 64, "--work-dir", str(FIXTURE_WORK))
        self.assertEqual((code, error), (0, ""))
        self.assertTrue(json.loads(output)["success"])
        module.check_settings_write_interrupt.assert_called_once_with(expected_apk_sha256="a" * 64)

    def test_texture_oracle_dispatch_keeps_staging_and_explicit_check_separate(self):
        self.modules["phone_texture_oracle"] = SimpleNamespace(
            stage_action=self.record("phone_texture_oracle", "stage_action"), run_editor=self.record("phone_texture_oracle", "run_editor")
        )
        self.dispatch("phone-texture-fixture")
        self.assertEqual(self.calls, [dict(module="phone_texture_oracle", function="stage_action", args=(), kwargs={})])
        self.calls.clear()
        self.dispatch("phone-texture-check", target="work/authored-project")
        self.assertEqual(self.calls, [dict(module="phone_texture_oracle", function="run_editor", args=("work/authored-project",), kwargs={})])

    def test_alpha_batch_requires_explicit_identity_and_known_done_file(self):
        for options in (
            (),
            ("--device", "fixture-device"),
            ("--device", "fixture-device", "--expected-apk-sha256", "a" * 64),
        ):
            code, _, error = self.cli("--action", "alpha-stability-batch", *options)
            self.assertEqual(code, 2)
            self.assertIn("requires --device", error)
        self.modules["device"].Device.assert_not_called()

    def test_alpha_batch_uses_canonical_repository_and_owns_final_cleanup(self):
        module = ModuleType("alpha_stability_batch")
        module.check_alpha_stability_batch = Mock(return_value={"success": True})
        self.modules["alpha_stability_batch"] = module
        with (
            patch.dict(sys.modules, {"alpha_stability_batch": module}),
            patch.object(common.subprocess, "check_output", return_value="/canonical/.git\n") as git,
        ):
            code, output, error = self.cli(
                "--action",
                "alpha-stability-batch",
                "--device",
                "fixture-device",
                "--expected-apk-sha256",
                "a" * 64,
                "--done-file",
                "/private-evidence/done.json",
                "--prior-settings-batch",
                "/private-evidence/prior.json",
            )
        self.assertEqual((code, error), (0, ""))
        self.assertTrue(json.loads(output)["success"])
        module.check_alpha_stability_batch.assert_called_once_with(
            device_serial="fixture-device",
            expected_apk_sha256="a" * 64,
            canonical_root=Path("/canonical"),
            done_file="/private-evidence/done.json",
            prior_settings_batch="/private-evidence/prior.json",
        )
        self.assertEqual(git.call_args.kwargs["cwd"], FIXTURE_ROOT)
        self.modules["device"].Device.sleep_awakened.assert_not_called()

    def test_registry_names_and_current_status_match_documented_contract(self):
        # Added actions have separate dispatch contracts rather than changing
        # the historical pre-registry snapshot.
        added = {
            "phone-content-ambient-fixture",
            "phone-content-ambient-check",
            "phone-texture-fixture",
            "phone-texture-check",
            "shared-catalog-code-build",
            "whole-catalog-fast-build",
            "shared-catalog-fast-build",
            "shared-catalog-scripts-build",
            "whole-catalog-scripts-build",
            "apk-member-compare",
            "touch-gesture",
            "settings-write-interrupt-check",
            "alpha-stability-batch",
            "rebuild-step",
            "shader-outline-candidate",
            "shader-ramp-fog",
            "shader-screen-damage",
            "shader-translucent",
            "owner-assembly-prefix",
        }
        self.assertEqual(set(actions.ACTIONS) - added, set(EXPECTED) - {"inspect"})
        self.assertEqual(len(actions._ENTRIES), len(actions.ACTIONS))
        self.assertEqual(
            {name for name, entry in actions.ACTIONS.items() if entry.status == "current"},
            {
                "whole-catalog-fast-build",
                "shared-catalog-code-build",
                "shared-catalog-fast-build",
                "shared-catalog-scripts-build",
                "whole-catalog-scripts-build",
                "apk-member-compare",
                "rebuild-step",
                "owner-assembly-prefix",
                "shader-outline-candidate",
                "shader-ramp-fog",
                "shader-screen-damage",
                "shader-translucent",
                "phone-content-fixture",
                "phone-content-check",
                "phone-content-ambient-fixture",
                "phone-content-ambient-check",
                "phone-content-build",
                "phone-apk-fixture",
                "phone-package-check",
                "phone-host-check",
                "phone-native-fixture",
                "phone-converter-fixture",
                "phone-linker-fixture",
                "phone-root-contract",
                "phone-native-registry",
                "phone-wrapper-search",
                "phone-wrapper-oracle",
                "phone-texture-fixture",
                "phone-texture-check",
                "phone-native-apk-fixture",
                "assembly-transforms-check",
                "asset-transforms-check",
                "authored-additions-check",
                "inherited-state-check",
                "inherited-store-capture",
                "composition-update-stage",
                "composition-update-dependencies",
                "whole-catalog-prepare",
                "whole-catalog-host",
                "survivor-kit-check",
                "session-cleanup-check",
                "session-abandon-check",
                "session-memory-check",
                "session-memory-root-check",
                "touch-gesture",
                "settings-write-interrupt-check",
                "alpha-stability-batch",
                "whole-catalog-repair-bindings",
                "whole-catalog-contracts",
                "whole-catalog-host-providers",
                "whole-catalog-build",
                "whole-catalog-code-build",
                "shared-catalog-code-build",
                "whole-catalog-run",
                "project-manifest-capture",
                "project-manifest-compare",
            },
        )
        for name, entry in actions.ACTIONS.items():
            with self.subTest(action=name):
                self.assertEqual(entry.name, name)
                self.assertIn(entry.status, ("current", "historical"))
                self.assertTrue(entry.help)
                self.assertNotIn("\n", entry.help)
                if name in added:
                    continue
                primary = EXPECTED[name]["calls"][0]
                self.assertEqual((entry.module, entry.function, entry.kwargs), (primary["module"], primary["function"], primary["kwargs"]))

    def test_list_is_lazy_and_current_actions_precede_historical(self):
        # Loading the registry and listing it must not import an action module.
        with patch("importlib.import_module") as load:
            runpy.run_path(str(ROOT / "scripts/lab/actions.py"))
            code, output, errors = self.cli("--action", "list")
        load.assert_not_called()
        self.assertEqual((code, errors), (0, ""))
        self.assertEqual(self.calls, [])
        current, historical = output.removeprefix("current:\n").split("historical:\n")
        for status, section in (("current", current), ("historical", historical)):
            expected = {entry.name: entry for entry in (*actions.ACTIONS.values(), actions.DEFAULT_ACTION) if entry.status == status}
            self.assertEqual([line.split()[0] for line in section.splitlines()], sorted(expected))
            for line in section.splitlines():
                self.assertIn(expected[line.split()[0]].help, line)

    def test_default_and_unknown_cli_names_keep_the_preparation_fallback(self):
        for options in ((), ("--action", "unknown-action")):
            with self.subTest(options=options):
                self.calls.clear()
                self.assertEqual(self.cli(*options), (0, "", ""))
                self.assertEqual(self.calls, self.expected_calls("inspect"))

    def test_full_catalog_build_forwards_symbol_and_capture_options(self):
        code, _, errors = self.cli(
            "--action",
            "whole-catalog-build",
            "--debug-symbols",
            "--capture-player-linker-inputs",
            "--capture-il2cpp-invocation",
        )
        self.assertEqual((code, errors), (0, ""))
        self.assertEqual(
            self.calls,
            [
                {
                    "module": "whole_catalog",
                    "function": "build_integration",
                    "args": (),
                    "kwargs": {"android_symbols": "debugging", "capture_player_linker_inputs": True, "capture_il2cpp_invocation": True},
                }
            ],
        )

    def test_movement_debug_options_are_omitted_unless_truthy(self):
        for name in ("movement-batch-run", "movement-batch-retry"):
            for debug in (None, "", "debug.json"):
                with self.subTest(action=name, debug=debug):
                    self.calls.clear()
                    self.assertEqual(self.dispatch(name, debug_options=debug), (None, ""))
                    kwargs = {"retry": True} if name.endswith("retry") else {}
                    if debug:
                        kwargs["debug_options"] = debug
                    self.assertEqual(self.calls, [dict(module="scene_runtime", function="movement_batch_run", args=(), kwargs=kwargs)])

    def test_scene_target_all_and_shader_positional_target(self):
        self.dispatch("source-scene-prepare", target="all")
        self.modules["source_scene_candidate"].prepare.assert_called_once_with(("lakes", "fixture-stage"))
        self.modules["source_scene_candidate"].stage_unavailable_audio.assert_called_once_with()
        self.dispatch("shader-recovery", target="vulkan")
        self.modules["shader_recovery"].recover.assert_called_once_with("vulkan")

    def test_compare_and_subprocess_preserve_nonzero_exit_codes(self):
        self.equal = False
        code, output = self.dispatch("project-manifest-compare")
        self.assertEqual(code, 1)
        self.assertFalse(json.loads(output)["equal"])
        for status in (0, 1, 7):
            with self.subTest(status=status):
                self.returncode = status
                self.assertEqual(self.dispatch("repair-reconstruction"), (status, ""))

    def test_cli_argument_guards_run_before_dispatch(self):
        for options in (
            ("--debug-options", "debug.json"),
            ("--action", "project-manifest-compare"),
            ("--compare", "a.json", "b.json"),
            ("--action", "list", "--compare", "a.json", "b.json"),
            ("--action", "inspect", "--skill-slot", "utility"),
        ):
            with self.subTest(options=options):
                self.assertEqual(self.cli(*options)[0], 2)
        self.assertEqual(self.calls, [])

    def test_mutating_target_receives_fresh_keyword_lists(self):
        function = self.modules["scene_runtime"].movement_batch_run
        function.side_effect = lambda **kwargs: kwargs["cases"].append("mutated")
        self.dispatch("grounded-motion-retry")
        self.dispatch("grounded-motion-retry")
        self.assertIsNot(function.call_args_list[0].kwargs["cases"], function.call_args_list[1].kwargs["cases"])
        self.assertEqual(actions.ACTIONS["grounded-motion-retry"].kwargs["cases"], ["state-ground-motion"])


def contract_test(name):
    def test(self):
        self.assert_contract(name)

    test.__doc__ = "Old AST contract: " + name
    return test


# Give every action (plus the default fallback) its own discoverable host test.
for _name in EXPECTED:
    setattr(PrototypeActionTests, "test_dispatch_" + _name.replace("-", "_"), contract_test(_name))


if __name__ == "__main__":
    unittest.main()
