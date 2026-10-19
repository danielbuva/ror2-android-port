#if UNITY_EDITOR
using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using Path = System.IO.Path;
using System.Linq;
using System.Reflection;
using System.Runtime.Serialization;
using System.Runtime.ExceptionServices;
using RoR2;
using RoR2.Projectile;
using UnityEditor;
using UnityEngine;
using UnityEngine.AddressableAssets;
using UnityEngine.AddressableAssets.Initialization;
using UnityEngine.AddressableAssets.ResourceLocators;
using UnityEngine.AddressableAssets.ResourceProviders;
using UnityEngine.Networking;
using UnityEngine.ResourceManagement;
using UnityEngine.ResourceManagement.AsyncOperations;
using UnityEngine.ResourceManagement.ResourceLocations;
using UnityEngine.ResourceManagement.ResourceProviders;

// Support exact-editor contract. Invokes the actual authored owner and native
// EffectCatalog.SetEntries against a temporary local provider for the staged
// baked catalog. It does not save or alter any asset.
public static class MercEvisImpactEffectExactEditorFixture
{
    const string EvisPath = "Assets/WholeGame/RoR2/Base/Characters/Merc/Skills/EvisProjectile.prefab";
    const string SwingPath = "Assets/WholeGame/RoR2/Base/Characters/Merc/MercSwordFinisherSlash.prefab";
    const string BakedCatalogPath = "Assets/WholeGame/RoR2/Catalog/BakedEffectsCatalog.asset";
    // Exact native key in accepted e544 EffectCatalog.SetEntries; the staged
    // converted asset's Unity GUID may differ from this Addressables key.
    const string BakedCatalogKey = "a234c23838a4396429025d637ffa6154";
    const string GroundLightConfigPath = "Assets/WholeGame/RoR2/Base/Characters/Merc/Skills/EntityStates.Merc.Weapon.GroundLight2.asset";

    static void Require(bool condition, string message)
    {
        if (!condition) throw new InvalidOperationException(message);
    }

    static IResourceLocator fixtureInitializedLocator;

