// Opt-in owner for the selected player's original async skin lifecycle plus Android material copies.
using System;
using System.Collections.Generic;
using RoR2;
using UnityEngine;

public sealed class AndroidNativeSourceSkinLifecycle : MonoBehaviour
{
    [Serializable]
    public sealed class Report
    {
        public bool requested, attached, nativeOwnersActive, selectedSkinReady, animatorInitialized, displayDeactivated, ownerDestroyed;
        public int selectedSkinIndex = -1, currentSkinIndex = -1;
        public string controllerIdentity, avatarIdentity, firstFailure;
        public int materialCopiesCreated, materialCopiesRetired, materialCopiesReleased;
        public void Fail(string reason)
        {
            if (string.IsNullOrEmpty(firstFailure) && !string.IsNullOrEmpty(reason))
                firstFailure = reason.Length > 256 ? reason.Substring(0, 256) : reason;
        }
    }
    Report report;

    CharacterModel model;
    ModelSkinController skinController;
    Animator animator;
    RuntimeAnimatorController selectedControllerSnapshot;
    Avatar selectedAvatarSnapshot;
    int selectedSnapshotSkinIndex = -1;
    readonly Dictionary<Material, Material> translatedBySource = new Dictionary<Material, Material>();
    readonly Dictionary<Material, Material> sourceByTranslated = new Dictionary<Material, Material>();
    readonly List<Material> owned = new List<Material>();
    readonly List<Material> retired = new List<Material>();
    readonly HashSet<Material> currentSources = new HashSet<Material>();
    readonly HashSet<Renderer> referencedRenderers = new HashSet<Renderer>();
    readonly List<Material> sharedMaterialsScratch = new List<Material>();

    // Computed only from native owner state: no local "loaded" flag is set.
    public bool NativeSelectedSkinReady
    {
        get
        {
            return model && skinController && model.body && animator &&
                   skinController.currentSkinIndex == (int)model.body.skinIndex &&
                   animator.runtimeAnimatorController && animator.avatar &&
                   model.baseRendererInfos != null && model.baseRendererInfos.Length > 0;
        }
    }

    public bool NativeAnimatorInitialized => NativeSelectedSkinReady && animator.isInitialized;

    public static AndroidNativeSourceSkinLifecycle PrepareInactive(GameObject modelObject, CharacterBody expectedBody, Report report)
    {
        if (report == null)
            throw new ArgumentNullException(nameof(report));
        report.requested = true;
        if (!modelObject)
            throw Refuse(report, "Selected source model is missing");
        if (modelObject.activeInHierarchy)
            throw Refuse(report, "Native skin lifecycle must bind before source model activation");
        // This property is true only when the exact-input optional presentation transform was staged.
        // It guards CharacterModel.OnEnable's original RtpcSetter constructor/flush boundary.
        bool noAudioBoundary = WwiseIntegrationManager.noAudio;
        var model = modelObject.GetComponent<CharacterModel>();
        var skin = modelObject.GetComponent<ModelSkinController>();
        var animator = modelObject.GetComponentInChildren<Animator>(true);
        if (!model || !skin || !animator || !model.body || !expectedBody || model.body != expectedBody ||
            !expectedBody.modelLocator || expectedBody.modelLocator.modelTransform != modelObject.transform)
            throw Refuse(report, "Selected source model/body/catalog linkage is incomplete or mismatched");
        // Only continue when both native callbacks were enabled by the selected source prefab.
        // Do not force-enable a source-disabled callback.
        if (!AndroidNativeSkinActivationPolicy.ShouldActivate(true, true, noAudioBoundary, model.enabled, skin.enabled))
            throw Refuse(report, "Opt-in source skin lifecycle refused by source/audio/authored-enabled gate");
        var lifecycle = modelObject.GetComponent<AndroidNativeSourceSkinLifecycle>();
        if (!lifecycle)
            lifecycle = modelObject.AddComponent<AndroidNativeSourceSkinLifecycle>();
        lifecycle.Bind(model, skin, animator, report);
        return lifecycle;
    }

    static InvalidOperationException Refuse(Report report, string reason)
    {
        report.Fail(reason);
        return new InvalidOperationException(reason);
    }

    void Bind(CharacterModel sourceModel, ModelSkinController sourceSkinController, Animator sourceAnimator, Report sourceReport)
    {
        if (model)
        {
            if (model != sourceModel || skinController != sourceSkinController || animator != sourceAnimator)
                throw new InvalidOperationException("Native skin lifecycle cannot change source model ownership");
            return;
        }
        model = sourceModel;
        skinController = sourceSkinController;
        animator = sourceAnimator;
        report = sourceReport;
        report.attached = true;
        CaptureNativeState();
        // Subscribe before enabling/activating the model, so Start-triggered native async skin
        // application cannot complete before Android sees the source's completion notification.
        skinController.onSkinApplied += OnSkinApplied;
        ApplyAlreadyCompletedSkin();
    }

