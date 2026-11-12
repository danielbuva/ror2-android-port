"""Exercise authored project staging/build contracts; no SDK or phone execution."""

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("graphics_preload_build", ROOT / "scripts/build-graphics-preload-fixture.py")
BUILD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BUILD)


class GraphicsPreloadFixtureTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.commit = "a" * 40
        for name in BUILD.SOURCES:
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / name, path)
        self.output = self.root / "work/preload"

    def test_new_project_contains_only_authored_inputs_and_exact_pins(self):
        project, inputs = BUILD.stage(self.root, self.output, self.commit)
        self.assertEqual(inputs["source_commit"], self.commit)
        self.assertFalse(inputs["game_inputs"])
        self.assertFalse(inputs["custom_driver_loaded"])
        self.assertEqual(set(inputs["sources"]), set(BUILD.SOURCES))
        self.assertEqual(
            sorted(p.relative_to(project).as_posix() for p in project.rglob("*") if p.is_file()),
            [
                "Assets/Editor/GraphicsPreloadFixtureBuild.cs",
                "Assets/GraphicsPreloadFixture.cs",
                "Packages/manifest.json",
                "ProjectSettings/ProjectVersion.txt",
            ],
        )
        self.assertIn("2021.3.45f2 (88f88f591b2e)", (project / "ProjectSettings/ProjectVersion.txt").read_text())
        self.assertEqual(json.loads((project / "Packages/manifest.json").read_text()), {"dependencies": {"com.unity.modules.jsonserialize": "1.0.0"}})
        self.assertEqual((project / "Assets/GraphicsPreloadFixture.cs").read_bytes(), (self.root / BUILD.OWNER / "GraphicsPreloadFixture.cs").read_bytes())
        with self.assertRaises(ValueError):
            BUILD.stage(self.root, self.output, self.commit)

    def test_refuses_foreign_or_redirected_output(self):
        with self.assertRaises(ValueError):
            BUILD.stage(self.root, self.root / "not-work", self.commit)
        (self.root / "outside").mkdir()
        (self.root / "work").symlink_to(self.root / "outside", target_is_directory=True)
        with self.assertRaises(ValueError):
            BUILD.stage(self.root, self.output, self.commit)
        self.assertFalse((self.root / "outside/preload").exists())

    def test_build_commands_use_only_authored_native_and_isolated_project(self):
        project, _ = BUILD.stage(self.root, self.output, self.commit)
        editor = self.root / "Editor/Unity.app/Contents/MacOS/Unity"
        native, player = BUILD.commands(self.root, editor, project)
        self.assertIn("--target=aarch64-linux-android28", native)
        self.assertIn("-Wl,--no-undefined", native)
        self.assertEqual(
            native[-3:],
            [
                str(self.root / BUILD.OWNER / "native/GraphicsDriverPreload.cpp"),
                "-o",
                str(project / "Assets/Plugins/Android/arm64-v8a/libGraphicsDriverPreload.so"),
            ],
        )
        self.assertEqual(player[player.index("-projectPath") + 1], str(project))
        self.assertEqual(player[player.index("-executeMethod") + 1], "GraphicsPreloadFixtureBuild.Build")
        self.assertNotIn("adb", " ".join(native + player))
        self.assertNotIn("adrenotools", " ".join(native + player))

    def test_runner_work_link_uses_only_explicit_canonical_root(self):
        shared = self.root / "shared-work"
        shared.mkdir()
        (self.root / "work").symlink_to(shared, target_is_directory=True)
        project, _ = BUILD.stage(self.root, self.output, self.commit, work=shared)
        self.assertEqual(project, shared / "preload/project")
        outside = self.root / "outside"
        outside.mkdir()
        (shared / "redirected").symlink_to(outside, target_is_directory=True)
        with self.assertRaises(ValueError):
            BUILD.stage(self.root, self.root / "work/redirected/new", self.commit, work=shared)
        self.assertFalse((outside / "new").exists())

    def test_receipt_requires_explicit_preload_and_matching_source(self):
        BUILD.stage(self.root, self.output, self.commit)
        report = dict(success=True, preloaded=True, editor_compatible=False, custom_driver_loaded=False, source_commit=self.commit, failure=None)
        library = self.output / "project/Assets/Plugins/Android/arm64-v8a/libGraphicsDriverPreload.so"
        library.write_bytes(b"authored non-executable fixture")
        apk = self.output / "graphics-preload-fixture.apk"
        with zipfile.ZipFile(apk, "w") as archive:
            archive.writestr("lib/arm64-v8a/libGraphicsDriverPreload.so", library.read_bytes())
        path = self.output / "build-result.json"
        path.write_text(json.dumps(report))
        self.assertEqual(BUILD.validate_result(self.output, self.commit), hashlib.sha256(apk.read_bytes()).hexdigest())
        for key, value in (
            ("success", False),
            ("preloaded", False),
            ("editor_compatible", True),
            ("custom_driver_loaded", True),
            ("source_commit", "b" * 40),
            ("failure", "failed"),
        ):
            with self.subTest(key=key), self.assertRaises(ValueError):
                path.write_text(json.dumps(dict(report, **{key: value})))
                BUILD.validate_result(self.output, self.commit)
        path.write_text(json.dumps(report))
        library.write_bytes(b"changed")
        with self.assertRaises(ValueError):
            BUILD.validate_result(self.output, self.commit)

    def test_owned_child_timeout_is_reaped(self):
        with (self.root / "child.log").open("wb") as log:
            with self.assertRaises(subprocess.TimeoutExpired):
                BUILD.invoke([sys.executable, "-c", "import time; time.sleep(30)"], log, 0.1, dict(os.environ))

    def test_missing_editor_reports_fixed_failure_without_staging(self):
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts/build-graphics-preload-fixture.py"), "--editor", str(self.root / "absent"), "--output", str(self.output)],
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(result.returncode, 1, result.stderr)
        value = json.loads(result.stdout)
        self.assertEqual(value["classification"], "pinned-editor-unavailable")
        self.assertEqual(value["device_actions"], 0)
        self.assertFalse(value["runtime_preload_verified"])
        self.assertNotIn(str(self.root), result.stdout)
        self.assertFalse(self.output.exists())
