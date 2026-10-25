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
namespace EngineerConfigFixture
{
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Runtime.ExceptionServices;
using System.Security.Cryptography;
using EntityStates;
using EntityStates.Engi.EngiWeapon;
using RoR2;
using RoR2.AsyncManagement;
using UnityEditor;
using UnityEngine;
using UnityEngine.Networking;

// Inert native config/phase contracts only: no state entry, Addressables load,
// catalog initialization, gameplay, Run, profile, or networking lifecycle.
public static class EngineerLaserCutterConfigFixture
{
    const string Root = "Assets/WholeGame/RoR2/Base/Characters/Engi/Engi/Skills/LaserCutter/";
    const BindingFlags MutableStatic = BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Static | BindingFlags.DeclaredOnly;

    static void Require(bool condition, string message)
    {
        if (!condition) throw new InvalidOperationException("Engineer Laser Cutter config fixture failed: " + message);
    }

    static string Hash(string path)
    {
        using (var sha = SHA256.Create())
            return Convert.ToBase64String(sha.ComputeHash(File.ReadAllBytes(
                System.IO.Path.Combine(System.IO.Path.GetDirectoryName(Application.dataPath), path))));
    }

    static UnityEngine.Object Asset(string guid, string name, Type type, Dictionary<string, string> hashes)
    {
        string path = Root + name;
        Require(AssetDatabase.GUIDToAssetPath(guid) == path && AssetDatabase.AssetPathToGUID(path) == guid,
                "Generated source asset identity changed: " + name);
        hashes.Add(path, Hash(path));
        hashes.Add(path + ".meta", Hash(path + ".meta"));
        var asset = AssetDatabase.LoadAssetAtPath(path, type);
        Require(asset && !EditorUtility.IsDirty(asset), "Source asset is missing or already dirty: " + name);
        return asset;
    }

    static bool SameValue(object actual, object expected)
    {
        // EntityStateGameObject's bool/GameObject conversions load Addressables.
        // Inspect its stored identity only; never call its gameObject getter.
        if (actual is EntityStateGameObject || expected is EntityStateGameObject)
        {
            var a = actual as EntityStateGameObject;
            var b = expected as EntityStateGameObject;
            return a != null && b != null && a.directReference == null && b.directReference == null &&
                a.addressableReference != null && b.addressableReference != null &&
                a.addressableReference.AssetGUID == b.addressableReference.AssetGUID;
        }
        if (actual is AnimationCurve || expected is AnimationCurve)
        {
            var a = actual as AnimationCurve;
            var b = expected as AnimationCurve;
            return a != null && b != null && a.preWrapMode == b.preWrapMode && a.postWrapMode == b.postWrapMode &&
                a.keys.SequenceEqual(b.keys);
        }
        if (actual is UnityEngine.Object || expected is UnityEngine.Object)
            return (actual as UnityEngine.Object) == (expected as UnityEngine.Object);
        return Equals(actual, expected);
    }

    static object Sentinel(Type type)
    {
        if (type == typeof(float)) return -410001f;
        if (type == typeof(string)) return "fixture-unconfigured";
        Require(!type.IsValueType, "Unhandled native serialized field type: " + type.FullName);
        return null;
    }

    static int ApplyAndCheck(EntityStateConfiguration config, object state)
    {
        Type type = (Type)config.targetType;
        var names = new HashSet<string>(StringComparer.Ordinal);
        var expected = new List<KeyValuePair<FieldInfo, object>>();
        foreach (var serialized in config.serializedFieldsCollection.serializedFields)
        {
            Require(names.Add(serialized.fieldName), "Duplicate source config field: " + serialized.fieldName);
            // Default GetField deliberately includes inherited public fields, as
            // required by the native BuildInstanceInitializer API for phases 2/3.
            var field = type.GetField(serialized.fieldName);
            Require(field != null && !field.IsInitOnly && !field.IsLiteral,
                    "Native config field missing or immutable: " + serialized.fieldName);
            if (!field.IsStatic)
                Require(field.GetCustomAttribute<SerializeField>() != null && state != null,
                        "Native instance config field is not serialized: " + serialized.fieldName);
            object value = serialized.fieldValue.GetValue(field);
            object sentinel = Sentinel(field.FieldType);
            Require(!SameValue(sentinel, value), "Sentinel is not distinct: " + field.Name);
            field.SetValue(field.IsStatic ? null : state, sentinel);
            expected.Add(new KeyValuePair<FieldInfo, object>(field, value));
        }
        Require(expected.Count > 0, "Source config has no fields");
        config.ApplyStatic();
        Action<object> initialize = config.BuildInstanceInitializer();
        Require((state == null) == (initialize == null), "Unexpected native instance initializer availability");
        if (initialize != null) initialize(state);
        foreach (var pair in expected)
            Require(SameValue(pair.Key.GetValue(pair.Key.IsStatic ? null : state), pair.Value),
                    "Native config did not replace sentinel: " + type.FullName + "." + pair.Key.Name);
        return expected.Count;
    }

