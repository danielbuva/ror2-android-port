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
    public struct Vector3 { public float x, y, z; public static Vector3 zero => new Vector3(); }
    public struct Bounds { public Vector3 center, extents; }
    public class Renderer : Behaviour
    {
        public Material[] sharedMaterials = Array.Empty<Material>();
        public int getSharedMaterialsCalls, sharedMaterialGetterCalls;
        public Material sharedMaterial { get { sharedMaterialGetterCalls++; return sharedMaterials.Length > 0 ? sharedMaterials[0] : null; } }
        public bool isVisible;
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
    public class Camera : Behaviour { }
    public class Transform : Component { public Vector3 position; }
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
        public static int frameCount { get { if (throwFrameCount) throw new InvalidOperationException("synthetic Unity frame read failure"); return 12; } }
        public static float realtimeSinceStartup = 34.5f;
    }
}

namespace RoR2
{
    public static class WwiseIntegrationManager { public static bool noAudio; }
    public class CharacterBody : UnityEngine.MonoBehaviour { public int skinIndex; public ModelLocator modelLocator; public CharacterMaster master; }
    public class ModelLocator : UnityEngine.MonoBehaviour { public UnityEngine.Transform modelTransform; }
    public class CharacterModel : UnityEngine.MonoBehaviour
    {
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
        public static UnityEngine.Camera _camera;
        public UnityEngine.Camera camera;
        public CameraRigController cameraRigController;
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
