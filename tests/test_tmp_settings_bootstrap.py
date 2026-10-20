#!/usr/bin/env python3
"""Execute the authored TMP settings owner method and verify its actual call site."""

import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "work/host-tests/tmp-bootstrap"
UNITY = Path("/Applications/Unity/Hub/Editor/2021.3.45f2/Unity.app/Contents/MonoBleedingEdge")
CSC = UNITY / "lib/mono/msbuild/Current/bin/Roslyn/csc.exe"
MONO = UNITY / "bin/mono"
HUD = ROOT / "tools/unity/runtime/presentation/RecoveredHudBoundary.cs"
PORT = ROOT / "tools/unity/runtime/session/PortSession.cs"
CANDIDATE_PORT = PORT
OFFLINE = ROOT / "tools/unity/runtime/session/OfflineApplicationBoundary.cs"
BODY = ROOT / "tools/unity/runtime/catalog/BodyCatalogBoundary.cs"


def extract_method(text, signature):
    start = text.index(signature)
    opening = text.index("{", start)
    depth = 0
    for pos in range(opening, len(text)):
        if text[pos] == "{":
            depth += 1
        elif text[pos] == "}":
            depth -= 1
            if depth == 0:
                return text[opening : pos + 1]
    raise AssertionError("unclosed production method")


class TmpSettingsBootstrapTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not MONO.is_file() or not CSC.is_file():
            raise unittest.SkipTest("Pinned Unity host compiler unavailable")

    def test_owned_settings_and_startup_order(self):
        hud_source = HUD.read_text()
        port_source = CANDIDATE_PORT.read_text()
        offline_source = OFFLINE.read_text()
        body_source = BODY.read_text()
        method = extract_method(hud_source, "public void PrepareRecoveredText()")

        start = port_source.index("CollectPriorSessionGarbage();")
        phase = port_source.index('r.phase = "tmp-settings-bootstrap";', start)
        call = port_source.index("PrepareRecoveredText();", phase)
        before_presentation = port_source.index('ObserveSessionResources("before-presentation");', start)
        offline_start = port_source.index("var applicationStart = AwaitOfflineRunStart(config);")
        assert start < phase < call < before_presentation < offline_start
        skip = offline_source.index("coordinator.r.developerSurvivorOverride)")
        menu = offline_source.index("coordinator.PrepareRecoveredMenu();")
        assert skip < menu
        assert "CleanupRecoveredText();" in body_source
        assert body_source.index("CleanupRecoveredText();") > body_source.index("ReleaseObjectiveBundlePreload();")

        OUT.mkdir(parents=True, exist_ok=True)
        test_source = OUT / "tmp_settings_bootstrap_host.cs"
        exe = OUT / "tmp_settings_bootstrap_host.exe"
        test_source.write_text(
            """using System;
        using System.Reflection;
        using UnityEngine;
        namespace UnityEngine {
          public class Object { public static implicit operator bool(Object value) { return value != null; } }
          public static class Resources {
            public static int loads;
            public static TMPro.TMP_Settings next;
            public static T Load<T>(string path) where T : class {
              loads++;
              if (path != \"TMP Settings\") throw new Exception(\"wrong resource key\");
              return next as T;
            }
          }
        }
        namespace TMPro {
          public sealed class TMP_Settings : UnityEngine.Object {
            private static TMP_Settings s_Instance;
          }
        }
        public sealed class SessionReport { public bool recoveredHudEnabled; }
        public sealed class PortSession {
          public SessionReport r = new SessionReport();
          public bool ownsRecoveredText;
          public TMPro.TMP_Settings recoveredTextSettings;
          public int checks;
          public void Check(bool value, string message) { checks++; if (!value) throw new InvalidOperationException(message); }
          public sealed class RecoveredHudSession {
            readonly PortSession coordinator;
            FieldInfo recoveredTextField;
            object priorRecoveredText;
            public RecoveredHudSession(PortSession value) { coordinator = value; }
            public void PrepareRecoveredText()
        """
            + method
            + """
          }
        }
        public static class Program {
          static FieldInfo Field() { return typeof(TMPro.TMP_Settings).GetField(\"s_Instance\", BindingFlags.Static | BindingFlags.NonPublic); }
          static void Require(bool value, string message) { if (!value) throw new Exception(message); }
          public static int Main() {
            var field = Field();
            var instance = new PortSession();
            var owner = new PortSession.RecoveredHudSession(instance);
            UnityEngine.Resources.loads = 0;
            owner.PrepareRecoveredText();
            Require(UnityEngine.Resources.loads == 0 && !instance.ownsRecoveredText, \"disabled scope loaded or owned settings\");

            instance.r.recoveredHudEnabled = true;
            var setting = new TMPro.TMP_Settings();
            UnityEngine.Resources.next = setting;
            owner.PrepareRecoveredText();
            Require(UnityEngine.Resources.loads == 1 && instance.ownsRecoveredText, \"enabled scope did not acquire settings\");
            Require(ReferenceEquals(field.GetValue(null), setting), \"settings singleton not installed\");
            owner.PrepareRecoveredText();
            Require(UnityEngine.Resources.loads == 1, \"existing owner was not idempotent\");

            field.SetValue(null, null);
            var prior = new TMPro.TMP_Settings();
            field.SetValue(null, prior);
            var unowned = new PortSession { r = new SessionReport { recoveredHudEnabled = true } };
            var unownedOwner = new PortSession.RecoveredHudSession(unowned);
            bool refused = false;
            try { unownedOwner.PrepareRecoveredText(); } catch (InvalidOperationException) { refused = true; }
            Require(refused && ReferenceEquals(field.GetValue(null), prior), \"unowned prior singleton was replaced\");
            Require(!unowned.ownsRecoveredText, \"failed setup claimed ownership\");
            Require(UnityEngine.Resources.loads == 1, \"failed prior-owner refusal loaded a replacement\");
            Console.WriteLine(\"PASS: disabled no-op, enabled acquisition, owned idempotence, strict prior-owner refusal\");
            return 0;
          }
        }
        """
        )
        subprocess.run([str(MONO), str(CSC), "-nologo", "-out:" + str(exe), str(test_source)], check=True)
        subprocess.run([str(MONO), str(exe)], check=True)
        print("PASS: actual authored caller ordering puts TMP preparation after stale-owner cleanup and before presentation/run catalog")
        print("PASS: startup TMP preparation occurs independently of the developer-override menu skip")
        print("PASS: TMP owner cleanup remains at BodyCatalog teardown")
        print("LIMIT: caller/order checks inspect production source; runtime owner method is compiled/executed with minimal Unity stubs")


if __name__ == "__main__":
    unittest.main()