    static IResourceLocator InitializeAndValidateAddressables()
    {
        var existingLocators = Addressables.ResourceLocators.ToArray();
        var existingBootstrap = existingLocators.FirstOrDefault(locator => ReferenceEquals(locator, fixtureInitializedLocator));
        Require(existingLocators.Length == 0 || (existingLocators.Length == 1 && existingBootstrap != null),
                "Addressables has unowned locators; refusing uncertain initialization state");

        var priorTransform = Addressables.InternalIdTransformFunc;
        string settingsPath = null;
        if (existingBootstrap == null)
        {
            // This Editor project has no built Addressables runtime settings file.
            // Use the real public initialization pipeline with a valid empty
            // catalog. Keep these authored test files in ignored work because
            // the registered content locator retains their paths.
            var fixtureDirectory = Path.GetFullPath(Path.Combine(Application.dataPath, "..", "..", "..", "work",
                "tests", "merc-evis-impact-effect", "addressables-init"));
            var catalogPath = Path.Combine(fixtureDirectory, "catalog.json");
            settingsPath = Path.Combine(fixtureDirectory, "settings.json");
            const string catalogJson = "{\"m_LocatorId\":\"merc-evis-fixture\",\"m_ProviderIds\":[],\"m_InternalIds\":[],\"m_KeyDataString\":\"AAAAAA==\",\"m_BucketDataString\":\"AAAAAA==\",\"m_EntryDataString\":\"AAAAAA==\",\"m_ExtraDataString\":\"\",\"m_resourceTypes\":[]}";
            var runtimeData = new ResourceManagerRuntimeData
            {
                BuildTarget = "Android",
                DisableCatalogUpdateOnStartup = true,
                LogResourceManagerExceptions = true
            };
            runtimeData.CatalogLocations.Add(new ResourceLocationData(
                new[] { ResourceManagerRuntimeData.kCatalogAddress }, catalogPath,
                typeof(ContentCatalogProvider), typeof(ContentCatalogData)));
            var settingsJson = JsonUtility.ToJson(runtimeData);
            if (!Directory.Exists(fixtureDirectory))
            {
                Directory.CreateDirectory(fixtureDirectory);
                File.WriteAllText(catalogPath, catalogJson);
                File.WriteAllText(settingsPath, settingsJson);
            }
            else
                Require(File.Exists(catalogPath) && File.Exists(settingsPath) &&
                            File.ReadAllText(catalogPath) == catalogJson && File.ReadAllText(settingsPath) == settingsJson,
                        "Fixture Addressables initialization files already exist with different contents");
        }
        IResourceLocator initializedLocator = null;
        RunWithCleanup(() =>
        {
            if (settingsPath != null)
            {
                var expectedSettingsPath = Addressables.RuntimePath + "/settings.json";
                Addressables.InternalIdTransformFunc = location =>
                    location.InternalId == expectedSettingsPath ? settingsPath : location.InternalId;
            }

            // Always exercise the public no-argument initialization operation,
            // including when the fixture content locator was already present. A
            // locator alone does not prove public initialization succeeded.
            var initialization = Addressables.InitializeAsync();
            Addressables.ResourceManager.Acquire(initialization);
            try
            {
                initializedLocator = initialization.WaitForCompletion();
                Require(initialization.IsDone && initialization.Status == AsyncOperationStatus.Succeeded &&
                            initializedLocator != null &&
                            Addressables.ResourceLocators.Contains(initializedLocator),
                        "Public Addressables initialization did not return a successful registered locator. " +
                        "done=" + initialization.IsDone + ", status=" + initialization.Status +
                        ", result=" + (initializedLocator == null ? "<null>" : initializedLocator.LocatorId) +
                        ", resultRegistered=" + (initializedLocator != null && Addressables.ResourceLocators.Contains(initializedLocator)) +
                        ", operationException=" + initialization.OperationException);
            }
            finally
            {
                if (initialization.IsValid())
                    Addressables.Release(initialization);
            }
        },
        () => true,
        () =>
        {
            Addressables.InternalIdTransformFunc = priorTransform;
        },
        "Addressables fixture initialization");
        fixtureInitializedLocator = initializedLocator;
        return initializedLocator;
    }

    static void RunWithCleanup(Action action, Func<bool> shouldCleanup, Action cleanup, string label)
    {
        Exception actionFailure = null;
        Exception cleanupFailure = null;
        try { action(); }
        catch (Exception error) { actionFailure = error; }
        finally
        {
            bool cleanupRequired = false;
            try { cleanupRequired = shouldCleanup(); }
            catch (Exception error) { cleanupFailure = error; }
            if (cleanupFailure == null && cleanupRequired)
            {
                try { cleanup(); }
                catch (Exception error) { cleanupFailure = error; }
            }
        }
        if (actionFailure != null && cleanupFailure != null)
            throw new AggregateException(label + " failed and owned-state cleanup also failed", actionFailure, cleanupFailure);
        if (actionFailure != null)
            ExceptionDispatchInfo.Capture(actionFailure).Throw();
        if (cleanupFailure != null)
            ExceptionDispatchInfo.Capture(cleanupFailure).Throw();
    }

