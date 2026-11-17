using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Reflection;
using Newtonsoft.Json.Linq;
using UnityEditor;
using UnityEditor.Animations;
using UnityEngine;
using UnityEngine.AddressableAssets;
using UnityEngine.AddressableAssets.Initialization;
using UnityEngine.AddressableAssets.ResourceLocators;
using UnityEngine.AddressableAssets.ResourceProviders;
using UnityEngine.ResourceManagement.AsyncOperations;
using UnityEngine.ResourceManagement.ResourceProviders;

// Only the editor substitutes AssetDatabase for the Android bundle provider.
public static class WholeCatalogHost
{
    public static object AuditBodyAnimations(string manifestPath, string outputPath)
    {
        RequireIdleEditor();
        var manifest = JObject.Parse(File.ReadAllText(manifestPath));
        var locations = manifest["locations"].ToDictionary(row => (int)row["id"], row => (string)row["path"]);
        var addresses = new AnimationAddresses(manifest, locations);
        var errors = new JArray();
        var survivors = new JArray();
        var survivorBodies = new HashSet<GameObject>();
        foreach (string path in FamilyPaths(manifest, locations, "SurvivorDef"))
        {
            var survivor = AssetDatabase.LoadAssetAtPath<RoR2.SurvivorDef>(path);
            var body = survivor ? survivor.bodyPrefab : null;
            if (body)
                survivorBodies.Add(body);
            else
                errors.Add(path + ": missing typed SurvivorDef/body prefab");
            survivors.Add(new JObject { ["definition"] = path, ["body"] = AssetPath(body) });
        }
        var bodies = new JArray();
        var seen = new HashSet<GameObject>();
        foreach (string path in FamilyPaths(manifest, locations, "CharacterBody"))
        {
            var root = AssetDatabase.LoadAssetAtPath<GameObject>(path);
            var body = root ? root.GetComponent<RoR2.CharacterBody>() : null;
            if (!body)
            {
                errors.Add(path + ": missing typed CharacterBody prefab");
                continue;
            }
            seen.Add(root);
            var issues = new JArray();
            var locator = root.GetComponent<RoR2.ModelLocator>();
            var model = locator ? locator.modelTransform : null;
            bool survivor = survivorBodies.Contains(root);
            if (survivor && !model)
                issues.Add("Survivor model locator has no model");
            var animators = new JArray();
            var controllers = new Dictionary<Animator, RuntimeAnimatorController>();
            foreach (var animator in root.GetComponentsInChildren<Animator>(true))
            {
                string objectPath = HierarchyPath(animator.transform);
                var skin = animator.GetComponent<RoR2.ModelSkinController>();
                var serialized = skin ? new SerializedObject(skin) : null;
                var controller = addresses.Inspect(serialized, "_animatorControllerAddress", animator.runtimeAnimatorController,
                                                   skin ? skin._animatorController : null, out var controllerBinding);
                var avatar = addresses.Inspect(serialized, "_avatarAddress", animator.avatar, skin ? skin._avatar : null,
                                               out var avatarBinding);
                if ((string)controllerBinding["addressStatus"] == "unresolved")
                    issues.Add(objectPath + ": unresolved controller address");
                if ((string)avatarBinding["addressStatus"] == "unresolved")
                    issues.Add(objectPath + ": unresolved avatar address");
                controllers.Add(animator, controller);
                var skins = new JArray();
                var visitedSkins = new HashSet<RoR2.SkinDef>();
                if (skin && skin.skins != null)
                    foreach (var definition in skin.skins)
                        InspectAnimationSkin(definition, addresses, visitedSkins, skins, issues);
                var clips = controller ? controller.animationClips.Where(clip => clip).Distinct().ToArray() : Array.Empty<AnimationClip>();
                var events = InspectClipEvents(animator, clips);
                var missingReceivers = events.Where(row => (bool)row["receiverRequired"] && !(bool)row["receiverPresent"])
                    .Select(row => (string)row["function"]).Distinct().ToArray();
                if (missingReceivers.Length != 0)
                    issues.Add(objectPath + ": missing required clip-event receivers: " + string.Join(", ", missingReceivers));
                animators.Add(new JObject { ["object"] = objectPath, ["enabled"] = animator.enabled,
                                            ["controller"] = controllerBinding, ["avatar"] = avatarBinding,
                                            ["avatarValid"] = avatar ? new JValue(avatar.isValid) : JValue.CreateNull(),
                                            ["skins"] = skins, ["clips"] = clips.Length, ["events"] = events });
            }
            var machines = new JArray();
            foreach (var machine in root.GetComponentsInChildren<RoR2.EntityStateMachine>(true))
                machines.Add(new JObject { ["object"] = HierarchyPath(machine.transform), ["name"] = machine.customName,
                                           ["initial"] = InspectState(machine, "initial", machine.initialStateType, issues),
                                           ["main"] = InspectState(machine, "main", machine.mainStateType, issues) });
            var aims = new JArray();
            foreach (var aim in root.GetComponentsInChildren<RoR2.AimAnimator>(true))
                aims.Add(InspectAim(body, locator, aim, controllers, issues));
            foreach (string issue in issues.Values<string>())
                errors.Add(path + ": " + issue);
            bodies.Add(new JObject { ["path"] = path, ["survivor"] = survivor, ["model"] = HierarchyPath(model),
                                     ["aimOrigin"] = HierarchyPath(body.aimOriginTransform), ["animators"] = animators,
                                     ["stateMachines"] = machines, ["aim"] = aims });
        }
        foreach (var body in survivorBodies.Except(seen))
            errors.Add(AssetPath(body) + ": survivor body outside the native CharacterBody family");
        if (bodies.Count == 0 || survivors.Count == 0)
            errors.Add("Native body or survivor family is empty");
        File.WriteAllText(outputPath, new JObject { ["survivors"] = survivors, ["bodies"] = bodies, ["errors"] = errors }.ToString());
        return new { bodies = bodies.Count, survivors = survivors.Count, errors = errors.Count, output = outputPath };
    }

