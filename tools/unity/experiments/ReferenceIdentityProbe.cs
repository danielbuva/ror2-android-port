using System;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEngine;

// Read imported object identities without entering Play Mode or instantiating prefabs.
public static class ReferenceIdentityProbe {
    [Serializable] public class Query { public string path, fileID; }
    [Serializable] public class Config { public string output, attempt; public Query[] queries; }
    [Serializable] public class Row { public string path, fileID, name, objectType, scriptType, assembly, error; public bool resolved; }
    [Serializable] public class Report { public string attempt; public Row[] rows; }
    [MenuItem("Porting Lab/Inspect Reference Identities")]
    public static void Inspect() {
        var config = JsonUtility.FromJson<Config>(File.ReadAllText("Assets/LabReferenceQuery.json"));
        var rows = config.queries.Select(q => {
            var row = new Row {path=q.path, fileID=q.fileID};
            try {
                var candidates = AssetDatabase.LoadAllAssetsAtPath(q.path);
                var main = AssetDatabase.LoadMainAssetAtPath(q.path);
                if (main) candidates = candidates.Concat(new[]{main}).Distinct().ToArray();
                foreach (var item in candidates) {
                    string guid; long id;
                    if (!AssetDatabase.TryGetGUIDAndLocalFileIdentifier(item, out guid, out id) || id.ToString()!=q.fileID) continue;
                    row.resolved=true; row.name=item.name; row.objectType=item.GetType().FullName;
                    var script=item as MonoScript;
                    if (script) {
                        var type=script.GetClass();
                        row.scriptType=type==null ? null : type.FullName;
                        row.assembly=type==null ? null : type.Assembly.GetName().Name;
                    }
                    break;
                }
            } catch(Exception e) {row.error=e.ToString();}
            return row;
        }).ToArray();
        File.WriteAllText(config.output, JsonUtility.ToJson(new Report{attempt=config.attempt,rows=rows},true));
        Debug.Log("LAB_REFERENCE_IDENTITIES "+config.attempt);
    }
}
