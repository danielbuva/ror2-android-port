using System;
using System.IO;
using UnityEditor;
using UnityEngine;
using UnityEngine.Rendering;

// Host supplier compiler. The existing source-camera recipe owns every input.
public static class SourceCameraProgramBundle
{
    [Serializable] public class Kernel { public string name; public uint x; public uint y; public uint z; }
    [Serializable] public class ProgramRow { public string target; public Kernel[] kernels; }
    [Serializable] public class Request { public ProgramRow[] programs; }
    [Serializable] public class Receipt { public string unity; public int count; public string[] assets; }
    public static void Build()
    {
        if (Application.unityVersion != "2021.3.45f2" || EditorUserBuildSettings.activeBuildTarget != BuildTarget.Android)
            throw new Exception("Pinned Android editor required");
        string project = Path.GetDirectoryName(Application.dataPath);
        var request = JsonUtility.FromJson<Request>(File.ReadAllText(Path.Combine(project, "programs.json")));
        PlayerSettings.SetUseDefaultGraphicsAPIs(BuildTarget.Android, false);
        PlayerSettings.SetGraphicsAPIs(BuildTarget.Android, new[] { GraphicsDeviceType.Vulkan });
        var paths = new string[request.programs.Length];
        for (int i = 0; i < paths.Length; i++)
        {
            var row = request.programs[i]; paths[i] = row.target;
            if (row.target.EndsWith(".compute", StringComparison.Ordinal))
            {
                var shader = AssetDatabase.LoadAssetAtPath<ComputeShader>(row.target);
                if (!shader) throw new Exception("Compute import missing: " + row.target);
                foreach (var message in ShaderUtil.GetComputeShaderMessages(shader))
                    if (message.severity.ToString() == "Error") throw new Exception(message.message);
                foreach (var kernel in row.kernels)
                {
                    if (!shader.HasKernel(kernel.name)) throw new Exception("Compute kernel missing: " + kernel.name);
                    shader.GetKernelThreadGroupSizes(shader.FindKernel(kernel.name), out uint x, out uint y, out uint z);
                    if (x != kernel.x || y != kernel.y || z != kernel.z)
                        throw new Exception("Compute thread group differs: " + kernel.name);
                }
            }
            else
            {
                var shader = AssetDatabase.LoadAssetAtPath<Shader>(row.target);
                if (!shader || ShaderUtil.ShaderHasError(shader)) throw new Exception("Graphics import failed: " + row.target);
            }
        }
        string output = Path.GetFullPath(Path.Combine(project, "../bundles"));
        Directory.CreateDirectory(output);
        var builds = new[] { new AssetBundleBuild { assetBundleName = "source-camera-programs", assetNames = paths } };
        if (!BuildPipeline.BuildAssetBundles(output, builds, BuildAssetBundleOptions.StrictMode | BuildAssetBundleOptions.ChunkBasedCompression, BuildTarget.Android))
            throw new Exception("Source camera Android bundle build failed");
        File.WriteAllText(Path.GetFullPath(Path.Combine(project, "../compiled.json")), JsonUtility.ToJson(new Receipt {
            unity = Application.unityVersion, count = paths.Length, assets = paths
        }, true));
    }
}
