using System;
using System.Collections.Generic;

namespace UnityEngine
{
    public class Object
    {
        static int nextInstanceId;
        readonly int instanceId = ++nextInstanceId;
        public bool destroyed;
        public string name;
        public int GetInstanceID() => instanceId;
        public static implicit operator bool(Object value) => !ReferenceEquals(value, null) && !value.destroyed;
        public static bool operator !(Object value) => !(bool)value;
        public static void Destroy(Object value) { if (!ReferenceEquals(value, null)) value.destroyed = true; }
    }
    public class Component : Object
    {
        public GameObject gameObject;
        public bool enabled = true;
        public Transform transform => gameObject.transform;
        public T GetComponent<T>() where T : Component => gameObject.GetComponent<T>();
        public T GetComponentInChildren<T>(bool includeInactive) where T : Component => gameObject.GetComponent<T>();
    }
    public class Behaviour : Component
    {
        public bool isActiveAndEnabled => enabled && gameObject && gameObject.activeInHierarchy;
    }
    public class MonoBehaviour : Behaviour { }
    public class GameObject : Object
    {
        readonly Dictionary<Type, Component> components = new Dictionary<Type, Component>();
        public bool activeSelf = true;
        public bool activeInHierarchy => activeSelf;
        public int layer;
        public UnityEngine.Transform transform = new UnityEngine.Transform();
        public GameObject(string name) { this.name = name; transform.gameObject = this; }
        public T AddComponent<T>() where T : Component, new()
        {
            var component = new T { gameObject = this };
            components.Add(typeof(T), component);
            return component;
        }
        public T GetComponent<T>() where T : Component => components.TryGetValue(typeof(T), out var component) ? (T)component : null;
        public T GetComponentInChildren<T>(bool includeInactive) where T : Component => GetComponent<T>();
    }
    public class Material : Object
    {
        public Shader shader = new Shader { name = "test-shader" };
        public Material(string name) { this.name = name; }
        public Material(Material source) { name = source.name + ".copy"; shader = source.shader; }
    }
    public class Shader : Object { }
    public struct Vector3
    {
        public float x, y, z;
        public Vector3(float x, float y, float z) { this.x = x; this.y = y; this.z = z; }
        public static Vector3 zero => new Vector3();
    }
    public struct Quaternion { public float x, y, z, w; }
    public struct Rect { public float x, y, width, height; }
    public struct Bounds
    {
        public Vector3 center, extents;
        public Vector3 min => new Vector3 { x = center.x - extents.x, y = center.y - extents.y, z = center.z - extents.z };
        public Vector3 max => new Vector3 { x = center.x + extents.x, y = center.y + extents.y, z = center.z + extents.z };
    }
    public enum CameraClearFlags { Skybox = 1, Color = 2, Depth = 3, Nothing = 4 }
    public class Renderer : Behaviour
    {
        public Material[] sharedMaterials = Array.Empty<Material>();
        public int getSharedMaterialsCalls, sharedMaterialGetterCalls;
        public Material sharedMaterial { get { sharedMaterialGetterCalls++; if (throwSharedMaterialGetter) throw new InvalidOperationException("synthetic sharedMaterial read failure"); return sharedMaterials.Length > 0 ? sharedMaterials[0] : null; } }
        public bool isVisible;
        public bool throwSharedMaterialGetter;
        public Bounds bounds;
        public void GetSharedMaterials(List<Material> destination)
        {
            getSharedMaterialsCalls++;
            destination.Clear();
            destination.AddRange(sharedMaterials);
        }
    }
    public class Mesh : Object { }
    public class MeshFilter : Component { public Mesh sharedMesh; }
    public class SkinnedMeshRenderer : Renderer { public Mesh sharedMesh; }
    public static class QualitySettings {public static int activeColorSpace=1;}
    public class Camera : Behaviour
    {
        public static readonly List<Camera> enabledCameras = new List<Camera>();
        public static int getAllCamerasCalls;
        public static int growBeforeGet, removedBeforeGet;
        public static bool throwCameraCount;
        public static bool nonFiniteProjection;
        public static int allCamerasCount
        {
            get
            {
                if (throwCameraCount) throw new InvalidOperationException("synthetic camera count read failure");
                return enabledCameras.Count;
            }
        }
        public static int GetAllCameras(Camera[] destination)
        {
            getAllCamerasCalls++;
            while (growBeforeGet-- > 0)
                enabledCameras.Add(new GameObject("racing camera").AddComponent<Camera>());
            while (removedBeforeGet-- > 0 && enabledCameras.Count > 0)
                enabledCameras.RemoveAt(enabledCameras.Count - 1);
            if (destination == null) throw new NullReferenceException();
            if (destination.Length < allCamerasCount)
                throw new ArgumentException("GetAllCameras requires enough room for all enabled cameras");
            int count = enabledCameras.Count;
            for (int i = 0; i < count; i++) destination[i] = enabledCameras[i];
            return count;
        }
        public float depth, nearClipPlane = .3f, farClipPlane = 1000f, fieldOfView = 60f;
        public int cullingMask = -1, targetDisplay;
        public CameraClearFlags clearFlags = CameraClearFlags.Skybox;
        public bool orthographic;
        public bool allowHDR=true;
        public int renderingPath=-1,actualRenderingPath=3,depthTextureMode;
        public Rect rect = new Rect { width = 1, height = 1 };
        public Texture targetTexture;
        public Vector3 WorldToScreenPoint(Vector3 point) => nonFiniteProjection
            ? new Vector3(float.NaN, point.y, point.z)
            : point;
    }
    public class Texture : Object { }
    public class Transform : Component { public Vector3 position; public Quaternion rotation; }
    public class RuntimeAnimatorController : Object { public RuntimeAnimatorController() { name = "runtime controller"; } }
    public class Avatar : Object { public Avatar() { name = "avatar"; } }
    public class Animator : Component
    {
        public RuntimeAnimatorController runtimeAnimatorController;
        public Avatar avatar;
        public bool isInitialized;
        public int layerCount;
        public AnimatorStateInfo GetCurrentAnimatorStateInfo(int layer) => new AnimatorStateInfo { fullPathHash = 42, normalizedTime = .5f };
    }
    public struct AnimatorStateInfo { public int fullPathHash; public float normalizedTime; }
    public static class Time
    {
        public static bool throwFrameCount;
        public static int frameCountValue = 12;
        public static int frameCount { get { if (throwFrameCount) throw new InvalidOperationException("synthetic Unity frame read failure"); return frameCountValue; } }
        public static float realtimeSinceStartup = 34.5f;
    }
}

