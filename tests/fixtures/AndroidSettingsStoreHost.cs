using System;
using System.IO;
using System.Reflection;
using System.Runtime.Serialization;
using System.Runtime.Serialization.Json;
using System.Text;

// Controlled JSON platform peer; the production store owns every real file
// write, validation, atomic replacement, recovery and rejection below.
namespace UnityEngine
{
    public static class JsonUtility
    {
        public static string ToJson(object value, bool pretty)
        {
            using (var stream = new MemoryStream())
            {
                new DataContractJsonSerializer(value.GetType()).WriteObject(stream, value);
                return Encoding.UTF8.GetString(stream.ToArray());
            }
        }
        public static void FromJsonOverwrite(string json, object value)
        {
            try
            {
                using (var stream = new MemoryStream(Encoding.UTF8.GetBytes(json)))
                {
                    var restored = new DataContractJsonSerializer(value.GetType()).ReadObject(stream);
                    foreach (var field in value.GetType().GetFields(BindingFlags.Public | BindingFlags.Instance))
                        field.SetValue(value, field.GetValue(restored));
                }
            }
            catch (SerializationException error) { throw new ArgumentException("invalid JSON", error); }
        }
    }
}
static class AndroidSettingsStoreHost
{
    static void Check(bool value, string message) { if (!value) throw new Exception(message); }
    static bool Same(byte[] a, byte[] b)
    {
        if (a.Length != b.Length) return false;
        for (int i = 0; i < a.Length; i++) if (a[i] != b[i]) return false;
        return true;
    }
    static void Main(string[] args)
    {
        var store = new AndroidOfflineSettings(args[1]);
        string path = Path.Combine(args[1], "preferences.json"), pending = path + ".pending";
        store.values.deadzone = .18f;
        Check(store.TrySave(), "first save");
        var first = File.ReadAllBytes(path);
        switch (args[0])
        {
            case "roundtrip":
                store.values.deadzone = .3f; store.values.lookSensitivity = 1.5f; store.values.invertY = true;
                Check(store.TrySave(), "atomic update");
                var loaded = new AndroidOfflineSettings(args[1]);
                Check(loaded.values.deadzone == .3f && loaded.values.invertY && loaded.values.lookSensitivity == 1.5f, "cold reload");
                Check(Same(first, File.ReadAllBytes(path + ".backup")), "previous validated bytes retained");
                break;
            case "partial-pending":
                File.WriteAllText(pending, "{partial");
                var current = new AndroidOfflineSettings(args[1]);
                Check(current.values.deadzone == .18f && current.recovery == "validated-primary", "partial pending superseded valid primary");
                Check(Same(first, File.ReadAllBytes(path)), "load edited the valid primary");
                current.values.deadzone = .25f;
                Check(current.TrySave() && !File.Exists(pending), "ordinary save cannot replace incomplete pending output");
                break;
            case "backup":
            case "missing-primary":
                store.values.deadzone = .3f; Check(store.TrySave(), "second save");
                if (args[0] == "backup") File.WriteAllText(path, "{broken");
                else { File.Delete(path); File.WriteAllText(pending, "{partial"); }
                var recovered = new AndroidOfflineSettings(args[1]);
                Check(recovered.values.deadzone == .18f && recovered.recovery == "validated-backup", "validated backup not restored");
                Check(Same(first, File.ReadAllBytes(path)), "restored output does not match validated generation");
                if (args[0] == "backup")
                {
                    var rejected = Directory.GetFiles(args[1], "preferences.json.rejected-*");
                    Check(rejected.Length == 1 && File.ReadAllText(rejected[0]) == "{broken", "rejected primary was discarded");
                }
                break;
            case "blocked-write":
                Directory.CreateDirectory(pending);
                store.values.deadzone = .3f;
                Check(!store.TrySave() && !string.IsNullOrEmpty(store.saveError), "blocked write claimed success");
                Check(!store.saveError.Contains(args[1]), "storage error exposed a private path");
                Check(Same(first, File.ReadAllBytes(path)), "failed pending write changed primary");
                Directory.Delete(pending);
                Check(store.TrySave() && store.saveError == null, "repaired storage did not permit retry");
                Check(new AndroidOfflineSettings(args[1]).values.deadzone == .3f, "retry not durable");
                break;
            case "invalid-value":
                store.values.deadzone = float.NaN;
                Check(!store.TrySave() && Same(first, File.ReadAllBytes(path)), "invalid preference damaged primary");
                break;
            default: throw new Exception("unknown case");
        }
        Console.WriteLine(args[0] + ": PASS");
    }
}
