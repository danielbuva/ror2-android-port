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
        var addresses = new CatalogAddresses(manifest, locations);
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
    sealed class CatalogAddresses
    {
        readonly Dictionary<string, string[]> paths;

        public CatalogAddresses(JObject manifest, Dictionary<int, string> locations)
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

        public T Resolve<T>(string key, string subobject = null) where T : UnityEngine.Object
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

    static void InspectAnimationSkin(RoR2.SkinDef skin, CatalogAddresses addresses, HashSet<RoR2.SkinDef> visited, JArray rows,
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
        var addresses = new CatalogAddresses(manifest, locations.ToDictionary(row => row.Key, row => (string)row.Value["path"]));
        var roots = new JArray();
        var rows = new JArray();
        var errors = new JArray();
        var families = new Dictionary<string, JObject>(StringComparer.Ordinal);
        var otherFamilies = Resources.Load<TextAsset>("AndroidNativeMaterialFamilies");
        if (otherFamilies)
            foreach (var family in JObject.Parse(otherFamilies.text)["families"].OfType<JObject>())
                families.Add((string)family["shader"], family);
        var standard = Resources.Load<TextAsset>("AndroidNativeStandardVariants");
        if (standard)
            families["Hopoo Games/Deferred/Standard"] = JObject.Parse(standard.text);
        var materialMappings = new Dictionary<Material, JObject>();
        JObject Mapping(Material material)
        {
            if (!material)
                return CombatMaterialMapping(material, families);
            if (!materialMappings.TryGetValue(material, out var mapping))
            {
                mapping = CombatMaterialMapping(material, families);
                materialMappings.Add(material, mapping);
            }
            return mapping;
        }

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

        JToken Location(string file) => locations.Values.Single(row => ((string)row["path"]).EndsWith("/" + file, StringComparison.Ordinal));
        var candidatePaths = new HashSet<string>(candidates.Select(row => (string)row["path"]), StringComparer.Ordinal);
        var locationByPath = locations.Values.ToLookup(row => (string)row["path"], StringComparer.Ordinal);
        void Include(string path, string category)
        {
            if (candidatePaths.Add(path))
            {
                var location = locationByPath[path].FirstOrDefault();
                candidates.Add(new JObject { ["id"] = (int?)location?["id"] ?? -1, ["path"] = path, ["category"] = category,
                                             ["provider"] = -1 });
            }
        }

        // These source effects are acquired outside the registered effect list.
        Include((string)Location("MercExposeEffect.prefab")["path"], "DirectEffect");
        Include((string)Location("CrocoDiseaseImpactEffect.prefab")["path"], "DirectEffect");
        var ghostBindings = new Dictionary<string, JObject>(StringComparer.Ordinal);
        var impactBindings = new JArray();
        void InspectProjectileGhost(GameObject prefab, string path)
        {
            var projectile = prefab ? prefab.GetComponent<RoR2.Projectile.ProjectileController>() : null;
            if (!projectile)
            {
                ghostBindings[path] = new JObject { ["projectile"] = path, ["status"] = "missing-controller" };
                errors.Add(path + ": missing typed ProjectileController");
                return;
            }
            var ghost = addresses.Inspect(new SerializedObject(projectile), "ghostPrefabAddress", null, projectile.ghostPrefab,
                                          out var binding);
            binding["projectile"] = path;
            ghostBindings[path] = binding;
            string ghostPath = (string)binding["effective"];
            // The native controller creates the visual even when it has no follower component.
            binding["ghostControllerPresent"] = ghost && ghost.GetComponent<RoR2.Projectile.ProjectileGhostController>();
            if (!string.IsNullOrEmpty(ghostPath))
            {
                binding["status"] = "resolved";
                Include(ghostPath, "ProjectileGhost");
            }
            else if (!ghost && (string)binding["addressStatus"] == "empty" && !projectile.ghostPrefab)
                binding["status"] = "unassigned";
            else
            {
                binding["status"] = "invalid";
                errors.Add(path + ": invalid typed projectile ghost binding");
            }
        }

        string IncludeImpactEffect(GameObject effect, string projectilePath)
        {
            if (!effect)
                return null;
            string path = AssetPath(effect);
            if (string.IsNullOrEmpty(path))
                errors.Add(projectilePath + ": projectile impact effect asset path missing for " + effect.name);
            else
                Include(path, "ProjectileImpactEffect");
            return path;
        }

        void InspectProjectileImpacts(GameObject prefab, string path)
        {
            foreach (var impact in prefab.GetComponentsInChildren<RoR2.Projectile.ProjectileImpactExplosion>(true))
            {
                string impactEffect = IncludeImpactEffect(impact.impactEffect, path);
                string explosionEffect = IncludeImpactEffect(impact.explosionEffect, path);
                impactBindings.Add(new JObject {
                    ["projectile"] = path,
                    ["component"] = HierarchyPath(impact.transform),
                    ["impactEffect"] = impactEffect,
                    ["explosionEffect"] = explosionEffect,
                    ["detonationEffect"] = impactEffect ?? explosionEffect,
                    ["expiredEffect"] = IncludeImpactEffect(impact.expiredEffect, path),
                    ["blastImpactEffect"] = IncludeImpactEffect(impact.blastImpactEffect, path)
                });
            }
        }

        // Projectile edges append unique visual roots for the same slot census.
        for (int i = 0; i < candidates.Count; i++)
        {
            var location = candidates[i];
            string category = (string)location["category"];
            int provider = (int)location["provider"], id = (int)location["id"];
            string path = (string)location["path"];
            var root = AssetDatabase.LoadAssetAtPath<GameObject>(path);
            roots.Add(new JObject { ["category"] = category, ["provider"] = provider, ["location"] = id, ["path"] = path,
                                    ["loaded"] = (bool)root });
            if (category == "Projectile")
                InspectProjectileGhost(root, path);
            if (!root)
            {
                errors.Add("Typed prefab missing: " + category + "/" + path);
                continue;
            }
            if (category == "Projectile")
                InspectProjectileImpacts(root, path);
            foreach (var renderer in root.GetComponentsInChildren<Renderer>(true))
            {
                var hierarchy = HierarchyPath(renderer.transform);
                var particle = renderer as ParticleSystemRenderer;
                var streams = new List<ParticleSystemVertexStream>();
                if (particle)
                    particle.GetActiveVertexStreams(streams);
                var materials = renderer.sharedMaterials;
                for (int slot = 0; slot < materials.Length; slot++)
                    AddCombatMaterial(rows, Mapping, id, category, path, renderer, hierarchy, particle, streams, "sharedMaterials", slot,
                                      materials[slot]);
                foreach (var model in root.GetComponentsInChildren<RoR2.CharacterModel>(true))
                    foreach (var info in model.baseRendererInfos.Where(info => info.renderer == renderer))
                    {
                        var row = AddCombatMaterial(rows, Mapping, id, category, path, renderer, hierarchy, particle, streams,
                                                    "CharacterModel.defaultMaterial", 0, info.defaultMaterial);
                        row["materialAddress"] =
                            info.defaultMaterialAddress == null ? null : Convert.ToString(info.defaultMaterialAddress.RuntimeKey);
                    }
                var billboard = renderer as BillboardRenderer;
                if (billboard && billboard.billboard)
                    AddCombatMaterial(rows, Mapping, id, category, path, renderer, hierarchy, particle, streams, "billboard.material", 0,
                                      billboard.billboard.material);
                if (particle && particle.trailMaterial)
                    AddCombatMaterial(rows, Mapping, id, category, path, renderer, hierarchy, particle, streams, "trailMaterial", 0,
                                      particle.trailMaterial);
                if (materials.Length == 0 && !(billboard && billboard.billboard))
                    AddCombatMaterial(rows, Mapping, id, category, path, renderer, hierarchy, particle, streams, "sharedMaterials", -1, null);
            }
        }
        JObject RequireProjectileGhost(string projectilePath, string expectedGhost)
        {
            if (!ghostBindings.TryGetValue(projectilePath, out var binding) || (bool?)binding["ghostControllerPresent"] != true ||
                Path.GetFileNameWithoutExtension((string)binding["effective"]) != expectedGhost)
                throw new Exception("Projectile ghost binding missing for " + expectedGhost);
            return (JObject)binding.DeepClone();
        }

        var titanGhost = RequireProjectileGhost((string)Location("TitanPreFistProjectile.prefab")["path"], "TitanPreFistGhost");
        var fireBoltConfig = AssetDatabase.LoadAssetAtPath<RoR2.EntityStateConfiguration>(
            (string)Location("EntityStates.Mage.Weapon.FireFireBolt.asset")["path"]);
        if (!fireBoltConfig)
            throw new Exception("Fire Bolt state configuration missing");
        // Initialize only an inert state. The owned configuration supplies the projectile PPtr.
        string before = JsonUtility.ToJson(fireBoltConfig);
        var fireBolt = new EntityStates.Mage.Weapon.FireFireBolt();
        fireBoltConfig.BuildInstanceInitializer()(fireBolt);
        if (!fireBolt.projectilePrefab || fireBolt.projectilePrefab.name != "MageFireboltBasic" ||
            JsonUtility.ToJson(fireBoltConfig) != before)
            throw new Exception("Fire Bolt state projectile configuration differs");
        var fireBoltGhost = RequireProjectileGhost(AssetPath(fireBolt.projectilePrefab), "MageFireboltGhost");
        fireBoltGhost["configuration"] = AssetPath(fireBoltConfig);

        JObject RequireProjectileDetonation(string projectilePath, string effectFile, bool useExplosionFallback = false)
        {
            string effectPath = (string)Location(effectFile)["path"];
            var binding = impactBindings.OfType<JObject>().SingleOrDefault(row => (string)row["projectile"] == projectilePath);
            string configuredField = useExplosionFallback ? "explosionEffect" : "impactEffect";
            if (binding == null || (string)binding[configuredField] != effectPath ||
                (string)binding["detonationEffect"] != effectPath ||
                (useExplosionFallback && (string)binding["impactEffect"] != null) ||
                !rows.Any(row => (string)row["root"] == effectPath))
                throw new Exception("Projectile detonation material binding missing for " + effectFile);
            return (JObject)binding.DeepClone();
        }

        var mortarImpact = RequireProjectileDetonation((string)Location("TreebotMortar2.prefab")["path"],
                                                       "OmniExplosionVFXTreebotMortar.prefab");
        var fireBoltImpact = RequireProjectileDetonation(AssetPath(fireBolt.projectilePrefab), "OmniExplosionVFXQuick.prefab");
        var drifterImpact = RequireProjectileDetonation((string)Location("DrifterJunkCubeProjectile.prefab")["path"],
                                                        "DrifterBluntForceSlamGroundImpVFX.prefab", useExplosionFallback: true);

        var vagrantSkin = AssetDatabase.LoadAssetAtPath<RoR2.SkinDef>((string)Location("skinVagrantBodyDefault.asset")["path"]);
        if (!vagrantSkin)
            throw new Exception("Vagrant default skin missing");
        var parameters = addresses.Inspect(new SerializedObject(vagrantSkin), "skinDefParamsAddress", null, vagrantSkin.skinDefParams,
                                           out var skinBinding);
        if (!parameters)
            throw new Exception("Vagrant default skin parameters missing");
        var skinInfo = parameters.rendererInfos.Single(row => row.renderer && row.renderer.name == "VagrantMesh");
        var reference = skinInfo.defaultMaterialAddress;
        var material = reference != null && reference.RuntimeKeyIsValid()
                           ? addresses.Resolve<Material>(Convert.ToString(reference.RuntimeKey))
                           : skinInfo.defaultMaterial;
        var vagrant = Location("VagrantBody.prefab");
        if (!material || AssetPath(skinInfo.renderer) != (string)vagrant["path"])
            throw new Exception("Vagrant default skin body material binding missing");
        var skinMaterial = AddCombatMaterial(rows, Mapping, (int)vagrant["id"], "CharacterBody", (string)vagrant["path"], skinInfo.renderer,
                                             HierarchyPath(skinInfo.renderer.transform), null, new List<ParticleSystemVertexStream>(),
                                             "SkinDefParams.defaultMaterial", 0, material);
        skinMaterial["materialAddress"] = reference == null ? null : Convert.ToString(reference.RuntimeKey);

        var result = new JObject {
            ["scope"] =
                "Native-provider bodies and projectiles, configured ghosts and ProjectileImpactExplosion effects, registered effects and targeted source bindings; Android rendering and reference comparison remain open",
            ["roots"] = roots, ["slots"] = rows, ["errors"] = errors,
            ["projectileGhostBindings"] = new JArray(ghostBindings.Values),
            ["projectileImpactBindings"] = impactBindings,
            ["titanGhostBinding"] = titanGhost, ["fireBoltGhostBinding"] = fireBoltGhost, ["vagrantSkinBinding"] = skinBinding,
            ["mortarImpactBinding"] = mortarImpact, ["fireBoltImpactBinding"] = fireBoltImpact, ["drifterImpactBinding"] = drifterImpact,
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
        PortSession.SurfaceMaterialObservation Observe(Material source)
        {
            const System.Reflection.BindingFlags flags = System.Reflection.BindingFlags.Instance | System.Reflection.BindingFlags.Public |
                                                         System.Reflection.BindingFlags.InvokeMethod | System.Reflection.BindingFlags.OptionalParamBinding;
            return (PortSession.SurfaceMaterialObservation)type.InvokeMember("ObserveSurfaceMaterial", flags, null, observer,
                                                                            new object[] { source });
        }
        var material = new Material(Shader.Find("Standard"));
        var texture = new Texture2D(2, 2) { name = "Authored census fixture texture" };
        try
        {
            material.name = "Authored census fixture material";
            material.renderQueue = 3123;
            material.SetTexture("_MainTex", texture);
            material.SetTextureScale("_MainTex", new Vector2(2, 3));
            material.EnableKeyword("_EMISSION");
            var row = Observe(material);
            var main = row.properties.Single(property => property.name == "_MainTex");
            if (row.material != material.name || row.shader != material.shader.name || row.queue != 3123 ||
                row.supported != material.shader.isSupported || !row.keywords.Contains("_EMISSION") ||
                main.textureId != texture.GetInstanceID() || main.width != 2 || main.height != 2 ||
                main.scale != new Vector2(2, 3) || material.GetTexture("_MainTex") != texture || material.renderQueue != 3123 ||
                Observe(null) != null)
                throw new Exception("Live surface material observation contract failed");
            VerifyEffectiveSurfaceProperties(type, material);
            return new JObject { ["liveMaterialState"] = true, ["nullSlot"] = true, ["sourceUnchanged"] = true,
                                 ["effectiveSlotProperties"] = true };
        }
        finally
        {
            UnityEngine.Object.DestroyImmediate(material);
            UnityEngine.Object.DestroyImmediate(texture);
        }
    }
    static void VerifyEffectiveSurfaceProperties(Type observerType, Material material)
    {
        var observe = observerType.GetMethod("ObserveVagrantProperties",
                                             System.Reflection.BindingFlags.Static | System.Reflection.BindingFlags.NonPublic);
        var root = new GameObject("Authored property block fixture");
        try
        {
            var renderer = root.AddComponent<MeshRenderer>();
            renderer.sharedMaterials = new[] { material, material };
            var savedFade = new PortSession.SurfacePropertyObservation { name = "_Fade", value = Vector4.one };
            var saved = new PortSession.SurfaceMaterialObservation { properties = new[] { savedFade } };
            var materials = new[] { saved, saved };
            var rendererBlock = new MaterialPropertyBlock();
            var slotBlock = new MaterialPropertyBlock();
            PortSession.EffectiveSurfaceSlotObservation[] Read() =>
                (PortSession.EffectiveSurfaceSlotObservation[])observe.Invoke(null, new object[] { renderer, materials, rendererBlock, slotBlock });
            PortSession.EffectiveSurfacePropertyObservation Property(PortSession.EffectiveSurfaceSlotObservation slot, string name) =>
                slot.properties.Single(property => property.name == name);

            var block = new MaterialPropertyBlock();
            block.SetColor("_FlashColor", Color.clear);
            block.SetFloat("_Fade", 0);
            renderer.SetPropertyBlock(block);
            block.Clear();
            block.SetFloat("_EliteIndex", 0);
            renderer.SetPropertyBlock(block, 0);
            var rows = Read();
            if (rows.Length != 2 || rows[0].slot != 0 || rows[1].slot != 1 ||
                rows[0].propertyBlock != "slot-block" || rows[1].propertyBlock != "renderer-block" ||
                Property(rows[0], "_EliteIndex").source != "slot-block" || Property(rows[0], "_EliteIndex").value.x != 0 ||
                Property(rows[0], "_Fade").source != "material" || Property(rows[0], "_Fade").value != savedFade.value ||
                Property(rows[0], "_FlashColor").source != "absent" || Property(rows[1], "_EmColor").source != "absent" ||
                Property(rows[1], "_FlashColor").source != "renderer-block" || Property(rows[1], "_FlashColor").value != Vector4.zero ||
                Property(rows[1], "_Fade").source != "renderer-block" || Property(rows[1], "_Fade").value.x != 0)
                throw new Exception("Live effective surface property precedence failed");
            renderer.GetPropertyBlock(block, 0);
            if (!block.HasFloat("_EliteIndex") || block.HasFloat("_Fade"))
                throw new Exception("Surface observation changed the live slot block");
            renderer.SetPropertyBlock(null, 0);
            if (Property(Read()[0], "_Fade").source != "renderer-block")
                throw new Exception("Clearing the slot block did not restore renderer-wide precedence");
            renderer.SetPropertyBlock(null);
            rows = Read();
            if (rows[0].propertyBlock != "none" || Property(rows[0], "_Fade").source != "material" || savedFade.value != Vector4.one)
                throw new Exception("Clearing the renderer block did not restore the original material value");
        }
        finally
        {
            UnityEngine.Object.DestroyImmediate(root);
        }
    }
    static JObject AddCombatMaterial(JArray rows, Func<Material, JObject> mapping, int id, string category, string root,
                                     Renderer renderer, string hierarchy, ParticleSystemRenderer particle,
                                     List<ParticleSystemVertexStream> streams, string binding, int slot, Material material)
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
                          ["renderer"] = hierarchy,
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
                          ["srcBlend"] = material && material.HasProperty("_SrcBlend") ? (float?)material.GetFloat("_SrcBlend") : null,
                          ["dstBlend"] = material && material.HasProperty("_DstBlend") ? (float?)material.GetFloat("_DstBlend") : null,
                          ["textures"] = textures,
                          ["particleMode"] = particle ? particle.renderMode.ToString() : null,
                          ["particleMesh"] = particle && particle.mesh ? AssetDatabase.GetAssetPath(particle.mesh) : null,
                          ["particleMeshes"] = new JArray(meshes.Select(mesh => mesh ? AssetDatabase.GetAssetPath(mesh) : null)),
                          ["vertexStreams"] = new JArray(streams.Select(stream => stream.ToString())),
                          ["mapping"] = mapping(material) };
        rows.Add(row);
        return row;
    }
    static JObject CombatMaterialMapping(Material material, Dictionary<string, JObject> families)
    {
        if (!material || !material.shader)
            return new JObject { ["outcome"] = "missing-material-or-shader" };
        string shader = material.shader.name;
        if (families.TryGetValue(shader, out var family))
        {
            // The imported stub may omit declarations for saved source keywords.
            var savedKeywords = material.shaderKeywords;
            var keys = family["features"].Values<string>().Where(key => savedKeywords.Contains(key)).OrderBy(key => key).ToArray();
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
