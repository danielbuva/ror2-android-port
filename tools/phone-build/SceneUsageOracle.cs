using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Security.Cryptography;
using UnityEditor;
using UnityEditor.Build.Content;
using UnityEditor.Build.Player;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Rendering;

// SDK-only desktop observation. Never builds a player or supplies phone roots.
public static class SceneUsageOracle
{
    [Serializable] public sealed class TypeRow { public string assembly, name; }
    [Serializable] public sealed class FileRow { public string path, sha256; }
    [Serializable] public sealed class ObjectRow
    {
        public string guid, file_path, loaded_name;
        public long local_id;
        public int file_type, instance_id;
        public bool resolved, support_queried, supported, types_returned_null;
        public TypeRow[] types, loaded_types;
    }
    [Serializable] public sealed class Group { public string name; public ObjectRow[] objects; }
    [Serializable] public sealed class FieldRow { public string name, value; }
    [Serializable] public sealed class Usage { public string name; public FieldRow[] fields; }
    [Serializable] public sealed class Settings
    {
        public string target, group, backend, architecture, stripping, api;
        public string[] graphics;
        public bool strip_engine;
        public int script_options, content_flags;
    }
    [Serializable] public sealed class Report
    {
        public int schema = 1;
        public string unity, source_commit, profile = "authored-default-scene-dependencies-v1";
        public bool game_inputs, player_built, root_generation_qualified;
        public string phase, failure, scene, scene_sha256, type_db_hash;
        public Settings settings;
        public FileRow[] compiled_assemblies, loaded_assemblies;
        public TypeRow[] scene_types, manager_types;
        public Group[] groups;
        public Usage[] global_usage;
    }

