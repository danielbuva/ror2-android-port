"""Exercise the composed entry's default application against independent convar peers."""

from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
EDITOR = Path("/Applications/Unity/Hub/Editor/2021.3.45f2/Unity.app/Contents")
MONO = EDITOR / "MonoBleedingEdge/bin/mono"
CSC = EDITOR / "MonoBleedingEdge/lib/mono/msbuild/Current/bin/Roslyn/csc.exe"


class ConsoleRetentionDefaultTests(unittest.TestCase):
    def test_default_lifetime_and_original_configuration_authority(self):
        if not MONO.is_file() or not CSC.is_file():
            self.skipTest("pinned Unity Mono/Roslyn unavailable")
        production = (ROOT / "tools/unity/runtime/session/OfflineApplicationBoundary.cs").read_text()
        method = production.split("        static bool consoleRetentionInitialized;", 1)[1].split("        // Application screen lifetime:", 1)[0]
        harness = (
            """
using System;
namespace RoR2.ConVar {
 public class IntConVar {
  public int value;
  public string defaultValue = "25";
  public int writes;
  public void AttemptSetString(string text) { value = int.Parse(text); writes++; }
 }
}
namespace RoR2 {
 public class Console {
  public static Console instance;
  static ConVar.IntConVar maxMessages = new ConVar.IntConVar();
  public static ConVar.IntConVar Limit { get { return maxMessages; } }
  public static implicit operator bool(Console value) { return value != null; }
 }
}
class Owner {
 static bool consoleRetentionInitialized;
"""
            + method
            + """
 static int Main(string[] args) {
  var limit = RoR2.Console.Limit;
  if(args[0] == "live") RoR2.Console.instance = new RoR2.Console();
  if(args[0] == "configured") limit.value = 73;
  InitializeConsoleRetention();
  if(args[0] == "live" && (limit.value != 0 || limit.writes != 0)) return 1;
  if(args[0] == "configured" && (limit.value != 73 || limit.writes != 0)) return 2;
  if(args[0] == "default") {
   if(limit.value != 25 || limit.writes != 1) return 3;
   // A coordinator handoff must preserve even a later explicit unlimited value.
   limit.value = 0;
   InitializeConsoleRetention();
   if(limit.value != 0 || limit.writes != 1) return 4;
  }
  System.Console.WriteLine("PASS " + args[0]); return 0;
 }
}
"""
        )
        with tempfile.TemporaryDirectory(prefix="console-default-") as directory:
            source = Path(directory) / "Host.cs"
            executable = Path(directory) / "Host.exe"
            source.write_text(harness)
            built = subprocess.run([str(MONO), str(CSC), "-nologo", f"-out:{executable}", str(source)], capture_output=True, text=True, timeout=60)
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            for scenario in ("default", "live", "configured"):
                with self.subTest(scenario=scenario):
                    result = subprocess.run([str(MONO), str(executable), scenario], capture_output=True, text=True, timeout=20)
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                    self.assertIn("PASS " + scenario, result.stdout)
