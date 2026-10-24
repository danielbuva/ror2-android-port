"""Real-Git lane ownership and dispatch contracts without Unity or APFS."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from contextlib import nullcontext
from unittest.mock import patch
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts/lab"))
import build_lanes as lanes
from build_lock import host_build_lock


class BuildLaneTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve() / "repo"
        self.root.mkdir()
        self.git("init", "-q")
        self.git("config", "user.name", "Authored Fixture")
        self.git("config", "user.email", "fixture.invalid")
        (self.root / ".gitignore").write_text("/work/\n/.local/\n")
        (self.root / "dev").write_text("#!/bin/sh\nexit 0\n")
        bootstrap = self.root / "android/Assets/Editor/BootstrapMcp.cs"
        bootstrap.parent.mkdir(parents=True)
        bootstrap.write_text("// authored editor bootstrap fixture\n")
        self.git("add", ".")
        self.git("commit", "-qm", "fixture")
        self.work = self.root / "work"
        for folder in ("lab-project/Library", "lab-project/Temp", "config", "generated-android-data", "device"):
            (self.work / folder).mkdir(parents=True)
        (self.work / "lab-project/Library/cache").write_text("authored cache")
        (self.work / "lab-project/Temp/UnityLockfile").write_text("live canonical editor")
        (self.work / "config/local.json").write_text("{}")
        audio = self.work / "config/original-game-audio"
        audio.mkdir()
        (audio / "selection.json").write_text(json.dumps({"inputs": {"native_library": "coordination/audio-provider/library"}}))
        (self.work / "coordination/audio-provider").mkdir(parents=True)
        (self.work / "coordination/audio-provider/library").write_text("authored provider")
        (self.work / "config/iteration-base.json").write_text("{}")
        (self.work / "device/installed.json").write_text("{}")
        (self.work / "generated-android-data/payload").write_text("authored content")
        (self.work / "internal-link").symlink_to(self.work / "generated-android-data/payload")
        (self.root / ".local/tools").mkdir(parents=True)
        (self.root / ".local/lab-venv").mkdir()
        self.patches = [
            patch.object(lanes.sys, "platform", "darwin"),
            patch.object(lanes, "check_space", return_value=200 * 1024**3),
            patch.object(lanes, "clone", side_effect=self.clone),
            patch.object(lanes, "restage"),
        ]
        for p in self.patches:
            p.start()
            self.addCleanup(p.stop)

    def git(self, *arguments):
        return lanes.git(self.root, *arguments)

    def clone(self, sources, destination):
        destination.mkdir(parents=True, exist_ok=True)
        for source in sources:
            target = destination / source.name
            if source.is_symlink():
                target.symlink_to(os.readlink(source))
            elif source.is_dir():
                shutil.copytree(source, target, symlinks=True)
            else:
                shutil.copy2(source, target)

    def create(self, name="second"):
        return lanes.create(name, port=9081, root=self.root)

    def test_clone_retains_library_but_not_live_editor_or_device_state(self):
        facts = self.create()
        lanes.restage.assert_called_once_with(facts)
        self.assertEqual(facts["canonical_source_commit"], self.git("rev-parse", "HEAD"))
        work = Path(facts["checkout"]) / "work"
        self.assertEqual((work / "lab-project/Library/cache").read_text(), "authored cache")
        self.assertFalse((work / "lab-project/Temp").exists())
        self.assertFalse((work / "device").exists())
        self.assertEqual((work / "coordination/audio-provider/library").read_text(), "authored provider")
        self.assertFalse((work / "coordination/unity-build.lock").exists())
        self.assertFalse((work / "config/iteration-base.json").exists())
        self.assertEqual((work / "internal-link").resolve(), work / "generated-android-data/payload")
        (work / "generated-android-data/payload").write_text("independent")
        self.assertEqual((self.work / "generated-android-data/payload").read_text(), "authored content")
        self.assertNotEqual(Path(facts["lock"]), self.work / "coordination/unity-build.lock")
        self.assertEqual(lanes.git(Path(facts["checkout"]), "rev-parse", "HEAD"), facts["seed_commit"])

    def test_dispatch_passes_only_its_lock_while_canonical_is_held(self):
        facts = self.create()
        lanes.restage.reset_mock()
        original_run = subprocess.run
        calls = []

        def invoke(args, **kwargs):
            if str(args[0]) == str(Path(facts["checkout"]) / "dev"):
                lanes.restage.assert_called_once_with(facts)
                self.assertEqual(lanes.git(Path(facts["checkout"]), "rev-parse", "HEAD"), self.git("rev-parse", "HEAD"))
                calls.append((args, kwargs))
                (fd,) = kwargs["pass_fds"]
                self.assertEqual(os.fstat(fd).st_ino, Path(facts["lock"]).stat().st_ino)
                self.assertNotIn("LAB_LANE", kwargs["env"])
                return subprocess.CompletedProcess(args, 0)
            return original_run(args, **kwargs)

        with host_build_lock(self.work / "coordination/unity-build.lock", operation="canonical busy"):
            with (
                patch.object(lanes, "start_server"),
                patch.object(lanes, "publish", return_value={"apk": "published", "payload_directory": "payload"}),
                patch.object(subprocess, "run", side_effect=invoke),
            ):
                self.assertEqual(lanes.dispatch("second", ["prototype", "--action", "whole-catalog-code-build"], root=self.root), 0)
        self.assertEqual(len(calls), 1)

    def test_device_dispatch_refuses_and_teardown_preserves_canonical_and_lock(self):
        facts = self.create()
        server_log = lanes.location("second", self.root) / "mcp-server.log"
        server_log.write_text("authored server evidence")
        retirement = Path(facts["checkout"]) / "work/coordination/staging-retirements/fixture.json"
        retirement.parent.mkdir(parents=True, exist_ok=True)
        retirement.write_text("{}\n")
        for arguments in (["install"], ["preflight"], ["prototype", "--action", "whole-catalog-run"], ["prototype", "--action"]):
            with self.subTest(arguments=arguments), self.assertRaises(RuntimeError):
                lanes.dispatch("second", arguments, root=self.root)
        result = lanes.remove("second", root=self.root)
        self.assertTrue(result["removed"])
        self.assertFalse(lanes.location("second", self.root).exists())
        self.assertTrue(Path(facts["lock"]).exists())
        self.assertEqual((self.work / "lab-project/Temp/UnityLockfile").read_text(), "live canonical editor")
        self.assertEqual(json.loads(Path(result["evidence"]).read_text())["seed_commit"], facts["seed_commit"])
        self.assertEqual((Path(result["evidence"]).parent / "mcp-server.log").read_text(), "authored server evidence")
        self.assertEqual((Path(result["evidence"]).parent / "coordination/staging-retirements/fixture.json").read_text(), "{}\n")
        self.assertNotIn(facts["checkout"], self.git("worktree", "list"))

    def test_names_ports_and_existing_lane_refuse_without_overwriting(self):
        for name in ("../other", "canonical", "", "with space"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                lanes.location(name, self.root)
        with self.assertRaises(ValueError):
            lanes.create("second", port=8080, root=self.root)
        self.create()
        with self.assertRaises(RuntimeError):
            self.create()
        with self.assertRaisesRegex(ValueError, "port is already reserved"):
            self.create("duplicate-port")
        self.assertFalse(lanes.read_lane("duplicate-port", self.root)["complete"])
        lanes.remove("duplicate-port", self.root)

    def test_teardown_recovers_an_unregistered_partial_tree_without_primary_git_operations(self):
        facts = self.create()
        checkout = Path(facts["checkout"])
        original = self.git("rev-parse", "HEAD")
        self.git("worktree", "remove", "--force", str(checkout))
        checkout.mkdir()
        (checkout / "residual-registry").write_text("authored daemon residue")
        lanes.remove("second", self.root)
        self.assertFalse(checkout.exists())
        self.assertEqual(self.git("rev-parse", "HEAD"), original)
        self.assertTrue((self.work / "lab-project/Temp/UnityLockfile").is_file())

    def test_optional_pinned_gradle_daemon_stops_before_lane_deletion(self):
        android = Path("/Applications/Unity/Hub/Editor") / lanes.toolchain()["unity_version"] / "PlaybackEngines/AndroidPlayer"
        launchers = list((android / "Tools/gradle/lib").glob("gradle-launcher-*.jar"))
        java = android / "OpenJDK/bin/java"
        if not java.is_file() or len(launchers) != 1:
            self.skipTest("optional pinned Gradle/OpenJDK is unavailable")
        facts = self.create()
        checkout = Path(facts["checkout"])
        home = checkout / ".local/gradle"
        project = checkout / "work/gradle-fixture"
        project.mkdir()
        (project / "build.gradle").write_text("// authored empty Gradle lifecycle fixture\n")
        command = [str(java), "-classpath", str(launchers[0]), "org.gradle.launcher.GradleMain", "--gradle-user-home", str(home)]
        try:
            subprocess.run(command + ["-p", str(project), "help", "--daemon"], check=True, capture_output=True, timeout=60)
            (log,) = home.glob("daemon/*/daemon-*.out.log")
            pid = int(log.name.split("-")[1].split(".")[0])
            os.kill(pid, 0)
            lanes.remove("second", self.root)
            self.assertFalse(checkout.exists())
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                try:
                    os.kill(pid, 0)
                except ProcessLookupError:
                    break
                time.sleep(0.1)
            else:
                self.fail("private Gradle daemon survived owned teardown")
        finally:
            if home.exists():
                subprocess.run(command + ["--stop"], capture_output=True, timeout=60)

    def test_published_artifact_survives_lane_teardown_without_changing_current_pointer(self):
        facts = self.create()
        work = Path(facts["checkout"]) / "work"
        cache = work / "build-cache/authored"
        (cache / "payload").mkdir(parents=True)
        (cache / "authored.apk").write_bytes(b"authored package")
        (cache / "payload/data").write_bytes(b"authored payload")
        result = dict(
            success=True,
            apk=str(cache / "authored.apk"),
            apk_sha256=lanes.sha(cache / "authored.apk"),
            payload_directory=str(cache / "payload"),
            request_id="authored",
            payload={"data": lanes.sha(cache / "payload/data")},
        )
        (work / "config/current-build.json").write_text(json.dumps(result))
        published = lanes.publish(facts)
        lanes.remove("second", self.root)
        self.assertEqual(Path(published["apk"]).read_bytes(), b"authored package")
        self.assertEqual((Path(published["payload_directory"]) / "data").read_bytes(), b"authored payload")
        self.assertFalse((self.work / "config/current-build.json").exists())

    def test_server_environment_does_not_import_the_lab_main_module(self):
        facts = self.create()
        process = Mock(pid=987654321)
        process.poll.return_value = None
        with patch.dict(os.environ, {"LAB_LANE": "second", "PYTHONPATH": "authored-lab-modules"}):
            with patch.object(subprocess, "Popen", return_value=process) as launch, patch.object(lanes.urllib.request, "urlopen", return_value=nullcontext()):
                lanes.start_server(facts)
        self.assertNotIn("PYTHONPATH", launch.call_args.kwargs["env"])
        self.assertNotIn("LAB_LANE", launch.call_args.kwargs["env"])


if __name__ == "__main__":
    unittest.main()
