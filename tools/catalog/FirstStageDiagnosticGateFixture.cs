#if UNITY_EDITOR
using System;
using System.Linq;
using System.Reflection;
using UnityEditor;
using UnityEngine.Networking;

// Exercises only the production pure decision gates. It creates no Unity objects,
// invokes no lifecycle callback, and makes no claim about Stage/network behavior.
public static class FirstStageDiagnosticGateFixture
{
    static Type gateType;

    static void Require(bool condition, string message)
    {
        if (!condition)
            throw new InvalidOperationException("First-stage diagnostic gate fixture failed: " + message);
    }

    static bool Gate(string methodName, params object[] arguments)
    {
        if (gateType == null)
        {
            var assembly =
                AppDomain.CurrentDomain.GetAssemblies().SingleOrDefault(candidate => candidate.GetName().Name == "Assembly-CSharp");
            Require(assembly != null, "Authored runtime assembly is not loaded");
            gateType = assembly.GetType("LabPort.SourceStageLifecycle.FirstStageDiagnosticGate", false);
            Require(gateType != null, "Production diagnostic gate type is missing");
        }
        var method = gateType.GetMethod(methodName, BindingFlags.Static | BindingFlags.NonPublic);
        Require(method != null, "Production gate method is missing: " + methodName);
        try
        {
            return (bool)method.Invoke(null, arguments);
        }
        catch (TargetInvocationException exception) when (exception.InnerException != null)
        {
            throw exception.InnerException;
        }
    }

    public static object Run()
    {
        Require(!EditorApplication.isPlaying && !EditorApplication.isCompiling && !NetworkServer.active && !NetworkClient.active,
                "Run the pure contract fixture in an idle editor without a network session");

        Require(!Gate("Requested", true, false), "native diagnostic request must remain default-off");
        Require(!Gate("Enabled", false, true, "golemplains"), "request requires integrated-world path");
        Require(Gate("Enabled", true, true, "golemplains"), "supported Golemplains selection refused");
        Require(Gate("Enabled", true, true, "lakes"), "supported Lakes selection refused");
        Require(!Gate("Enabled", true, true, "blackbeach"), "unsupported stage enabled");
        Require(Gate("RefuseUnsupported", true, true, "blackbeach"), "explicit unsupported stage must refuse rather than fall back");

        Require(Gate("HasExactStageCapture", true, true, true, true, 17u, 17u, true), "exact capture proof was refused");
        Require(!Gate("HasExactStageCapture", false, true, true, true, 17u, 17u, true),
                "failed capture callback passed despite otherwise matching fields");
        Require(!Gate("HasExactStageCapture", true, true, true, true, 17u, 18u, true), "changed network ID passed capture");
        Require(!Gate("HasExactStageCapture", true, true, true, true, 17u, 17u, false), "missing exact server-map proof passed capture");

        Require(Gate("IsAssisted", true, false, false), "native lifecycle attempt must be assisted when all other assists are off");
        Require(!Gate("NormalAcceptanceEligible", true, false, false), "native lifecycle attempt must not qualify for normal acceptance");
        Require(Gate("NormalAcceptanceEligible", false, false, false), "ordinary unassisted attempt lost normal acceptance eligibility");

        Require(Gate("MayDisarmPopulationObserver", false, false, true, true),
                "completed pre-start abort with empty queues should disarm its observer");
        Require(!Gate("MayDisarmPopulationObserver", true, false, true, true), "started incomplete population must remain retained");
        Require(!Gate("MayDisarmPopulationObserver", false, false, false, true), "observer disarmed without completed exact abort");
        Require(!Gate("MayDisarmPopulationObserver", false, false, true, false), "observer disarmed while native queues are nonempty");

        return new { productionGate = "LabPort.SourceStageLifecycle.FirstStageDiagnosticGate",
                     defaultOffAndSceneSelection = true,
                     exactStageCaptureAndMappingRefusals = true,
                     diagnosticAssistedProvenance = true,
                     preStartAbortVersusPartialPopulation = true,
                     unityLifecycleOrStageExecutionClaimed = false };
    }
}
#endif

#if UNITY_EDITOR
namespace NativeSourceFieldFixture
{
using System;
using System.Reflection;
using RoR2;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Networking;
using UnityEngine.SceneManagement;

// Diagnostic contract fixture only. It constructs an inactive WakeController,
// never enters Play Mode, and does not run Awake/Start, Run, networking, or a
// native stage lifecycle. It tests managed field access through the production
// borrowed-field lease after its Unity component and GameObject become fake-null.
public static class WakeManagedFieldLeaseExactEditorFixture
{
    const BindingFlags Nested = BindingFlags.Public | BindingFlags.NonPublic;
    const BindingFlags Instance = BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic;

    static void Require(bool condition, string message)
    {
        if (!condition)
            throw new InvalidOperationException("Wake managed-field lease fixture failed: " + message);
    }

    static void Invoke(MethodInfo method, object target)
    {
        try
        {
            method.Invoke(target, null);
        }
        catch (TargetInvocationException error) when (error.InnerException != null)
        {
            System.Runtime.ExceptionServices.ExceptionDispatchInfo.Capture(error.InnerException).Throw();
        }
    }

