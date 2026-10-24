using System;
using System.Collections.Generic;

// Inert authored stubs. The three methods below are extracted from production.
class Obj
{
    public bool destroyed;
    public string name;
    public static implicit operator bool(Obj value) => value != null && !value.destroyed;
    protected static T Instantiate<T>(T value) where T : SobelOutline => (T)value.Copy();
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
class SobelOutline : Obj
{
    public bool active = true;
    public BoolParameter enabled = new BoolParameter();
    public FloatParameter outlineIntensity = new FloatParameter(), outlineScale = new FloatParameter();
    public SobelOutline Copy() => new SobelOutline {
        active = active, enabled = new BoolParameter { value = enabled.value },
        outlineIntensity = new FloatParameter { value = outlineIntensity.value },
        outlineScale = new FloatParameter { value = outlineScale.value }
    };
}
class PostProcessProfile : ScriptableObject
{
    public List<Obj> settings = new List<Obj>();
    public void AddSettings(Obj x) { settings.Add(x); }
    public bool TryGetSettings(out SobelOutline x) { x = settings.Find(s => s is SobelOutline) as SobelOutline; return x; }
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
    public Mask volumeLayer = new Mask();
    public Bundle bundle = new Bundle();
    public Bundle GetBundle<T>() => bundle;
}
class Camera : Behaviour
{
    public static event Action<Camera> onPostRender;
    public T GetComponent<T>() where T : Behaviour => gameObject.GetComponent<T>();
    public static void Render(Camera x) { onPostRender?.Invoke(x); }
    public static bool HasSubscribers => onPostRender != null;
}
class Shader : Obj { public bool isSupported = true; }
class LegacyShaderAPI { public static Shader shader = new Shader(); public static Shader Find(string name) => shader; }
class RoR2Application : Behaviour { public Behaviour[] BehavioursToEnableDuringStartup; }
class Scene { public GameObject[] roots; public GameObject[] GetRootGameObjects() => roots; }
class SceneManager { public static Scene scene; public static Scene GetActiveScene() => scene; }
class Harness : Obj
{
    GameObject stagingRoot = new GameObject("staging");
    Camera viewCamera;
    PostProcessVolume sourceSobelVolume;
    PostProcessProfile sourceSobelProfile;
    SobelOutline sourceSobelSettings;
    class SourceSobelObservation
    {
        public bool volumeActiveWhenRendered, renderedCameraObserved, blendedEnabled, shaderSupported, retired;
        public float outlineIntensity, outlineScale;
    }
    SourceSobelObservation sourceSobelObservation;
    __METHODS__
    static void Check(bool x, string why) { if (!x) throw new Exception(why); }
    static void Main()
    {
        var appRoot = new GameObject("RoR2Application") { layer = 20 };
        var app = appRoot.AddComponent<RoR2Application>();
        var source = appRoot.AddComponent<PostProcessVolume>();
        source.enabled = false;
        source.sharedProfile = new PostProcessProfile { name = "ppApplication_opt" };
        var setting = new SobelOutline();
        setting.outlineIntensity.value = .75f; setting.outlineScale.value = 3;
        source.sharedProfile.settings.Add(setting);
        source.sharedProfile.settings.Add(new Obj()); // An unrecovered effect is never activated.
        app.BehavioursToEnableDuringStartup = new Behaviour[] { source };
        SceneManager.scene = new Scene { roots = new[] { appRoot } };
        var cameraRoot = new GameObject("camera");
        var camera = cameraRoot.AddComponent<Camera>();
        var layer = cameraRoot.AddComponent<PostProcessLayer>();
        var owner = new Harness { viewCamera = camera };
        appRoot.activeInHierarchy = true;
        try { owner.PrepareSourceSobel(); throw new Exception("active application accepted"); }
        catch (InvalidOperationException) { }
        appRoot.activeInHierarchy = false;
        layer.volumeLayer.value = 0;
        try { owner.PrepareSourceSobel(); throw new Exception("excluded volume layer accepted"); }
        catch (InvalidOperationException) { }
        layer.volumeLayer.value = 1 << 20;
        LegacyShaderAPI.shader.isSupported = false;
        try { owner.PrepareSourceSobel(); throw new Exception("unsupported shader accepted"); }
        catch (InvalidOperationException) { }
        LegacyShaderAPI.shader.isSupported = true;
        owner.PrepareSourceSobel();
        Check(!appRoot.activeInHierarchy && !source.enabled, "source application or volume changed");
        Check(source.sharedProfile.settings.Count == 2 && owner.sourceSobelProfile.settings.Count == 1, "unrecovered settings copied");
        Check(owner.sourceSobelSettings != setting && owner.sourceSobelSettings.outlineIntensity.value == .75f && owner.sourceSobelSettings.outlineScale.value == 3, "source settings not cloned exactly");
        layer.bundle.settings = owner.sourceSobelSettings;
        Camera.Render(new GameObject("foreign").AddComponent<Camera>());
        Check(!owner.sourceSobelObservation.renderedCameraObserved, "foreign camera sampled");
        Camera.Render(camera);
        Check(owner.sourceSobelObservation.renderedCameraObserved && owner.sourceSobelObservation.blendedEnabled && owner.sourceSobelObservation.volumeActiveWhenRendered, "rendered settings not observed");
        Check(!Camera.HasSubscribers, "one-shot callback retained");
        var ownedProfile = owner.sourceSobelProfile; var ownedSettings = owner.sourceSobelSettings;
        owner.ReleaseSourceSobel(); owner.ReleaseSourceSobel();
        Check(!owner.sourceSobelVolume.enabled && owner.sourceSobelObservation.retired && ownedSettings.destroyed && ownedProfile.destroyed, "owned assets or registration retained");
        Check(!setting.destroyed && setting.outlineIntensity.value == .75f && !source.enabled && !appRoot.activeInHierarchy, "source asset changed during cleanup");
        Console.WriteLine("source Sobel lifecycle PASS");
    }
}
