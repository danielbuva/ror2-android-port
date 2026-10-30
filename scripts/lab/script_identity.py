"""Unity script identities of a precompiled assembly, from the legitimate installation (J597).

Unity names a MonoScript inside a DLL by the assembly importer's GUID and a file ID: the first
four bytes (little-endian int32) of MD4("s\\0\\0\\0" + namespace + class name). This is the rule
the pinned AssetRipper `ScriptHashing.CalculateScriptFileID` (1ac666f) and ThunderKit
`FileIdUtil` replicate (J430). The installation's player data lists every shipped MonoScript,
so no editor is needed to resolve a serialized `m_Script` reference.
"""

from collections import defaultdict, namedtuple
from contextlib import closing
from bisect import bisect_right
import copy
import gc
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import struct
from types import SimpleNamespace as N
import uuid

MASK = 0xFFFFFFFF

# Standard Unity type-tree strings used by the admitted 2021.3 script schemas.
# Pinned UnityPy 1.25.3 TypeTreeNode/Tpk documents the offset convention; these
# are native serialization vocabulary, never game field names or type trees.
COMMON = {
    0: "AABB",
    19: "AnimationCurve",
    49: "Array",
    55: "Base",
    60: "BitField",
    81: "char",
    86: "ColorRGBA",
    106: "data",
    117: "double",
    161: "float",
    172: "GameObject",
    222: "int",
    226: "list",
    245: "Matrix4x4f",
    263: "MonoBehaviour",
    299: "m_Curve",
    307: "m_EditorClassIdentifier",
    331: "m_EditorHideFlags",
    349: "m_Enabled",
    374: "m_GameObject",
    387: "m_Index",
    427: "m_Name",
    434: "m_ObjectHideFlags",
    490: "m_Script",
    519: "m_Type",
    526: "m_Version",
    564: "PPtr<GameObject>",
    616: "PPtr<MonoScript>",
    646: "PPtr<Prefab>",
    741: "Quaternionf",
    753: "Rectf",
    767: "RectOffset",
    795: "size",
    800: "SInt16",
    814: "SInt64",
    821: "SInt8",
    840: "string",
    907: "UInt16",
    921: "UInt64",
    928: "UInt8",
    934: "unsigned int",
    981: "vector",
    988: "Vector2f",
    997: "Vector3f",
    1006: "Vector4f",
    1042: "Gradient",
    1057: "int2_storage",
    1070: "int3_storage",
    1093: "m_CorrespondingSourceObject",
    1121: "m_PrefabInstance",
    1138: "m_PrefabAsset",
}


def _rotate(value, bits):
    return ((value << bits) | (value >> (32 - bits))) & MASK


def md4(data):
    """RFC 1320 MD4; hashlib's OpenSSL backend may not provide it."""
    message = bytearray(data) + b"\x80"
    message += b"\0" * ((56 - len(message)) % 64) + struct.pack("<Q", len(data) * 8)
    state = [0x67452301, 0xEFCDAB89, 0x98BADCFE, 0x10325476]
    rounds = (
        (lambda x, y, z: (x & y) | (~x & z), 0, range(16), (3, 7, 11, 19)),
        (lambda x, y, z: (x & y) | (x & z) | (y & z), 0x5A827999, (0, 4, 8, 12, 1, 5, 9, 13, 2, 6, 10, 14, 3, 7, 11, 15), (3, 5, 9, 13)),
        (lambda x, y, z: x ^ y ^ z, 0x6ED9EBA1, (0, 8, 4, 12, 2, 10, 6, 14, 1, 9, 5, 13, 3, 11, 7, 15), (3, 9, 11, 15)),
    )
    for offset in range(0, len(message), 64):
        words = struct.unpack("<16I", message[offset : offset + 64])
        a, b, c, d = state
        for function, constant, order, shifts in rounds:
            for step, index in enumerate(order):
                value = _rotate((a + function(b, c, d) + words[index] + constant) & MASK, shifts[step % 4])
                a, b, c, d = d, value, b, c
        state = [(x + y) & MASK for x, y in zip(state, (a, b, c, d))]
    return struct.pack("<4I", *state)


def script_file_id(namespace, name):
    return struct.unpack("<i", md4(b"s\0\0\0" + namespace.encode() + name.encode())[:4])[0]


def tree_nodes(blob):
    """Decode embedded v22 type metadata without a UnityPy/Editor dependency."""
    if len(blob) < 8:
        raise ValueError("truncated script schema")
    count, length = struct.unpack_from("<II", blob)
    end = 8 + count * 32
    if not 0 < count <= 100000 or len(blob) != end + length:
        raise ValueError("invalid script schema extent")
    strings = blob[end:]

    def label(offset):
        if offset & 0x80000000:
            try:
                return COMMON[offset & 0x7FFFFFFF]
            except KeyError as error:
                raise ValueError("unqualified script common string") from error
        stop = strings.find(b"\0", offset)
        if offset >= length or stop < 0:
            raise ValueError("script schema string outside table")
        return strings[offset:stop].decode("utf-8")

    nodes = []
    previous = -1
    for version, level, flags, kind, name, size, _, meta, _ in struct.iter_unpack("<hBBIIiiiQ", blob[8:end]):
        if (not nodes and level) or (nodes and (not level or level > previous + 1)):
            raise ValueError("invalid script schema nesting")
        nodes.append({"version": version, "level": level, "flags": flags, "type": label(kind), "name": label(name), "size": size, "meta": meta})
        previous = level
    return nodes


def properties_hash(class_name, namespace, assembly_name, original_tree, sdk_tree):
    """Hash source custom fields with the SDK's editor MonoBehaviour base.

    Unity 2021.3's script hash uses the editor (flags=0) schema, rather than
    the player's release schema. All native node values come from the supplied
    SDK; all custom node values come from original PC type metadata.
    """
    original, native = tree_nodes(original_tree), tree_nodes(sdk_tree)
    for nodes in (original, native):
        if nodes[0]["type"] != "MonoBehaviour" or nodes[0]["name"] != "Base":
            raise ValueError("script schema is not MonoBehaviour")
    cutoff = next((i for i, node in enumerate(native) if node["level"] == 1 and node["name"] == "m_EditorClassIdentifier"), None)
    if cutoff is None:
        raise ValueError("SDK editor script base absent")
    cutoff += 1
    while cutoff < len(native) and native[cutoff]["level"] > 1:
        cutoff += 1
    native = native[:cutoff]
    names = {node["name"] for node in native if node["level"] == 1}
    custom, retain = [], False
    for node in original[1:]:
        if node["level"] == 1:
            retain = node["name"] not in names
        if retain:
            custom.append(node)
    data = bytearray((class_name + namespace + assembly_name).encode("utf-8"))
    for node in native + custom:
        data += node["type"].encode("utf-8") + node["name"].encode("utf-8")
        data += struct.pack("<iiiI", node["size"], node["flags"], node["version"], node["meta"] & 0x4000)
    return md4(data)


def installed_scripts(data_directory, assembly):
    """(namespace, class name) of every MonoScript the installation ships for `assembly`."""
    import UnityPy

    scripts = set()
    for item in UnityPy.load(str(data_directory / "globalgamemanagers.assets")).objects:
        if item.type.name == "MonoScript":
            script = item.read()
            if script.m_AssemblyName == assembly:
                scripts.add((script.m_Namespace, script.m_ClassName))
    if not scripts:
        raise RuntimeError("Installation lists no MonoScript for " + assembly)
    return scripts


