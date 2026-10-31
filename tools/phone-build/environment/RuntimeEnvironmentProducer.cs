using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using System.Security.Cryptography;
using System.Text.RegularExpressions;
using UnityEngine;
using UnityEngine.Rendering;

namespace OwnerConversion
{
    // Compile into an owner-built SDK tool player. This component is not part
    // of the game runtime and never loads original game assemblies or saves.
    public sealed class RuntimeEnvironmentProducer : MonoBehaviour
    {
        [Serializable] public sealed class Request
        {
            public string id, source_recipe_sha256, bundle_path, bundle_sha256, material;
            public int width = 128;
            public Vector3 light_euler = new Vector3(35, 40, 0);
        }
        [Serializable] public sealed class Image
        {
            public string file, sha256;
            public int face, mip, width, bytes;
        }
        [Serializable] public sealed class Result
        {
            public string schema = "owner-runtime-environment-v1";
            public bool success;
            public string error, unity_version, source_recipe_sha256, bundle_sha256, graphics_api;
            public string texture_format = "RGBAHalf";
            public string ambient_semantics = "RenderSettings.ambientProbe (final)";
            public int width, mips;
            public float[] ambient, hdr_decode;
            public Image[] images;
        }

        Request request;
        string output;
        AssetBundle bundle;
        Material material, previousSky;
        Light previousSun;
        GameObject owned;
        ReflectionProbe probe;
        bool previousRealtime, stateSaved, running;
        AmbientMode previousAmbientMode;
        float previousAmbientIntensity;

        public void Begin(Request selected, string destination)
        {
            if (running) throw new InvalidOperationException("Environment producer already running");
            if (selected == null || !Regex.IsMatch(selected.id ?? "", "^[a-f0-9]{32}$") ||
                !Regex.IsMatch(selected.source_recipe_sha256 ?? "", "^[a-f0-9]{64}$") ||
                !Regex.IsMatch(selected.bundle_sha256 ?? "", "^[a-f0-9]{64}$"))
                throw new InvalidDataException("Invalid source environment request identity");
            if (selected.width != 128 || string.IsNullOrEmpty(selected.material))
                throw new InvalidDataException("Current source environment contract requires a 128-pixel SDK sky");
            if (Directory.Exists(destination) || File.Exists(destination))
                throw new IOException("Environment output must be new");
            Directory.CreateDirectory(destination);
            request = selected;
            output = destination;
            running = true;
            StartCoroutine(Run());
        }

        IEnumerator Run()
        {
            var operation = Produce();
            try
            {
                while (true)
                {
                    object next = null;
                    bool advance = false;
                    try
                    {
                        advance = operation.MoveNext();
                        if (advance) next = operation.Current;
                    }
                    catch (Exception error)
                    {
                        Save(new Result { success = false, error = error.ToString() });
                    }
                    if (!advance) break;
                    yield return next;
                }
            }
            finally
            {
                var disposable = operation as IDisposable;
                if (disposable != null) disposable.Dispose();
                Cleanup();
                running = false;
            }
        }

