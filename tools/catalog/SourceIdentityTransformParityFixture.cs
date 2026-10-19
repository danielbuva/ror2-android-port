#if UNITY_EDITOR
using System;
using System.Reflection;
using Newtonsoft.Json.Linq;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.SceneManagement;

// An exact-editor contract fixture for the authored source-identity resolver.
// It creates and closes a disposable preview scene; it never loads generated game
// scenes or starts Run, networking, or native scene lifecycle callbacks.
internal static class SourceIdentityTransformParityFixture
{
    const string ExpectedShapeHash = "24b7a5111ef7cbd1a43dd76458cc5a147e5301b214c4d3017951a344992a9863";

    [MenuItem("Porting Lab/Verify Source Identity Transform Metadata")]
    static void Run()
    {
        Scene preview = EditorSceneManager.NewPreviewScene();
        GameObject root = null;
        GameObject duplicateRoot = null;
        GameObject wrongShapeRoot = null;
        try
        {
            // The inactive root includes Unicode and duplicate child names. The
            // selected object is distinguished by serialized child index, not name.
            root = new GameObject("Røøt");
            root.SetActive(false);
            var firstDuplicate = Child(root.transform, "Dup");
            var secondDuplicate = Child(root.transform, "Dup");
            var exactTarget = Child(secondDuplicate, "雪").gameObject;
            Child(root.transform, "Tail");
            SceneManager.MoveGameObjectToScene(root, preview);

            // Same root name but a different ordered tree must not shadow the
            // source root selected by its shape digest.
            wrongShapeRoot = new GameObject("Røøt");
            wrongShapeRoot.SetActive(false);
            Child(wrongShapeRoot.transform, "Dup");
            Child(wrongShapeRoot.transform, "Other");
            SceneManager.MoveGameObjectToScene(wrongShapeRoot, preview);

            Type resolver = typeof(PortSession).Assembly.GetType("LabPort.SourceStageLifecycle.SourceStageIdentityLifecycle", true);
            const BindingFlags PrivateStatic = BindingFlags.Static | BindingFlags.NonPublic;
            MethodInfo shapeHash = resolver.GetMethod("ShapeHash", PrivateStatic);
            MethodInfo resolvePath = resolver.GetMethod("ResolveTransformPath", PrivateStatic);
            Require(shapeHash != null && resolvePath != null, "production hash/resolver methods are available");
            string actualHash = (string)shapeHash.Invoke(null, new object[] { root.transform });
            Require(actualHash == ExpectedShapeHash, "Python/C# canonical shape hash matches Unicode golden value");

            JArray path =
                Path(ExpectedShapeHash, 2, new JObject { ["root"] = false, ["index"] = 1, ["sibling_count"] = 3, ["name"] = "Dup" },
                     new JObject { ["root"] = false, ["index"] = 0, ["sibling_count"] = 1, ["name"] = "雪" });
            var resolved = (GameObject)resolvePath.Invoke(null, new object[] { preview, path });
            Require(ReferenceEquals(resolved, exactTarget), "duplicate names resolve through exact child order");
            ExpectRefusal(
                resolvePath, preview,
                Path(ExpectedShapeHash, 2, new JObject { ["root"] = false, ["index"] = 1, ["sibling_count"] = 4, ["name"] = "Dup" }));
            ExpectRefusal(
                resolvePath, preview,
                Path(ExpectedShapeHash, 2, new JObject { ["root"] = false, ["index"] = 0, ["sibling_count"] = 3, ["name"] = "Wrong" }));

            var wrongRootDigest = (string)shapeHash.Invoke(null, new object[] { wrongShapeRoot.transform });
            Require(wrongRootDigest != ExpectedShapeHash, "same-name wrong-shape root has a distinct digest");
            ExpectRefusal(
                resolvePath, preview,
                Path(wrongRootDigest, 2, new JObject { ["root"] = false, ["index"] = 1, ["sibling_count"] = 3, ["name"] = "Dup" }));

            // A second identical root makes the name+shape binding ambiguous.
            duplicateRoot = UnityEngine.Object.Instantiate(root);
            duplicateRoot.name = root.name;
            SceneManager.MoveGameObjectToScene(duplicateRoot, preview);
            ExpectRefusal(resolvePath, preview,
                          Path(ExpectedShapeHash, 3,
                               new JObject { ["root"] = false, ["index"] = 1, ["sibling_count"] = 3, ["name"] = "Dup" },
                               new JObject { ["root"] = false, ["index"] = 0, ["sibling_count"] = 1, ["name"] = "雪" }));

            // Null serialized slots have no transform path. The production resolver
            // must reject one if accidentally asked to resolve it; host metadata
            // tests separately prove that the producer preserves the null slot.
            ExpectRefusal(resolvePath, preview, null);
            Debug.Log("Source identity transform metadata fixture passed.");
        }
        finally
        {
            if (root)
                UnityEngine.Object.DestroyImmediate(root);
            if (duplicateRoot)
                UnityEngine.Object.DestroyImmediate(duplicateRoot);
            if (wrongShapeRoot)
                UnityEngine.Object.DestroyImmediate(wrongShapeRoot);
            if (preview.IsValid())
                EditorSceneManager.ClosePreviewScene(preview);
        }
    }

    static Transform Child(Transform parent, string name)
    {
        var child = new GameObject(name);
        child.transform.SetParent(parent, false);
        return child.transform;
    }

    static JArray Path(string rootHash, int sameNameRootCount, params JObject[] children)
    {
        var path = new JArray { new JObject { ["root"] = true, ["index"] = JValue.CreateNull(), ["name"] = "Røøt",
                                              ["sibling_count"] = JValue.CreateNull(), ["same_name_root_count"] = sameNameRootCount,
                                              ["root_shape_sha256"] = rootHash, ["same_name_same_shape_count"] = 1 } };
        foreach (var child in children)
            path.Add(child);
        return path;
    }

    static void ExpectRefusal(MethodInfo resolvePath, Scene scene, JArray path)
    {
        try
        {
            resolvePath.Invoke(null, new object[] { scene, path });
        }
        catch (TargetInvocationException)
        {
            return;
        }
        throw new InvalidOperationException("Expected production resolver to refuse malformed or ambiguous metadata.");
    }

    static void Require(bool condition, string contract)
    {
        if (!condition)
            throw new InvalidOperationException("Source identity fixture failed: " + contract);
    }
}
#endif
