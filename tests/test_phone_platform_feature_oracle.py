"""The SDK API oracle must remain independent verification with exact queries."""

import copy
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts/lab"))
import phone_platform_feature_oracle as oracle


class PlatformFeatureOracleTests(unittest.TestCase):
    def test_fresh_destination_satisfies_actual_owned_directory_guard(self):
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory).resolve() / "work"
            destination = oracle.new_destination(work)
            project = destination / "project"
            with oracle.guard.owned_directory(project, work, create=True, new=True):
                self.assertTrue(project.is_dir())
            with self.assertRaises(FileExistsError):
                with oracle.guard.owned_directory(project, work, create=True, new=True):
                    self.fail("An existing oracle must not be reused")
            self.assertNotEqual(destination, oracle.new_destination(work))

    def fixture(self):
        declaration = dict(
            profile="android-platform-feature-declarations-v1",
            platform_define="PLATFORM_ANDROID",
            root_generation_qualified=False,
            declarations=[dict(feature="AUTHORED_FEATURE"), dict(feature="ENABLE_AUDIO")],
        )
        queries = dict(schema=1, features=oracle.query_features(declaration))
        inputs = dict(source_commit="a" * 40, query_sha256="b" * 64)
        report = dict(
            schema=1,
            profile="android-feature-api-oracle-v1",
            unity=oracle.guard.VERSION,
            source_commit=inputs["source_commit"],
            success=True,
            phase="complete",
            failure="",
            game_inputs=False,
            player_built=False,
            phone_generation_input=False,
            root_generation_qualified=False,
            target="Android",
            target_value=19,
            platform_define="PLATFORM_ANDROID",
            query_sha256=inputs["query_sha256"],
            rows=[dict(feature=value, supported=value in {"AUTHORED_FEATURE", "ENABLE_AUDIO"}) for value in queries["features"]],
        )
        return declaration, queries, inputs, report

    def test_queries_contain_no_expected_results_and_keep_native_and_unknown_probes(self):
        declaration, queries, _, _ = self.fixture()
        self.assertEqual(set(queries), {"schema", "features"})
        self.assertEqual(len(queries["features"]), len(set(queries["features"])))
        self.assertTrue(set(oracle.PROBES) <= set(queries["features"]))
        for key, value in (
            ("profile", "unknown"),
            ("platform_define", "PLATFORM_IOS"),
            ("root_generation_qualified", True),
            ("declarations", [dict(feature="not-a-macro")]),
        ):
            wrong = dict(declaration, **{key: value})
            with self.subTest(key=key), self.assertRaises(ValueError):
                oracle.query_features(wrong)

    def test_report_requires_exact_sdk_target_queries_scope_and_results(self):
        declaration, queries, inputs, report = self.fixture()
        oracle.validate_report(report, inputs, declaration, queries)
        changes = [
            ("schema", 2),
            ("profile", "wrong"),
            ("unity", "other"),
            ("source_commit", "c" * 40),
            ("success", False),
            ("phase", "query"),
            ("failure", "retained failure"),
            ("game_inputs", True),
            ("player_built", True),
            ("phone_generation_input", True),
            ("root_generation_qualified", True),
            ("target", "iOS"),
            ("target_value", 2),
            ("platform_define", "UNITY_EDITOR"),
            ("query_sha256", "c" * 64),
            ("rows", report["rows"][:-1]),
            ("rows", list(reversed(report["rows"]))),
        ]
        for key, value in changes:
            with self.subTest(key=key), self.assertRaises(ValueError):
                oracle.validate_report(dict(report, **{key: value}), inputs, declaration, queries)
        for value in (None, 1, not report["rows"][0]["supported"]):
            altered = copy.deepcopy(report)
            altered["rows"][0]["supported"] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                oracle.validate_report(altered, inputs, declaration, queries)
