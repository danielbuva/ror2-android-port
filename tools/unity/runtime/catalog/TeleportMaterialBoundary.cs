// Subsystem: catalog/resources (game path). Owner map: docs/ARCHITECTURE.md#ownership.
// Session phases: setup PrepareTeleportMaterial, ObserveTeleportOverlays (TeleportMaterialSession); teardown CleanupTeleportMaterial (coroutine); Dispose retains release state.
using System;
using System.Collections;
using System.Collections.Generic;
using Path = System.IO.Path;
using System.Linq;
using System.Reflection;
using RoR2;
using UnityEngine;
using UnityEngine.AddressableAssets;
using UnityEngine.AddressableAssets.ResourceLocators;
using UnityEngine.ResourceManagement.AsyncOperations;
using UnityEngine.ResourceManagement.ResourceLocations;
using UnityEngine.ResourceManagement.ResourceProviders;

// Uses the original manager's public removal/update APIs while resolving its
// private registry read-only. managerIndex alone is not an identity token.
public static class TeleportOverlayRegistryOwnership
{
    static readonly FieldInfo ArrayField =
        typeof(TemporaryOverlayManager).GetField("overlayArray", BindingFlags.NonPublic | BindingFlags.Static);
    static readonly FieldInfo CountField =
        typeof(TemporaryOverlayManager).GetField("arraySize", BindingFlags.NonPublic | BindingFlags.Static);

    static TemporaryOverlayInstance[] ReadRegistry(out int count)
    {
        if (ArrayField == null || CountField == null)
            throw new InvalidOperationException("Original temporary overlay registry fields are unavailable");
        var overlays = ArrayField.GetValue(null) as TemporaryOverlayInstance[];
        if (overlays == null || !(CountField.GetValue(null) is int activeCount) || activeCount < 0 || activeCount > overlays.Length)
            throw new InvalidOperationException("Original temporary overlay registry is not initialized or has an invalid size");
        count = activeCount;
        return overlays;
    }

    public static int ActiveCount
    {
        get {
            ReadRegistry(out int count);
            return count;
        }
    }

    public static bool Contains(TemporaryOverlayInstance overlay)
    {
        if (overlay == null)
            return false;
        var overlays = ReadRegistry(out int count);
        for (int i = 0; i < count; i++)
            if (ReferenceEquals(overlays[i], overlay))
                return true;
        return false;
    }

    public static bool RemoveIfActive(TemporaryOverlayInstance ownedOverlay)
    {
        if (ownedOverlay == null)
            return false;
        var overlays = ReadRegistry(out int count);
        int index = -1;
        for (int i = 0; i < count; i++)
        {
            if (ReferenceEquals(overlays[i], ownedOverlay))
            {
                index = i;
                break;
            }
        }
        if (index < 0)
        {
            // Native RemoveOverlay can leave a removed last-slot instance with
            // its old positive index. It is safe to normalize only after proving
            // the exact instance is absent from the active registry prefix.
            if (ownedOverlay.managerIndex >= 0)
                ownedOverlay.managerIndex = -1;
            return false;
        }

        if (!ReferenceEquals(overlays[index], ownedOverlay))
            throw new InvalidOperationException("Temporary overlay identity changed during exact removal");
        TemporaryOverlayManager.RemoveOverlay(index);
        if (Contains(ownedOverlay))
            throw new InvalidOperationException("Native removal retained the exact owned temporary overlay");
        if (ownedOverlay.managerIndex >= 0)
            ownedOverlay.managerIndex = -1;
        return true;
    }
}

// A single measured legacy Material location. The prefab bundle keeps its existing owner.
public sealed partial class PortSession
{
    const string TeleportBundle = "teleport-material-lab";
    TeleportMaterialSession teleportMaterialSession;
    TeleportMaterialSession GetTeleportMaterialSession()
    {
        if (teleportMaterialSession == null)
            teleportMaterialSession = new TeleportMaterialSession(this);
        return teleportMaterialSession;
    }
    int TeleportOverlayCount()
    {
        return GetTeleportMaterialSession().TeleportOverlayCount();
    }
    IEnumerator PrepareTeleportMaterial(SessionConfig cfg)
    {
        return GetTeleportMaterialSession().PrepareTeleportMaterial(cfg);
    }
    void AcceptTeleportMaterial(Material material, SessionConfig cfg)
    {
        GetTeleportMaterialSession().AcceptTeleportMaterial(material, cfg);
    }
    void ObserveTeleportOverlays(CharacterBody body)
    {
        GetTeleportMaterialSession().ObserveTeleportOverlays(body);
    }
    void ProbeTeleportOverlay(CharacterBody body, SessionConfig cfg)
    {
        GetTeleportMaterialSession().ProbeTeleportOverlay(body, cfg);
    }
    IEnumerator CleanupTeleportMaterial()
    {
        return GetTeleportMaterialSession().CleanupTeleportMaterial();
    }