    public static object Run()
    {
        Require(!EditorApplication.isPlayingOrWillChangePlaymode && !EditorApplication.isCompiling &&
                    !EditorApplication.isUpdating && !NetworkServer.active && !NetworkClient.active,
                "Fixture requires idle Edit Mode and no native network session");
        InitializeAndValidateAddressables();
        var swing = AssetDatabase.LoadAssetAtPath<GameObject>(SwingPath);
        var evis = AssetDatabase.LoadAssetAtPath<GameObject>(EvisPath);
        var bakedCatalog = AssetDatabase.LoadAssetAtPath<RoR2.ContentManagement.BakedEffectsCatalog>(BakedCatalogPath);
        var groundLight = AssetDatabase.LoadAssetAtPath<EntityStateConfiguration>(GroundLightConfigPath);
        Require(swing && evis && bakedCatalog && groundLight, "Exact accepted Merc staged assets are missing");
        var impact = evis.GetComponents<ProjectileImpactExplosion>();
        var sourceVfx = swing.GetComponent<VFXAttributes>();
        var sourceTimer = swing.GetComponent<DestroyOnTimer>();
        Require(impact.Length == 1 && impact[0].impactEffect == swing && !impact[0].explosionEffect &&
                    !impact[0].blastImpactEffect, "Accepted Evis impact field contract changed");
        Require(!swing.GetComponent<EffectComponent>() && sourceVfx && !sourceVfx.DoNotPool && sourceTimer &&
                    Mathf.Abs(sourceTimer.duration - 1f) < 0.0001f && swing.GetComponent<ShakeEmitter>() &&
                    swing.GetComponent<ScaleParticleSystemDuration>(), "Accepted source visual component/lifetime contract changed");
        Require((Type)groundLight.targetType == typeof(EntityStates.Merc.Weapon.GroundLight2),
                "GroundLight2 target identity changed");
        var serialized = groundLight.serializedFieldsCollection.serializedFields.Where(x => x.fieldName == "comboFinisherSwingEffectPrefab").ToArray();
        Require(serialized.Length == 1 && serialized[0].fieldValue.stringValue == "add2601728367ff4ea7af75a73953373",
                "GroundLight2 shared swing visual preload changed");

        var entriesField = typeof(EffectCatalog).GetField("entries", BindingFlags.NonPublic | BindingFlags.Static);
        var mapField = typeof(EffectCatalog).GetField("nameToEffectIndex", BindingFlags.NonPublic | BindingFlags.Static);
        Require(entriesField != null && mapField != null, "Pinned EffectCatalog fields unavailable");
        var manager = Addressables.ResourceManager;
        var originalProviders = manager.ResourceProviders.ToArray();
        var originalLocators = Addressables.ResourceLocators.ToArray();
        var providerMap = ReadProviderMap(manager);
        var originalProviderMap = providerMap.ToDictionary(pair => pair.Key, pair => pair.Value);
        var priorEntries = (EffectDef[])entriesField.GetValue(null);
        var nameMap = (IDictionary)mapField.GetValue(null);
        var priorNameMap = new Dictionary<string, EffectIndex>();
        foreach (DictionaryEntry entry in nameMap)
            priorNameMap.Add((string)entry.Key, (EffectIndex)entry.Value);
        var priorAvailability = EffectCatalog.availability;
        Require(priorEntries.Length == 0 && priorNameMap.Count == 0 && !priorAvailability.available,
                "Fixture refuses an already-owned EffectCatalog");