    static void CheckReference(EntityStateGameObject reference, string addressableGuid)
    {
        Require(reference != null && reference.directReference == null && reference.addressableReference != null &&
                    reference.addressableReference.AssetGUID == addressableGuid,
                "Native deferred prefab identity changed");
    }

    public static object Run()
    {
        Require(!EditorApplication.isPlaying && !EditorApplication.isCompiling && !EditorApplication.isUpdating &&
                    !NetworkServer.active && !NetworkClient.active && !RoR2.Run.instance,
                "Require the exact idle editor without Play Mode, compilation, network, or Run");
        var hashes = new Dictionary<string, string>(StringComparer.Ordinal);
        var assets = new List<UnityEngine.Object>();
        var snapshots = new List<KeyValuePair<FieldInfo, object>>();
        foreach (Type type in new[] { typeof(EnterEngiLaserCutter), typeof(EngiLaserCutter) })
            foreach (var field in type.GetFields(MutableStatic))
                if (!field.IsLiteral && !field.IsInitOnly)
                    snapshots.Add(new KeyValuePair<FieldInfo, object>(field, field.GetValue(null)));
        object result = null;
        Exception failure = null, cleanupFailure = null;
        try
        {
            string[] names = { "EnterEngiLaserCutter", "EngiLaserCutter", "EngiLaserCutter2", "EngiLaserCutter3" };
            string[] guids = { "d13b3c44ba4778e4f8c316b544f2ec01", "42a33b20af1bec44fb59eaf23a806a5b",
                               "6fb33cacc7712af46a11ef5ebc22ad80", "bc1e1611ea4513844925acb689a33933" };
            Type[] types = { typeof(EnterEngiLaserCutter), typeof(EngiLaserCutter), typeof(EngiLaserCutter2), typeof(EngiLaserCutter3) };
            var configs = new EntityStateConfiguration[4];
            for (int i = 0; i < configs.Length; i++)
            {
                configs[i] = (EntityStateConfiguration)Asset(guids[i], "EntityStates.Engi." + names[i] + ".asset",
                                                            typeof(EntityStateConfiguration), hashes);
                assets.Add(configs[i]);
                Require((Type)configs[i].targetType == types[i], "Source config target type changed: " + names[i]);
            }
            // Generated Unity GUIDs are distinct from the original Addressables
            // GUIDs above. Validate staged prefabs without resolving the wrappers.
            string[] prefabNames = { "ChargeLaserCutter", "LaserCutterBeamSmall", "LaserCutterBeamMedium", "LaserCutterBeamLarge", "LaserCutterHitVFX" };
            string[] prefabGuids = { "8ed50b0f5ebec9e4082d2fc33ad6b67a", "d29ad4cbab5f03f4d9b11a88a64032e6",
                                    "148eb904252df5445a294310fc28f02f", "4654d0483242b9c46a984dc4ad346f6a", "ff2f9c6e9194a6c48906f64bfda93c6c" };
            for (int i = 0; i < prefabNames.Length; i++)
                assets.Add(Asset(prefabGuids[i], prefabNames[i] + ".prefab", typeof(GameObject), hashes));
            var sound = Asset("9c20a074d7950f646b1ade5b3bd3cd11", "lsdLaserCutter.asset", typeof(RoR2.Audio.LoopSoundDef), hashes);
            assets.Add(sound);
            int enterFields = ApplyAndCheck(configs[0], null);
            Require(enterFields == 3 && Mathf.Approximately(EnterEngiLaserCutter.baseDuration, 0.6f), "Native charge duration/field contract changed");
            CheckReference(EnterEngiLaserCutter.chargeEffectPrefab, "128de1607ef2a3343a5298ebe353d272");
            var phases = new EngiLaserCutter[] { new EngiLaserCutter(), new EngiLaserCutter2(), new EngiLaserCutter3() };
            int[] fieldCounts = new int[3];
            string[] beamGuids = { "0744bfd82b0b0d24a9c627bbc009e212", "7d725d209b464284e884fd498b4ac9df", "813c6a8e9212a254d9f90a6df8b0a71e" };
            for (int i = 0; i < phases.Length; i++)
            {
                fieldCounts[i] = ApplyAndCheck(configs[i + 1], phases[i]);
                Require(fieldCounts[i] == (i == 0 ? 18 : 17) && phases[i].laserCutterSound == sound,
                        "Native beam config field count/sound identity changed");
                CheckReference(phases[i].laserLPrefabVFX, beamGuids[i]);
                CheckReference(phases[i].laserRPrefabVFX, beamGuids[i]);
                CheckReference(phases[i].impactEffectPrefab, "366b4cc19aebc1b428d761fcea6934c0");
            }
            Require(phases[0].damageCoefficient < phases[1].damageCoefficient && phases[1].damageCoefficient < phases[2].damageCoefficient &&
                        phases[0].healCoefficient < phases[1].healCoefficient && phases[1].healCoefficient < phases[2].healCoefficient &&
                        phases[0].maxTurnSpeed > phases[1].maxTurnSpeed && phases[1].maxTurnSpeed > phases[2].maxTurnSpeed &&
                        phases[0].baseMaxDuration == phases[1].baseMaxDuration && phases[2].baseMaxDuration > phases[1].baseMaxDuration,
                    "Native phase escalation contract changed");
            var aim = typeof(EngiLaserCutter).GetField("currentAimVector", BindingFlags.Instance | BindingFlags.NonPublic);
            Require(aim != null, "Native phase aim handoff field missing");
            var direction = new Vector3(0.25f, -0.5f, 0.75f);
            aim.SetValue(phases[0], direction);
            phases[0].fireStopwatch = 0.375f;
            var second = phases[0].GetNextState() as EngiLaserCutter2;
            Require(second != null && second.initialAimVector == direction && second.fireStopwatch == phases[0].fireStopwatch,
                    "Native phase 1->2 lost aim or fire timer");
            aim.SetValue(second, direction);
            second.fireStopwatch = 0.625f;
            var third = second.GetNextState() as EngiLaserCutter3;
            Require(third != null && third.initialAimVector == direction && third.fireStopwatch == 0f && third.GetNextState().GetType() == typeof(Idle),
                    "Native phase 2->3->Idle handoff changed");
            result = new { nativeStaticAndInheritedInstanceConfigVerified = true, enterFields, phaseFieldCounts = fieldCounts,
                           nativePhaseAimAndTimerHandoffVerified = true, staticFieldsRestored = true, sourceAssetsUnchanged = true,
                           stateEntryCatalogRunProfileOrNetworkCreated = false, deviceBeamDamageHealingOrReleaseProven = false };
        }
        catch (Exception error) { failure = error; }
        finally
        {
            foreach (var pair in snapshots)
                try { pair.Key.SetValue(null, pair.Value); }
                catch (Exception error) { if (cleanupFailure == null) cleanupFailure = error; }
            foreach (var pair in snapshots)
                try { Require(ReferenceEquals(pair.Key.GetValue(null), pair.Value) || Equals(pair.Key.GetValue(null), pair.Value), "Static restore failed: " + pair.Key.Name); }
                catch (Exception error) { if (cleanupFailure == null) cleanupFailure = error; }
            foreach (var pair in hashes)
                try { Require(Hash(pair.Key) == pair.Value, "Source asset bytes changed: " + pair.Key); }
                catch (Exception error) { if (cleanupFailure == null) cleanupFailure = error; }
            foreach (var asset in assets)
                try { Require(asset && !EditorUtility.IsDirty(asset), "Source asset became dirty"); }
                catch (Exception error) { if (cleanupFailure == null) cleanupFailure = error; }
        }
        if (failure != null) ExceptionDispatchInfo.Capture(failure).Throw();
        if (cleanupFailure != null) ExceptionDispatchInfo.Capture(cleanupFailure).Throw();
        return result;
    }
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

#if UNITY_EDITOR
namespace MageConfigFixture
{
using System;
using System.Collections.Generic;
using System.Reflection;
using System.Runtime.ExceptionServices;
using EntityStates.Mage.Weapon;
using RoR2;
using RoR2.Projectile;
using UnityEditor;
using UnityEngine;
using UnityEngine.Networking;

public static class MageEarthShardsStaticConfigFixture
{
    const string ConfigGuid = "aa0faf673d02e8a448725ed13b403c88";
    const string ConfigPath = "Assets/WholeGame/RoR2/Base/Characters/Mage/Skills/FireEarthShards/EntityStates.Mage.Weapon.FireEarthShards.asset";
    const string ProjectileGuid = "2c83499e4cf62f54eb25b74fb2e47656";
    const string ProjectilePath = "Assets/WholeGame/RoR2/Base/Characters/Mage/Skills/FireEarthShards/MageEarthShardProjectile.prefab";

