"""Recompute editor pass keys on qualified source-produced Shader record packs.

The original Shader schema, original dummy properties or acquired SDK snippets,
and current SDK compiler metadata own the new keys. Programs are retained from
an explicit successful source provider; this owner never compiles a program.
"""

import argparse
import hashlib
import io
import json
from pathlib import Path
import struct
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import object_produce as O
import record_produce as A
import shader_produce as P
import shader_sdk as SDK


def key_spans(body, root):
    spans = A.fields(body, root)[1]
    found = {}
    for path, (start, end) in spans.items():
        if path[-1] != "m_EditorDataHash":
            continue
        count = struct.unpack_from("<I", body, start)[0]
        if not count:
            continue
        if count != 1 or end - start != 20:
            raise ValueError("Unsupported source Shader editor-key array")
        offset = spans[path[:-1] + ("m_State", "gpuProgramID")][0]
        identity = struct.unpack_from("<I", body, offset)[0]
        if identity in found:
            raise ValueError("Duplicate source Shader snippet identity")
        found[identity] = (start + 4, end)
    return found


def replace_keys(body, root, keys):
    """Change only checked 16-byte key slots; retain all program/body bytes."""
    spans = key_spans(body, root)
    if not spans or set(keys) != spans.keys() or any(not isinstance(key, bytes) or len(key) != 16 for key in keys.values()):
        raise ValueError("Source Shader editor-key coverage differs")
    result = bytearray(body)
    for identity, (start, end) in spans.items():
        result[start:end] = keys[identity]
    return bytes(result)


def checked_original(pc, selected):
    path = P.relative(pc, selected["path"])
    P.checked(path, selected)
    with O.source_member(path, selected["member"]) as stream:
        metadata = O.W.read_serialized(stream)
        obj = next(row for row in metadata["objects"] if row["path_id"] == selected["path_id"])
        typ = metadata["types"][obj["type_id"]]
        if typ["class_id"] != 48:
            raise ValueError("Shader context requires original Shader metadata")
        stream.seek(metadata["data_offset"] + obj["offset"])
        body = O.B.exact(stream, obj["bytes"])
    if hashlib.sha256(body).hexdigest() != selected["body_sha256"]:
        raise ValueError("Original Shader context body drift")
    return body, A.SCHEMA.type_tree(io.BytesIO(typ["tree"]))