    void OnSkinApplied(int appliedIndex)
    {
        if (!model || !skinController || !model.body || appliedIndex != (int)model.body.skinIndex ||
            skinController.currentSkinIndex != appliedIndex)
            return;
        if (!CaptureSelectedAnimatorSnapshot(appliedIndex))
            return;
        report.selectedSkinIndex = appliedIndex;
        CaptureNativeState();
        TranslateCurrentNativeRecords();
    }

    void ApplyAlreadyCompletedSkin()
    {
        if (!NativeSelectedSkinReady)
            return;
        if (!CaptureSelectedAnimatorSnapshot(skinController.currentSkinIndex))
            return;
        report.selectedSkinIndex = skinController.currentSkinIndex;
        CaptureNativeState();
        TranslateCurrentNativeRecords();
    }

    bool CaptureSelectedAnimatorSnapshot(int appliedIndex)
    {
        if (!NativeSelectedSkinReady || !model.body || appliedIndex != (int)model.body.skinIndex ||
            skinController.currentSkinIndex != appliedIndex || !animator.runtimeAnimatorController || !animator.avatar)
            return false;
        // This snapshot is written only at the native selected-skin completion boundary.
        // CaptureNativeState remains diagnostic and cannot bless a later replacement.
        selectedControllerSnapshot = animator.runtimeAnimatorController;
        selectedAvatarSnapshot = animator.avatar;
        selectedSnapshotSkinIndex = appliedIndex;
        return true;
    }

    // True only while this exact live owner still owns the selected model's native
    // inventory callback. Call only at setup and inventory-change boundaries.
    public bool IsActiveInventoryDisplayOwner(CharacterBody expectedBody, CharacterModel expectedModel, Report expectedReport)
    {
        int selectedIndex = expectedBody ? (int)expectedBody.skinIndex : -1;
        var evidence = new AndroidNativeItemDisplayDispatch.OwnerEvidence {
            expectedBody = expectedBody,
            ownerBody = model ? model.body : null,
            expectedModel = expectedModel,
            ownerModel = model,
            expectedReport = expectedReport,
            ownerReport = report,
            componentActive = this && isActiveAndEnabled && gameObject.activeInHierarchy &&
                              expectedModel && gameObject == expectedModel.gameObject,
            modelEnabled = model && model.enabled,
            modelActive = model && model.gameObject.activeInHierarchy && expectedBody && expectedBody.modelLocator &&
                          expectedBody.modelLocator.modelTransform == model.transform,
            skinControllerEnabled = skinController && skinController.enabled && skinController.gameObject.activeInHierarchy,
            reportRequested = report != null && report.requested,
            reportAttached = report != null && report.attached,
            reportNativeOwnersActive = report != null && report.nativeOwnersActive,
            selectedSkinReady = NativeSelectedSkinReady,
            animatorInitialized = NativeAnimatorInitialized && animator && animator.enabled,
            selectedIndexMatches = selectedIndex >= 0 && skinController && skinController.currentSkinIndex == selectedIndex &&
                                   report != null && report.selectedSkinIndex == selectedIndex &&
                                   report.currentSkinIndex == selectedIndex,
            expectedController = selectedControllerSnapshot,
            liveController = animator ? animator.runtimeAnimatorController : null,
            expectedAvatar = selectedAvatarSnapshot,
            liveAvatar = animator ? animator.avatar : null,
            expectedSelectedIndex = selectedSnapshotSkinIndex,
            liveSelectedIndex = skinController ? skinController.currentSkinIndex : -1,
            notDeactivatedOrDestroyed = report != null && !report.displayDeactivated && !report.ownerDestroyed,
            noFailure = report != null && string.IsNullOrEmpty(report.firstFailure)
        };
        return AndroidNativeItemDisplayDispatch.IsExactReadyOwner(evidence);
    }

    public void CaptureNativeState()
    {
        if (report == null)
            return;
        report.attached = !ReferenceEquals(model, null);
        report.nativeOwnersActive = model && skinController && model.enabled && skinController.enabled && model.gameObject.activeInHierarchy;
        report.selectedSkinIndex = model && model.body ? (int)model.body.skinIndex : -1;
        report.currentSkinIndex = skinController ? skinController.currentSkinIndex : -1;
        report.selectedSkinReady = NativeSelectedSkinReady;
        report.animatorInitialized = report.selectedSkinReady && animator.isInitialized;
        report.controllerIdentity = Identity(animator ? animator.runtimeAnimatorController : null);
        report.avatarIdentity = Identity(animator ? animator.avatar : null);
    }

    static string Identity(UnityEngine.Object value)
    {
        if (!value)
            return string.Empty;
        string identity = value.GetType().FullName + ":" + value.name;
        return identity.Length > 160 ? identity.Substring(0, 160) : identity;
    }