    static void Require(bool condition, string message)
    {
        if (!condition)
            throw new InvalidOperationException("Mage Earth Shards static config fixture failed: " + message);
    }

    static bool SameValue(object left, object right)
    {
        if (left is UnityEngine.Object || right is UnityEngine.Object)
            return (left as UnityEngine.Object) == (right as UnityEngine.Object);
        return Equals(left, right);
    }

    public static object Run()
    {
        Require(!EditorApplication.isPlaying && !EditorApplication.isCompiling && !EditorApplication.isUpdating &&
                    !NetworkServer.active && !NetworkClient.active && !RoR2.Run.instance,
                "Require the exact editor idle, with no compilation, Play Mode, network, or Run");

        Require(AssetDatabase.GUIDToAssetPath(ConfigGuid) == ConfigPath &&
                    AssetDatabase.AssetPathToGUID(ConfigPath) == ConfigGuid,
                "Generated source map identity for the native EntityStateConfiguration changed or is ambiguous");
        Require(AssetDatabase.GUIDToAssetPath(ProjectileGuid) == ProjectilePath &&
                    AssetDatabase.AssetPathToGUID(ProjectilePath) == ProjectileGuid,
                "Generated source map identity for the native Earth Shard projectile changed or is ambiguous");

        var config = AssetDatabase.LoadAssetAtPath<EntityStateConfiguration>(ConfigPath);
        var expectedPrefab = AssetDatabase.LoadAssetAtPath<GameObject>(ProjectilePath);
        Require(config && config.name == "EntityStates.Mage.Weapon.FireEarthShards" &&
                    (Type)config.targetType == typeof(FireEarthShards),
                "Exact staged config object or target state type changed");
        Require(expectedPrefab && expectedPrefab.name == "MageEarthShardProjectile" &&
                    AssetDatabase.LoadAssetAtPath<GameObject>(ProjectilePath) == expectedPrefab,
                "Exact staged projectile prefab cannot be loaded at its generated path");