    // Retain the owner for partial setup, repeated cleanup and later calls. Asset
    // release must await the coroutine's original frame yields and release order;
    // Dispose leaves that state intact, including when setup was skipped.
    sealed class TeleportMaterialSession : IDisposable
    {
        readonly PortSession coordinator;
        ResourceLocationMap teleportLocator;
        AsyncOperationHandle<Material> teleportHandle;
        Material teleportMaterial;
        readonly List<TemporaryOverlayInstance> ownedTeleportOverlays = new List<TemporaryOverlayInstance>();
        readonly HashSet<TemporaryOverlayInstance> observedTeleportOverlays = new HashSet<TemporaryOverlayInstance>();
        public TeleportMaterialSession(PortSession coordinator)
        {
            this.coordinator = coordinator;
        }
        public int TeleportOverlayCount()
        {
            return TeleportOverlayRegistryOwnership.ActiveCount;
        }
        public IEnumerator PrepareTeleportMaterial(SessionConfig cfg)
        {
            coordinator.Check(!AssetBundle.GetAllLoadedAssetBundles().Any(b => b.name == TeleportBundle),
                              "Teleport bundle already has an owner");
            coordinator.Check(TeleportOverlayCount() == 0, "Existing overlays; refuse ownership");
            string key;
            coordinator.Check(LegacyResourcesAPI.GetGuid("Materials/matTPInOut", out key) && key == cfg.teleportMaterialKey,
                              "Actual legacy material GUID");
            var providers = Addressables.ResourceManager.ResourceProviders;
            if (!providers.Any(p => p is AssetBundleProvider))
                providers.Add(new AssetBundleProvider());
            if (!providers.Any(p => p is BundledAssetProvider))
                providers.Add(new BundledAssetProvider());
            var bundle = new ResourceLocationBase(TeleportBundle, Path.Combine(Application.persistentDataPath, "payload", TeleportBundle),
                                                  typeof(AssetBundleProvider).FullName, typeof(IAssetBundleResource));
            bundle.Data = new AssetBundleRequestOptions { BundleName = TeleportBundle };
            var location =
                new ResourceLocationBase(key, cfg.teleportMaterialAsset, typeof(BundledAssetProvider).FullName, typeof(Material), bundle);
            teleportLocator = new ResourceLocationMap("teleport-material-probe");
            teleportLocator.Add(key, location);
            Addressables.AddResourceLocator(teleportLocator);
            if (coordinator.r.id != "body-state-spawn-state-material")
                yield break;
            coordinator.r.phase = "original-teleport-material-cold-sync";
            coordinator.Save();
            teleportMaterial = LegacyResourcesAPI.Load<Material>("Materials/matTPInOut");
            if (teleportMaterial)
                coordinator.r.teleportSyncLoads++;
            AcceptTeleportMaterial(teleportMaterial, cfg);
            coordinator.r.phase = "original-teleport-material-async";
            coordinator.Save();
            teleportHandle = LegacyResourcesAPI.LoadAsync<Material>("Materials/matTPInOut");
            var deadline = Time.realtimeSinceStartup + 5;
            while (!teleportHandle.IsDone && Time.realtimeSinceStartup < deadline)
                yield return null;
            yield return null;
            coordinator.Check(teleportHandle.IsDone && teleportHandle.Status == AsyncOperationStatus.Succeeded &&
                                  teleportHandle.Result == teleportMaterial,
                              "Original async/sync material identity");
            coordinator.Check(LegacyResourcesAPI.ActiveCount == 0, "Legacy material callbacks not drained");
        }
        public void AcceptTeleportMaterial(Material material, SessionConfig cfg)
        {
            coordinator.Check(material && material.name == "matTPInOut" && material.shader, "Actual typed teleport material missing");
            coordinator.Check(AssetBundle.GetAllLoadedAssetBundles().Any(
                                  b => b.name == TeleportBundle &&
                                       b.GetAllAssetNames().Contains(cfg.teleportMaterialAsset, StringComparer.OrdinalIgnoreCase)),
                              "Provider did not load the separately owned material bundle");
            coordinator.r.teleportMaterialLoaded = true;
            coordinator.r.teleportMaterialName = material.name;
            coordinator.r.teleportShader = material.shader.name;
        }
        public void ObserveTeleportOverlays(CharacterBody body)
        {
            // MovementBatchProbe is the unchanged resource/file name.
            var cfg = JsonUtility.FromJson<SessionConfig>(Resources.Load<TextAsset>("MovementBatchProbe").text);
            var model = body.modelLocator.modelTransform.GetComponent<CharacterModel>();
            foreach (var overlay in model.temporaryOverlays)
            {
                if (!observedTeleportOverlays.Add(overlay))
                    continue;
                ownedTeleportOverlays.Add(overlay);
                if (overlay.originalMaterial)
                {
                    teleportMaterial = overlay.originalMaterial;
                    coordinator.r.teleportSyncLoads++;
                }
                AcceptTeleportMaterial(overlay.originalMaterial, cfg);
                coordinator.r.teleportOverlays++;
                coordinator.Check(overlay.initialized && overlay.assignedCharacterModel == model && overlay.materialInstance &&
                                      overlay.materialInstance != overlay.originalMaterial &&
                                      overlay.materialInstance.shader == overlay.originalMaterial.shader,
                                  "Original overlay material copy/assignment");
            }
        }
        public void ProbeTeleportOverlay(CharacterBody body, SessionConfig cfg)
        {
            var model = body.modelLocator.modelTransform.GetComponent<CharacterModel>();
            coordinator.Check(model && model.temporaryOverlays.Count == 0, "Recovered model overlay baseline");
            coordinator.r.phase = "original-teleport-overlay-setup";
            coordinator.Save();
            TeleportOutController.AddTPOutEffect(model, 1f, 0f, cfg.sourceSpawnDelay);
            ObserveTeleportOverlays(body);
            coordinator.Check(coordinator.r.teleportOverlays == 1 && TeleportOverlayCount() == 1, "Original overlay registration");
            var overlay = ownedTeleportOverlays.Single();
            coordinator.Check(overlay.animateShaderAlpha && overlay.destroyComponentOnEnd && overlay.duration == cfg.sourceSpawnDelay &&
                                  overlay.alphaCurve.Evaluate(0) == 1 && overlay.alphaCurve.Evaluate(1) == 0,
                              "Original overlay configuration");
            TemporaryOverlayManager.OverlayUpdate();
            coordinator.Check(overlay.stopwatch > 0 &&
                                  Mathf.Abs(overlay.materialInstance.GetFloat("_ExternalAlpha") -
                                            overlay.alphaCurve.Evaluate(overlay.stopwatch / overlay.duration)) < .0001f,
                              "Original diagnostic overlay update");
            coordinator.r.phase = "original-teleport-overlay-remove";
            coordinator.Save();
            TeleportOverlayRegistryOwnership.RemoveIfActive(overlay);
            coordinator.Check(TeleportOverlayCount() == 0 && model.temporaryOverlays.Count == 0 && overlay.managerIndex == -1 &&
                                  overlay.assignedCharacterModel == null,
                              "Original overlay removal");
            coordinator.r.teleportOverlayRemoved = true;
        }
        public IEnumerator CleanupTeleportMaterial()
        {
            if (teleportLocator == null)
                yield break;
            var copies = ownedTeleportOverlays.Select(x => x.materialInstance).ToArray();
            foreach (var overlay in ownedTeleportOverlays)
                TeleportOverlayRegistryOwnership.RemoveIfActive(overlay);
            coordinator.Check(ownedTeleportOverlays.All(x => !TeleportOverlayRegistryOwnership.Contains(x)),
                              "An exact owned overlay remains in the active manager registry");
            yield return null;
            // The world loop is already stopped. One public native update prunes
            // remaining invalid source entries while preserving live foreign ones.
            TemporaryOverlayManager.OverlayUpdate();
            coordinator.Check(TeleportOverlayCount() == 0, "Unowned live overlays remain after native pruning");
            coordinator.Check(copies.All(x => !x), "Overlay material copies survived destruction");
            var deadline = Time.realtimeSinceStartup + 3;
            while (LegacyResourcesAPI.ActiveCount != 0 && Time.realtimeSinceStartup < deadline)
                yield return null;
            coordinator.Check(LegacyResourcesAPI.ActiveCount == 0, "Refuse material release with pending callbacks");
            for (int i = 0; i < coordinator.r.teleportSyncLoads; i++)
                Addressables.Release(teleportMaterial);
            if (teleportHandle.IsValid())
                Addressables.Release(teleportHandle);
            yield return null;
            coordinator.Check(!teleportHandle.IsValid() && !AssetBundle.GetAllLoadedAssetBundles().Any(b => b.name == TeleportBundle),
                              "Original material release retained its bundle");
            Addressables.RemoveResourceLocator(teleportLocator);
            teleportLocator = null;
            coordinator.r.teleportBundleReleased = true;
        }
        public void Dispose()
        {
        }
    }
}
