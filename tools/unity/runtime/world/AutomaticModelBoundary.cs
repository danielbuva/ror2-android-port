// Subsystem: world/director (game path). Owner map: docs/ARCHITECTURE.md#ownership.
// Session phases: setup PrepareAutomaticModel, ObserveAutomaticModelFollow; teardown —.
using System.Collections;
using System.Linq;
using System.Reflection;
using RoR2;
using UnityEngine;

// Observe original detachment/following/destruction; never move or turn the model in the harness.
public sealed partial class PortSession
{
    GameObject ownedDetachedModel;
    Renderer[] deferredSourceModelRenderers;
    bool UsesNativeSelectedSkin(string survivor)
    {
        // These models leave their body meshes unbound until ModelSkinController.Start.
        return r.nativeSourceSkinLifecycleDiagnosticRequested || (IsPlayableSpine() && (survivor == "Huntress" || survivor == "Croco"));
    }
    bool IsAutomaticModel()
    {
        return IsNovaInput() || IsAutomaticSkill() || r.id.StartsWith("body-state-spawn-state-auto-model-");
    }
    void PrepareAutomaticModel(CharacterBody body, SessionConfig cfg)
    {
        var locator = body.modelLocator;
        var model = locator.modelTransform;
        Check(locator && model && model.parent == locator.modelBaseTransform && !locator.enabled,
              "Original model pre-Start identity/isolation");
        Check(typeof(ModelLocator).GetField("modelParentTransform", BindingFlags.Instance | BindingFlags.NonPublic).GetValue(locator) ==
                  null,
              "ModelLocator Start already ran");
        Check(locator.autoUpdateModelTransform && !locator.dontDetatchFromParent && !locator.preserveModel,
              "Recovered model lifecycle settings changed");
        ownedDetachedModel = model.gameObject;
        model.gameObject.SetActive(false); // Detachment must not activate the unproven child callbacks.
        string survivor = SelectedSourceSurvivor() ? r.selectedSurvivor : null;
        if (IsPlayableSpine() && !UsesNativeSelectedSkin(survivor))
        {
            // BaseCharacterMain snapshots available Animator parameters on entry.
            RuntimeAnimatorController controller;
            Avatar avatar;
            if (survivor == null)
            {
                controller = artifactBundle.LoadAsset<RuntimeAnimatorController>(cfg.displayAssets[0]);
                avatar = artifactBundle.LoadAsset<Avatar>(cfg.displayAssets[1]);
            }
            else
            {
                var root = "Assets/WholeGame/RoR2/Base/Characters/" + survivor + "/";
                controller = WholeCatalogComposed.LoadOwnedContent<RuntimeAnimatorController>(root + "anim" + survivor + ".controller");
                avatar = WholeCatalogComposed.LoadOwnedContent<Avatar>(root + "mdl" + survivor + "Avatar.asset");
                // Preserve the existing presentation boundary while the Animator starts.
                deferredSourceModelRenderers = model.GetComponentsInChildren<Renderer>(true)
                    .Where(renderer => !renderer.forceRenderingOff).ToArray();
                foreach (var renderer in deferredSourceModelRenderers)
                    renderer.forceRenderingOff = true;
            }
            Check(model.GetComponent<Animator>() && controller && avatar, "Original survivor animation assets unavailable before spawn");
            NovaDiagnosticDisplay.PrepareAnimationBeforeSpawn(model, controller, avatar, survivor != null);
        }
        r.modelTarget = model.name;
        r.modelParent = locator.modelBaseTransform.name;
        Save();
    }
    void VerifyAutomaticAnimatorBeforeMainState(CharacterBody body)
    {
        string survivor = SelectedSourceSurvivor() ? r.selectedSurvivor : null;
        if (!IsPlayableSpine() || UsesNativeSelectedSkin(survivor)) return;
        var animator = body.modelLocator.modelTransform.GetComponent<Animator>();
        animator.Update(0);
        var parameters = CharacterAnimParamAvailability.FromAnimator(animator);
        Check(parameters.isMoving && parameters.forwardSpeed && parameters.rightSpeed,
              "Original survivor locomotion parameters unavailable after native model Start before main state");
    }
    void RevealPreparedSourceModel()
    {
        if (deferredSourceModelRenderers == null) return;
        foreach (var renderer in deferredSourceModelRenderers)
            if (renderer)
                renderer.forceRenderingOff = false;
        deferredSourceModelRenderers = null;
    }
    void ObserveAutomaticModelFollow(CharacterBody body)
    {
        var locator = body.modelLocator;
        var model = locator.modelTransform;
        var parent = locator.modelBaseTransform;
        Check(locator.enabled && model && model.gameObject == ownedDetachedModel && !model.parent &&
                  (!model.gameObject.activeInHierarchy || IsPlayableSpine()),
              "Original detached model identity/isolation");
        Check(typeof(ModelLocator).GetField("modelParentTransform", BindingFlags.Instance | BindingFlags.NonPublic).GetValue(locator) ==
                  parent,
              "Original model Start parent cache");
        // The source ModelLocator tilts floor-normalized models (Treebot) before
        // applying the parent rotation. Compare against that original pose.
        var normal =
            (Vector3) typeof(ModelLocator).GetField("currentNormal", BindingFlags.Instance | BindingFlags.NonPublic).GetValue(locator);
        var expectedRotation = Quaternion.FromToRotation(Vector3.up, normal) * parent.rotation;
        float position = Vector3.Distance(model.position, parent.position), rotation = Quaternion.Angle(model.rotation, expectedRotation);
        r.modelPositionError = Mathf.Max(r.modelPositionError, position);
        r.modelRotationError = Mathf.Max(r.modelRotationError, rotation);
        r.modelFollowFrames++;
        Check(position < .001f && rotation < .03f, "Original LateUpdate model follow pose");
        r.modelDetached = true;
    }
    IEnumerator VerifyAutomaticModelDestruction()
    {
        if (!IsAutomaticModel() || string.IsNullOrEmpty(r.modelTarget))
            yield break;
        // Root destruction invokes original OnDestroy, whose model destruction is also deferred.
        for (int frame = 0; ownedDetachedModel && frame < 3; frame++)
            yield return null;
        r.modelDestroyed = !ownedDetachedModel;
        // Genuine integrated death/abandonment may end before the isolated proof's
        // sampling quota. Still require observed native follow and actual destruction.
        int requiredFrames = r.integratedWorld || !string.IsNullOrEmpty(r.firstFailure) ? 1 : 301;
        Check(r.modelDetached && r.modelFollowFrames >= requiredFrames && r.modelDestroyed,
              "Original detached model lifecycle before provider release: followed=" + r.modelFollowFrames + " required=" + requiredFrames +
                  " destroyed=" + r.modelDestroyed);
        Save();
    }
}
