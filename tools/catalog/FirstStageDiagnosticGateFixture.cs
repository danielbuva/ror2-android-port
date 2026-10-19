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

        static string DecidePolicy(Component component, GameObject capturedOwner, bool componentOwnerMatchesCaptured,
                                   bool ownerSceneMatchesRequested)
        {
            Type policy = typeof(PortSession).Assembly.GetType("NativeSourceBindingRestorePolicy", false);
            Require(policy != null, "Production retired-binding policy type is unavailable");
            MethodInfo decide = policy.GetMethod("Decide", BindingFlags.Static | BindingFlags.NonPublic);
            Require(decide != null, "Production retired-binding policy method is unavailable");
            bool componentAlive = component;
            bool ownerAlive = capturedOwner;
            object action = decide.Invoke(null, new object[]
            {
                true, componentAlive, !ReferenceEquals(component, null), ownerAlive,
                !ReferenceEquals(capturedOwner, null), componentOwnerMatchesCaptured,
                ownerSceneMatchesRequested, true
            });
            return action.ToString();
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
            GameObject creatorObject = null;
            BasicPickupDropTable original = null;
            BasicPickupDropTable owned = null;
            BasicPickupDropTable foreign = null;
            WakeController wake = null;
            CreatePickupsFromDropTable creator = null;
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
                creatorObject = new GameObject("Inactive Wake child pickup creator fixture");
                creatorObject.SetActive(false);
                creatorObject.transform.SetParent(owner.transform, false);
                creator = creatorObject.AddComponent<CreatePickupsFromDropTable>();
                wake.shamanPickupCreator = creator;
                Require(owner && owner.scene == preview && !owner.activeSelf && !owner.activeInHierarchy && !wake.isActiveAndEnabled &&
                            creator && !creator.isActiveAndEnabled,
                        "WakeController and child creator fixture must remain inactive");

                Type sessionType = typeof(PortSession).GetNestedType("WholeInteractableSession", Nested);
                MethodInfo fieldContract = sessionType.GetMethod("IsExactNativeManagedTableField", BindingFlags.Static | BindingFlags.NonPublic);
                Require(fieldContract != null, "Production native field contract is unavailable");
                foreach (string field in new[] { "goldDropTable", "silverDropTable", "bronzeDropTable" })
                    Require((bool)fieldContract.Invoke(null, new object[] { wake, "WakeAltar.WakeController." + field }),
                            "Exact native Wake field contract changed: " + field);
                Require(!(bool)fieldContract.Invoke(null, new object[] { wake, "Chest2.ChestBehavior.dropTable" }),
                        "Wrong native component type passed the field contract");
                FieldInfo chestField = typeof(ChestBehavior).GetField("dropTable", BindingFlags.Instance | BindingFlags.Public | BindingFlags.DeclaredOnly);
                Require(chestField != null && chestField.FieldType == typeof(PickupDropTable) && !chestField.IsInitOnly,
                        "Native ChestBehavior direct field API changed");

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
                creator.sourceDropTable = owned; // Model the native reward-copy assignment without invoking it.

                UnityEngine.Object.DestroyImmediate(wake);
                Require(!wake && !ReferenceEquals(wake, null),
                        "Fixture did not retain a Unity fake-null WakeController component wrapper");
                Require(owner && owner.scene == preview && creator && creator.gameObject.scene == preview && ReferenceEquals(creator.sourceDropTable, owned),
                        "Destroying only the component must leave its GameObject/child consumer live");
                Require(DecidePolicy(wake, owner, false, owner.scene == preview) == "Refuse",
                        "Dead component with a live captured owner/child consumer must refuse cleanup");

                UnityEngine.Object.DestroyImmediate(owner);
                Require(!owner && !ReferenceEquals(owner, null) && !creator && !ReferenceEquals(creator, null),
                        "Destroying the captured owner must also retire the child pickup consumer");
                Require(ReferenceEquals(read(), owned),
                        "Managed table field was not readable through the fake-null component wrapper");
                Require(DecidePolicy(wake, owner, false, false) == "RestoreCapturedManagedField",
                        "Dead component and dead captured owner should select only the captured field lease");

                Invoke(restore, lease);
                Require(ReferenceEquals(read(), original),
                        "Production lease could not restore the managed table field after native destruction");
                Invoke(restore, lease);
                Require(ReferenceEquals(read(), original),
                        "Repeated restore changed the original table field");

                foreign = ScriptableObject.CreateInstance<BasicPickupDropTable>();
                Require(foreign && !ReferenceEquals(foreign, original) && !ReferenceEquals(foreign, owned),
                        "Foreign replacement fixture table must be distinct");
                write(foreign);
                bool foreignRefused = false;
                try
                {
                    Invoke(restore, lease);
                }
                catch (InvalidOperationException)
                {
                    foreignRefused = true;
                }
                Require(foreignRefused && ReferenceEquals(read(), foreign),
                        "Production lease must refuse and preserve a foreign replacement");
                write(original);
                Invoke(restore, lease);

                result = new
                {
                    productionLease = "PortSession.WholeInteractableSession.NativeBorrowedFieldLease<BasicPickupDropTable>",
                    ownerInactive = true,
                    wakeControllerAndCapturedOwnerFakeNull = true,
                    childCreatorSurvivesComponentOnlyDestroyAndRefuses = true,
                    childCreatorRetiredWithCapturedOwner = true,
                    ownedFieldReadableAfterOwnerDestroyImmediate = true,
                    productionRestoreAfterOwnerDestroyImmediate = true,
                    repeatedRestore = true,
                    foreignReplacementRefused = true,
                    exactNativeFieldContracts = true,
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
                if (creatorObject)
                    Cleanup(ref cleanupFailure, () => UnityEngine.Object.DestroyImmediate(creatorObject));
                if (original)
                    Cleanup(ref cleanupFailure, () => UnityEngine.Object.DestroyImmediate(original));
                if (owned)
                    Cleanup(ref cleanupFailure, () => UnityEngine.Object.DestroyImmediate(owned));
                if (foreign)
                    Cleanup(ref cleanupFailure, () => UnityEngine.Object.DestroyImmediate(foreign));
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
