import subprocess
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
RUNTIME_ROOT = REPO / "tools/unity/runtime"
EDITOR = Path("/Applications/Unity/Hub/Editor/2021.3.45f2/Unity.app/Contents/MonoBleedingEdge")


def extract_class(source, declaration):
    start = source.index(declaration)
    opening = source.index("{", start)
    depth = 0
    for pos in range(opening, len(source)):
        if source[pos] == "{":
            depth += 1
        elif source[pos] == "}":
            depth -= 1
            if depth == 0:
                return source[start : pos + 1]
    raise AssertionError(f"{declaration} does not close")


def extract_method(source, declaration):
    start = source.index(declaration)
    opening = source.index("{", start)
    depth = 0
    for pos in range(opening, len(source)):
        if source[pos] == "{":
            depth += 1
        elif source[pos] == "}":
            depth -= 1
            if depth == 0:
                return source[start : pos + 1]
    raise AssertionError(f"{declaration} does not close")


class PortableInputPolicyTests(unittest.TestCase):
    def test_default_touch_start_ignores_physical_map_and_nova_keeps_its_wait(self):
        mono = EDITOR / "bin/mono"
        compiler = EDITOR / "lib/mono/msbuild/Current/bin/Roslyn/csc.exe"
        if not mono.exists() or not compiler.exists():
            self.skipTest("matching Unity Mono compiler is unavailable")
        owner = (RUNTIME_ROOT / "input/NovaInputBoundary.cs").read_text()
        source = (RUNTIME_ROOT / "session/PortSession.cs").read_text()
        start = source.index("        else\n        {\n            if (!config.launchPlayableSlice)")
        opening = source.index("{", start)
        depth = 1
        end = opening + 1
        while depth:
            depth += (source[end] == "{") - (source[end] == "}")
            end += 1
        block = source[opening + 1 : end - 1]
        host = (
            """using System; using System.IO; using System.Collections;
class Application { public static string persistentDataPath; }
class WaitForSeconds { public WaitForSeconds(float seconds) {} }
class NovaInputBridge { public class Mapping { public string attempt; } }
class JsonUtility { public static int reads; public static T FromJson<T>(string text) { reads++; return (T)(object)new NovaInputBridge.Mapping { attempt=text }; } }
"""
            + extract_class(owner, "public static class InputSessionPolicy")
            + """
class Fixture {
 public class Config { public bool launchPlayableSlice=true; public string attempt="fixture"; }
 public class SessionReport { public string attempt,id; public bool freePlay; }
 public Config config=new Config(); public SessionReport r; public string model;
 string CurrentDeviceModel() { return model; }
"""
            + extract_method(owner, "    bool UsesTouchUi()")
            + "\n public IEnumerator DefaultStart() {"
            + block
            + "\n} }\n"
            + """
class Program {
 static void Need(bool value,string reason) { if(!value)throw new Exception(reason); }
 static void Main(string[] args) {
  Application.persistentDataPath=args[0]; var path=Path.Combine(args[0],"nova-input-mapping.json");
  Directory.CreateDirectory(path);
  var touch=new Fixture { model="AYN Thor" };
  Need(!touch.DefaultStart().MoveNext() && touch.r.freePlay && JsonUtility.reads==0,"touch read or waited for a physical map");
  Directory.Delete(path);
  var nova=new Fixture { model="Retroid Pocket Nova" }; var wait=nova.DefaultStart();
  Need(wait.MoveNext() && nova.r==null,"Nova proceeded without mapping");
  File.WriteAllText(path,"stale"); Need(wait.MoveNext() && nova.r==null,"Nova accepted stale mapping");
  File.WriteAllText(path,"fixture"); Need(!wait.MoveNext() && nova.r.freePlay,"Nova could not proceed with accepted mapping");
  var disabled=new Fixture { model="AYN Thor" }; disabled.config.launchPlayableSlice=false;
  Need(!disabled.DefaultStart().MoveNext() && disabled.r==null,"touch enabled a default-off player");
  File.Delete(path); var unknown=new Fixture { model="unknown" };
  Need(unknown.DefaultStart().MoveNext() && unknown.r==null,"unknown hardware inferred touch qualification");
  Console.WriteLine("default startup boundary passed");
 }
}
"""
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "Startup.cs"
            path.write_text(host)
            output = Path(directory) / "startup.exe"
            compiled = subprocess.run([str(mono), str(compiler), "-nologo", "-langversion:9", "-out:" + str(output), str(path)], capture_output=True, text=True)
            self.assertEqual(compiled.returncode, 0, compiled.stdout + compiled.stderr)
            result = subprocess.run([str(mono), str(output), directory], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_production_extracted_policy_and_unmapped_route(self):
        mono = EDITOR / "bin/mono"
        compiler = EDITOR / "lib/mono/msbuild/Current/bin/Roslyn/csc.exe"
        if not mono.exists() or not compiler.exists():
            self.skipTest("matching Unity Mono compiler is unavailable")
        owner = (RUNTIME_ROOT / "input/NovaInputBoundary.cs").read_text()
        bridge = (RUNTIME_ROOT / "input/NovaInputBridge.cs").read_text()
        policy = extract_class(owner, "public static class InputSessionPolicy")
        host = (
            """using System;
"""
            + policy
            + """
public sealed class NovaInputBridge {
 public sealed class Mapping {}
"""
            + extract_method(bridge, "public static bool IsAutomaticDiagnosticWithoutPhysicalInput(")
            + """
"""
            + extract_method(bridge, "public static bool IsPhysicalInputAvailable(")
            + """
"""
            + extract_method(bridge, "public static bool MissingMappingRequiresNeutral(")
            + """
}
public static class Program {
 static void Check(bool value, string name) { if (!value) throw new Exception(name); }
 public static void Main() {
  Check(InputSessionPolicy.Resolve("Retroid Pocket Nova", false) == InputSessionPolicy.Mode.MeasuredNovaPhysicalInput, "Nova physical");
  Check(InputSessionPolicy.Resolve("Retroid Pocket Nova", true) == InputSessionPolicy.Mode.MeasuredNovaPhysicalInput, "Nova bringup unchanged");
  Check(InputSessionPolicy.Resolve("AYN Thor", true) == InputSessionPolicy.Mode.AutomaticDiagnosticWithoutPhysicalInput, "Thor explicit bringup");
  Check(InputSessionPolicy.Resolve("AYN Thor", false) == InputSessionPolicy.Mode.TouchWithoutPhysicalInput, "Thor ordinary touch; physical input remains unavailable");
  Check(InputSessionPolicy.Resolve("retroid pocket nova", true) == InputSessionPolicy.Mode.RefuseUnmeasuredPhysicalInput, "lowercase Nova refused");
  Check(InputSessionPolicy.Resolve("Retroid Pocket Nova Pro", true) == InputSessionPolicy.Mode.RefuseUnmeasuredPhysicalInput, "Nova-like model refused");
  Check(InputSessionPolicy.Resolve(null, true) == InputSessionPolicy.Mode.RefuseUnmeasuredPhysicalInput, "null model refused");
  Check(InputSessionPolicy.Resolve("", true) == InputSessionPolicy.Mode.RefuseUnmeasuredPhysicalInput, "blank model refused");
  Check(InputSessionPolicy.Resolve("unknown", true) == InputSessionPolicy.Mode.RefuseUnmeasuredPhysicalInput, "unknown model refused");
  Check(InputSessionPolicy.Resolve("ayn thor", true) == InputSessionPolicy.Mode.RefuseUnmeasuredPhysicalInput, "Thor model matching remains exact");
  Check(NovaInputBridge.IsAutomaticDiagnosticWithoutPhysicalInput(true, true), "Thor explicit diagnostic-only route");
  Check(!NovaInputBridge.IsAutomaticDiagnosticWithoutPhysicalInput(false, true), "ordinary mode cannot route");
  Check(!NovaInputBridge.IsAutomaticDiagnosticWithoutPhysicalInput(true, false), "legacy diagnostic remains mapped-mode");
  Check(!NovaInputBridge.IsAutomaticDiagnosticWithoutPhysicalInput(false, false), "legacy ordinary mode remains unchanged");
  var mapped = new NovaInputBridge.Mapping();
  Check(NovaInputBridge.IsPhysicalInputAvailable(false, mapped), "mapped legacy bridge remains physically available");
  Check(!NovaInputBridge.IsPhysicalInputAvailable(false, null), "null map is not physical availability");
  Check(!NovaInputBridge.IsPhysicalInputAvailable(true, mapped), "diagnostic-only mode never claims physical");
  Check(NovaInputBridge.MissingMappingRequiresNeutral(true, false, false), "legacy null map neutral");
  Check(NovaInputBridge.MissingMappingRequiresNeutral(true, true, false), "legacy diagnostic null map remains neutral");
  Check(NovaInputBridge.MissingMappingRequiresNeutral(true, false, true), "diagnostic-only flag without diagnostic input stays neutral");
  Check(!NovaInputBridge.MissingMappingRequiresNeutral(true, true, true), "Thor diagnostic permits null map");
  Check(!NovaInputBridge.MissingMappingRequiresNeutral(false, false, false), "legacy mapped ordinary route proceeds");
  Check(!NovaInputBridge.MissingMappingRequiresNeutral(false, true, false), "legacy mapped diagnostic proceeds");
  Check(!NovaInputBridge.MissingMappingRequiresNeutral(false, false, true), "mapped route does not need missing-map neutral");
  Check(!NovaInputBridge.MissingMappingRequiresNeutral(false, true, true), "Thor route with no map remains diagnostic");
  Console.WriteLine("portable input policy and routing passed");
 }
}
"""
        )
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "InputRouteHost.cs"
            output = Path(directory) / "InputRouteHost.exe"
            source.write_text(host)
            compiled = subprocess.run(
                [str(mono), str(compiler), "-nologo", "-langversion:9", "-out:" + str(output), str(source)], capture_output=True, text=True
            )
            self.assertEqual(compiled.returncode, 0, compiled.stdout + compiled.stderr)
            executed = subprocess.run([str(mono), str(output)], capture_output=True, text=True)
            self.assertEqual(executed.returncode, 0, executed.stdout + executed.stderr)
            self.assertIn("portable input policy and routing passed", executed.stdout)

    def test_all_runtime_mapping_and_raw_reads_are_guarded_for_no_physical_mode(self):
        bridge = (RUNTIME_ROOT / "input/NovaInputBridge.cs").read_text()
        update = extract_method(bridge, "    void Update()")
        fixed = extract_method(bridge, "    void FixedUpdate()")
        no_physical_branch = update.index("IsAutomaticDiagnosticWithoutPhysicalInput(diagnosticInput, automaticDiagnosticOnly)")
        presence_create = update.index("new ControllerPresence(requiredControllerName)")
        raw_read = update.index("ReadRaw()")
        self.assertLess(no_physical_branch, presence_create)
        self.assertLess(no_physical_branch, raw_read)
        branch = update[no_physical_branch:presence_create]
        self.assertNotIn("ReadRaw()", branch)
        self.assertNotIn("new ControllerPresence", branch)
        self.assertIn("IsAutomaticDiagnosticWithoutPhysicalInput(diagnosticInput, automaticDiagnosticOnly)", fixed)
        self.assertIn("MissingMappingRequiresNeutral(mapping == null, diagnosticInput, automaticDiagnosticOnly)", fixed)
        self.assertIn("!automaticDiagnosticOnly && mapping != null && mapping.enableSkills || enableAllSkills", fixed)
        self.assertIn("diagnosticInput || touchManual ? null : ReadRaw()", fixed)

        offline = (RUNTIME_ROOT / "session/OfflineApplicationBoundary.cs").read_text()
        present = extract_method(offline, "        public bool OfflineUiControllerPresent()")
        self.assertLess(present.index("if (map == null"), present.index("Input.GetJoystickNames()"))
        self.assertLess(present.index("if (map == null"), present.index("ReadRaw()"))
        self.assertIn("if (coordinator.IsNovaInput())", offline)
        self.assertIn("mode != InputSessionPolicy.Mode.RefuseUnmeasuredPhysicalInput", offline)
        self.assertIn("if (coordinator.UsesTouchUi())\n                offlineMenuMapping = null;", offline)
        self.assertIn("offlineMenuMapping != null && OfflineUiControllerPresent()", offline)
        self.assertIn("coordinator.r.nova.mapping != null && coordinator.r.nova.physicalInputAvailable", offline)

        world = (RUNTIME_ROOT / "world/IntegratedWorldBoundary.cs").read_text()
        self.assertIn("inputBridge.manualInputAvailable &&", world)
        self.assertIn("inputBridge.automaticDiagnosticOnly", world)
        restart = extract_method(world, "        public void ObserveWorldRestartInput()")
        self.assertIn("coordinator.r.nova.mapping != null && coordinator.r.nova.physicalInputAvailable", restart)

        owner = (RUNTIME_ROOT / "input/NovaInputBoundary.cs").read_text()
        self.assertIn('inputSource = physicalInputAvailable ? "measured-nova"', owner)
        self.assertIn('automaticDiagnosticOnly ? "automatic-diagnostic" : "touch"', owner)
        self.assertIn("automaticDiagnosticOnly = inputMode == InputSessionPolicy.Mode.AutomaticDiagnosticWithoutPhysicalInput", owner)
        self.assertIn("bool automaticDiagnosticOnly = inputMode == InputSessionPolicy.Mode.AutomaticDiagnosticWithoutPhysicalInput", owner)
        self.assertIn("physicalInputAvailable ? NovaInputBridge.ReadRaw() : null", owner)
        self.assertIn("if (automaticDiagnosticOnly)\n                {\n                    coordinator.worldManualTakeover = false;", owner)

        settings = (RUNTIME_ROOT / "input/OfflineSettingsBoundary.cs").read_text()
        self.assertIn("coordinator.r.nova.physicalInputAvailable", settings)
        self.assertIn("Touch controls: survivor, difficulty, and start", offline)
        self.assertIn('Start run" : "Start run (A)', offline)
        self.assertIn("Android offline settings · touch controls", settings)


if __name__ == "__main__":
    unittest.main()
