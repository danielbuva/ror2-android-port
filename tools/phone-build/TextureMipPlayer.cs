using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using UnityEngine;
using UnityEngine.Networking;
using UnityEngine.Rendering;

public sealed class TextureMipPlayer : MonoBehaviour
{
    public Shader samplingShader;
    public string bundleSha256;
    public TextureMipSampling.Asset[] assets;

    [Serializable] sealed class Report
    {
        public string graphics;
        public string bundleSha256;
        public bool unloaded;
        public bool passed;
        public string failure;
        public List<TextureMipSampling.Sample> samples = new List<TextureMipSampling.Sample>();
    }

    [Serializable] sealed class Marker
    {
        public string graphics;
        public bool passed;
        public string sha256;
        public string failure;
    }

    IEnumerator Start()
    {
        var directory = Application.persistentDataPath;
        var path = Path.Combine(directory, "texture-readback.bundle");
        using (var request = new UnityWebRequest(Application.streamingAssetsPath + "/texture-readback.bundle",
                   UnityWebRequest.kHttpVerbGET, new DownloadHandlerFile(path) { removeFileOnAbort = true }, null))
        {
            yield return request.SendWebRequest();
            yield return new WaitForEndOfFrame();
            var report = new Report { graphics = SystemInfo.graphicsDeviceType.ToString() };
            AssetBundle bundle = null;
            var loaded = new List<Texture>();
            try
            {
                if (request.result != UnityWebRequest.Result.Success)
                    throw new Exception(request.error);
                if (SystemInfo.graphicsDeviceType != GraphicsDeviceType.Vulkan)
                    throw new Exception("Texture player requires Vulkan");
                report.bundleSha256 = TextureMipSampling.Hash(path);
                if (report.bundleSha256 != bundleSha256)
                    throw new Exception("Texture player bundle hash mismatch");
                bundle = AssetBundle.LoadFromFile(path);
                if (bundle == null) throw new Exception("Texture player bundle failed to load");
                foreach (var asset in assets)
                {
                    var texture = TextureMipSampling.Load(bundle, asset);
                    loaded.Add(texture);
                    report.samples.Add(TextureMipSampling.Read(texture, asset.texture_mip, samplingShader, directory, report.samples.Count));
                }
            }
            catch (Exception error) { report.failure = error.ToString(); }
            finally
            {
                if (bundle != null)
                {
                    bundle.Unload(true);
                    report.unloaded = bundle == null && loaded.TrueForAll(texture => texture == null);
                }
                File.Delete(path);
                report.passed = report.failure == null && report.unloaded && report.samples.Count == assets.Length;
                var receipt = Path.Combine(directory, "texture-readback.json");
                File.WriteAllText(receipt, JsonUtility.ToJson(report));
                Debug.Log("PHONE_TEXTURE_READBACK " + JsonUtility.ToJson(new Marker {
                    graphics = report.graphics, passed = report.passed, sha256 = TextureMipSampling.Hash(receipt),
                    failure = report.failure?.Split('\n')[0]
                }));
            }
        }
    }
}
