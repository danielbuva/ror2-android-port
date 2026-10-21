using System;
using System.Reflection;
using RoR2;
using RoR2.PostProcess;
using UnityEngine;

// Source-backed readiness for the optional cloned Main Camera. Run Prepare
// while the clone is still beneath its inactive staging root. It resolves the
// same Addressables keys used by the original camera/post-process components;
// it does not write LegacyShaderAPI or SobelCommandBuffer static state.
public static class AndroidNativeSourceCameraPrerequisites
{
    static readonly string[] ShaderNames =
    {
        "Hopoo Games/Internal/Outline Highlight",
        "Hopoo Games/Internal/SobelBuffer",
        "Hopoo Games/Internal/VisionLimit",
        "TranslucentImage/DownTent",
    };

    static readonly FieldInfo SobelShaderField = typeof(SobelCommandBuffer).GetField(
        "sobelShader", BindingFlags.Static | BindingFlags.NonPublic);
    static ActivationScope activationScope;
    static Type markerType;
    static MethodInfo markerBegin;
    static MethodInfo markerEnd;

    public sealed class PreparedCamera
    {
        internal readonly SceneCamera SceneCamera;
        internal PreparedCamera(SceneCamera sceneCamera) { SceneCamera = sceneCamera; }
    }

    public sealed class ActivationScope : IDisposable
    {
        readonly SceneCamera expectedSceneCamera;
        bool disposed;
        public bool ConsoleConfigurationUnavailable { get; private set; }

        internal ActivationScope(SceneCamera sceneCamera) { expectedSceneCamera = sceneCamera; }

        public void Dispose()
        {
            if (disposed)
                return;
            disposed = true;
            if (ReferenceEquals(activationScope, this))
            {
                try
                {
                    ConsoleConfigurationUnavailable = (bool)ResolveMarkerEnd().Invoke(null, new object[] { expectedSceneCamera });
                }
                finally
                {
                    activationScope = null;
                }
            }
        }
    }

    public static PreparedCamera Prepare(SceneCamera sceneCamera, out string failure)
    {
        failure = null;
        if (!sceneCamera)
        {
            failure = "the original SceneCamera component is absent";
            return null;
        }
        try
        {
            foreach (string shaderName in ShaderNames)
                if (!LegacyShaderAPI.Find(shaderName))
                    throw new InvalidOperationException("Original camera shader resolved to null: " + shaderName);

            // Find populated the original LegacyShaderAPI cache. The source
            // preload method then takes its cached-shader branch and sets the
            // private Sobel static before any clone Awake/OnEnable can run.
            SobelCommandBuffer.PreloadShaderReference();
            if (SobelShaderField == null || SobelShaderField.FieldType != typeof(Shader) ||
                !(SobelShaderField.GetValue(null) is Shader))
                throw new InvalidOperationException("Original Sobel shader is still pending; keep the cloned camera inactive");
            return new PreparedCamera(sceneCamera);
        }
        catch (Exception exception)
        {
            failure = exception.GetType().Name + ": " + exception.Message;
            return null;
        }
    }

    public static ActivationScope BeginOwnedViewActivation(PreparedCamera prepared)
    {
        if (prepared == null || !prepared.SceneCamera)
            throw new InvalidOperationException("Camera activation requires exact prepared SceneCamera evidence");
        if (activationScope != null)
            throw new InvalidOperationException("Another owned camera activation scope is live");
        var scope = new ActivationScope(prepared.SceneCamera);
        ResolveMarkerBegin().Invoke(null, new object[] { prepared.SceneCamera });
        activationScope = scope;
        return scope;
    }

    static MethodInfo ResolveMarkerBegin()
    {
        ResolveMarkerMethods();
        return markerBegin;
    }

    static MethodInfo ResolveMarkerEnd()
    {
        ResolveMarkerMethods();
        return markerEnd;
    }

    static void ResolveMarkerMethods()
    {
        if (markerBegin != null && markerEnd != null)
            return;
        markerType = typeof(CameraRigController).Assembly.GetType("RoR2.AndroidNativeSourceViewOnlyRigMarker", false, false);
        if (markerType == null)
            throw new InvalidOperationException("exact merged camera activation marker is unavailable");
        markerBegin = markerType.GetMethod("BeginOwnedSceneCameraActivation", BindingFlags.Public | BindingFlags.Static, null,
            new[] { typeof(SceneCamera) }, null);
        markerEnd = markerType.GetMethod("EndOwnedSceneCameraActivation", BindingFlags.Public | BindingFlags.Static, null,
            new[] { typeof(SceneCamera) }, null);
        if (markerBegin == null || markerBegin.ReturnType != typeof(void) || markerEnd == null || markerEnd.ReturnType != typeof(bool))
            throw new InvalidOperationException("exact merged camera activation marker contract changed");
    }
}
