using System;
using System.IO;
using UnityEditor;
using UnityEditor.Build;
using UnityEditor.Build.Reporting;
using UnityEngine;
using UnityEngine.SceneManagement;

public static partial class ContentFixtureBuilder
{
    public static void BuildTexturePlayer()
    {
        var path = Environment.GetEnvironmentVariable("ROR2_PHONE_TEXTURE_READBACK");
        var directory = Path.GetDirectoryName(path);
        var shader = AssetDatabase.LoadAssetAtPath<Shader>("Assets/TextureMipFixture.shader");
        var texture = new Texture2D(4, 4, TextureFormat.RGBA32, true, true);
        var cube = new Cubemap(4, TextureFormat.RGBA32, true);
        try
        {
            var green = new Color32(0, 255, 0, 255);
            var blue = new Color32(0, 0, 255, 255);
            texture.SetPixels32(Array.ConvertAll(new Color32[4], _ => green), 1);
            texture.Apply(false);
            for (int face = 0; face < 6; face++)
                cube.SetPixels(Array.ConvertAll(new Color[4], _ => face == 2 ? (Color)blue : Color.red), (CubemapFace)face, 1);
            cube.Apply(false);
            TextureMipSampling.Read(texture, new TextureMipSampling.Sample { mip = 1 }, shader, directory, 0);
            TextureMipSampling.Read(cube, new TextureMipSampling.Sample { mip = 1, face = 2 }, shader, directory, 1);
            for (int index = 0; index < 2; index++)
            {
                var bytes = File.ReadAllBytes(Path.Combine(directory, $"texture-{index}.rgba"));
                var color = index == 0 ? green : blue;
                for (int pixel = 0; pixel < 4; pixel++)
                {
                    int offset = 4 * pixel;
                    if (bytes.Length != 16 || bytes[offset] != color.r || bytes[offset + 1] != color.g ||
                        bytes[offset + 2] != color.b || bytes[offset + 3] != color.a)
                        throw new Exception("Authored texture mip sampling failed");
                }
            }
        }
        finally
        {
            UnityEngine.Object.DestroyImmediate(cube);
            UnityEngine.Object.DestroyImmediate(texture);
        }
        Build();
    }

    public sealed class ConfigureTexturePlayer : IProcessSceneWithReport
    {
        public int callbackOrder => 0;

        public void OnProcessScene(Scene scene, BuildReport report)
        {
            var path = Environment.GetEnvironmentVariable("ROR2_PHONE_TEXTURE_READBACK");
            if (report == null || String.IsNullOrEmpty(path)) return;
            var request = JsonUtility.FromJson<TextureReadbackRequest>(File.ReadAllText(path));
            foreach (var root in scene.GetRootGameObjects())
            {
                var fixture = root.GetComponent<ContentFixture>();
                if (fixture == null) continue;
                UnityEngine.Object.DestroyImmediate(fixture);
                var player = root.AddComponent<TextureMipPlayer>();
                player.samplingShader = AssetDatabase.LoadAssetAtPath<Shader>("Assets/TextureMipFixture.shader");
                player.bundleSha256 = request.sha256;
                player.assets = request.assets;
                return;
            }
            throw new BuildFailedException("Texture player could not find the content fixture scene object");
        }
    }
}
