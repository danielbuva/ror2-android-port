using System;
using System.Collections;
using System.IO;
using System.Security.Cryptography;
using UnityEngine;
using UnityEngine.Networking;

// Isolated authored probe. No game, catalog or existing runtime owner is read.
public sealed class ContentFixture : MonoBehaviour
{
    [Serializable] public sealed class Report
    {
        public string unity;
        public string graphics;
        public bool bundleLoaded;
        public bool textMatched;
        public bool unloaded;
        public string source;
        public string bundleSha256;
        public int successfulCycles;
        public string failure;
    }

    [Serializable] sealed class Selection { public string sha256; }
    [Serializable] sealed class Paths
    {
        public string persistentDataPath;
        public string filesDir;
        public string externalFilesDir;
    }

    static string Sha256(byte[] data)
    {
        using (var hash = SHA256.Create()) return BitConverter.ToString(hash.ComputeHash(data)).Replace("-", "").ToLowerInvariant();
    }

    public static Report Check(string path)
    {
        var report = new Report { unity = Application.unityVersion, graphics = SystemInfo.graphicsDeviceType.ToString() };
        AssetBundle bundle = null;
        TextAsset text = null;
        try
        {
            bundle = AssetBundle.LoadFromFile(path);
            report.bundleLoaded = bundle != null;
            if (!report.bundleLoaded) throw new Exception("AssetBundle.LoadFromFile returned null");
            text = bundle.LoadAsset<TextAsset>("assets/phone-fixture.txt");
            report.textMatched = text != null && text.text == "phone-owned-content-fixture-v1\n";
            if (!report.textMatched) throw new Exception("TextAsset deserialization/payload mismatch");
        }
        catch (Exception error) { report.failure = error.GetType().Name + ": " + error.Message; }
        finally
        {
            if (bundle != null) { bundle.Unload(true); report.unloaded = text == null; }
        }
        return report;
    }

    IEnumerator Start()
    {
        using (var player = new AndroidJavaClass("com.unity3d.player.UnityPlayer"))
        using (var activity = player.GetStatic<AndroidJavaObject>("currentActivity"))
        using (var files = activity.Call<AndroidJavaObject>("getFilesDir"))
        using (var external = activity.Call<AndroidJavaObject>("getExternalFilesDir", new object[] { null }))
        {
            var paths = new Paths {
                persistentDataPath = Application.persistentDataPath,
                filesDir = files.Call<string>("getCanonicalPath"),
                externalFilesDir = external.Call<string>("getCanonicalPath")
            };
            File.WriteAllText(Path.Combine(paths.filesDir, "phone-content-paths.json"), JsonUtility.ToJson(paths));
        }
        var path = Path.Combine(Application.persistentDataPath, "phone-fixture.bundle");
        var report = new Report { unity = Application.unityVersion };
        var selector = Path.Combine(Application.persistentDataPath, "phone-fixture-selection.json");
        string source = "embedded";
        string digest = "";
        bool ready = false;
        if (File.Exists(selector))
        {
            try
            {
                var selection = JsonUtility.FromJson<Selection>(File.ReadAllText(selector));
                path = Path.Combine(Application.persistentDataPath, "phone-candidate.bundle");
                digest = Sha256(File.ReadAllBytes(path));
                if (selection == null || selection.sha256 == null || selection.sha256.Length != 64 || digest != selection.sha256)
                    throw new Exception("Candidate hash mismatch");
                source = "external-candidate";
                ready = true;
            }
            catch (Exception error) { report.failure = "candidate: " + error.Message; }
        }
        else using (var request = UnityWebRequest.Get(Application.streamingAssetsPath + "/phone-fixture.bundle"))
        {
            yield return request.SendWebRequest();
            if (request.result != UnityWebRequest.Result.Success) report.failure = "fixture copy: " + request.error;
            else { File.WriteAllBytes(path, request.downloadHandler.data); digest = Sha256(request.downloadHandler.data); ready = true; }
        }
        if (ready)
        {
            int cycles = 0;
            for (int i = 0; i < 2; ++i)
            {
                report = Check(path);
                if (!report.bundleLoaded || !report.textMatched || !report.unloaded || !String.IsNullOrEmpty(report.failure)) break;
                ++cycles;
                yield return null;
            }
            report.successfulCycles = cycles;
        }
        report.source = source;
        report.bundleSha256 = digest;
        File.WriteAllText(Path.Combine(Application.persistentDataPath, "phone-content-report.json"), JsonUtility.ToJson(report, true));
        Debug.Log("PHONE_CONTENT_FIXTURE " + JsonUtility.ToJson(report));
    }
}
