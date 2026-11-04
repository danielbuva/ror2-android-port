"""Synthetic scratch and fake image inventory only; never invoke real hdiutil."""

import importlib.util
import json
import os
from pathlib import Path
import plistlib
import selectors
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

HELPER = Path(__file__).resolve().parents[1] / "scripts/ci-scratch.py"
spec = importlib.util.spec_from_file_location("ci_scratch", HELPER)
cleanup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cleanup)


class ScratchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.path = self.root / "ci-local.fixture"
        self.path.mkdir()
        (self.path / "owner.lock").touch()
        (self.path / "owner.pid").write_text("99999991")
        (self.path / "owner.json").write_text(json.dumps({"pid": 99999991, "pgid": 99999992, "completed": True}))
        os.utime(self.path, (0, 0))

    def reclaim(self, **kwargs):
        with mock.patch.object(cleanup, "alive", return_value=False):
            return cleanup.reclaim(self.path, **kwargs)

    def fake_hdiutil(self, *, mode="success", attached=True):
        image = self.path / "volume.sparseimage"
        image.touch()
        os.utime(self.path, (0, 0))
        self.state = self.root / "state.plist"
        self.log = self.root / "commands.jsonl"
        data = {"images": [{"image-path": str(image), "system-entities": [{"dev-entry": "/dev/disk71"}]}] if attached else []}
        self.state.write_bytes(plistlib.dumps(data))
        binary = self.root / "hdiutil"
        binary.write_text(
            f"#!{sys.executable}\n"
            "import json, os, pathlib, plistlib, sys\n"
            "args=sys.argv[1:]\n"
            "with open(os.environ['FAKE_LOG'], 'a') as f: f.write(json.dumps(args)+'\\n')\n"
            "state=pathlib.Path(os.environ['FAKE_STATE'])\n"
            "mode=os.environ['FAKE_MODE']\n"
            "if args[0]=='info':\n"
            " if mode=='bad-info': print('invalid'); sys.exit(0)\n"
            " sys.stdout.buffer.write(state.read_bytes()); sys.exit(0)\n"
            "if mode=='detach-fail' or (mode=='force' and '-force' not in args): sys.exit(1)\n"
            "state.write_bytes(plistlib.dumps({'images':[]}))\n"
        )
        binary.chmod(0o755)
        self.env = mock.patch.dict(
            os.environ, PATH=str(self.root) + os.pathsep + os.environ["PATH"], FAKE_LOG=str(self.log), FAKE_STATE=str(self.state), FAKE_MODE=mode
        )
        self.env.start()
        self.addCleanup(self.env.stop)

    def test_old_dead_owner_removed(self):
        self.assertEqual(self.reclaim(), "removed")
        self.assertFalse(self.path.exists())

    def test_live_owner_and_group_preserved(self):
        for answers in ([True], [False, True]):
            with mock.patch.object(cleanup, "alive", side_effect=answers):
                self.assertEqual(cleanup.reclaim(self.path), "live")
        self.assertTrue(self.path.exists())

    def test_recent_and_unknown_owner_preserved(self):
        os.utime(self.path, None)
        self.assertEqual(self.reclaim(), "recent")
        os.utime(self.path, (0, 0))
        (self.path / "owner.pid").write_text("malformed")
        self.assertEqual(self.reclaim(), "preserved")
        (self.path / "owner.pid").unlink()
        os.utime(self.path, (0, 0))
        self.assertEqual(self.reclaim(), "preserved")

    def test_pid_permission_error_means_alive(self):
        with mock.patch.object(cleanup.os, "kill", side_effect=PermissionError):
            self.assertTrue(cleanup.alive(99))

    def test_symlinks_are_not_owned(self):
        alias = self.root / "ci-local.alias"
        alias.symlink_to(self.path, target_is_directory=True)
        self.assertEqual(cleanup.reclaim(alias), "unowned")
        (self.path / "owner.pid").unlink()
        (self.path / "owner.pid").symlink_to(self.root / "external")
        os.utime(self.path, (0, 0))
        self.assertEqual(self.reclaim(), "unowned")

    def test_concurrent_cleanup_lock_preserves(self):
        import fcntl

        with (self.path / "owner.lock").open() as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            self.assertEqual(self.reclaim(), "busy")

    def test_exact_image_detached_by_device(self):
        self.fake_hdiutil()
        with mock.patch.object(cleanup.sys, "platform", "darwin"):
            self.assertEqual(self.reclaim(), "removed")
        calls = [json.loads(x) for x in self.log.read_text().splitlines()]
        self.assertIn(["detach", "/dev/disk71"], calls)

    def test_force_fallback(self):
        self.fake_hdiutil(mode="force")
        with mock.patch.object(cleanup.sys, "platform", "darwin"):
            self.assertEqual(self.reclaim(), "removed")
        self.assertIn('["detach", "-force", "/dev/disk71"]', self.log.read_text())

    def test_known_completed_attach_without_saved_device_reconciles(self):
        # No saved device result: only hdiutil's current exact image mapping counts.
        self.fake_hdiutil()
        with mock.patch.object(cleanup.sys, "platform", "darwin"):
            self.assertEqual(self.reclaim(), "removed")

    def test_failed_detach_preserves(self):
        self.fake_hdiutil(mode="detach-fail")
        with mock.patch.object(cleanup.sys, "platform", "darwin"):
            self.assertEqual(self.reclaim(), "preserved")
        self.assertTrue(self.path.exists())

    def test_bad_inventory_preserves(self):
        self.fake_hdiutil(mode="bad-info")
        with mock.patch.object(cleanup.sys, "platform", "darwin"):
            self.assertEqual(self.reclaim(), "preserved")
        self.assertNotIn("detach", self.log.read_text())

    def test_unrelated_image_untouched(self):
        self.fake_hdiutil()
        data = plistlib.loads(self.state.read_bytes())
        data["images"][0]["image-path"] = str(self.root / "unrelated.sparseimage")
        self.state.write_bytes(plistlib.dumps(data))
        with mock.patch.object(cleanup.sys, "platform", "darwin"):
            self.assertEqual(self.reclaim(), "removed")
        self.assertNotIn("detach", self.log.read_text())

    def test_ambiguous_shared_device_preserved(self):
        self.fake_hdiutil()
        data = plistlib.loads(self.state.read_bytes())
        data["images"].append({"image-path": str(self.root / "unrelated.sparseimage"), "system-entities": [{"dev-entry": "/dev/disk71s1"}]})
        self.state.write_bytes(plistlib.dumps(data))
        with mock.patch.object(cleanup.sys, "platform", "darwin"):
            self.assertEqual(self.reclaim(), "preserved")
        self.assertNotIn("detach", self.log.read_text())

    def test_invalid_device_preserved(self):
        self.fake_hdiutil()
        data = plistlib.loads(self.state.read_bytes())
        data["images"][0]["system-entities"][0]["dev-entry"] = "/private/unrelated"
        self.state.write_bytes(plistlib.dumps(data))
        with mock.patch.object(cleanup.sys, "platform", "darwin"):
            self.assertEqual(self.reclaim(), "preserved")
        self.assertNotIn("detach", self.log.read_text())

    def test_foreign_or_renamed_image_mounted_under_scratch_preserved(self):
        self.fake_hdiutil()
        for image_path in (self.root / "foreign.sparseimage", self.path / "renamed.sparseimage"):
            data = {
                "images": [{"image-path": str(image_path), "system-entities": [{"dev-entry": "/dev/disk72", "mount-point": str(self.path / "case-sensitive")}]}]
            }
            self.state.write_bytes(plistlib.dumps(data))
            with mock.patch.object(cleanup.sys, "platform", "darwin"):
                self.assertEqual(self.reclaim(), "preserved")
            self.assertTrue(self.path.exists())
        self.assertNotIn("detach", self.log.read_text())

    def test_non_image_mount_preserved(self):
        self.fake_hdiutil(attached=False)
        with mock.patch.object(cleanup.sys, "platform", "darwin"), mock.patch.object(cleanup.os.path, "ismount", return_value=True):
            self.assertEqual(self.reclaim(), "preserved")
        self.assertTrue(self.path.exists())

    def test_oversized_pid_and_pgid_refuse_without_system_call(self):
        for pid, pgid in ((2**100, 99), (99, 2**100)):
            (self.path / "owner.pid").write_text(str(pid))
            (self.path / "owner.json").write_text(json.dumps({"pid": pid, "pgid": pgid, "completed": True}))
            with mock.patch.object(cleanup, "alive") as check:
                self.assertEqual(cleanup.reclaim(self.path), "unowned")
                check.assert_not_called()
        with mock.patch.object(cleanup.os, "kill", side_effect=OverflowError):
            self.assertTrue(cleanup.alive(2**100))

    def test_delayed_uncertain_attach_preserves_even_with_empty_inventory(self):
        self.fake_hdiutil(attached=False)
        (self.path / "attach.pending").write_text("attachment-completion-unconfirmed\n")
        os.utime(self.path, (0, 0))
        with mock.patch.object(cleanup.sys, "platform", "darwin"):
            self.assertEqual(self.reclaim(), "uncertain-attach")
        self.assertTrue(self.path.exists())
        self.assertFalse(self.log.exists(), "empty inventory cannot prove pending attachment quiescent")
        # The service can publish its delayed mount after the rejected cleanup.
        self.state.write_bytes(
            plistlib.dumps(
                {
                    "images": [
                        {
                            "image-path": str(self.path / "volume.sparseimage"),
                            "system-entities": [{"dev-entry": "/dev/disk71", "mount-point": str(self.path / "case-sensitive")}],
                        }
                    ]
                }
            )
        )
        with mock.patch.object(cleanup.sys, "platform", "darwin"):
            self.assertEqual(self.reclaim(), "uncertain-attach")

    def test_same_device_linux_bind_mount_refuses(self):
        with (
            mock.patch.object(cleanup, "linux_mounts", return_value=[self.path / "bound"]),
            mock.patch.object(cleanup.os.path, "ismount", return_value=False),
            mock.patch.object(cleanup.sys, "platform", "linux"),
        ):
            self.assertEqual(self.reclaim(), "preserved")
        self.assertTrue(self.path.exists())

    def test_mountinfo_decodes_escaped_mount_locations(self):
        with mock.patch("builtins.open", mock.mock_open(read_data="1 2 0:3 / /synthetic/with\\040space rw - tmpfs tmpfs rw\n")):
            self.assertEqual(cleanup.linux_mounts(), [Path("/synthetic/with space")])

    def test_scratch_identity_rechecked_after_inventory(self):
        moved = self.root / "original"

        def replace(_path):
            self.path.rename(moved)
            self.path.mkdir()
            (self.path / "unrelated").write_text("keep")

        with mock.patch.object(cleanup, "require_no_mounts", side_effect=replace):
            self.assertEqual(self.reclaim(), "changed")
        self.assertTrue((self.path / "unrelated").exists())

    def test_timeout_kill_race_still_reaps(self):
        process = mock.Mock(pid=99)
        with mock.patch.object(cleanup.os, "killpg", side_effect=ProcessLookupError):
            cleanup.kill_and_reap(process)
        process.wait.assert_called_once_with()

    def ownership(self, process):
        for scratch in self.root.glob("ci-local.*"):
            try:
                record = json.loads((scratch / "owner.json").read_text())
                pid = int((scratch / "owner.pid").read_text())
                if (
                    isinstance(record, dict)
                    and type(record.get("pid")) is int
                    and record["pid"] == pid == process.pid
                    and type(record.get("pgid")) is int
                    and 1 < record["pgid"] <= 2147483647
                    and record.get("completed") is False
                ):
                    return scratch, record
            except (OSError, ValueError):
                continue
        return None

    def stop_process(self, process):
        owned = self.ownership(process)
        if process.poll() is None:
            process.terminate()
        try:
            process.communicate(timeout=7)
        except subprocess.TimeoutExpired:
            if owned:
                try:
                    os.killpg(owned[1]["pgid"], signal.SIGKILL)
                except ProcessLookupError:
                    pass
            if process.poll() is None:
                process.kill()
            process.communicate(timeout=5)
        # Tests that kill the supervisor may leave its owned shell alive.
        if owned:
            try:
                os.killpg(owned[1]["pgid"], signal.SIGTERM)
            except ProcessLookupError:
                pass

    def start_process(self, command):
        process = subprocess.Popen(command, env=os.environ | {"TMPDIR": str(self.root)}, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.addCleanup(self.stop_process, process)
        return process

    def ready(self, process, timeout=10):
        # Child stdout does not order the supervisor's owner.json write. Require
        # both child readiness and a complete record bound to this exact Popen.
        deadline = time.monotonic() + timeout
        output = b""
        with selectors.DefaultSelector() as selector:
            selector.register(process.stdout, selectors.EVENT_READ)
            while time.monotonic() < deadline:
                owned = self.ownership(process)
                if b"ready\n" in output and owned:
                    return owned
                if process.poll() is not None:
                    self.fail("fixture exited before valid ownership readiness")
                for key, _events in selector.select(min(0.02, max(0, deadline - time.monotonic()))):
                    output += os.read(key.fd, 1024)
                    if len(output) > 4096:
                        self.fail("fixture readiness output exceeded bound")
        self.fail("fixture ownership readiness timed out")

    def stop_detached(self, pidfile):
        try:
            pid = int(pidfile.read_text())
            pidfile.unlink()
            if pid > 1:
                os.kill(pid, signal.SIGTERM)
        except (OSError, ValueError):
            pass

    def launch(self, body):
        script = self.root / "fixture.sh"
        script.write_text(body)
        return self.start_process([sys.executable, str(HELPER), str(script)])

    def test_readiness_waits_for_missing_then_partial_owner_record(self):
        os.utime(self.path, None)
        script = self.root / "fixture.sh"
        script.write_text("echo ready; exec sleep 30\n")
        launcher = (
            "import pathlib,runpy,sys,time\n"
            "original=pathlib.Path.write_text\n"
            "def delayed(path,data,*args,**kwargs):\n"
            " if path.name=='owner.json':\n"
            "  time.sleep(0.1)\n"
            "  original(path,'{')\n"
            "  time.sleep(0.1)\n"
            " return original(path,data,*args,**kwargs)\n"
            "pathlib.Path.write_text=delayed\n"
            "sys.argv=sys.argv[1:]\n"
            "runpy.run_path(sys.argv[0],run_name='__main__')\n"
        )
        process = self.start_process([sys.executable, "-c", launcher, str(HELPER), str(script)])
        scratch, record = self.ready(process)
        self.assertEqual(record["pid"], process.pid)
        self.assertEqual(record, json.loads((scratch / "owner.json").read_text()))
        process.terminate()
        process.communicate(timeout=10)

    def test_readiness_failure_stops_spawned_fixture(self):
        os.utime(self.path, None)
        process = self.launch("echo ready; exec sleep 30\n")
        self.ready(process)
        with mock.patch.object(self, "ownership", return_value=None):
            with self.assertRaisesRegex(AssertionError, "readiness timed out"):
                self.ready(process, timeout=0.05)
        self.stop_process(process)
        self.assertIsNotNone(process.poll())

    def test_normal_and_failure_exit_clean_synchronously(self):
        # Existing fixture belongs to a fake dead PID; leave it recent so the
        # real startup sweep does not rely on assumptions about host PID ranges.
        os.utime(self.path, None)
        for status in (0, 19):
            process = self.launch(f"exit {status}\n")
            out, err = process.communicate(timeout=10)
            self.assertEqual(process.returncode, status, out + err)
            self.assertEqual(list(self.root.glob("ci-local.*")), [self.path])
            self.assertIn(b"cleanup: removed", err)

    def test_shell_signal_style_exit_preserves_uncertainty(self):
        os.utime(self.path, None)
        process = self.launch("exit 143\n")
        _, err = process.communicate(timeout=10)
        self.assertEqual(process.returncode, 143)
        self.assertIn(b"uncertain-descendants", err)

    def test_signals_preserve_uncertain_descendants(self):
        os.utime(self.path, None)
        for sig in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
            process = self.launch("echo ready; exec sleep 30\n")
            self.ready(process)
            process.send_signal(sig)
            _, err = process.communicate(timeout=10)
            self.assertEqual(process.returncode, 128 + sig, err)
            self.assertIn(b"uncertain-descendants", err)

    def test_killed_child_is_reaped_but_preserved(self):
        os.utime(self.path, None)
        process = self.launch("echo ready; exec sleep 30\n")
        scratch, record = self.ready(process)
        os.killpg(record["pgid"], signal.SIGKILL)
        _, err = process.communicate(timeout=10)
        self.assertEqual(process.returncode, 137, err)
        self.assertTrue(scratch.exists())
        self.assertIn(b"uncertain-descendants", err)

    def test_macos_supervisor_detaches_after_normal_and_terminated_runs(self):
        self.fake_hdiutil()
        os.utime(self.path, None)
        script = self.root / "mac-fixture.sh"
        setup = (
            f"{sys.executable} - <<'FIXTURE'\n"
            "import os, pathlib, plistlib\n"
            "scratch=pathlib.Path(os.environ['CI_LOCAL_OWNED_SCRATCH'])\n"
            "image=scratch/'volume.sparseimage'; image.touch()\n"
            "pathlib.Path(os.environ['FAKE_STATE']).write_bytes(plistlib.dumps({'images':[{'image-path':str(image),'system-entities':[{'dev-entry':'/dev/disk71'}]}]}))\n"
            "FIXTURE\n"
        )
        for terminate in (False, True):
            script.write_text(setup + ("echo ready; exec sleep 30\n" if terminate else "exit 19\n"))
            command = [
                sys.executable,
                "-c",
                "import runpy,sys;sys.platform='darwin';sys.argv=sys.argv[1:];runpy.run_path(sys.argv[0],run_name='__main__')",
                str(HELPER),
                str(script),
            ]
            process = self.start_process(command)
            if terminate:
                self.ready(process)
                process.terminate()
            _, err = process.communicate(timeout=10)
            self.assertEqual(process.returncode, 143 if terminate else 19, err)
            if terminate:
                self.assertIn(b"uncertain-descendants", err)
            else:
                self.assertEqual(list(self.root.glob("ci-local.*")), [self.path])
                self.assertIn(b"cleanup: removed", err)
        self.assertEqual(sum(json.loads(line)[0] == "detach" for line in self.log.read_text().splitlines()), 1)

    def test_shell_term_trap_cannot_certify_detached_grandchild(self):
        os.utime(self.path, None)
        pidfile = self.root / "detached.pid"
        self.addCleanup(self.stop_detached, pidfile)
        body = f"trap 'exit 143' TERM\n{sys.executable} - <<'CHILD'\nimport subprocess,pathlib\np=subprocess.Popen(['sleep','30'],start_new_session=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)\npathlib.Path({str(pidfile)!r}).write_text(str(p.pid))\nCHILD\necho ready; while :; do sleep 0.1; done\n"
        process = self.launch(body)
        scratch, record = self.ready(process)
        detached = int(pidfile.read_text())
        try:
            os.kill(record["pgid"], signal.SIGTERM)
            _, err = process.communicate(timeout=10)
            self.assertEqual(process.returncode, 143, err)
            os.kill(detached, 0)
            os.utime(scratch, (0, 0))
            self.assertEqual(cleanup.reclaim(scratch), "uncertain-descendants")
        finally:
            self.stop_detached(pidfile)

    def test_detached_grandchild_keeps_abnormal_scratch_uncertain(self):
        os.utime(self.path, None)
        pidfile = self.root / "detached.pid"
        self.addCleanup(self.stop_detached, pidfile)
        body = f"{sys.executable} - <<'CHILD'\nimport subprocess,pathlib\np=subprocess.Popen(['sleep','30'],start_new_session=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)\npathlib.Path({str(pidfile)!r}).write_text(str(p.pid))\nCHILD\necho ready; exec sleep 30\n"
        process = self.launch(body)
        scratch, record = self.ready(process)
        detached = int(pidfile.read_text())
        try:
            process.kill()
            process.wait(timeout=5)
            os.killpg(record["pgid"], signal.SIGTERM)
            process.communicate(timeout=5)
            os.kill(detached, 0)
            os.utime(scratch, (0, 0))
            self.assertEqual(cleanup.reclaim(scratch), "uncertain-descendants")
            self.assertTrue(scratch.exists())
        finally:
            self.stop_detached(pidfile)

    def test_sigkill_leaves_recorded_live_child_untouched(self):
        os.utime(self.path, None)
        process = self.launch("echo ready; exec sleep 30\n")
        scratch, record = self.ready(process)
        process.kill()
        process.wait(timeout=5)
        os.utime(scratch, (0, 0))
        try:
            self.assertEqual(cleanup.reclaim(scratch), "uncertain-descendants")
        finally:
            os.killpg(record["pgid"], signal.SIGTERM)
            process.communicate(timeout=5)
        # Even when no recorded process remains, abnormal completion cannot
        # certify escaped descendants; age alone never clears the marker.
        with mock.patch.object(cleanup, "alive", return_value=False):
            self.assertEqual(cleanup.reclaim(scratch), "uncertain-descendants")