    static IEnumerable<string> FamilyPaths(JObject manifest, Dictionary<int, string> locations, string category)
    {
        return WholeCatalogComposed.FamilyLocationGroups(manifest, category).SelectMany(group => group)
            .Select(id => locations[id]).Distinct(StringComparer.Ordinal);
    }

    static string AssetPath(UnityEngine.Object asset)
    {
        return asset ? AssetDatabase.GetAssetPath(asset) : null;
    }

    static string HierarchyPath(Transform transform)
    {
        if (!transform)
            return null;
        var parts = new List<string>();
        for (var node = transform; node; node = node.parent)
            parts.Add(node.name + "[" + node.GetSiblingIndex() + "]");
        parts.Reverse();
        return string.Join("/", parts);
    }

    // Use the manifest's string keys and typed prepared assets without starting Addressables.
    sealed class AnimationAddresses
    {
        readonly Dictionary<string, string[]> paths;

        public AnimationAddresses(JObject manifest, Dictionary<int, string> locations)
        {
            paths = manifest["keys"].Where(row => row["keyType"] == null || (string)row["keyType"] == "System.String")
                .ToDictionary(row => (string)row["key"],
                              row => row["locations"].Values<int>().Where(locations.ContainsKey).Select(id => locations[id])
                                  .Distinct(StringComparer.Ordinal).ToArray());
        }

