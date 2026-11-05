"""Execute the authored static bridge against synthetic backend/activity doubles."""

from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "tools/phone-build/owner-apk/PayloadBootstrapActivity.java"


class BootstrapBridgeTests(unittest.TestCase):
    def test_static_bridge_preserves_commands_review_gates_and_activity(self):
        compiler = shutil.which("javac")
        if compiler is None:
            self.skipTest("Java compiler absent; bridge behavior not host-qualified")
        activity = SOURCE.read_text()
        self.assertIn('new Bridge(this), "OwnerPayload"', activity)
        bridge = activity[activity.index("    private static final class Bridge") : activity.index("    private static byte[] readBounded")]
        harness = r"""
import java.util.*;
import java.lang.ref.WeakReference;
import java.lang.reflect.*;
import java.lang.annotation.*;
public final class PayloadBootstrapActivity {
    @Retention(RetentionPolicy.RUNTIME) @interface JavascriptInterface {}
    static class Handler {
        Runnable pending;
        void post(Runnable task) { pending = task; }
        void drain() { Runnable task = pending; pending = null; task.run(); }
    }
    static final Handler MAIN = new Handler();
    final Backend backend = new Backend();
    Map<String, String> reviewed;
    void reviewUpdate(Map<String, String> observed) { reviewed = observed; }
    static final class Backend {
        String status = "idle";
        boolean reviewPending, unityRequested;
        Map<String, String> drift;
        int pauses, resumes, retries, launches;
        PayloadBootstrapActivity launched;
        String snapshot() { return "synthetic-state"; }
        boolean pause() { pauses++; return true; }
        boolean resume() { resumes++; return false; }
        boolean retry() { retries++; return true; }
        boolean launch(WeakReference<PayloadBootstrapActivity> activity) { launches++; launched = activity.get(); return true; }
    }
BRIDGE
    static void require(boolean value) { if (!value) throw new AssertionError(); }
    public static void main(String[] args) throws Exception {
        require(Modifier.isStatic(Bridge.class.getModifiers()));
        require(!Bridge.class.isAnonymousClass() && Bridge.class.getEnclosingMethod() == null);
        require(Bridge.class.getDeclaredConstructors().length == 1);
        require(Arrays.equals(Bridge.class.getDeclaredConstructors()[0].getParameterTypes(), new Class<?>[] {PayloadBootstrapActivity.class}));
        for (Field field : Bridge.class.getDeclaredFields()) require(!field.isSynthetic());
        require(Bridge.class.getDeclaredMethod("getState").isAnnotationPresent(JavascriptInterface.class));
        require(Bridge.class.getDeclaredMethod("invoke", String.class).isAnnotationPresent(JavascriptInterface.class));
        PayloadBootstrapActivity activity = new PayloadBootstrapActivity();
        Bridge bridge = new Bridge(activity);
        require(bridge.getState().equals("synthetic-state"));
        require(bridge.invoke("pause") && activity.backend.pauses == 1);
        require(!bridge.invoke("resume") && activity.backend.resumes == 1);
        require(!bridge.invoke(null) && !bridge.invoke("unknown"));
        require(!bridge.invoke("retry") && activity.backend.retries == 0);
        activity.backend.status = "error";
        require(bridge.invoke("retry") && activity.backend.retries == 1 && MAIN.pending == null);
        activity.backend.drift = new HashMap<>();
        activity.backend.drift.put("synthetic", "changed");
        activity.backend.unityRequested = true;
        require(!bridge.invoke("retry") && !activity.backend.reviewPending);
        activity.backend.unityRequested = false;
        require(bridge.invoke("retry") && activity.backend.reviewPending && activity.reviewed == null);
        require(!bridge.invoke("retry") && activity.backend.retries == 1);
        MAIN.drain();
        require(activity.reviewed == activity.backend.drift);
        require(bridge.invoke("launch") && activity.backend.launches == 1 && activity.backend.launched == activity);
        System.out.println("static-bridge-contracts-passed");
    }
}
""".replace("BRIDGE", bridge)
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            source = base / SOURCE.name
            source.write_text(harness)
            classes = base / "classes"
            classes.mkdir()
            compiled = subprocess.run([compiler, "-source", "8", "-target", "8", "-d", str(classes), str(source)], capture_output=True, text=True, timeout=60)
            self.assertEqual(compiled.returncode, 0, compiled.stderr)
            self.assertEqual(int.from_bytes((classes / "PayloadBootstrapActivity$Bridge.class").read_bytes()[6:8], "big"), 52)
            result = subprocess.run([str(Path(compiler).with_name("java")), "-cp", str(classes), SOURCE.stem], capture_output=True, text=True, timeout=60)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("static-bridge-contracts-passed", result.stdout)


if __name__ == "__main__":
    unittest.main()
