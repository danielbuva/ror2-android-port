"""scripts/env.sh keeps Unity from killing the shared adb server."""

import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
ENV_SH = ROOT / "scripts/env.sh"


def _stub(directory: Path, name: str, body: str) -> None:
    path = directory / name
    path.write_text("#!/bin/sh\n" + body)
    path.chmod(0o755)


class UnityAdbPreferenceTests(unittest.TestCase):
    def source(self, system: str, current: str | None) -> list[str]:
        with tempfile.TemporaryDirectory() as tmp:
            bin_dir = Path(tmp)
            log = bin_dir / "defaults.log"
            _stub(bin_dir, "uname", f"echo {system}\n")
            read = f"echo {current}" if current is not None else "exit 1"
            _stub(
                bin_dir,
                "defaults",
                f'echo "$*" >> "{log}"\n[ "$1" = read ] && {{ {read}; exit $?; }}\nexit 0\n',
            )
            env = dict(os.environ, PATH=f"{bin_dir}:/usr/bin:/bin", HOME=tmp)
            subprocess.run(["/bin/sh", "-c", f'. "{ENV_SH}"'], env=env, check=True, timeout=30)
            return log.read_text().splitlines() if log.exists() else []

    def test_unset_preference_is_turned_off(self):
        calls = self.source("Darwin", None)
        self.assertIn("write com.unity3d.UnityEditor5.x AndroidADBKillExternalInstance -int 0", calls)

    def test_enabled_preference_is_turned_off(self):
        calls = self.source("Darwin", "1")
        self.assertIn("write com.unity3d.UnityEditor5.x AndroidADBKillExternalInstance -int 0", calls)

    def test_disabled_preference_is_left_alone(self):
        calls = self.source("Darwin", "0")
        self.assertFalse([c for c in calls if c.startswith("write")])

    def test_other_hosts_never_call_defaults(self):
        self.assertEqual(self.source("Linux", None), [])


if __name__ == "__main__":
    unittest.main()