        public T Inspect<T>(SerializedObject owner, string field, T animator, T direct, out JObject binding) where T : UnityEngine.Object
        {
            var address = owner?.FindProperty(field);
            string key = address?.FindPropertyRelative("m_AssetGUID")?.stringValue;
            string subobject = address?.FindPropertyRelative("m_SubObjectName")?.stringValue;
            var deferred = Resolve<T>(key, subobject);
            var resolved = animator ? animator : !string.IsNullOrEmpty(key) ? deferred : direct;
            binding = new JObject { ["animator"] = AssetPath(animator), ["direct"] = AssetPath(direct), ["key"] = key,
                                    ["subobject"] = subobject, ["address"] = AssetPath(deferred), ["effective"] = AssetPath(resolved),
                                    ["addressStatus"] = string.IsNullOrEmpty(key) ? "empty" : deferred ? "resolved" : "unresolved" };
            return resolved;
        }

        T Resolve<T>(string key, string subobject) where T : UnityEngine.Object
        {
            if (string.IsNullOrEmpty(key))
                return null;
            bool named = !string.IsNullOrEmpty(subobject);
            if ((!named || !paths.TryGetValue(key + "[" + subobject + "]", out var candidates)) &&
                !paths.TryGetValue(key, out candidates))
                return null;
            var matches = candidates
                .SelectMany(path => named ? AssetDatabase.LoadAllAssetsAtPath(path).OfType<T>().Where(asset => asset.name == subobject)
                                          : new[] { AssetDatabase.LoadAssetAtPath<T>(path) })
                .Where(asset => asset).Distinct().Take(2).ToArray();
            return matches.Length == 1 ? matches[0] : null;
        }
    }

    static void InspectAnimationSkin(RoR2.SkinDef skin, AnimationAddresses addresses, HashSet<RoR2.SkinDef> visited, JArray rows,
                                     JArray issues)
    {
        if (!skin)
        {
            issues.Add("Missing SkinDef in model's skin chain");
            return;
        }
        if (!visited.Add(skin))
            return;
        addresses.Inspect(new SerializedObject(skin), "skinDefParamsAddress", null, skin.skinDefParams, out var parameters);
        if ((string)parameters["addressStatus"] == "unresolved")
            issues.Add(AssetPath(skin) + ": unresolved SkinDefParams address");
        rows.Add(new JObject { ["skin"] = AssetPath(skin), ["root"] = AssetPath(skin.rootObject), ["parameters"] = parameters });
        foreach (var parent in skin.baseSkins ?? Array.Empty<RoR2.SkinDef>())
            InspectAnimationSkin(parent, addresses, visited, rows, issues);
    }

    static JObject InspectState(RoR2.EntityStateMachine machine, string slot, EntityStates.SerializableEntityStateType state, JArray issues)
    {
        var type = state.stateType;
        if (!string.IsNullOrEmpty(state.typeName) && (type == null || type.IsAbstract))
            issues.Add(machine.customName + ": " + slot + " state does not resolve to a concrete type: " + state.typeName);
        return new JObject { ["configured"] = state.typeName, ["type"] = type?.FullName };
    }