        var serialized = config.serializedFieldsCollection;
        Require(serialized.serializedFields != null && serialized.serializedFields.Length > 0,
                "Native SerializedFieldCollection is missing or empty");

        // Match SpawnStateBoundary's captured-state ownership seam: snapshot every
        // mutable static field on this exact state before applying the native config.
        var fields = typeof(FireEarthShards).GetFields(
            BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Static | BindingFlags.DeclaredOnly);
        var snapshots = new List<KeyValuePair<FieldInfo, object>>();
        foreach (var field in fields)
        {
            if (!field.IsStatic || field.IsLiteral || field.IsInitOnly)
                continue;
            snapshots.Add(new KeyValuePair<FieldInfo, object>(field, field.GetValue(null)));
        }
        Require(snapshots.Count > 0, "No mutable native state fields were captured");

        object result = null;
        Exception fixtureFailure = null;
        Exception restoreFailure = null;
        try
        {
            var serializedNames = new HashSet<string>(StringComparer.Ordinal);
            int seenMaxProjectiles = 0, seenDuration = 0, seenCharge = 0, seenFire = 0, seenProjectile = 0;
            foreach (var serializedField in serialized.serializedFields)
            {
                Require(!string.IsNullOrEmpty(serializedField.fieldName) && serializedNames.Add(serializedField.fieldName),
                        "Serialized field names are empty or duplicated");
                var field = typeof(FireEarthShards).GetField(
                    serializedField.fieldName,
                    BindingFlags.Public | BindingFlags.Static | BindingFlags.DeclaredOnly);
                Require(field != null && !field.IsLiteral && !field.IsInitOnly,
                        "Serialized field is not an exact mutable native static field: " + serializedField.fieldName);
                // The public native ApplyStatic() performs SerializedValue.GetValue
                // against the declared field type. Count required config field names
                // here, then verify their actual native static values after applying.
                switch (serializedField.fieldName)
                {
                    case "maxProjectiles": seenMaxProjectiles++; break;
                    case "baseDuration": seenDuration++; break;
                    case "chargeTime": seenCharge++; break;
                    case "fireTime": seenFire++; break;
                    case "projectilePrefab": seenProjectile++; break;
                }
            }
            Require(seenMaxProjectiles == 1 && seenDuration == 1 && seenCharge == 1 && seenFire == 1 && seenProjectile == 1,
                    "Required native serialized fields are absent or duplicated");

            // EntityStateCatalog.ApplyEntityStateConfiguration calls this native API
            // after verifying that its source EntityState type is registered. Avoid
            // catalog initialization here; this fixture isolates ApplyStatic only.
            // Distinct sentinels make a swallowed native conversion/binding error
            // observable even if an earlier editor fixture left configured values.
            FireEarthShards.maxProjectiles = -410001;
            FireEarthShards.baseDuration = -.25f;
            FireEarthShards.chargeTime = -.5f;
            FireEarthShards.fireTime = -.75f;
            FireEarthShards.projectilePrefab = null;
            config.ApplyStatic();

            var configuredPrefab = FireEarthShards.projectilePrefab;
            var simple = configuredPrefab ? configuredPrefab.GetComponent<ProjectileSimple>() : null;
            Require(FireEarthShards.maxProjectiles == 8 && Mathf.Approximately(FireEarthShards.baseDuration, 0.8f) &&
                        Mathf.Approximately(FireEarthShards.chargeTime, 0.167f) &&
                        Mathf.Approximately(FireEarthShards.fireTime, 0.167f),
                    "Native ApplyStatic did not produce the expected Earth Shards numeric fields");
            Require(configuredPrefab == expectedPrefab &&
                        AssetDatabase.GetAssetPath(configuredPrefab) == ProjectilePath && simple &&
                        Mathf.Approximately(simple.lifetime, 0.3f),
                    "Native ApplyStatic did not bind the exact staged projectile and its serialized lifetime");

            result = new
            {
                configGuid = ConfigGuid,
                configPath = ConfigPath,
                targetType = typeof(FireEarthShards).FullName,
                serializedFieldCount = serialized.serializedFields.Length,
                mutableStaticFieldSnapshotCount = snapshots.Count,
                maxProjectiles = FireEarthShards.maxProjectiles,
                baseDuration = FireEarthShards.baseDuration,
                chargeTime = FireEarthShards.chargeTime,
                fireTime = FireEarthShards.fireTime,
                projectileGuid = ProjectileGuid,
                projectilePath = AssetDatabase.GetAssetPath(configuredPrefab),
                projectileLifetime = simple.lifetime,
                nativeApplyStaticVerified = true,
                staticFieldsRestored = true,
                catalogInitializationRunOrNetworkCreated = false,
                deviceVolleyOrDamageProven = false
            };
        }
        catch (Exception error)
        {
            fixtureFailure = error;
        }
        finally
        {
            // Restore all mutable native state fields, not only serialized config
            // members. Keep the first fixture failure if restoration also fails.
            foreach (var pair in snapshots)
            {
                try
                {
                    pair.Key.SetValue(null, pair.Value);
                }
                catch (Exception error)
                {
                    if (restoreFailure == null)
                        restoreFailure = error;
                }
            }
            foreach (var pair in snapshots)
            {
                try
                {
                    Require(SameValue(pair.Key.GetValue(null), pair.Value),
                            "Native static field was not restored: " + pair.Key.Name);
                }
                catch (Exception error)
                {
                    if (restoreFailure == null)
                        restoreFailure = error;
                }
            }
        }
        if (fixtureFailure != null)
            ExceptionDispatchInfo.Capture(fixtureFailure).Throw();
        if (restoreFailure != null)
            ExceptionDispatchInfo.Capture(restoreFailure).Throw();
        return result;
    }
}
}
#endif

#if UNITY_EDITOR
namespace NativeShrineOperationFixture
{
using System.Linq;
using UnityEditor;
// Authored exact-editor fixture. It uses only a temporary local Addressables
// locator/provider and a new GameObject; it does not load game assets or mutate
// the user's configured locators after TearDown.
using System;
using System.Collections.Generic;
using System.Reflection;
using System.Runtime.Serialization;
using RoR2;
using UnityEngine;
using UnityEngine.AddressableAssets;
using UnityEngine.AddressableAssets.ResourceLocators;
using UnityEngine.ResourceManagement;
using UnityEngine.ResourceManagement.AsyncOperations;
using UnityEngine.ResourceManagement.ResourceLocations;
using UnityEngine.ResourceManagement.ResourceProviders;

public static class NativeShrineOperationSnapshotEditorFixture
{
    const string FixtureKey = "native-shrine-operation-witness-fixture-key";
    const string FixtureGuid = "0123456789abcdef0123456789abcdef";

