#if UNITY_EDITOR
using System.Collections.Generic;
using UnityEngine;

// Authored exact-editor native serialization control; never attached by the game.
public sealed class NativeScriptSchemaFixture : MonoBehaviour
{
    public int control;
    public PropertyName propertyName;
    public ExposedReference<GameObject> exposedReference;
    public Vector2Int vector2Int;
    public Vector2Int[] vector2IntArray;
    public List<Vector2Int> vector2IntList;
    public Vector3Int vector3Int;
}
#endif
