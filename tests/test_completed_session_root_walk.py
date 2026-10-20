"""Execute the production completed-session root walk against small managed graphs."""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_native_commerce_release_order import braced_block  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OWNER = ROOT / "tools/unity/runtime/session/SessionResourceBoundary.cs"

HOST = r"""
using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;

public sealed class Probe { public object report; public Probe previous; }
public sealed class Holder { public List<object> items = new List<object>(); public Dictionary<string, object> byName = new Dictionary<string, object>(); }
public struct Pair { public object value; }
public sealed class Subscriber { public bool destroyed; public void On(int x) { } public static void Static(int x) { } }
public static class Roots
{
    public static Holder holder;
    public static event Action changed;
    public static WeakReference weak;
    public static Pair[] pairs;
    public static void Raise() { if (changed != null) changed(); }
    public static void Subscribe(Action action) { changed += action; }
}
public static class Unrelated { public static int count = 3; public static string text = "x"; }

public static class Program
{
    static KeyValuePair<string, object> P(string name, object value) { return new KeyValuePair<string, object>(name, value); }
    static Type[] Types() { return new[] { typeof(Roots), typeof(Unrelated) }; }
    static void Reset() { Roots.holder = null; Roots.weak = null; Roots.pairs = null; typeof(Roots).GetField("changed", BindingFlags.Static | BindingFlags.NonPublic).SetValue(null, null); }
    public static void Main()
    {
        var output = new Dictionary<string, object>();
        var empty = new List<KeyValuePair<string, object>>();

        Reset();
        var a = new Probe { report = new object() };
        Roots.holder = new Holder();
        Roots.holder.byName.Add("session", a);
        var found = CompletedSessionRootWalk.Find(Types(), empty, new[] { P("completed[0].probe", a), P("completed[0].report", a.report) }, 1000, 8);
        output["dictionary"] = found.paths;

        Reset();
        var b = new Probe();
        Roots.Subscribe(() => GC.KeepAlive(b));
        output["delegate"] = CompletedSessionRootWalk.Find(Types(), empty, new[] { P("completed[0].probe", b) }, 1000, 8).paths;

        Reset();
        var c = new Probe();
        Roots.weak = new WeakReference(c);
        output["weak_only"] = CompletedSessionRootWalk.Find(Types(), empty, new[] { P("completed[0].probe", c) }, 1000, 8).paths;

        Reset();
        var older = new Probe();
        var newer = new Probe { previous = older };
        Roots.pairs = new[] { new Pair { value = newer } };
        output["chain"] = CompletedSessionRootWalk.Find(Types(), empty, new[] { P("completed[0].probe", older), P("completed[1].probe", newer) }, 1000, 8).paths;

        Reset();
        var live = new Holder();
        var d = new Probe();
        live.items.Add(d);
        output["extra_root"] = CompletedSessionRootWalk.Find(Types(), new[] { P("live:Holder@menu", live) }, new[] { P("completed[0].probe", d) }, 1000, 8).paths;

        Reset();
        Roots.holder = new Holder();
        for (int i = 0; i < 100; i++) Roots.holder.items.Add(new Probe());
        var e = new Probe();
        Roots.holder.items.Add(e);
        var bounded = CompletedSessionRootWalk.Find(Types(), empty, new[] { P("completed[0].probe", e) }, 20, 8);
        output["budget_truncated"] = bounded.truncated;
        output["budget_paths"] = bounded.paths.Length;
        output["budget_nodes"] = bounded.nodes;

        Reset();
        var dead = new Subscriber { destroyed = true };
        var alive = new Subscriber();
        Action<int> handler = dead.On;
        handler += alive.On;
        handler += Subscriber.Static;
        int removed;
        var kept = (Action<int>)CompletedSessionRootWalk.RemoveTargets(handler, target => target is Subscriber && ((Subscriber)target).destroyed, out removed);
        output["prune_removed"] = removed;
        output["prune_remaining"] = kept.GetInvocationList().Length;
        int none;
        output["prune_null"] = CompletedSessionRootWalk.RemoveTargets(null, target => true, out none) == null && none == 0;

        Reset();
        Roots.holder = new Holder();
        for (int i = 0; i < 3; i++) Roots.holder.items.Add(new Probe());
        Roots.holder.items.Add(new byte[100]);
        var census = CompletedSessionRootWalk.Find(Types(), empty, new KeyValuePair<string, object>[0], 1000, 8, 10).census;
        output["census"] = census;
        output["attribution"] = CompletedSessionRootWalk.Find(Types(), empty, new KeyValuePair<string, object>[0], 1000, 8, 10).rootAttribution;

        var registry = new List<Subscriber> { new Subscriber { destroyed = true }, new Subscriber(), new Subscriber { destroyed = true }, new Subscriber() };
        var survivor = registry[3];
        output["registry_removed"] = CompletedSessionRootWalk.RemoveWhere(registry, item => ((Subscriber)item).destroyed);
        output["registry_order"] = registry.Count == 2 && ReferenceEquals(registry[1], survivor);

        var parts = new List<string>();
        foreach (var entry in output)
        {
            var paths = entry.Value as string[];
            parts.Add("\"" + entry.Key + "\":" + (paths != null ? "[" + string.Join(",", Array.ConvertAll(paths, x => "\"" + x.Replace("\"", "'") + "\"")) + "]" : entry.Value.ToString().ToLowerInvariant()));
        }
        Console.WriteLine("{" + string.Join(",", parts) + "}");
    }
}
"""


