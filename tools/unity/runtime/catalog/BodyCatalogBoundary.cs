// Subsystem: catalog/resources (game path). Owner map: docs/ARCHITECTURE.md#ownership.
// Session phases: setup RegisterBodyCatalog, RegisterOriginalSkins (BodyCatalogSession); teardown CleanupBodyCatalog coordinates CleanupOriginalSkins, CleanupLoadoutTables (Dispose), template/catalog and composed release.
using System;
using System.Collections;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Collections.Generic;
using RoR2.Skills;
using RoR2.Projectile;
using Path = System.IO.Path;
using RoR2;
using UnityEngine;
using UnityEngine.AddressableAssets;
using UnityEngine.AddressableAssets.Initialization;
using UnityEngine.AddressableAssets.ResourceLocators;
using UnityEngine.AddressableAssets.ResourceProviders;
using UnityEngine.ResourceManagement.AsyncOperations;
using UnityEngine.ResourceManagement.ResourceLocations;

public sealed partial class PortSession
{
    bool ownsBodyAvailability;
    ResourceAvailability priorBodyAvailability;
    readonly Dictionary<int, GameObject> priorCatalogBodyTemplates = new Dictionary<int, GameObject>();
    void CleanupBodyCatalog()
    {
        Check(LegacyResourcesAPI.ActiveCount == 0, "Refuse teardown with pending portrait callbacks");
        CleanupOriginalSkins();
        CleanupLoadoutTables();
        RestoreCatalogBodyTemplates();
        if (ownsBodyAvailability)
        {
            BodyCatalog.availability = priorBodyAvailability;
            ownsBodyAvailability = false;
        }
        if (ownsBodyCatalog)
        {
            StaticCall(typeof(BodyCatalog), "SetBodyPrefabs", (object) new GameObject[0]);
            Check(BodyCatalog.bodyCount == 0, "Owned catalog reset failed");
            ownsBodyCatalog = false;
        }
        if (artifactBundle)
        {
            artifactBundle.Unload(true);
            artifactBundle = null;
        }
        ReleaseObjectiveBundlePreload();
        CleanupRecoveredText();
        if (Resources.Load<TextAsset>("WholeCatalogBootstrap"))
            WholeCatalogComposed.Release();
        RestoreBodySettingsTransform();
        if (r.liveCatalogs != null)
        {
            r.liveCatalogs.bodySkillCleanup =
                BodyCatalog.bodyCount == 0 && SkillCatalog.skillCount == 0 && SkillCatalog.skillFamilyCount == 0;
        }
    }
    BodyCatalogSession bodyCatalogSession;
    BodyCatalogSession GetBodyCatalogSession()
    {
        if (bodyCatalogSession == null)
            bodyCatalogSession = new BodyCatalogSession(this);
        return bodyCatalogSession;
    }
    static FieldInfo SkinField(string name)
    {
        return BodyCatalogSession.SkinField(name);
    }
    IEnumerator RegisterOriginalSkins()
    {
        return GetBodyCatalogSession().RegisterOriginalSkins();
    }
    void CleanupOriginalSkins()
    {
        GetBodyCatalogSession().CleanupOriginalSkins();
    }
    static Func<IResourceLocation, string> CreateBodySettingsTransform(string original, string local)
    {
        return BodyCatalogSession.CreateBodySettingsTransform(original, local);
    }
    static FieldInfo LoadoutField(string name)
    {
        return BodyCatalogSession.LoadoutField(name);
    }
    static FieldInfo ViewableField(string name)
    {
        return BodyCatalogSession.ViewableField(name);
    }
    void PrepareLoadoutTables(GameObject prefab)
    {
        GetBodyCatalogSession().PrepareLoadoutTables(prefab);
    }
    void CleanupLoadoutTables()
    {
        GetBodyCatalogSession().Dispose();
    }
    IEnumerator RegisterBodyCatalog() => GetBodyCatalogSession().RegisterBodyCatalog();
    void AdaptComposedEffectAudio(EffectDef definition)
    {
        GetBodyCatalogSession().AdaptComposedEffectAudio(definition);
    }
    void SetCatalogBodyTemplate(int index, GameObject template)
    {
        GetBodyCatalogSession().SetCatalogBodyTemplate(index, template);
    }
    void BindCatalogBodyTemplate(GameObject template)
    {
        GetBodyCatalogSession().BindCatalogBodyTemplate(template);
    }
    void RestoreCatalogBodyTemplates()
    {
        GetBodyCatalogSession().RestoreCatalogBodyTemplates();
    }
    void InitializeComposedEffects(System.Collections.Generic.IEnumerable<EffectDef> definitions, bool includeMercEvisAdapter)
    {
        GetBodyCatalogSession().InitializeComposedEffects(definitions, includeMercEvisAdapter);
    }
    void RegisterComposedEffects(System.Collections.Generic.IEnumerable<EffectDef> definitions)
    {
        GetBodyCatalogSession().RegisterComposedEffects(definitions);
    }
    void RestoreComposedEffects(EffectDef[] previous)
    {
        GetBodyCatalogSession().RestoreComposedEffects(previous);
    }
    BuffDef[] UpdatedComparisonBuffs(SessionConfig cfg)
    {
        return GetBodyCatalogSession().UpdatedComparisonBuffs(cfg);
    }
    ItemDef[] UpdatedComparisonItems(SessionConfig cfg)
    {
        return GetBodyCatalogSession().UpdatedComparisonItems(cfg);
    }
    void RestoreBodySettingsTransform()
    {
        GetBodyCatalogSession().RestoreBodySettingsTransform();
    }

