using System;
using System.IO;
using System.Reflection;
using System.Runtime.Serialization;
using UnityEngine;

// Authored reflection test: runs only the locally configured virtual method cases.
// Uninitialized instances deliberately avoid platform-device constructors. This is
// AOT/dispatch evidence, not middleware initialization or controller acceptance.
public static class MetadataDispatchProbe {
    [Serializable] public class Case { public string assembly, type, baseType, method, field; public int fieldValue, expected; }
    [Serializable] public class Config { public string attempt; public Case[] cases; }
    [Serializable] public class Observation { public string type, method; public int actual, expected; public bool success; }
    [Serializable] public class Result { public string attempt, utc, error; public int pid; public bool success; public Observation[] observations; }
    [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
    public static void Run() {
        var configAsset = Resources.Load<TextAsset>("MetadataDispatchProbe");
        if (!configAsset) return;
        var config = JsonUtility.FromJson<Config>(configAsset.text);
        var result = new Result { attempt = config.attempt, utc = DateTime.UtcNow.ToString("o"), observations = new Observation[config.cases.Length] };
#if UNITY_ANDROID && !UNITY_EDITOR
        using (var process = new AndroidJavaClass("android.os.Process")) result.pid = process.CallStatic<int>("myPid");
#endif
        try {
            for (int i=0; i<config.cases.Length; i++) {
                var c = config.cases[i];var a = Assembly.Load(c.assembly);
                var type = a.GetType(c.type, true);var parent = a.GetType(c.baseType, true);
                var obj = FormatterServices.GetUninitializedObject(type);
                GC.SuppressFinalize(obj);
                if (!string.IsNullOrEmpty(c.field)) parent.GetField(c.field, BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance).SetValue(obj, (uint)c.fieldValue);
                var method = parent.GetMethod(c.method, BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance);
                if (method == null) throw new MissingMethodException(c.baseType, c.method);
                int actual = Convert.ToInt32(method.Invoke(obj, null));
                result.observations[i] = new Observation { type=c.type,method=c.method,actual=actual,expected=c.expected,success=actual==c.expected };
                if (actual != c.expected) throw new Exception("Virtual dispatch result mismatch: "+c.type);
            }
            result.success = true;
        } catch (Exception e) { result.error=e.ToString();Debug.LogException(e); }
        string json=JsonUtility.ToJson(result,true);
        File.WriteAllText(Path.Combine(Application.persistentDataPath,"metadata-dispatch.json"),json);
        Debug.Log("LAB_METADATA_DISPATCH "+result.success+" "+result.attempt);
    }
}
