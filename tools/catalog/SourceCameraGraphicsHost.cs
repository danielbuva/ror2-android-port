// Exact-editor contract for the existing source-camera graphics owner.
// Inactive authored objects only: no application, camera rendering or server.
#if UNITY_EDITOR
using System;
using System.Collections.Generic;
using System.Reflection;
using Newtonsoft.Json.Linq;
using UnityEditor;
using UnityEngine;
using UnityEngine.Rendering.PostProcessing;

public static class SourceCameraGraphicsHost
{
    const BindingFlags PrivateInstance = BindingFlags.Instance | BindingFlags.NonPublic;

    public static object Run()
    {
        Require(!EditorApplication.isPlaying && !EditorApplication.isCompiling && !EditorApplication.isUpdating &&
                    !EditorUtility.scriptCompilationFailed && !BuildPipeline.isBuildingPlayer &&
                    !UnityEngine.Networking.NetworkServer.active && !UnityEngine.Networking.NetworkClient.active,
                "Source graphics fixture requires compiled idle editor without a game/server");
        var original = AssetDatabase.LoadAssetAtPath<PostProcessResources>(
            "Assets/WholeGame/MonoBehaviour/PostProcessResources_53.asset");
        Require(original, "Original camera resources missing");
        var profiles = new[] {
            AssetDatabase.LoadAssetAtPath<PostProcessProfile>("Assets/WholeGame/RoR2/Base/Scenes/title/PostProcessing/ppApplication_opt.asset"),
            AssetDatabase.LoadAssetAtPath<PostProcessProfile>("Assets/WholeGame/RoR2/Base/Scenes/title/PostProcessing/ppDisabler_opt.asset")
        };
        Require(profiles[0] && profiles[1], "Original startup profiles missing");
        string originalResources = EditorJsonUtility.ToJson(original);
        var originalSettings = new Dictionary<PostProcessEffectSettings, string>();
        foreach (var profile in profiles)
            foreach (var setting in profile.settings)
                originalSettings[setting] = EditorJsonUtility.ToJson(setting);
        var root = new GameObject("Source graphics contract fixture");
        root.SetActive(false);
        var ownedProfiles = new List<PostProcessProfile>();
        PostProcessResources ownedResources = null;
        AndroidNativeSourceCameraRigOwner owner = null;
        int settingsChecked = 0;
        try
        {
            owner = root.AddComponent<AndroidNativeSourceCameraRigOwner>();
            typeof(AndroidNativeSourceCameraRigOwner).GetField("stagingRoot", PrivateInstance).SetValue(owner, root);
            typeof(AndroidNativeSourceCameraRigOwner).GetProperty("sourceSobelObservation").SetValue(
                owner, new AndroidNativeSourceCameraRigOwner.SourceSobelObservation());
            var layer = root.AddComponent<PostProcessLayer>();
            layer.Init(original);
            typeof(AndroidNativeSourceCameraRigOwner).GetMethod("PrepareSourceGraphicsResources", PrivateInstance)
                .Invoke(owner, new object[] { layer });
            ownedResources = (PostProcessResources)typeof(AndroidNativeSourceCameraRigOwner)
                .GetField("sourceGraphicsResources", PrivateInstance).GetValue(owner);
            Require(ownedResources && ownedResources != original &&
                        !ReferenceEquals(ownedResources.shaders, original.shaders) &&
                        !ReferenceEquals(ownedResources.computeShaders, original.computeShaders),
                    "Original resource object or nested tables shared");
            Require(ownedResources.shaders.uber == original.shaders.uber &&
                        ownedResources.computeShaders.autoExposure == original.computeShaders.autoExposure,
                    "An unrelated source program was replaced");
            Require(ownedResources.shaders.multiScaleAO == Resources.Load<Shader>("SourceCameraMultiScaleVO") &&
                        ownedResources.shaders.lut2DBaker == Resources.Load<Shader>("SourceCameraLut2DBaker") &&
                        ownedResources.computeShaders.lut3DBaker == Resources.Load<ComputeShader>("SourceCameraLut3DBaker") &&
                        ownedResources.computeShaders.multiScaleAODownsample1 == Resources.Load<ComputeShader>("SourceCameraMultiScaleVODownsample1") &&
                        ownedResources.computeShaders.multiScaleAODownsample2 == Resources.Load<ComputeShader>("SourceCameraMultiScaleVODownsample2") &&
                        ownedResources.computeShaders.multiScaleAORender == Resources.Load<ComputeShader>("SourceCameraMultiScaleVORender") &&
                        ownedResources.computeShaders.multiScaleAOUpsample == Resources.Load<ComputeShader>("SourceCameraMultiScaleVOUpsample"),
                    "Runtime resource fields do not select the exact generated program assets");
            Require(owner.sourceSobelObservation.ownedResourcesBound && owner.sourceSobelObservation.computeKernelsVerified == 22,
                    "Original public Init or runtime kernel checks failed");
            foreach (var source in profiles)
            {
                var sourceRoot = new GameObject("Inactive source profile fixture");
                sourceRoot.transform.SetParent(root.transform, false);
                sourceRoot.layer = 20;
                var sourceVolume = sourceRoot.AddComponent<PostProcessVolume>();
                sourceVolume.sharedProfile = source;
                sourceVolume.priority = -2.5f;
                sourceVolume.weight = .37f;
                sourceVolume.blendDistance = 4.2f;
                object[] args = { sourceVolume, null };
                var volume = (PostProcessVolume)typeof(AndroidNativeSourceCameraRigOwner)
                    .GetMethod("CloneSourceGraphicsVolume", PrivateInstance).Invoke(owner, args);
                var copy = (PostProcessProfile)args[1];
                ownedProfiles.Add(copy);
                Require(volume && !volume.isActiveAndEnabled && copy && copy != source && volume.sharedProfile == copy &&
                            copy.settings.Count == source.settings.Count && volume.gameObject.layer == sourceRoot.layer &&
                            volume.isGlobal == sourceVolume.isGlobal && volume.priority == sourceVolume.priority &&
                            volume.weight == sourceVolume.weight && volume.blendDistance == sourceVolume.blendDistance,
                        "Source volume blend/layer/profile contract changed");
                for (int i = 0; i < source.settings.Count; i++)
                {
                    var setting = source.settings[i];
                    var cloned = copy.settings[i];
                    Require(cloned && cloned != setting && cloned.GetType() == setting.GetType(), "Setting not individually cloned");
                    JObject before = JObject.Parse(EditorJsonUtility.ToJson(setting));
                    JObject after = JObject.Parse(EditorJsonUtility.ToJson(cloned));
                    before.Remove("m_Name");
                    after.Remove("m_Name");
                    Require(JToken.DeepEquals(before, after), "Cloned original parameter values/override flags differ: " + setting.GetType().Name);
                    settingsChecked++;
                }
            }
            Require(EditorJsonUtility.ToJson(original) == originalResources, "Original resource asset mutated");
            foreach (var item in originalSettings)
                Require(EditorJsonUtility.ToJson(item.Key) == item.Value, "Original setting asset mutated");
            return new { profiles = profiles.Length, settingsChecked, programBindings = 7, kernelsVerified = 22,
                         originalAssetsUnchanged = true, inactiveFixtureOnly = true, renderingTested = false };
        }
        finally
        {
            // Editor-only fixture cleanup. Production deferred teardown is covered
            // separately; it must not be invoked as Destroy() in edit mode.
            if (!ownedResources && owner)
                ownedResources = (PostProcessResources)typeof(AndroidNativeSourceCameraRigOwner)
                    .GetField("sourceGraphicsResources", PrivateInstance).GetValue(owner);
            foreach (var profile in ownedProfiles)
                if (profile)
                {
                    foreach (var setting in profile.settings)
                        if (setting) UnityEngine.Object.DestroyImmediate(setting);
                    UnityEngine.Object.DestroyImmediate(profile);
                }
            if (ownedResources) UnityEngine.Object.DestroyImmediate(ownedResources);
            UnityEngine.Object.DestroyImmediate(root);
        }
    }

    static void Require(bool condition, string message)
    {
        if (!condition) throw new InvalidOperationException(message);
    }
}
#endif
