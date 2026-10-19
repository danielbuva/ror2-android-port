#if UNITY_EDITOR
using System;
using System.Reflection;
using RoR2;
using UnityEditor;
using UnityEngine;
using UnityEngine.Networking;

// Synthetic lifecycle contract fixture only. It does not identify the device
// culprit template, exercise automatic Unity lifecycle, or invoke gameplay.
public sealed class SkillResponseCleanupFixtureBehavior : SkillResponseBehavior
{
    public int callbackCount;

    public override void OnAnySkillSlotSkillChanged(GenericSkill skill)
    {
        callbackCount++;
    }
}

public static class SkillResponseCleanupExactEditorFixture
{
    static void Require(bool condition, string message)
    {
        if (!condition)
            throw new InvalidOperationException(message);
    }

    static FieldInfo RequireField(Type owner, string name, BindingFlags flags)
    {
        var field = owner.GetField(name, flags);
        Require(field != null, "Expected source field missing: " + owner.FullName + "." + name);
        return field;
    }

    static Delegate EventDelegate(GenericSkill skill, FieldInfo backingField)
    {
        return backingField.GetValue(skill) as Delegate;
    }

    static int HandlerCount(Delegate handlers, Delegate expected)
    {
        if (handlers == null)
            return 0;
        var count = 0;
        foreach (var handler in handlers.GetInvocationList())
            if (handler == expected)
                count++;
        return count;
    }

    static Delegate FindHandler(Delegate handlers, object target, string methodName)
    {
        if (handlers == null)
            return null;
        foreach (var handler in handlers.GetInvocationList())
            if (ReferenceEquals(handler.Target, target) && handler.Method.Name == methodName)
                return handler;
        return null;
    }

    static void InvokeLifecycle(MethodInfo method, SkillResponseBehavior target)
    {
        try
        {
            method.Invoke(target, null);
        }
        catch (TargetInvocationException ex) when (ex.InnerException != null)
        {
            throw ex.InnerException;
        }
    }

    public static object Run()
    {
        Require(!EditorApplication.isPlaying && !EditorApplication.isCompiling &&
                    !NetworkServer.active && !NetworkClient.active,
                "Fixture requires an idle editor without a network session");

        var baseType = typeof(SkillResponseBehavior);
        var slotsField = RequireField(baseType, "allSkillSlots", BindingFlags.Instance | BindingFlags.NonPublic);
        Require(slotsField.FieldType == typeof(GenericSkill[]), "Native skill-slot field type changed");
        var start = baseType.GetMethod("Start", BindingFlags.Instance | BindingFlags.NonPublic);
        var destroy = baseType.GetMethod("OnDestroy", BindingFlags.Instance | BindingFlags.NonPublic);
        Require(start != null && start.IsFamily && start.IsVirtual && start.GetParameters().Length == 0,
                "Native protected Start contract changed");
        Require(destroy != null && destroy.IsFamily && destroy.IsVirtual && destroy.GetParameters().Length == 0,
                "Native protected OnDestroy contract changed");

        var skillChanged = typeof(GenericSkill).GetEvent("onSkillChanged", BindingFlags.Instance | BindingFlags.Public);
        Require(skillChanged != null && skillChanged.EventHandlerType == typeof(Action<GenericSkill>),
                "Native onSkillChanged event contract changed");
        var skillChangedField = RequireField(typeof(GenericSkill), "onSkillChanged", BindingFlags.Instance | BindingFlags.NonPublic);
        Require(skillChangedField.FieldType == typeof(Action<GenericSkill>),
                "Native onSkillChanged backing delegate contract changed");

