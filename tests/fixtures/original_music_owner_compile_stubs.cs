using System;
using System.Collections.Generic;
using System.Linq;

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
        public static void Destroy(Object value) { }
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

    public class Transform : Component { public void SetParent(Transform parent, bool worldPositionStays) { } }

    public class GameObject : Object
    {
        private readonly List<Component> components = new List<Component>();
        public GameObject() { }
        public GameObject(string objectName) { name = objectName; }
        public bool activeSelf;
        public Transform transform = new Transform();
        public T GetComponent<T>() where T : Component => components.OfType<T>().FirstOrDefault();
        public T AddComponent<T>() where T : Component
        {
            var component = (T)Activator.CreateInstance(typeof(T));
            component.gameObject = this;
            components.Add(component);
            return component;
        }
        public T[] GetComponents<T>() where T : Component => Array.Empty<T>();
        public void SetActive(bool active) { activeSelf = active; }
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

    public sealed class TriggerIntroMusicStart : MonoBehaviour { }

    public class MusicController : MonoBehaviour
    {
        public static MusicController Instance;
        public bool enableMusicSystem = true;
        public Object target;
        private MusicTrackDef _currentTrack;
        private MusicTrackDef currentTrack { get { return _currentTrack; } set { _currentTrack = value; } }
        public void SetCurrentTrackForFixture(MusicTrackDef value) { currentTrack = value; }
        public static event Action pickTrackHook;
        private RoR2.WwiseUtils.RtpcSetter rtpcPlayerHealthValue, rtpcEnemyValue,
            rtpcTeleporterProximityValue, rtpcTeleporterDirectionValue, rtpcTeleporterPlayerStatus;
        public void PreloadForCutsceneStart() { }
    }

    public class MusicTrackDef : Object
    {
        [Obsolete(".name should not be used. Use .cachedName instead.", true)]
        public new string name;
        public string cachedName;
    }

    public static class LegacyResourcesAPI
    {
        public static bool GetGuid(string path, out string guid) { guid = null; return false; }
        public static AsyncOperationHandle<T> LoadAsync<T>(string path) => default(AsyncOperationHandle<T>);
    }

    public static class WwiseIntegrationManager { public static bool noAudio; }
    public static class CameraRigController { public static List<object> readOnlyInstancesList; }
    public class TeleporterInteraction : Object { public static TeleporterInteraction instance; public bool isIdle; }
    public class SceneDef : Object { public string cachedName; public MusicTrackDef mainTrack, bossTrack; }
    public static class SceneCatalog
    {
        private static SceneDef current;
        public static bool ThrowOnRead;
        public static SceneDef mostRecentSceneDef
        {
            get { if (ThrowOnRead) throw new InvalidOperationException("scene unavailable"); return current; }
            set { current = value; }
        }
    }
}

public static class GameAudioOriginalOwner
{
    public static bool Ready;
    public static bool OriginalTermsReturned;
}

public sealed class PortSessionOriginalAudioOwner : UnityEngine.MonoBehaviour { }
public static class AkSoundEngine
{
    public const ulong AK_INVALID_GAME_OBJECT = ulong.MaxValue;
    public const uint AK_INVALID_PLAYING_ID = 0;
    public static bool Initialized;
    public static int QueryCalls;
    public static string[] QueryNames = new string[3];
    public static ulong LastGameObject;
    public static uint LastPlayingId;
    public static AKRESULT QueryResult = AKRESULT.AK_Success;
    public static bool ReturnUnexpectedType;
    public static bool ReturnNonFinite;
    public static bool ThrowOnQuery;
    public static AKRESULT[] QueryResults;
    public static int[] QueryReturnedTypes;
    public static float[] QueryValues;
    public static bool IsInitialized() => Initialized;
    public static void ResetQueryControls()
    {
        QueryCalls = 0;
        QueryResult = AKRESULT.AK_Success;
        ReturnUnexpectedType = false;
        ReturnNonFinite = false;
        ThrowOnQuery = false;
        QueryResults = null;
        QueryReturnedTypes = null;
        QueryValues = null;
    }
    public static AKRESULT GetRTPCValue(string name, ulong gameObject, uint playingId, out float value, ref int valueType)
    {
        int i = QueryCalls++;
        if (i < QueryNames.Length) QueryNames[i] = name;
        LastGameObject = gameObject; LastPlayingId = playingId;
        if (ThrowOnQuery) throw new InvalidOperationException("fixture query failure");
        if (QueryReturnedTypes != null && i < QueryReturnedTypes.Length) valueType = QueryReturnedTypes[i];
        else if (ReturnUnexpectedType) valueType = (int)AkQueryRTPCValue.RTPCValue_GameObject;
        if (QueryValues != null && i < QueryValues.Length) value = QueryValues[i];
        else value = name == "Volume_Master" ? 100f : (name == "Volume_MSX" ? 80f : 65f);
        if (ReturnNonFinite) value = float.NaN;
        return QueryResults != null && i < QueryResults.Length ? QueryResults[i] : QueryResult;
    }
}

public enum AKRESULT { AK_Success = 1, AK_Fail = 2, AK_IDNotFound = 15 }
public enum AkQueryRTPCValue { RTPCValue_Default, RTPCValue_Global, RTPCValue_GameObject, RTPCValue_PlayingID, RTPCValue_Unavailable }
namespace RoR2.WwiseUtils { public struct RtpcSetter { public float value; } }
public sealed class AkAudioListener : UnityEngine.Behaviour
{
    public sealed class ManagedDefaultListeners { public readonly List<AkAudioListener> ListenerList = new List<AkAudioListener>(); }
    public static readonly ManagedDefaultListeners DefaultListeners = new ManagedDefaultListeners();
    public bool isDefaultListener;
    public ulong GetAkGameObjectID() => 0;
}
public sealed class AkGameObj : UnityEngine.Behaviour { }
