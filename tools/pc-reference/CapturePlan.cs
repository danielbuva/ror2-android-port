using System;
using UnityEngine;

namespace Ror2Lab.Reference
{
    [Serializable]
    internal sealed class CaptureRequest
    {
        public CaptureSettings settings;
        public CaptureScenario scenario;
    }

    [Serializable]
    internal sealed class CaptureSettings
    {
        public int width = 1280;
        public int height = 960;
        public int fps = 60;
        public float fov = 60;
        public bool disablePostProcessing = true;
    }

    [Serializable]
    internal sealed class CaptureScenario
    {
        public string id;
        public string scene;
        public string seed;
        public string body;
        public bool naturalFirstStage;
        public bool captureAudio;
        public CaptureStep[] steps;
    }

    [Serializable]
    internal sealed class CaptureStep
    {
        public string id;
        public string action;
        public string subject;
        public string value;
        public string machine;
        public string aimAt;
        public bool freezeAi;
        public bool relativeToPlayer;
        public float settleSeconds;
        public float recordSeconds;
        public float[] player;
        public float[] position;
        public float[] aim;
        public CaptureView view;

        public static Vector3 Vector(float[] xyz)
        {
            if (xyz == null || xyz.Length != 3 ||
                Array.Exists(xyz, value => float.IsNaN(value) || float.IsInfinity(value)))
                throw new ArgumentException("Expected three finite world coordinates.");
            return new Vector3(xyz[0], xyz[1], xyz[2]);
        }
    }

    [Serializable]
    internal sealed class CaptureView
    {
        public float[] position;
        public bool relativeToPlayer;
        public float yaw;
        public float pitch;
    }
}
