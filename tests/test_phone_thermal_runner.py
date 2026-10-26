"""Synthetic sensors and process trees exercise the shared on-device supervisor."""

import errno
import importlib.util
import json
from pathlib import Path
import signal
import tempfile
import unittest
from unittest.mock import Mock, patch

SPEC = importlib.util.spec_from_file_location("phone_thermal_runner", Path(__file__).resolve().parents[1] / "tools/phone-build/accepted-output/phone_runner.py")
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)


def zones(cpu=45, gpu=45, battery=35):
    return {"cpu0": ("cpu", cpu), "gpu0": ("gpu", gpu), "battery": ("battery", battery)}


class DutyCycleTests(unittest.TestCase):
    def test_nova_and_thor_hysteresis_and_pause_accounting(self):
        for profile, high, low in (("nova", 70, 55), ("thor", 75, 60)):
            policy = runner.ThermalDutyCycle(profile)
            policy.observe(zones(), 0, admission=True)
            self.assertEqual(policy.observe(zones(gpu=high), 0.25), signal.SIGSTOP)
            self.assertIsNone(policy.observe(zones(cpu=low + 0.1), 0.5))
            self.assertEqual(policy.observe(zones(cpu=low), 0.75), signal.SIGCONT)
            self.assertEqual(policy.receipt(1)["pause_seconds"], 0.5)
            self.assertEqual(policy.pauses, 1)

    def test_last_resort_safety_during_pause(self):
        policy = runner.ThermalDutyCycle()
        for tick in range(13):
            policy.observe(zones(cpu=85), tick * 0.25)
        self.assertEqual(policy.receipt(3)["time_above_80_seconds"], 3)
        self.assertEqual(policy.receipt(3)["peak_cpu_gpu_celsius"], 85)
        for tick in range(12):
            policy.observe(zones(cpu=96), 3.25 + tick * 0.25)
        with self.assertRaisesRegex(RuntimeError, "95 C for 3 s"):
            policy.observe(zones(cpu=96), 6.25)
        runner.ThermalDutyCycle().observe(zones(cpu=95, battery=46), 0)
        for values, message in ((zones(battery=46.1), "46 C"), ({}, "unavailable")):
            with self.subTest(values=values), self.assertRaisesRegex(RuntimeError, message):
                runner.ThermalDutyCycle().observe(values, 0)
        policy = runner.ThermalDutyCycle()
        policy.observe(zones(), 0)
        with self.assertRaisesRegex(RuntimeError, "sample gap"):
            policy.observe(zones(), 1.01)
        with self.assertRaisesRegex(RuntimeError, "admission"):
            runner.ThermalDutyCycle().observe(zones(gpu=50.1), 0, admission=True)

    def test_fake_sensor_supervises_command_and_records_pauses(self):
        with tempfile.TemporaryDirectory() as temporary:
            receipt = Path(temporary) / "receipt.json"
            child = Mock(returncode=None)
            child.poll.side_effect = [None, None, 0]
            family = Mock()
            tick = [0.0]

            def wait(seconds):
                tick[0] += seconds

            def sample():
                return zones(cpu=45 if tick[0] == 0 else 70 if tick[0] == 0.25 else 55)

            with (
                patch.object(runner, "efficiency_cpus", return_value={0, 1}),
                patch.object(runner.subprocess, "Popen", return_value=child) as spawn,
                patch.object(runner, "Family", return_value=family),
            ):
                result = runner.run(["producer"], receipt, sensor=sample, clock=lambda: tick[0], wait=wait)
            self.assertTrue(result["success"])
            self.assertEqual(result["pause_seconds"], 0.25)
            self.assertEqual([row.args[0] for row in family.send.call_args_list], [signal.SIGSTOP, signal.SIGCONT, signal.SIGKILL])
            self.assertEqual(spawn.call_args.kwargs["env"]["OMP_NUM_THREADS"], "2")
            self.assertEqual(spawn.call_args.args[0], ["/system/bin/taskset", "3", "producer"])
            self.assertEqual(json.loads(receipt.read_text()), result)
            self.assertEqual(json.loads(Path(str(receipt) + ".pause.json").read_text()), {"paused_seconds": 0.25, "paused_at": None})
            self.assertEqual(spawn.call_args.kwargs["env"]["ROR2LAB_BUILD_PAUSE_CLOCK"], str(Path(str(receipt) + ".pause.json").resolve()))

    def test_cancelled_paused_work_is_killed_without_resume(self):
        with tempfile.TemporaryDirectory() as temporary:
            child, family = Mock(returncode=None), Mock()
            child.poll.return_value = None
            tick = [0.0]

            def wait(seconds):
                tick[0] += seconds

            with (
                patch.object(runner, "efficiency_cpus", return_value={0}),
                patch.object(runner.subprocess, "Popen", return_value=child),
                patch.object(runner, "Family", return_value=family),
            ):
                result = runner.run(
                    ["producer"],
                    Path(temporary) / "receipt.json",
                    sensor=lambda: zones(cpu=45 if tick[0] == 0 else 70),
                    clock=lambda: tick[0],
                    wait=wait,
                    cancelled=lambda: tick[0] >= 0.5,
                )
            self.assertFalse(result["success"])
            self.assertEqual(result["pause_seconds"], 0.25)
            self.assertEqual([row.args[0] for row in family.send.call_args_list], [signal.SIGSTOP, signal.SIGKILL])

    def test_escaped_child_and_reused_pid(self):
        child = Mock(pid=100, returncode=None)
        live = {100: (1, 10), 101: (100, 11), 102: (101, 12), 200: (1, 99)}
        with (
            patch.object(runner, "identity", side_effect=lambda pid: live.get(pid)),
            patch.object(runner.Path, "iterdir", return_value=[Path(f"/proc/{pid}") for pid in live]),
            patch.object(runner.os, "killpg") as group,
            patch.object(runner.os, "kill") as kill,
        ):
            family = runner.Family(child)
            family.send(signal.SIGSTOP)
            group.assert_called_once_with(100, signal.SIGSTOP)
            self.assertEqual({row.args[0] for row in kill.call_args_list}, {100, 101, 102})
            live[102] = (1, 120)  # PID reused by unrelated process.
            kill.reset_mock()
            family.send(signal.SIGKILL)
            self.assertNotIn(102, {row.args[0] for row in kill.call_args_list})

    def test_einval_zone_is_excluded_but_other_io_errors_refuse(self):
        original = Path.read_text
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for index in range(2):
                node = root / f"thermal_zone{index}"
                node.mkdir()
                (node / "type").write_text("cpu" + str(index))
                (node / "temp").write_text("45000")

            def read(path, *args, **kwargs):
                if path == root / "thermal_zone1/temp":
                    raise OSError(errno.EINVAL, "unavailable interface")
                return original(path, *args, **kwargs)

            with patch.object(Path, "read_text", read):
                self.assertEqual(runner.read_zones(root), {"thermal_zone0": ("cpu", 45)})

    def test_sysfs_sensor_excludes_pmic_and_sentinels(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for index, (kind, value) in enumerate((("cpu0", 45000), ("gpu", 46000), ("pmic", 120000), ("cpu1", -300000))):
                node = root / f"thermal_zone{index}"
                node.mkdir()
                (node / "type").write_text(kind)
                (node / "temp").write_text(str(value))
            self.assertEqual(runner.read_zones(root), {"thermal_zone0": ("cpu", 45), "thermal_zone1": ("gpu", 46)})


if __name__ == "__main__":
    unittest.main()