def compile_and_run(source):
    editor = Path(os.environ.get("UNITY_EDITOR_PATH", "/Applications/Unity/Hub/Editor/2021.3.45f2/Unity.app/Contents"))
    mono = editor / "MonoBleedingEdge/bin/mono"
    compiler = editor / "MonoBleedingEdge/lib/mono/msbuild/Current/bin/Roslyn/csc.exe"
    if not mono.is_file() or not compiler.is_file():
        raise unittest.SkipTest("pinned Unity 2021.3.45f2 Mono/Roslyn toolchain is unavailable")
    with tempfile.TemporaryDirectory(prefix="completed-root-walk-") as temporary:
        scratch = Path(temporary).resolve()
        (scratch / "Host.cs").write_text(source)
        environment = dict(os.environ, TMPDIR=str(scratch), TMP=str(scratch), TEMP=str(scratch))
        compiled = subprocess.run(
            [str(mono), str(compiler), "-nologo", "-langversion:9", "-target:exe", "-out:" + str(scratch / "Host.exe"), str(scratch / "Host.cs")],
            cwd=scratch,
            env=environment,
            capture_output=True,
            text=True,
        )
        if compiled.returncode:
            raise AssertionError(compiled.stdout + compiled.stderr)
        executed = subprocess.run([str(mono), str(scratch / "Host.exe")], cwd=scratch, env=environment, capture_output=True, text=True)
        if executed.returncode:
            raise AssertionError(executed.stdout + executed.stderr)
        return json.loads(executed.stdout)


class CompletedSessionRootWalkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        walker = braced_block(OWNER.read_text(), "public static class CompletedSessionRootWalk")
        cls.result = compile_and_run(HOST + "\n" + walker + "\n")

    def test_names_static_field_and_collection_path(self):
        paths = self.result["dictionary"]
        self.assertEqual(len(paths), 2)
        self.assertTrue(paths[0].startswith("completed[0].probe <= Roots.holder (Holder) -> .byName"))
        self.assertIn("completed[0].report <= ", paths[1])
        self.assertIn(".report (Object)", paths[1])

    def test_follows_static_event_targets(self):
        (path,) = self.result["delegate"]
        self.assertTrue(path.startswith("completed[0].probe <= Roots.changed"))
        self.assertIn(").Target", path)

    def test_weak_references_do_not_retain(self):
        self.assertEqual(self.result["weak_only"], [])

    def test_labels_hops_through_another_completed_session(self):
        paths = self.result["chain"]
        self.assertEqual(len(paths), 2)
        older = [path for path in paths if path.startswith("completed[0].probe")][0]
        self.assertIn("[completed[1].probe]", older)
        self.assertIn(".previous (Probe)", older)

    def test_extra_named_roots(self):
        (path,) = self.result["extra_root"]
        self.assertTrue(path.startswith("completed[0].probe <= live:Holder@menu (Holder) -> .items"))

    def test_remove_targets_keeps_other_and_static_entries(self):
        self.assertEqual(self.result["prune_removed"], 1)
        self.assertEqual(self.result["prune_remaining"], 2)
        self.assertIs(self.result["prune_null"], True)

    def test_census_counts_types_and_primitive_array_bytes(self):
        census = self.result["census"]
        self.assertIn("Probe:3:0", census)
        self.assertIn("System.Byte[]:1:100", census)
        self.assertEqual(census[0], "Probe:3:0")

    def test_root_attribution_names_the_static_holder(self):
        top = self.result["attribution"][0]
        self.assertTrue(top.startswith("Roots.holder (Holder):"), top)
        self.assertGreaterEqual(int(top.rsplit(":", 1)[1]), 6)

    def test_remove_where_keeps_live_order(self):
        self.assertEqual(self.result["registry_removed"], 2)
        self.assertIs(self.result["registry_order"], True)

    def test_budget_truncates_without_inventing_a_path(self):
        self.assertIs(self.result["budget_truncated"], True)
        self.assertEqual(self.result["budget_paths"], 0)
        self.assertEqual(self.result["budget_nodes"], 20)


if __name__ == "__main__":
    unittest.main()
