using System;
using System.Collections.Generic;

namespace UnityEngine
{
    public class Object
    {
        public string name;
        public int GetInstanceID() => 1;
        public static implicit operator bool(Object value) => !ReferenceEquals(value, null);
        public static bool operator !(Object value) => ReferenceEquals(value, null);
        public static bool operator true(Object value) => !ReferenceEquals(value, null);
        public static bool operator false(Object value) => ReferenceEquals(value, null);
        public static T FindObjectOfType<T>() where T : Object => null;
        public static T Instantiate<T>(T original, Transform parent, bool worldPositionStays) where T : Object => original;
        public static void DestroyImmediate(Object value) { }
    }

    public class Component : Object
    {
        public GameObject gameObject;
        public Transform transform => gameObject == null ? null : gameObject.transform;
        public T GetComponent<T>() where T : Component => null;
    }

    public class Behaviour : Component
    {
        public bool enabled = true;
        public bool isActiveAndEnabled => enabled;
    }

    public class MonoBehaviour : Behaviour { }

    public class Transform : Component { }

    public class GameObject : Object
    {
        public Transform transform = new Transform();
        public T GetComponent<T>() where T : Component => null;
        public T AddComponent<T>() where T : Component => null;
        public T[] GetComponents<T>() where T : Component => Array.Empty<T>();
    }

    public static class Time { public static float realtimeSinceStartup; }
    public static class Mathf { public static float Max(float left, float right) => left > right ? left : right; }
}

namespace UnityEngine.SceneManagement
{
    public struct Scene { public string name; }
    public enum LoadSceneMode { Single, Additive }
    public static class SceneManager
    {
        public static event Action<Scene, LoadSceneMode> sceneLoaded;
    }
}

namespace UnityEngine.ResourceManagement.AsyncOperations
{
    public enum AsyncOperationStatus { None, Succeeded, Failed }
    public struct AsyncOperationHandle<T>
    {
        public bool IsValid() => false;
        public bool IsDone => false;
        public T Result => default(T);
        public AsyncOperationStatus Status => AsyncOperationStatus.None;
        public event Action<AsyncOperationHandle<T>> Completed
        {
            add { }
            remove { }
        }
    }
}

namespace UnityEngine.AddressableAssets
{
    using UnityEngine.ResourceManagement.AsyncOperations;
    public static class Addressables { public static void Release<T>(AsyncOperationHandle<T> handle) { } }
}

namespace RoR2
{
    using UnityEngine;
    using UnityEngine.ResourceManagement.AsyncOperations;

    public class MusicController : MonoBehaviour
    {
        public static MusicController Instance;
        public bool enableMusicSystem = true;
        public Object target;
        public void PreloadForCutsceneStart() { }
    }

    public static class LegacyResourcesAPI
    {
        public static bool GetGuid(string path, out string guid) { guid = null; return false; }
        public static AsyncOperationHandle<T> LoadAsync<T>(string path) => default(AsyncOperationHandle<T>);
    }

    public static class WwiseIntegrationManager { public static bool noAudio; }
    public static class CameraRigController { public static List<object> readOnlyInstancesList; }
    public class TeleporterInteraction : Object { public static TeleporterInteraction instance; }
    public class SceneDefinition : Object { public string cachedName; }
    public static class SceneCatalog { public static SceneDefinition mostRecentSceneDef; }
}

public static class GameAudioOriginalOwner
{
    public static bool Ready;
    public static bool OriginalTermsReturned;
}

public sealed class PortSessionOriginalAudioOwner : UnityEngine.MonoBehaviour { }
public static class AkSoundEngine { public static bool IsInitialized() => false; }
public enum AKRESULT { AK_Success = 1 }
public sealed class AkAudioListener : UnityEngine.Behaviour
{
    public bool isDefaultListener;
    public ulong GetAkGameObjectID() => 0;
}
public sealed class AkGameObj : UnityEngine.Behaviour { }