        var provider = new FixtureBakedCatalogProvider();
        provider.Initialize("MercEvisBakedCatalogFixtureProvider", string.Empty);
        var locator = new FixtureBakedCatalogLocator(provider.ProviderId);
        var providerAdded = false;
        var locatorAdded = false;
        int providerMapKey = provider.ProviderId.GetHashCode() * 31 + typeof(RoR2.ContentManagement.BakedEffectsCatalog).GetHashCode();
        try
        {
            if (providerMap.ContainsKey(providerMapKey))
                throw new InvalidOperationException("Fixture refuses an already-owned provider cache key");
            manager.ResourceProviders.Add(provider);
            providerAdded = true;
            Addressables.AddResourceLocator(locator);
            locatorAdded = true;

            var coordinator = (PortSession)FormatterServices.GetUninitializedObject(typeof(PortSession));
            typeof(PortSession).GetField("r", BindingFlags.Instance | BindingFlags.NonPublic)
                .SetValue(coordinator, new PortSession.SessionReport());
            var sessionType = typeof(PortSession).GetNestedType("BodyCatalogSession", BindingFlags.NonPublic);
            var session = Activator.CreateInstance(sessionType, BindingFlags.Instance | BindingFlags.Public,
                                                   null, new object[] { coordinator }, null);
            var initialize = sessionType.GetMethod("InitializeMercEvisAdapterFixture", BindingFlags.Instance | BindingFlags.Public);
            var initializeDefault = sessionType.GetMethod("InitializeComposedEffectsFixture", BindingFlags.Instance | BindingFlags.Public);
            var lastOwnedObjects = sessionType.GetMethod("MercEvisFixtureLastOwnedObjects", BindingFlags.Instance | BindingFlags.Public);
            var restore = sessionType.GetMethod("RestoreComposedEffects", BindingFlags.Instance | BindingFlags.Public);
            Require(initialize != null && initializeDefault != null && lastOwnedObjects != null && restore != null,
                    "Authored effect owner fixture seam unavailable");

            // Generation one: actual owner registration, lookup, field binding,
            // and complete normal teardown. The second SetEntries is a new
            // generation after every catalog value and owner lease was restored.
            EffectDef firstAdded = null;
            GameObject[] generationOneObjects = null;
            bool generationOneInitialized = false;
            RunWithCleanup(() =>
            {
                var requestCountBefore = provider.NativeCatalogRequests;
                initialize.Invoke(session, new object[] { swing, evis, Array.Empty<EffectDef>(), null });
                generationOneInitialized = true;
                Require(provider.NativeCatalogRequests == requestCountBefore + 1,
                        "First native catalog generation did not issue exactly one canonical provider request");
                var bound = impact[0].impactEffect;
                Require(bound && bound != swing && bound.name == "MercSwordFinisherSlash_PortEvisImpact",
                        "Authored owner did not bind the exact Evis field to its owned clone");
                generationOneObjects = (GameObject[])lastOwnedObjects.Invoke(session, null);
                Require(generationOneObjects.Length == 2 && generationOneObjects[0] == bound &&
                            generationOneObjects[1] == bound.transform.parent.gameObject,
                        "Fixture did not capture exact owned clone and temporary owner references");
                var registeredIndex = EffectCatalog.FindEffectIndexFromPrefab(bound);
                Require(registeredIndex != EffectIndex.Invalid, "Native SetEntries did not assign the cloned visual an effect index");
                firstAdded = EffectCatalog.GetEffectDef(registeredIndex);
                Require(firstAdded != null && firstAdded.prefab == bound && firstAdded.index == registeredIndex &&
                            firstAdded.prefabEffectComponent == bound.GetComponent<EffectComponent>() && !firstAdded.shouldPool &&
                            !firstAdded.prefabEffectComponent.applyScale && string.IsNullOrEmpty(firstAdded.spawnSoundEventName),
                        "Native SetEntries did not register the owner-created clone contract");
                var markerType = sessionType.GetNestedType("MercEvisEffectInstanceMarker", BindingFlags.NonPublic);
                Require(markerType != null && bound.GetComponent(markerType), "Owned effect instance marker missing");
                Require(!sourceVfx.DoNotPool && !swing.GetComponent<EffectComponent>() && impact[0].impactEffect == bound,
                        "Setup changed the shared source visual instead of only Evis impactEffect");
                var retainedEntries = (EffectDef[])entriesField.GetValue(null);
                var retainedMap = (IDictionary)mapField.GetValue(null);
                var retainedAvailability = EffectCatalog.availability;
                var liveProjectile = new GameObject("MercEvisFixtureLiveProjectile");
                try
                {
                    liveProjectile.AddComponent<ProjectileImpactExplosion>().impactEffect = bound;
                    bool cleanupRefused = false;
                    try { restore.Invoke(session, new object[] { priorEntries }); }
                    catch (TargetInvocationException) { cleanupRefused = true; }
                    Require(cleanupRefused && impact[0].impactEffect == bound &&
                                ReferenceEquals(entriesField.GetValue(null), retainedEntries) &&
                                ReferenceEquals(mapField.GetValue(null), retainedMap) &&
                                EffectCatalog.availability.Equals(retainedAvailability) &&
                                bound && bound.transform.parent && firstAdded.prefab == bound,
                            "Cleanup did not retain adapter/catalog while a live projectile referenced its clone");
                }
                finally { UnityEngine.Object.DestroyImmediate(liveProjectile); }
            },
            () => generationOneInitialized || !ReferenceEquals(entriesField.GetValue(null), priorEntries) ||
                  ((GameObject[])lastOwnedObjects.Invoke(session, null)).Any(value => value),
            () => { restore.Invoke(session, new object[] { priorEntries }); },
            "Merc adapter generation one");
            Require(impact[0].impactEffect == swing && ReferenceEquals(entriesField.GetValue(null), priorEntries) &&
                        SameNameMap((IDictionary)mapField.GetValue(null), priorNameMap) &&
                        EffectCatalog.availability.Equals(priorAvailability) &&
                        firstAdded.index == EffectIndex.Invalid && !generationOneObjects[0] && !generationOneObjects[1],
                    "Normal owner cleanup did not restore the original catalog and binding");

            // Generation two: force the existing RegisterComposedEffects path to
            // fail after one valid replacement was assigned, then verify that
            // the actual setup catch restores every owned native state.
            var validReplacementPrefab = MakeTestEffectPrefab("MercEvisFixtureValidReplacement");
            var unbakedPrefab = MakeTestEffectPrefab("MercEvisFixtureUnbakedReplacement");
            var validReplacement = new EffectDef(validReplacementPrefab);
            var unbakedReplacement = new EffectDef(unbakedPrefab);
            try
            {
                bool generationTwoInitialized = false;
                RunWithCleanup(() =>
                {
                    var requestCountBefore = provider.NativeCatalogRequests;
                    bool setupFailed = false;
                    try
                    {
                    initialize.Invoke(session, new object[] { swing, evis,
                        new[] { validReplacement, unbakedReplacement }, new[] { validReplacement } });
                        generationTwoInitialized = true;
                    }
                    catch (TargetInvocationException) { setupFailed = true; }
                    var failedGenerationObjects = (GameObject[])lastOwnedObjects.Invoke(session, null);
                    Require(setupFailed, "Expected unbaked second replacement to exercise setup rollback");
                    Require(provider.NativeCatalogRequests == requestCountBefore + 1,
                        "Second native catalog generation did not issue exactly one canonical provider request");
                    Require(impact[0].impactEffect == swing && ReferenceEquals(entriesField.GetValue(null), priorEntries) &&
                            SameNameMap((IDictionary)mapField.GetValue(null), priorNameMap) &&
                            EffectCatalog.availability.Equals(priorAvailability) &&
                            validReplacement.index == EffectIndex.Invalid &&
                            validReplacement.prefabEffectComponent.effectIndex == EffectIndex.Invalid &&
                            validReplacement.spawnSoundEventName == "MercEvisFixtureSound" &&
                            unbakedReplacement.index == EffectIndex.Invalid &&
                            unbakedReplacement.prefabEffectComponent.effectIndex == EffectIndex.Invalid &&
                            failedGenerationObjects.Length == 2 && !failedGenerationObjects[0] && !failedGenerationObjects[1] &&
                            !sourceVfx.DoNotPool && !swing.GetComponent<EffectComponent>(),
                        "Setup failure did not restore target, indices, catalog map, availability, and owned-object retirement");
                },
                () => generationTwoInitialized || !ReferenceEquals(entriesField.GetValue(null), priorEntries) ||
                      ((GameObject[])lastOwnedObjects.Invoke(session, null)).Any(value => value),
                () => { restore.Invoke(session, new object[] { priorEntries }); },
                "Merc adapter generation two");
            }
            finally
            {
                UnityEngine.Object.DestroyImmediate(validReplacementPrefab);
                UnityEngine.Object.DestroyImmediate(unbakedPrefab);
            }
            Require(provider.NativeCatalogRequests == 2,
                    "Fixture did not prove both native catalog generations used the exact baked-catalog provider");

            // Generation three exercises the default non-Merc setup rollback.
            // Native SetEntries appends the valid replacement; registration then
            // succeeds for it and fails on the deliberately unbaked second row.
            var defaultValidPrefab = MakeTestEffectPrefab("MercEvisFixtureDefaultValid");
            var defaultUnbakedPrefab = MakeTestEffectPrefab("MercEvisFixtureDefaultUnbaked");
            var defaultValid = new EffectDef(defaultValidPrefab);
            var defaultUnbaked = new EffectDef(defaultUnbakedPrefab);
            var savedDefinitionIndex = (EffectIndex)321;
            var savedComponentIndex = (EffectIndex)322;
            typeof(EffectDef).GetProperty("index").SetValue(defaultValid, savedDefinitionIndex, null);
            defaultValid.prefabEffectComponent.effectIndex = savedComponentIndex;
            typeof(EffectDef).GetProperty("spawnSoundEventName").SetValue(defaultValid, "MercEvisFixtureDefaultSound", null);
            try
            {
                bool generationThreeInitialized = false;
                RunWithCleanup(() =>
                {
                    var requestCountBefore = provider.NativeCatalogRequests;
                    bool setupFailed = false;
                    try
                    {
                        initializeDefault.Invoke(session, new object[] {
                            new[] { defaultValid, defaultUnbaked }, new[] { defaultValid }
                        });
                        generationThreeInitialized = true;
                    }
                    catch (TargetInvocationException) { setupFailed = true; }
                    Require(setupFailed && provider.NativeCatalogRequests == requestCountBefore + 1,
                            "Default-path failure did not reach the exact native catalog and later registration failure");
                    Require(ReferenceEquals(entriesField.GetValue(null), priorEntries) &&
                            SameNameMap((IDictionary)mapField.GetValue(null), priorNameMap) &&
                            EffectCatalog.availability.Equals(priorAvailability) &&
                            defaultValid.index == savedDefinitionIndex &&
                            defaultValid.prefabEffectComponent.effectIndex == savedComponentIndex &&
                            defaultValid.spawnSoundEventName == "MercEvisFixtureDefaultSound" &&
                            defaultUnbaked.index == EffectIndex.Invalid &&
                            defaultUnbaked.prefabEffectComponent.effectIndex == EffectIndex.Invalid,
                        "Default-path rollback did not restore each exact prior definition/component index and sound");
                },
                () => generationThreeInitialized || !ReferenceEquals(entriesField.GetValue(null), priorEntries),
                () => { restore.Invoke(session, new object[] { priorEntries }); },
                "Non-Merc generation three");
            }
            finally
            {
                UnityEngine.Object.DestroyImmediate(defaultValidPrefab);
                UnityEngine.Object.DestroyImmediate(defaultUnbakedPrefab);
            }
            Require(provider.NativeCatalogRequests == 3,
                    "Fixture did not prove the default-path generation used the exact baked-catalog provider");
        }
        finally
        {
            if (locatorAdded) Addressables.RemoveResourceLocator(locator);
            if (providerAdded) manager.ResourceProviders.Remove(provider);
            IResourceProvider cached;
            if (providerMap.TryGetValue(providerMapKey, out cached) && ReferenceEquals(cached, provider))
                providerMap.Remove(providerMapKey);
        }
        Require(originalProviders.SequenceEqual(manager.ResourceProviders) && originalLocators.SequenceEqual(Addressables.ResourceLocators),
                "Fixture changed existing Addressables providers or locators");
        Require(providerMap.Count == originalProviderMap.Count && originalProviderMap.All(pair =>
                    providerMap.ContainsKey(pair.Key) && ReferenceEquals(providerMap[pair.Key], pair.Value)),
                "Fixture did not restore provider-cache membership exactly");
        Require(impact[0].impactEffect == swing && !sourceVfx.DoNotPool && !swing.GetComponent<EffectComponent>(),
                "Fixture left a source asset mutation");
        return new {
            actualAuthoredOwnerExecuted = true,
            nativeEffectCatalogSetEntriesExecuted = true,
            threeFullyRestoredCatalogGenerations = true,
            nativePrefabToIndexRoundTrip = true,
            evisOnlyFieldRestored = true,
            failureAfterValidReplacementRestoredIndicesAndCatalog = true,
            defaultPathFailureRestoredExactPriorDefinitionAndComponentIndices = true,
            cleanupRefusedWhileLiveProjectileReferencedClone = true,
            bakedProviderLocatorAndCacheRestored = true,
            sharedGroundLightSourceUntouched = true,
            exactOneSecondDestroyOnTimer = true,
            devicePresentationProven = false
        };
    }

