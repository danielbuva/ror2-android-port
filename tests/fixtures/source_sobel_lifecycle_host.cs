using System;
using System.Collections.Generic;
using System.Reflection;

// Inert authored objects execute the production lifecycle without a game installation.
class Obj
{
    public bool destroyed;
    public string name;
    public static implicit operator bool(Obj value) => value != null && !value.destroyed;
    public virtual Obj Copy() => (Obj)MemberwiseClone();
    protected static T Instantiate<T>(T value) where T : Obj => (T)value.Copy();
    protected static void Destroy(Obj value) { if (value != null) value.destroyed = true; }
}
class Transform { public void SetParent(Transform parent, bool world) { } }
class GameObject : Obj
{
    public int layer;
    public bool activeInHierarchy;
    public Transform transform = new Transform();
    public List<Behaviour> components = new List<Behaviour>();
    public GameObject(string label) { name = label; }
    public T AddComponent<T>() where T : Behaviour, new() { var x = new T { gameObject = this }; components.Add(x); return x; }
    public T GetComponent<T>() where T : Behaviour { return components.Find(x => x is T) as T; }
}
class Behaviour : Obj { public GameObject gameObject; public bool enabled = true; public bool isActiveAndEnabled => enabled; }
class ScriptableObject : Obj { public static T CreateInstance<T>() where T : new() => new T(); }
class BoolParameter { public bool value = true; }
class FloatParameter { public float value; }
class PostProcessEffectSettings : Obj
{
    public bool active = true;
    public BoolParameter enabled = new BoolParameter();
    public override Obj Copy() { var x = (PostProcessEffectSettings)base.Copy(); x.enabled = new BoolParameter { value = enabled.value }; return x; }
}
class AmbientOcclusion : PostProcessEffectSettings { }
class ColorGrading : PostProcessEffectSettings { }
class SobelOutline : PostProcessEffectSettings
{
    public FloatParameter outlineIntensity = new FloatParameter(), outlineScale = new FloatParameter();
    public override Obj Copy() { var x = (SobelOutline)base.Copy(); x.outlineIntensity = new FloatParameter { value = outlineIntensity.value }; x.outlineScale = new FloatParameter { value = outlineScale.value }; return x; }
}
class PostProcessProfile : ScriptableObject
{
    public List<PostProcessEffectSettings> settings = new List<PostProcessEffectSettings>();
    public void AddSettings(PostProcessEffectSettings x) { settings.Add(x); }
    public bool TryGetSettings<T>(out T x) where T : PostProcessEffectSettings { x = settings.Find(s => s is T) as T; return x; }
}
class PostProcessVolume : Behaviour
{
    public PostProcessProfile sharedProfile;
    public bool isGlobal = true;
    public PostProcessLayer targetLayer;
    public float priority, weight = 1, blendDistance;
}
class Mask { public int value = 1 << 20; }
class Bundle { public Obj settings; }
class PostProcessLayer : Behaviour
{
    PostProcessResources m_Resources;
    public PostProcessResources Bound => m_Resources;
    public void Init(PostProcessResources value) { m_Resources = value; }
    public Mask volumeLayer = new Mask();
    public Dictionary<Type,Bundle> bundles = new Dictionary<Type,Bundle>();
    public Bundle GetBundle<T>() => bundles[typeof(T)];
}
class PostProcessResources : ScriptableObject
{
    public class Shaders { public Shader multiScaleAO, lut2DBaker, uber; public Shaders Clone() => (Shaders)MemberwiseClone(); }
    public class ComputeShaders {
        public ComputeShader lut3DBaker, multiScaleAODownsample1, multiScaleAODownsample2, multiScaleAORender, multiScaleAOUpsample, autoExposure;
        public ComputeShaders Clone() => (ComputeShaders)MemberwiseClone();
    }
    public Shaders shaders = new Shaders();
    public ComputeShaders computeShaders = new ComputeShaders();
}
class Camera : Behaviour
{
    public static event Action<Camera> onPostRender;
    public T GetComponent<T>() where T : Behaviour => gameObject.GetComponent<T>();
    public static void Render(Camera x) { onPostRender?.Invoke(x); }
    public static bool HasSubscribers => onPostRender != null;
}
class Shader : Obj { public bool isSupported = true; }
class ComputeShader : Obj { public bool HasKernel(string kernel) => kernel != Resources.missingKernel; }
class SystemInfo { public static bool supportsComputeShaders = true; }
class Resources {
    public static string missingKernel, missingResource;
    public static T Load<T>(string name) where T : Obj, new() => name == missingResource ? null : new T { name = name };
}
class LegacyShaderAPI { public static Shader shader = new Shader(); public static Shader Find(string name) => shader; }
class RoR2Application : Behaviour { public Behaviour[] BehavioursToEnableDuringStartup; }
class Scene { public GameObject[] roots; public GameObject[] GetRootGameObjects() => roots; }
class SceneManager { public static Scene scene; public static Scene GetActiveScene() => scene; }
class Harness : Obj
{
    GameObject stagingRoot = new GameObject("staging");
    Camera viewCamera;
    PostProcessVolume sourceSobelVolume, sourceGradingVolume;
    PostProcessProfile sourceSobelProfile, sourceGradingProfile;
    SobelOutline sourceSobelSettings;
    PostProcessResources sourceGraphicsResources;
    class SourceSobelObservation
    {
        public bool volumeActiveWhenRendered, renderedCameraObserved, blendedEnabled, shaderSupported, retired;
        public float outlineIntensity, outlineScale;
        public bool ambientOcclusionEnabled, colorGradingEnabled, ownedResourcesBound;
        public int computeKernelsVerified;
    }
    SourceSobelObservation sourceSobelObservation;
    __METHODS__
    static void Check(bool x, string why) { if (!x) throw new Exception(why); }
    static void Reject(Action action) { try { action(); } catch (InvalidOperationException) { return; } throw new Exception("invalid source contract accepted"); }
    static void Main()
    {
        var appRoot = new GameObject("RoR2Application") { layer = 20 };
        var app = appRoot.AddComponent<RoR2Application>();
        var source = appRoot.AddComponent<PostProcessVolume>(); source.enabled = false;
        source.sharedProfile = new PostProcessProfile { name = "ppApplication_opt" };
        var setting = new SobelOutline(); setting.outlineIntensity.value = .37f; setting.outlineScale.value = 2.5f;
        source.sharedProfile.settings.Add(setting);
        source.sharedProfile.settings.Add(new AmbientOcclusion());
        source.sharedProfile.settings.Add(new ColorGrading { active = false });
        var grading = appRoot.AddComponent<PostProcessVolume>(); grading.enabled = false; grading.priority = 100;
        grading.sharedProfile = new PostProcessProfile { name = "ppDisabler_opt" };
        grading.sharedProfile.settings.Add(new ColorGrading());
        grading.sharedProfile.settings.Add(new SobelOutline { active = false });
        app.BehavioursToEnableDuringStartup = new Behaviour[] { grading, source };
        var stage = new Scene { roots = new[] { appRoot } };
        SceneManager.scene = new Scene { roots = new GameObject[0] }; // Active scene is selected later.
        var cameraRoot = new GameObject("camera");
        var camera = cameraRoot.AddComponent<Camera>(); var layer = cameraRoot.AddComponent<PostProcessLayer>();
        var original = new PostProcessResources(); original.shaders.uber = new Shader(); original.computeShaders.autoExposure = new ComputeShader();
        layer.Init(original);
        var owner = new Harness { viewCamera = camera };
        appRoot.activeInHierarchy = true; Reject(() => owner.PrepareSourceSobel(stage)); appRoot.activeInHierarchy = false;
        layer.volumeLayer.value = 0; Reject(() => owner.PrepareSourceSobel(stage)); layer.volumeLayer.value = 1 << 20;
        LegacyShaderAPI.shader.isSupported = false; Reject(() => owner.PrepareSourceSobel(stage)); LegacyShaderAPI.shader.isSupported = true;
        Resources.missingKernel = "MultiScaleVOUpSample_MSAA_premin_blendout";
        Reject(() => owner.PrepareSourceSobel(stage)); owner.ReleaseSourceSobel(); Resources.missingKernel = null;
        Check(layer.Bound == original && !original.destroyed, "failed resource setup changed original");
        Resources.missingResource = "SourceCameraLut2DBaker";
        Reject(() => owner.PrepareSourceSobel(stage)); owner.ReleaseSourceSobel(); Resources.missingResource = null;
        owner.PrepareSourceSobel(stage);
        Check(!appRoot.activeInHierarchy && !source.enabled && !grading.enabled, "source application or volume changed");
        Check(source.sharedProfile.settings.Count == owner.sourceSobelProfile.settings.Count && grading.sharedProfile.settings.Count == owner.sourceGradingProfile.settings.Count, "source settings missing");
        Check(!owner.sourceSobelProfile.settings[2].active && !owner.sourceGradingProfile.settings[1].active, "inactive source effects activated");
        Check(owner.sourceSobelSettings != setting && owner.sourceSobelSettings.outlineIntensity.value == .37f && owner.sourceSobelSettings.outlineScale.value == 2.5f, "source values not cloned exactly");
        Check(owner.sourceGradingVolume.priority == grading.priority && owner.sourceSobelVolume.weight == source.weight, "volume blend values changed");
        Check(layer.Bound == owner.sourceGraphicsResources && layer.Bound != original && layer.Bound.shaders != original.shaders && layer.Bound.computeShaders != original.computeShaders, "resource tables shared");
        Check(layer.Bound.shaders.uber == original.shaders.uber && layer.Bound.computeShaders.autoExposure == original.computeShaders.autoExposure && original.shaders.multiScaleAO == null && original.computeShaders.lut3DBaker == null, "unrelated or original resources changed");
        Check(owner.sourceSobelObservation.computeKernelsVerified == 22 && owner.sourceSobelObservation.ownedResourcesBound, "compute readiness not measured");
        layer.bundles[typeof(SobelOutline)] = new Bundle { settings = owner.sourceSobelSettings };
        layer.bundles[typeof(AmbientOcclusion)] = new Bundle { settings = owner.sourceSobelProfile.settings[1] };
        layer.bundles[typeof(ColorGrading)] = new Bundle { settings = owner.sourceGradingProfile.settings[0] };
        Camera.Render(new GameObject("foreign").AddComponent<Camera>()); Check(!owner.sourceSobelObservation.renderedCameraObserved, "foreign camera sampled");
        Camera.Render(camera);
        Check(owner.sourceSobelObservation.renderedCameraObserved && owner.sourceSobelObservation.blendedEnabled && owner.sourceSobelObservation.volumeActiveWhenRendered && owner.sourceSobelObservation.ambientOcclusionEnabled && owner.sourceSobelObservation.colorGradingEnabled, "rendered settings not observed");
        Check(!Camera.HasSubscribers, "one-shot callback retained");
        var ownedProfile = owner.sourceSobelProfile; var ownedGrading = owner.sourceGradingProfile; var ownedResources = owner.sourceGraphicsResources;
        owner.ReleaseSourceSobel(); owner.ReleaseSourceSobel();
        Check(!owner.sourceSobelVolume.enabled && !owner.sourceGradingVolume.enabled && owner.sourceSobelObservation.retired && ownedProfile.destroyed && ownedGrading.destroyed && ownedResources.destroyed, "owned assets or registration retained");
        foreach (var profile in new[] { ownedProfile, ownedGrading }) foreach (var value in profile.settings) Check(value.destroyed, "owned setting retained");
        Check(!setting.destroyed && setting.outlineIntensity.value == .37f && !original.destroyed && !source.enabled && !grading.enabled && !appRoot.activeInHierarchy, "source asset changed during cleanup");
        Console.WriteLine("source Sobel lifecycle PASS");
    }
}
