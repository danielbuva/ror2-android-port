#if UNITY_EDITOR
using System;
using System.Collections.Generic;
using System.Reflection;
using RoR2;
using EntityStates;
using UnityEditor;
using UnityEngine.Networking;

// Exact-editor contract check for read-only native exit telemetry and bounded retention.
public static class TeleporterExitTraceSourceContractFixture
{
    static void Require(bool condition, string message)
    {
        if (!condition)
            throw new InvalidOperationException(message);
    }

    static void VerifyMember(Type owner, string name, Type expected, bool property = false, bool isPublic = false, bool isStatic = false)
    {
        var flags = (isStatic ? BindingFlags.Static : BindingFlags.Instance) | (isPublic ? BindingFlags.Public : BindingFlags.NonPublic);
        MemberInfo member = property ? (MemberInfo)owner.GetProperty(name, flags) : owner.GetField(name, flags);
        Type actual = member is PropertyInfo p ? p.PropertyType : (member as FieldInfo)?.FieldType;
        Require(member != null && actual == expected, "Native member contract changed: " + owner.FullName + "." + name);
    }

    static void VerifyBuffer()
    {
        var entries = new List<ObjectiveExitTraceEntry>();
        for (int i = 0; i < ObjectiveExitTraceBuffer.Capacity; i++)
            ObjectiveExitTraceBuffer.Append(entries, new ObjectiveExitTraceEntry { kind = i == 0 ? "first" : "sample", frame = i });
        ObjectiveExitTraceBuffer.Append(entries, new ObjectiveExitTraceEntry { kind = "first-fault", frame = 100 });
        Require(entries.Count == ObjectiveExitTraceBuffer.Capacity - 1 && entries[0].frame == 0 &&
                    entries.Exists(x => x.kind == "first-fault" && x.frame == 100),
                "Trace buffer failed to retain initial and first observer fault entries at capacity");
        ObjectiveExitTraceBuffer.Append(entries, new ObjectiveExitTraceEntry { kind = "terminal", frame = 101 });
        Require(entries.Count == ObjectiveExitTraceBuffer.Capacity && entries[0].frame == 0 &&
                    entries.Exists(x => x.kind == "first-fault") && entries.Exists(x => x.kind == "terminal"),
                "Trace buffer failed to reserve the terminal entry while retaining the first fault");
        for (int i = 0; i < 32; i++)
            ObjectiveExitTraceBuffer.Append(entries, new ObjectiveExitTraceEntry { kind = "sample", frame = 200 + i });
        Require(entries.Count == ObjectiveExitTraceBuffer.Capacity && entries[0].frame == 0 &&
                    entries.Exists(x => x.kind == "first-fault") && entries.Exists(x => x.kind == "terminal"),
                "Trace buffer exceeded capacity or evicted a protected observation");
        ObjectiveExitTraceBuffer.Append(entries, new ObjectiveExitTraceEntry { kind = "first-fault", frame = 300 });
        ObjectiveExitTraceBuffer.Append(entries, new ObjectiveExitTraceEntry { kind = "terminal", frame = 301 });
        Require(entries.Count == ObjectiveExitTraceBuffer.Capacity && entries.Find(x => x.kind == "first-fault").frame == 100 &&
                    entries.Find(x => x.kind == "terminal").frame == 101,
                "Repeated fault/terminal observations replaced the first protected evidence");
    }

    public static object Run()
    {
        Require(!EditorApplication.isPlaying && !EditorApplication.isCompiling && !NetworkServer.active && !NetworkClient.active,
                "Fixture requires an idle editor and no network session");
        VerifyMember(typeof(EntityStateMachine), "nextState", typeof(EntityState));
        VerifyMember(typeof(SceneExitController), "exitState", typeof(SceneExitController.ExitState));
        VerifyMember(typeof(SceneExitController), "isRunning", typeof(bool), property: true, isPublic: true, isStatic: true);
        VerifyMember(typeof(Stage), "nextStage", typeof(SceneDef));
        VerifyMember(typeof(Stage), "sceneDef", typeof(SceneDef), property: true, isPublic: true);
        VerifyMember(typeof(Stage), "stageAdvanceTime", typeof(Run.FixedTimeStamp), property: true, isPublic: true);
        VerifyMember(typeof(Run.FixedTimeStamp), "t", typeof(float), isPublic: true);
        VerifyMember(typeof(Run), "nextStageScene", typeof(SceneDef), isPublic: true);
        VerifyMember(typeof(Run), "time", typeof(float), isPublic: true);
        VerifyMember(typeof(TeleporterInteraction), "isIdle", typeof(bool), property: true, isPublic: true);
        VerifyMember(typeof(TeleporterInteraction), "isCharging", typeof(bool), property: true, isPublic: true);
        VerifyMember(typeof(TeleporterInteraction), "isCharged", typeof(bool), property: true, isPublic: true);
        VerifyMember(typeof(TeleporterInteraction), "isInFinalSequence", typeof(bool), property: true, isPublic: true);
        VerifyMember(typeof(InputBankTest), "interact", typeof(InputBankTest.ButtonState), isPublic: true);
        VerifyMember(typeof(InputBankTest.ButtonState), "down", typeof(bool), isPublic: true);
        VerifyMember(typeof(InputBankTest.ButtonState), "hasPressBeenClaimed", typeof(bool), isPublic: true);
        VerifyMember(typeof(InputBankTest.ButtonState), "justPressed", typeof(bool), property: true, isPublic: true);
        VerifyBuffer();
        return new { nativeExitMembersVerified = true, bufferBoundedAtSixteen = true, firstObservationFaultAndTerminalPreserved = true,
                     nativeGameplayMethodsNotInvoked = true };
    }
}
#endif
