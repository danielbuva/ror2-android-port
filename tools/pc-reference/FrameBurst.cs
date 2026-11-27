using System;
using System.Collections.Generic;
using System.IO;
using UnityEngine;
using UnityEngine.Experimental.Rendering;
using UnityEngine.Rendering;

namespace Ror2Lab.Reference
{
    [Serializable]
    internal sealed class FrameTime
    {
        public string frame;
        public double seconds;
    }

    internal sealed class FrameBurst : IDisposable
    {
        private readonly List<Frame> frames = new List<Frame>();
        private readonly RenderTexture screen;
        private int pending;
        private bool disposed;

        public FrameBurst()
        {
            if (SystemInfo.supportsAsyncGPUReadback)
                screen = new RenderTexture(Screen.width, Screen.height, 0, RenderTextureFormat.ARGB32);
        }

        public bool IsReady => pending == 0;

        // Called at end of frame. Defer PNG compression until the capture window closes.
        public void Capture()
        {
            var frame = new Frame { seconds = Time.realtimeSinceStartupAsDouble };
            frames.Add(frame);
            if (!screen)
            {
                frame.texture = ScreenCapture.CaptureScreenshotAsTexture();
                return;
            }

            ScreenCapture.CaptureScreenshotIntoRenderTexture(screen);
            pending++;
            AsyncGPUReadback.Request(screen, 0, TextureFormat.RGBA32, result =>
            {
                if (!result.hasError && !disposed)
                    frame.pixels = result.GetData<byte>().ToArray();
                pending--;
                if (disposed && IsReady)
                    UnityEngine.Object.Destroy(screen);
            });
        }

        public FrameTime[] Write(string folder)
        {
            var timeline = new FrameTime[frames.Count];
            for (int index = 0; index < frames.Count; index++)
            {
                Frame frame = frames[index];
                if (frame.pixels == null && !frame.texture)
                    throw new InvalidOperationException($"Could not read recorded frame {index}.");
                string name = index == 0 ? "frame.png" : $"frame-{index:D4}.png";
                byte[] png = frame.texture ? frame.texture.EncodeToPNG() :
                    ImageConversion.EncodeArrayToPNG(frame.pixels, GraphicsFormat.R8G8B8A8_UNorm,
                        (uint)screen.width, (uint)screen.height);
                File.WriteAllBytes(Path.Combine(folder, name), png);
                timeline[index] = new FrameTime { frame = name, seconds = frame.seconds };
            }
            return timeline;
        }

        public void Dispose()
        {
            disposed = true;
            foreach (Frame frame in frames)
                if (frame.texture)
                    UnityEngine.Object.Destroy(frame.texture);
            frames.Clear();
            if (screen && IsReady)
                UnityEngine.Object.Destroy(screen);
        }

        private sealed class Frame
        {
            public double seconds;
            public byte[] pixels;
            public Texture2D texture;
        }
    }
}
