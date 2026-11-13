"""The SDK process must exit even when Android leaves observer threads alive."""

import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from test_portable_diagnostic_input import extract_method

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts/lab"))
DEFAULT_JDK = Path("/Applications/Unity/Hub/Editor/2021.3.45f2/PlaybackEngines/AndroidPlayer/OpenJDK")


class PendingObserverLifetimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        jdk = Path(os.environ.get("JAVA_HOME", DEFAULT_JDK))
        cls.java, javac = jdk / "bin/java", jdk / "bin/javac"
        if not cls.java.is_file() or not javac.is_file():
            raise unittest.SkipTest("host JDK unavailable")
        cls.temporary = tempfile.TemporaryDirectory(prefix="pending-observer-lifetime-")
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.directory = Path(cls.temporary.name)
        source = (ROOT / "tools/android-write-interruption/LabPendingWriteStop.java").read_text()
        methods = (
            extract_method(source, "    static String observerNonce(")
            + extract_method(source, "    static void enforceDeadline(")
            + extract_method(source, "    public static void main(")
        )
        fixture = """import java.io.File;
public final class LabPendingWriteStop {
METHODS
    private static void run(String[] args) throws Exception {
        Thread observer = new Thread(() -> {
            try { Thread.sleep(60000); } catch (InterruptedException ignored) { }
        });
        observer.setDaemon(false);
        observer.start();
        if (args[0].equals("fail")) throw new Exception("authored observer failure");
        System.out.println("authored observer complete");
    }
}
class NonceFixture {
    public static void main(String[] args) {
        System.out.print(LabPendingWriteStop.observerNonce(new File(args[0])));
    }
}
class DeadlineFixture {
    public static void main(String[] args) throws Exception {
        LabPendingWriteStop.enforceDeadline(100);
        Thread.sleep(60000);
    }
}
""".replace("METHODS", methods)
        path = cls.directory / "LabPendingWriteStop.java"
        path.write_text(fixture)
        result = subprocess.run([str(javac), "-d", str(cls.directory), str(path)], capture_output=True, text=True, timeout=30)
        if result.returncode:
            raise AssertionError(result.stdout + result.stderr)

    def run_fixture(self, name, *args):
        return subprocess.run([str(self.java), "-cp", str(self.directory), name, *args], capture_output=True, text=True, timeout=5)

    def test_success_exits_despite_non_daemon_observer_thread(self):
        result = self.run_fixture("LabPendingWriteStop", "success")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("authored observer complete", result.stdout)

    def test_failure_exits_despite_non_daemon_observer_thread(self):
        result = self.run_fixture("LabPendingWriteStop", "fail")
        self.assertEqual(result.returncode, 1)
        self.assertIn("authored observer failure", result.stderr)

    def test_deadline_terminates_only_its_own_blocked_sdk_process(self):
        result = self.run_fixture("DeadlineFixture")
        self.assertEqual(result.returncode, 124)
        self.assertIn("observer exceeded its deadline", result.stderr)

    def test_ready_filename_nonce_satisfies_host_binding(self):
        import settings_write_interrupt_check as check

        nonce = "0123456789abcdef" * 2
        result = self.run_fixture("NonceFixture", "/runtime/ror2lab-write-" + nonce + ".ready")
        self.assertEqual(result.returncode, 0, result.stderr)
        check.validate_observer_binding(dict(nonce=result.stdout, pid=123, uid=10001, observerPid=124), nonce, "123", 10001)
