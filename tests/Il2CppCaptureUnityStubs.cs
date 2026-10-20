using System;
using System.Linq;
using System.Reflection;
using System.Text;
using System.Text.RegularExpressions;

namespace UnityEngine
{
    public enum LogType { Log, Warning, Error }
    public static class Application
    {
        public static string dataPath;
        public delegate void LogCallback(string condition, string stackTrace, LogType type);
        public static event LogCallback logMessageReceived;
        public static int Subscribers { get { return logMessageReceived == null ? 0 : logMessageReceived.GetInvocationList().Length; } }
        public static void Emit(string value) { if (logMessageReceived != null) logMessageReceived(value, "", LogType.Log); }
    }
    public static class JsonUtility
    {
        static string ReadString(string json, string key)
        {
            Match m = Regex.Match(json, "\\\"" + Regex.Escape(key) + "\\\"\\s*:\\s*\\\"([^\\\"]*)\\\"");
            return m.Success ? m.Groups[1].Value : null;
        }
        public static T FromJson<T>(string json) where T : new()
        {
            T value = new T();
            foreach (FieldInfo f in typeof(T).GetFields(BindingFlags.Instance | BindingFlags.Public))
            {
                if (f.FieldType == typeof(string)) f.SetValue(value, ReadString(json, f.Name));
                else if (f.FieldType == typeof(bool))
                {
                    Match m = Regex.Match(json, "\\\"" + Regex.Escape(f.Name) + "\\\"\\s*:\\s*(true|false)");
                    if (m.Success) f.SetValue(value, m.Groups[1].Value == "true");
                }
            }
            return value;
        }
        public static string ToJson(object value, bool prettyPrint)
        {
            var builder = new StringBuilder("{");
            bool first = true;
            foreach (FieldInfo field in value.GetType().GetFields(BindingFlags.Instance | BindingFlags.Public))
            {
                if (field.FieldType != typeof(string)) continue;
                if (!first) builder.Append(',');
                first = false;
                builder.Append('"').Append(field.Name).Append("\":\"").Append((field.GetValue(value) as string ?? "").Replace("\\", "\\\\").Replace("\"", "\\\"")).Append('"');
            }
            return builder.Append('}').ToString();
        }
    }
}
namespace UnityEditor
{
    public enum BuildTarget { Android, StandaloneOSX }
    public enum BuildResult { Unknown, Succeeded, Failed }
    public class GUID { public string value; public override string ToString() { return value; } }
    public static class SessionState { public static string request; public static string GetString(string key, string fallback) { return request ?? fallback; } }
    public static class BuildPipeline { public static bool isBuildingPlayer; }
    public static class EditorApplication
    {
        public static double timeSinceStartup;
        public static event Action update;
        public static void Tick() { if (update != null) update(); }
    }
}
namespace UnityEditor.Build
{
    public interface IPreprocessBuildWithReport { int callbackOrder { get; } void OnPreprocessBuild(UnityEditor.Build.Reporting.BuildReport report); }
    public interface IPostprocessBuildWithReport { int callbackOrder { get; } void OnPostprocessBuild(UnityEditor.Build.Reporting.BuildReport report); }
}
namespace UnityEditor.Build.Reporting
{
    public class BuildSummary
    {
        public UnityEditor.GUID guid;
        public UnityEditor.BuildTarget platform;
        public string outputPath;
        public UnityEditor.BuildResult result;
    }
    public class BuildReport { public BuildSummary summary; }
}
