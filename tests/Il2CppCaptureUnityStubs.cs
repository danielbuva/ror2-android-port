using System;
using System.Collections;
using System.Reflection;
using System.Text;
using System.Text.RegularExpressions;

namespace UnityEngine
{
    public enum LogType { Log, Warning, Error }
    public static class Application
    {
        public static string dataPath;
        public static void LogWarning(string value) { Console.Error.WriteLine(value); }
    }
    public static class Debug
    {
        public static void LogWarning(string value) { Console.Error.WriteLine(value); }
    }
    public static class JsonUtility
    {
        static string ReadString(string json, string key)
        {
            Match m = Regex.Match(json, "\"" + Regex.Escape(key) + "\"\\s*:\\s*\"((?:\\\\.|[^\"\\\\])*)\"");
            return m.Success ? m.Groups[1].Value.Replace("\\\"", "\"").Replace("\\\\\\", "\\\\") : null;
        }
        static string Quote(string value)
        {
            return "\"" + (value ?? "").Replace("\\", "\\\\").Replace("\"", "\\\"").Replace("\r", "\\r").Replace("\n", "\\n").Replace("\t", "\\t") + "\"";
        }
        static string Write(object value)
        {
            if (value == null) return "null";
            if (value is string) return Quote((string)value);
            if (value is bool) return (bool)value ? "true" : "false";
            if (value is int || value is long || value is double || value is float) return Convert.ToString(value, System.Globalization.CultureInfo.InvariantCulture);
            if (value is IEnumerable && !(value is string))
            {
                var parts = new System.Collections.Generic.List<string>();
                foreach (object item in (IEnumerable)value) parts.Add(Write(item));
                return "[" + String.Join(",", parts.ToArray()) + "]";
            }
            var fields = new System.Collections.Generic.List<string>();
            foreach (FieldInfo field in value.GetType().GetFields(BindingFlags.Instance | BindingFlags.Public))
                fields.Add(Quote(field.Name) + ":" + Write(field.GetValue(value)));
            return "{" + String.Join(",", fields.ToArray()) + "}";
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
                else if (f.FieldType == typeof(int) || f.FieldType == typeof(long))
                {
                    Match m = Regex.Match(json, "\\\"" + Regex.Escape(f.Name) + "\\\"\\s*:\\s*(-?[0-9]+)");
                    if (m.Success) f.SetValue(value, Convert.ChangeType(m.Groups[1].Value, f.FieldType));
                }
            }
            return value;
        }
        public static string ToJson(object value, bool prettyPrint) { return Write(value); }
    }
}
namespace UnityEditor
{
    public enum BuildTarget { Android, StandaloneOSX }
    public enum BuildResult { Unknown, Succeeded, Failed }
    public class GUID { public string value; public override string ToString() { return value; } }
    public static class SessionState { public static string request; public static string GetString(string key, string fallback) { return request ?? fallback; } }
}
namespace UnityEditorInternal
{
    public static class InternalEditorUtility
    {
        public static string GetFullUnityVersion() { return "2021.3.45f2 (88f88f591b2e)"; }
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
        public ulong totalErrors;
    }
    public class BuildReport { public BuildSummary summary; }
}
