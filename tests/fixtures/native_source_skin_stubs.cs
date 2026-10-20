using System;
using System.Collections.Generic;

namespace UnityEngine
{
    public class Object
    {
        public bool destroyed;
        public string name;
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
        public UnityEngine.Transform transform = new UnityEngine.Transform();
        public GameObject(string name) { transform.gameObject = this; }
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
        public string name;
        public Material(string name) { this.name = name; }
        public Material(Material source) { name = source.name + ".copy"; }
    }
    public class Renderer : Component
    {
        public Material[] sharedMaterials = Array.Empty<Material>();
        public void GetSharedMaterials(List<Material> destination)
        {
            destination.Clear();
            destination.AddRange(sharedMaterials);
        }
    }
    public class Transform : Component { }
    public class RuntimeAnimatorController : Object { public RuntimeAnimatorController() { name = "runtime controller"; } }
    public class Avatar : Object { public Avatar() { name = "avatar"; } }
    public class Animator : Component
    {
        public RuntimeAnimatorController runtimeAnimatorController;
        public Avatar avatar;
        public bool isInitialized;
    }
}

namespace RoR2
{
    public static class WwiseIntegrationManager { public static bool noAudio; }
    public class CharacterBody : UnityEngine.MonoBehaviour { public int skinIndex; public ModelLocator modelLocator; }
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
    }
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
