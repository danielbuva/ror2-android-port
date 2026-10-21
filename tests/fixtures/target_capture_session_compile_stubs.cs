using System;
using System.Collections.Generic;

namespace UnityEngine.Scripting
{
    [AttributeUsage(AttributeTargets.Class | AttributeTargets.Method | AttributeTargets.Property | AttributeTargets.Constructor)]
    internal sealed class PreserveAttribute : Attribute { }
}

namespace UnityEngine
{
    public enum LogType { Error, Assert, Warning, Log, Exception }
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
        public static void Destroy(Object value) { }
        public static void DontDestroyOnLoad(Object value) { }
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

    public class MonoBehaviour : Behaviour { protected object StartCoroutine(System.Collections.IEnumerator routine) => null; }

    public class Transform : Component { public void SetParent(Transform parent, bool worldPositionStays) { } }

    public class GameObject : Object
    {
        public GameObject() { }
        public GameObject(string objectName) { name = objectName; }
        public bool activeSelf;
        public Transform transform = new Transform();
        public T GetComponent<T>() where T : Component => null;
        public T AddComponent<T>() where T : Component => null;
        public T[] GetComponents<T>() where T : Component => Array.Empty<T>();
        public void SetActive(bool active) { activeSelf = active; }
    }

    public static class Time { public static float realtimeSinceStartup; }
    public static class Application
    {
        public static string streamingAssetsPath = "/tmp";
        public static string persistentDataPath = "/tmp";
        public static event Action<string, string, LogType> logMessageReceived;
    }
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

    public sealed class TriggerIntroMusicStart : MonoBehaviour { }

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

    public static class WwiseIntegrationManager { public static bool noAudio; public static void Init() { } }
    public static class CameraRigController { public static List<object> readOnlyInstancesList; }
    public class MusicTrackDef : Object
    {
        [Obsolete(".name should not be used. Use .cachedName instead.", true)]
        public new string name;
        public string cachedName;
    }
    public class TeleporterInteraction : Object { public static TeleporterInteraction instance; public bool isIdle; }
    public class SceneDef : Object { public string cachedName; public MusicTrackDef mainTrack, bossTrack; }
    public static class SceneCatalog { public static SceneDef mostRecentSceneDef; }
}



public static class AkSoundEngine
{
    public const ulong AK_INVALID_GAME_OBJECT = ulong.MaxValue;
    public const uint AK_INVALID_PLAYING_ID = 0;
    public static bool IsInitialized() => false;
    public static AKRESULT GetRTPCValue(string name, ulong gameObject, uint playingId, out float value, ref int valueType)
    { value = 0f; return AKRESULT.AK_Success; }
}
public enum AKRESULT { AK_Success = 1 }
public enum AkQueryRTPCValue { RTPCValue_Default = 0, RTPCValue_Global = 1, RTPCValue_GameObject = 2, RTPCValue_PlayingID = 3, RTPCValue_Unavailable = 4 }
public sealed class AkAudioListener : UnityEngine.Behaviour
{
    public bool isDefaultListener;
    public ulong GetAkGameObjectID() => 0;
    public static ListenerCollection DefaultListeners = new ListenerCollection();
    public sealed class ListenerCollection { public readonly List<AkAudioListener> ListenerList = new List<AkAudioListener>(); }
}
public sealed class AkGameObj : UnityEngine.Behaviour { }

public static class GameAudioOriginalRequestBootstrap
{
    public static bool PassivePcmCaptureRequested;
    public static bool PassivePcmCaptureMusicOutputRequested;
    public static bool IsConfigured;
    public static Func<AkWwiseInitializationSettings> OriginalSettingsProvider;
    public static void ConfigureBeforeOriginalStartup() { }
}

public sealed class AkWwiseInitializationSettings : UnityEngine.Object
{
    private static AkWwisePlatformSettings m_ActivePlatformSettings;
    private static AkWwiseInitializationSettings instance;
    public static AkWwiseInitializationSettings Instance { get { return instance; } }
    public static AkWwisePlatformSettings ActivePlatformSettings { get { return m_ActivePlatformSettings; } }
    public bool IsValid => true;
    public System.Collections.Generic.List<string> PlatformSettingsNameList = new System.Collections.Generic.List<string>();
    public System.Collections.Generic.List<AkWwisePlatformSettings> PlatformSettingsList = new System.Collections.Generic.List<AkWwisePlatformSettings>();
}
public sealed class GameAudioOriginalPayloadCopy : IGameAudioOriginalPayloadCopyOperation
{
    public GameAudioOriginalPayloadCopy(string streamingRoot, string destination, System.Collections.Generic.IEnumerable<string> names, string receipt) { }
    public string Refusal => null;
    public System.Collections.IEnumerator CopyToOriginalSearchRoot() { yield break; }
}
public sealed class AkInitializer : UnityEngine.MonoBehaviour { }
public sealed class AkWwisePlatformSettings { public string SoundBankPersistentDataPath = "Audio"; }
public static class AkBasePathGetter
{
    public delegate void CustomPlatformNameGetter(ref string name);
    private static object Instance;
    public static CustomPlatformNameGetter GetCustomPlatformName;
    public static string GetPlatformName() { string value = null; GetCustomPlatformName?.Invoke(ref value); return value; }
}

public static class WholeCatalogComposed
{
    public static bool OriginalAudioLeaseHeld;
    public static string OriginalAudioLeaseIdentity;
    public static bool IsConfigured;
    public static string RetainForOriginalAudioOwner(string input) => "lease";
    public static T LoadOwnedContent<T>(string path) => default(T);
    public static void ReleaseOriginalAudioOwnerLease(string identity) { }
}
