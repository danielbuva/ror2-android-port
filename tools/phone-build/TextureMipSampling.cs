using System;
using System.IO;
using System.Security.Cryptography;
using UnityEngine;
using UnityEngine.Rendering;

public static class TextureMipSampling
{
    [Serializable] public sealed class Asset
    {
        public string name;
        public string type;
        public string subasset;
        public Sample texture_mip;
    }

    [Serializable] public sealed class Sample
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

    public static Texture Load(AssetBundle bundle, Asset asset)
    {
        var type = asset.type == "Cubemap" ? typeof(Cubemap) : typeof(Texture2D);
        var value = String.IsNullOrEmpty(asset.subasset) ? bundle.LoadAsset(asset.name, type)
            : Array.Find(bundle.LoadAssetWithSubAssets(asset.name, type), item => item.name == asset.subasset);
        if (!(value is Texture texture) || texture.GetType() != type)
            throw new Exception("Texture readback typed load failed: " + asset.name);
        return texture;
    }

    public static string Hash(string path)
    {
        using (var stream = File.OpenRead(path))
        using (var hash = SHA256.Create())
            return BitConverter.ToString(hash.ComputeHash(stream)).Replace("-", "").ToLowerInvariant();
    }

    static void Destroy(UnityEngine.Object value)
    {
        if (Application.isPlaying) UnityEngine.Object.Destroy(value);
        else UnityEngine.Object.DestroyImmediate(value);
    }

    public static Sample Read(Texture source, Sample selection, Shader shader, string directory, int index)
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
            if (pixels != null) Destroy(pixels);
            if (material != null) Destroy(material);
            RenderTexture.ReleaseTemporary(target);
        }
        return new Sample {
            mip = mip, face = face, width = width, height = height, graphics = graphics.ToString(),
            color_space = QualitySettings.activeColorSpace.ToString(), sha256 = Hash(path),
            format = cube ? ((Cubemap)source).format.ToString() : ((Texture2D)source).format.ToString()
        };
    }
}