        GameObject coldOwner = null;
        GameObject startedOwner = null;
        GameObject emptyOwner = null;
        GenericSkill coldSkill = null;
        GenericSkill startedSkill = null;
        GenericSkill emptySkill = null;
        Action<GenericSkill> fixtureHandler = null;
        bool fixtureHandlerAttached = false;
        try
        {
            // Native AddComponent calls occur under inactive owners. Neither
            // GenericSkill nor the fixture behavior receives Awake/Start from
            // Unity; lifecycle entry points below are invoked explicitly.
            coldOwner = new GameObject("Skill response null-array fixture");
            coldOwner.SetActive(false);
            coldSkill = coldOwner.AddComponent<GenericSkill>();
            var coldBehavior = coldOwner.AddComponent<SkillResponseCleanupFixtureBehavior>();
            Require(slotsField.GetValue(coldBehavior) == null, "Unstarted behavior unexpectedly owns a skill array");
            Require(EventDelegate(coldSkill, skillChangedField) == null, "Cold skill unexpectedly has event handlers");
            InvokeLifecycle(destroy, coldBehavior);
            Require(EventDelegate(coldSkill, skillChangedField) == null,
                    "Null-array cleanup changed the cold skill event delegate");

            // Supply an initialized empty array to retain the native empty-loop
            // case independently from the null-array guard.
            emptyOwner = new GameObject("Skill response initialized-empty fixture");
            emptyOwner.SetActive(false);
            emptySkill = emptyOwner.AddComponent<GenericSkill>();
            var emptyBehavior = emptyOwner.AddComponent<SkillResponseCleanupFixtureBehavior>();
            var emptyArray = new GenericSkill[0];
            slotsField.SetValue(emptyBehavior, emptyArray);
            InvokeLifecycle(destroy, emptyBehavior);
            Require(ReferenceEquals(slotsField.GetValue(emptyBehavior), emptyArray),
                    "Initialized empty cleanup changed the native array");
            Require(EventDelegate(emptySkill, skillChangedField) == null,
                    "Initialized empty cleanup changed the skill event delegate");

            // Explicitly invoke native Start on another inactive instance.
            // Its GetComponents<GenericSkill>() sees this fixture-owned native
            // component, subscribes, and emits the source initial callback.
            startedOwner = new GameObject("Skill response subscribed fixture");
            startedOwner.SetActive(false);
            startedSkill = startedOwner.AddComponent<GenericSkill>();
            var startedBehavior = startedOwner.AddComponent<SkillResponseCleanupFixtureBehavior>();
            fixtureHandler = _ => { };
            skillChanged.AddEventHandler(startedSkill, fixtureHandler);
            fixtureHandlerAttached = true;

            InvokeLifecycle(start, startedBehavior);
            var initializedSlots = slotsField.GetValue(startedBehavior) as GenericSkill[];
            Require(initializedSlots != null && initializedSlots.Length == 1 && initializedSlots[0] == startedSkill,
                    "Native Start did not initialize its component-local skill array");
            Require(startedBehavior.callbackCount == 1,
                    "Native Start did not make its initial skill-change callback");
            var subscribedHandlers = EventDelegate(startedSkill, skillChangedField);
            var nativeHandler = FindHandler(subscribedHandlers, startedBehavior, "OnAnySkillSlotSkillChanged");
            Require(nativeHandler != null && HandlerCount(subscribedHandlers, nativeHandler) == 1 &&
                        HandlerCount(subscribedHandlers, fixtureHandler) == 1,
                    "Native Start did not preserve and add the expected event handlers");

            subscribedHandlers.DynamicInvoke(startedSkill);
            Require(startedBehavior.callbackCount == 2,
                    "Direct native event-delegate dispatch did not reach the source callback");

            InvokeLifecycle(destroy, startedBehavior);
            var remainingHandlers = EventDelegate(startedSkill, skillChangedField);
            Require(HandlerCount(remainingHandlers, nativeHandler) == 0 &&
                        HandlerCount(remainingHandlers, fixtureHandler) == 1,
                    "Native OnDestroy did not remove only its callback");
            skillChanged.RemoveEventHandler(startedSkill, fixtureHandler);
            fixtureHandlerAttached = false;

            return new {
                nullUnstartedArrayCleanupReturned = true,
                initializedEmptyArrayCleanupPreserved = true,
                explicitNativeStartInitializedAndSubscribed = true,
                initialAndDispatchedCallbacksObserved = true,
                nativeCleanupRemovedOnlyItsHandler = true,
                syntheticLifecycleOnly = true,
                culpritTemplateAttribution = false,
                gameplayOrAutomaticUnityLifecycleClaimed = false
            };
        }
        finally
        {
            if (fixtureHandlerAttached && startedSkill != null && fixtureHandler != null)
                skillChanged.RemoveEventHandler(startedSkill, fixtureHandler);
            if (coldOwner)
                UnityEngine.Object.DestroyImmediate(coldOwner);
            if (startedOwner)
                UnityEngine.Object.DestroyImmediate(startedOwner);
            if (emptyOwner)
                UnityEngine.Object.DestroyImmediate(emptyOwner);
        }
    }
}
#endif
