using System;
using System.Collections.Generic;
using System.IO;
using UnityEditor;
using UnityEngine;
using UnityEngine.Rendering;

public static partial class ContentFixtureBuilder
{
    [Serializable] sealed class TextureReadbackAsset
    {
        public string name;
        public string type;
        public string subasset;
        public NativeTextureMip texture_mip;
    }
    [Serializable] sealed class TextureReadbackRequest
    {
        public string path;
        public string sha256;
        public NativeContentBundle[] dependencies;
        public TextureReadbackAsset[] assets;
    }
    [Serializable] sealed class TextureReadbackSamples
    {
        public List<NativeTextureMip> samples = new List<NativeTextureMip>();
    }
    [Serializable] public sealed class NativeTextureMip
    {
        public int mip;
        public int face;
        public int width;
        public int height;
        public string graphics;
        public string color_space;
        public string format;
        public string sha256;
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
                var type = NativeContentType(asset.type);
                var value = String.IsNullOrEmpty(asset.subasset) ? primary.LoadAsset(asset.name, type)
                    : Array.Find(primary.LoadAssetWithSubAssets(asset.name, type), item => item.name == asset.subasset);
                if (!(value is Texture texture) || texture.GetType() != type)
                    throw new Exception("Texture readback typed load failed: " + asset.name);
                loaded.Add(texture);
                samples.samples.Add(ObserveTextureMip(texture, asset.texture_mip, directory, receipt.count));
                receipt.assets.Add(new NativeContentAsset {
                    name = asset.name, type = asset.type, subasset = asset.subasset,
                    loaded_name = texture.name, loaded_type = type.FullName
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

    static NativeTextureMip ObserveTextureMip(Texture source, NativeTextureMip selection, string directory, int index)
    {
        var graphics = SystemInfo.graphicsDeviceType;
        if (graphics == GraphicsDeviceType.Null || QualitySettings.masterTextureLimit != 0)
            throw new Exception("Texture mip fixture requires graphics and full resolution textures");
        bool cube = source is Cubemap;
        int mip = selection.mip;
        int face = selection.face;
        if (mip < 0 || mip >= source.mipmapCount || face < 0 || face >= (cube ? 6 : 1))
            throw new Exception("Texture mip or face is outside the loaded texture: " + source.name);
        int width = Math.Max(1, source.width >> mip);
        int height = Math.Max(1, source.height >> mip);
        var shader = AssetDatabase.LoadAssetAtPath<Shader>("Assets/TextureMipFixture.shader");
        if (shader == null || !shader.isSupported)
            throw new Exception("Texture mip sampling shader unavailable");
        var active = RenderTexture.active;
        var filter = source.filterMode;
        var target = RenderTexture.GetTemporary(width, height, 0, RenderTextureFormat.ARGB32, RenderTextureReadWrite.Linear);
        Material material = null;
        Texture2D pixels = null;
        string path = Path.Combine(directory, $"texture-{index}.rgba");
        try
        {
            source.filterMode = FilterMode.Point;
            material = new Material(shader);
            material.SetFloat("_Mip", mip);
            material.SetInt("_Face", face);
            if (cube) material.SetTexture("_Cube", source);
            Graphics.Blit(cube ? null : source, target, material, cube ? 1 : 0);
            RenderTexture.active = target;
            pixels = new Texture2D(width, height, TextureFormat.RGBA32, false, true);
            pixels.ReadPixels(new Rect(0, 0, width, height), 0, 0, false);
            File.WriteAllBytes(path, pixels.GetRawTextureData());
        }
        finally
        {
            source.filterMode = filter;
            RenderTexture.active = active;
            if (pixels != null) UnityEngine.Object.DestroyImmediate(pixels);
            if (material != null) UnityEngine.Object.DestroyImmediate(material);
            RenderTexture.ReleaseTemporary(target);
        }
        return new NativeTextureMip {
            mip = mip, face = face, width = width, height = height, graphics = graphics.ToString(),
            color_space = QualitySettings.activeColorSpace.ToString(), sha256 = FileHash(path),
            format = cube ? ((Cubemap)source).format.ToString() : ((Texture2D)source).format.ToString()
        };
    }
}
