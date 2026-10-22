using System;
using System.Collections;

namespace UnityEngine
{
    public static class Time { public static float realtimeSinceStartup { get { return 0f; } } }
    public static class Application { public static string persistentDataPath { get { return "/tmp/app"; } } }
    public sealed class AndroidJavaObject : IDisposable
    {
        public AndroidJavaObject(string name, params object[] args) { }
        public T Call<T>(string method, params object[] args) { return default(T); }
        public void Dispose() { }
    }
    public static class JsonUtility { public static T FromJson<T>(string value) { return default(T); } }
}

namespace UnityEngine.Networking
{
    public class DownloadHandler { public byte[] data { get { return new byte[0]; } } public string text { get { return ""; } } }
    public sealed class DownloadHandlerFile : DownloadHandler
    { public DownloadHandlerFile(string path, bool append) { } }
    public sealed class UnityWebRequest : IDisposable
    {
        public enum Result { Success, Failure }
        public int timeout;
        public Result result;
        public DownloadHandler downloadHandler;
        public static UnityWebRequest Get(string url) { return new UnityWebRequest(); }
        public IEnumerator SendWebRequest() { yield break; }
        public void Dispose() { }
    }
}

public interface IGameAudioOriginalPayloadCopyOperation { IEnumerator CopyToOriginalSearchRoot(); }
