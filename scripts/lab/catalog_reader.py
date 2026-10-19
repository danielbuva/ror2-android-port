"""Host reader for the shipped Addressables content catalog (schema 2 source-catalog.json).

It mirrors the original `ContentCatalogData.CreateLocator` and the lab's former editor query
(`tools/catalog/ExportCatalog.cs.txt`), so catalog evidence no longer needs a Unity editor.
Labels and provider identifiers come from shipped IL through the assembly probe. Nothing from
the game is executed. The output is compared byte-for-byte with the editor-made reference.
"""

import base64
import json
import struct
from pathlib import Path

RUNTIME_PATH_TOKEN = "{UnityEngine.AddressableAssets.Addressables.RuntimePath}"
BUNDLE_OPTIONS = ("UnityEngine.ResourceManagement.ResourceProviders.AssetBundleRequestOptions",)


def _int32(data, offset):
    return struct.unpack_from("<i", data, offset)[0]


def read_object(data, index):
    """`SerializationUtilities.ReadObjectFromByteArray`: returns (value, .NET type name)."""
    kind = data[index]
    index += 1
    if kind == 0:  # AsciiString
        count = _int32(data, index)
        return data[index + 4 : index + 4 + count].decode("ascii"), "System.String"
    if kind == 1:  # UnicodeString
        count = _int32(data, index)
        return data[index + 4 : index + 4 + count].decode("utf-16-le"), "System.String"
    if kind == 2:
        return struct.unpack_from("<H", data, index)[0], "System.UInt16"
    if kind == 3:
        return struct.unpack_from("<I", data, index)[0], "System.UInt32"
    if kind == 4:
        return _int32(data, index), "System.Int32"
    if kind == 7:  # JsonObject: assembly, class, UTF-16 JsonUtility body
        length = data[index]
        assembly = data[index + 1 : index + 1 + length].decode("ascii")
        index += 1 + length
        length = data[index]
        name = data[index + 1 : index + 1 + length].decode("ascii")
        index += 1 + length
        count = _int32(data, index)
        body = data[index + 4 : index + 4 + count].decode("utf-16-le")
        return dict(assembly=assembly, type=name, json=json.loads(body)), name
    raise RuntimeError("Unsupported catalog object kind " + str(kind) + "; extend the reader from the original source first")


def key_text(value):
    # The editor query wrote key.ToString(); only strings and integers occur in the shipped catalog.
    if isinstance(value, (str, int)) and not isinstance(value, bool):
        return str(value)
    raise RuntimeError("Unsupported catalog key value: " + repr(value))


def read_shipped(catalog, runtime_path, names, provider_suffix="whole-source-audit"):
    """Return the schema 2 catalog record the editor query produced, from catalog.json alone."""
    raw = json.loads(Path(catalog).read_text(encoding="utf-8-sig"))
    if raw.get("m_InternalIdPrefixes"):
        raise RuntimeError("Internal ID prefixes are present; mirror ExpandInternalId before use")
    buckets_data = base64.b64decode(raw["m_BucketDataString"])
    buckets, offset = [], 4
    for _ in range(_int32(buckets_data, 0)):
        data_offset, count = _int32(buckets_data, offset), _int32(buckets_data, offset + 4)
        offset += 8
        buckets.append((data_offset, [_int32(buckets_data, offset + 4 * j) for j in range(count)]))
        offset += 4 * count
    providers = [p if p.endswith(provider_suffix) else p + provider_suffix for p in raw["m_ProviderIds"]]
    extra = base64.b64decode(raw["m_ExtraDataString"])
    key_data = base64.b64decode(raw["m_KeyDataString"])
    keys = [read_object(key_data, data_offset) for data_offset, _ in buckets]
    types = []
    for row in raw["m_resourceTypes"]:
        # The editor resolved every shipped type; AssemblyQualifiedName nests with '+'.
        types.append(row["m_ClassName"] + ", " + row["m_AssemblyName"] if row["m_ClassName"] and row["m_AssemblyName"] else None)
    entries_data = base64.b64decode(raw["m_EntryDataString"])
    entries = []
    for m in range(_int32(entries_data, 0)):
        internal, provider, dependency, _dep_hash, data_index, primary, resource = struct.unpack_from("<7i", entries_data, 4 + m * 28)
        data = read_object(extra, data_index)[0] if data_index >= 0 else None
        internal_id = raw["m_InternalIds"][internal]
        if "{" in internal_id.replace(RUNTIME_PATH_TOKEN, ""):
            raise RuntimeError("Unmeasured runtime property token in " + internal_id)
        entries.append(
            dict(
                internalId=internal_id.replace(RUNTIME_PATH_TOKEN, runtime_path),
                provider=providers[provider],
                dependency=dependency,
                data=data,
                primaryKey=key_text(keys[primary][0]),
                type=types[resource],
            )
        )
    # ResourceLocationMap: one key per bucket, in bucket order (a Dictionary with no removals).
    seen = set()
    for value, kind in keys:
        if (kind, value) in seen:
            raise RuntimeError("Duplicate catalog key " + repr(value))
        seen.add((kind, value))

    ids, order = {}, []

    def identify(entry):
        if entry not in ids:
            ids[entry] = len(order)
            order.append(entry)
        return ids[entry]

    out_keys = [dict(key=key_text(value), keyType=kind, locations=[identify(e) for e in bucket]) for (value, kind), (_, bucket) in zip(keys, buckets)]
    dependency_sets, dependency_ids, rows = [], {}, []
    i = 0
    while i < len(order):
        entry = entries[order[i]]
        deps = []
        if entry["dependency"] >= 0:
            # CompactLocation.Dependencies locates with typeof(object): unresolved types drop out.
            found = [e for e in buckets[entry["dependency"]][1] if entries[e]["type"] is not None]
            deps = [identify(e) for e in found]
        signature = ",".join(map(str, deps))
        if signature not in dependency_ids:
            dependency_ids[signature] = len(dependency_sets)
            dependency_sets.append(deps)
        data = entry["data"]
        bundle = None
        if isinstance(data, dict) and data["type"] in BUNDLE_OPTIONS:
            options = data["json"]
            bundle = dict(BundleName=options["m_BundleName"], Hash=options["m_Hash"], BundleSize=options["m_BundleSize"], Crc=options["m_Crc"])
        rows.append(
            dict(
                id=i,
                primaryKey=entry["primaryKey"],
                internalId=entry["internalId"],
                provider=entry["provider"],
                type=entry["type"],
                dependencySet=dependency_ids[signature],
                bundle=bundle,
            )
        )
        i += 1
    return dict(schemaVersion=2, keys=out_keys, locations=rows, dependencySets=dependency_sets, labels=names["labels"], providers=names["providers"])


def dumps(record):
    """Newtonsoft `Formatting.Indented` as the editor query wrote it (two spaces, LF, no BOM)."""
    return json.dumps(record, indent=2, ensure_ascii=False)