    static readonly HashSet<Assembly> observedAssemblies = new HashSet<Assembly>();
    static string Sha(string path)
    {
        using (var hash = SHA256.Create())
        using (var input = File.OpenRead(path))
            return BitConverter.ToString(hash.ComputeHash(input)).Replace("-", "").ToLowerInvariant();
    }
    static FileRow FileInput(string path) { path = Path.GetFullPath(path); return new FileRow { path = path, sha256 = Sha(path) }; }
    static TypeRow TypeInput(Type type)
    {
        if (type == null || String.IsNullOrEmpty(type.FullName)) throw new InvalidOperationException("Missing observed type identity");
        observedAssemblies.Add(type.Assembly);
        return new TypeRow { assembly = type.Assembly.FullName, name = type.FullName };
    }
    static TypeRow[] Types(IEnumerable<Type> values) { return values.Select(TypeInput).ToArray(); }
    static ObjectRow Observe(ObjectIdentifier id)
    {
        Type[] types = ContentBuildInterface.GetTypesForObject(id);
        var target = ObjectIdentifier.ToObject(id);
        bool resolved = target != null;
        return new ObjectRow {
            guid = id.guid.ToString(), local_id = id.localIdentifierInFile, file_type = (int)id.fileType, file_path = id.filePath ?? "",
            instance_id = ObjectIdentifier.ToInstanceID(id), resolved = resolved, loaded_name = resolved ? target.name : "",
            support_queried = resolved, supported = resolved && ContentBuildInterface.ObjectIsSupportedInBuild(target),
            types_returned_null = types == null, types = types == null ? new TypeRow[0] : Types(types),
            loaded_types = resolved ? new[] { TypeInput(target.GetType()) } : new TypeRow[0]
        };
    }
    static Group Objects(string name, IEnumerable<ObjectIdentifier> values)
    {
        return new Group { name = name, objects = values.Select(Observe).ToArray() };
    }
    static Usage UsageFields(string name, BuildUsageTagGlobal value)
    {
        var fields = typeof(BuildUsageTagGlobal).GetFields(BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic);
        if (fields.Length == 0 || fields.Any(f => f.FieldType != typeof(uint) && f.FieldType != typeof(bool)))
            throw new InvalidOperationException("Unknown SDK global usage layout");
        return new Usage { name = name, fields = fields.OrderBy(f => f.Name, StringComparer.Ordinal).Select(f =>
            new FieldRow { name = f.Name, value = Convert.ToString(f.GetValue(value), System.Globalization.CultureInfo.InvariantCulture) }).ToArray() };
    }
    static void Configure()
    {
        PlayerSettings.companyName = "Porting Laboratory";
        PlayerSettings.productName = "Phone Content Fixture";
        PlayerSettings.bundleVersion = "0.0.2";
        PlayerSettings.Android.bundleVersionCode = 2;
        PlayerSettings.SetApplicationIdentifier(BuildTargetGroup.Android, "dev.ror2lab.phonecontentfixture");
        PlayerSettings.SetScriptingBackend(BuildTargetGroup.Android, ScriptingImplementation.IL2CPP);
        PlayerSettings.Android.targetArchitectures = AndroidArchitecture.ARM64;
        PlayerSettings.Android.minSdkVersion = AndroidSdkVersions.AndroidApiLevel23;
        PlayerSettings.Android.targetSdkVersion = AndroidSdkVersions.AndroidApiLevel30;
        PlayerSettings.SetManagedStrippingLevel(BuildTargetGroup.Android, ManagedStrippingLevel.Low);
        PlayerSettings.stripEngineCode = false;
        PlayerSettings.SetUseDefaultGraphicsAPIs(BuildTarget.Android, false);
        PlayerSettings.SetGraphicsAPIs(BuildTarget.Android, new[] { GraphicsDeviceType.Vulkan });
    }
    public static void Check()
    {
        if (!Application.isBatchMode || Application.unityVersion != "2021.3.45f2" || EditorUserBuildSettings.activeBuildTarget != BuildTarget.Android)
            throw new InvalidOperationException("Fresh exact Android SDK batch required");
        string attempt = Path.GetFullPath(Path.Combine(Application.dataPath, "../.."));
        string output = Environment.GetEnvironmentVariable("ROR2_SCENE_USAGE_REPORT");
        if (String.IsNullOrEmpty(output) || Path.GetFullPath(output) != Path.Combine(attempt, "oracle.json") || File.Exists(output))
            throw new InvalidOperationException("Explicit new oracle output required");
        string scripts = Path.Combine(attempt, "player-scripts");
        if (Directory.Exists(scripts) || File.Exists("Assets/Fixture.unity")) throw new InvalidOperationException("Fresh authored project required");
        var report = new Report { unity = Application.unityVersion, source_commit = Environment.GetEnvironmentVariable("ROR2_PHONE_BUILD_SOURCE"), phase = "configure" };
        try
        {
            observedAssemblies.Clear();
            foreach (var type in new[] { typeof(SceneUsageOracle), typeof(ContentBuildInterface), typeof(PlayerBuildInterface), typeof(EditorSceneManager), typeof(GameObject) })
                observedAssemblies.Add(type.Assembly);
            Configure();
            var options = ScriptCompilationOptions.DevelopmentBuild | ScriptCompilationOptions.Assertions;
            report.settings = new Settings {
                target = BuildTarget.Android.ToString(), group = BuildTargetGroup.Android.ToString(),
                backend = PlayerSettings.GetScriptingBackend(BuildTargetGroup.Android).ToString(),
                architecture = PlayerSettings.Android.targetArchitectures.ToString(), stripping = PlayerSettings.GetManagedStrippingLevel(BuildTargetGroup.Android).ToString(),
                strip_engine = PlayerSettings.stripEngineCode, api = PlayerSettings.GetApiCompatibilityLevel(BuildTargetGroup.Android).ToString(),
                graphics = PlayerSettings.GetGraphicsAPIs(BuildTarget.Android).Select(g => g.ToString()).ToArray(),
                script_options = (int)options, content_flags = (int)ContentBuildFlags.DevelopmentBuild
            };
            report.phase = "scene";
            var scene = EditorSceneManager.NewScene(NewSceneSetup.DefaultGameObjects, NewSceneMode.Single);
            new GameObject("PhoneContentFixture").AddComponent<ContentFixture>();
            report.scene = "Assets/Fixture.unity";
            if (!EditorSceneManager.SaveScene(scene, report.scene)) throw new InvalidOperationException("Authored scene was not saved");
            report.scene_sha256 = Sha(report.scene);
            var loaded = new List<ObjectIdentifier>();
            foreach (var root in scene.GetRootGameObjects())
            foreach (var transform in root.GetComponentsInChildren<Transform>(true))
            foreach (var target in new UnityEngine.Object[] { transform.gameObject }.Concat(transform.GetComponents<Component>().Cast<UnityEngine.Object>()))
            {
                ObjectIdentifier id;
                if (!ObjectIdentifier.TryGetObjectIdentifier(target, out id)) throw new InvalidOperationException("Saved scene object has no identifier");
                loaded.Add(id);
            }
            report.phase = "compile-player-scripts";
            Directory.CreateDirectory(scripts);
            var compiled = PlayerBuildInterface.CompilePlayerScripts(new ScriptCompilationSettings {
                target = BuildTarget.Android, group = BuildTargetGroup.Android, options = options
            }, scripts);
            if (compiled.typeDB == null || compiled.assemblies.Count == 0) throw new InvalidOperationException("No compiled player type database");
            using (compiled.typeDB)
            using (var sceneUsage = new BuildUsageTagSet())
            using (var managerUsage = new BuildUsageTagSet())
            {
                report.type_db_hash = compiled.typeDB.GetHash128().ToString();
                report.compiled_assemblies = compiled.assemblies.Select(path => FileInput(Path.IsPathRooted(path) ? path : Path.Combine(scripts, path))).ToArray();
                var settings = new BuildSettings { target = BuildTarget.Android, group = BuildTargetGroup.Android, typeDB = compiled.typeDB, buildFlags = ContentBuildFlags.DevelopmentBuild };
                report.phase = "scene-dependencies";
                var dependencies = ContentBuildInterface.CalculatePlayerDependenciesForScene(report.scene, settings, sceneUsage);
                if (dependencies.scene != report.scene) throw new InvalidOperationException("SDK returned another scene");
                report.scene_types = Types(dependencies.includedTypes);
                var graphics = ContentBuildInterface.GetGlobalUsageFromGraphicsSettings();
                var managerGlobal = dependencies.globalUsage | graphics;
                report.global_usage = new[] { UsageFields("scene", dependencies.globalUsage), UsageFields("graphics", graphics), UsageFields("managers", managerGlobal) };
                report.phase = "manager-dependencies";
                var managers = ContentBuildInterface.CalculatePlayerDependenciesForGameManagers(settings, managerGlobal, managerUsage);
                report.manager_types = Types(managers.includedTypes);
                report.phase = "object-observations";
                report.groups = new[] {
                    Objects("scene_loaded", loaded), Objects("scene_references", dependencies.referencedObjects),
                    Objects("scene_usage", sceneUsage.GetObjectIdentifiers()), Objects("manager_objects", managers.managerObjects),
                    Objects("manager_references", managers.referencedObjects), Objects("manager_usage", managerUsage.GetObjectIdentifiers())
                };
            }
            report.loaded_assemblies = observedAssemblies.OrderBy(a => a.FullName, StringComparer.Ordinal).Select(a => FileInput(a.Location)).ToArray();
            report.phase = "complete";
        }
        catch (Exception error) { report.failure = error.GetType().Name + ": " + error.Message; throw; }
        finally
        {
            using (var file = new FileStream(output, FileMode.CreateNew, FileAccess.Write))
            using (var writer = new StreamWriter(file)) writer.Write(JsonUtility.ToJson(report, true));
        }
    }
}