def identity_rows(data_directory, assembly, guid):
    """`file ID|GUID|full name` rows, the format of the historical moon-script-identities.txt."""
    rows = sorted(
        (script_file_id(namespace, name), (namespace + "." if namespace else "") + name) for namespace, name in installed_scripts(data_directory, assembly)
    )
    if len({file_id for file_id, _ in rows}) != len(rows):
        raise RuntimeError("Script file ID collision in " + assembly)
    return "".join(f"{file_id}|{guid}|{name}\n" for file_id, name in rows)


def _node(kind, name, size, level=1, flags=0, meta=0):
    return {"type": kind, "name": name, "size": size, "level": level, "flags": flags, "meta": meta, "version": 1}


def _shift(nodes, delta):
    return [dict(node, level=node["level"] + delta) for node in nodes]


def _tree(nodes, common_strings=False):
    strings, offsets, entries = bytearray(), {}, []
    common = {value: 0x80000000 + key for key, value in COMMON.items()} if common_strings else {}

    def offset(value):
        if value in common:
            return common[value]
        if value not in offsets:
            offsets[value] = len(strings)
            strings.extend(value.encode() + b"\0")
        return offsets[value]

    for index, node in enumerate(nodes):
        entries.append(
            struct.pack(
                "<hBBIIiiiQ", node["version"], node["level"], node["flags"], offset(node["type"]), offset(node["name"]), node["size"], index, node["meta"], 0
            )
        )
    return struct.pack("<II", len(nodes), len(strings)) + b"".join(entries) + strings


def _fields(nodes):
    result = {}
    for index, node in enumerate(nodes):
        if node["level"] != nodes[0]["level"] + 1:
            continue
        end = index + 1
        while end < len(nodes) and nodes[end]["level"] > node["level"]:
            end += 1
        result[node["name"]] = nodes[index:end]
    return result


def _native_collection(field_type, nodes):
    """Apply the authored 45f2 fixture's native-value collection transfer rule.

    The original Vector3[] witness independently agrees: the vector's Array
    node is aligned, while its native scalar element is unchanged. This does
    not apply to object pointers, primitives or managed custom classes.
    """
    if nodes and field_type[0] in ("array", "generic"):
        if field_type[0] == "array":
            inner = field_type[1]
        elif _type_name(field_type[1][2]) == ("System.Collections.Generic", "List`1"):
            inner = field_type[2][0]
        else:
            return nodes
        data = next((node for node in nodes if node["level"] == 3 and node["name"] == "data"), None)
        array = next((node for node in nodes if node["level"] == 2 and node["type"] == "Array"), None)
        if inner[0] == "type" and str(inner[2].TypeNamespace) == "UnityEngine" and data and data["meta"] & 0x200000 and array:
            nodes[0]["type"] = "vector"
            array["meta"] |= 0x4000
    return nodes


def _type_name(row):
    return str(row.TypeNamespace), str(row.TypeName)


_MetaValue = namedtuple("_MetaValue", "value")
_MetaField = namedtuple("_MetaField", "Name Signature Flags")
_MetaFieldIndex = namedtuple("_MetaFieldIndex", "row row_index")
_MetaReference = namedtuple("_MetaReference", "table row_index row")


def _compact_metadata(pe, coded):
    """Retain only consumed CLR facts, without dnfile cross-table loading."""
    tables = pe.net.mdtables

    def raw(name):
        table = getattr(tables, name)
        return table.rows if table else ()

    source_defs = raw("TypeDef")
    type_flags = {}
    definitions = []
    for row in source_defs:
        key = bool(row.Flags.tdAbstract), bool(row.Flags.tdSerializable)
        if key not in type_flags:
            type_flags[key] = N(tdAbstract=key[0], tdSerializable=key[1])
        definitions.append(N(TypeName=str(row.TypeName), TypeNamespace=str(row.TypeNamespace), Flags=type_flags[key]))
    references = [N(TypeName=str(row.TypeName), TypeNamespace=str(row.TypeNamespace)) for row in raw("TypeRef")]
    specs = [N(Signature=_MetaValue(bytes(row.Signature.value))) for row in raw("TypeSpec")]
    assemblies = [N(Name=str(row.Name)) for row in raw("AssemblyRef")]
    local = {"TypeDef": definitions, "TypeRef": references, "TypeSpec": specs, "AssemblyRef": assemblies}
    names = {}

    def reference(value, encoding):
        tag = value & ((1 << encoding.tag_bits) - 1)
        index = value >> encoding.tag_bits
        kind = encoding.table_names[tag]
        row = local[kind][index - 1] if index and kind in local else None
        if kind not in names:
            names[kind] = N(name=kind)
        return _MetaReference(names[kind], index, row)

    for row, compact in zip(raw("TypeRef"), references):
        compact.ResolutionScope = reference(row.struct.ResolutionScope_CodedIndex, coded.ResolutionScope)
    field_flags, fields = {}, []
    for row in raw("Field"):
        key = bool(row.Flags.fdStatic), bool(row.Flags.fdInitOnly), bool(row.Flags.fdNotSerialized), bool(row.Flags.fdPublic)
        if key not in field_flags:
            field_flags[key] = N(fdStatic=key[0], fdInitOnly=key[1], fdNotSerialized=key[2], fdPublic=key[3])
        fields.append(_MetaField(str(row.Name), _MetaValue(bytes(row.Signature.value)), field_flags[key]))
    method_starts = [row.struct.MethodList_Index for row in source_defs]
    for position, (row, compact) in enumerate(zip(source_defs, definitions)):
        compact.Extends = reference(row.struct.Extends_CodedIndex, coded.TypeDefOrRef)
        start = row.struct.FieldList_Index
        stop = source_defs[position + 1].struct.FieldList_Index if position + 1 < len(source_defs) else len(fields) + 1
        compact.FieldList = [_MetaFieldIndex(fields[index - 1], index) for index in range(start, stop)]

    attributes = defaultdict(set)
    members = raw("MemberRef")
    for row in raw("CustomAttribute"):
        parent = reference(row.struct.Parent_CodedIndex, coded.HasCustomAttribute)
        if parent.table.name != "Field":
            continue
        constructor = reference(row.struct.Type_CodedIndex, coded.CustomAttributeType)
        identity = None
        if constructor.table.name == "MethodDef":
            owner = bisect_right(method_starts, constructor.row_index) - 1
            if owner >= 0:
                identity = _type_name(definitions[owner])
        elif constructor.table.name == "MemberRef":
            member = members[constructor.row_index - 1]
            owner = reference(member.struct.Class_CodedIndex, coded.MemberRefParent)
            if owner.table.name in ("TypeDef", "TypeRef"):
                identity = _type_name(owner.row)
        if identity in {("UnityEngine", "SerializeField"), ("UnityEngine", "SerializeReference")}:
            attributes["Field", parent.row_index].add(identity)
        elif identity == ("UnityEngine.Serialization", "FormerlySerializedAsAttribute"):
            attributes["Field", parent.row_index].add((*identity, bytes(row.Value.value)))
    exported = [
        N(
            TypeName=str(row.TypeName),
            TypeNamespace=str(row.TypeNamespace),
            Flags=N(tdForwarder=bool(row.Flags.tdForwarder)),
            Implementation=reference(row.struct.Implementation_CodedIndex, coded.Implementation),
        )
        for row in raw("ExportedType")
    ]
    nested = [N(NestedClass=N(row_index=row.struct.NestedClass_Index)) for row in raw("NestedClass")]
    projected = N(TypeDef=N(rows=definitions), TypeRef=N(rows=references), TypeSpec=N(rows=specs), ExportedType=N(rows=exported), NestedClass=N(rows=nested))
    return N(net=N(mdtables=projected), close=lambda: None), attributes