    public static object Run()
    {
        if (EditorApplication.isPlayingOrWillChangePlaymode || EditorApplication.isCompiling ||
            UnityEngine.Networking.NetworkServer.active || UnityEngine.Networking.NetworkClient.active)
            throw new InvalidOperationException("Operation fixture requires an idle editor without a network session");
        var manager = Addressables.ResourceManager;
        var providers = manager.ResourceProviders.ToArray();
        var locators = Addressables.ResourceLocators.ToArray();
        var providerMap = ReadProviderMap(manager).ToArray();
        var observations = new List<string>();
        for (int iteration = 0; iteration < 2; iteration++)
        {
            observations.Add(Verify());
            if (!providers.SequenceEqual(manager.ResourceProviders) ||
                !locators.SequenceEqual(Addressables.ResourceLocators))
                throw new InvalidOperationException("Fixture changed the existing provider or locator membership/order");
            var current = ReadProviderMap(manager);
            if (current.Count != providerMap.Length || providerMap.Any(entry =>
                !current.ContainsKey(entry.Key) || !ReferenceEquals(current[entry.Key], entry.Value)))
                throw new InvalidOperationException("Fixture retained or replaced a provider cache entry");
        }
        return new { authoredOperationObservations = observations,
                     repeatedSetupTeardown = true, existingProvidersAndLocatorsPreserved = true,
                     existingProviderCachePreserved = true, gameAssetsOrNativeRunUsed = false };
    }