    static void Cleanup(ref Exception failure, Action action)
    {
        try
        {
            action();
        }
        catch (Exception error)
        {
            if (failure == null)
                failure = error;
        }
    }

    static Type FindProductionLeaseType()
    {
        Type session = typeof(PortSession).GetNestedType("WholeInteractableSession", Nested);
        Require(session != null, "Production WholeInteractableSession type is unavailable");
        Type openLease = session.GetNestedType("NativeBorrowedFieldLease`1", Nested);
        Require(openLease != null, "Production NativeBorrowedFieldLease<T> type is unavailable");
        return openLease.MakeGenericType(typeof(BasicPickupDropTable));
    }

    public static object Run()
    {
        Require(!EditorApplication.isPlaying && !EditorApplication.isCompiling &&
                    !NetworkServer.active && !NetworkClient.active && !RoR2.Run.instance,
                "Require an idle editor without Play Mode, network, or Run");

        Scene preview = EditorSceneManager.NewPreviewScene();
        GameObject owner = null;
        BasicPickupDropTable original = null;
        BasicPickupDropTable owned = null;
        WakeController wake = null;
        object lease = null;
        MethodInfo restore = null;
        object result = null;
        Exception fixtureFailure = null;
        Exception cleanupFailure = null;
        try
        {
            owner = new GameObject("Inactive Wake managed-field lease fixture");
            owner.SetActive(false);
            SceneManager.MoveGameObjectToScene(owner, preview);
            wake = owner.AddComponent<WakeController>();
            Require(owner && !owner.activeSelf && !owner.activeInHierarchy && !wake.isActiveAndEnabled,
                    "WakeController fixture must remain inactive");

            original = ScriptableObject.CreateInstance<BasicPickupDropTable>();
            owned = ScriptableObject.CreateInstance<BasicPickupDropTable>();
            Require(original && owned && !ReferenceEquals(original, owned),
                    "Fixture needs two live, distinct ScriptableObject values");
            wake.bronzeDropTable = original;

            Func<BasicPickupDropTable> read = () => wake.bronzeDropTable as BasicPickupDropTable;
            Action<BasicPickupDropTable> write = value => wake.bronzeDropTable = value;
            Type leaseType = FindProductionLeaseType();
            ConstructorInfo constructor = leaseType.GetConstructor(
                Instance, null,
                new[] { typeof(Func<BasicPickupDropTable>), typeof(Action<BasicPickupDropTable>),
                        typeof(BasicPickupDropTable), typeof(BasicPickupDropTable) }, null);
            Require(constructor != null, "Production lease constructor signature changed");
            lease = constructor.Invoke(new object[] { read, write, original, owned });
            MethodInfo bind = leaseType.GetMethod("Bind", Instance);
            restore = leaseType.GetMethod("Restore", Instance);
            Require(bind != null && restore != null, "Production lease methods are unavailable");
            Invoke(bind, lease);
            Require(ReferenceEquals(read(), owned), "Production lease did not bind the owned table");

            UnityEngine.Object.DestroyImmediate(owner);
            owner = null;
            Require(!wake && !ReferenceEquals(wake, null),
                    "Fixture did not retain a Unity fake-null WakeController wrapper");
            Require(ReferenceEquals(read(), owned),
                    "Managed table field was not readable through the fake-null wrapper");

            Invoke(restore, lease);
            Require(ReferenceEquals(read(), original),
                    "Production lease could not restore the managed table field after native destruction");
            Invoke(restore, lease);
            Require(ReferenceEquals(read(), original),
                    "Repeated restore changed the original table field");

            result = new
            {
                productionLease = "PortSession.WholeInteractableSession.NativeBorrowedFieldLease<BasicPickupDropTable>",
                ownerInactive = true,
                wakeControllerFakeNull = true,
                ownedFieldReadableAfterDestroyImmediate = true,
                productionRestoreAfterDestroyImmediate = true,
                repeatedRestore = true,
                gameplayRunNetworkAndAwakeStart = false,
                nativeWakeSpawnerPathProven = false
            };
        }
        catch (Exception error)
        {
            fixtureFailure = error;
        }
        finally
        {
            // Try the production restore before destroying its managed values,
            // including when an earlier assertion failed. Preserve the primary
            // fixture failure if cleanup itself also fails.
            if (lease != null && restore != null)
                Cleanup(ref cleanupFailure, () => Invoke(restore, lease));
            if (owner)
                Cleanup(ref cleanupFailure, () => UnityEngine.Object.DestroyImmediate(owner));
            if (original)
                Cleanup(ref cleanupFailure, () => UnityEngine.Object.DestroyImmediate(original));
            if (owned)
                Cleanup(ref cleanupFailure, () => UnityEngine.Object.DestroyImmediate(owned));
            if (preview.IsValid())
                Cleanup(ref cleanupFailure, () => EditorSceneManager.ClosePreviewScene(preview));
        }
        if (fixtureFailure != null)
            System.Runtime.ExceptionServices.ExceptionDispatchInfo.Capture(fixtureFailure).Throw();
        if (cleanupFailure != null)
            System.Runtime.ExceptionServices.ExceptionDispatchInfo.Capture(cleanupFailure).Throw();
        return result;
    }
}
}
#endif
