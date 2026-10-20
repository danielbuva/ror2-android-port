from __future__ import annotations

import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
PRIMARY = ROOT / "tools/unity/runtime/world/PrimaryFireBoundary.cs"
CLEANUP = ROOT / "tools/unity/runtime/world/AutomaticSpawnBoundary.cs"
CLEANUP_FIXTURE = ROOT / "tests/fixtures/automatic_spawn_cleanup_lease.cs"


def extract_member(source: str, declaration: str) -> str:
    start = source.index(declaration)
    opening = source.index("{", start)
    depth = 0
    for index in range(opening, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[start : index + 1]
    raise AssertionError(f"unclosed production member: {declaration}")


OBSERVER_STUBS = r"""
using System;
using UnityEngine;
using RoR2;
using EntityStates;
using EntityStates.Commando.CommandoWeapon;
namespace UnityEngine
{
    public class Object
    {
        public bool destroyed;
        public int instanceId; public int instanceIdReads;
        public static implicit operator bool(Object value) => !ReferenceEquals(value, null) && !value.destroyed;
        public int GetInstanceID() { instanceIdReads++; return instanceId; }
    }
    public static class Time { public static float realtimeSinceStartup = 18.0716858f; }
}
namespace EntityStates
{
    public class EntityState { }
    public class Idle : EntityState { }
}
namespace EntityStates.Commando.CommandoWeapon
{
    public class FirePistol2 : EntityStates.EntityState { }
    public class ReloadPistols : EntityStates.EntityState { }
}
namespace RoR2
{
    public class CharacterBody : UnityEngine.Object
    {
        SkillLocator locator; public int locatorReads; public bool throwLocator;
        float spreadValue = 7f; public int spreadReads;
        public float spreadBloomAngle { get { spreadReads++; return spreadValue; } set { spreadValue=value; } }
        public SkillLocator skillLocator { get { locatorReads++; if (throwLocator) throw failure; return locator; } set { locator=value; } }
        public Exception failure;
    }
    public class SkillLocator : UnityEngine.Object
    {
        GenericSkill current; public int primaryReads; public bool throwPrimary; public Exception failure;
        public GenericSkill primary { get { primaryReads++; if (throwPrimary) throw failure; return current; } set { current=value; } }
    }
    public class GenericSkill : UnityEngine.Object
    {
        EntityStateMachine machine; public int machineReads; public bool throwMachine; public Exception failure;
        public EntityStateMachine stateMachine { get { machineReads++; if (throwMachine) throw failure; return machine; } set { machine=value; } }
        public int stockReads; public int stockValue=1;
        public int stock { get { stockReads++; return stockValue; } }
    }
    public class EntityStateMachine : UnityEngine.Object
    {
        EntityStates.EntityState current; public int stateReads; public bool throwState; public Exception failure;
        public string customName="Weapon";
        public EntityStates.EntityState state { get { stateReads++; if (throwState) throw failure; return current; } set { current=value; } }
    }
}
public sealed class SessionReport { public string phase="integrated-world-playing"; public PortSession.PrimaryFireReport primary; }
public sealed class PortSession
{
    public SessionReport r;
    public PortSession(SessionReport report) { r=report; }
    public void Check(bool ok, string message)
    {
        if (!ok) { if (String.IsNullOrEmpty(r.primary.firstFailure)) r.primary.firstFailure=message; throw new InvalidOperationException(message); }
    }
"""

OBSERVER_MAIN = r"""
public static class Program
{
    static void Need(bool value, string message) { if(!value) throw new Exception(message); }
    static RoR2.CharacterBody Healthy(EntityStates.EntityState state, out RoR2.SkillLocator locator,
                                      out RoR2.GenericSkill primary, out RoR2.EntityStateMachine machine)
    {
        machine=new RoR2.EntityStateMachine { instanceId=44, state=state };
        primary=new RoR2.GenericSkill { instanceId=33, stateMachine=machine, stockValue=2 };
        locator=new RoR2.SkillLocator { instanceId=22, primary=primary };
        return new RoR2.CharacterBody { instanceId=11, skillLocator=locator };
    }
    public static void Main()
    {
        // Healthy read preserves the exact body/slot/machine/state identities and reads
        // each reference, state, stock and conditional spread only once.
        var report=new PortSession.PrimaryFireReport(); var owner=new PortSession(new SessionReport { primary=report });
        var observer=new PortSession.PrimaryObserverHarness(owner);
        RoR2.SkillLocator locator; RoR2.GenericSkill primary; RoR2.EntityStateMachine machine;
        var body=Healthy(new EntityStates.Idle(), out locator, out primary, out machine);
        observer.ObserveSpinePrimary(body);
        Need(report.observerTicks==1 && report.lastOperands.sequence==1 && report.lastOperands.seconds==18.0716858f,
             "one bounded timestamped observer witness is recorded");
        Need(report.lastOperands.bodyStatus=="live" && report.lastOperands.skillLocatorStatus=="live" &&
             report.lastOperands.primaryStatus=="live" && report.lastOperands.stateMachineStatus=="live" &&
             report.lastOperands.stateStatus=="live" && report.lastOperands.bodyInstanceId==0 &&
             report.lastOperands.primaryInstanceId==0 && report.lastOperands.stateMachineInstanceId==0 &&
             body.instanceIdReads==0 && locator.instanceIdReads==0 && primary.instanceIdReads==0 && machine.instanceIdReads==0,
             "healthy witness records liveness without instance identity queries");
        Need(body.locatorReads==1 && locator.primaryReads==1 && primary.machineReads==1 && machine.stateReads==1 &&
             primary.stockReads==1 && body.spreadReads==0,
             "healthy observation does not reread references or access conditional spread");
        var boundedSnapshot=report.lastOperands;
        observer.ObserveSpinePrimary(body);
        Need(System.Object.ReferenceEquals(boundedSnapshot, report.lastOperands) && report.observerTicks==2 &&
             report.stockAfter==2 && report.state==typeof(EntityStates.Idle).FullName && report.firstFailureOperands==null,
             "healthy report reuses one bounded snapshot and preserves captured operands");

        // Missing and Unity fake-null operands fail closed before the next dereference.
        var missingReport=new PortSession.PrimaryFireReport();
        var missingObserver=new PortSession.PrimaryObserverHarness(new PortSession(new SessionReport { primary=missingReport }));
        bool rejected=false;
        try { missingObserver.ObserveSpinePrimary(null); }
        catch (InvalidOperationException) { rejected=true; }
        Need(rejected && missingReport.firstFailure.Contains("body:clr-null") &&
             missingReport.firstFailureOperands.bodyStatus=="clr-null" && missingReport.observerTicks==1,
             "CLR-null body is explicitly witnessed and refuses the observer");

        var fakeReport=new PortSession.PrimaryFireReport();
        var fakeObserver=new PortSession.PrimaryObserverHarness(new PortSession(new SessionReport { primary=fakeReport }));
        var fakeBody=Healthy(new EntityStates.Idle(), out locator, out primary, out machine); fakeBody.destroyed=true;
        rejected=false;
        try { fakeObserver.ObserveSpinePrimary(fakeBody); }
        catch (InvalidOperationException) { rejected=true; }
        Need(rejected && fakeReport.firstFailureOperands.bodyStatus=="unity-fake-null" && fakeBody.locatorReads==0,
             "Unity fake-null body is distinguished and no later operand is read");

        var slotReport=new PortSession.PrimaryFireReport();
        var slotObserver=new PortSession.PrimaryObserverHarness(new PortSession(new SessionReport { primary=slotReport }));
        var missingSlotBody=Healthy(new EntityStates.Idle(), out locator, out primary, out machine); locator.primary=null;
        rejected=false;
        try { slotObserver.ObserveSpinePrimary(missingSlotBody); }
        catch (InvalidOperationException) { rejected=true; }
        Need(rejected && slotReport.firstFailureOperands.primaryStatus=="clr-null" &&
             slotReport.firstFailureOperands.stateMachineStatus=="not-read-prerequisite-unavailable" && primary.machineReads==0,
             "transient missing primary is identified before reading stateMachine");

        var locatorReport=new PortSession.PrimaryFireReport();
        var locatorObserver=new PortSession.PrimaryObserverHarness(new PortSession(new SessionReport { primary=locatorReport }));
        var noLocatorBody=Healthy(new EntityStates.Idle(), out locator, out primary, out machine); noLocatorBody.skillLocator=null;
        rejected=false;
        try { locatorObserver.ObserveSpinePrimary(noLocatorBody); }
        catch (InvalidOperationException) { rejected=true; }
        Need(rejected && locatorReport.firstFailureOperands.skillLocatorStatus=="clr-null" &&
             locatorReport.firstFailureOperands.primaryStatus=="not-read-prerequisite-unavailable" && locator.primaryReads==0,
             "missing SkillLocator is diagnosed before slot lookup");

        var fakeLocatorReport=new PortSession.PrimaryFireReport();
        var fakeLocatorObserver=new PortSession.PrimaryObserverHarness(new PortSession(new SessionReport { primary=fakeLocatorReport }));
        var fakeLocatorBody=Healthy(new EntityStates.Idle(), out locator, out primary, out machine); locator.destroyed=true;
        rejected=false;
        try { fakeLocatorObserver.ObserveSpinePrimary(fakeLocatorBody); }
        catch (InvalidOperationException) { rejected=true; }
        Need(rejected && fakeLocatorReport.firstFailureOperands.skillLocatorStatus=="unity-fake-null" && locator.primaryReads==0,
             "fake-null SkillLocator is distinguished from CLR null");

        var fakePrimaryReport=new PortSession.PrimaryFireReport();
        var fakePrimaryObserver=new PortSession.PrimaryObserverHarness(new PortSession(new SessionReport { primary=fakePrimaryReport }));
        var fakePrimaryBody=Healthy(new EntityStates.Idle(), out locator, out primary, out machine); primary.destroyed=true;
        rejected=false;
        try { fakePrimaryObserver.ObserveSpinePrimary(fakePrimaryBody); }
        catch (InvalidOperationException) { rejected=true; }
        Need(rejected && fakePrimaryReport.firstFailureOperands.primaryStatus=="unity-fake-null" && primary.machineReads==0,
             "fake-null GenericSkill is distinct from CLR null");

        var machineReport=new PortSession.PrimaryFireReport();
        var machineObserver=new PortSession.PrimaryObserverHarness(new PortSession(new SessionReport { primary=machineReport }));
        var missingMachineBody=Healthy(new EntityStates.Idle(), out locator, out primary, out machine); machine.destroyed=true;
        rejected=false;
        try { machineObserver.ObserveSpinePrimary(missingMachineBody); }
        catch (InvalidOperationException) { rejected=true; }
        Need(rejected && machineReport.firstFailureOperands.stateMachineStatus=="unity-fake-null" &&
             machineReport.firstFailureOperands.stateStatus=="not-read-prerequisite-unavailable" && machine.stateReads==0,
             "Unity fake-null state machine is distinguished before state access");

        var nullStateReport=new PortSession.PrimaryFireReport();
        var nullStateObserver=new PortSession.PrimaryObserverHarness(new PortSession(new SessionReport { primary=nullStateReport }));
        var nullStateBody=Healthy(null, out locator, out primary, out machine);
        rejected=false;
        try { nullStateObserver.ObserveSpinePrimary(nullStateBody); }
        catch (InvalidOperationException) { rejected=true; }
        Need(rejected && nullStateReport.firstFailureOperands.stateStatus=="clr-null",
             "null EntityState remains a strict failure with its operand distinguished");

        // A thrown accessor is diagnosed and rethrown as the identical exception.
        var exceptionReport=new PortSession.PrimaryFireReport();
        var exceptionObserver=new PortSession.PrimaryObserverHarness(new PortSession(new SessionReport { primary=exceptionReport }));
        var exceptionBody=Healthy(new EntityStates.Idle(), out locator, out primary, out machine);
        var original=new NullReferenceException("synthetic stateMachine getter failure");
        primary.throwMachine=true; primary.failure=original;
        Exception caught=null;
        try { exceptionObserver.ObserveSpinePrimary(exceptionBody); }
        catch (Exception error) { caught=error; }
        Need(System.Object.ReferenceEquals(caught, original) && exceptionReport.observerExceptionStage=="primary.stateMachine" &&
             exceptionReport.observerExceptionType==typeof(NullReferenceException).FullName && primary.machineReads==1 &&
             exceptionReport.lastOperands.exceptionStage=="primary.stateMachine" && exceptionReport.firstFailureOperands!=null &&
             exceptionBody.instanceIdReads==1 && locator.instanceIdReads==1 && primary.instanceIdReads==1,
             "property exception is labeled, frozen once and rethrown without rereading: caught=" +
             (caught==null?"null":caught.GetType().FullName) + " stage=" + exceptionReport.observerExceptionStage +
             " snap=" + exceptionReport.lastOperands.exceptionStage + " frozen=" + (exceptionReport.firstFailureOperands!=null) +
             " ids=" + exceptionBody.instanceIdReads + "/" + locator.instanceIdReads + "/" + primary.instanceIdReads);
        var frozenException=exceptionReport.firstFailureOperands;
        primary.throwMachine=false;
        exceptionObserver.ObserveSpinePrimary(exceptionBody);
        Need(System.Object.ReferenceEquals(frozenException,exceptionReport.firstFailureOperands) &&
             frozenException.exceptionStage=="primary.stateMachine" && exceptionReport.lastOperands.exceptionStage==null,
             "later observation reuses last snapshot without replacing the frozen first failure");

        var stateExceptionReport=new PortSession.PrimaryFireReport();
        var stateExceptionObserver=new PortSession.PrimaryObserverHarness(new PortSession(new SessionReport { primary=stateExceptionReport }));
        var stateExceptionBody=Healthy(new EntityStates.Idle(), out locator, out primary, out machine);
        var stateException=new NullReferenceException("synthetic state getter failure");
        machine.throwState=true; machine.failure=stateException; caught=null;
        try { stateExceptionObserver.ObserveSpinePrimary(stateExceptionBody); }
        catch (Exception error) { caught=error; }
        Need(System.Object.ReferenceEquals(caught,stateException) && stateExceptionReport.observerExceptionStage=="stateMachine.state" &&
             machine.stateReads==1,"state getter exception is labeled and rethrown once");

        // Fire-only spread read remains once and after the same captured state check.
        var fireReport=new PortSession.PrimaryFireReport();
        var fireObserver=new PortSession.PrimaryObserverHarness(new PortSession(new SessionReport { primary=fireReport }));
        var fireBody=Healthy(new EntityStates.Commando.CommandoWeapon.FirePistol2(), out locator, out primary, out machine);
        fireObserver.ObserveSpinePrimary(fireBody);
        Need(fireBody.spreadReads==1 && fireReport.spreadAfter==7f && fireReport.shots==1,
             "the original fire-state branch still reads spread once and counts the same state");
    }
}
"""

CLEANUP_MAIN = r"""
public sealed class SessionReport
{
    public string phase="original-primary";
    public string error, firstFailure, firstFailurePhase, automaticSpawnCleanupError;
    public bool success=true, cleanup=true;
}
public sealed class GuardHarness
{
    public SessionReport r;
    public GuardHarness(SessionReport report) { r=report; }
    public System.Collections.IEnumerator Run(System.Collections.IEnumerator routine, System.Action<System.Exception> onError)
    { return RunGuarded(routine,onError); }
    HELPERS
}
public static class CleanupPrimaryHarness
{
    static void Need(bool value, string message) { if(!value) throw new System.Exception(message); }
    static GenericSkill Slot(string name, UnityEngine.GameObject owner) =>
        new GenericSkill { stateMachine=new EntityStateMachine { name=name, gameObject=owner } };
    sealed class PrimaryThrowingEnumerator : System.Collections.IEnumerator
    {
        readonly GuardHarness guard; readonly SkillLocator incomplete; readonly System.Exception primary;
        public PrimaryThrowingEnumerator(GuardHarness owner, SkillLocator skills, System.Exception error)
        { guard=owner; incomplete=skills; primary=error; }
        public object Current { get { return null; } }
        public bool MoveNext()
        {
            try { throw primary; }
            finally
            {
                System.Exception cleanup=null;
                ProductionCleanup.CaptureAutomaticSpawnCleanup(
                    () => ProductionCleanup.CaptureCanonicalSkillMachinesForCleanup(incomplete), ref cleanup);
                if(cleanup!=null) GuardHarness.RecordAutomaticSpawnCleanupFailure(guard.r,cleanup);
            }
        }
        public void Reset() { throw new System.NotSupportedException(); }
    }
    public static void Main()
    {
        var owner=new UnityEngine.GameObject("body");
        var valid=new SkillLocator { primary=Slot("Weapon",owner), secondary=Slot("Weapon2",owner),
                                     utility=Slot("Utility",owner), special=Slot("Special",owner) };
        var captured=ProductionCleanup.CaptureCanonicalSkillMachinesForCleanup(valid);
        Need(captured.Length==4 && captured[0].name=="Weapon" && captured[1].name=="Weapon2",
             "cleanup helper preserves exact canonical slot identities");
        var incomplete=new SkillLocator { primary=Slot("Weapon",owner), secondary=null,
                                          utility=Slot("Utility",owner), special=Slot("Special",owner) };
        var report=new SessionReport(); var guard=new GuardHarness(report);
        var primary=new System.NullReferenceException("primary observer dereference");
        Exception received=null;
        var guarded=guard.Run(new PrimaryThrowingEnumerator(guard,incomplete,primary),
                                     error => { received=error; GuardHarness.RecordPrimarySessionFailure(report,error); });
        while(guarded.MoveNext()) { }
        Need(System.Object.ReferenceEquals(received,primary),"outer guarded iterator passes original exception identity");
        Need(report.error.Contains("primary observer dereference") && report.firstFailure=="primary observer dereference" &&
             report.firstFailurePhase=="original-primary" && !report.success,
             "outer handler retains the primary failure attribution");
        Need(report.automaticSpawnCleanupError!=null &&
             report.automaticSpawnCleanupError.Contains("missing a canonical skill slot"),
             "strict cleanup refusal is separately retained without overwriting primary error");
        var fake=Slot("Weapon2",owner); fake.destroyed=true;
        bool rejected=false;
        try { ProductionCleanup.CaptureCanonicalSkillMachinesForCleanup(
                 new SkillLocator { primary=Slot("Weapon",owner), secondary=fake, utility=Slot("Utility",owner), special=Slot("Special",owner) }); }
        catch(System.InvalidOperationException) { rejected=true; }
        Need(rejected,"fake-null canonical state machine remains refused");
    }
}
"""


class PrimaryOperandWitnessTests(unittest.TestCase):
    def compiler(self):
        editor = Path(os.environ.get("UNITY_EDITOR_PATH", "/Applications/Unity/Hub/Editor/2021.3.45f2/Unity.app/Contents"))
        mono = editor / "MonoBleedingEdge/bin/mono"
        compiler = editor / "MonoBleedingEdge/lib/mono/msbuild/Current/bin/Roslyn/csc.exe"
        if not mono.is_file() or not compiler.is_file():
            self.skipTest("pinned Unity host compiler unavailable")
        return mono, compiler

    def compile_run(self, fixture: str, harness: str):
        mono, compiler = self.compiler()
        with tempfile.TemporaryDirectory(prefix="toolbot-2391-primary-witness-") as temp:
            temp_path = Path(temp).resolve()
            source, exe = temp_path / "Observer.cs", temp_path / "Observer.exe"
            source.write_text(fixture + "\n" + harness, encoding="utf-8")
            compiled = subprocess.run(
                [str(mono), str(compiler), "-nologo", "-langversion:9", "-target:exe", "-out:" + str(exe), str(source)], capture_output=True, text=True
            )
            self.assertEqual(
                compiled.returncode,
                0,
                compiled.stdout + compiled.stderr + "\n" + "\n".join(f"{i + 1}: {line}" for i, line in enumerate(fixture.splitlines()) if i > 320),
            )
            ran = subprocess.run([str(mono), str(exe)], capture_output=True, text=True)
            self.assertEqual(ran.returncode, 0, ran.stdout + ran.stderr)

    def test_actual_observer_under_healthy_and_invalid_operands(self):
        source = PRIMARY.read_text(encoding="utf-8")
        declarations = (
            "public class PrimaryFireOperandSnapshot",
            "public class PrimaryFireReport",
        )
        report_members = "\n".join(extract_member(source, declaration) for declaration in declarations)
        observer_declarations = (
            "static string UnityOperandStatus(",
            "static int FailureInstanceId(",
            "static void ResetPrimaryOperandSnapshot(",
            "void FreezePrimaryOperandFailure(",
            "void RecordPrimaryOperandException(",
            "void RefuseUnavailablePrimaryOperands(",
            "public void ObserveSpinePrimary(CharacterBody body)",
        )
        observer_members = "\n".join(extract_member(source, declaration) for declaration in observer_declarations)
        fixture = (
            OBSERVER_STUBS
            + report_members
            + "\n    public sealed class PrimaryObserverHarness\n    {\n"
            + "        readonly PortSession coordinator;\n"
            + "        EntityStates.EntityState lastSpineWeaponState;\n"
            + "        public PrimaryObserverHarness(PortSession owner) { coordinator=owner; }\n"
            + observer_members
            + "\n    }\n}\n"
        )
        self.compile_run(fixture, OBSERVER_MAIN)

    def test_actual_cleanup_helper_preserves_primary_and_refuses_missing(self):
        source = CLEANUP.read_text(encoding="utf-8")
        members = "\n".join(
            extract_member(source, declaration)
            for declaration in (
                "internal static void CaptureAutomaticSpawnCleanup(",
                "internal static EntityStateMachine[] CaptureCanonicalSkillMachines(",
                "internal static EntityStateMachine[] CaptureCanonicalSkillMachinesForCleanup(",
            )
        )
        fixture = CLEANUP_FIXTURE.read_text(encoding="utf-8")
        fixture = fixture.replace("public static class ProductionCleanup\n{\n}", "public static class ProductionCleanup\n{\n" + members + "\n}")
        port = (ROOT / "tools/unity/runtime/session/PortSession.cs").read_text(encoding="utf-8")
        attribution = extract_member(port, "internal static void RecordPrimarySessionFailure(")
        cleanup_record = extract_member(port, "internal static void RecordAutomaticSpawnCleanupFailure(")
        run_guarded = extract_member(port, "IEnumerator RunGuarded(")
        harness_helpers = attribution + "\n" + cleanup_record + "\n" + run_guarded
        fixture = fixture.replace("using System;", "using System;\nusing System.Collections;")
        self.compile_run(fixture, CLEANUP_MAIN.replace("HELPERS", harness_helpers))

    def test_production_callsite_is_single_capture_and_cleanup_is_nonreporting(self):
        primary = PRIMARY.read_text(encoding="utf-8")
        observer = extract_member(primary, "public void ObserveSpinePrimary(CharacterBody body)")
        self.assertEqual(observer.count("bodyRef.skillLocator"), 1)
        self.assertEqual(observer.count("locator.primary;"), 1)
        self.assertEqual(observer.count("primary.stateMachine;"), 1)
        self.assertEqual(observer.count("weapon.state;"), 1)
        self.assertNotIn("weapon.customName", observer)
        self.assertIn("var snapshot = report.lastOperands;", observer)
        self.assertEqual(observer.count("new PrimaryFireOperandSnapshot()"), 1)
        self.assertIn("RefuseUnavailablePrimaryOperands", observer)
        self.assertIn("RecordPrimaryOperandException", observer)
        freeze = extract_member(primary, "void FreezePrimaryOperandFailure(")
        self.assertIn("FailureInstanceId(body)", freeze)
        self.assertNotIn("GetInstanceID", observer)
        refuse = extract_member(primary, "void RefuseUnavailablePrimaryOperands(")
        self.assertIn("+ snapshot.firstUnavailable", refuse)
        self.assertNotIn(".ToString()", observer)
        self.assertEqual(observer.count("primary.stock;"), 1)
        cleanup = CLEANUP.read_text(encoding="utf-8")
        self.assertIn("currentCanonical = CaptureCanonicalSkillMachinesForCleanup(body.skillLocator);", cleanup)
        self.assertIn("RecordAutomaticSpawnCleanupFailure(r, automaticSpawnCleanupFailure);", cleanup)
        self.assertNotIn('r.error += " Automatic spawn cleanup', cleanup)
        helper = extract_member(cleanup, "internal static EntityStateMachine[] CaptureCanonicalSkillMachinesForCleanup(")
        self.assertIn("CaptureCanonicalSkillMachines(skills, (valid, message)", helper)
        self.assertIn("throw new InvalidOperationException(message);", helper)
        self.assertNotIn("Check(", helper)


if __name__ == "__main__":
    unittest.main(verbosity=2)
