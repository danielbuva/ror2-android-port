using System;
using System.Collections;

namespace UnityEngine
{
    public enum LogType { Log }
    public enum LogOption { NoStacktrace }
    public static class Debug
    {
        public static void LogFormat(LogType type, LogOption option, object context, string format, params object[] args) { }
    }
    public static class Time { public static int frameCount; public static float realtimeSinceStartup { get { return 0f; } } }
    public static class Application { public static string persistentDataPath { get { return "/tmp/app"; } } }
    public class AndroidJavaObject : IDisposable
    {
        public System.Collections.Generic.Dictionary<string, object> fields = new System.Collections.Generic.Dictionary<string, object>();
        public Func<string, object[], object> onCall;
        public AndroidJavaObject(string name, params object[] args) { }
        public T Call<T>(string method, params object[] args) { return onCall == null ? default(T) : (T)onCall(method, args); }
        public T Get<T>(string field) { return (T)fields[field]; }
        public void Dispose() { }
    }
    public sealed class AndroidJavaClass : AndroidJavaObject
    {
        public static Func<string, object[], object> onCallStatic;
        public static object currentActivity;
        public AndroidJavaClass(string name) : base(name) { }
        public T GetStatic<T>(string field) { return (T)currentActivity; }
        public T CallStatic<T>(string method, params object[] args) { return (T)onCallStatic(method, args); }
    }
    public static class JsonUtility
    {
        public static object decoded;
        public static T FromJson<T>(string value) { return decoded == null ? default(T) : (T)decoded; }
        public static string ToJson(object value) { return ""; }
    }
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