class _RegistryTypes:
    """Read source CLR metadata and serialize fields; never execute assemblies."""

    def __init__(self, managed, providers, pin, native, templates):
        import dnfile  # Optional on the existing stdlib-only player-data path.

        self.dnfile = dnfile
        self.managed, self.providers, self.pin = managed, providers, pin
        self.loaded, self.attributes, self.bindings = {}, {}, {}
        self.active = []
        self.native, self.native_templates = native, templates
        self.base = tree_nodes(native) if native else []
        if self.base:
            end = next(index for index, node in enumerate(self.base) if node["level"] == 1 and node["name"] == "m_EditorClassIdentifier") + 1
            while end < len(self.base) and self.base[end]["level"] > 1:
                end += 1
            self.base = self.base[:end]
        self.templates = {}

    def close(self):
        """Release PE mappings and cross-table row ownership after production."""
        while self.loaded:
            _, pe = self.loaded.popitem()
            pe.close()
            del pe
        self.attributes.clear()
        self.bindings.clear()
        self.active.clear()
        self.templates.clear()
        gc.collect()

    def load(self, assembly):
        if assembly not in self.loaded:
            provider = self.providers.get(assembly)
            path = Path(provider["path"]) if provider else self.managed / assembly
            self.pin(path, provider)
            with closing(self.dnfile.dnPE(str(path), clr_lazy_load=True)) as pe:
                if not pe.net or not pe.net.mdtables.TypeDef:
                    raise ValueError("registry source has no CLR types: " + assembly)
                self.loaded[assembly], self.attributes[assembly] = _compact_metadata(pe, self.dnfile.codedindex)
            del pe
            gc.collect()
        return self.loaded[assembly]

    def resolve(self, assembly, kind, row):
        if kind == "TypeDef":
            return assembly, row
        if kind == "TypeSpec":
            value, _ = self.field_type(assembly, row.Signature.value, 0)
            return value[1][1:] if value[0] == "generic" else value[1:]
        if kind != "TypeRef":
            raise ValueError("unqualified registry CLR reference: " + kind)
        namespace, name = _type_name(row)
        scope = row.ResolutionScope
        if scope.table.name == "AssemblyRef":
            assembly = str(scope.row.Name) + ".dll"
        elif scope.table.name == "TypeRef":
            assembly = self.resolve(assembly, "TypeRef", scope.row)[0]
        for _ in range(16):
            pe = self.load(assembly)
            found = [item for item in pe.net.mdtables.TypeDef.rows if _type_name(item) == (namespace, name)]
            if len(found) == 1:
                return assembly, found[0]
            table = pe.net.mdtables.ExportedType
            forward = (
                next(
                    (
                        item
                        for item in table.rows
                        if _type_name(item) == (namespace, name) and item.Flags.tdForwarder and item.Implementation.table.name == "AssemblyRef"
                    ),
                    None,
                )
                if table
                else None
            )
            if not forward or found:
                break
            assembly = str(forward.Implementation.row.Name) + ".dll"
        raise ValueError("unqualified registry CLR identity: " + str((assembly, namespace, name)))

    @staticmethod
    def compressed(data, index):
        value = data[index]
        index += 1
        if value & 0xC0 == 0x80:
            value = ((value & 0x3F) << 8) | data[index]
            index += 1
        elif value & 0xE0 == 0xC0:
            value = ((value & 0x1F) << 24) | int.from_bytes(data[index : index + 3], "big")
            index += 3
        return value, index

    def field_type(self, assembly, data, index):
        code = data[index]
        index += 1
        if code in (2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 24, 25, 28):
            return ("primitive", code), index
        if code == 19:
            argument, index = self.compressed(data, index)
            if argument >= len(self.active):
                raise ValueError("unbound registry generic field parameter")
            return self.active[argument], index
        if code in (17, 18):
            token, index = self.compressed(data, index)
            kind = ("TypeDef", "TypeRef", "TypeSpec")[token & 3]
            row = getattr(self.load(assembly).net.mdtables, kind).rows[(token >> 2) - 1]
            owner, resolved = self.resolve(assembly, kind, row)
            return ("type", owner, resolved), index
        if code == 29:
            inner, index = self.field_type(assembly, data, index)
            return ("array", inner), index
        if code == 21:
            base, index = self.field_type(assembly, data, index)
            count, index = self.compressed(data, index)
            arguments = []
            for _ in range(count):
                argument, index = self.field_type(assembly, data, index)
                arguments.append(argument)
            return ("generic", base, arguments), index
        raise ValueError("unsupported registry CLR field signature: " + str(code))

    def parent(self, assembly, row, arguments=True):
        reference = row.Extends
        if not reference or not reference.row_index:
            return None
        if reference.table.name != "TypeSpec":
            return self.resolve(assembly, reference.table.name, reference.row)
        data = reference.row.Signature.value
        if not arguments:
            if data[:2] not in (b"\x15\x11", b"\x15\x12"):
                raise ValueError("unsupported registry generic ancestor")
            token, _ = self.compressed(data, 2)
            kind = ("TypeDef", "TypeRef", "TypeSpec")[token & 3]
            return self.resolve(assembly, kind, getattr(self.load(assembly).net.mdtables, kind).rows[(token >> 2) - 1])
        previous, self.active = self.active, self.bindings.get((assembly, id(row)), [])
        try:
            value, _ = self.field_type(assembly, data, 0)
            if value[0] == "generic":
                base = value[1]
                self.bindings[base[1], id(base[2])] = value[2]
                return base[1:]
            return value[1:]
        finally:
            self.active = previous

    def hierarchy(self, assembly, row, arguments=True):
        result, seen = [], set()
        while row is not None and (assembly, id(row)) not in seen:
            seen.add((assembly, id(row)))
            identity = _type_name(row)
            if identity in {("UnityEngine", "Object"), ("UnityEngine", "MonoBehaviour"), ("UnityEngine", "ScriptableObject")}:
                return list(reversed(result)), True
            if identity == ("System", "Object"):
                return list(reversed(result)), False
            result.append((assembly, row))
            parent = self.parent(assembly, row, arguments)
            if not parent:
                return list(reversed(result)), False
            assembly, row = parent
        return list(reversed(result)), False

    @staticmethod
    def key(value):
        if value[0] == "primitive":
            return value
        if value[0] == "array":
            return "array", _RegistryTypes.key(value[1])
        if value[0] == "generic":
            return "generic", _RegistryTypes.key(value[1]), tuple(_RegistryTypes.key(item) for item in value[2])
        return "type", value[1], *_type_name(value[2])

    def eligible(self, assembly, index):
        field = index.row
        attributes = self.attributes[assembly]["Field", index.row_index]
        return not (field.Flags.fdStatic or field.Flags.fdInitOnly or field.Flags.fdNotSerialized) and (
            field.Flags.fdPublic or bool({("UnityEngine", "SerializeField"), ("UnityEngine", "SerializeReference")} & attributes)
        )

    def declared_field_names(self, class_name, namespace, assembly):
        found = [row for row in self.load(assembly).net.mdtables.TypeDef.rows if _type_name(row) == (namespace, class_name)]
        if len(found) != 1:
            raise ValueError("current script CLR identity is absent or ambiguous")
        hierarchy, is_object = self.hierarchy(assembly, found[0], arguments=False)
        if not is_object:
            raise ValueError("current script CLR hierarchy is not a Unity object")
        names = set()
        for owner, row in hierarchy:
            for index in row.FieldList:
                names.add(str(index.row.Name))
                for attribute in self.attributes[owner]["Field", index.row_index]:
                    if attribute[:2] != ("UnityEngine.Serialization", "FormerlySerializedAsAttribute"):
                        continue
                    blob = attribute[2]
                    if len(blob) < 5 or blob[:2] != b"\x01\0" or blob[2] == 255:
                        raise ValueError("unsupported original serialized-name alias")
                    length, start = self.compressed(blob, 2)
                    if start + length + 2 != len(blob) or blob[-2:] != bytes(2):
                        raise ValueError("unsupported original serialized-name alias arguments")
                    names.add(blob[start : start + length].decode("utf-8"))
        return names

    def custom_fields(self, hierarchy, depth=0):
        result = []
        for assembly, row in hierarchy:
            previous, self.active = self.active, self.bindings.get((assembly, id(row)), [])
            try:
                for index in row.FieldList:
                    if not self.eligible(assembly, index):
                        continue
                    if ("UnityEngine", "SerializeReference") in self.attributes[assembly]["Field", index.row_index]:
                        raise ValueError("unsupported registry managed-reference transfer")
                    value, end = self.field_type(assembly, index.row.Signature.value, 1)
                    if end != len(index.row.Signature.value):
                        raise ValueError("registry CLR field signature has trailing data")
                    nodes = self.emit(value, str(index.row.Name), depth + 1)
                    if nodes:
                        result.extend(nodes)
            finally:
                self.active = previous
        return result

    def emit(self, value, name, depth=0):
        if depth > 8:
            raise ValueError("recursive registry source field type")
        primitives = {
            2: ("UInt8", 1, 0x4000),
            3: ("UInt16", 2, 0x4000),
            4: ("SInt8", 1, 0x4000),
            5: ("UInt8", 1, 0x4000),
            6: ("SInt16", 2, 0x4000),
            7: ("UInt16", 2, 0x4000),
            8: ("int", 4, 0),
            9: ("unsigned int", 4, 0),
            10: ("SInt64", 8, 0),
            11: ("UInt64", 8, 0),
            12: ("float", 4, 0),
            13: ("double", 8, 0),
        }
        actual = value[1] if value[0] == "generic" else value
        if actual[0] == "type":
            namespace, class_name = _type_name(actual[2])
            if (namespace == "System" or namespace.startswith("System.")) and (namespace, class_name) != ("System.Collections.Generic", "List`1"):
                return None
        if value[0] == "generic" and _type_name(value[1][2]) != ("System.Collections.Generic", "List`1"):
            self.bindings[value[1][1], id(value[1][2])] = value[2]
        key = self.key(value)
        if key in self.templates:
            nodes = copy.deepcopy(self.templates[key])
            nodes[0]["name"] = name
            nodes = self.editor_curves(nodes)
            return _native_collection(value, nodes)
        if value[0] == "primitive":
            code = value[1]
            if code in primitives:
                kind, size, meta = primitives[code]
                return [_node(kind, name, size, meta=meta)]
            if code == 14:
                return [_node("string", name, -1), _node("Array", "Array", -1, 2, 1, 0x4000), _node("int", "size", 4, 3), _node("char", "data", 1, 3)]
            return None
        if value[0] in ("array", "generic"):
            if value[0] == "generic":
                if _type_name(value[1][2]) != ("System.Collections.Generic", "List`1"):
                    return self.emit(value[1], name, depth)
                inner = value[2][0]
            else:
                inner = value[1]
            if inner[0] in ("array", "generic") and (inner[0] == "array" or str(inner[1][2].TypeName) == "List`1"):
                return None
            nodes = self.emit(inner, "data", depth + 1)
            if nodes is None:
                return None
            kind = (
                "vector"
                if inner[0] == "primitive" or nodes[0]["type"] in {item[0] for item in primitives.values()} or nodes[0]["type"].startswith("PPtr<")
                else nodes[0]["type"]
            )
            align = 0x4000 if inner[0] == "primitive" and inner[1] in (2, 3, 4, 5, 6, 7) else 0
            if align:
                nodes[0]["meta"] &= ~0x4000
            result = [_node(kind, name, -1, meta=align), _node("Array", "Array", -1, 2, 1, align), _node("int", "size", 4, 3)] + _shift(nodes, 2)
            return _native_collection(value, result)
        assembly, row = value[1:]
        namespace, class_name = _type_name(row)
        parent = self.parent(assembly, row)
        if parent and _type_name(parent[1]) == ("System", "Enum"):
            field = next(index.row for index in row.FieldList if str(index.row.Name) == "value__")
            underlying, _ = self.field_type(assembly, field.Signature.value, 1)
            return self.emit(underlying, name, depth + 1)
        hierarchy, is_object = self.hierarchy(assembly, row)
        if is_object:
            return [_node("PPtr<$" + class_name + ">", name, 12), _node("int", "m_FileID", 4, 2), _node("SInt64", "m_PathID", 8, 2)]
        if namespace == "UnityEngine":
            kind = {
                "LayerMask": "BitField",
                "Vector2": "Vector2f",
                "Vector3": "Vector3f",
                "Vector4": "Vector4f",
                "Color": "ColorRGBA",
                "Quaternion": "Quaternionf",
                "Rect": "Rectf",
                "Bounds": "AABB",
                "AnimationCurve": "AnimationCurve",
                "Gradient": "Gradient",
                "RectOffset": "RectOffset",
                "Matrix4x4": "Matrix4x4f",
                "Hash128": "Hash128",
                "GUIStyle": "GUIStyle",
            }.get(class_name)
            if kind not in self.native_templates:
                raise ValueError("unsupported registry native field: " + class_name)
            nodes = copy.deepcopy(self.native_templates[kind])
            nodes[0]["name"] = name
            return nodes
        if not row.Flags.tdSerializable:
            return None
        fields = self.custom_fields(hierarchy, depth)
        size = -1 if any(node["size"] < 0 for node in fields if node["level"] == 1) else sum(node["size"] for node in fields if node["level"] == 1)
        return [_node(class_name, name, size)] + _shift(fields, 1)

    def editor_curves(self, nodes):
        result, index = [], 0
        while index < len(nodes):
            node = nodes[index]
            if node["type"] == "AnimationCurve":
                replacement = _shift(self.native_templates["AnimationCurve"], node["level"] - 1)
                replacement[0]["name"] = node["name"]
                result.extend(replacement)
                index += 1
                while index < len(nodes) and nodes[index]["level"] > node["level"]:
                    index += 1
            else:
                result.append(node)
                index += 1
        return result

    def cache_fields(self, schemas):
        """Cache unique source field layouts by their fully qualified CLR type."""
        shapes = defaultdict(dict)

        def register(value, nodes):
            if value[0] == "primitive":
                return
            key = self.key(value)
            normalized = _shift(nodes, 1 - nodes[0]["level"])
            normalized[0]["name"] = "data"
            signature = json.dumps([dict(node, meta=node["meta"] & 0x4000) for node in normalized], sort_keys=True)
            shapes[key][signature] = normalized
            if value[0] in ("array", "generic"):
                if value[0] == "generic":
                    if _type_name(value[1][2]) != ("System.Collections.Generic", "List`1"):
                        return
                    inner = value[2][0]
                else:
                    inner = value[1]
                start = next((index for index, node in enumerate(normalized) if node["level"] == 3 and node["name"] == "data"), None)
                if start is not None:
                    register(inner, normalized[start:])
                return
            assembly, row = value[1:]
            hierarchy, is_object = self.hierarchy(assembly, row)
            if is_object or not row.Flags.tdSerializable:
                return
            register_fields(hierarchy, nodes)

        def register_fields(hierarchy, nodes):
            fields = _fields(nodes)
            for assembly, row in hierarchy:
                for index in row.FieldList:
                    name = str(index.row.Name)
                    if name not in fields:
                        continue
                    try:
                        value, _ = self.field_type(assembly, index.row.Signature.value, 1)
                        register(value, fields[name])
                    except ValueError as error:
                        # An open generic definition supplies no closed field
                        # witness. Its concrete uses are resolved by the caller.
                        if "unbound registry generic field parameter" not in str(error):
                            raise

        for identity, trees in schemas.items():
            assembly, namespace, class_name = identity
            pe = self.load(assembly)
            matches = [row for row in pe.net.mdtables.TypeDef.rows if _type_name(row) == (namespace, class_name)]
            if len(matches) != 1:
                raise ValueError("source schema has no unique current CLR class")
            hierarchy, _ = self.hierarchy(assembly, matches[0])
            for tree in trees:
                register_fields(hierarchy, tree_nodes(tree))
        self.templates = {key: next(iter(values.values())) for key, values in shapes.items() if len(values) == 1}

    def unsupported(self, assembly, row):
        """Identify unimplemented native transfers before attempting a schema."""
        _, is_object = self.hierarchy(assembly, row)
        if not is_object or row.Flags.tdAbstract or "`" in str(row.TypeName):
            return []
        result, seen = [], set()

        def walk(value, path, depth=0):
            if depth > 8:
                raise ValueError("recursive registry native source field")
            if value[0] == "primitive":
                return
            if value[0] == "array":
                walk(value[1], path + "[]", depth + 1)
                return
            if value[0] == "generic":
                base = value[1]
                namespace, name = _type_name(base[2])
                if (namespace, name) == ("UnityEngine", "ExposedReference`1"):
                    result.append("ExposedReference")
                    return
                if namespace == "System" or namespace.startswith("System."):
                    if (namespace, name) == ("System.Collections.Generic", "List`1"):
                        walk(value[2][0], path + "[]", depth + 1)
                    return
                self.bindings[base[1], id(base[2])] = value[2]
                value = base
            owner, definition = value[1:]
            namespace, name = _type_name(definition)
            if (namespace, name) in {("UnityEngine", "PropertyName"), ("UnityEngine", "Vector3Int")}:
                result.append(name)
                return
            key = owner, namespace, name
            if key in seen:
                return
            seen.add(key)
            hierarchy, is_object = self.hierarchy(owner, definition)
            if path and (is_object or not definition.Flags.tdSerializable or namespace == "System" or namespace.startswith("System.")):
                return
            for current, ancestor in hierarchy:
                previous, self.active = self.active, self.bindings.get((current, id(ancestor)), [])
                try:
                    for index in ancestor.FieldList:
                        if not self.eligible(current, index):
                            continue
                        if ("UnityEngine", "SerializeReference") in self.attributes[current]["Field", index.row_index]:
                            result.append("SerializeReference")
                            continue
                        field, _ = self.field_type(current, index.row.Signature.value, 1)
                        walk(field, str(index.row.Name), depth + 1)
                finally:
                    self.active = previous

        walk(("type", assembly, row), "")
        return result

    def script_schema(self, identity, schemas):
        """Return the source-derived editor transfer tree for a concrete object."""
        assembly, namespace, class_name = identity
        pe = self.load(assembly)
        found = [row for row in pe.net.mdtables.TypeDef.rows if _type_name(row) == (namespace, class_name)]
        if not found:
            return None
        if len(found) != 1:
            raise ValueError("ambiguous registry source class")
        row = found[0]
        hierarchy, is_object = self.hierarchy(assembly, row)
        if not is_object or row.Flags.tdAbstract or "`" in class_name:
            return None
        if identity in schemas:
            trees = schemas[identity]
            if len({properties_hash(class_name, namespace, assembly, tree, self.native) for tree in trees}) != 1:
                raise ValueError("conflicting original registry schemas")
            names = {str(index.row.Name) for owner, ancestor in hierarchy for index in ancestor.FieldList}
            base_names = {node["name"] for node in self.base if node["level"] == 1}
            nodes, retain = [], True
            for node in tree_nodes(trees[0]):
                if node["level"] == 1:
                    retain = node["name"] in names or node["name"] in base_names
                if retain:
                    nodes.append(node)
            tree = _tree(self.editor_curves(nodes))
        else:
            tree = _tree(self.base + self.custom_fields(hierarchy))
        return tree

    def script_hash(self, identity, schemas):
        tree = self.script_schema(identity, schemas)
        if tree is None:
            return bytes(16)
        assembly, namespace, class_name = identity
        return properties_hash(class_name, namespace, assembly, tree, self.native)


