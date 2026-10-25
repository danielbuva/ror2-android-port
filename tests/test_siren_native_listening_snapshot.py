from pathlib import Path
import json
import os
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
METADATA = ROOT / "recipe"
SOURCE = ROOT / "tools/unity/runtime"
POLICY = SOURCE / "stage/SirenNativeListeningSnapshotPolicy.cs"
READER = SOURCE / "stage/SirenNativeListeningSnapshotReader.cs"
MONO = Path(
    os.environ.get(
        "UNITY_MONO",
        "/Applications/Unity/Hub/Editor/2021.3.45f2/Unity.app/Contents/MonoBleedingEdge/bin/mono",
    )
)
CSC = Path(
    os.environ.get(
        "UNITY_CSC",
        "/Applications/Unity/Hub/Editor/2021.3.45f2/Unity.app/Contents/MonoBleedingEdge/lib/mono/msbuild/Current/bin/Roslyn/csc.exe",
    )
)


class SirenNativeListeningSnapshotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not MONO.is_file() or not CSC.is_file():
            raise unittest.SkipTest("Pinned Unity host compiler unavailable")
        cls.temp = tempfile.TemporaryDirectory()
        temp = Path(cls.temp.name)
        harness = temp / "Program.cs"
        harness.write_text(
            r"""
using System;
using System.Collections.Generic;
using System.Reflection;
using EntityStates.Missions.SuperRoboBallEncounter;
using RoR2;
using UnityEngine;
using UnityEngine.Networking;
public static class Program
{
    static void Require(bool ok, string why) { if (!ok) throw new Exception(why); }
    public static int Main()
    {
        var source = new List<uint>();
        var native = new List<uint>();
        for (uint i = 1; i <= 12; i++) { source.Add(i); native.Add(i); }
        Require(SirenNativeListeningSnapshotPolicy.HasExactInitialCohort(native, source), "exact admission refused");
        native[11] = 0;
        Require(!SirenNativeListeningSnapshotPolicy.HasExactInitialCohort(native, source), "zero ID admitted");
        native[11] = native[10];
        Require(!SirenNativeListeningSnapshotPolicy.HasExactInitialCohort(native, source), "duplicate ID admitted");
        native[11] = 99;
        Require(!SirenNativeListeningSnapshotPolicy.HasExactInitialCohort(native, source), "foreign replacement admitted");
        native[11] = 12;
        native.RemoveAt(11);
        Require(!SirenNativeListeningSnapshotPolicy.HasExactInitialCohort(native, source), "partial initial list admitted");
        native.Add(12); native.Add(13);
        Require(!SirenNativeListeningSnapshotPolicy.HasExactInitialCohort(native, source), "oversized initial list admitted");
        source[11] = 11;
        Require(!SirenNativeListeningSnapshotPolicy.HasExactInitialCohort(new List<uint> { 1,2,3,4,5,6,7,8,9,10,11,12 }, source),
                "duplicate source cohort ID admitted");
        source[11] = 12;

        var alive = new List<bool>();
        for (int i = 0; i < 12; i++) alive.Add(true);
        alive[2] = false; alive[5] = false;
        int nullCount;
        Require(SirenNativeListeningSnapshotPolicy.TryCountUnityNullSlots(alive, true, out nullCount) && nullCount == 2,
                "bounded Unity-null count incorrect");
        Require(!SirenNativeListeningSnapshotPolicy.TryCountUnityNullSlots(alive, false, out nullCount),
                "unknown/replaced list got a null count");
        alive.RemoveAt(11);
        Require(!SirenNativeListeningSnapshotPolicy.TryCountUnityNullSlots(alive, true, out nullCount),
                "partial list got a null count");

        Require(SirenNativeListeningSnapshotPolicy.IsSlotIdentityConsistent(6, false, false, 0),
                "same original Unity-null slot lost its immutable source ID");
        Require(SirenNativeListeningSnapshotPolicy.IsSlotIdentityConsistent(6, true, true, 6), "matching live ID refused");
        Require(!SirenNativeListeningSnapshotPolicy.IsSlotIdentityConsistent(6, true, true, 7), "replacement ID accepted");
        Require(!SirenNativeListeningSnapshotPolicy.IsSlotIdentityConsistent(0, false, false, 0), "unknown source ID accepted");
        Require(SirenNativeListeningSnapshotPolicy.IsFiniteHealth(true, 0f), "zero health was not measured as finite");
        Require(SirenNativeListeningSnapshotPolicy.IsFiniteHealth(true, -2f), "negative finite health was treated as unknown");
        Require(!SirenNativeListeningSnapshotPolicy.IsFiniteHealth(false, 12f), "absent health component became known");
        Require(!SirenNativeListeningSnapshotPolicy.IsFiniteHealth(true, Single.NaN), "NaN health became known");
        Require(!SirenNativeListeningSnapshotPolicy.IsFiniteHealth(true, Single.PositiveInfinity), "infinite health became known");
        Require(SirenNativeListeningSnapshotPolicy.IsFreshInputSample(1.5f, 1f, 1f) &&
                !SirenNativeListeningSnapshotPolicy.IsFreshInputSample(3f, 1f, 1f) &&
                !SirenNativeListeningSnapshotPolicy.IsFreshInputSample(0.5f, 1f, 1f) &&
                !SirenNativeListeningSnapshotPolicy.IsFreshInputSample(Single.NaN, 1f, 1f),
                "input freshness accepted stale, future, or nonfinite time");

        var facts = new List<SirenNativeListeningSnapshotPolicy.DamageFact> {
            new SirenNativeListeningSnapshotPolicy.DamageFact { frame = 80, victimNetworkId = 6 },
            new SirenNativeListeningSnapshotPolicy.DamageFact { frame = 99, victimNetworkId = 7 },
            new SirenNativeListeningSnapshotPolicy.DamageFact { frame = 100, victimNetworkId = 6 },
            new SirenNativeListeningSnapshotPolicy.DamageFact { frame = 101, victimNetworkId = 0 }
        };
        int latest;
        Require(SirenNativeListeningSnapshotPolicy.CountRetainedVictimDamageFacts(facts, 6, 90, out latest) == 1 && latest == 100,
                "victim-ID/time-window correlation incorrect");
        Require(SirenNativeListeningSnapshotPolicy.CountRetainedVictimDamageFacts(facts, 0, 0, out latest) == 0,
                "zero victim ID matched");

        var owner = new SirenEncounterSession();
        var listening = new Listening();
        typeof(Listening).GetField("hasRegisteredEggs", BindingFlags.Instance | BindingFlags.NonPublic).SetValue(listening, true);
        typeof(Listening).GetField("previousDestroyedEggCount", BindingFlags.Instance | BindingFlags.NonPublic).SetValue(listening, 2);
        typeof(Listening).GetField("beginEncounterCountdown", BindingFlags.Instance | BindingFlags.NonPublic).SetValue(listening, true);
        typeof(Listening).GetField("encounterCountdown", BindingFlags.Instance | BindingFlags.NonPublic).SetValue(listening, 1.25f);
        owner.stateMachine = new FakeStateMachine { state = listening };
        owner.observedNativeListeningState = listening;
        owner.Report.nativeEggRegistrationMatchesSourceEntry = true;
        owner.Report.sourceEntryEggNetworkIds = new uint[12];
        owner.observedNativeEggList = new List<GameObject>();
        for (uint id = 1; id <= 12; id++)
        {
            var gameObject = new GameObject();
            var identity = new NetworkIdentity { isServer = true, netId = new NetworkInstanceId { Value = id }, gameObject = gameObject };
            var health = new HealthComponent { alive = id != 4, health = id == 4 ? 0f : 100f };
            gameObject.AddComponent(identity);
            gameObject.AddComponent(health);
            owner.Report.sourceEntryEggNetworkIds[id - 1] = id;
            owner.observedNativeEggList.Add(gameObject);
            NetworkServer.Register(id, gameObject);
        }
        GameObject twelfthOriginalObject = owner.observedNativeEggList[11];
        var input = new SirenEggInputReport {
            lastTargetSampleFrame = 4, lastTargetSampleRealtime = 1f, lastTargetSampleKnown = true,
            lastTargetNetworkId = 4, lastTargetVisible = true, lastTargetPrimaryRequested = true
        };
        var combat = new SurvivorCombatOutputObserver.Report();
        combat.damageFacts[0].frame = 5;
        combat.damageFacts[0].victimNetworkId = 4;
        typeof(SirenEncounterSession).GetMethod("CaptureNativeListeningSnapshot", BindingFlags.Instance | BindingFlags.NonPublic)
            .Invoke(owner, new object[] { input, combat });
        var snapshot = owner.Report.nativeListeningSnapshot;
        Require(snapshot.sampleAvailable && snapshot.registeredSlotCount == 12 && snapshot.thresholdKnown && snapshot.threshold == 4,
                "candidate reader did not report bounded registered slots/receipt-bound threshold");
        Require(snapshot.previousDestroyedCountKnown && snapshot.previousDestroyedCount == 2 && snapshot.countdownActiveKnown &&
                snapshot.countdownActive && snapshot.countdownSecondsKnown && snapshot.countdownSeconds == 1.25f,
                "receipt-bound private fields were not reported accurately");
        Require(snapshot.inputSampleFresh && snapshot.inputTargetKnown && snapshot.inputTargetNetworkId == 4 &&
                snapshot.inputTargetVisible && snapshot.inputPrimaryRequested,
                "latest ordinary input sample join was not preserved");
        Require(snapshot.slots[3].healthValueKnown && snapshot.slots[3].healthValue == 0f && !snapshot.slots[3].healthAlive &&
                snapshot.slots[3].retainedVictimDamageFacts == 1 && snapshot.slots[3].latestVictimDamageFrame == 5,
                "zero-health observation or existing victim-ID fact correlation failed");

        typeof(SirenEncounterSession).GetMethod("CaptureNativeListeningSnapshot", BindingFlags.Instance | BindingFlags.NonPublic)
            .Invoke(owner, new object[] { null, null });
        snapshot = owner.Report.nativeListeningSnapshot;
        Require(snapshot.sampleAvailable && snapshot.thresholdKnown && !snapshot.inputSampleFresh &&
                !snapshot.inputTargetKnown && !snapshot.damageObserverAvailable,
                "missing optional report was not safely represented as unknown input/combat context");
        typeof(SirenEncounterSession).GetMethod("CaptureNativeListeningSnapshot", BindingFlags.Instance | BindingFlags.NonPublic)
            .Invoke(owner, new object[] { input, combat });
        snapshot = owner.Report.nativeListeningSnapshot;
        Require(snapshot.sampleAvailable && snapshot.inputSampleFresh && snapshot.damageObserverAvailable,
                "reader did not recover after optional report arguments were absent");

        // A failure after threshold sampling but before the first slot read must
        // invalidate every value from that attempted native sample.
        typeof(SirenEncounterSession).GetMethod("ReleaseNativeListeningSnapshotBaseline", BindingFlags.Instance | BindingFlags.NonPublic)
            .Invoke(owner, null);
        NetworkServer.throwOnFind = true;
        typeof(SirenEncounterSession).GetMethod("CaptureNativeListeningSnapshot", BindingFlags.Instance | BindingFlags.NonPublic)
            .Invoke(owner, new object[] { input, combat });
        snapshot = owner.Report.nativeListeningSnapshot;
        RequireAborted(snapshot, "exception after threshold read retained sample values");
        NetworkServer.throwOnFind = false;
        typeof(SirenEncounterSession).GetMethod("CaptureNativeListeningSnapshot", BindingFlags.Instance | BindingFlags.NonPublic)
            .Invoke(owner, new object[] { input, combat });
        snapshot = owner.Report.nativeListeningSnapshot;
        Require(snapshot.sampleAvailable && snapshot.thresholdKnown && snapshot.slots.Length == 12,
                "reader did not recover after the one-shot baseline failure");

        // Throw after eight rows have already been written into the working
        // array; the aborted report must not expose any of those partial rows.
        owner.observedNativeEggList[8].throwOnGetComponent = true;
        typeof(SirenEncounterSession).GetMethod("CaptureNativeListeningSnapshot", BindingFlags.Instance | BindingFlags.NonPublic)
            .Invoke(owner, new object[] { input, combat });
        snapshot = owner.Report.nativeListeningSnapshot;
        RequireAborted(snapshot, "late slot exception exposed a partial native sample");
        owner.observedNativeEggList[8].throwOnGetComponent = false;
        typeof(SirenEncounterSession).GetMethod("CaptureNativeListeningSnapshot", BindingFlags.Instance | BindingFlags.NonPublic)
            .Invoke(owner, new object[] { input, combat });
        snapshot = owner.Report.nativeListeningSnapshot;
        Require(snapshot.sampleAvailable && snapshot.thresholdKnown && snapshot.slots.Length == 12,
                "reader did not recover after the late slot failure");

        GameObject destroyedWrapper = owner.observedNativeEggList[3];
        destroyedWrapper.destroyed = true;
        Time.frameCount = 20;
        Time.realtimeSinceStartup = 1.5f;
        typeof(SirenEncounterSession).GetMethod("CaptureNativeListeningSnapshot", BindingFlags.Instance | BindingFlags.NonPublic)
            .Invoke(owner, new object[] { input, combat });
        snapshot = owner.Report.nativeListeningSnapshot;
        Require(snapshot.sampleAvailable && snapshot.nativeUnityNullSlotCount == 1 && snapshot.slots[3].managedReferencePresent &&
                !snapshot.slots[3].unityObjectAlive && snapshot.slots[3].originalReferenceMatches &&
                snapshot.slots[3].originalNetworkId == 4 && !snapshot.slots[3].healthValueKnown,
                "Unity fake-null wrapper did not retain its original slot identity separately from managed null");
        Require(snapshot.inputSampleFresh, "fresh latest input sample became unknown");

        owner.observedNativeEggList[3] = new GameObject();
        typeof(SirenEncounterSession).GetMethod("CaptureNativeListeningSnapshot", BindingFlags.Instance | BindingFlags.NonPublic)
            .Invoke(owner, new object[] { input, combat });
        snapshot = owner.Report.nativeListeningSnapshot;
        Require(snapshot.sampleAvailable && !snapshot.nativeUnityNullSlotCountKnown &&
                !snapshot.slots[3].originalReferenceMatches &&
                !snapshot.slots[3].currentNetworkIdMatchesOriginal,
                "replacement object was mapped to the original source ID");
        owner.observedNativeEggList[3] = null;
        typeof(SirenEncounterSession).GetMethod("CaptureNativeListeningSnapshot", BindingFlags.Instance | BindingFlags.NonPublic)
            .Invoke(owner, new object[] { input, combat });
        snapshot = owner.Report.nativeListeningSnapshot;
        Require(snapshot.sampleAvailable && !snapshot.nativeUnityNullSlotCountKnown &&
                !snapshot.slots[3].managedReferencePresent && !snapshot.slots[3].unityObjectAlive &&
                !snapshot.slots[3].originalReferenceMatches && snapshot.slots[3].originalNetworkId == 4,
                "managed null entry was conflated with the original destroyed wrapper");
        owner.observedNativeEggList.RemoveAt(11);
        Time.realtimeSinceStartup = 3f;
        typeof(SirenEncounterSession).GetMethod("CaptureNativeListeningSnapshot", BindingFlags.Instance | BindingFlags.NonPublic)
            .Invoke(owner, new object[] { input, combat });
        snapshot = owner.Report.nativeListeningSnapshot;
        Require(!snapshot.sampleAvailable && !snapshot.registeredSlotCountKnown &&
                !snapshot.nativeUnityNullSlotCountKnown && !snapshot.inputSampleFresh,
                "latest malformed list/freshness failure retained stale known values");

        // A valid last sample survives the native Listening -> null transition.
        // Private Unity references are released, the subsequent ordinary poll
        // is a no-op for the scalar sample, and a new Listening starts clean.
        owner.observedNativeEggList.Add(twelfthOriginalObject);
        typeof(SirenEncounterSession).GetMethod("CaptureNativeListeningSnapshot", BindingFlags.Instance | BindingFlags.NonPublic)
            .Invoke(owner, new object[] { input, combat });
        snapshot = owner.Report.nativeListeningSnapshot;
        Require(snapshot.sampleAvailable && snapshot.observationAttempted && snapshot.thresholdKnown &&
                snapshot.registeredSlotCount == 12 && !snapshot.retainedAfterListenerExit,
                "fixture did not establish a valid final listener sample");
        SirenNativeListeningSnapshot lastListenerSample = snapshot;
        int finalFrame = snapshot.observationFrame;
        float finalRealtime = snapshot.observationRealtime;
        int finalThreshold = snapshot.threshold;
        var lifecycleHook = typeof(SirenEncounterSession).GetMethod(
            "ObserveNativeListeningStateChange", BindingFlags.Instance | BindingFlags.NonPublic);
        owner.stateMachine.state = null;
        lifecycleHook.Invoke(owner, new object[] { null });
        owner.observedNativeListeningState = null;
        Require(ReferenceEquals(owner.Report.nativeListeningSnapshot, lastListenerSample) &&
                owner.Report.nativeListeningSnapshot.retainedAfterListenerExit &&
                owner.Report.nativeListeningSnapshot.sampleAvailable &&
                owner.Report.nativeListeningSnapshot.observationFrame == finalFrame &&
                owner.Report.nativeListeningSnapshot.observationRealtime == finalRealtime &&
                owner.Report.nativeListeningSnapshot.thresholdKnown && owner.Report.nativeListeningSnapshot.threshold == finalThreshold &&
                owner.Report.nativeListeningSnapshot.slots.Length == 12,
                "Listening exit did not retain timestamped scalar evidence");
        Require(typeof(SirenEncounterSession).GetField("snapshotBaselineList", BindingFlags.Instance | BindingFlags.NonPublic)
                    .GetValue(owner) == null &&
                typeof(SirenEncounterSession).GetField("snapshotBaselineObjects", BindingFlags.Instance | BindingFlags.NonPublic)
                    .GetValue(owner) == null &&
                typeof(SirenEncounterSession).GetField("snapshotBaselineIds", BindingFlags.Instance | BindingFlags.NonPublic)
                    .GetValue(owner) == null,
                "Listening exit retained private native object references");
        typeof(SirenEncounterSession).GetMethod("CaptureNativeListeningSnapshot", BindingFlags.Instance | BindingFlags.NonPublic)
            .Invoke(owner, new object[] { input, combat });
        Require(ReferenceEquals(owner.Report.nativeListeningSnapshot, lastListenerSample) &&
                owner.Report.nativeListeningSnapshot.retainedAfterListenerExit &&
                owner.Report.nativeListeningSnapshot.observationFrame == finalFrame &&
                owner.Report.nativeListeningSnapshot.observationRealtime == finalRealtime &&
                owner.Report.nativeListeningSnapshot.slots.Length == 12,
                "post-exit capture cleared or refreshed the last listener sample");

        var nextListening = new Listening();
        owner.stateMachine.state = nextListening;
        lifecycleHook.Invoke(owner, new object[] { nextListening });
        owner.observedNativeListeningState = nextListening;
        snapshot = owner.Report.nativeListeningSnapshot;
        Require(!ReferenceEquals(snapshot, lastListenerSample) && !snapshot.observationAttempted &&
                !snapshot.retainedAfterListenerExit && !snapshot.sampleAvailable && !snapshot.thresholdKnown &&
                snapshot.slots != null && snapshot.slots.Length == 0,
                "new Listening instance inherited the previous listener snapshot");
        return 0;
    }

    static void RequireAborted(SirenNativeListeningSnapshot snapshot, string message)
    {
        Require(!snapshot.sampleAvailable && snapshot.sampleErrorType == "InvalidOperationException" &&
                !snapshot.thresholdKnown && snapshot.threshold == 0 && !snapshot.damageObserverAvailable &&
                !snapshot.nativeListReferenceMatchesBaseline && !snapshot.registeredSlotCountKnown &&
                !snapshot.nativeUnityNullSlotCountKnown && !snapshot.listeningRegisteredFlagKnown &&
                !snapshot.previousDestroyedCountKnown && !snapshot.countdownActiveKnown && !snapshot.countdownSecondsKnown &&
                snapshot.slots != null && snapshot.slots.Length == 0,
                message);
    }
}
"""
        )
        stubs = temp / "Stubs.cs"
        stubs.write_text(
            r"""
using System.Collections.Generic;
using System;
using UnityEngine;
public class SirenEggInputReport
{
    public int lastTargetSampleFrame;
    public float lastTargetSampleRealtime;
    public bool lastTargetSampleKnown, lastTargetVisible, lastTargetPrimaryRequested;
    public uint lastTargetNetworkId;
}
public class SurvivorCombatOutputObserver
{
    public const int DamageHistoryCapacity = 32;
    public struct DamageFact { public int frame; public uint victimNetworkId; }
    public class Report { public bool attached = true, cleaned, inert; public DamageFact[] damageFacts = new DamageFact[32]; }
}
public class SirenReport
{
    public SirenNativeListeningSnapshot nativeListeningSnapshot;
    public bool nativeEggRegistrationMatchesSourceEntry;
    public uint[] sourceEntryEggNetworkIds;
}
public class FakeStateMachine : UnityEngine.Object { public object state; }
public sealed partial class SirenEncounterSession
{
    public SirenReport Report = new SirenReport();
    public FakeStateMachine stateMachine;
    public EntityStates.Missions.SuperRoboBallEncounter.Listening observedNativeListeningState;
    public List<GameObject> observedNativeEggList;
    public bool NativeEggRegistrationObserved = true;
    public bool NativeEncounterStarted;
    public bool IsLiveNetworkOwner() => true;
    public static System.Reflection.FieldInfo ListeningHasRegisteredEggsField =
        typeof(EntityStates.Missions.SuperRoboBallEncounter.Listening).GetField("hasRegisteredEggs");
}
namespace UnityEngine
{
    public class Object
    {
        public bool destroyed;
        public static implicit operator bool(Object value) => value != null && !value.destroyed;
    }
    public class GameObject : Object
    {
        readonly Dictionary<System.Type, object> components = new Dictionary<System.Type, object>();
        public bool throwOnGetComponent;
        public void AddComponent<T>(T value) where T : class { components[typeof(T)] = value; }
        public T GetComponent<T>() where T : class
        {
            if (throwOnGetComponent) throw new InvalidOperationException("injected late component read failure");
            return components.ContainsKey(typeof(T)) ? (T)components[typeof(T)] : null;
        }
    }
    public static class Time { public static int frameCount = 1; public static float realtimeSinceStartup = 1f; }
}
namespace UnityEngine.Networking
{
    public struct NetworkInstanceId { public uint Value; }
    public class NetworkIdentity : UnityEngine.Object
    {
        public bool isServer;
        public NetworkInstanceId netId;
        public UnityEngine.GameObject gameObject;
    }
    public static class NetworkServer
    {
        static readonly Dictionary<uint, UnityEngine.GameObject> objects = new Dictionary<uint, UnityEngine.GameObject>();
        public static bool throwOnFind;
        public static void Register(uint id, UnityEngine.GameObject gameObject) { objects[id] = gameObject; }
        public static UnityEngine.GameObject FindLocalObject(NetworkInstanceId id)
        {
            if (throwOnFind) throw new InvalidOperationException("injected local-object read failure");
            return objects.ContainsKey(id.Value) ? objects[id.Value] : null;
        }
    }
}
namespace RoR2
{
    public class HealthComponent : UnityEngine.Object { public float health; public bool alive; }
}
namespace EntityStates.Missions.SuperRoboBallEncounter
{
    public class Listening
    {
        public static int eggsDestroyedToTriggerEncounter = 4;
        private List<UnityEngine.GameObject> eggList;
        private bool hasRegisteredEggs;
        private int previousDestroyedEggCount;
        private bool beginEncounterCountdown;
        private float encounterCountdown;
    }
}
"""
        )
        cls.exe = temp / "snapshot-tests.exe"
        compile_result = subprocess.run(
            [str(MONO), str(CSC), "/nologo", "/out:" + str(cls.exe), str(POLICY), str(READER), str(stubs), str(harness)],
            capture_output=True,
            text=True,
            check=False,
        )
        if compile_result.returncode:
            raise AssertionError(compile_result.stdout + compile_result.stderr)

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, "temp"):
            cls.temp.cleanup()

    def test_policy_fixture_compiles_and_runs(self):
        result = subprocess.run([str(MONO), str(self.exe)], capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_reader_is_passive_and_reuses_owned_reports(self):
        source = READER.read_text()
        contract = (SOURCE / "stage/SirenEncounterEggTargets.cs").read_text()
        cleanup = (ROOT / "tools/unity/runtime/stage/SirenSourceEntrySession.cs").read_text()
        boundary = (SOURCE / "stage/SirenEncounterBoundary.cs").read_text()
        integrated = (SOURCE / "stage/IntegratedStageBoundary.cs").read_text()
        input_source = (SOURCE / "input/SirenEggDiagnosticInput.cs").read_text()
        sources = json.loads((METADATA / "runtime-sources.json").read_text())
        native_view_sources = json.loads((METADATA / "runtime-sources.native-view-camera.json").read_text())
        layout = json.loads((METADATA / "project-layout.json").read_text())
        expected_new_sources = {
            "runtime/stage/SirenNativeListeningSnapshotPolicy.cs",
            "runtime/stage/SirenNativeListeningSnapshotReader.cs",
        }
        self.assertIn("void CaptureNativeListeningSnapshot", source)
        self.assertIn("Report.nativeEggRegistrationMatchesSourceEntry", source)
        self.assertIn("observedNativeEggList", source)
        self.assertIn("SirenNativeListeningSnapshotPolicy.ExpectedSourceEggCount", source)
        self.assertIn("ClearListeningSample(snapshot, discardSlots: true)", source)
        self.assertIn("snapshot.thresholdKnown = false", source)
        self.assertIn("snapshot.slots = Array.Empty<SirenNativeEggSlotSnapshot>()", source)
        self.assertIn("nativeEggRegistrationMatchesSourceEntry", contract)
        self.assertIn("ObserveNativeListeningStateChange(current);", contract)
        self.assertIn("ReleaseNativeListeningSnapshotBaseline();", contract)
        self.assertIn("Native source egg cohort is incomplete, ambiguous, or moved; retaining source context", cleanup)
        self.assertIn("SirenNativeListeningSnapshot nativeListeningSnapshot = new SirenNativeListeningSnapshot()", boundary)
        self.assertIn("public void Observe(bool force = false, SirenEggInputReport input = null,", boundary)
        self.assertIn("CaptureNativeListeningSnapshot(input, combat);", boundary)
        tick = integrated[integrated.index("public void TickOriginalStage()") :]
        observe_at = tick.index("sirenEncounter?.Observe(force: false,")
        report_guard_at = tick.index("if (coordinator.r == null")
        self.assertLess(observe_at, report_guard_at, "observer cadence/order moved past the existing report guard")
        observe_call = tick[observe_at : tick.index(";", observe_at) + 1]
        self.assertIn("input: coordinator.r != null ? coordinator.r.sirenEggInput : null", observe_call)
        self.assertIn("coordinator.r != null && coordinator.r.world != null", observe_call)
        self.assertIn("? coordinator.r.world.survivorCombatOutputs : null", observe_call)
        self.assertLess(
            input_source.index("report.lastTargetSampleKnown = false;", input_source.index("public bool Apply(")),
            input_source.index("if (disposed || terminal)", input_source.index("public bool Apply(")),
        )
        self.assertIn("report.lastTargetPrimaryRequested = primaryRequested;", input_source)
        self.assertIn("report.lastTargetSampleKnown = true;", input_source)
        self.assertIn("if (current == null)", source)
        self.assertIn("snapshot.retainedAfterListenerExit = true", source)
        self.assertIn("snapshot.observationAttempted = true", source)
        self.assertEqual(sources, sorted(set(sources)))
        self.assertEqual(native_view_sources, sorted(set(native_view_sources)))
        self.assertEqual(sources, native_view_sources)
        self.assertTrue(expected_new_sources <= set(sources))
        self.assertTrue(expected_new_sources <= set(native_view_sources))
        self.assertEqual(set(layout["runtime_source_guids"]), set(sources))
        self.assertTrue(all(layout["runtime_source_guids"][name] is None for name in expected_new_sources))
        recipe_readme = METADATA / "README.md"
        architecture = ROOT / "docs/ARCHITECTURE.md"
        self.assertIn("SirenNativeListeningSnapshotPolicy.cs", recipe_readme.read_text())
        self.assertIn("last-observed scalars", architecture.read_text())
        for forbidden in ("NetworkServer.Spawn(", ".TakeDamage(", "SetNextState(", ".health ="):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