        IEnumerator Produce()
        {
            if (Application.unityVersion != "2021.3.45f2" || QualitySettings.activeColorSpace != ColorSpace.Linear)
                throw new InvalidOperationException("Source environment requires the pinned linear SDK player");
            if (!SystemInfo.SupportsTextureFormat(TextureFormat.RGBAHalf))
                throw new InvalidOperationException("Native half-float texture readback unavailable");
            if (Hash(request.bundle_path) != request.bundle_sha256)
                throw new InvalidDataException("Source SDK material bundle changed");
            bundle = AssetBundle.LoadFromFile(request.bundle_path);
            if (!bundle) throw new InvalidDataException("Source SDK material bundle failed to load");
            var source = bundle.LoadAsset<Material>(request.material);
            if (!source || !source.shader || source.shader.name != "Skybox/Procedural" || !source.shader.isSupported)
                throw new InvalidDataException("Source procedural SDK sky is unavailable");
            material = new Material(source);
            previousSky = RenderSettings.skybox;
            previousSun = RenderSettings.sun;
            previousAmbientMode = RenderSettings.ambientMode;
            previousAmbientIntensity = RenderSettings.ambientIntensity;
            previousRealtime = QualitySettings.realtimeReflectionProbes;
            stateSaved = true;
            owned = new GameObject("Owner source environment capture");
            var light = owned.AddComponent<Light>();
            light.type = LightType.Directional;
            light.transform.rotation = Quaternion.Euler(request.light_euler);
            light.color = Color.white;
            light.intensity = 1;
            RenderSettings.skybox = material;
            RenderSettings.sun = light;
            RenderSettings.ambientMode = AmbientMode.Skybox;
            RenderSettings.ambientIntensity = 1;
            QualitySettings.realtimeReflectionProbes = true;
            var cameraObject = new GameObject("Source environment camera");
            cameraObject.transform.SetParent(owned.transform, false);
            var camera = cameraObject.AddComponent<Camera>();
            camera.clearFlags = CameraClearFlags.SolidColor;
            camera.backgroundColor = new Color(.04f, .06f, .09f);
            camera.cullingMask = 0;
            var probeObject = new GameObject("Source environment reflection");
            probeObject.transform.SetParent(owned.transform, false);
            probe = probeObject.AddComponent<ReflectionProbe>();
            probe.mode = ReflectionProbeMode.Realtime;
            probe.refreshMode = ReflectionProbeRefreshMode.ViaScripting;
            probe.timeSlicingMode = ReflectionProbeTimeSlicingMode.NoTimeSlicing;
            probe.clearFlags = ReflectionProbeClearFlags.Skybox;
            probe.cullingMask = 0;
            probe.hdr = true;
            probe.resolution = request.width;
            // Let the native renderer establish the supplied directional-light
            // globals before either capture. Geometry is excluded from all faces.
            yield return new WaitForEndOfFrame();
            DynamicGI.UpdateEnvironment();
            int capture = probe.RenderProbe();
            if (capture < 0) throw new InvalidOperationException("Native reflection capture refused");
            float started = Time.realtimeSinceStartup;
            while (!probe.IsFinishedRendering(capture))
            {
                if (Time.realtimeSinceStartup - started > 120)
                    throw new TimeoutException("Native source environment capture timed out");
                yield return null;
            }
            yield return new WaitForEndOfFrame();
            var texture = probe.texture as RenderTexture;
            if (!texture || texture.dimension != TextureDimension.Cube || texture.width != request.width)
                throw new InvalidDataException("Native reflection has an unexpected shape");
            var images = new List<Image>();
            var previous = RenderTexture.active;
            try
            {
                for (int face = 0; face < 6; face++)
                {
                    for (int mip = 0; mip < texture.mipmapCount; mip++)
                    {
                        int width = Math.Max(1, texture.width >> mip);
                        var pixels = new Texture2D(width, width, TextureFormat.RGBAHalf, false, true);
                        try
                        {
                            Graphics.SetRenderTarget(texture, mip, (CubemapFace)face);
                            pixels.ReadPixels(new Rect(0, 0, width, width), 0, 0, false);
                            byte[] bytes = pixels.GetRawTextureData();
                            if (bytes.Length != width * width * 8)
                                throw new InvalidDataException("Native half-float face extent differs");
                            string name = "face-" + face + "-mip-" + mip + ".rgba16f";
                            string path = Path.Combine(output, name);
                            using (var file = new FileStream(path, FileMode.CreateNew, FileAccess.Write))
                                file.Write(bytes, 0, bytes.Length);
                            images.Add(new Image { file = name, sha256 = Hash(path), face = face, mip = mip, width = width, bytes = bytes.Length });
                        }
                        finally { Destroy(pixels); }
                    }
                }
            }
            finally { RenderTexture.active = previous; }
            var ambient = new float[27];
            var sh = RenderSettings.ambientProbe;
            for (int color = 0; color < 3; color++)
                for (int coefficient = 0; coefficient < 9; coefficient++)
                    ambient[color * 9 + coefficient] = sh[color, coefficient];
            var decode = probe.textureHDRDecodeValues;
            if (Hash(request.bundle_path) != request.bundle_sha256)
                throw new InvalidDataException("Source SDK material changed during capture");
            Save(new Result { success = true, ambient = ambient, hdr_decode = new[] { decode.x, decode.y, decode.z, decode.w },
                width = texture.width, mips = texture.mipmapCount, images = images.ToArray() });
        }

        void Save(Result result)
        {
            result.unity_version = Application.unityVersion;
            result.graphics_api = SystemInfo.graphicsDeviceType.ToString();
            result.source_recipe_sha256 = request.source_recipe_sha256;
            result.bundle_sha256 = request.bundle_sha256;
            using (var file = new StreamWriter(new FileStream(Path.Combine(output, "result.json"), FileMode.CreateNew, FileAccess.Write)))
                file.Write(JsonUtility.ToJson(result, true));
        }

        static string Hash(string path)
        {
            using (var stream = File.OpenRead(path))
            using (var sha = SHA256.Create())
                return BitConverter.ToString(sha.ComputeHash(stream)).Replace("-", "").ToLowerInvariant();
        }

        void Cleanup()
        {
            if (stateSaved)
            {
                RenderSettings.skybox = previousSky;
                RenderSettings.sun = previousSun;
                RenderSettings.ambientMode = previousAmbientMode;
                RenderSettings.ambientIntensity = previousAmbientIntensity;
                QualitySettings.realtimeReflectionProbes = previousRealtime;
                stateSaved = false;
            }
            if (owned) Destroy(owned);
            if (material) Destroy(material);
            if (bundle) bundle.Unload(true);
            owned = null; material = null; bundle = null; probe = null;
        }
        void OnDestroy() { Cleanup(); }
    }
}
