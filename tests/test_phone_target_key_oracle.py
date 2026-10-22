"""The SDK verification protocol must not supply or normalize expected answers."""

import copy
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts/lab"))
import phone_target_key_oracle as oracle


class TargetKeyOracleTests(unittest.TestCase):
    def fixture(self):
        metadata = dict(
            profile="native-target-key-inputs-v1",
            source_argument_slots_complete=True,
            root_generation_qualified=False,
            rows=[dict(key=17, label="authored"), dict(key=23, label="fixture")],
        )
        request = oracle.queries(metadata)
        inputs = dict(source_commit="a" * 40, request_sha256="b" * 64)
        report = dict(
            schema=1,
            profile="target-key-api-observations-v1",
            unity=oracle.guard.VERSION,
            source_commit=inputs["source_commit"],
            success=True,
            phase="complete",
            failure="",
            request_sha256=inputs["request_sha256"],
            game_inputs=False,
            player_built=False,
            phone_generation_input=False,
            root_generation_qualified=False,
            keys=[dict(key=17, value="authored", error=""), dict(key=23, value="fixture", error="")],
            names=[dict(name="authored", value=17, returned=True, error=""), dict(name="fixture", value=23, returned=True, error="")],
        )
        return metadata, request, inputs, report

    def test_request_contains_only_separate_queries_without_expected_pairs(self):
        metadata, request, _, _ = self.fixture()
        self.assertEqual(request, dict(schema=1, keys=[17, 23], names=["authored", "fixture"]))
        for key, value in (
            ("profile", "unknown"),
            ("source_argument_slots_complete", False),
            ("root_generation_qualified", True),
            ("rows", [dict(key=True, label="authored")]),
            ("rows", [dict(key=1, label="invalid/name")]),
        ):
            with self.subTest(key=key), self.assertRaises(ValueError):
                oracle.queries(dict(metadata, **{key: value}))

    def test_actual_guard_accepts_fresh_target_attempt_and_refuses_reuse(self):
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory).resolve() / "work"
            project = work / "rebuild/phone-wrapper-oracle/target-authored/project"
            with oracle.guard.owned_directory(project, work, create=True, new=True):
                self.assertTrue(project.is_dir())
            with self.assertRaises(FileExistsError):
                with oracle.guard.owned_directory(project, work, create=True, new=True):
                    self.fail("Existing SDK projects cannot be reused")

    def test_observation_identity_scope_types_and_order_are_exact(self):
        _, request, inputs, report = self.fixture()
        oracle.observations(report, inputs, request)
        for key, value in (
            ("schema", 2),
            ("profile", "wrong"),
            ("unity", "other"),
            ("source_commit", "c" * 40),
            ("success", False),
            ("phase", "names"),
            ("failure", "retained failure"),
            ("game_inputs", True),
            ("player_built", True),
            ("phone_generation_input", True),
            ("root_generation_qualified", True),
            ("request_sha256", "c" * 64),
            ("keys", report["keys"][:-1]),
            ("names", list(reversed(report["names"]))),
        ):
            with self.subTest(key=key), self.assertRaises(ValueError):
                oracle.observations(dict(report, **{key: value}), inputs, request)
        for field, key, value in (("keys", "value", 17), ("names", "value", True), ("names", "returned", 1)):
            changed = copy.deepcopy(report)
            changed[field][0][key] = value
            with self.subTest(field=field, key=key), self.assertRaises(ValueError):
                oracle.observations(changed, inputs, request)

    def test_comparison_preserves_case_aliases_exceptions_and_unreturned_queries(self):
        metadata, _, _, report = self.fixture()
        self.assertTrue(oracle.compare(report, metadata)["all_exact"])
        for field, key, value in (
            ("keys", "value", "Authored"),
            ("keys", "error", "SDK refused"),
            ("names", "value", 99),
            ("names", "returned", False),
            ("names", "error", "SDK refused"),
        ):
            changed = copy.deepcopy(report)
            changed[field][0][key] = value
            with self.subTest(field=field, key=key):
                result = oracle.compare(changed, metadata)
                self.assertFalse(result["all_exact"])
                self.assertFalse(result["root_generation_qualified"])
                if field == "keys" and key == "value":
                    self.assertEqual(result["rows"][0]["observed_name"], "Authored")