namespace RoR2
{
    public static class InstanceTracker
    {
        public static readonly Dictionary<Type, object> tracked = new Dictionary<Type, object>();
        public static bool throwGetInstancesList;
        public static System.Collections.Generic.List<T> GetInstancesList<T>()
        {
            if (throwGetInstancesList) throw new InvalidOperationException("synthetic tracker lookup failure");
            object values;
            if (tracked.TryGetValue(typeof(T), out values)) return (System.Collections.Generic.List<T>)values;
            var created = new System.Collections.Generic.List<T>(); tracked[typeof(T)] = created; return created;
        }
    }
    public static class WwiseIntegrationManager { public static bool noAudio; }
    public class CharacterBody : UnityEngine.MonoBehaviour { public int skinIndex; public ModelLocator modelLocator; public CharacterMaster master; }
    public class ModelLocator : UnityEngine.MonoBehaviour { public UnityEngine.Transform modelTransform; }
    public class CharacterModel : UnityEngine.MonoBehaviour
    {
        private static int maxMaterials = 2;
        private static UnityEngine.Material[][] sharedMaterialArrays;
        private static void InitSharedMaterialsArrays()
        {
            sharedMaterialArrays = new[]
            {
                new UnityEngine.Material[0],
                new UnityEngine.Material[1],
                new UnityEngine.Material[2]
            };
        }
        public struct RendererInfo
        {
            public UnityEngine.Renderer renderer;
            public UnityEngine.Material defaultMaterial;
            public int defaultShadowCastingMode;
            public bool ignoreOverlays;
        }
        public CharacterBody body;
        public RendererInfo[] baseRendererInfos;
        public bool forceUpdate;
        public VisibilityLevel visibility = VisibilityLevel.Visible;
        public int invisibilityCount;
        public bool GetMaterialsDirty() { return true; }
    }
    public enum VisibilityLevel { Invisible, Visible, Untargetable }
    public class CameraRigController : UnityEngine.MonoBehaviour
    {
        public static List<CameraRigController> readOnlyInstancesList = new List<CameraRigController>();
        public UnityEngine.GameObject target, firstPersonTarget;
        public CharacterBody targetBody;
        public int targetTeamIndex;
        public CameraTargetParams targetParams;
        public NetworkUser viewer;
        public LocalUser localUserViewer;
        public bool enableFading, hasOverride;
        public float fadeStartDistance, fadeEndDistance;
        public object cameraMode;
        public UnityEngine.Camera sceneCam;
        public bool IsOverrideCam(object provider) => false;
    }
    public class SceneCamera : UnityEngine.MonoBehaviour
    {
        public delegate void SceneCameraDelegate(SceneCamera value);
        public static event SceneCameraDelegate onSceneCameraPreRender;
        public static UnityEngine.Camera _camera;
        public UnityEngine.Camera camera;
        public CameraRigController cameraRigController;
        public static void RaisePreRender(SceneCamera value) { var callback = onSceneCameraPreRender; if (callback != null) callback(value); }
    }
    public class CameraTargetParams : UnityEngine.MonoBehaviour { }
    public class CharacterMaster : UnityEngine.MonoBehaviour { public PlayerCharacterMasterController playerCharacterMasterController; }
    public class PlayerCharacterMasterController : UnityEngine.MonoBehaviour { public NetworkUser networkUser; }
    public class NetworkUser : UnityEngine.MonoBehaviour
    {
        public static List<NetworkUser> readOnlyInstancesList = new List<NetworkUser>();
        public static List<NetworkUser> readOnlyLocalPlayersList = new List<NetworkUser>();
        public bool isLocalPlayer;
        public LocalUser localUser;
        public CameraRigController cameraRigController;
    }
    public class LocalUser
    {
        public int id;
        public NetworkUser currentNetworkUser;
        public CharacterBody cachedBody;
        public CameraRigController cameraRigController;
    }
    public static class LocalUserManager { public static List<LocalUser> readOnlyLocalUsersList = new List<LocalUser>(); }
    public class ModelSkinController : UnityEngine.MonoBehaviour
    {
        public int currentSkinIndex;
        public event Action<int> onSkinApplied;
        public void CompleteNativeSkin(int index) { currentSkinIndex = index; onSkinApplied?.Invoke(index); }
    }
}

public static class AndroidMaterialPresentation
{
    public static int applyCalls, releaseCalls;
    public static void Apply(UnityEngine.Material source, UnityEngine.Material copy) { applyCalls++; }
    public static void Release(UnityEngine.Material material) { releaseCalls++; }
}

// Host-only representation of the authored audio lifecycle readiness dependency.
// This does not simulate Wwise; it only lets the source-owner fixture exercise
// the same no-audio-or-Ready admission boundary used by production.
public static class GameAudioOriginalOwner
{
    public static bool Ready;
}