    public void RecordDisplayDeactivated()
    {
        if (report == null)
            return;
        report.displayDeactivated = true;
        report.nativeOwnersActive = false;
    }

    Material NativeSource(Material value)
    {
        Material source;
        return value && sourceByTranslated.TryGetValue(value, out source) ? source : value;
    }

    Material Translate(Material value)
    {
        var source = NativeSource(value);
        if (!source)
            return null;
        currentSources.Add(source);
        Material copy;
        if (translatedBySource.TryGetValue(source, out copy) && copy)
        {
            retired.Remove(copy);
            return copy;
        }
        copy = new Material(source);
        AndroidMaterialPresentation.Apply(source, copy);
        translatedBySource.Add(source, copy);
        sourceByTranslated.Add(copy, source);
        owned.Add(copy);
        if (report != null)
            report.materialCopiesCreated++;
        return copy;
    }

    void TranslateCurrentNativeRecords()
    {
        if (!NativeSelectedSkinReady)
            return;
        currentSources.Clear();
        var records = model.baseRendererInfos;
        for (int i = 0; i < records.Length; i++)
        {
            var record = records[i];
            if (record.renderer)
                referencedRenderers.Add(record.renderer);
            // Keep the complete native RendererInfo (renderer, defaultShadowCastingMode,
            // ignoreOverlays, and future fields) and replace only its material reference.
            record.defaultMaterial = Translate(record.defaultMaterial);
            records[i] = record;
        }
        model.baseRendererInfos = records;
        // CharacterModel's source Update consumes these records and refreshes actual slots.
        model.forceUpdate = true;
        QueueNoLongerSelectedCopies();
        RetireIfNativeOwnersReleasedCopies();
    }

    void QueueNoLongerSelectedCopies()
    {
        for (int i = 0; i < owned.Count; i++)
        {
            var copy = owned[i];
            Material source;
            if (copy && sourceByTranslated.TryGetValue(copy, out source) && !currentSources.Contains(source) && !retired.Contains(copy))
            {
                retired.Add(copy);
                if (report != null)
                    report.materialCopiesRetired++;
            }
        }
    }

    void LateUpdate()
    {
        // Skin swaps are rare. Scan only pending old copies, never every model renderer per frame.
        if (retired.Count != 0)
            RetireIfNativeOwnersReleasedCopies();
    }

    void RetireIfNativeOwnersReleasedCopies()
    {
        for (int i = retired.Count - 1; i >= 0; i--)
        {
            var copy = retired[i];
            if (copy && IsReferencedByNativeModel(copy))
                continue;
            ReleaseOwnedCopy(copy);
        }
    }

    bool IsReferencedByNativeModel(Material sought)
    {
        if (model)
        {
            var records = model.baseRendererInfos;
            if (records != null)
                foreach (var record in records)
                    if (ReferenceEquals(record.defaultMaterial, sought))
                        return true;
        }
        foreach (var renderer in referencedRenderers)
        {
            if (!renderer)
                continue;
            sharedMaterialsScratch.Clear();
            renderer.GetSharedMaterials(sharedMaterialsScratch);
            foreach (var material in sharedMaterialsScratch)
                if (ReferenceEquals(material, sought))
                    return true;
        }
        return false;
    }

    void ReleaseOwnedCopy(Material copy)
    {
        if (ReferenceEquals(copy, null))
            return;
        AndroidMaterialPresentation.Release(copy);
        Material source;
        if (sourceByTranslated.TryGetValue(copy, out source))
        {
            Material current;
            if (translatedBySource.TryGetValue(source, out current) && ReferenceEquals(current, copy))
                translatedBySource.Remove(source);
            sourceByTranslated.Remove(copy);
        }
        if (copy)
            Destroy(copy);
        if (report != null)
            report.materialCopiesReleased++;
        owned.Remove(copy);
        retired.Remove(copy);
    }

    void OnDestroy()
    {
        if (!ReferenceEquals(skinController, null))
            skinController.onSkinApplied -= OnSkinApplied;
        selectedControllerSnapshot = null;
        selectedAvatarSnapshot = null;
        selectedSnapshotSkinIndex = -1;
        if (report != null)
        {
            report.ownerDestroyed = true;
            report.attached = false;
            report.nativeOwnersActive = false;
        }
        // This component shares the native model/body destruction lifetime. Display deactivation
        // does not release native skin handles or dispose this owner.
        for (int i = owned.Count - 1; i >= 0; i--)
            ReleaseOwnedCopy(owned[i]);
        owned.Clear();
        retired.Clear();
        currentSources.Clear();
        referencedRenderers.Clear();
        sharedMaterialsScratch.Clear();
        translatedBySource.Clear();
        sourceByTranslated.Clear();
    }
}