    static JObject InspectAim(RoR2.CharacterBody body, RoR2.ModelLocator locator, RoR2.AimAnimator aim,
                              Dictionary<Animator, RuntimeAnimatorController> controllers, JArray issues)
    {
        var animator = aim.GetComponent<Animator>();
        // Read the prefab links used to initialize the native caches on activation.
        if (!animator && locator && (aim.gameObject == body.gameObject || aim.GetComponent<RoR2.CharacterModel>()))
            animator = locator.forcedAnimatorAtStart ? locator.forcedAnimatorAtStart :
                locator.modelTransform ? locator.modelTransform.GetComponent<Animator>() : null;
        RuntimeAnimatorController controller = null;
        if (animator)
            controllers.TryGetValue(animator, out controller);
        while (controller is AnimatorOverrideController wrapper)
            controller = wrapper.runtimeAnimatorController;
        var imported = controller as AnimatorController;
        var required = aim.enableAimWeight ? new[] { "aimPitchCycle", "aimYawCycle", "aimWeight" } : new[] { "aimPitchCycle", "aimYawCycle" };
        var parameters = imported ? imported.parameters : Array.Empty<AnimatorControllerParameter>();
        var missing = required.Where(name => !parameters.Any(parameter => parameter.name == name &&
                                                                 parameter.type == AnimatorControllerParameterType.Float)).ToArray();
        string objectPath = HierarchyPath(aim.transform);
        bool input = aim.inputBank && aim.inputBank == body.GetComponent<RoR2.InputBankTest>();
        bool direction = aim.directionComponent && aim.directionComponent == body.GetComponent<RoR2.CharacterDirection>();
        // Native aim falls back to the model's forward direction when its input bank is absent.
        // The serialized direction component is optional.
        if (aim.enabled && ((aim.inputBank && !input) || (aim.directionComponent && !direction)))
            issues.Add(objectPath + ": configured aim links point outside the body's input or direction component");
        if (aim.enabled && missing.Length != 0)
            issues.Add(objectPath + ": missing aim float parameters: " + string.Join(", ", missing));
        return new JObject { ["object"] = objectPath, ["enabled"] = aim.enabled, ["mode"] = aim.aimType.ToString(),
                             ["animator"] = animator ? HierarchyPath(animator.transform) : null,
                             ["inputBank"] = aim.inputBank ? HierarchyPath(aim.inputBank.transform) : null,
                             ["directionComponent"] = aim.directionComponent ? HierarchyPath(aim.directionComponent.transform) : null,
                             ["inputBankMatches"] = input, ["directionMatches"] = direction, ["missingFloats"] = new JArray(missing),
                             ["layers"] = new JArray(imported ? imported.layers.Select(layer => layer.name).ToArray() : Array.Empty<string>()) };
    }

    static JArray InspectClipEvents(Animator animator, AnimationClip[] clips)
    {
        var rows = new JArray();
        if (clips.Length == 0)
            return rows;
        var methods = animator.GetComponents<MonoBehaviour>().Where(component => component)
            .SelectMany(component => component.GetType().GetMethods(BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic))
            .ToLookup(method => method.Name, StringComparer.Ordinal);
        foreach (var clip in clips)
            foreach (var animationEvent in AnimationUtility.GetAnimationEvents(clip))
            {
                bool receiver = methods[animationEvent.functionName].Any(method => AcceptsAnimationEvent(method, animationEvent));
                rows.Add(new JObject { ["clip"] = clip.name, ["path"] = AssetPath(clip), ["time"] = animationEvent.time,
                                       ["function"] = animationEvent.functionName, ["receiverPresent"] = receiver,
                                       ["receiverRequired"] = animationEvent.messageOptions == SendMessageOptions.RequireReceiver });
            }
        return rows;
    }

    static bool AcceptsAnimationEvent(MethodInfo method, AnimationEvent animationEvent)
    {
        if (method.IsGenericMethod || method.ReturnType != typeof(void))
            return false;
        var parameters = method.GetParameters();
        if (parameters.Length != 1)
            return parameters.Length == 0;
        var type = parameters[0].ParameterType;
        return type == typeof(AnimationEvent) || type == typeof(string) || type == typeof(float) || type == typeof(int) ||
               type.IsEnum || (typeof(UnityEngine.Object).IsAssignableFrom(type) &&
                               (!animationEvent.objectReferenceParameter || type.IsInstanceOfType(animationEvent.objectReferenceParameter)));
    }

    static void RequireIdleEditor()
    {
        if (EditorApplication.isCompiling || EditorApplication.isUpdating || EditorUtility.scriptCompilationFailed ||
            EditorApplication.isPlayingOrWillChangePlaymode || BuildPipeline.isBuildingPlayer || stack.Count != 0)
            throw new Exception("Editor busy or source not compiled");
    }