    public static string Verify()
    {
        var effect = new GameObject("NativeShrineOperationSnapshotFixtureEffect");
        var provider = new FixtureGameObjectProvider(effect);
        provider.Initialize("NativeShrineOperationSnapshotFixtureProvider", string.Empty);
        var locator = new FixtureLocator(provider.ProviderId);
        AsyncOperationHandle<GameObject> lease = default(AsyncOperationHandle<GameObject>);
        AsyncOperationHandle<GameObject> second = default(AsyncOperationHandle<GameObject>);
        bool providerAdded = false, locatorAdded = false;
        IDictionary<int, IResourceProvider> providerMap = null;
        int providerCacheKey = 0;
        try
        {
            providerMap = ReadProviderMap(Addressables.ResourceManager);
            providerCacheKey = provider.ProviderId.GetHashCode() * 31 + typeof(GameObject).GetHashCode();
            if (providerMap.ContainsKey(providerCacheKey))
                throw new InvalidOperationException("Refusing fixture provider cache key already owned by another provider");
            Addressables.ResourceManager.ResourceProviders.Add(provider);
            providerAdded = true;
            Addressables.AddResourceLocator(locator);
            locatorAdded = true;

            lease = Addressables.ResourceManager.ProvideResource<GameObject>(locator.Location);
            if (lease.WaitForCompletion() != effect || !lease.IsValid())
                throw new InvalidOperationException("Authored provider did not complete the local GameObject operation");
            if (!lease.IsDone || lease.Status != AsyncOperationStatus.Succeeded || lease.Result != effect)
                throw new InvalidOperationException("Local authored operation did not finish successfully with the supplied object");
            int beforeObserver = ReferenceCount(lease);
            var snapshotType = typeof(PortSession).Assembly.GetType("NativeShrineEffectOperationSnapshot", true);
            var flags = BindingFlags.Static | BindingFlags.NonPublic;
            var baselineMethod = snapshotType.GetMethod("CaptureBaseline", flags);
            object[] baselineArgs = { lease, FixtureGuid, FixtureGuid, null };
            object baseline = baselineMethod.Invoke(null, baselineArgs);
            string baselineError = Convert.ToString(baselineArgs[3]);
            if (baseline is System.Collections.ICollection entries && entries.Count == 0)
                throw new InvalidOperationException("The authored ResourceManager cache did not expose its matching operation");
            if (!string.IsNullOrEmpty(baselineError))
                throw new InvalidOperationException("The authored cache baseline reported an error: " + baselineError);

            // A second ProvideResource uses the same key and must share the
            // cached operation. This tests the production comparison path with
            // a real cached handle, without involving game locators or effects.
            second = Addressables.ResourceManager.ProvideResource<GameObject>(locator.Location);
            if (second.WaitForCompletion() != effect)
                throw new InvalidOperationException("The second local operation did not return the authored object");
            int beforeCapture = ReferenceCount(lease);
            var captureMethod = snapshotType.GetMethod("Capture", flags);
            object[] captureArgs = { lease, effect, FixtureGuid, FixtureGuid, -1, "authored-editor-fixture", baseline, baselineError };
            string row = Convert.ToString(captureMethod.Invoke(null, captureArgs));
            int afterCapture = ReferenceCount(lease);
            if (beforeCapture != afterCapture || afterCapture <= beforeObserver)
                throw new InvalidOperationException("Observer mutated the lease count or fixture failed to add a shared cache reference");
            int entriesStart = row.IndexOf("entries=[", StringComparison.Ordinal);
            int entriesEnd = entriesStart < 0 ? -1 : row.IndexOf("]", entriesStart, StringComparison.Ordinal);
            string operationRows = entriesStart < 0 || entriesEnd < 0 ? string.Empty : row.Substring(entriesStart + 9, entriesEnd - entriesStart - 9);
            bool sameOperationEvidence = false;
            foreach (var operationRow in operationRows.Split('|'))
            {
                if (operationRow.IndexOf("owned=True", StringComparison.Ordinal) >= 0 &&
                    operationRow.IndexOf("prior=True", StringComparison.Ordinal) >= 0 &&
                    operationRow.IndexOf("beforeRc=" + beforeObserver, StringComparison.Ordinal) >= 0 &&
                    operationRow.IndexOf("afterRc=" + beforeCapture, StringComparison.Ordinal) >= 0 &&
                    operationRow.IndexOf("delta=" + (beforeCapture - beforeObserver), StringComparison.Ordinal) >= 0 &&
                    operationRow.IndexOf("resultOwned=True", StringComparison.Ordinal) >= 0)
                    sameOperationEvidence = true;
            }
            if (row.IndexOf("leaseValid=True", StringComparison.Ordinal) < 0 ||
                row.IndexOf("supportIndex=-1", StringComparison.Ordinal) < 0 ||
                row.IndexOf("effectCatalogIndex=", StringComparison.Ordinal) < 0 ||
                row.IndexOf("cacheUnavailable=true", StringComparison.Ordinal) >= 0 || !sameOperationEvidence)
                throw new InvalidOperationException("Snapshot did not identify one owned, prior cached operation and its result/count facts: " + row);

            object[] missingArgs = { lease, effect, "fedcba9876543210fedcba9876543210", "fedcba9876543210fedcba9876543210",
                                     -1, "authored-editor-missing-key", null, "" };
            string missingRow = Convert.ToString(captureMethod.Invoke(null, missingArgs));
            if (missingRow.IndexOf("cacheMatches=0", StringComparison.Ordinal) < 0 ||
                missingRow.IndexOf("candidateLocations=0", StringComparison.Ordinal) < 0)
                throw new InvalidOperationException("Missing-key observation did not report an empty bounded match set: " + missingRow);

            // Exercise the actual session wrapper's catch boundary with an
            // intentionally incomplete, uninitialized coordinator. It must
            // return a diagnostic string without escaping the observer fault.
            var coordinator = (PortSession)FormatterServices.GetUninitializedObject(typeof(PortSession));
            typeof(PortSession).GetField("r", BindingFlags.Instance | BindingFlags.NonPublic)
                .SetValue(coordinator, new PortSession.SessionReport());
            var sessionType = typeof(PortSession).GetNestedType("WorldCommerceSession", BindingFlags.NonPublic);
            var session = Activator.CreateInstance(sessionType, BindingFlags.Instance | BindingFlags.Public,
                                                   null, new object[] { coordinator }, null);
            var wrapper = sessionType.GetMethod("CaptureNativeShrineEffectOperationWitness", BindingFlags.Instance | BindingFlags.NonPublic);
            string inertFailure = Convert.ToString(wrapper.Invoke(session, new object[] { "authored-invalid-coordinator" }));
            if (inertFailure.IndexOf("captureError=", StringComparison.Ordinal) < 0)
                throw new InvalidOperationException("Session observer did not contain the intentionally invalid capture state");
            return row + "\nmissing=" + missingRow + "\ninert=" + inertFailure;
        }
        finally
        {
            if (second.IsValid()) Addressables.Release(second);
            if (lease.IsValid()) Addressables.Release(lease);
            if (locatorAdded) Addressables.RemoveResourceLocator(locator);
            if (providerAdded) Addressables.ResourceManager.ResourceProviders.Remove(provider);
            if (providerMap != null)
            {
                IResourceProvider cached;
                if (providerMap.TryGetValue(providerCacheKey, out cached) && ReferenceEquals(cached, provider))
                    providerMap.Remove(providerCacheKey);
            }
            UnityEngine.Object.DestroyImmediate(effect);
        }
    }

