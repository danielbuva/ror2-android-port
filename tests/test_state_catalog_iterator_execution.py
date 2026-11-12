"""Execute the production state driver with nested native-style iterators."""

from pathlib import Path
import subprocess
import tempfile
import unittest


class StateCatalogIteratorExecutionTests(unittest.TestCase):
    def test_nested_yield_identity_accounting_and_early_disposal(self):
        root = Path(__file__).resolve().parents[1]
        editor = Path("/Applications/Unity/Hub/Editor/2021.3.45f2/Unity.app/Contents")
        mono = editor / "MonoBleedingEdge/bin/mono"
        compiler = editor / "MonoBleedingEdge/lib/mono/msbuild/Current/bin/Roslyn/csc.exe"
        if not mono.is_file() or not compiler.is_file():
            self.skipTest("pinned Unity Roslyn/Mono host compiler unavailable")
        source = (root / "tools/unity/runtime/session/PortSession.cs").read_text()
        start = source.index("    static IEnumerator BuildStateCatalogRoutine(")
        opening = source.index("{", start)
        depth = 0
        for end in range(opening, len(source)):
            depth += (source[end] == "{") - (source[end] == "}")
            if depth == 0:
                break
        method = source[start : end + 1].replace("static IEnumerator", "public static IEnumerator", 1)
        harness = r"""
using System;
using System.Collections;
using System.Collections.Generic;
using System.Reflection;
public class EntityStateConfiguration {}
public static class EntityStateCatalog {
    public static Func<IEnumerator> Factory;
    static IEnumerator SetElements(Type[] types, EntityStateConfiguration[] configs) { return Factory(); }
}
public static class Driver { METHOD }
public sealed class Native : IEnumerator, IDisposable {
    readonly object[] values; readonly string name; int index = -1;
    public static readonly List<string> Disposals = new List<string>();
    public Native(string name, params object[] values) { this.name=name; this.values=values; }
    public object Current { get { return values[index]; } }
    public bool MoveNext() { return ++index < values.Length; }
    public void Reset() { throw new NotSupportedException(); }
    public void Dispose() { Disposals.Add(name); }
}
public static class Program {
    static readonly object token1 = new object(), token2 = new object();
    static void Need(bool value, string message) { if (!value) throw new Exception(message); }
    static IEnumerator Create() { return new Native("root", null, new Native("child", null, token1), token2); }
    public static int Main() {
        EntityStateCatalog.Factory = Create;
        foreach (bool observed in new[] {false, true}) {
            Native.Disposals.Clear(); int reports=0; string report=null;
            Action<string> sink = observed ? (Action<string>)(value => { reports++; report=value; }) : null;
            var routine=Driver.BuildStateCatalogRoutine(new Type[0], null, sink);
            var yields=new List<object>();
            while (routine.MoveNext()) yields.Add(routine.Current);
            Need(yields.Count==4 && yields[0]==null && yields[1]==null &&
                 ReferenceEquals(yields[2],token1) && ReferenceEquals(yields[3],token2), "yield order/identity");
            Need(String.Join(",",Native.Disposals)=="child,root", "completion disposal");
            Need(reports==(observed ? 1 : 0), "single completion summary");
            if (observed) Need(report.Contains("calls=7 nullYields=2 nestedYields=1 otherYields=2"), "terminal/nested accounting");
        }
        Native.Disposals.Clear(); int earlyReports=0;
        var early=Driver.BuildStateCatalogRoutine(new Type[0], null, value => earlyReports++);
        Need(early.MoveNext() && early.MoveNext(), "enter nested iterator");
        ((IDisposable)early).Dispose();
        Need(String.Join(",",Native.Disposals)=="child,root" && earlyReports==0, "early nested disposal");
        return 0;
    }
}
""".replace("METHOD", method)
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            cs = folder / "driver.cs"
            exe = folder / "driver.exe"
            cs.write_text(harness)
            subprocess.run([str(mono), str(compiler), "/nologo", f"/out:{exe}", str(cs)], check=True, capture_output=True)
            subprocess.run([str(mono), str(exe)], check=True, capture_output=True)
