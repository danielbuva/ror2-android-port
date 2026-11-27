using System;
using System.IO;
using System.Linq;
using RoR2;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.SceneManagement;
using Path = System.IO.Path;

namespace Ror2Lab.Reference
{
    internal static class CaptureEvidence
    {
        public static void WriteState(string folder, Camera camera, CharacterBody player, CharacterBody subject,
            CaptureStep step, CaptureScenario scenario)
        {
            Plane[] frustum = GeometryUtility.CalculateFrustumPlanes(camera);
            var visible = UnityEngine.Object.FindObjectsOfType<Renderer>()
                .Where(renderer => renderer.enabled && GeometryUtility.TestPlanesAABB(frustum, renderer.bounds))
                .OrderBy(renderer => (renderer.bounds.center - camera.transform.position).sqrMagnitude)
                .ToArray();
            WriteJson(Path.Combine(folder, "state.json"), new FrameState
            {
                id = step.id,
                scene = SceneManager.GetActiveScene().name,
                seed = scenario.seed,
                action = step.action,
                frame = Time.frameCount,
                seconds = Time.realtimeSinceStartup,
                width = Screen.width,
                height = Screen.height,
                target_fps = Application.targetFrameRate,
                vsync = QualitySettings.vSyncCount,
                shadows = QualitySettings.shadows.ToString(),
                camera_position = camera.transform.position,
                camera_rotation = camera.transform.rotation,
                field_of_view = camera.fieldOfView,
                player_position = player.footPosition,
                player_primary = player.skillLocator.primary.skillNameToken,
                subject = subject.name,
                subject_position = subject.footPosition,
                states = subject.GetComponents<EntityStateMachine>().Select(state => new Machine
                {
                    name = state.customName,
                    type = state.state?.GetType().FullName
                }).ToArray(),
                frustum_renderers = visible.Length,
                renderers = visible.Take(160).Select(ObserveRenderer).ToArray()
            });
        }

        private static RendererState ObserveRenderer(Renderer renderer)
        {
            var particles = renderer as ParticleSystemRenderer;
            return new RendererState
            {
                name = renderer.name,
                parent = renderer.transform.parent ? renderer.transform.parent.name : "",
                type = renderer.GetType().Name,
                position = renderer.transform.position,
                mesh = particles && particles.mesh ? particles.mesh.name :
                    renderer is SkinnedMeshRenderer skinned && skinned.sharedMesh ? skinned.sharedMesh.name :
                    renderer.TryGetComponent(out MeshFilter filter) && filter.sharedMesh ? filter.sharedMesh.name : "",
                slots = renderer.sharedMaterials.Select((material, slot) => ObserveMaterial(material, renderer, slot)).ToArray(),
                trail = particles && particles.trailMaterial ? ObserveMaterial(particles.trailMaterial, renderer, -1) : null
            };
        }

        private static MaterialState ObserveMaterial(Material material, Renderer renderer, int slot)
        {
            if (!material || !material.shader)
                return new MaterialState { slot = slot, name = material ? material.name : "" };
            var block = new MaterialPropertyBlock();
            if (slot >= 0)
                renderer.GetPropertyBlock(block, slot);
            if (block.isEmpty)
                renderer.GetPropertyBlock(block);
            Shader shader = material.shader;
            var properties = new Property[shader.GetPropertyCount()];
            for (int index = 0; index < properties.Length; index++)
            {
                int id = shader.GetPropertyNameId(index);
                ShaderPropertyType type = shader.GetPropertyType(index);
                var property = new Property { name = shader.GetPropertyName(index), type = type.ToString() };
                switch (type)
                {
                    case ShaderPropertyType.Color:
                    case ShaderPropertyType.Vector:
                        property.value = block.HasVector(id) ? block.GetVector(id) : material.GetVector(id);
                        break;
                    case ShaderPropertyType.Float:
                    case ShaderPropertyType.Range:
                        property.value.x = block.HasFloat(id) ? block.GetFloat(id) : material.GetFloat(id);
                        break;
                    case ShaderPropertyType.Texture:
                        Texture texture = block.HasTexture(id) ? block.GetTexture(id) : material.GetTexture(id);
                        property.texture = texture ? texture.name : "";
                        break;
                }
                properties[index] = property;
            }
            return new MaterialState
            {
                slot = slot,
                name = material.name,
                shader = shader.name,
                shader_supported = shader.isSupported,
                render_queue = material.renderQueue,
                keywords = material.shaderKeywords,
                properties = properties
            };
        }

        public static void WriteJson<T>(string path, T data)
        {
            string temporary = path + ".tmp";
            File.WriteAllText(temporary, JsonUtility.ToJson(data, true) + Environment.NewLine);
            File.Move(temporary, path);
        }

        [Serializable]
        private sealed class FrameState
        {
            public string id, scene, seed, action, shadows, subject, player_primary;
            public int frame, width, height, target_fps, vsync, frustum_renderers;
            public float seconds, field_of_view;
            public Vector3 camera_position, player_position, subject_position;
            public Quaternion camera_rotation;
            public Machine[] states;
            public RendererState[] renderers;
        }

        [Serializable]
        private sealed class Machine
        {
            public string name, type;
        }

        [Serializable]
        private sealed class RendererState
        {
            public string name, parent, type, mesh;
            public Vector3 position;
            public MaterialState[] slots;
            public MaterialState trail;
        }

        [Serializable]
        private sealed class MaterialState
        {
            public int slot, render_queue;
            public string name, shader;
            public bool shader_supported;
            public string[] keywords;
            public Property[] properties;
        }

        [Serializable]
        private sealed class Property
        {
            public string name, type, texture;
            public Vector4 value;
        }
    }
}