    sealed class FixtureGameObjectProvider : ResourceProviderBase
    {
        readonly GameObject result;
        internal FixtureGameObjectProvider(GameObject result) { this.result = result; }
        public override Type GetDefaultType(IResourceLocation location) { return typeof(GameObject); }
        public override void Provide(ProvideHandle handle) { handle.Complete(result, true, null); }
    }

    sealed class FixtureLocator : IResourceLocator
    {
        readonly IResourceLocation location;
        internal readonly IResourceLocation Location;
        internal FixtureLocator(string providerId)
        {
            Location = new ResourceLocationBase(FixtureKey, FixtureGuid, providerId, typeof(GameObject));
            location = Location;
        }
        public string LocatorId { get { return "NativeShrineOperationSnapshotFixture"; } }
        public IEnumerable<object> Keys { get { yield return FixtureGuid; } }
        public bool Locate(object key, Type type, out IList<IResourceLocation> locations)
        {
            if (Equals(key, FixtureGuid) && (type == null || type == typeof(GameObject)))
            {
                locations = new List<IResourceLocation> { location };
                return true;
            }
            locations = null;
            return false;
        }
    }

    static IDictionary<int, IResourceProvider> ReadProviderMap(ResourceManager manager)
    {
        var field = typeof(ResourceManager).GetField("m_providerMap", BindingFlags.Instance | BindingFlags.NonPublic);
        var map = field == null ? null : field.GetValue(manager) as IDictionary<int, IResourceProvider>;
        if (map == null) throw new InvalidOperationException("Pinned ResourceManager provider map is unavailable");
        return map;
    }

    static int ReferenceCount(AsyncOperationHandle<GameObject> handle)
    {
        var property = typeof(AsyncOperationHandle<GameObject>).GetProperty("ReferenceCount", BindingFlags.Instance | BindingFlags.NonPublic);
        return Convert.ToInt32(property.GetValue(handle, null));
    }
}

}
#endif
