using System;
using System.IO;
using UnityEditor;
using UnityEngine;
using UnityEngine.Rendering;

public static partial class ContentFixtureBuilder
{
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

    static NativeTextureMip ObserveTextureMip(Texture source, NativeTextureMip selection, string oracle, int index)
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
        string path = Path.Combine(Path.GetDirectoryName(oracle), $"texture-{index}.rgba");
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