    // Current exact-editor inventory; published membership is the native provider policy.
    // This inspects imported assets and resource coverage, never claims Android rendering.
    public static object AuditCombatMaterials(string manifestPath, string outputPath)
    {
        RequireIdleEditor();
        var manifest = JObject.Parse(File.ReadAllText(manifestPath));
        var locations = manifest["locations"].ToDictionary(row => (int)row["id"]);
        var roots = new JArray();
        var rows = new JArray();
        var errors = new JArray();
        var candidates = new JArray();
        foreach (var category in new[] { "CharacterBody", "Projectile" })
        {
            var groups = WholeCatalogComposed.FamilyLocationGroups(manifest, category);
            for (int provider = 0; provider < groups.Length; provider++)
                foreach (int id in groups[provider])
                {
                    var candidate = (JObject)locations[id].DeepClone();
                    candidate["category"] = category;
                    candidate["provider"] = provider;
                    candidates.Add(candidate);
                }
        }
        // The lab publishes effects from its session config, independently of the
        // catalog's Effect label. Inspect precisely those registered source prefabs.
        var config = Resources.Load<TextAsset>("MovementBatchProbe");
        if (!config)
            throw new Exception("Current lab session config missing");
        foreach (var path in JObject.Parse(config.text)["objectiveEffectAssets"].Values<string>().Distinct())
            candidates.Add(new JObject { ["id"] = -1, ["path"] = path, ["category"] = "RegisteredEffect", ["provider"] = -1 });
        foreach (JObject location in candidates)
        {
            string category = (string)location["category"];
            int provider = (int)location["provider"], id = (int)location["id"];
            string path = (string)location["path"];
            var root = AssetDatabase.LoadAssetAtPath<GameObject>(path);
            roots.Add(new JObject { ["category"] = category, ["provider"] = provider, ["location"] = id, ["path"] = path,
                                    ["loaded"] = (bool)root });
            if (!root)
            {
                errors.Add("Typed prefab missing: " + category + "/" + path);
                continue;
            }
            foreach (var renderer in root.GetComponentsInChildren<Renderer>(true))
            {
                var hierarchy = new List<string>();
                for (var node = renderer.transform; node; node = node.parent)
                    hierarchy.Add(node.name + "[" + node.GetSiblingIndex() + "]");
                hierarchy.Reverse();
                var particle = renderer as ParticleSystemRenderer;
                var streams = new List<ParticleSystemVertexStream>();
                if (particle)
                    particle.GetActiveVertexStreams(streams);
                var materials = renderer.sharedMaterials;
                for (int slot = 0; slot < materials.Length; slot++)
                    AddCombatMaterial(rows, id, category, path, renderer, hierarchy, particle, streams, "sharedMaterials", slot,
                                      materials[slot]);
                foreach (var model in root.GetComponentsInChildren<RoR2.CharacterModel>(true))
                    foreach (var info in model.baseRendererInfos.Where(info => info.renderer == renderer))
                    {
                        var row = AddCombatMaterial(rows, id, category, path, renderer, hierarchy, particle, streams,
                                                    "CharacterModel.defaultMaterial", 0, info.defaultMaterial);
                        row["materialAddress"] =
                            info.defaultMaterialAddress == null ? null : Convert.ToString(info.defaultMaterialAddress.RuntimeKey);
                    }
                var billboard = renderer as BillboardRenderer;
                if (billboard && billboard.billboard)
                    AddCombatMaterial(rows, id, category, path, renderer, hierarchy, particle, streams, "billboard.material", 0,
                                      billboard.billboard.material);
                if (particle && particle.trailMaterial)
                    AddCombatMaterial(rows, id, category, path, renderer, hierarchy, particle, streams, "trailMaterial", 0,
                                      particle.trailMaterial);
                if (materials.Length == 0 && !(billboard && billboard.billboard))
                    AddCombatMaterial(rows, id, category, path, renderer, hierarchy, particle, streams, "sharedMaterials", -1, null);
            }
        }
        var result = new JObject {
            ["scope"] =
                "Native-provider body/projectile candidates before per-provider name deduplication, plus current lab registered effects; resource coverage only; Android rendering and reference comparison remain open",
            ["roots"] = roots, ["slots"] = rows, ["errors"] = errors,
            ["surfaceObservationContract"] = VerifySurfaceMaterialObservation()
        };
        File.WriteAllText(outputPath, result.ToString());
        return new { roots = roots.Count, slots = rows.Count, errors = errors.Count, output = outputPath };
    }
    static JObject VerifySurfaceMaterialObservation()
    {
        // Exercise the actual runtime observer against live Unity material state.
        // No session, catalog, scene or presentation adapter is initialized.
        var type = typeof(PortSession).GetNestedType("TeleporterWorldSession", System.Reflection.BindingFlags.NonPublic);
        var observer = Activator.CreateInstance(type, new object[] { null });
        var method = type.GetMethod("ObserveSurfaceMaterial");
        var material = new Material(Shader.Find("Standard"));
        var texture = new Texture2D(2, 2) { name = "Authored census fixture texture" };
        try
        {
            material.name = "Authored census fixture material";
            material.renderQueue = 3123;
            material.SetTexture("_MainTex", texture);
            material.SetTextureScale("_MainTex", new Vector2(2, 3));
            material.EnableKeyword("_EMISSION");
            var row = (PortSession.SurfaceMaterialObservation)method.Invoke(observer, new object[] { material });
            var main = row.properties.Single(property => property.name == "_MainTex");
            if (row.material != material.name || row.shader != material.shader.name || row.queue != 3123 ||
                row.supported != material.shader.isSupported || !row.keywords.Contains("_EMISSION") ||
                main.textureId != texture.GetInstanceID() || main.width != 2 || main.height != 2 ||
                main.scale != new Vector2(2, 3) || material.GetTexture("_MainTex") != texture || material.renderQueue != 3123 ||
                method.Invoke(observer, new object[] { null }) != null)
                throw new Exception("Live surface material observation contract failed");
            return new JObject { ["liveMaterialState"] = true, ["nullSlot"] = true, ["sourceUnchanged"] = true };
        }
        finally
        {
            UnityEngine.Object.DestroyImmediate(material);
            UnityEngine.Object.DestroyImmediate(texture);
        }
    }
    static JObject AddCombatMaterial(JArray rows, int id, string category, string root, Renderer renderer, List<string> hierarchy,
                                     ParticleSystemRenderer particle, List<ParticleSystemVertexStream> streams, string binding, int slot,
                                     Material material)
    {
        var textures = new JArray();
        var meshes = particle ? new Mesh[particle.meshCount] : new Mesh[0];
        if (particle)
            particle.GetMeshes(meshes);
        if (material && material.shader)
            foreach (var name in material.GetTexturePropertyNames())
            {
                var texture = material.GetTexture(name);
                textures.Add(new JObject { ["property"] = name, ["name"] = texture ? texture.name : null,
                                           ["path"] = texture ? AssetDatabase.GetAssetPath(texture) : null });
            }
        var row =
            new JObject { ["location"] = id,
                          ["category"] = category,
                          ["root"] = root,
                          ["renderer"] = string.Join("/", hierarchy),
                          ["kind"] = renderer.GetType().Name,
                          ["component"] = Array.IndexOf(renderer.GetComponents<Renderer>(), renderer),
                          ["binding"] = binding,
                          ["slot"] = slot,
                          ["active"] = renderer.gameObject.activeSelf,
                          ["enabled"] = renderer.enabled,
                          ["material"] = material ? AssetDatabase.GetAssetPath(material) : null,
                          ["shader"] = material && material.shader ? material.shader.name : null,
                          ["keywords"] = new JArray(material ? material.shaderKeywords.OrderBy(key => key, StringComparer.Ordinal).ToArray()
                                                             : new string[0]),
                          ["queue"] = material ? material.renderQueue : -1,
                          ["textures"] = textures,
                          ["particleMode"] = particle ? particle.renderMode.ToString() : null,
                          ["particleMesh"] = particle && particle.mesh ? AssetDatabase.GetAssetPath(particle.mesh) : null,
                          ["particleMeshes"] = new JArray(meshes.Select(mesh => mesh ? AssetDatabase.GetAssetPath(mesh) : null)),
                          ["vertexStreams"] = new JArray(streams.Select(stream => stream.ToString())),
                          ["mapping"] = CombatMaterialMapping(material) };
        rows.Add(row);
        return row;
    }
    static JObject CombatMaterialMapping(Material material)
    {
        if (!material || !material.shader)
            return new JObject { ["outcome"] = "missing-material-or-shader" };
        string shader = material.shader.name;
        var standard = Resources.Load<TextAsset>("AndroidNativeStandardVariants");
        var families = Resources.Load<TextAsset>("AndroidNativeMaterialFamilies");
        JObject family = null;
        if (shader == "Hopoo Games/Deferred/Standard" && standard)
            family = JObject.Parse(standard.text);
        else if (families)
            family = JObject.Parse(families.text)["families"].OfType<JObject>().SingleOrDefault(row => (string)row["shader"] == shader);
        if (family != null)
        {
            var keys = family["features"].Values<string>().Where(key => material.IsKeywordEnabled(key)).OrderBy(key => key).ToArray();
            var variant =
                family["variants"].SingleOrDefault(row => row["keywords"].Values<string>().OrderBy(key => key).SequenceEqual(keys));
            string resource = variant == null ? null : (string)variant["resource"];
            var recovered = resource == null ? null : Resources.Load<Shader>(resource);
            return new JObject { ["outcome"] = recovered ? "recovered-resource-present" : "known-family-missing-resource-or-variant",
                                 ["features"] = new JArray(keys), ["resource"] = resource,
                                 ["editorSupported"] = recovered && recovered.isSupported };
        }
        bool nativeParticle = shader == "Mobile/Particles/Alpha Blended" || shader == "Particles/Standard Unlit" ||
                              shader == "Legacy Shaders/Particles/Additive" || shader == "Legacy Shaders/Particles/Additive (Soft)";
        return new JObject { ["outcome"] = nativeParticle ? "native-unity-particle" : "separate-or-approximate-path",
                             ["editorSupported"] = material.shader.isSupported };
    }
    sealed class ImportedAssetProvider : ResourceProviderBase
    {
        public override void Provide(ProvideHandle handle)
        {
            try
            {
                var asset = AssetDatabase.LoadAssetAtPath(handle.Location.InternalId, handle.Type);
                if (!asset)
                    throw new Exception("Typed import missing: " + handle.Location.InternalId + " [" + handle.Type + "]");
                handle.Complete<UnityEngine.Object>(asset, true, null);
            }
            catch (Exception e)
            {
                WholeCatalogLoader.failures.Add(e.ToString());
                handle.Complete<UnityEngine.Object>(null, false, e);
            }
        }
    }
    static readonly Stack<IEnumerator> stack = new Stack<IEnumerator>();
    static string output;
    static AsyncOperationHandle? waiting;
    static double deadline;
    static void Log(string message, string trace, LogType kind)
    {
        if (kind == LogType.Error || kind == LogType.Exception || kind == LogType.Assert)
            WholeCatalogLoader.failures.Add(message + "\n" + trace);
    }
    static IEnumerator LoadAndInitialize(JObject manifest)
    {
        yield return WholeCatalogLoader.Load(manifest, typeof(ImportedAssetProvider).FullName);
        if (WholeCatalogLoader.failures.Count != 0)
            throw new Exception("Original provider loading reported errors");
        yield return WholeCatalogLoader.InitializeCatalogs();
    }
    public static void Begin(string manifestPath, string outputPath)
    {
        if (EditorApplication.isCompiling || EditorApplication.isUpdating || EditorApplication.isPlayingOrWillChangePlaymode ||
            UnityEditor.BuildPipeline.isBuildingPlayer || stack.Count != 0)
            throw new Exception("Editor busy");
        output = outputPath;
        deadline = EditorApplication.timeSinceStartup + 240;
        waiting = null;
        var directory = Path.GetDirectoryName(output);
        var catalog = Path.Combine(directory, "host-empty-catalog.json");
        var settings = Path.Combine(directory, "host-settings.json");
        File.WriteAllText(
            catalog,
            "{\"m_LocatorId\":\"whole-host-init\",\"m_ProviderIds\":[],\"m_InternalIds\":[],\"m_KeyDataString\":\"AAAAAA==\",\"m_BucketDataString\":\"AAAAAA==\",\"m_EntryDataString\":\"AAAAAA==\",\"m_ExtraDataString\":\"\",\"m_resourceTypes\":[]}");
        var settingsData = new ResourceManagerRuntimeData { BuildTarget = "Android", DisableCatalogUpdateOnStartup = true,
                                                            LogResourceManagerExceptions = true };
        settingsData.CatalogLocations.Add(new ResourceLocationData(new[] { ResourceManagerRuntimeData.kCatalogAddress }, catalog,
                                                                   typeof(ContentCatalogProvider), typeof(ContentCatalogData)));
        File.WriteAllText(settings, JsonUtility.ToJson(settingsData));
        string original = Addressables.RuntimePath + "/settings.json";
        Addressables.InternalIdTransformFunc = location => location.InternalId == original ? settings : location.InternalId;
        Addressables.ResourceManager.ResourceProviders.Add(new ImportedAssetProvider());
        stack.Push(LoadAndInitialize(JObject.Parse(File.ReadAllText(manifestPath))));
        Application.logMessageReceived += Log;
        EditorApplication.update += Tick;
    }
    static void Save(bool success, string error = null)
    {
        var text = Newtonsoft.Json.JsonConvert.SerializeObject(
            new { success, finished = stack.Count == 0 || error != null, phase = WholeCatalogLoader.phase,
                  progress = WholeCatalogLoader.progress, error, failures = WholeCatalogLoader.failures,
                  counts = WholeCatalogLoader.Counts() },
            Newtonsoft.Json.Formatting.Indented);
        File.WriteAllText(output + ".pending", text);
        if (File.Exists(output))
            File.Replace(output + ".pending", output, null);
        else
            File.Move(output + ".pending", output);
    }
    static void Tick()
    {
        try
        {
            // The preserved package's editor scheduler is internal, unlike newer APIs.
            typeof(UnityEngine.ResourceManagement.ResourceManager)
                .GetMethod("Update", System.Reflection.BindingFlags.Instance | System.Reflection.BindingFlags.NonPublic)
                .Invoke(Addressables.ResourceManager, new object[] { 0.016f });
            if (EditorApplication.timeSinceStartup > deadline)
                throw new TimeoutException("Original provider phase stalled");
            if (waiting.HasValue)
            {
                if (!waiting.Value.IsDone)
                    return;
                waiting = null;
            }
            for (int i = 0; i < 100 && stack.Count != 0; i++)
            {
                var top = stack.Peek();
                if (!top.MoveNext())
                {
                    stack.Pop();
                    continue;
                }
                var child = top.Current as IEnumerator;
                if (child != null)
                {
                    stack.Push(child);
                    continue;
                }
                if (top.Current is AsyncOperationHandle)
                {
                    waiting = (AsyncOperationHandle)top.Current;
                    break;
                }
                break;
            }
            if (stack.Count == 0)
            {
                Save(WholeCatalogLoader.failures.Count == 0);
                EditorApplication.update -= Tick;
                Application.logMessageReceived -= Log;
            }
            else
                Save(false);
        }
        catch (Exception e)
        {
            Save(false, e.ToString());
            stack.Clear();
            EditorApplication.update -= Tick;
            Application.logMessageReceived -= Log;
            Debug.LogException(e);
        }
    }
}
