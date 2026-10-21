using UnityEngine;

// Compile-only exact Unity 2021.3 API contract; no Unity object is instantiated or executed.
static class Unity2021CameraApiCompile
{
    static int Capture(Camera camera, Camera[] cameras, Renderer renderer)
    {
        int observed = Camera.allCamerasCount;
        int copied = Camera.GetAllCameras(cameras);
        Rect rect = camera.rect;
        Vector3 screen = camera.WorldToScreenPoint(renderer.bounds.min);
        Vector3 position = camera.transform.position;
        Quaternion rotation = camera.transform.rotation;
        Material material = renderer.sharedMaterial;
        string materialName = material ? material.name : string.Empty;
        string shaderName = material && material.shader ? material.shader.name : string.Empty;
        return observed + copied + camera.targetDisplay + (int)camera.clearFlags + camera.cullingMask +
               (camera.targetTexture ? 1 : 0) + (int)(rect.width + screen.z + camera.nearClipPlane + camera.farClipPlane +
               camera.fieldOfView + camera.depth + position.x + rotation.w) + materialName.Length + shaderName.Length;
    }
}
