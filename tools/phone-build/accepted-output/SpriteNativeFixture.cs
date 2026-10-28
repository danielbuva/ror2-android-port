// Current SDK-only diagnostic. Inputs and generated geometry remain private.
using System;
using System.Collections.Generic;
using System.IO;
using System.Security.Cryptography;
using UnityEngine;

public static class SpriteNativeFixture
{
    [Serializable] public sealed class Item
    {
        public string id, png, sha256;
        public float[] rect, pivot, border;
        public float pixels_per_unit;
        public uint extrude;
        public int mesh_type;
    }
    [Serializable] public sealed class Request { public Item[] items; }
    [Serializable] public sealed class Shape { public int[] xy_bits; }
    [Serializable] public sealed class Result
    {
        public string id;
        public int width, height;
        public int[] vertex_xy_bits, triangles;
        public Shape[] physics;
    }
    [Serializable] public sealed class Results
    {
        public bool success;
        public string unity_version;
        public Result[] items;
    }

    static int Bits(float value) { return BitConverter.ToInt32(BitConverter.GetBytes(value), 0); }
    static int[] Points(IList<Vector2> points)
    {
        var output = new int[points.Count * 2];
        for (int i = 0; i < points.Count; ++i)
        {
            output[i * 2] = Bits(points[i].x);
            output[i * 2 + 1] = Bits(points[i].y);
        }
        return output;
    }

    public static void Run(string requestPath, string outputPath)
    {
        if (Application.unityVersion != "2021.3.45f2") throw new InvalidOperationException("Exact SDK version required");
        var request = JsonUtility.FromJson<Request>(File.ReadAllText(requestPath));
        var results = new List<Result>();
        foreach (var item in request.items)
        {
            byte[] png = File.ReadAllBytes(item.png);
            using (var sha = SHA256.Create())
                if (BitConverter.ToString(sha.ComputeHash(png)).Replace("-", "").ToLowerInvariant() != item.sha256)
                    throw new InvalidOperationException("Source image hash changed");
            Texture2D texture = null;
            Sprite sprite = null;
            try
            {
                texture = new Texture2D(2, 2, TextureFormat.RGBA32, false);
                if (!ImageConversion.LoadImage(texture, png, false)) throw new InvalidOperationException("Source image decode failed");
                sprite = Sprite.Create(texture, new Rect(item.rect[0], item.rect[1], item.rect[2], item.rect[3]),
                    new Vector2(item.pivot[0], item.pivot[1]), item.pixels_per_unit, item.extrude,
                    (SpriteMeshType)item.mesh_type, new Vector4(item.border[0], item.border[1], item.border[2], item.border[3]), true);
                var shapes = new Shape[sprite.GetPhysicsShapeCount()];
                var points = new List<Vector2>();
                for (int index = 0; index < shapes.Length; ++index)
                {
                    points.Clear();
                    sprite.GetPhysicsShape(index, points);
                    shapes[index] = new Shape { xy_bits = Points(points) };
                }
                results.Add(new Result { id = item.id, width = texture.width, height = texture.height,
                    vertex_xy_bits = Points(sprite.vertices), triangles = Array.ConvertAll(sprite.triangles, v => (int)v), physics = shapes });
            }
            finally
            {
                if (sprite) UnityEngine.Object.DestroyImmediate(sprite);
                if (texture) UnityEngine.Object.DestroyImmediate(texture);
            }
        }
        File.WriteAllText(outputPath, JsonUtility.ToJson(new Results { success = true, unity_version = Application.unityVersion, items = results.ToArray() }, true));
    }
}
