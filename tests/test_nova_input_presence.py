import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EDITOR = Path("/Applications/Unity/Hub/Editor/2021.3.45f2/Unity.app/Contents/MonoBleedingEdge")


def controller_presence_source():
    source = (ROOT / "tools/unity/runtime/input/NovaInputBridge.cs").read_text()
    start = source.index("public sealed class ControllerPresence")
    opening = source.index("{", start)
    depth = 0
    for position in range(opening, len(source)):
        if source[position] == "{":
            depth += 1
        elif source[position] == "}":
            depth -= 1
            if depth == 0:
                return source[start : position + 1]
    raise AssertionError("ControllerPresence class does not close")


class NovaInputPresenceTests(unittest.TestCase):
    def test_loading_render_interval_covers_preparation_and_restores_before_play_and_recovery(self):
        source = (ROOT / "tools/unity/runtime/input/NovaInputBoundary.cs").read_text()
        begin = source.index("public IEnumerator NovaInputBoundary(")
        setup = source.index("OnDemandRendering.renderFrameInterval = 3;", begin)
        prepare = source.index("coordinator.PrepareIntegratedWorld(body, cfg)", begin)
        restore = "OnDemandRendering.renderFrameInterval = priorRenderFrameInterval;"
        ready = source.index(restore, prepare)
        playing = source.index("Application.targetFrameRate = 300;", prepare)
        first_input_frame = source.index("yield return new WaitForEndOfFrame();", playing)
        cleanup = source.index("finally", first_input_frame)
        recovery = source.index("if (coordinator.r.sourceStageLifecycleRecoveryRequired)", cleanup)
        self.assertLess(setup, prepare)
        self.assertLess(prepare, ready)
        self.assertLess(ready, playing)
        self.assertLess(playing, first_input_frame)
        self.assertIn(restore, source[cleanup:recovery])

    def test_measured_slot_loss_neutral_reacquisition_and_edge_reset(self):
        mono = EDITOR / "bin/mono"
        csc = EDITOR / "lib/mono/msbuild/Current/bin/Roslyn/csc.exe"
        if not mono.exists() or not csc.exists():
            self.skipTest("matching Unity Mono compiler is unavailable")
        host = (
            """using System;
using System.Linq;
public sealed class NovaInputBridge {
"""
            + controller_presence_source()
            + """
}
public static class Program {
 static void Check(bool passed,string name){if(!passed)throw new Exception(name);}
 public static void Main(){
  var p=new NovaInputBridge.ControllerPresence("Measured Nova");
  var same=new[]{"Measured Nova"};
  Check(!p.Observe(same,true,0f),"initial stable window");
  Check(!p.Observe(same,true,.24f),"premature first attach");
  Check(p.Observe(same,true,.25f)&&p.connected,"first attach");
  Check(p.Observe(same,false,.30f),"held input while connected");
  Check(!p.Observe(Array.Empty<string>(),false,.31f),"disconnect");
  Check(!p.connected&&p.suspensions==1,"one loss transition");
  Check(!p.Observe(new[]{"Other Controller"},true,.60f),"wrong controller rejected");
  Check(!p.Observe(new[]{"Measured Nova","Extra"},true,.80f),"ambiguous slot rejected");
  Check(p.suspensions==1&&p.reconnections==0,"no duplicate loss");
  Check(!p.Observe(same,false,1f),"held button blocks return");
  Check(!p.Observe(same,true,1.10f),"neutral interval starts after release");
  Check(!p.Observe(same,true,1.34f),"premature reconnect");
  Check(p.Observe(same,true,1.35f)&&p.reconnections==1,"same measured controller returns");
  p.Suspend();Check(!p.connected&&p.suspensions==2,"focus or pause neutralizes");
  Check(!p.Observe(same,true,2f),"new stable window");
  Check(!p.Observe(same,false,2.1f),"input resets stable window");
  Check(!p.Observe(same,true,2.2f),"neutral interval restarts");
  Check(p.Observe(same,true,2.45f)&&p.reconnections==2,"second return");
  Console.WriteLine("presence transitions passed");
 }
}
"""
        )
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "PresenceHost.cs"
            output = Path(directory) / "PresenceHost.exe"
            source.write_text(host)
            compiled = subprocess.run(
                [str(mono), str(csc), "-nologo", "-langversion:9", "-out:" + str(output), str(source)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(compiled.returncode, 0, compiled.stdout + compiled.stderr)
            executed = subprocess.run([str(mono), str(output)], capture_output=True, text=True)
            self.assertEqual(executed.returncode, 0, executed.stdout + executed.stderr)
            self.assertIn("presence transitions passed", executed.stdout)


if __name__ == "__main__":
    unittest.main()
