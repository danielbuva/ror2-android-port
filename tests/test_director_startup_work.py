"""Execute the startup observer with ordinary, failed and post-start callbacks."""

from pathlib import Path
import unittest

from test_native_commerce_release_order import braced_block
from test_retained_catalog_dependencies import execute_host

ROOT = Path(__file__).resolve().parents[1]


class DirectorStartupWorkTests(unittest.TestCase):
    def test_assisted_population_limit_restores_native_team_and_is_inert_for_ordinary_play(self):
        source = (ROOT / "tools/unity/runtime/world/AutomaticDirectorBoundary.cs").read_text()
        methods = "\n".join(braced_block(source, name) for name in ("void PrepareSustainedPopulationLimit()", "void RestoreSustainedPopulationLimit()"))
        harness = r"""
using System;
enum TeamIndex { Monster }
class TeamDef { public int softCharacterLimit = 40; }
static class TeamCatalog {
    static TeamDef monster = new TeamDef();
    public static TeamDef GetTeamDef(TeamIndex team) { return monster; }
}
class DirectorReport { public int restoredMonsterLimit; }
class Report { public bool combatPerformanceFocus; public DirectorReport director = new DirectorReport(); }
class Coordinator { public Report r = new Report(); }
public static class Host {
    static Coordinator coordinator = new Coordinator();
    static int? priorSustainedMonsterLimit;
METHODS
    static void Need(bool value, string reason) { if (!value) throw new Exception(reason); }
    public static void Main() {
        var monster = TeamCatalog.GetTeamDef(TeamIndex.Monster);
        PrepareSustainedPopulationLimit(); RestoreSustainedPopulationLimit();
        Need(monster.softCharacterLimit == 40 && !priorSustainedMonsterLimit.HasValue, "ordinary untouched");
        coordinator.r.combatPerformanceFocus = true;
        PrepareSustainedPopulationLimit();
        Need(monster.softCharacterLimit == 12 && priorSustainedMonsterLimit == 40, "native bounded admission");
        RestoreSustainedPopulationLimit(); RestoreSustainedPopulationLimit();
        Need(monster.softCharacterLimit == 40 && !priorSustainedMonsterLimit.HasValue, "restored once");
        Need(coordinator.r.director.restoredMonsterLimit == 40, "restoration evidence");
        coordinator.r.director = null;
        PrepareSustainedPopulationLimit(); RestoreSustainedPopulationLimit();
        Need(monster.softCharacterLimit == 40, "failed setup restoration");
        Console.WriteLine("sustained population ownership PASS");
    }
}
""".replace("METHODS", methods.replace("void ", "static void "))
        result = execute_host(harness, "sustained-population")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stdout.strip(), "sustained population ownership PASS")

    def test_callbacks_keep_identity_order_errors_and_stop_accounting(self):
        source = (ROOT / "tools/unity/runtime/world/AutomaticDirectorBoundary.cs").read_text()
        observer = braced_block(source, "sealed class DirectorStartupWork")
        harness = r"""
using System;
using System.Globalization;
public static class Host {
OBSERVER
static void Need(bool value, string message) { if (!value) throw new Exception(message); }
public static void Main() {
    CultureInfo.CurrentCulture = new CultureInfo("fr-FR");
    var observer = new DirectorStartupWork();
    int calls = 0; var token = new object();
    observer.Run(() => calls++);
    Action<object> callback = value => { Need(ReferenceEquals(value, token), "identity"); calls++; };
    observer.Run(callback, token);
    var failure = new Exception("native callback");
    try { observer.Run(() => { calls++; throw failure; }); }
    catch (Exception error) { Need(ReferenceEquals(error, failure), "exception identity"); }
    try { observer.Run<object>(value => { calls++; throw failure; }, token); }
    catch (Exception error) { Need(ReferenceEquals(error, failure), "generic exception identity"); }
    Need(calls == 4, "exactly once including failures");
    string summary = observer.Summary("spawn");
    Need(summary.StartsWith("spawnCalls=4 "), "failed calls included");
    string[] fields = summary.Split(' ');
    double total = double.Parse(fields[1].Split('=')[1], CultureInfo.InvariantCulture);
    double maximum = double.Parse(fields[2].Split('=')[1], CultureInfo.InvariantCulture);
    Need(!double.IsNaN(total) && !double.IsInfinity(total) && total >= maximum && maximum >= 0, "finite totals");
    observer.enabled = false;
    observer.Run(() => calls++);
    observer.Run(callback, token);
    Need(calls == 6 && observer.Summary("spawn") == summary, "later native callbacks unmeasured");
    Console.WriteLine("director startup observation PASS");
}
}
""".replace("OBSERVER", observer)
        result = execute_host(harness, "director")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stdout.strip(), "director startup observation PASS")


if __name__ == "__main__":
    unittest.main()