    // Retain this owner after cleanup. The coordinator preserves the catalog and
    // composed-hook order; Dispose releases loadout tables at their existing step.
    sealed class BodyCatalogSession : IDisposable
    {
        readonly PortSession coordinator;
        public BodyCatalogSession(PortSession coordinator)
        {
            this.coordinator = coordinator;
        }
        bool ownsLoadoutTables, ownsSkillCatalog;
        bool ownsSkinCatalog;
        ResourceAvailability priorSkinAvailability;
        SkinDef[] priorSkinDefs;
        SkinDef[][] priorSkinsByBody;
        readonly Dictionary<SkinDef, SkinIndex> priorSkinIndices = new Dictionary<SkinDef, SkinIndex>();
        readonly Dictionary<string, SkinIndex> priorSkinNames = new Dictionary<string, SkinIndex>();
        public static FieldInfo SkinField(string name)
        {
            return typeof(SkinCatalog).GetField(name, BindingFlags.NonPublic | BindingFlags.Static);
        }
        public IEnumerator RegisterOriginalSkins()
        {
            coordinator.Check(coordinator.r.liveCatalogs != null && BodyCatalog.availability.available &&
                                  ProjectileCatalog.catalogAvailability.available && SkinCatalog.skinCount == 0 && !ownsSkinCatalog,
                              "Original skin catalog dependencies or ownership missing");
            priorSkinDefs = (SkinDef[])SkinField("allSkinDefs").GetValue(null);
            priorSkinsByBody = (SkinDef[][])SkinField("skinsByBody").GetValue(null);
            priorSkinAvailability = SkinCatalog.availability;
            var names = (Dictionary<string, SkinIndex>)SkinField("skinNameToIndex").GetValue(null);
            coordinator.Check(priorSkinDefs.Length == 0 && priorSkinsByBody.Length == 0 && names.Count == 0 &&
                                  !priorSkinAvailability.available,
                              "Unowned original skin catalog state");
            foreach (var prefab in BodyCatalog.allBodyPrefabs)
            {
                var locator = prefab.GetComponent<ModelLocator>();
                if (!locator || !locator.modelTransform)
                    continue;
                var controller = locator.modelTransform.GetComponent<ModelSkinController>();
                if (!controller)
                    continue;
                foreach (var skin in controller.skins)
                    if (skin && !priorSkinIndices.ContainsKey(skin))
                        priorSkinIndices.Add(skin, skin.skinIndex);
            }
            foreach (var pair in names)
                priorSkinNames.Add(pair.Key, pair.Value);
            ownsSkinCatalog = true;
            coordinator.r.phase = "original-skin-catalog-register";
            coordinator.Save();
            var method = typeof(SkinCatalog).GetMethod("Init", BindingFlags.NonPublic | BindingFlags.Static);
            coordinator.Check(method != null, "Original skin initializer missing");
            var routine = (IEnumerator)method.Invoke(null, null);
            var deadline = Time.realtimeSinceStartup + 180f;
            while (routine.MoveNext())
            {
                coordinator.Check(Time.realtimeSinceStartup < deadline, "Original skin catalog initialization timed out");
                yield return routine.Current;
            }
            coordinator.Check(
                SkinCatalog.availability.available && SkinCatalog.skinCount == priorSkinIndices.Count &&
                    priorSkinIndices.Keys.All(skin => skin.runtimeSkin != null && SkinCatalog.GetSkinDef(skin.skinIndex) == skin),
                "Original skin baking or index identity differs");
            var commando = BodyCatalog.FindBodyIndex("CommandoBody");
            coordinator.Check(SkinCatalog.GetBodySkinCount(commando) > 0 && SkinCatalog.GetBodySkinDef(commando, 0),
                              "Original Commando default skin missing");
        }
        public void CleanupOriginalSkins()
        {
            if (!ownsSkinCatalog)
                return;
            foreach (var pair in priorSkinIndices)
                if (pair.Key)
                    pair.Key.skinIndex = pair.Value;
            SkinField("allSkinDefs").SetValue(null, priorSkinDefs);
            SkinField("skinsByBody").SetValue(null, priorSkinsByBody);
            var names = (Dictionary<string, SkinIndex>)SkinField("skinNameToIndex").GetValue(null);
            names.Clear();
            foreach (var pair in priorSkinNames)
                names.Add(pair.Key, pair.Value);
            SkinCatalog.availability = priorSkinAvailability;
            ownsSkinCatalog = false;
            priorSkinIndices.Clear();
            priorSkinNames.Clear();
            coordinator.Check(SkinCatalog.skinCount == 0, "Original skin catalog outlived its owned body bundle");
        }
        bool ownsBodySettingsTransform;
        Func<IResourceLocation, string> priorBodySettingsTransform, ownedBodySettingsTransform;
        // A separate closure owns only path strings, never this session or its report.
        public static Func<IResourceLocation, string> CreateBodySettingsTransform(string original, string local)
        {
            return loc => loc.InternalId == original ? local : loc.InternalId;
        }
        object priorLoadoutDefaults, priorBodyInfos;
        readonly Dictionary<object, object> priorViewables = new Dictionary<object, object>();
        readonly HashSet<ViewablesCatalog.Node> priorViewableChildren = new HashSet<ViewablesCatalog.Node>();
        public static FieldInfo LoadoutField(string name)
        {
            return typeof(Loadout.BodyLoadoutManager).GetField(name, BindingFlags.NonPublic | BindingFlags.Static);
        }
        public static FieldInfo ViewableField(string name)
        {
            return typeof(ViewablesCatalog).GetField(name, BindingFlags.NonPublic | BindingFlags.Static);
        }
        public void PrepareLoadoutTables(GameObject prefab)
        {
            coordinator.Check(!SkillCatalog.allSkillDefs.Any() && !SkillCatalog.allSkillFamilies.Any(), "Existing skill catalog ownership");
            priorLoadoutDefaults = LoadoutField("defaultBodyLoadouts").GetValue(null);
            priorBodyInfos = LoadoutField("allBodyInfos").GetValue(null);
            coordinator.Check(priorLoadoutDefaults == null && priorBodyInfos == null, "Existing loadout defaults ownership");
            var slots = prefab.GetComponents<GenericSkill>();
            coordinator.Check(slots.Length == 4, "Original Commando skill-slot count");
            bool complete = coordinator.r.liveCatalogs != null;
            var selectedFamilies = BodyCatalog.allBodyPrefabs.SelectMany(x => x.GetComponents<GenericSkill>())
                                       .Select(x => x.skillFamily)
                                       .Where(x => x)
                                       .Distinct()
                                       .ToArray();
            var families =
                complete ? WholeCatalogComposed.CategoryFamily(RoR2.ContentManagement.AddressablesLabels.skillFamily, selectedFamilies)
                         : selectedFamilies;
            coordinator.Check(families.Length >= 4 &&
                                  families.All(x => x && x.variants.Length > 0 && x.defaultVariantIndex < x.variants.Length),
                              "Actual family/default-variant contract");
            // A source Copycat family has an empty variant. Register it unchanged; never invent a SkillDef.
            var selectedDefs = families.SelectMany(x => x.variants.Select(v => v.skillDef)).Where(x => x).Distinct().ToArray();
            var defs = complete ? WholeCatalogComposed.CategoryFamily(RoR2.ContentManagement.AddressablesLabels.skillDef, selectedDefs)
                                : selectedDefs;
            if (complete)
            {
                coordinator.r.liveCatalogs.skills = defs.Length;
                coordinator.r.liveCatalogs.skillFamilies = families.Length;
                coordinator.r.liveCatalogs.emptySkillVariants = families.Sum(family => family.variants.Count(variant => !variant.skillDef));
            }
            ownsSkillCatalog = true;
            PortSession.StaticCall(typeof(SkillCatalog), "SetSkillDefs", (object)defs);
            PortSession.StaticCall(typeof(SkillCatalog), "SetSkillFamilies", (object)families);
            foreach (var family in families)
                coordinator.Check(SkillCatalog.GetSkillFamily(family.catalogIndex) == family, "Original family catalog identity");
            foreach (var def in defs)
                coordinator.Check(SkillCatalog.GetSkillDef(def.skillIndex) == def, "Original skill catalog identity");
            coordinator.Check(SurvivorCatalog.GetSurvivorIndexFromBodyIndex(prefab.GetComponent<CharacterBody>().bodyIndex) ==
                                  SurvivorIndex.None,
                              "Unexpected survivor-specific viewable context");
            var map = (IDictionary)ViewableField("fullNameToNodeMap").GetValue(null);
            foreach (DictionaryEntry entry in map)
                priorViewables.Add(entry.Key, entry.Value);
            var root = (ViewablesCatalog.Node)ViewableField("rootNode").GetValue(null);
            foreach (var child in root.children)
                priorViewableChildren.Add(child);
            ownsLoadoutTables = true;
            coordinator.r.phase = "original-loadout-initialize";
            coordinator.Save();
            PortSession.StaticCall(typeof(Loadout.BodyLoadoutManager), "Init");
            var body = prefab.GetComponent<CharacterBody>();
            var defaults = (Array)LoadoutField("defaultBodyLoadouts").GetValue(null);
            coordinator.Check(defaults != null && defaults.Length == BodyCatalog.bodyCount, "Original default body loadout missing");
            var loadout = new Loadout();
            coordinator.Check(loadout.bodyLoadoutManager.GetSkinIndex(body.bodyIndex) == 0, "Original default skin");
            for (int i = 0; i < slots.Length; i++)
                coordinator.Check(loadout.bodyLoadoutManager.GetSkillVariant(body.bodyIndex, i) == slots[i].skillFamily.defaultVariantIndex,
                                  "Original default skill variant");
        }
        public void CleanupLoadoutTables()
        {
            if (ownsLoadoutTables)
            {
                LoadoutField("defaultBodyLoadouts").SetValue(null, priorLoadoutDefaults);
                LoadoutField("allBodyInfos").SetValue(null, priorBodyInfos);
                var root = (ViewablesCatalog.Node)ViewableField("rootNode").GetValue(null);
                foreach (var child in root.children.ToArray())
                    if (!priorViewableChildren.Contains(child))
                        child.SetParent(null);
                var map = (IDictionary)ViewableField("fullNameToNodeMap").GetValue(null);
                map.Clear();
                foreach (var pair in priorViewables)
                    map.Add(pair.Key, pair.Value);
                ownsLoadoutTables = false;
            }
            if (ownsSkillCatalog)
            {
                PortSession.StaticCall(typeof(SkillCatalog), "SetSkillFamilies", (object) new SkillFamily[0]);
                PortSession.StaticCall(typeof(SkillCatalog), "SetSkillDefs", (object) new SkillDef[0]);
                ownsSkillCatalog = false;
            }
        }
        public IEnumerator RegisterBodyCatalog()
        {
            // Current original SpawnBody requires the game's PreSplash preset table.
            // This immutable application table is initialized once, not per session.
            if (BodyHandlingConfig.DefaultSettings == null)
            {
                coordinator.r.phase = "original-body-handling-presets";
                coordinator.Save();
                BodyHandlingConfig.Presets.InitializePresets();
            }
            coordinator.Check(BodyHandlingConfig.DefaultSettings != null &&
                                  BodyHandlingConfig.DefaultSettings.currentPreset == BodyHandlingPresetIndex.Initial,
                              "Original body-handling presets unavailable");
            if (Resources.Load<TextAsset>("WholeCatalogBootstrap"))
            {
                var shared = WholeCatalogComposed.Prepare();
                while (shared.MoveNext())
                    yield return shared.Current;
            }
            coordinator.Check(BodyCatalog.bodyCount == 0 && LegacyResourcesAPI.ActiveCount == 0, "Existing catalog/request ownership");
            coordinator.r.phase = "body-catalog-initialize";
            coordinator.Save();
            var directory = Path.Combine(Application.persistentDataPath, "body-catalog-probe");
            Directory.CreateDirectory(directory);
            var catalog = Path.Combine(directory, "catalog.json");
            var settings = Path.Combine(directory, "settings.json");
            // Reuse the accepted controller probe's real, empty Addressables initialization.
            File.WriteAllText(
                catalog,
                "{\"m_LocatorId\":\"body-catalog-probe\",\"m_ProviderIds\":[],\"m_InternalIds\":[],\"m_KeyDataString\":\"AAAAAA==\",\"m_BucketDataString\":\"AAAAAA==\",\"m_EntryDataString\":\"AAAAAA==\",\"m_ExtraDataString\":\"\",\"m_resourceTypes\":[]}");
            var data = new ResourceManagerRuntimeData { BuildTarget = "Android", DisableCatalogUpdateOnStartup = true,
                                                        LogResourceManagerExceptions = true };
            data.CatalogLocations.Add(new ResourceLocationData(new[] { ResourceManagerRuntimeData.kCatalogAddress }, catalog,
                                                               typeof(ContentCatalogProvider), typeof(ContentCatalogData)));
            File.WriteAllText(settings, JsonUtility.ToJson(data));
            var originalSettings = Addressables.RuntimePath + "/settings.json";
            coordinator.Check(!ownsBodySettingsTransform, "Existing owned settings transform");
            priorBodySettingsTransform = Addressables.InternalIdTransformFunc;
            ownedBodySettingsTransform = CreateBodySettingsTransform(originalSettings, settings);
            Addressables.InternalIdTransformFunc = ownedBodySettingsTransform;
            ownsBodySettingsTransform = true;
            coordinator.r.catalogTransformInstalled = true;
            var init = Addressables.InitializeAsync();
            Addressables.ResourceManager.Acquire(init);
            var deadline = Time.realtimeSinceStartup + 8;
            while (!init.IsDone && Time.realtimeSinceStartup < deadline)
                yield return null;
            coordinator.Check(init.IsDone && init.Status == AsyncOperationStatus.Succeeded, "Real Addressables initialization failed");
            Addressables.Release(init);
            string mapped;
            const string key = "Textures/BodyIcons/CommandoBody";
            coordinator.Check(!LegacyResourcesAPI.GetGuid(key, out mapped), "Unexpected legacy portrait alias");
            var missing = LegacyResourcesAPI.LoadAsync<Texture2D>(key);
            deadline = Time.realtimeSinceStartup + 3;
            while (!missing.IsDone && Time.realtimeSinceStartup < deadline)
                yield return null;
            yield return null;
            coordinator.Check(missing.IsDone && missing.Status == AsyncOperationStatus.Failed && missing.Result == null,
                              "Missing portrait did not fail honestly");
            coordinator.Check(missing.OperationException is InvalidKeyException, "Unexpected portrait failure class");
            Addressables.Release(missing);
            coordinator.Check(LegacyResourcesAPI.ActiveCount == 0, "Missing request callback not drained");
            // MovementBatchProbe is the unchanged resource/file name.
            var cfg = JsonUtility.FromJson<SessionConfig>(Resources.Load<TextAsset>("MovementBatchProbe").text);
            coordinator.artifactBundle =
                AssetBundle.LoadFromFile(Path.Combine(Application.persistentDataPath, "payload", "commando-prefab-lab"));
            coordinator.Check(coordinator.artifactBundle, "Body bundle missing");
            if (cfg.teleporterLoop)
            {
                var preload = coordinator.PreloadObjectiveBundle();
                while (preload.MoveNext())
                    yield return preload.Current;
            }
            var prefab = coordinator.artifactBundle.LoadAsset<GameObject>(cfg.bodyAsset);
            coordinator.Check(prefab && !prefab.activeSelf && prefab.name == "CommandoBody", "Unexpected body prefab");
            var body = prefab.GetComponent<CharacterBody>();
            var portrait = body.portraitIcon;
            coordinator.Check(portrait && portrait.name == "texCommandoIcon", "Serialized portrait missing");
            coordinator.r.phase = "original-body-catalog-register";
            coordinator.Save();
            var bodies =
                cfg.enemySpine ? new[] { prefab, coordinator.artifactBundle.LoadAsset<GameObject>(cfg.enemyBodyAsset) } : new[] { prefab };
            if (cfg.teleporterLoop)
                bodies = bodies.Concat(cfg.objectiveActors.Select(x => coordinator.artifactBundle.LoadAsset<GameObject>(x.body))).ToArray();
            if (cfg.integratedWorld && Resources.Load<TextAsset>("WholeCatalogBootstrap"))
            {
                bodies = WholeCatalogComposed.CategoryFamily(RoR2.ContentManagement.AddressablesLabels.characterBody, bodies.Distinct());
                coordinator.r.liveCatalogs = new LiveCatalogReport { bodies = bodies.Length };
            }
            coordinator.ownsBodyCatalog = true;
            PortSession.StaticCall(typeof(BodyCatalog), "SetBodyPrefabs", (object)bodies);
            deadline = Time.realtimeSinceStartup + 3;
            while (LegacyResourcesAPI.ActiveCount != 0 && Time.realtimeSinceStartup < deadline)
                yield return null;
            yield return null;
            yield return null;
            coordinator.Check(LegacyResourcesAPI.ActiveCount == 0, "Catalog portrait callback still pending");
            coordinator.Check(BodyCatalog.bodyCount == bodies.Length && body.bodyIndex != (BodyIndex)(-1),
                              "Original index assignment failed");
            coordinator.Check(BodyCatalog.FindBodyIndex("CommandoBody") == body.bodyIndex &&
                                  BodyCatalog.FindBodyIndex("CommandoBody(Clone)") == body.bodyIndex,
                              "Original name/index lookup failed");
            coordinator.Check(BodyCatalog.GetBodyPrefab(body.bodyIndex) == prefab, "Original prefab lookup failed");
            coordinator.Check(body.portraitIcon == portrait, "Missing-key callback replaced serialized portrait");
            coordinator.Check(!prefab.activeSelf, "Catalog registration activated gameplay");
            if (cfg.initializeLoadoutTables)
                PrepareLoadoutTables(prefab);
            if (Resources.Load<TextAsset>("WholeCatalogBootstrap"))
            {
                WholeCatalogComposed.ConfigureLocations();
                coordinator.priorBodyAvailability = BodyCatalog.availability;
                coordinator.Check(!coordinator.priorBodyAvailability.available, "Unowned original body availability");
                BodyCatalog.availability.MakeAvailable();
                coordinator.ownsBodyAvailability = true;
            }
        }
        ResourceAvailability priorComposedEffectAvailability;
        readonly Dictionary<EffectDef, string> priorComposedEffectSounds = new Dictionary<EffectDef, string>();
        EffectDef[] ownedComposedEntries, nativeComposedEntryBaseline;
        IDictionary ownedComposedNameMap;
        Dictionary<string, EffectIndex> nativeComposedNameMapBaseline;
        ResourceAvailability ownedComposedAvailability;
#if UNITY_EDITOR
        GameObject fixtureLastMercOwnedPrefab, fixtureLastMercOwnedOwner;
#endif
        MercEvisImpactEffectLease mercEvisImpactEffectLease;
        EffectMutationState[] ownedEffectMutationStates = Array.Empty<EffectMutationState>();
        sealed class EffectMutationState
        {
            public readonly EffectDef definition;
            readonly GameObject prefab;
            readonly EffectComponent component;
            readonly EffectIndex priorDefinitionIndex;
            readonly EffectIndex priorComponentIndex;
            readonly string priorSound;
            EffectIndex registeredIndex = EffectIndex.Invalid;
            public EffectIndex RegisteredIndex => registeredIndex;
            public EffectMutationState(EffectDef value)
            {
                if (value == null) throw new InvalidOperationException("Null EffectDef in composed definition set");
                definition = value;
                prefab = value.prefab;
                component = value.prefabEffectComponent;
                priorDefinitionIndex = value.index;
                priorComponentIndex = component ? component.effectIndex : EffectIndex.Invalid;
                priorSound = value.spawnSoundEventName;
            }
            public void CaptureRegisteredIndex()
            {
                registeredIndex = EffectCatalog.FindEffectIndex(definition.prefabName);
            }
            public bool IsOwnedCurrentValue()
            {
                return definition != null && definition.prefab == prefab && definition.prefabEffectComponent == component &&
                       (definition.index == priorDefinitionIndex || definition.index == registeredIndex) &&
                       (!component || component.effectIndex == priorComponentIndex || component.effectIndex == registeredIndex) &&
                       (definition.spawnSoundEventName == priorSound ||
                        (!string.IsNullOrEmpty(priorSound) && definition.spawnSoundEventName == null));
            }
            public void RestorePriorValues()
            {
                if (definition == null || definition.prefab != prefab || definition.prefabEffectComponent != component)
                    throw new InvalidOperationException("Composed EffectDef identity changed before restoring saved fields");
                typeof(EffectDef).GetProperty("index").SetValue(definition, priorDefinitionIndex, null);
                if (component) component.effectIndex = priorComponentIndex;
                typeof(EffectDef).GetProperty("spawnSoundEventName").SetValue(definition, priorSound, null);
            }
        }
        static EffectDef[] UniqueEffectDefinitions(IEnumerable<EffectDef> source)
        {
            var result = new List<EffectDef>();
            foreach (var value in source)
                if (!result.Any(existing => ReferenceEquals(existing, value)))
                    result.Add(value);
            return result.ToArray();
        }
        static void DestroyOwnedObject(GameObject value)
        {
            if (!value) return;
#if UNITY_EDITOR
            if (!Application.isPlaying)
                UnityEngine.Object.DestroyImmediate(value);
            else
                UnityEngine.Object.Destroy(value);
#else
            UnityEngine.Object.Destroy(value);
#endif
        }
        bool ComposedCatalogStructureStillOwned(EffectDef[] entries, IDictionary nameMap)
        {
            if (!ReferenceEquals(entries, ownedComposedEntries) || !ReferenceEquals(nameMap, ownedComposedNameMap) ||
                entries == null || nameMap == null || nativeComposedEntryBaseline == null || nativeComposedNameMapBaseline == null ||
                entries.Length != nativeComposedEntryBaseline.Length || nameMap.Count != nativeComposedNameMapBaseline.Count ||
                !EffectCatalog.availability.Equals(ownedComposedAvailability)) return false;
            foreach (var pair in nativeComposedNameMapBaseline)
                if (!nameMap.Contains(pair.Key) || !Equals(nameMap[pair.Key], pair.Value)) return false;
            for (int i = 0; i < entries.Length; i++)
                if (!ReferenceEquals(entries[i], nativeComposedEntryBaseline[i]) &&
                    !ownedEffectMutationStates.Any(state => (int)state.RegisteredIndex == i &&
                                                            ReferenceEquals(state.definition, entries[i]))) return false;
            return true;
        }
        sealed class MercEvisImpactEffectLease
        {
            const string VisualPath = "Assets/WholeGame/RoR2/Base/Characters/Merc/MercSwordFinisherSlash.prefab";
            const string ProjectilePath = "Assets/WholeGame/RoR2/Base/Characters/Merc/Skills/EvisProjectile.prefab";
            readonly GameObject targetProjectile;
            readonly ProjectileImpactExplosion targetComponent;
            readonly GameObject originalImpactEffect;
            readonly GameObject ownedEffectPrefab;
            readonly GameObject inactiveOwner;
            readonly EffectDef definition;
            readonly int markerToken;
            EffectDef[] ownedCatalogEntries;
            IDictionary ownedCatalogNameMap;
            EffectDef[] nativeEntryBaseline;
            Dictionary<string, EffectIndex> nativeNameMapBaseline;
            ResourceAvailability ownedCatalogAvailability;
            public EffectDef Definition => definition;
            public GameObject OwnedEffectPrefab => ownedEffectPrefab;
            public GameObject OwnedEffectOwner => inactiveOwner;
            public void CaptureCatalogOwnership(EffectDef[] entries, IDictionary nameMap, ResourceAvailability availability)
            {
                if (entries == null || !entries.Contains(definition) || nameMap == null ||
                    !nameMap.Contains(definition.prefabName) ||
                    (EffectIndex)nameMap[definition.prefabName] != definition.index)
                    throw new InvalidOperationException("Merc Evis registered catalog ownership was not established");
                ownedCatalogEntries = entries;
                ownedCatalogNameMap = nameMap;
                ownedCatalogAvailability = availability;
                nativeEntryBaseline = entries.ToArray();
                nativeNameMapBaseline = new Dictionary<string, EffectIndex>();
                foreach (DictionaryEntry entry in nameMap)
                    nativeNameMapBaseline.Add((string)entry.Key, (EffectIndex)entry.Value);
            }
            public void CaptureCatalogAvailability(ResourceAvailability availability) { ownedCatalogAvailability = availability; }
            public EffectDef[] NativeEntryBaseline => nativeEntryBaseline;
            public IDictionary OwnedCatalogNameMap => ownedCatalogNameMap;
            public Dictionary<string, EffectIndex> NativeNameMapBaseline => nativeNameMapBaseline;
            public ResourceAvailability OwnedCatalogAvailability => ownedCatalogAvailability;
            public bool CanRestoreTarget()
            {
                return targetProjectile && targetComponent && targetComponent.gameObject == targetProjectile &&
                       (targetComponent.impactEffect == originalImpactEffect || targetComponent.impactEffect == ownedEffectPrefab);
            }
            public void RestoreTargetForRollback()
            {
                if (!CanRestoreTarget())
                    throw new InvalidOperationException("Foreign Merc Evis target field during setup rollback");
                if (targetComponent.impactEffect == ownedEffectPrefab)
                    targetComponent.impactEffect = originalImpactEffect;
            }
            public bool CatalogStructureStillOwned(EffectDef[] entries, IDictionary nameMap, ResourceAvailability availability)
            {
                if (!ReferenceEquals(entries, ownedCatalogEntries) || !ReferenceEquals(nameMap, ownedCatalogNameMap) ||
                    !availability.Equals(ownedCatalogAvailability) || nativeEntryBaseline == null || nativeNameMapBaseline == null ||
                    entries.Length != nativeEntryBaseline.Length || nameMap.Count != nativeNameMapBaseline.Count)
                    return false;
                foreach (var pair in nativeNameMapBaseline)
                    if (!nameMap.Contains(pair.Key) || !Equals(nameMap[pair.Key], pair.Value)) return false;
                return true;
            }
            MercEvisImpactEffectLease(GameObject projectile, ProjectileImpactExplosion component, GameObject original,
                                     GameObject effectPrefab, GameObject owner, EffectDef effectDefinition, int token)
            {
                targetProjectile = projectile;
                targetComponent = component;
                originalImpactEffect = original;
                ownedEffectPrefab = effectPrefab;
                inactiveOwner = owner;
                definition = effectDefinition;
                markerToken = token;
            }
            public static MercEvisImpactEffectLease Create(GameObject visualSource, GameObject projectileSource,
                                                           bool requireOwnedProjectileCatalog = true)
            {
                if (!visualSource || visualSource.name != "MercSwordFinisherSlash" ||
                    visualSource.GetComponent<EffectComponent>() || !visualSource.GetComponent<VFXAttributes>() ||
                    !visualSource.GetComponent<DestroyOnTimer>() || !visualSource.GetComponent<ShakeEmitter>() ||
                    !visualSource.GetComponent<ScaleParticleSystemDuration>())
                    throw new InvalidOperationException("Exact Merc swing visual source contract changed");
                var timer = visualSource.GetComponent<DestroyOnTimer>();
                if (!timer || Mathf.Abs(timer.duration - 1f) > 0.0001f)
                    throw new InvalidOperationException("Exact Merc swing native one-second lifetime changed");
                if (!projectileSource || projectileSource.name != "EvisProjectile" ||
                    projectileSource.GetComponent<ProjectileController>() == null)
                    throw new InvalidOperationException("Exact Evis projectile source contract changed");
                var components = projectileSource.GetComponents<ProjectileImpactExplosion>();
                if (components.Length != 1 || components[0].impactEffect != visualSource || components[0].explosionEffect ||
                    components[0].blastImpactEffect)
                    throw new InvalidOperationException("Exact Evis impact-effect field ownership changed");
                if (requireOwnedProjectileCatalog && WholeCatalogComposed.CategoryFamily(RoR2.ContentManagement.AddressablesLabels.projectile, new GameObject[0])
                        .Count(value => ReferenceEquals(value, projectileSource)) != 1)
                    throw new InvalidOperationException("Evis projectile is not the unique exact owned projectile-catalog object");

                GameObject owner = null;
                GameObject clone = null;
                try
                {
                    owner = new GameObject("Owned Merc Evis impact-effect lease");
                    owner.SetActive(false);
                    clone = UnityEngine.Object.Instantiate(visualSource, owner.transform, false);
                    clone.name = "MercSwordFinisherSlash_PortEvisImpact";
                    if (clone.activeSelf != visualSource.activeSelf || clone.activeInHierarchy)
                        throw new InvalidOperationException("Owned effect clone activation state changed during setup");
                    var vfx = clone.GetComponent<VFXAttributes>();
                    if (!vfx)
                        throw new InvalidOperationException("Owned effect clone lost native VFXAttributes");
                    vfx.DoNotPool = true;
                    var component = clone.AddComponent<EffectComponent>();
                    var token = NextMercEvisEffectToken();
                    var marker = clone.AddComponent<MercEvisEffectInstanceMarker>();
                    marker.token = token;
                    component.applyScale = false;
                    component.soundName = null;
                    var definition = new EffectDef(clone);
                    if (definition.prefabEffectComponent != component || definition.prefab != clone || definition.shouldPool ||
                        !string.IsNullOrEmpty(definition.spawnSoundEventName))
                        throw new InvalidOperationException("Owned Merc effect definition contract changed");
                    return new MercEvisImpactEffectLease(projectileSource, components[0], visualSource, clone, owner, definition, token);
                }
                catch
                {
                    if (owner)
                        DestroyOwnedObject(owner);
                    else if (clone)
                        DestroyOwnedObject(clone);
                    throw;
                }
            }
            public void Bind()
            {
                if (!targetProjectile || !targetComponent || targetComponent.gameObject != targetProjectile ||
                    targetComponent.impactEffect != originalImpactEffect || !ownedEffectPrefab)
                    throw new InvalidOperationException("Merc Evis impact target ownership changed before bind");
                targetComponent.impactEffect = ownedEffectPrefab;
                if (targetComponent.impactEffect != ownedEffectPrefab)
                    throw new InvalidOperationException("Owned Merc Evis impact binding did not stick");
            }
            public void PreflightCleanup(EffectDef[] currentEntries)
            {
                var currentNameMap = (IDictionary)PortSession.RewardField(typeof(EffectCatalog), "nameToEffectIndex").GetValue(null);
                if (!targetProjectile || !targetComponent || targetComponent.gameObject != targetProjectile ||
                    targetComponent.impactEffect != ownedEffectPrefab || !ownedEffectPrefab || !inactiveOwner ||
                    definition == null || definition.prefab != ownedEffectPrefab || definition.prefabEffectComponent !=
                        ownedEffectPrefab.GetComponent<EffectComponent>() ||
                    !CatalogStructureStillOwned(currentEntries, currentNameMap, EffectCatalog.availability) ||
                    !ReferenceEquals(currentEntries, ownedCatalogEntries) ||
                    definition.prefabEffectComponent.effectIndex != definition.index ||
                    EffectCatalog.FindEffectIndex(definition.prefabName) != definition.index ||
                    EffectCatalog.GetEffectDef(definition.index) != definition ||
                    !currentEntries.Contains(definition))
                    throw new InvalidOperationException("Merc Evis adapter ownership changed; retain catalog and asset lease");
                var pools = (Dictionary<GameObject, EffectPool>)PortSession.RewardField(typeof(EffectManager), "_EffectPrefabMap")
                                .GetValue(null);
                if (pools.ContainsKey(ownedEffectPrefab))
                    throw new InvalidOperationException("Non-pooled Merc Evis adapter unexpectedly owns an EffectPool");
                var pooledUse = (IDictionary)PortSession.RewardField(typeof(EffectManager), "_ShouldUsePooledEffectMap").GetValue(null);
                if (pooledUse.Contains(ownedEffectPrefab) && !Equals(pooledUse[ownedEffectPrefab], false))
                    throw new InvalidOperationException("Merc Evis adapter's pooled-use cache is not explicitly false");
                var liveOwnedInstances = Resources.FindObjectsOfTypeAll<MercEvisEffectInstanceMarker>()
                    .Any(value => value && value.token == markerToken && value.gameObject != ownedEffectPrefab);
                if (liveOwnedInstances)
                    throw new InvalidOperationException("Merc Evis marked effect instance remains; retain catalog and asset lease");
                var liveProjectilesHoldingEffect = Resources.FindObjectsOfTypeAll<ProjectileImpactExplosion>()
                    .Any(value => value && value != targetComponent && value.impactEffect == ownedEffectPrefab &&
                                  value.gameObject.scene.IsValid());
                if (liveProjectilesHoldingEffect)
                    throw new InvalidOperationException("Live projectile still references the Merc Evis effect clone; retain catalog and asset lease");
            }
            public void RestoreBinding()
            {
                if (!targetComponent || targetComponent.impactEffect != ownedEffectPrefab)
                    throw new InvalidOperationException("Merc Evis impact field changed after cleanup preflight");
                targetComponent.impactEffect = originalImpactEffect;
                if (targetComponent.impactEffect != originalImpactEffect)
                    throw new InvalidOperationException("Merc Evis original impact reference failed to restore");
            }
            public void ReleaseAfterCatalogRestore()
            {
                var pools = (Dictionary<GameObject, EffectPool>)PortSession.RewardField(typeof(EffectManager), "_EffectPrefabMap")
                                .GetValue(null);
                var cache = (IDictionary)PortSession.RewardField(typeof(EffectManager), "_ShouldUsePooledEffectMap").GetValue(null);
                cache.Remove(ownedEffectPrefab);
                if (pools.ContainsKey(ownedEffectPrefab))
                    throw new InvalidOperationException("Merc Evis adapter pool appeared during teardown");
                DestroyOwnedObject(inactiveOwner);
            }
        }
        static int nextMercEvisEffectToken;
        static int NextMercEvisEffectToken()
        {
            var live = Resources.FindObjectsOfTypeAll<MercEvisEffectInstanceMarker>();
            do
            {
                unchecked { nextMercEvisEffectToken++; }
                if (nextMercEvisEffectToken == 0) unchecked { nextMercEvisEffectToken++; }
            }
            while (live.Any(value => value && value.token == nextMercEvisEffectToken));
            return nextMercEvisEffectToken;
        }
        sealed class MercEvisEffectInstanceMarker : MonoBehaviour { public int token; }
        public void AdaptComposedEffectAudio(EffectDef definition)
        {
            // These owned runtime records are distinct from original baked assets.
            // Audio is unavailable; preserve visual dispatch and restore the event metadata.
            if (string.IsNullOrEmpty(definition.spawnSoundEventName) || priorComposedEffectSounds.ContainsKey(definition))
                return;
            priorComposedEffectSounds.Add(definition, definition.spawnSoundEventName);
            typeof(EffectDef).GetProperty("spawnSoundEventName").SetValue(definition, null, null);
            if (coordinator.r.rewards != null)
                coordinator.r.rewards.unavailableEffectSounds = priorComposedEffectSounds.Count;
        }
        public void SetCatalogBodyTemplate(int index, GameObject template)
        {
            ((GameObject[])PortSession.RewardField(typeof(BodyCatalog), "bodyPrefabs").GetValue(null))[index] = template;
            ((CharacterBody[])PortSession.RewardField(typeof(BodyCatalog), "bodyPrefabBodyComponents").GetValue(null))[index] =
                template.GetComponent<CharacterBody>();
            ((Component[][])PortSession.RewardField(typeof(BodyCatalog), "bodyComponents").GetValue(null))[index] =
                template.GetComponents<Component>();
            ((GenericSkill[][])PortSession.RewardField(typeof(BodyCatalog), "skillSlots").GetValue(null))[index] =
                template.GetComponents<GenericSkill>();
        }
        public void BindCatalogBodyTemplate(GameObject template)
        {
            var body = template.GetComponent<CharacterBody>();
            int index = (int)body.bodyIndex;
            var original = BodyCatalog.GetBodyPrefab(body.bodyIndex);
            coordinator.Check(coordinator.ownsBodyCatalog && original && original.name == template.name && original != template &&
                                  template.activeSelf && !template.activeInHierarchy &&
                                  !coordinator.priorCatalogBodyTemplates.ContainsKey(index),
                              "Owned catalog body-template identity invalid: " + template.name);
            coordinator.priorCatalogBodyTemplates.Add(index, original);
            SetCatalogBodyTemplate(index, template);
            coordinator.Check(BodyCatalog.GetBodyPrefab(body.bodyIndex) == template &&
                                  BodyCatalog.GetBodyPrefabBodyComponent(body.bodyIndex) == body,
                              "Original spawn catalog did not select the owned template");
        }
        public void RestoreCatalogBodyTemplates()
        {
            foreach (var pair in coordinator.priorCatalogBodyTemplates)
                SetCatalogBodyTemplate(pair.Key, pair.Value);
            coordinator.priorCatalogBodyTemplates.Clear();
        }
        public void InitializeComposedEffects(System.Collections.Generic.IEnumerable<EffectDef> definitions, bool includeMercEvisAdapter)
        {
            InitializeComposedEffectsCore(definitions, includeMercEvisAdapter, null, null, null, true);
        }
#if UNITY_EDITOR
        public void InitializeMercEvisAdapterFixture(GameObject visualSource, GameObject projectileSource,
                                                       System.Collections.Generic.IEnumerable<EffectDef> definitions,
                                                       System.Collections.Generic.IEnumerable<EffectDef> fixtureAdditions = null)
        {
            InitializeComposedEffectsCore(definitions, true, visualSource, projectileSource, fixtureAdditions, false);
        }
        public GameObject[] MercEvisFixtureLastOwnedObjects()
        {
            return new[] { fixtureLastMercOwnedPrefab, fixtureLastMercOwnedOwner };
        }
        public void InitializeComposedEffectsFixture(System.Collections.Generic.IEnumerable<EffectDef> definitions,
                                                       System.Collections.Generic.IEnumerable<EffectDef> fixtureAdditions = null)
        {
            InitializeComposedEffectsCore(definitions, false, null, null, fixtureAdditions, false);
        }
#endif
        void InitializeComposedEffectsCore(System.Collections.Generic.IEnumerable<EffectDef> definitions,
                                           bool includeMercEvisAdapter, GameObject fixtureVisual, GameObject fixtureProjectile,
                                           System.Collections.Generic.IEnumerable<EffectDef> fixtureAdditions = null,
                                           bool requireOwnedProjectileCatalog = true)
        {
            coordinator.Check(mercEvisImpactEffectLease == null, "Existing Merc Evis effect adapter owner");
            priorComposedEffectAvailability = EffectCatalog.availability;
            var entriesField = PortSession.RewardField(typeof(EffectCatalog), "entries");
            var nameMapField = PortSession.RewardField(typeof(EffectCatalog), "nameToEffectIndex");
            var priorEntries = (EffectDef[])entriesField.GetValue(null);
            var nameMap = (IDictionary)nameMapField.GetValue(null);
            coordinator.Check(priorEntries.Length == 0 && nameMap.Count == 0 && !priorComposedEffectAvailability.available,
                              "Original effect catalog already owned");
            var priorNames = new Dictionary<string, EffectIndex>();
            foreach (DictionaryEntry entry in nameMap)
                priorNames.Add((string)entry.Key, (EffectIndex)entry.Value);
            MercEvisImpactEffectLease candidate = null;
            if (includeMercEvisAdapter)
                candidate = MercEvisImpactEffectLease.Create(
                    fixtureVisual ? fixtureVisual : WholeCatalogComposed.LoadOwnedContent<GameObject>("Assets/WholeGame/RoR2/Base/Characters/Merc/MercSwordFinisherSlash.prefab"),
                    fixtureProjectile ? fixtureProjectile : WholeCatalogComposed.LoadOwnedContent<GameObject>("Assets/WholeGame/RoR2/Base/Characters/Merc/Skills/EvisProjectile.prefab"),
                    requireOwnedProjectileCatalog);
#if UNITY_EDITOR
            if (candidate != null && fixtureVisual)
            {
                fixtureLastMercOwnedPrefab = candidate.OwnedEffectPrefab;
                fixtureLastMercOwnedOwner = candidate.OwnedEffectOwner;
            }
#endif
            bool setEntriesCalled = false, setEntriesReturned = false;
            EffectDef[] ownedEntries = null, nativeEntriesBaseline = null;
            IDictionary ownedNameMap = null;
            EffectMutationState[] mutationStates = Array.Empty<EffectMutationState>();
            try
            {
                // This is the only SetEntries call in this catalog generation.
                // Additions are separate from baked-name replacement definitions.
                var additions = fixtureAdditions == null ? Array.Empty<EffectDef>() : fixtureAdditions.ToArray();
                var replacements = definitions == null ? null : definitions.ToArray();
                mutationStates = UniqueEffectDefinitions((candidate == null ? Enumerable.Empty<EffectDef>() : new[] { candidate.Definition })
                    .Concat(additions).Concat(replacements ?? Array.Empty<EffectDef>()))
                    .Select(value => new EffectMutationState(value)).ToArray();
                setEntriesCalled = true;
                EffectCatalog.SetEntries((candidate == null ? Enumerable.Empty<EffectDef>() : new[] { candidate.Definition })
                                             .Concat(additions).ToArray());
                setEntriesReturned = true;
                ownedEntries = (EffectDef[])entriesField.GetValue(null);
                ownedNameMap = (IDictionary)nameMapField.GetValue(null);
                if (ownedEntries == null || !ReferenceEquals(ownedNameMap, nameMap))
                    throw new InvalidOperationException("Native SetEntries replaced the exact owned catalog structure");
                nativeEntriesBaseline = ownedEntries.ToArray();
                if (candidate != null)
                    candidate.CaptureCatalogOwnership(ownedEntries, ownedNameMap, EffectCatalog.availability);
                foreach (var state in mutationStates)
                    state.CaptureRegisteredIndex();
                ownedEffectMutationStates = mutationStates;
                ownedComposedEntries = ownedEntries;
                ownedComposedNameMap = ownedNameMap;
                nativeComposedEntryBaseline = nativeEntriesBaseline;
                nativeComposedNameMapBaseline = new Dictionary<string, EffectIndex>();
                foreach (DictionaryEntry entry in ownedNameMap)
                    nativeComposedNameMapBaseline.Add((string)entry.Key, (EffectIndex)entry.Value);
                EffectCatalog.availability.MakeAvailable();
                ownedComposedAvailability = EffectCatalog.availability;
                if (candidate != null)
                    candidate.CaptureCatalogAvailability(EffectCatalog.availability);
                coordinator.Check(EffectCatalog.effectCount > 0, "Original baked effect catalog unavailable");
                if (candidate != null)
                {
                    var index = EffectCatalog.FindEffectIndex(candidate.Definition.prefabName);
                    coordinator.Check(index != EffectIndex.Invalid && EffectCatalog.GetEffectDef(index) == candidate.Definition &&
                                          EffectCatalog.FindEffectIndexFromPrefab(candidate.OwnedEffectPrefab) == index,
                                      "Owned Merc Evis effect catalog identity failed");
                }
                RegisterComposedEffectsInitial(candidate == null ? definitions : replacements);
                foreach (var definition in (EffectDef[])entriesField.GetValue(null))
                    AdaptComposedEffectAudio(definition);
                if (candidate != null)
                    candidate.Bind();
                mercEvisImpactEffectLease = candidate;
                ownedEffectMutationStates = mutationStates;
            }
            catch (Exception setupFailure)
            {
                if (!setEntriesCalled)
                {
                    if (candidate != null && candidate.OwnedEffectPrefab)
                        DestroyOwnedObject(candidate.OwnedEffectOwner);
                    throw;
                }
                if (!setEntriesReturned)
                {
                    // SetEntries may have partially assigned indices or replaced
                    // static catalog state before it throws. No such state is
                    // mutated during recovery; retain the candidate for recovery.
                    mercEvisImpactEffectLease = candidate;
                    ownedEffectMutationStates = mutationStates;
                    throw new AggregateException("Native EffectCatalog.SetEntries failed before ownership capture", setupFailure);
                }
                if (candidate == null)
                {
                    try
                    {
                        var current = (EffectDef[])entriesField.GetValue(null);
                        var currentMap = (IDictionary)nameMapField.GetValue(null);
                        if (!ComposedCatalogStructureStillOwned(current, currentMap) ||
                            mutationStates.Any(state => !state.IsOwnedCurrentValue()) ||
                            priorComposedEffectSounds.Any(pair => pair.Key == null ||
                                (pair.Key.spawnSoundEventName != null && pair.Key.spawnSoundEventName != pair.Value)))
                            throw new InvalidOperationException("Non-Merc composed catalog ownership changed before setup rollback");
                    }
                    catch (Exception ownershipFailure)
                    {
                        ownedEffectMutationStates = mutationStates;
                        throw new AggregateException("Non-Merc setup rollback refused; retain the exact catalog state",
                                                     setupFailure, ownershipFailure);
                    }
                    foreach (var state in mutationStates.Reverse())
                        state.RestorePriorValues();
                    foreach (var pair in priorComposedEffectSounds)
                        typeof(EffectDef).GetProperty("spawnSoundEventName").SetValue(pair.Key, pair.Value, null);
                    priorComposedEffectSounds.Clear();
                    entriesField.SetValue(null, priorEntries);
                    nameMap.Clear();
                    foreach (var pair in priorNames) nameMap.Add(pair.Key, pair.Value);
                    EffectCatalog.availability = priorComposedEffectAvailability;
                    ClearOwnedComposedCatalogSnapshot();
                    ownedEffectMutationStates = Array.Empty<EffectMutationState>();
                    throw;
                }

                // Prove every owned structure and field before the first rollback
                // write. Foreign replacement or uncertain SetEntries state keeps
                // the catalog, source lease, and clone intact.
                try
                {
                    var currentEntries = (EffectDef[])entriesField.GetValue(null);
                    var currentNameMap = (IDictionary)nameMapField.GetValue(null);
                    if (!candidate.CanRestoreTarget() || !ReferenceEquals(currentEntries, ownedEntries) ||
                        !ReferenceEquals(currentNameMap, ownedNameMap) || currentEntries.Length != nativeEntriesBaseline.Length ||
                        !EffectCatalog.availability.Equals(candidate.OwnedCatalogAvailability) ||
                        currentNameMap.Count != candidate.NativeNameMapBaseline.Count)
                        throw new InvalidOperationException("Catalog or target field ownership changed before setup rollback");
                    foreach (var pair in candidate.NativeNameMapBaseline)
                        if (!currentNameMap.Contains(pair.Key) || !Equals(currentNameMap[pair.Key], pair.Value))
                            throw new InvalidOperationException("Native effect name map changed before setup rollback");
                    for (int i = 0; i < currentEntries.Length; i++)
                    {
                        if (ReferenceEquals(currentEntries[i], nativeEntriesBaseline[i])) continue;
                        if (!mutationStates.Any(state => (int)state.RegisteredIndex == i &&
                                                   ReferenceEquals(state.definition, currentEntries[i])))
                            throw new InvalidOperationException("Foreign EffectDef replacement before setup rollback at index " + i);
                    }
                    if (mutationStates.Any(state => !state.IsOwnedCurrentValue()))
                        throw new InvalidOperationException("Composed definition changed before setup rollback");
                    if (priorComposedEffectSounds.Any(pair => pair.Key == null ||
                        (pair.Key.spawnSoundEventName != null && pair.Key.spawnSoundEventName != pair.Value)))
                        throw new InvalidOperationException("Composed audio metadata changed before setup rollback");
                }
                catch (Exception ownershipFailure)
                {
                    mercEvisImpactEffectLease = candidate;
                    ownedEffectMutationStates = mutationStates;
                    throw new AggregateException("Setup rollback refused; retain the exact catalog and source lease",
                                                 setupFailure, ownershipFailure);
                }

                candidate.RestoreTargetForRollback();
                foreach (var state in mutationStates.Reverse())
                    state.RestorePriorValues();
                foreach (var pair in priorComposedEffectSounds)
                    typeof(EffectDef).GetProperty("spawnSoundEventName").SetValue(pair.Key, pair.Value, null);
                entriesField.SetValue(null, priorEntries);
                nameMap.Clear();
                foreach (var pair in priorNames) nameMap.Add(pair.Key, pair.Value);
                EffectCatalog.availability = priorComposedEffectAvailability;
                priorComposedEffectSounds.Clear();
                if (candidate.OwnedEffectPrefab)
                    DestroyOwnedObject(candidate.OwnedEffectOwner);
                ClearOwnedComposedCatalogSnapshot();
                ownedEffectMutationStates = Array.Empty<EffectMutationState>();
                throw;
            }
        }
        void ClearOwnedComposedCatalogSnapshot()
        {
            ownedComposedEntries = null;
            ownedComposedNameMap = null;
            nativeComposedEntryBaseline = null;
            nativeComposedNameMapBaseline = null;
            ownedComposedAvailability = default(ResourceAvailability);
        }
        public void RegisterComposedEffects(System.Collections.Generic.IEnumerable<EffectDef> definitions)
        {
            if (definitions == null)
                throw new InvalidOperationException("Late composed effect registration has no definitions");
            var entries = (EffectDef[])PortSession.RewardField(typeof(EffectCatalog), "entries").GetValue(null);
            var nameMap = (IDictionary)PortSession.RewardField(typeof(EffectCatalog), "nameToEffectIndex").GetValue(null);
            if (!ComposedCatalogStructureStillOwned(entries, nameMap) ||
                ownedEffectMutationStates.Any(state => !state.IsOwnedCurrentValue()) ||
                priorComposedEffectSounds.Any(pair => pair.Key == null ||
                    (pair.Key.spawnSoundEventName != null && pair.Key.spawnSoundEventName != pair.Value)))
                throw new InvalidOperationException("Cannot add composed effects after catalog ownership changed");

            // Resolve and validate the whole request before writing. For a repeated
            // baked identity in this batch, preserve the supplied order; each
            // mutation snapshot is captured immediately before its own writes.
            var plans = new List<KeyValuePair<EffectDef, EffectIndex>>();
            foreach (var definition in definitions.ToArray())
            {
                if (definition == null || !definition.prefab || !definition.prefabEffectComponent ||
                    definition.prefabEffectComponent.gameObject != definition.prefab)
                    throw new InvalidOperationException("Late composed EffectDef has no exact prefab component");
                var index = EffectCatalog.FindEffectIndex(definition.prefabName);
                if (index == EffectIndex.Invalid || (int)index < 0 || (int)index >= entries.Length)
                    throw new InvalidOperationException("Original baked effect identity absent: " + definition.prefabName);
                bool slotOwned = ReferenceEquals(entries[(int)index], nativeComposedEntryBaseline[(int)index]) ||
                    ownedEffectMutationStates.Any(state => (int)state.RegisteredIndex == (int)index &&
                                                           ReferenceEquals(state.definition, entries[(int)index]));
                if (!slotOwned)
                    throw new InvalidOperationException("Foreign composed EffectDef occupies baked slot " + index);
                plans.Add(new KeyValuePair<EffectDef, EffectIndex>(definition, index));
            }

            foreach (var plan in plans)
            {
                var definition = plan.Key;
                var state = new EffectMutationState(definition);
                state.CaptureRegisteredIndex();
                if (state.RegisteredIndex != plan.Value)
                    throw new InvalidOperationException("Baked effect identity changed during late registration: " + definition.prefabName);
                // Publish ownership before the first mutation so a later failure
                // can only clean up through the ordinary strict teardown path.
                ownedEffectMutationStates = ownedEffectMutationStates.Concat(new[] { state }).ToArray();
                typeof(EffectDef).GetProperty("index").SetValue(definition, plan.Value, null);
                definition.prefabEffectComponent.effectIndex = plan.Value;
                entries[(int)plan.Value] = definition;
                AdaptComposedEffectAudio(definition);
            }
        }
        void RegisterComposedEffectsInitial(System.Collections.Generic.IEnumerable<EffectDef> definitions)
        {
            var entries = (EffectDef[])PortSession.RewardField(typeof(EffectCatalog), "entries").GetValue(null);
            foreach (var definition in definitions)
            {
                var index = EffectCatalog.FindEffectIndex(definition.prefabName);
                coordinator.Check(index != EffectIndex.Invalid && definition.prefabEffectComponent,
                                  "Original baked effect identity absent: " + definition.prefabName);
                typeof(EffectDef).GetProperty("index").SetValue(definition, index, null);
                definition.prefabEffectComponent.effectIndex = index;
                entries[(int)index] = definition;
                AdaptComposedEffectAudio(definition);
            }
        }
        public void RestoreComposedEffects(EffectDef[] previous)
        {
            var entries = (EffectDef[])PortSession.RewardField(typeof(EffectCatalog), "entries").GetValue(null);
            var nameMap = (IDictionary)PortSession.RewardField(typeof(EffectCatalog), "nameToEffectIndex").GetValue(null);
            if (mercEvisImpactEffectLease != null)
            {
                mercEvisImpactEffectLease.PreflightCleanup(entries);
                for (int i = 0; i < entries.Length; i++)
                {
                    if (ReferenceEquals(entries[i], mercEvisImpactEffectLease.NativeEntryBaseline[i]))
                        continue;
                    if (!ownedEffectMutationStates.Any(state => (int)state.RegisteredIndex == i &&
                                                              ReferenceEquals(state.definition, entries[i])))
                        throw new InvalidOperationException("Foreign composed EffectDef prevents Merc adapter teardown at index " + i);
                }
                if (ownedEffectMutationStates.Any(state => !state.IsOwnedCurrentValue()) ||
                    priorComposedEffectSounds.Any(pair => pair.Key == null ||
                        (pair.Key.spawnSoundEventName != null && pair.Key.spawnSoundEventName != pair.Value)))
                    throw new InvalidOperationException("Composed effect fields changed; retain Merc catalog and asset lease");
            }
            else if (!ComposedCatalogStructureStillOwned(entries, nameMap) ||
                     ownedEffectMutationStates.Any(state => !state.IsOwnedCurrentValue()) ||
                     priorComposedEffectSounds.Any(pair => pair.Key == null ||
                         (pair.Key.spawnSoundEventName != null && pair.Key.spawnSoundEventName != pair.Value)))
                throw new InvalidOperationException("Composed effect ownership changed; retain catalog state");
            // Restore only after every adapter/catalog/pool ownership check passes.
            if (mercEvisImpactEffectLease != null)
                mercEvisImpactEffectLease.RestoreBinding();
            foreach (var state in ownedEffectMutationStates.Reverse())
                state.RestorePriorValues();
            foreach (var pair in priorComposedEffectSounds)
                typeof(EffectDef).GetProperty("spawnSoundEventName").SetValue(pair.Key, pair.Value, null);
            priorComposedEffectSounds.Clear();
            if (coordinator.r.rewards != null)
                coordinator.r.rewards.effectSoundMetadataRestored = true;
            PortSession.RewardField(typeof(EffectCatalog), "entries").SetValue(null, previous);
            ((IDictionary)PortSession.RewardField(typeof(EffectCatalog), "nameToEffectIndex").GetValue(null)).Clear();
            EffectCatalog.availability = priorComposedEffectAvailability;
            if (mercEvisImpactEffectLease != null)
            {
                mercEvisImpactEffectLease.ReleaseAfterCatalogRestore();
                mercEvisImpactEffectLease = null;
            }
            ownedEffectMutationStates = Array.Empty<EffectMutationState>();
            ClearOwnedComposedCatalogSnapshot();
        }
        public BuffDef[] UpdatedComparisonBuffs(SessionConfig cfg)
        {
            if (!cfg.integratedWorld || !Resources.Load<TextAsset>("WholeCatalogBootstrap"))
                return new BuffDef[0];
            var definitions = WholeCatalogComposed.BuffDefinitions();
            // The current original DLC4 provider maps Buffs fields to "bd" + field name.
            // Definition registration supplies comparisons; it grants no buff or expansion.
            var fields = typeof(DLC4Content.Buffs).GetFields(BindingFlags.Public | BindingFlags.Static);
            var selected = fields.Select(field => definitions.SingleOrDefault(def => def.name == "bd" + field.Name)).ToArray();
            coordinator.Check(selected.All(def => def) && selected.Distinct().Count() == fields.Length,
                              "Current original comparison buff identities missing or ambiguous");
            for (int i = 0; i < fields.Length; i++)
                coordinator.BindEnemyDefinition(typeof(DLC4Content.Buffs), fields[i].Name, selected[i]);
            return selected;
        }
        public ItemDef[] UpdatedComparisonItems(SessionConfig cfg)
        {
            if (!cfg.integratedWorld || !Resources.Load<TextAsset>("WholeCatalogBootstrap"))
                return new ItemDef[0];
            var definitions = WholeCatalogComposed.ItemDefinitions();
            var fields = typeof(DLC4Content.Items).GetFields(BindingFlags.Public | BindingFlags.Static);
            var selected = fields.Select(field => definitions.SingleOrDefault(def => def.name == field.Name)).ToArray();
            coordinator.Check(selected.All(def => def) && selected.Distinct().Count() == fields.Length,
                              "Current original comparison item identities missing or ambiguous");
            for (int i = 0; i < fields.Length; i++)
                coordinator.BindEnemyDefinition(typeof(DLC4Content.Items), fields[i].Name, selected[i]);
            return selected;
        }
        public void RestoreBodySettingsTransform()
        {
            if (ownsBodySettingsTransform)
            {
                coordinator.Check(ReferenceEquals(Addressables.InternalIdTransformFunc, ownedBodySettingsTransform),
                                  "Owned settings transform replaced before cleanup");
                Addressables.InternalIdTransformFunc = priorBodySettingsTransform;
                coordinator.Check(ReferenceEquals(Addressables.InternalIdTransformFunc, priorBodySettingsTransform),
                                  "Prior settings transform did not restore");
                ownsBodySettingsTransform = false;
                priorBodySettingsTransform = null;
                ownedBodySettingsTransform = null;
                coordinator.r.catalogTransformRestored = true;
            }
        }
        public void Dispose()
        {
            CleanupLoadoutTables();
        }
    }
}