def produce(profile_path, profile_pin, pc, sdk, asset_ripper, provider, provider_pin, output):
    profile_path, pc, sdk, provider = (Path(p).resolve(strict=True) for p in (profile_path, pc, sdk, provider))
    P.checked(profile_path, {"bytes": profile_path.stat().st_size, "sha256": profile_pin})
    profile = json.loads(profile_path.read_text())
    if profile["input_id"] != A.M.INPUT_ID:
        raise ValueError("Shader context original input differs")
    required_sdk = {"MacOS/Unity", "Tools/UnityShaderCompiler"}
    if any(row["kind"] == "sdk" for row in profile["records"]):
        required_sdk.add("Resources/unity_builtin_extra")
    if not required_sdk <= profile["sdk"].keys():
        raise ValueError("Shader context SDK providers must be explicitly pinned")
    output = Path(output).absolute()
    roots = [pc, sdk, provider, profile_path]
    if asset_ripper is not None:
        asset_ripper = Path(asset_ripper).resolve(strict=True)
        roots.append(asset_ripper)
    output = output.parent.resolve(strict=True) / output.name
    if output.exists() or output.is_symlink() or any(output.is_relative_to(p) or p.is_relative_to(output) for p in roots):
        raise ValueError("Shader context output must be new and disjoint")
    pins = [(profile_path, {"bytes": profile_path.stat().st_size, "sha256": profile_pin})]
    pins.extend((P.relative(sdk, name), pin) for name, pin in profile["sdk"].items())
    for path, pin in pins:
        P.checked(path, pin)
    inventory, common = P.includes(sdk / "CGIncludes")
    if inventory != profile["includes_sha256"]:
        raise ValueError("Shader context common includes drift")
    _, root = checked_original(pc, profile["source_type"])
    selections = {}
    for row in profile["records"]:
        selections.setdefault(row["source_record"]["member"], []).append(
            {"path_id": row["source_record"]["path_id"], "record": profile["provider_profile_sha256"]}
        )
    packed, providers = O.record_packs(
        [{"name": name, "objects": objects} for name, objects in selections.items()],
        [(provider, provider_pin)],
        {"name": profile["provider_bundle"]},
    )
    templates = {}
    if any(row["kind"] == "dummy" for row in profile["records"]):
        if asset_ripper is None:
            raise ValueError("Dummy context requires explicit public template source")
        for name, pin in profile["template_inputs"].items():
            raw = subprocess.check_output(
                ["git", "-C", str(asset_ripper), "show", profile["exporter_revision"] + ":Source/AssetRipper.Export.UnityProjects/Shaders/Templates/" + name]
            )
            if len(raw) != pin["bytes"] or hashlib.sha256(raw).hexdigest() != pin["sha256"]:
                raise ValueError("Shader context public template drift")
            templates[name] = raw.decode().replace("\r", "")
    repo = HERE.parents[2]
    compiler = P.module("_context_compiler", repo / "tools/phone-build/owner-code/shader.py")
    sys.path.insert(0, str(repo / "scripts/lab"))
    sources = P.module("_context_dummy_source", repo / "scripts/lab/shader_source.py")
    image = (sdk / "MacOS/Unity").read_bytes()
    output.mkdir()
    started = time.monotonic()
    receipt = {
        "success": False,
        "input_id": A.M.INPUT_ID,
        "profile_sha256": profile_pin,
        "provider_receipt_sha256": provider_pin,
        "compile_requests": 0,
        "objects": 0,
        "object_bytes": 0,
    }
    try:
        with (
            compiler.compiler([sdk / "Tools/UnityShaderCompiler"], sdk, output / "compiler-metadata", includes=[sdk / "CGIncludes"]) as connection,
            (output / "objects.bin").open("xb") as data,
            (output / "index.jsonl").open("x") as index,
        ):
            for selected in profile["records"]:
                identity = selected["source_record"]
                directory, record = packed[identity["member"], identity["path_id"]]
                if any(record[k] != identity[k] for k in ("bytes", "sha256")):
                    raise ValueError("Shader context source record drift")
                body = O.record_extent(directory / "objects.bin", record)
                needed = key_spans(body, root)
                snippets = {}
                if selected["kind"] == "sdk":
                    sdk_source = SDK.sdk_source(sdk, selected["sdk_shader"], profile["sdk"]["Resources/unity_builtin_extra"]["sha256"])
                    for ident, snippet in sdk_source["m_CompileInfo"]["m_Snippets"]:
                        if ident in needed:
                            ih = bytes(snippet["m_IncludesHash"][f"bytes[{i}]"] for i in range(16))
                            snippets[ident] = {"source": snippet["m_Code"], "fields": [0] * 6 + list(struct.unpack("<4i", ih))}
                elif selected["kind"] == "dummy":
                    checked_original(pc, selected["original"])
                    import UnityPy

                    obj = next(
                        obj
                        for obj in UnityPy.load(str(P.relative(pc, selected["original"]["path"]))).objects
                        if obj.assets_file.name == selected["original"]["member"] and obj.path_id == selected["original"]["path_id"]
                    )
                    text, template = sources.dummy_shader_source(obj.read_typetree()["m_ParsedForm"], templates)
                    if template != selected["template"]:
                        raise ValueError("Shader context dummy template selection differs")
                    pre = connection.preprocess(
                        text,
                        selected["source_filename"],
                        platform_keywords=["SHADER_API_MOBILE"],
                        caching_preprocessor=profile["settings"]["caching_preprocessor"],
                    )
                    if not pre["success"]:
                        raise ValueError("Shader context source preprocessing failed")
                    snippets = {row["fields"][0]: row for row in pre["snippets"] if row["fields"][0] in needed}
                else:
                    raise ValueError("Unknown Shader context source kind")
                keys = {ident: P.editor_hash(snippet, image, connection.capabilities, profile["settings"], common) for ident, snippet in snippets.items()}
                made = replace_keys(body, root, keys)
                for target in selected["outputs"]:
                    result = O.remap(made, target.get("references", []))
                    if len(result) != target["bytes"] or hashlib.sha256(result).hexdigest() != target["sha256"]:
                        raise ValueError("Shader context record differs from accepted hash")
                    row = {key: target[key] for key in ("bundle", "member", "path_id", "bytes", "sha256")}
                    row["offset"] = data.tell()
                    data.write(result)
                    index.write(json.dumps(row, sort_keys=True) + "\n")
                    receipt["objects"] += 1
                    receipt["object_bytes"] += len(result)
        with (output / "index.jsonl").open() as index:
            for row in map(json.loads, index):
                O.record_extent(output / "objects.bin", row)
        for path, pin in pins:
            P.checked(path, pin)
        checked_original(pc, profile["source_type"])
        for selected in profile["records"]:
            if selected["kind"] == "dummy":
                checked_original(pc, selected["original"])
        O.check_record_packs(providers)
        if P.includes(sdk / "CGIncludes")[0] != inventory:
            raise ValueError("Shader context common includes changed")
        receipt.update(
            success=True, outputs={name: {"bytes": (output / name).stat().st_size, "sha256": P.sha(output / name)} for name in ("objects.bin", "index.jsonl")}
        )
        return receipt
    except Exception as error:
        receipt["error"] = type(error).__name__ + ": " + str(error)
        raise
    finally:
        receipt["seconds"] = time.monotonic() - started
        (output / "result.json").write_text(json.dumps(receipt, indent=2) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--profile-sha256", required=True)
    parser.add_argument("--pc-root", type=Path, required=True)
    parser.add_argument("--sdk", type=Path, required=True)
    parser.add_argument("--asset-ripper", type=Path)
    parser.add_argument("--record-pack", type=Path, required=True)
    parser.add_argument("--receipt-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(produce(args.profile, args.profile_sha256, args.pc_root, args.sdk, args.asset_ripper, args.record_pack, args.receipt_sha256, args.output)))


if __name__ == "__main__":
    main()
