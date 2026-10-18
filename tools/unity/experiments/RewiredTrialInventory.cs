using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using UnityEditor;
using UnityEngine;

// Evaluation through public reflection and Unity's serialized-property API only.
// Never reads vendor IL, private resources, or trial enforcement code.
public static class RewiredTrialInventory
{
    [Serializable] public class Member
    {
        public string signature;
        public bool isStatic;
        public int genericArity;
    }
    [Serializable] public class ApiType
    {
        public string type, assembly, baseType;
        public bool isSealed, isAbstract, isInterface;
        public Member[] methods, fields;
        public string[] interfaces;
        public string[] enumNames, enumValues;
    }
    [Serializable] public class Script
    {
        public string path, guid, type, assembly;
        public int executionOrder;
    }
    [Serializable] public class Plugin
    {
        public string path, guid;
        public bool editor, android;
        public string androidCpu;
    }
    [Serializable] public class Report
    {
        public string editor, project;
        public ApiType[] types;
        public Script[] scripts;
        public Plugin[] plugins;
        public string[] controllerAssets;
    }

    static string TypeName(Type t)
    {
        if (t.IsByRef) return TypeName(t.GetElementType()) + "&";
        if (t.IsPointer) return TypeName(t.GetElementType()) + "*";
        if (t.IsArray) return TypeName(t.GetElementType()) + "[" + new string(',', t.GetArrayRank() - 1) + "]";
        if (t.IsGenericParameter) return t.Name;
        if (t.IsGenericType && !t.IsGenericTypeDefinition)
            return TypeName(t.GetGenericTypeDefinition()) + "<" + string.Join(",", t.GetGenericArguments().Select(TypeName).ToArray()) + ">";
        return (t.FullName ?? t.Name).Replace('+', '/');
    }

    static IEnumerable<Type> ContractTypes(Type type)
    {
        yield return type;
        foreach (var nested in type.GetNestedTypes(BindingFlags.Public | BindingFlags.NonPublic)
            .Where(t => t.IsNestedPublic || t.IsNestedFamily || t.IsNestedFamORAssem))
            foreach (var child in ContractTypes(nested)) yield return child;
    }

