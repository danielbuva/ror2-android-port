using System;
using System.Collections;
using System.IO;
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
        public string failure;
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
        var path = Path.Combine(Application.persistentDataPath, "phone-fixture.bundle");
        var report = new Report { unity = Application.unityVersion };
        using (var request = UnityWebRequest.Get(Application.streamingAssetsPath + "/phone-fixture.bundle"))
        {
            yield return request.SendWebRequest();
            if (request.result != UnityWebRequest.Result.Success) report.failure = "fixture copy: " + request.error;
            else { File.WriteAllBytes(path, request.downloadHandler.data); report = Check(path); }
        }
        File.WriteAllText(Path.Combine(Application.persistentDataPath, "phone-content-report.json"), JsonUtility.ToJson(report, true));
        Debug.Log("PHONE_CONTENT_FIXTURE " + JsonUtility.ToJson(report));
    }
}
