using UnityEditor.Build.Reporting;
namespace UnityEditor.Build { public interface IUnityLinkerProcessor { int callbackOrder { get; } string GenerateAdditionalLinkXmlFile(BuildReport report, UnityEditor.UnityLinker.UnityLinkerBuildPipelineData data); } }
namespace UnityEditor.Build.Reporting { public sealed class BuildSummary { public System.Guid guid; } public sealed class BuildReport { public BuildSummary summary = new BuildSummary(); } }
namespace UnityEditor { public static class SessionState { public static string GetString(string key, string fallback) { return fallback; } } }
namespace UnityEditor.UnityLinker { public sealed class UnityLinkerBuildPipelineData { public string inputDirectory; public UnityEngine.BuildTarget target; } }
namespace UnityEngine { public enum BuildTarget { Android } public static class Application { public static string dataPath; } public static class JsonUtility { public static T FromJson<T>(string value) { return default(T); } public static string ToJson(object value, bool prettyPrint) { return "{}"; } } }
