"""Execute the production timeout dispatch seam against controlled lifecycle state."""

from pathlib import Path
import os
import subprocess
import tempfile
import unittest

from test_original_audio_camera_context_host import extract_method

ROOT = Path(__file__).resolve().parents[1]
EDITOR = Path(os.environ.get("UNITY_EDITOR_PATH", "/Applications/Unity/Hub/Editor/2021.3.45f2/Unity.app/Contents"))
MONO = EDITOR / "MonoBleedingEdge/bin/mono"
CSC = EDITOR / "MonoBleedingEdge/lib/mono/msbuild/Current/bin/Roslyn/csc.exe"


class PointSoundTimeoutHostTests(unittest.TestCase):
    def test_original_method_dispatch_and_lifecycle_admission(self):
        if not MONO.is_file() or not CSC.is_file():
            self.skipTest("pinned Unity Mono/Roslyn unavailable")
        source = (ROOT / "tools/unity/runtime/session/PortSessionOriginalAudioOwner.cs").read_text()
        method = extract_method(source, "    private static void TickOriginalPointSoundTimeouts()")
        program = (
            r"""using System;
static class GameAudioOriginalOwner {
    public static bool Ready, OptInRequested, NativeApiCallsAvailable, OriginalTermsReturned;
}
namespace RoR2 {
    static class WwiseIntegrationManager { public static bool noAudio; }
    class RoR2Application {
        public static RoR2Application instance;
        public bool isActiveAndEnabled;
        public static implicit operator bool(RoR2Application value) { return value != null; }
    }
}
namespace RoR2.Audio {
    static class PointSoundManager {
        public static int calls;
        private static void ProcessTimeoutQueue() { calls++; }
    }
}
class Program {
    private static Action processOriginalPointSoundTimeouts;
"""
            + method
            + r"""
    static void Check(bool condition) { if (!condition) throw new Exception("dispatch contract failed"); }
    static void Main() {
        TickOriginalPointSoundTimeouts();
        Check(processOriginalPointSoundTimeouts == null);
        GameAudioOriginalOwner.Ready = true;
        GameAudioOriginalOwner.OptInRequested = true;
        GameAudioOriginalOwner.NativeApiCallsAvailable = true;
        TickOriginalPointSoundTimeouts();
        var cached = processOriginalPointSoundTimeouts;
        Check(RoR2.Audio.PointSoundManager.calls == 1 && cached != null);
        RoR2.RoR2Application.instance = new RoR2.RoR2Application { isActiveAndEnabled = true };
        TickOriginalPointSoundTimeouts();
        Check(RoR2.Audio.PointSoundManager.calls == 1);
        RoR2.RoR2Application.instance.isActiveAndEnabled = false;
        TickOriginalPointSoundTimeouts();
        Check(RoR2.Audio.PointSoundManager.calls == 2 && cached == processOriginalPointSoundTimeouts);
        for (int gate = 0; gate < 5; gate++) {
            GameAudioOriginalOwner.Ready = gate != 0;
            GameAudioOriginalOwner.OptInRequested = gate != 1;
            GameAudioOriginalOwner.NativeApiCallsAvailable = gate != 2;
            GameAudioOriginalOwner.OriginalTermsReturned = gate == 3;
            RoR2.WwiseIntegrationManager.noAudio = gate == 4;
            TickOriginalPointSoundTimeouts();
            Check(RoR2.Audio.PointSoundManager.calls == 2);
        }
        Console.WriteLine("PASS original private-method dispatch, delegate reuse, active-app ownership and five audio gates");
    }
}
"""
        )
        self.assertIn("TickOriginalPointSoundTimeouts();", extract_method(source, "    private void Update()"))
        with tempfile.TemporaryDirectory(prefix="point-timeout-host-") as name:
            temp = Path(name)
            fixture = temp / "Program.cs"
            fixture.write_text(program)
            exe = temp / "Program.exe"
            compiled = subprocess.run(
                [str(MONO), str(CSC), "-nologo", "-out:" + str(exe), str(fixture)],
                capture_output=True,
                text=True,
                timeout=60,
            )
            self.assertEqual(compiled.returncode, 0, compiled.stdout + compiled.stderr)
            ran = subprocess.run([str(MONO), str(exe)], capture_output=True, text=True, timeout=30)
            self.assertEqual(ran.returncode, 0, ran.stdout + ran.stderr)
            self.assertIn("PASS", ran.stdout)


if __name__ == "__main__":
    unittest.main()
