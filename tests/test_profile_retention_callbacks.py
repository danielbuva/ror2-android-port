"""Run the actual retention lifecycle callback with synthetic Android types."""

from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "tools/phone-build/owner-apk/ProfileRetentionProvider.java"


class ProfileRetentionCallbackTests(unittest.TestCase):
    def test_named_static_callback_preserves_unity_latch(self):
        compiler = shutil.which("javac")
        if compiler is None:
            self.skipTest("Java compiler absent; retention callback not host-qualified")
        source = SOURCE.read_text()
        self.assertIn("registerActivityLifecycleCallbacks(new UnityLifecycleCallbacks())", source)
        self.assertNotIn("new Application.ActivityLifecycleCallbacks() {", source)
        declaration = source[source.index("    private static final class UnityLifecycleCallbacks") : source.index("    private static ProfileStore openStore")]
        harness = r"""
import android.app.Activity;
import android.app.Application;
import android.os.Bundle;
import java.lang.reflect.Modifier;
public final class ProfileRetentionProvider {
    static final Object LOCK = new Object();
    private static boolean unityStarted;
CALLBACK
    static void require(boolean ok) { if (!ok) throw new AssertionError(); }
    public static void main(String[] args) throws Exception {
        Class<?> type = UnityLifecycleCallbacks.class;
        require(Modifier.isStatic(type.getModifiers()) && !type.isAnonymousClass());
        require(type.getEnclosingMethod() == null && type.getDeclaredFields().length == 0);
        require(type.getDeclaredConstructors()[0].getParameterCount() == 0);
        UnityLifecycleCallbacks callback = new UnityLifecycleCallbacks();
        Activity ordinary = new Activity();
        Activity unity = new com.unity3d.player.UnityActivity();
        callback.onActivityCreated(ordinary, null);
        require(!unityStarted);
        callback.onActivityStarted(unity);
        callback.onActivityResumed(unity);
        callback.onActivityPaused(unity);
        callback.onActivityStopped(unity);
        callback.onActivitySaveInstanceState(unity, null);
        callback.onActivityDestroyed(unity);
        require(!unityStarted);
        callback.onActivityCreated(unity, null);
        require(unityStarted);
        callback.onActivityDestroyed(unity);
        callback.onActivityCreated(ordinary, null);
        require(unityStarted); // Only process restart clears the conservative latch.
        System.out.println("retention-callback-contract-passed");
    }
}
""".replace("CALLBACK", declaration)
        files = {
            "ProfileRetentionProvider.java": harness,
            "android/app/Activity.java": "package android.app; public class Activity {}",
            "android/os/Bundle.java": "package android.os; public class Bundle {}",
            "com/unity3d/player/UnityActivity.java": "package com.unity3d.player; public class UnityActivity extends android.app.Activity {}",
            "android/app/Application.java": """package android.app;
import android.os.Bundle;
public class Application {
    public interface ActivityLifecycleCallbacks {
        void onActivityCreated(Activity activity, Bundle state);
        void onActivityStarted(Activity activity);
        void onActivityResumed(Activity activity);
        void onActivityPaused(Activity activity);
        void onActivityStopped(Activity activity);
        void onActivitySaveInstanceState(Activity activity, Bundle state);
        void onActivityDestroyed(Activity activity);
    }
}""",
        }
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            for name, body in files.items():
                path = base / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(body)
            classes = base / "classes"
            compiled = subprocess.run(
                [compiler, "-source", "8", "-target", "8", "-d", str(classes), *[str(base / name) for name in files]],
                capture_output=True,
                text=True,
                timeout=60,
            )
            self.assertEqual(compiled.returncode, 0, compiled.stderr)
            for path in classes.rglob("*.class"):
                self.assertEqual(int.from_bytes(path.read_bytes()[6:8], "big"), 52)
                self.assertNotRegex(path.name, r"\$[0-9]+\.class$")
            result = subprocess.run([str(Path(compiler).with_name("java")), "-cp", str(classes), SOURCE.stem], capture_output=True, text=True, timeout=60)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("retention-callback-contract-passed", result.stdout)
