using System;
using System.Collections.Generic;
using System.IO;
using UnityEditor;
using UnityEngine;

public static partial class ContentFixtureBuilder
{
    [Serializable] sealed class TextureReadbackRequest
    {
        public string path;
        public string sha256;
        public NativeContentBundle[] dependencies;
        public TextureMipSampling.Asset[] assets;
    }
    [Serializable] sealed class TextureReadbackSamples
    {
        public List<TextureMipSampling.Sample> samples = new List<TextureMipSampling.Sample>();
    }

    public static void CheckTextureReadback()
    {
        if (Application.unityVersion != "2021.3.45f2") throw new Exception("Exact editor required");
        var requestPath = Environment.GetEnvironmentVariable("ROR2_PHONE_TEXTURE_READBACK");
        if (String.IsNullOrEmpty(requestPath) || !Path.IsPathRooted(requestPath))
            throw new Exception("Absolute texture readback request required");
        var directory = Path.GetDirectoryName(requestPath);
        var reportPath = Path.Combine(directory, "native-content-check.json");
        var receipt = new NativeContentReceipt {
            unity = Application.unityVersion,
            source_commit = Environment.GetEnvironmentVariable("ROR2_PHONE_BUILD_SOURCE"),
            request_sha256 = FileHash(requestPath)
        };
        var bundles = new List<AssetBundle>();
        var loaded = new List<Texture>();
        var samples = new TextureReadbackSamples();
        try
        {
            var request = JsonUtility.FromJson<TextureReadbackRequest>(File.ReadAllText(requestPath));
            receipt.path = request.path;
            receipt.sha256 = request.sha256;
            AssetBundle LoadPinned(string path, string hash)
            {
                if (!Path.IsPathRooted(path) || FileHash(path) != hash)
                    throw new Exception("Texture readback bundle path or hash differs");
                var bundle = AssetBundle.LoadFromFile(path);
                if (bundle == null) throw new Exception("Texture readback bundle failed to load");
                bundles.Add(bundle);
                return bundle;
            }

            foreach (var pin in request.dependencies ?? Array.Empty<NativeContentBundle>())
            {
                LoadPinned(pin.path, pin.sha256);
                receipt.dependencies.Add(pin);
            }
            var primary = LoadPinned(receipt.path, receipt.sha256);
            foreach (var asset in request.assets)
            {
                var texture = TextureMipSampling.Load(primary, asset);
                loaded.Add(texture);
                var shader = AssetDatabase.LoadAssetAtPath<Shader>("Assets/TextureMipFixture.shader");
                samples.samples.Add(TextureMipSampling.Read(texture, asset.texture_mip, shader, directory, receipt.count));
                receipt.assets.Add(new NativeContentAsset {
                    name = asset.name, type = asset.type, subasset = asset.subasset,
                    loaded_name = texture.name, loaded_type = texture.GetType().FullName
                });
                receipt.count = loaded.Count;
            }
            File.WriteAllText(Path.Combine(directory, "texture-readback.json"), JsonUtility.ToJson(samples, true));
        }
        catch (Exception error) { receipt.failure = error.ToString(); throw; }
        finally
        {
            try
            {
                for (int index = bundles.Count - 1; index >= 0; index--) bundles[index].Unload(true);
                receipt.unloaded = bundles.Count != 0 && bundles.TrueForAll(bundle => bundle == null)
                    && loaded.TrueForAll(texture => texture == null);
            }
            finally { File.WriteAllText(reportPath, JsonUtility.ToJson(receipt, true)); }
        }
    }

}