class OriginalScriptFields:
    """Scoped original CLR declarations under the existing pinned managed contract."""

    def __init__(self, pc, managed):
        self.pc = Path(pc).resolve(strict=True)
        relative = PurePosixPath(managed["path"])
        if relative.is_absolute() or ".." in relative.parts or "\\" in managed["path"]:
            raise ValueError("unsafe original script field root")
        self.directory = (self.pc / relative).resolve(strict=True)
        if not self.directory.is_relative_to(self.pc):
            raise ValueError("original script field root leaves game input")
        self.files, self.pins = managed["files"], {}
        self.clr = _RegistryTypes(self.directory, {}, self.pin, None, {})

    def pin(self, path, provider=None):
        path = Path(path).resolve(strict=True)
        if path.parent != self.directory or path.name not in self.files:
            raise ValueError("unadmitted original script field assembly")
        with path.open("rb") as stream:
            actual = hashlib.file_digest(stream, "sha256").hexdigest()
        if actual != self.files[path.name]:
            raise ValueError("original script field assembly drift")
        self.pins[str(path.relative_to(self.pc))] = actual

    def names(self, script):
        assembly, namespace, class_name = _script_record(script)["identity"]
        return self.clr.declared_field_names(class_name, namespace, assembly)

    def verify(self):
        for path in list(self.pins):
            self.pin(self.pc / path)

    def close(self):
        self.clr.close()