    public static void Record()
    {
        if (Application.unityVersion != "2021.3.33f1" || !Application.dataPath.EndsWith("/rewired-trial-reference/Assets"))
            throw new InvalidOperationException("Wrong editor or reference project");
        if (EditorApplication.isCompiling || EditorApplication.isPlaying)
            throw new InvalidOperationException("Reference editor must be idle");
        var types = new List<ApiType>();
        foreach (var assembly in AppDomain.CurrentDomain.GetAssemblies())
        {
            if (assembly.IsDynamic) continue;
            Type[] exported;
            try { exported = assembly.GetExportedTypes(); }
            catch (ReflectionTypeLoadException e) { exported = e.Types.Where(t => t != null && t.IsVisible).ToArray(); }
            foreach (var type in exported.Where(t => t.Namespace == "Rewired" || (t.Namespace ?? "").StartsWith("Rewired.")).SelectMany(ContractTypes).Distinct())
            {
                var flags = BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance | BindingFlags.Static | BindingFlags.DeclaredOnly;
                var methods = type.GetMethods(flags).Where(m => m.IsPublic || m.IsFamily || m.IsFamilyOrAssembly).Select(m => new Member {
                    signature = TypeName(m.ReturnType) + " " + TypeName(type) + "::" + m.Name + "(" + string.Join(",", m.GetParameters().Select(p => TypeName(p.ParameterType)).ToArray()) + ")",
                    isStatic = m.IsStatic, genericArity = m.GetGenericArguments().Length
                }).ToList();
                methods.AddRange(type.GetConstructors(flags).Where(m => m.IsPublic || m.IsFamily || m.IsFamilyOrAssembly).Select(m => new Member {
                    signature = "System.Void " + TypeName(type) + "::.ctor(" + string.Join(",", m.GetParameters().Select(p => TypeName(p.ParameterType)).ToArray()) + ")", isStatic = false
                }));
                types.Add(new ApiType {
                    type = TypeName(type), assembly = assembly.FullName, baseType = type.BaseType == null ? null : TypeName(type.BaseType),
                    isSealed = type.IsSealed, isAbstract = type.IsAbstract, isInterface = type.IsInterface,
                    interfaces = type.GetInterfaces().Select(TypeName).OrderBy(s => s).ToArray(), methods = methods.OrderBy(m => m.signature).ToArray(),
                    fields = type.GetFields(flags).Where(f => f.IsPublic || f.IsFamily || f.IsFamilyOrAssembly).Select(f => new Member { signature = TypeName(f.FieldType) + " " + TypeName(type) + "::" + f.Name, isStatic = f.IsStatic }).ToArray(),
                    enumNames = type.IsEnum ? Enum.GetNames(type) : new string[0],
                    enumValues = type.IsEnum ? Enum.GetValues(type).Cast<object>().Select(v => Convert.ToInt64(v).ToString()).ToArray() : new string[0]
                });
            }
        }
        var scripts = new List<Script>();
        foreach (var guid in AssetDatabase.FindAssets("t:MonoScript", new[] { "Assets/Rewired" }))
        {
            var path = AssetDatabase.GUIDToAssetPath(guid);
            var script = AssetDatabase.LoadAssetAtPath<MonoScript>(path);
            var type = script.GetClass();
            scripts.Add(new Script { path = path, guid = guid, type = type == null ? null : TypeName(type), assembly = type == null ? null : type.Assembly.FullName, executionOrder = MonoImporter.GetExecutionOrder(script) });
        }
        var plugins = new List<Plugin>();
        foreach (var importer in PluginImporter.GetAllImporters().Where(i => i.assetPath.StartsWith("Assets/Rewired/")))
            plugins.Add(new Plugin { path = importer.assetPath, guid = AssetDatabase.AssetPathToGUID(importer.assetPath), editor = importer.GetCompatibleWithEditor(), android = importer.GetCompatibleWithPlatform(BuildTarget.Android), androidCpu = importer.GetPlatformData(BuildTarget.Android, "CPU") });
        var report = new Report { editor = Application.unityVersion, project = Application.dataPath,
            types = types.OrderBy(t => t.type).ToArray(), scripts = scripts.ToArray(), plugins = plugins.ToArray(),
            controllerAssets = AssetDatabase.FindAssets("t:ScriptableObject", new[] { "Assets/Rewired/Internal/Data/Controllers" }).Select(AssetDatabase.GUIDToAssetPath).OrderBy(s => s).ToArray() };
        System.IO.File.WriteAllText(System.IO.Path.Combine(Application.dataPath, "../../trial-public-api.json"), JsonUtility.ToJson(report, true) + "\n");
        Debug.Log("REWIRED_TRIAL_API_RECORDED types=" + report.types.Length);
    }

    public static void RecordSerialized()
    {
        if (!Application.dataPath.EndsWith("/rewired-trial-reference/Assets") || EditorApplication.isCompiling || EditorApplication.isPlaying)
            throw new InvalidOperationException("Reference editor must be idle");
        var prefab = AssetDatabase.LoadAssetAtPath<GameObject>("Assets/ReferenceInput/GameInputManager.prefab");
        var manager = prefab.GetComponent<Rewired.InputManager>();
        if (manager == null) throw new InvalidOperationException("Copied manager did not deserialize");
        var output = System.IO.Path.GetFullPath(System.IO.Path.Combine(Application.dataPath, "../.."));
        System.IO.File.WriteAllText(System.IO.Path.Combine(output, "trial-loaded-game-manager.json"), EditorJsonUtility.ToJson(manager, true) + "\n");
        var serialized = new SerializedObject(manager);
        var fields = new List<string>();
        var property = serialized.GetIterator();
        while (property.Next(true)) fields.Add(property.propertyPath + ":" + property.propertyType + ":" + property.type);
        System.IO.File.WriteAllLines(System.IO.Path.Combine(output, "trial-loaded-game-manager-schema.txt"), fields.ToArray());
        Debug.Log("REWIRED_TRIAL_SERIALIZED_RECORDED missingScripts=" + prefab.GetComponents<Component>().Count(c => c == null));
    }
}