    static GameObject MakeTestEffectPrefab(string name)
    {
        var value = new GameObject(name);
        value.AddComponent<VFXAttributes>().DoNotPool = true;
        value.AddComponent<EffectComponent>().soundName = "MercEvisFixtureSound";
        return value;
    }

    static bool SameNameMap(IDictionary actual, IDictionary<string, EffectIndex> expected)
    {
        if (actual == null || actual.Count != expected.Count) return false;
        foreach (var pair in expected)
            if (!actual.Contains(pair.Key) || !Equals(actual[pair.Key], pair.Value)) return false;
        return true;
    }

    static IDictionary<int, IResourceProvider> ReadProviderMap(ResourceManager manager)
    {
        var field = typeof(ResourceManager).GetField("m_providerMap", BindingFlags.Instance | BindingFlags.NonPublic);
        var map = field == null ? null : field.GetValue(manager) as IDictionary<int, IResourceProvider>;
        if (map == null) throw new InvalidOperationException("Pinned ResourceManager provider map unavailable");
        return map;
    }

    sealed class FixtureBakedCatalogProvider : ResourceProviderBase
    {
        public int NativeCatalogRequests { get; private set; }
        public override Type GetDefaultType(IResourceLocation location) { return typeof(RoR2.ContentManagement.BakedEffectsCatalog); }
        public override void Provide(ProvideHandle handle)
        {
            try
            {
                if (handle.Location.PrimaryKey != BakedCatalogKey || handle.Location.InternalId != BakedCatalogPath ||
                    handle.Type != typeof(RoR2.ContentManagement.BakedEffectsCatalog))
                    throw new InvalidOperationException("Fixture provider refused a noncanonical native catalog request");
                NativeCatalogRequests++;
                var asset = AssetDatabase.LoadAssetAtPath(handle.Location.InternalId, handle.Type);
                if (!asset) throw new InvalidOperationException("Staged baked effects catalog missing at exact internal id");
                handle.Complete<UnityEngine.Object>(asset, true, null);
            }
            catch (Exception error) { handle.Complete<UnityEngine.Object>(null, false, error); }
        }
    }

    sealed class FixtureBakedCatalogLocator : IResourceLocator
    {
        readonly IResourceLocation location;
        public FixtureBakedCatalogLocator(string providerId)
        {
            location = new ResourceLocationBase(BakedCatalogKey, BakedCatalogPath, providerId,
                                                typeof(RoR2.ContentManagement.BakedEffectsCatalog));
        }
        public string LocatorId { get { return "MercEvisBakedCatalogFixtureLocator"; } }
        public IEnumerable<object> Keys { get { yield return BakedCatalogKey; } }
        public bool Locate(object key, Type type, out IList<IResourceLocation> locations)
        {
            if (Equals(key, BakedCatalogKey) && (type == null || type == typeof(RoR2.ContentManagement.BakedEffectsCatalog)))
            {
                locations = new List<IResourceLocation> { location };
                return true;
            }
            locations = null;
            return false;
        }
    }
}
#endif