def pointer_script_schema(pc, managed, script, base_tree, pointer_tree, sdk_tree):
    """Derive a one-pointer script schema from pinned CLR and native inputs."""
    pc = Path(pc).resolve(strict=True)
    relative = PurePosixPath(managed["path"])
    if relative.is_absolute() or ".." in relative.parts or "\\" in managed["path"]:
        raise ValueError("unsafe script schema managed root")
    directory = (pc / relative).resolve(strict=True)
    if not directory.is_relative_to(pc):
        raise ValueError("script schema managed root leaves original input")
    pins = {}

    def pin(path, provider=None):
        path = Path(path).resolve(strict=True)
        if path.parent != directory or path.name not in managed["files"]:
            raise ValueError("unadmitted script schema assembly")
        with path.open("rb") as stream:
            actual = hashlib.file_digest(stream, "sha256").hexdigest()
        if actual != managed["files"][path.name]:
            raise ValueError("script schema assembly drift")
        pins[str(path.relative_to(pc))] = actual

    identity = _script_record(script)["identity"]
    assembly, namespace, class_name = identity
    base = tree_nodes(base_tree)
    native_names = {n["name"] for n in tree_nodes(sdk_tree) if n["level"] == 1}
    if any(n["level"] == 1 and n["name"] not in native_names for n in base):
        raise ValueError("script schema base has custom fields")
    prototype = [n for field, nodes in _fields(tree_nodes(pointer_tree)).items() if field not in native_names for n in nodes]
    if len(prototype) != 3 or not prototype[0]["type"].startswith("PPtr<") or [n["name"] for n in prototype[1:]] != ["m_FileID", "m_PathID"]:
        raise ValueError("script schema prototype is not one original pointer")
    with closing(_RegistryTypes(directory, {}, pin, b"", {})) as clr:
        found = [row for row in clr.load(assembly).net.mdtables.TypeDef.rows if _type_name(row) == (namespace, class_name)]
        if len(found) != 1:
            raise ValueError("script schema original class identity differs")
        hierarchy, is_object = clr.hierarchy(assembly, found[0])
        if not is_object:
            raise ValueError("script schema class is not a Unity object")
        custom = clr.custom_fields(hierarchy)
    if len(custom) != 3 or not custom[0]["type"].startswith("PPtr<$"):
        raise ValueError("script schema CLR fields are not one object pointer")
    release = copy.deepcopy(prototype)
    for original, generated in zip(release, custom, strict=True):
        if any(original[key] != generated[key] for key in ("level", "flags", "size", "version")):
            raise ValueError("script schema pointer transfer differs")
        original.update(type=generated["type"], name=generated["name"])
    tree = _tree(base + release, common_strings=True)
    properties = properties_hash(class_name, namespace, assembly, tree, sdk_tree)
    if properties != _script_record(script)["properties"]:
        raise ValueError("script schema differs from original script properties")
    for path, expected in list(pins.items()):
        pin(pc / path)
        if pins[path] != expected:
            raise ValueError("script schema assembly changed during production")
    return {"tree": tree, "hash": properties, "script_id": md4((class_name + namespace + assembly).encode())}, pins


