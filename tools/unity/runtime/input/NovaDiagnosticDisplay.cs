// Subsystem: input/camera (game path). Owner map: docs/ARCHITECTURE.md#ownership.
// Session phases: setup NovaDiagnosticDisplay, ConfigureThirdPerson; teardown Dispose.
using System;
using System.Collections.Generic;
using System.Linq;
using UnityEngine;

// Owned view of the detached model, with optional original aiming presentation.
// Native animation/state code chooses the pose; this adapter never rotates bones.
public sealed class NovaDiagnosticDisplay : IDisposable
{
    public GameObject root;
    public Camera camera;
    Material material, floorMaterial;
    Texture2D grid;
    Transform copy, source;
    LineRenderer aim;
    bool actualModel;
    readonly List<Material> ownedSurvivorMaterials = new List<Material>();
    public NovaThirdPersonView thirdPerson;
    public AndroidPresentationCamera presentationCamera;
    RoR2.AimAnimator nativeAim;
    Animator nativeAnimator;
    AndroidNativeSourceSkinLifecycle nativeSourceSkinLifecycle;
    bool sourceSkinLifecycleDiagnostic;
    AndroidNativeSourceSkinLifecycle.Report sourceSkinReport;
    public bool NativeSourceSkinAssetsReady => sourceSkinLifecycleDiagnostic && nativeSourceSkinLifecycle &&
                                               nativeSourceSkinLifecycle.NativeSelectedSkinReady;
    public bool NativeSourceSkinAnimatorReady => sourceSkinLifecycleDiagnostic && nativeSourceSkinLifecycle &&
                                                 nativeSourceSkinLifecycle.NativeAnimatorInitialized;
    public void CaptureNativeSourceSkinReport()
    {
        if (nativeSourceSkinLifecycle)
        {
            nativeSourceSkinLifecycle.CaptureNativeState();
            nativeSourceSkinLifecycle.CaptureNativeVisualState(camera, nativeAnimator);
        }
    }
    public void EnableNativeSourceAnimatorAfterSkinReady()
    {
        if (!NativeSourceSkinAssetsReady || !nativeAnimator || !nativeAnimator.runtimeAnimatorController || !nativeAnimator.avatar)
            throw new Exception("Original selected-skin controller/avatar is not ready");
        nativeAnimator.enabled = true;
    }
    public void EnableNativeAimAfterAnimatorReady()
    {
        if (!NativeSourceSkinAnimatorReady)
            throw new Exception("Original Animator is not initialized for native aim");
        if (nativeAim)
            nativeAim.enabled = true;
    }
    public void ObserveNativeAim(PortSession.NovaReport report)
    {
        if (!nativeAim)
            return;
        report.originalAimAnimator = nativeAim.isActiveAndEnabled;
        report.aimPitchCycle = nativeAnimator.GetFloat("aimPitchCycle");
        report.aimYawCycle = nativeAnimator.GetFloat("aimYawCycle");
        report.modelForward = source.forward;
        report.characterMatteApproximation = !AndroidNativeDeferredPresentation.report.available;
    }
    static Transform Copy(Transform s, Transform parent, Dictionary<Transform, Transform> map)
    {
        var t = new GameObject(s.name).transform;
        t.gameObject.layer = 30;
        t.SetParent(parent, false);
        t.localPosition = s.localPosition;
        t.localRotation = s.localRotation;
        t.localScale = s.localScale;
        map[s] = t;
        foreach (Transform child in s)
            Copy(child, t, map);
        return t;
    }
    public NovaDiagnosticDisplay(Transform model, AssetBundle bundle, string[] assets, GameObject floor, bool actual = false,
                                 RoR2.CharacterBody aimingBody = null, string sourceSurvivor = null,
                                 bool nativeSourceSkinLifecycleDiagnostic = false, RoR2.CharacterBody selectedBody = null,
                                 AndroidNativeSourceSkinLifecycle.Report nativeSourceSkinReport = null)
    {
        actualModel = actual;
        bool sourceSelected = !string.IsNullOrEmpty(sourceSurvivor);
        sourceSkinLifecycleDiagnostic = sourceSelected && actual && nativeSourceSkinLifecycleDiagnostic;
        sourceSkinReport = nativeSourceSkinReport;
        if (nativeSourceSkinLifecycleDiagnostic && (!sourceSkinLifecycleDiagnostic || sourceSkinReport == null))
            throw new InvalidOperationException("Requested native source skin lifecycle requires an actual source-selected model and report");
        source = model;
        root = new GameObject("Nova recovered survivor display");
        var map = new Dictionary<Transform, Transform>();
        if (!actual)
            copy = Copy(model, root.transform, map);
        else
        {
            if (sourceSkinLifecycleDiagnostic)
                nativeSourceSkinLifecycle = AndroidNativeSourceSkinLifecycle.PrepareInactive(model.gameObject, selectedBody, sourceSkinReport);
            foreach (var component in model.GetComponentsInChildren<MonoBehaviour>(true))
            {
                // The source model owns original melee hitboxes and incoming hurtboxes.
                // Preserve those gameplay components and animation-event receivers; the
                // unrelated model callbacks remain isolated from unavailable middleware.
                bool authoredEnabled = component.enabled;
                bool nativeSkinOwner = sourceSkinLifecycleDiagnostic && authoredEnabled &&
                                       nativeSourceSkinLifecycle && component.gameObject == nativeSourceSkinLifecycle.gameObject &&
                                       (component is RoR2.ModelSkinController || component is RoR2.CharacterModel);
                bool nativeSkinAdapter = sourceSkinLifecycleDiagnostic && component == nativeSourceSkinLifecycle;
                bool nativeGameplay = component is RoR2.AnimationEvents || component is RoR2.HitBox || component is RoR2.HitBoxGroup ||
                                      component is RoR2.HurtBox || component is RoR2.HurtBoxGroup;
                component.enabled = sourceSelected && (nativeSkinOwner || nativeSkinAdapter || nativeGameplay && authoredEnabled);
                // Optional native sound producers cannot enter Awake on this silent Android instance.
                if (component.GetType().Name.StartsWith("Ak", StringComparison.Ordinal))
                    UnityEngine.Object.DestroyImmediate(component);
            }
        }
        var shader = Resources.Load<Shader>("CommandoMaterialPreview");
        var simple = Resources.Load<Shader>("CommandoPreview");
        if ((!sourceSelected && (assets == null || assets.Length != 6)) || !shader || !shader.isSupported || !simple)
            throw new Exception("Nova display contract unavailable");
        if (!sourceSelected)
        {
            material = new Material(bundle.LoadAsset<Material>(assets[5]));
            material.shader = shader;
            material.shaderKeywords = new string[0];
            material.SetFloat("_EmissionEnabled", 1);
            AndroidMaterialPresentation.Apply(bundle.LoadAsset<Material>(assets[5]), material);
        }
        // PC references expose the temporary Blinn response as chrome-like. Retain
        // source palette/emission and stage lighting while omitting that unrecovered
        // character specular approximation. This is not the original deferred shader.
        if (aimingBody && !sourceSelected && !AndroidNativeDeferredPresentation.report.available)
        {
            if (!actual || !material.HasProperty("_AndroidCharacterMatte"))
                throw new Exception("Character palette shader contract unavailable");
            material.SetFloat("_AndroidCharacterMatte", 1);
        }
        var renderers = model.GetComponentsInChildren<Renderer>(true);
        if (sourceSelected)
        {
            if (!actual || renderers.Length == 0)
                throw new Exception("Source survivor model renderers unavailable");
            foreach (var renderer in renderers)
            {
                renderer.gameObject.layer = 30;
                var sources = renderer.sharedMaterials;
                var copies = new Material[sources.Length];
                for (int i = 0; i < sources.Length; i++)
                {
                    if (!sources[i])
                        continue;
                    copies[i] = new Material(sources[i]);
                    AndroidMaterialPresentation.Apply(sources[i], copies[i]);
                    ownedSurvivorMaterials.Add(copies[i]);
                }
                renderer.sharedMaterials = copies;
            }
        }
        else
            foreach (var path in assets.Skip(2).Take(3))
            {
                var mesh = bundle.LoadAsset<Mesh>(path);
                if (!mesh)
                    throw new Exception("Recovered display mesh missing");
                var src = renderers.Single(x => x.name == mesh.name);
                var target = actual ? src.transform : map[src.transform];
                Renderer renderer;
                if (actual)
                {
                    renderer = src;
                    renderer.enabled = true;
                    target.gameObject.layer = 30;
                    if (src is SkinnedMeshRenderer original)
                    {
                        original.sharedMesh = mesh;
                        original.updateWhenOffscreen = true;
                    }
                    else
                        target.GetComponent<MeshFilter>().sharedMesh = mesh;
                }
                else if (src is SkinnedMeshRenderer skin)
                {
                    var sk = target.gameObject.AddComponent<SkinnedMeshRenderer>();
                    sk.sharedMesh = mesh;
                    sk.bones = skin.bones.Select(x => map[x]).ToArray();
                    sk.rootBone = map[skin.rootBone];
                    sk.localBounds = skin.localBounds;
                    sk.updateWhenOffscreen = true;
                    renderer = sk;
                }
                else
                {
                    target.gameObject.AddComponent<MeshFilter>().sharedMesh = mesh;
                    renderer = target.gameObject.AddComponent<MeshRenderer>();
                }
                renderer.sharedMaterial = material;
            }
        if (root.GetComponentsInChildren<MonoBehaviour>(true).Length != 0)
            throw new Exception("Display unexpectedly contains gameplay behaviours");
        if (actual)
        {
            foreach (var collider in model.GetComponentsInChildren<Collider>(true))
                collider.enabled = false;
            var animator = model.GetComponent<Animator>();
            if (!animator)
                throw new Exception("Original survivor Animator missing");
            nativeAnimator = animator;
            if (sourceSelected && !sourceSkinLifecycleDiagnostic)
            {
                // Preserve the existing diagnostic path only when the new opt-in is off.
                var rootPath = "Assets/WholeGame/RoR2/Base/Characters/" + sourceSurvivor + "/";
                animator.runtimeAnimatorController =
                    WholeCatalogComposed.LoadOwnedContent<RuntimeAnimatorController>(rootPath + "anim" + sourceSurvivor + ".controller");
                animator.avatar = WholeCatalogComposed.LoadOwnedContent<Avatar>(rootPath + "mdl" + sourceSurvivor + "Avatar.asset");
            }
            else if (!sourceSelected)
            {
                animator.runtimeAnimatorController = bundle.LoadAsset<RuntimeAnimatorController>(assets[0]);
                animator.avatar = bundle.LoadAsset<Avatar>(assets[1]);
            }
            // Opt-in source models leave both controller/avatar fields native-owned.
            // ModelSkinController's typed async provider supplies them through the selected SkinDef.
            if (!sourceSkinLifecycleDiagnostic)
            {
                animator.applyRootMotion = false;
                animator.cullingMode = AnimatorCullingMode.AlwaysAnimate;
            }
            animator.enabled = !sourceSkinLifecycleDiagnostic;
            if (aimingBody)
            {
                nativeAim = model.GetComponent<RoR2.AimAnimator>();
                if (!nativeAim || nativeAim.inputBank != aimingBody.inputBank ||
                    nativeAim.directionComponent != aimingBody.characterDirection ||
                    (!sourceSelected && nativeAim.aimType != RoR2.AimAnimator.AimType.Direct))
                    throw new Exception("Original Commando aim links/layers unavailable");
            }
            model.gameObject.SetActive(true);
            if (sourceSkinLifecycleDiagnostic)
                CaptureNativeSourceSkinReport();
            if (nativeAim && !sourceSkinLifecycleDiagnostic)
            {
                animator.Update(0);
                if (!sourceSelected && (animator.GetLayerIndex("AimPitch") < 0 || animator.GetLayerIndex("AimYaw") < 0))
                    throw new Exception("Initialized original Commando aim layers unavailable");
                nativeAim.enabled = true;
            }
        }
        grid = new Texture2D(64, 64);
        for (int y = 0; y < 64; y++)
            for (int x = 0; x < 64; x++)
                grid.SetPixel(x, y, x < 2 || y < 2 ? new Color(.2f, .24f, .3f) : new Color(.075f, .09f, .12f));
        grid.Apply();
        grid.wrapMode = TextureWrapMode.Repeat;
        floorMaterial = new Material(simple);
        floorMaterial.mainTexture = grid;
        floorMaterial.mainTextureScale = Vector2.one * 50;
        if (floor)
            floor.GetComponent<Renderer>().sharedMaterial = floorMaterial;
        camera = new GameObject("Nova diagnostic camera").AddComponent<Camera>();
        camera.transform.SetParent(root.transform, false);
        camera.depth = 100;
        camera.cullingMask = 1 << 30;
        camera.clearFlags = CameraClearFlags.SolidColor;
        camera.backgroundColor = new Color(.04f, .05f, .07f);
        camera.orthographic = true;
        camera.orthographicSize = 8;
        camera.nearClipPlane = .01f;
        camera.farClipPlane = 200;
        var light = new GameObject("Nova diagnostic light").AddComponent<Light>();
        light.transform.SetParent(root.transform, false);
        light.type = LightType.Directional;
        light.transform.rotation = Quaternion.Euler(45, -30, 0);
        presentationCamera = camera.gameObject.AddComponent<AndroidPresentationCamera>();
        presentationCamera.fallbackLight = light;
        aim = new GameObject("Input aim indicator").AddComponent<LineRenderer>();
        aim.transform.SetParent(root.transform, false);
        aim.gameObject.layer = 30;
        aim.sharedMaterial = floorMaterial;
        aim.positionCount = 2;
        aim.startWidth = aim.endWidth = .1f;
    }
    public void ConfigureThirdPerson(RoR2.CharacterBody body)
    {
        thirdPerson = new NovaThirdPersonView(camera, body);
        aim.enabled = false;
    }
    public void Observe(Vector3 bodyPosition, Vector3 direction)
    {
        if (!actualModel)
            copy.SetPositionAndRotation(source.position, source.rotation);
        if (thirdPerson != null)
        {
            thirdPerson.Place();
            return;
        }
        camera.transform.position = new Vector3(bodyPosition.x, bodyPosition.y + 10, bodyPosition.z - 12);
        camera.transform.LookAt(bodyPosition + Vector3.up);
        aim.SetPosition(0, bodyPosition + Vector3.up);
        aim.SetPosition(1, bodyPosition + Vector3.up + direction * 3);
    }
    public void Dispose()
    {
        if (nativeAim)
            nativeAim.enabled = false;
        if (actualModel && source)
        {
            source.gameObject.SetActive(false);
            if (nativeSourceSkinLifecycle)
                nativeSourceSkinLifecycle.RecordDisplayDeactivated();
        }
        if (root)
            UnityEngine.Object.Destroy(root);
        if (material)
            UnityEngine.Object.Destroy(material);
        foreach (var owned in ownedSurvivorMaterials)
            if (owned)
                UnityEngine.Object.Destroy(owned);
        ownedSurvivorMaterials.Clear();
        if (floorMaterial)
            UnityEngine.Object.Destroy(floorMaterial);
        if (grid)
            UnityEngine.Object.Destroy(grid);
    }
}
