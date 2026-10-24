using System;
using System.IO;
using System.Collections.Generic;
using UnityEditor;
using UnityEngine;

// Authored nongame image-import oracle. No output is a reconstruction input.
public static class TextureMipFixture
{
    [Serializable] public sealed class Level { public int width; public int height; public int mip; public string file; }
    [Serializable] public sealed class ImageReport { public string pattern; public string mode; public string format; public string input; public Level[] levels; }
    [Serializable] public sealed class Report { public string unity; public string source_commit; public ImageReport[] images; }
    static byte[] Bytes(Color32[] pixels)
    {
        var bytes = new byte[pixels.Length * 4];
        for (int i = 0; i < pixels.Length; i++) { bytes[i*4]=pixels[i].r; bytes[i*4+1]=pixels[i].g; bytes[i*4+2]=pixels[i].b; bytes[i*4+3]=pixels[i].a; }
        return bytes;
    }
    public static void Run()
    {
        string output=Environment.GetEnvironmentVariable("ROR2_TEXTURE_MIP_REPORT");
        if (String.IsNullOrEmpty(output)) throw new Exception("Explicit texture oracle output required");
        Check(output);
    }
    public static void Check(string output)
    {
        if (Application.unityVersion != "2021.3.45f2" || Directory.Exists(output)) throw new Exception("Fresh exact-editor mip oracle required");
        Directory.CreateDirectory(output);
        if (!AssetDatabase.IsValidFolder("Assets/TextureMipFixture")) AssetDatabase.CreateFolder("Assets", "TextureMipFixture");
        var images = new List<ImageReport>();
        foreach (string pattern in new [] { "ramp", "noise", "normal" })
        {
            int width = pattern == "ramp" ? 256 : 32, height = pattern == "ramp" ? 4 : 32;
            var pixels = new Color32[width * height]; uint state = 731;
            for (int y=0; y<height; y++) for (int x=0; x<width; x++)
            {
                int r,g,b;
                if (pattern == "ramp") { r=x; g=(x*17)%256; b=(x*73)%256; }
                else if (pattern == "normal") { r=64+(x*13+y*11)%128; g=64+(x*7+y*19)%128; b=(int)((Math.Sqrt(Math.Max(0,255*255-(2*r-255)*(2*r-255)-(2*g-255)*(2*g-255)))+255)/2); }
                else { state=unchecked(state*1664525+1013904223); r=(int)(state>>24); state=unchecked(state*1664525+1013904223); g=(int)(state>>24); state=unchecked(state*1664525+1013904223); b=(int)(state>>24); }
                pixels[y*width+x]=new Color32((byte)r,(byte)g,(byte)b,255);
            }
            File.WriteAllBytes(Path.Combine(output,pattern+".input.rgba"), Bytes(pixels));
            var source = new Texture2D(width,height,TextureFormat.RGBA32,false,true);
            source.SetPixels32(pixels); source.Apply(false,false); byte[] png = source.EncodeToPNG(); UnityEngine.Object.DestroyImmediate(source);
            foreach (string mode in new [] { "linear", "srgb", "normal" })
            {
                string name=pattern+"-"+mode, asset="Assets/TextureMipFixture/"+name+".png";
                if (File.Exists(asset) && !System.Linq.Enumerable.SequenceEqual(File.ReadAllBytes(asset),png)) throw new Exception("Owned authored PNG drift");
                File.WriteAllBytes(asset,png); AssetDatabase.ImportAsset(asset,ImportAssetOptions.ForceSynchronousImport);
                var importer=(TextureImporter)AssetImporter.GetAtPath(asset);
                importer.textureType=mode=="normal"?TextureImporterType.NormalMap:TextureImporterType.Default;
                importer.convertToNormalmap=false; importer.sRGBTexture=mode=="srgb"; importer.alphaIsTransparency=false;
                importer.mipmapEnabled=true; importer.mipmapFilter=TextureImporterMipFilter.BoxFilter; importer.mipMapsPreserveCoverage=false;
                importer.isReadable=true; importer.npotScale=TextureImporterNPOTScale.None; importer.textureCompression=TextureImporterCompression.Uncompressed;
                importer.SetPlatformTextureSettings(new TextureImporterPlatformSettings { name="Android",overridden=true,format=TextureImporterFormat.RGBA32,maxTextureSize=2048 });
                importer.SaveAndReimport(); var texture=AssetDatabase.LoadAssetAtPath<Texture2D>(asset);
                if (!texture || texture.width!=width || texture.height!=height) throw new Exception("Authored image import extent differs");
                var levels=new List<Level>();
                for(int mip=0;mip<texture.mipmapCount;mip++)
                {
                    string file=name+".mip"+mip+".rgba"; File.WriteAllBytes(Path.Combine(output,file),Bytes(texture.GetPixels32(mip)));
                    levels.Add(new Level {width=Math.Max(1,width>>mip),height=Math.Max(1,height>>mip),mip=mip,file=file});
                }
                images.Add(new ImageReport {pattern=pattern,mode=mode,format=texture.format.ToString(),input=pattern+".input.rgba",levels=levels.ToArray()});
            }
        }
        var report=new Report {unity=Application.unityVersion,source_commit=Environment.GetEnvironmentVariable("ROR2_PHONE_BUILD_SOURCE"),images=images.ToArray()};
        File.WriteAllText(Path.Combine(output,"result.json"),JsonUtility.ToJson(report,true));
    }
}