def _script_record(body):
    stream = io.BytesIO(body)

    def string():
        size = struct.unpack("<I", stream.read(4))[0]
        value = stream.read(size).decode()
        stream.seek(-stream.tell() % 4, 1)
        return value

    name = string()
    order = struct.unpack("<i", stream.read(4))[0]
    properties = stream.read(16)
    class_name, namespace, assembly = string(), string(), string()
    if stream.read(1):
        raise ValueError("unqualified original MonoScript body")
    return {"name": name, "order": order, "properties": properties, "identity": (assembly, namespace, class_name), "body": body}


def _script_body(identity, properties, order=0):
    stream = io.BytesIO()

    def string(value):
        raw = value.encode()
        stream.write(struct.pack("<I", len(raw)) + raw)
        stream.write(bytes(-stream.tell() % 4))

    assembly, namespace, class_name = identity
    string(class_name)
    stream.write(struct.pack("<i", order) + properties)
    for value in (class_name, namespace, assembly):
        string(value)
    return stream.getvalue()


def _source_namespace(text, name):
    text = re.sub(r'//[^\n]*|/\*.*?\*/|@"(?:""|[^"])*"|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'', " ", text, flags=re.S)
    tokens = re.findall(r"\bnamespace\s+([A-Za-z_][A-Za-z0-9_.]*)|\b(?:class|struct|interface|enum)\s+([A-Za-z_][A-Za-z0-9_]*)|([{};])", text)
    stack, pending = [], None
    for namespace, class_name, brace in tokens:
        if class_name == name:
            return ".".join(value for value in stack if value)
        if namespace or class_name:
            pending = namespace or class_name
        elif brace == "{":
            stack.append(pending)
            pending = None
        elif brace == "}":
            stack.pop()
            pending = None
        elif brace == ";":
            pending = None
    return ""


def _native_subtrees(blob, kind):
    """Decode only a requested SDK subtree, not unrelated native class strings."""
    count, length = struct.unpack_from("<II", blob)
    end = 8 + count * 32
    strings, result = blob[end:], []
    if len(strings) != length:
        raise ValueError("invalid SDK native tree extent")
    for index in range(count):
        start = 8 + index * 32
        offset = struct.unpack_from("<I", blob, start + 4)[0]
        if offset & 0x80000000:
            label = COMMON.get(offset & 0x7FFFFFFF)
        else:
            stop = strings.find(b"\0", offset)
            label = strings[offset:stop].decode() if stop >= offset else None
        if label != kind:
            continue
        level, finish = blob[start + 2], index + 1
        while finish < count and blob[8 + finish * 32 + 2] > level:
            finish += 1
        entries = bytearray(blob[start : 8 + finish * 32])
        for position in range(2, len(entries), 32):
            entries[position] -= level
        result.append(_shift(tree_nodes(struct.pack("<II", finish - index, length) + entries + strings), 1))
    return result


def _original_membership(managed, scripts, imported_assemblies, pin):
    original_clr = _RegistryTypes(managed, {}, pin, None, {})
    identities = []
    try:
        assemblies = sorted({script["identity"][0] for script in scripts} - {"Assembly-CSharp.dll"} - imported_assemblies)
        for assembly in assemblies:
            if not (managed / assembly).is_file():
                continue
            pe = original_clr.load(assembly)
            nested = {item.NestedClass.row_index for item in pe.net.mdtables.NestedClass.rows} if pe.net.mdtables.NestedClass else set()
            for index, row in enumerate(pe.net.mdtables.TypeDef.rows, 1):
                if index not in nested and original_clr.hierarchy(assembly, row, arguments=False)[1]:
                    identities.append((assembly, *_type_name(row)))
        return identities
    finally:
        original_clr.close()
        del original_clr
        gc.collect()


def registry(pc, editor_resources, managed_production, authored_root, packages_root, input_hashes, registry_profile, W):
    """Produce a complete registry from admitted original/public/SDK sources.

    Return layout, body bytes, independently allocated script identities and
    input pins. The caller owns its existing writer, input-id policy and output
    receipt. No Unity execution, accepted file, cached schema or fixture binary
    is used. ``dnfile`` is loaded only when this function is requested.
    """
    pc, editor_resources, managed_production, authored_root, packages_root = [
        Path(value).resolve(strict=True) for value in (pc, editor_resources, managed_production, authored_root, packages_root)
    ]
    pins = {}

    def pin(path, expected=None):
        path = Path(path).resolve(strict=True)
        if not path.is_file():
            raise ValueError("registry provider is not a file")
        with path.open("rb") as stream:
            actual = {"bytes": path.stat().st_size, "sha256": hashlib.file_digest(stream, "sha256").hexdigest()}
        if expected and any(actual[key] != expected[key] for key in actual if key in expected):
            raise ValueError("registry source provider drift: " + path.name)
        if str(path) in pins and pins[str(path)] != actual:
            raise ValueError("registry input changed during production")
        pins[str(path)] = actual
        return actual

    def relative(root, value):
        name = PurePosixPath(value)
        if name.is_absolute() or ".." in name.parts or "\\" in value:
            raise ValueError("unsafe registry source path")
        path = (root / name).resolve(strict=True)
        if not path.is_relative_to(root):
            raise ValueError("registry source leaves admitted root")
        return path

    def serialized(path):
        with path.open("rb") as stream:
            stream.size = path.stat().st_size
            layout = W.read_serialized(stream)
            bodies = {}
            for row in layout["objects"]:
                if layout["types"][row["type_id"]]["class_id"] in (115, 150, 21):
                    stream.seek(layout["data_offset"] + row["offset"])
                    bodies[row["path_id"]] = W.B.exact(stream, row["bytes"])
        return layout, bodies

    authored = registry_profile["authored"]
    for name in authored["runtime_sources"]:
        value = authored["guids"].get(name)
        if not isinstance(value, str) or not re.fullmatch("[0-9a-f]{32}", value):
            raise ValueError("required explicit authored/source importer GUID missing")
    source = registry_profile["source"]
    startup = relative(pc, source["path"])
    pin(startup, source)
    original, native_bodies = serialized(startup)
    scripts = []
    for row in original["objects"]:
        if original["types"][row["type_id"]]["class_id"] == 115:
            scripts.append(_script_record(native_bodies[row["path_id"]]))
    original_scripts = {}
    for script in scripts:
        prior = original_scripts.get(script["identity"])
        if prior and prior["body"] != script["body"]:
            raise ValueError("ambiguous original registry script identity")
        original_scripts[script["identity"]] = script
    scripts = list(original_scripts.values())
    selected = registry_profile["script_properties_sdk"]
    pin(editor_resources, selected)
    with editor_resources.open("rb") as stream:
        stream.size = editor_resources.stat().st_size
        sdk = W.read_serialized(stream)
    row = next(row for row in sdk["objects"] if row["path_id"] == selected["path_id"])
    native_type = sdk["types"][row["type_id"]]
    if native_type["class_id"] != 114 or not native_type.get("tree"):
        raise ValueError("registry SDK MonoBehaviour schema differs")
    native = native_type["tree"]
    curves = []
    for typ in sdk["types"]:
        if typ.get("tree"):
            curves.extend(_native_subtrees(typ["tree"], "AnimationCurve"))
    curve = next((nodes for nodes in curves if any(node["name"] == "tangentMode" for node in nodes)), None)
    if curve is None:
        raise ValueError("SDK editor AnimationCurve transfer unavailable")

    engine = sdk["engine"]
    sdk = native_type = curves = typ = row = None
    gc.collect()

    result_path, providers_path = managed_production / "result.json", managed_production / "providers.json"
    pin(result_path)
    pin(providers_path)
    result, providers = json.loads(result_path.read_text()), json.loads(providers_path.read_text())
    if result.get("success") is not True or result.get("phase") != "managed-produced" or result.get("source_commit") != authored["source_commit"]:
        raise ValueError("fresh public-source managed production required")
    compiler_inputs = managed_production / "gameplay/inputs.json"
    pin(compiler_inputs)
    for name, digest in json.loads(compiler_inputs.read_text())["sources"].items():
        pin(Path(name), {"sha256": digest})
    for name, digest in authored["source_files"].items():
        pin(relative(authored_root, name), {"sha256": digest})

    # Load admitted original members first, including source MonoScript members.
    member_scripts = {}
    for witness in registry_profile["schema_witnesses"]:
        path = relative(pc, witness["path"])
        pin(path, witness)
        member = W.B.Bundle(path).member(witness["member"])
        layout = W.read_serialized(member)
        local = {}
        for item in layout["objects"]:
            if layout["types"][item["type_id"]]["class_id"] == 115:
                member.seek(layout["data_offset"] + item["offset"])
                local[item["path_id"]] = _script_record(W.B.exact(member, item["bytes"]))["identity"]
        if witness["member"] in member_scripts and member_scripts[witness["member"]] != local:
            raise ValueError("ambiguous original serialized member")
        member_scripts[witness["member"]] = local
    schemas = defaultdict(list)
    for witness in registry_profile["schema_witnesses"]:
        member = W.B.Bundle(relative(pc, witness["path"])).member(witness["member"])
        layout = W.read_serialized(member)
        for chosen in witness["types"]:
            typ = layout["types"][chosen["index"]]
            tree = typ.get("tree")
            if typ["class_id"] != 114 or not tree or hashlib.sha256(tree).hexdigest() != chosen["tree_sha256"] or typ["script_type"] < 0:
                raise ValueError("original registry schema witness drift")
            item = next(item for item in layout["objects"] if item["type_id"] == chosen["index"])
            member.seek(layout["data_offset"] + item["offset"])
            prefix = W.B.exact(member, min(item["bytes"], 28))
            fields = [node["name"] for node in tree_nodes(tree) if node["level"] == 1]
            if fields[:3] != ["m_GameObject", "m_Enabled", "m_Script"] or len(prefix) < 28:
                raise ValueError("unqualified original script relationship schema")
            relationship = struct.unpack_from("<iq", prefix, 16)
            if relationship != layout["scripts"][typ["script_type"]]:
                raise ValueError("original object and type script relationship differ")
            file_id, path_id = relationship
            if file_id == 0:
                source_member = witness["member"]
            elif 0 < file_id <= len(layout["externals"]):
                source_member = layout["externals"][file_id - 1]["path"].split("/")[-1]
            else:
                raise ValueError("unqualified original script external")
            identity = member_scripts.get(source_member, {}).get(path_id)
            if identity != tuple(chosen["identity"]):
                raise ValueError("original schema MonoScript identity differs")
            if tree not in schemas[identity]:
                schemas[identity].append(tree)

    member = layout = typ = None
    gc.collect()

    native_templates = {}
    kinds = {
        "BitField",
        "Vector2f",
        "Vector3f",
        "Vector4f",
        "Quaternionf",
        "ColorRGBA",
        "Rectf",
        "Bounds",
        "AABB",
        "Gradient",
        "RectOffset",
        "Matrix4x4f",
        "Hash128",
        "GUIStyle",
    }
    for trees in schemas.values():
        for tree in trees:
            nodes = tree_nodes(tree)
            for index, node in enumerate(nodes):
                if node["type"] not in kinds or node["type"] in native_templates:
                    continue
                end = index + 1
                while end < len(nodes) and nodes[end]["level"] > node["level"]:
                    end += 1
                native_templates[node["type"]] = _shift(nodes[index:end], 1 - node["level"])
    native_templates["AnimationCurve"] = curve
    managed = pc / "Risk of Rain 2_Data/Managed"
    package_manifest = Path(input_hashes).resolve(strict=True)
    pin(package_manifest)
    package_inputs = json.loads(package_manifest.read_text())
    package_files = {}
    for name, digest in package_inputs.items():
        if not name.startswith("packages/"):
            continue
        path = relative(packages_root, name.removeprefix("packages/"))
        pin(path, {"sha256": digest})
        package_files[path] = digest
    definitions = {}
    for path in package_files:
        if path.suffix == ".asmdef":
            definition = json.loads(path.read_text())
            definitions[path.parent] = definition
    rows, imported_assemblies = [], set()

    def guid(value):
        if not isinstance(value, str) or not re.fullmatch("[0-9a-f]{32}", value):
            raise ValueError("required explicit authored/source importer GUID missing")
        return value

    def add(identity, importer, importer_guid, body):
        rows.append({"identity": identity, "importer": importer, "guid": guid(importer_guid), "body": body})

    for path in sorted(package_files):
        if path.suffix != ".cs":
            continue
        owners = [parent for parent in definitions if path.is_relative_to(parent)]
        if not owners:
            raise ValueError("source importer has no admitted asmdef")
        definition = definitions[max(owners, key=lambda value: len(value.parts))]
        include, exclude = definition.get("includePlatforms") or [], definition.get("excludePlatforms") or []
        if (include and "Android" not in include) or "Android" in exclude:
            continue
        assembly = definition["name"] + ".dll"
        imported_assemblies.add(assembly)
        meta = path.with_name(path.name + ".meta")
        if meta not in package_files:
            raise ValueError("source importer has no admitted original meta")
        match = re.search(r"^guid: ([0-9a-f]{32})$", meta.read_text(), re.M)
        if not match:
            raise ValueError("source importer GUID missing")
        found = [script for script in scripts if script["identity"][0] == assembly and script["name"] == path.stem]
        if len(found) > 1:
            namespace = _source_namespace(path.read_text(encoding="utf-8-sig"), path.stem)
            found = [script for script in found if script["identity"][1] == namespace]
        if len(found) == 1:
            identity, body = found[0]["identity"], found[0]["body"]
        elif not found:
            identity = assembly, _source_namespace(path.read_text(encoding="utf-8-sig"), path.stem), path.stem
            body = _script_body(identity, bytes(16))
        else:
            raise ValueError("ambiguous source importer filename")
        add(identity, 11500000, match[1], body)

    original_identities = _original_membership(managed, scripts, imported_assemblies, pin)
    gc.collect()
    with closing(_RegistryTypes(managed, providers, pin, native, native_templates)) as clr:
        schemas = {identity: trees for identity, trees in schemas.items() if identity[0] in providers or (managed / identity[0]).is_file()}
        clr.cache_fields(schemas)

        def body_for(identity, previous=None):
            assembly, namespace, class_name = identity
            found = [row for row in clr.load(assembly).net.mdtables.TypeDef.rows if _type_name(row) == (namespace, class_name)]
            unsupported = clr.unsupported(assembly, found[0]) if found else []
            if unsupported:
                provider = providers.get(assembly)
                original_path = managed / assembly
                actual = pin(original_path)
                provider_path = Path(provider["path"]) if provider else original_path
                if previous is None or pin(provider_path)["sha256"] != actual["sha256"]:
                    raise ValueError("unsupported native registry transfer with changed/new provider: " + str(identity))
                return previous["body"]
            properties = clr.script_hash(identity, schemas)
            if previous:
                body = previous["body"]
                start = (4 + struct.unpack_from("<I", body)[0] + 3) // 4 * 4 + 4
                return body[:start] + properties + body[start + 16 :]
            return _script_body(identity, properties)

        for identity in original_identities:
            assembly, namespace, class_name = identity
            importer_guid = uuid.UUID(bytes_le=hashlib.md5(assembly.removesuffix(".dll").encode()).digest()).hex
            add(identity, script_file_id(namespace, class_name), importer_guid, body_for(identity, original_scripts.get(identity)))
        for name in authored["runtime_sources"]:
            if name not in authored["source_files"]:
                raise ValueError("authored registry source is not pinned")
            path = relative(authored_root, name)
            identity = "Assembly-CSharp.dll", _source_namespace(path.read_text(), path.stem), path.stem
            body = body_for(identity)
            order = authored["execution_orders"].get(name, 0)
            if order:
                body = _script_body(identity, _script_record(body)["properties"], order)
            add(identity, 11500000, authored["guids"].get(name), body)
        for generated in authored["generated"]:
            identity = "Assembly-CSharp.dll", generated["namespace"], generated["name"]
            add(identity, 11500000, generated["guid"], _script_body(identity, bytes(16)))
        for name in authored["support_sources"]:
            found = [script for script in scripts if script["identity"][0] == "Assembly-CSharp.dll" and script["name"] == PurePosixPath(name).stem]
            if len(found) != 1:
                raise ValueError("original support MonoScript is not unique")
            identity = found[0]["identity"]
            importer_guid = uuid.UUID(bytes_le=hashlib.md5(("Assembly-CSharp" + identity[1] + identity[2]).encode()).digest()).hex
            add(identity, 11500000, importer_guid, body_for(identity, found[0]))
        rows.sort(key=lambda row: (row["importer"], row["guid"]))
        if len({(row["importer"], row["guid"]) for row in rows}) != len(rows) or len({row["identity"] for row in rows}) != len(rows):
            raise ValueError("registry importer/identity collision")
        layout = {name: copy.deepcopy(original[name]) for name in ("trees", "scripts", "externals", "ref_types", "user")}
        layout.update(engine=engine, platform=13, types=[copy.deepcopy(typ) for typ in original["types"] if typ["class_id"] in (115, 150, 21)])
        objects, bodies, script_ids, offset = [], {}, {}, 0
        script_type = next(index for index, typ in enumerate(layout["types"]) if typ["class_id"] == 115)
        for path_id, row in enumerate(rows, 3):
            body = row["body"]
            objects.append({"path_id": path_id, "type_id": script_type, "offset": offset, "bytes": len(body)})
            bodies[path_id], script_ids[row["identity"]] = body, path_id
            offset = (offset + len(body) + 7) // 8 * 8
        for class_id in (150, 21):
            row = next(row for row in original["objects"] if original["types"][row["type_id"]]["class_id"] == class_id)
            body = native_bodies[row["path_id"]]
            objects.append(
                {
                    "path_id": row["path_id"],
                    "type_id": next(index for index, typ in enumerate(layout["types"]) if typ["class_id"] == class_id),
                    "offset": offset,
                    "bytes": len(body),
                }
            )
            bodies[row["path_id"]] = body
            offset = (offset + len(body) + 7) // 8 * 8
        layout["objects"] = sorted(objects, key=lambda row: row["path_id"])
        for path, expected in list(pins.items()):
            pin(Path(path), expected)
        return {"layout": layout, "bodies": bodies, "script_ids": script_ids, "provider_pins": pins}
