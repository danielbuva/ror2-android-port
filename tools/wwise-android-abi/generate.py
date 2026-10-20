#!/usr/bin/env python3
"""Host-only, exact-input Wwise Android ABI candidate generator.

The accepted game install is read-only. All plans and candidates must be new
files under ignored work/. No project, editor, device, or build operation occurs.
"""

from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
WORK = ROOT / "work"
POLICY_PATH = ROOT / "recipe/wwise-android-abi.json"
POLICY = json.loads(POLICY_PATH.read_text())
ANDROID_DECL_SHA = POLICY["official_android_declaration_source_sha256"]
OUTPUT_BASENAME = re.compile(r"[a-z0-9][a-z0-9_-]*(?:\.[a-z0-9][a-z0-9_-]*)*\Z")


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda: f.read(1024 * 1024), b""):
            h.update(b)
    return h.hexdigest()


def require(ok: bool, msg: str) -> None:
    if not ok:
        raise ValueError(msg)


def validate_output_basename(path: Path) -> None:
    """Limit artifacts to portable lowercase ASCII names before input work."""
    name = path.name
    require(
        len(name) <= 128 and OUTPUT_BASENAME.fullmatch(name) is not None,
        "output basename must be 1-128 lowercase ASCII artifact characters; use dot-separated lowercase alphanumeric segments with internal '-' or '_'",
    )


def accepted_managed_input() -> tuple[Path, Path, str]:
    accepted = json.loads((WORK / "config/accepted-input.json").read_text())
    inventory = json.loads((WORK / "inventory/files.json").read_text())
    recipe = json.loads((ROOT / "recipe/original-assemblies.json").read_text())
    input_id = accepted.get("input_id")
    require(isinstance(input_id, str) and re.fullmatch(r"[0-9a-f]{64}", input_id) is not None, "invalid accepted input identity")
    require(inventory.get("input_id") == input_id and recipe.get("input_id") == input_id, "accepted input, inventory, and assembly recipe disagree")
    row = [x for x in recipe.get("assemblies", []) if x.get("source") == "AK.Wwise.Unity.API.dll"]
    require(len(row) == 1 and row[0].get("sha256") == POLICY["retained_managed_sha256"], "accepted assembly recipe does not match this reviewed API")
    record = [x for x in inventory.get("files", []) if x.get("path") == "Risk of Rain 2_Data/Managed/AK.Wwise.Unity.API.dll"]
    require(len(record) == 1 and record[0].get("sha256") == row[0]["sha256"], "accepted inventory has no unique matching Wwise API record")
    local = json.loads((WORK / "config/local.json").read_text())
    configured = Path(local["game_path"]).expanduser().resolve(strict=True)
    source = configured / "Risk of Rain 2_Data/Managed/AK.Wwise.Unity.API.dll"
    require(source.is_file() and not source.is_symlink(), "configured accepted Wwise API is missing or symlinked")
    require(sha(source) == row[0]["sha256"], "configured accepted Wwise API hash mismatch")
    return source, configured, input_id


def assert_output_path(path: Path, game_root: Path) -> Path:
    raw = Path(os.path.abspath(path.expanduser()))
    require(not raw.exists() and not raw.is_symlink(), "refusing to overwrite or follow output")
    # Reject any symlink component, even if it eventually resolves inside work.
    cur = raw
    while cur != cur.parent:
        require(not cur.is_symlink(), "output path contains a symlink")
        cur = cur.parent
    resolved_parent = raw.parent.resolve(strict=True)
    dest = resolved_parent / raw.name
    require(dest.is_relative_to(WORK.resolve()) and dest != WORK.resolve(), "new output must be inside this repository's ignored work/")
    require(not dest.is_relative_to(game_root), "output cannot be inside the accepted game installation")
    require(raw.parent == resolved_parent, "output parent may not traverse symlinks")
    check = subprocess.run(["git", "check-ignore", "--quiet", str(dest)], cwd=ROOT)
    require(check.returncode == 0, "output path is not ignored by Git")
    return dest


def assert_distinct_outputs(output: Path, candidate: Path | None) -> None:
    """Refuse filesystem-equivalent destinations before publishing either file."""
    if candidate is None:
        return
    try:
        same_parent = os.path.samefile(output.parent, candidate.parent)
    except OSError as exc:
        raise ValueError("unable to establish whether output parent directories alias") from exc
    if not same_parent:
        return
    # validate_output_basename() only permits lowercase ASCII names, so equal
    # leaves are the only possible case/normalization-equivalent names here.
    require(output.name != candidate.name, "plan and candidate output paths must be distinct on this filesystem")


def discover_dotnet(explicit: Path | None) -> Path:
    candidate = explicit or (Path(shutil.which("dotnet")) if shutil.which("dotnet") else None)
    if candidate is None or not candidate.is_file():
        raise ValueError("dotnet not found; source scripts/env.sh or pass --dotnet")
    return candidate.resolve(strict=True)


def discover_cecil(explicit: Path | None) -> Path:
    if explicit is not None:
        candidate = explicit
    elif os.environ.get("WWISE_CECIL"):
        candidate = Path(os.environ["WWISE_CECIL"])
    elif os.environ.get("UNITY_EDITOR"):
        editor = Path(os.environ["UNITY_EDITOR"]).resolve(strict=True)
        gac = editor.parent.parent / "MonoBleedingEdge/lib/mono/gac/Mono.Cecil"
        candidates = sorted(gac.glob("*__*/Mono.Cecil.dll"))
        if len(candidates) != 1:
            raise ValueError("could not resolve one bundled Mono.Cecil from UNITY_EDITOR; pass --cecil")
        candidate = candidates[0]
    else:
        raise ValueError("Mono.Cecil not found; source scripts/env.sh or pass --cecil")
    require(candidate.is_file(), "selected Mono.Cecil assembly is missing")
    return candidate.resolve(strict=True)


def split_top(text: str, delim=",") -> list[str]:
    out = []
    start = 0
    depth = 0
    bracket = 0
    for i, ch in enumerate(text):
        if ch in "(<[":
            depth += 1
        elif ch in ")>]":
            depth -= 1
        elif ch == delim and depth == 0:
            out.append(text[start:i].strip())
            start = i + 1
        if depth < 0:
            raise ValueError("unbalanced declaration")
    if depth != 0:
        raise ValueError("unbalanced declaration")
    tail = text[start:].strip()
    if tail:
        out.append(tail)
    return out


def norm_type(raw: str) -> str:
    x = re.sub(r"\s+", "", raw).replace("global::", "")
    aliases = {
        "System.Void": "void",
        "System.Boolean": "bool",
        "System.Byte": "byte",
        "System.SByte": "sbyte",
        "System.Int16": "short",
        "System.UInt16": "ushort",
        "System.Int32": "int",
        "System.UInt32": "uint",
        "System.Int64": "long",
        "System.UInt64": "ulong",
        "System.Single": "float",
        "System.Double": "double",
        "System.String": "string",
        "System.IntPtr": "IntPtr",
        "System.UIntPtr": "UIntPtr",
    }
    for a, b in aliases.items():
        x = x.replace(a, b)
    return x.replace("/", ".")


def source_options(raw: str) -> dict:
    items = split_top(raw)
    require(bool(items) and items[0].startswith('"') and items[0].endswith('"'), "unrecognized DllImport library")
    library = items[0].strip('"')
    kv = {}
    for item in items[1:]:
        if "=" not in item:
            raise ValueError("unrecognized DllImport option")
        k, v = [x.strip() for x in item.split("=", 1)]
        if k not in {"EntryPoint", "CharSet", "ExactSpelling", "SetLastError", "CallingConvention", "BestFitMapping", "ThrowOnUnmappableChar"}:
            raise ValueError("unsupported DllImport option: " + k)
        kv[k] = v.strip('"')
    for key in ("ExactSpelling", "SetLastError", "BestFitMapping", "ThrowOnUnmappableChar"):
        if key in kv and kv[key].lower() not in {"true", "false"}:
            raise ValueError("unsupported Boolean DllImport option: " + key)
    require("EntryPoint" in kv, "Android declaration has no explicit EntryPoint")
    charset = {"CharSet.None": "default", "CharSet.Ansi": "Ansi", "CharSet.Unicode": "Unicode", "CharSet.Auto": "Auto"}
    conv = {
        "CallingConvention.Winapi": "default",
        "CallingConvention.Cdecl": "Cdecl",
        "CallingConvention.StdCall": "StdCall",
        "CallingConvention.ThisCall": "ThisCall",
        "CallingConvention.FastCall": "FastCall",
    }
    bestfit = {"true": "enabled", "false": "disabled"}
    unmappable = {"true": "enabled", "false": "disabled"}
    charset_value = charset.get(kv.get("CharSet", "CharSet.None"), "UNKNOWN")
    convention_value = conv.get(kv.get("CallingConvention", "CallingConvention.Winapi"), "UNKNOWN")
    bestfit_value = bestfit.get(kv.get("BestFitMapping", "").lower(), "default")
    unmappable_value = unmappable.get(kv.get("ThrowOnUnmappableChar", "").lower(), "default")
    exact = kv.get("ExactSpelling", "false").lower() == "true"
    last_error = kv.get("SetLastError", "false").lower() == "true"
    # ECMA-335 P/Invoke flags as represented by the pinned Cecil profile.
    raw_flags = {"Ansi": 2, "Unicode": 4, "Auto": 6}.get(charset_value, 0)
    raw_flags |= {"Cdecl": 512, "StdCall": 768, "ThisCall": 1024, "FastCall": 1280}.get(convention_value, 256)
    raw_flags |= {"enabled": 16, "disabled": 32}.get(bestfit_value, 0)
    raw_flags |= {"enabled": 4096, "disabled": 8192}.get(unmappable_value, 0)
    raw_flags |= (1 if exact else 0) | (64 if last_error else 0)
    return {
        "library": library,
        "entrypoint": kv["EntryPoint"],
        "charset": charset_value,
        "calling_convention": convention_value,
        "best_fit_mapping": bestfit_value,
        "throw_on_unmappable_char": unmappable_value,
        "raw_pinvoke_flags": raw_flags,
        "exact_spelling": "true" if exact else "default",
        "set_last_error": "true" if last_error else "default",
    }


def parse_android_source(path: Path) -> list[dict]:
    src = path.read_text(encoding="utf-8-sig")
    pattern = re.compile(
        r"((?:\s*\[[^\]]*\]\s*)*)\[global::System\.Runtime\.InteropServices\.DllImport\((.*?)\)\]\s*public\s+static\s+extern\s+([^\s]+)\s+(\w+)\((.*?)\);", re.S
    )
    result = []
    for m in pattern.finditer(src):
        # C# source cannot provide raw metadata blobs for arbitrary attributes.
        # Refuse any extra method/return-target attribute rather than assuming
        # that the Android declaration has the same metadata payload.
        if m.group(1).strip():
            raise ValueError("unsupported extra Android method/return custom attribute")
        options = source_options(m.group(2))
        ret = norm_type(m.group(3))
        name = m.group(4)
        args = []
        for raw in split_top(m.group(5)):
            attrs = []
            am = re.match(r"\[(.*?)\]\s*(.*)$", raw)
            if am:
                attrs = [x.strip() for x in split_top(am.group(1))]
                raw = am.group(2)
            mar = []
            flags = []
            for a in attrs:
                if a.endswith(".In"):
                    flags.append("In")
                elif a.endswith(".Out"):
                    flags.append("Out")
                else:
                    mm = re.fullmatch(
                        r"global::System\.Runtime\.InteropServices\.MarshalAs\(global::System\.Runtime\.InteropServices\.UnmanagedType\.(\w+)\)", a
                    )
                    if not mm:
                        raise ValueError("unsupported Android parameter attribute")
                    mar = [mm.group(1)]
            direction = "value"
            for mod in ("ref", "out", "in"):
                if raw.startswith(mod + " "):
                    direction = mod
                    raw = raw[len(mod) :].strip()
                    break
            if direction == "in":
                flags.append("In")
            if direction == "out":
                flags.append("Out")
            tm = re.fullmatch(r"(.+?)\s+\w+", raw)
            if not tm:
                raise ValueError("unparsed Android parameter declaration")
            typ = norm_type(tm.group(1))
            # C# source maps the native array marshal kind, but not non-default
            # size/subtype metadata; this generator accepts only the default form.
            if mar == ["LPArray"]:
                marshal = "LPArray"
            else:
                marshal = mar[0] if mar else None
            param_flags = set(flags)
            if mar:
                param_flags.add("HasFieldMarshal")
            args.append({"type": typ, "direction": direction, "marshal": marshal, "attributes": sorted(param_flags), "custom_attributes": []})
        result.append(
            {
                **options,
                "name": name,
                "return": ret,
                "return_marshal": None,
                "return_attributes": "None",
                "method_custom_attributes": [],
                "return_custom_attributes": [],
                "args": args,
            }
        )
    require(len(result) == 1280, f"unexpected official Android import count: {len(result)}")
    require(len({r["entrypoint"] for r in result}) == len(result), "duplicate Android entrypoint")
    return result


def native_exports(nm: Path, so: Path) -> set[str]:
    run = subprocess.run([str(nm), "-D", "--defined-only", str(so)], check=True, text=True, capture_output=True)
    return {line.split()[-1].split("@")[0] for line in run.stdout.splitlines() if line.split()}


def native_shape(info: dict) -> dict:
    def mar(v):
        if v is None:
            return None
        props = v["properties"]
        native = props.get("NativeType")
        if v["kind"] == "MarshalInfo":
            return native
        if v["kind"] == "ArrayMarshalInfo":
            expected = {"ElementType": "Max", "NativeType": "Array", "Size": "-1", "SizeParameterIndex": "-1", "SizeParameterMultiplier": "-1"}
            require(props == expected, "non-default array MarshalInfo is not supported by source parser")
            return "LPArray"
        raise ValueError("unsupported native marshal metadata")

    args = []
    for p in info["parameters"]:
        rawtype = p["type"]
        if rawtype.endswith("&"):
            rawtype = rawtype[:-1]
        flags = set(filter(lambda x: x and x != "None", p["attributes"].replace(" ", "").split(",")))
        args.append(
            {
                "type": rawtype,
                "direction": p["direction"],
                "marshal": mar(p["marshal"]),
                "attributes": sorted(flags),
                "custom_attributes": p["customAttributes"],
            }
        )
    return {
        "library": info["library"],
        "entrypoint": info["entrypoint"],
        "charset": info["charset"],
        "calling_convention": info["calling_convention"],
        "exact_spelling": "true" if info["exact_spelling"] else "default",
        "best_fit_mapping": info["best_fit_mapping"],
        "throw_on_unmappable_char": info["throw_on_unmappable_char"],
        "raw_pinvoke_flags": info["raw_pinvoke_flags"],
        "set_last_error": "true" if info["set_last_error"] else "default",
        "return": info["return_type"],
        "return_marshal": mar(info["return_marshal"]),
        "return_attributes": info["return_attributes"],
        "method_custom_attributes": info["method_custom_attributes"],
        "return_custom_attributes": info["return_custom_attributes"],
        "args": args,
    }


def compatible(game: dict, android: dict) -> tuple[bool, list[int]]:
    for k in (
        "library",
        "charset",
        "calling_convention",
        "best_fit_mapping",
        "throw_on_unmappable_char",
        "raw_pinvoke_flags",
        "exact_spelling",
        "set_last_error",
        "return",
        "return_marshal",
        "return_attributes",
        "method_custom_attributes",
        "return_custom_attributes",
    ):
        if game[k] != android[k]:
            return False, []
    if len(game["args"]) != len(android["args"]):
        return False, []
    changes = []
    for i, (g, a) in enumerate(zip(game["args"], android["args"])):
        if (g["type"], g["direction"], g["attributes"], g["custom_attributes"]) != (a["type"], a["direction"], a["attributes"], a["custom_attributes"]):
            return False, []
        if g["marshal"] == a["marshal"]:
            continue
        if g["type"] == "string" and g["marshal"] == "LPWStr" and a["marshal"] == "LPStr":
            changes.append(i)
        else:
            return False, []
    return True, changes


def plan_shape(x: dict) -> dict:
    return {
        "entrypoint": x["entrypoint"],
        "library": x["library"],
        "calling_convention": x["calling_convention"],
        "charset": x["charset"],
        "best_fit_mapping": x["best_fit_mapping"],
        "throw_on_unmappable_char": x["throw_on_unmappable_char"],
        "raw_pinvoke_flags": x["raw_pinvoke_flags"],
        "exact_spelling": x["exact_spelling"],
        "set_last_error": x["set_last_error"],
        "return": x["return"],
        "return_attributes": x["return_attributes"],
        "method_custom_attributes": x["method_custom_attributes"],
        "return_custom_attributes": x["return_custom_attributes"],
        "return_marshal": [] if x["return_marshal"] is None else ["UnmanagedType." + x["return_marshal"]],
        "args": [
            {
                "type": a["type"],
                "direction": a["direction"],
                "marshal": [] if a["marshal"] is None else ["UnmanagedType." + a["marshal"]],
                "attributes": a["attributes"],
                "custom_attributes": a["custom_attributes"],
            }
            for a in x["args"]
        ],
    }


def stem(name: str) -> str:
    return re.sub(r"__SWIG_\d+$", "", name)


def derive_plan(original: dict, android_rows: list[dict], exports: set[str]) -> dict:
    source_rows = [native_shape(row) for row in original["imports"]]
    mapped = []
    unavailable = []
    remaps = []
    rewrites = []
    android_by_stem = {}
    for row in android_rows:
        android_by_stem.setdefault(stem(row["entrypoint"]), []).append(row)
    for game in source_rows:
        candidates = android_by_stem.get(stem(game["entrypoint"]), [])
        exact_name = [x for x in candidates if x["entrypoint"] == game["entrypoint"]]
        same_name_matches = []
        for target in exact_name:
            ok, changes = compatible(game, target)
            if ok:
                same_name_matches.append((target, changes))
        if len(same_name_matches) > 1:
            raise ValueError("duplicate exact-name Android ABI match: " + game["entrypoint"])
        matches = same_name_matches
        if not matches:
            matches = []
            for target in candidates:
                if target["entrypoint"] == game["entrypoint"]:
                    continue
                ok, changes = compatible(game, target)
                if ok:
                    matches.append((target, changes))
        if len(matches) > 1:
            raise ValueError("ambiguous Android ABI match: " + game["entrypoint"])
        if not matches:
            if candidates:
                raise ValueError("same-family Android ABI mismatch; refusing: " + game["entrypoint"])
            unavailable.append({"entrypoint": game["entrypoint"], "reason": "no_verified_android_counterpart", "game": plan_shape(game)})
            continue
        target, changes = matches[0]
        if target["entrypoint"] not in exports:
            raise ValueError("matched target absent from native exports")
        if target["entrypoint"] != game["entrypoint"]:
            remaps.append({"source": game["entrypoint"], "target": target["entrypoint"]})
        if changes:
            rewrites.append({"entrypoint": game["entrypoint"], "parameter_indices": changes})
        g = plan_shape(game)
        a = plan_shape(target)
        mapped.append(
            {"source_entrypoint": game["entrypoint"], "target_entrypoint": target["entrypoint"], "parameter_lpstr_indices": changes, "game": g, "android": a}
        )
    if (
        len(source_rows) != 1280
        or len(mapped) != 1269
        or len(unavailable) != 11
        or len(remaps) != 28
        or len(rewrites) != 84
        or sum(len(x["parameter_indices"]) for x in rewrites) != 88
    ):
        raise ValueError("derived ABI totals differ from the reviewed exact-input profile")
    if sorted(remaps, key=lambda x: x["source"]) != sorted(POLICY["entrypoint_remaps"], key=lambda x: x["source"]):
        raise ValueError("derived entrypoint remaps differ from reviewed profile")
    if sorted(rewrites, key=lambda x: x["entrypoint"]) != sorted(POLICY["lpwstr_to_lpstr"], key=lambda x: x["entrypoint"]):
        raise ValueError("derived LPWStr indices differ from reviewed profile")
    names = sorted(x["entrypoint"] for x in unavailable)
    if names != sorted(POLICY["unavailable"]):
        raise ValueError("unavailable set differs from reviewed profile")
    if not set(x["target_entrypoint"] for x in mapped) <= exports:
        raise ValueError("mapped target missing from native export set")
    if set(names) & exports:
        raise ValueError("unavailable entrypoint unexpectedly exported")
    return {
        "schema": 1,
        "status": "draft_incomplete_android_candidate",
        "full_enable_ready": False,
        "input_assembly_sha256": original["sha256"],
        "counts": POLICY["counts"],
        "imports": mapped,
        "unavailable": unavailable,
        "enablement_blockers": [
            "11 imports have no verified Android counterpart",
            "only Android ABI metadata is established",
            "runtime audio readiness has not been established",
        ],
    }


def atomic_new(path: Path, data: bytes) -> None:
    require(not path.exists() and not path.is_symlink(), "refusing to overwrite output")
    with tempfile.NamedTemporaryFile(mode="wb", dir=path.parent, prefix=".wwise-abi-", delete=False) as f:
        temp = Path(f.name)
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    try:
        os.link(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--android-source", required=True, type=Path)
    p.add_argument("--native-so", required=True, type=Path)
    p.add_argument("--llvm-nm", required=True, type=Path)
    p.add_argument("--output", required=True, type=Path)
    p.add_argument("--candidate", type=Path, help="write an optional incomplete ABI candidate; it remains runtime-ineligible")
    p.add_argument("--dotnet", type=Path)
    p.add_argument("--cecil", type=Path)
    args = p.parse_args()
    validate_output_basename(args.output)
    if args.candidate is not None:
        validate_output_basename(args.candidate)
    managed, game_root, input_id = accepted_managed_input()
    output = assert_output_path(args.output, game_root)
    candidate = assert_output_path(args.candidate, game_root) if args.candidate is not None else None
    assert_distinct_outputs(output, candidate)
    require(sha(args.android_source) == ANDROID_DECL_SHA, "official Android declaration source pin mismatch")
    require(sha(args.native_so) == POLICY["android_arm64_release_plugin_sha256"], "official native plugin pin mismatch")
    exports = native_exports(args.llvm_nm, args.native_so)
    export_hash = hashlib.sha256(("\n".join(sorted(exports)) + "\n").encode()).hexdigest()
    require(len(exports) == POLICY["android_arm64_export_count"] and export_hash == POLICY["android_arm64_export_set_sha256"], "native export set pin mismatch")
    android = parse_android_source(args.android_source)
    dotnet = discover_dotnet(args.dotnet)
    cecil = discover_cecil(args.cecil)
    tempdir = tempfile.TemporaryDirectory(prefix="wwise-abi-v6-", dir=WORK)
    build = Path(tempdir.name) / "inspector"
    subprocess.run(
        [
            str(dotnet),
            "build",
            str(HERE / "CecilAbiTool.csproj"),
            "-o",
            str(build),
            "-p:BaseIntermediateOutputPath=" + str(Path(tempdir.name) / "obj-inspector") + os.sep,
            "-p:CecilPath=" + str(cecil),
            "--nologo",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    inspector = build / "CecilAbiTool.dll"
    try:
        inspected = subprocess.run([str(dotnet), str(inspector), "--inspect-pinvoke", str(managed)], check=True, capture_output=True, text=True)
        original = json.loads(inspected.stdout)
        require(original["sha256"] == POLICY["retained_managed_sha256"], "inspected assembly is not the accepted original")
        plan = derive_plan(original, android, exports)
        plan["accepted_input_id"] = input_id
        plan["android_source_sha256"] = sha(args.android_source)
        plan["native_plugin_sha256"] = sha(args.native_so)
        plan["native_export_set_sha256"] = export_hash
        content = (json.dumps(plan, sort_keys=True, indent=2) + "\n").encode()
        if candidate is not None:
            plan_path = Path(tempdir.name) / "plan.json"
            atomic_new(plan_path, content)
            writer_dir = Path(tempdir.name) / "writer"
            subprocess.run(
                [
                    str(dotnet),
                    "build",
                    str(HERE / "CecilAbiWriter.csproj"),
                    "-o",
                    str(writer_dir),
                    "-p:BaseIntermediateOutputPath=" + str(Path(tempdir.name) / "obj-writer") + os.sep,
                    "-p:CecilPath=" + str(cecil),
                    "--nologo",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            subprocess.run(
                [
                    str(dotnet),
                    str(writer_dir / "CecilAbiWriter.dll"),
                    "--emit-incomplete-candidate",
                    str(managed),
                    str(plan_path),
                    str(POLICY_PATH),
                    str(candidate),
                ],
                check=True,
            )
        atomic_new(output, content)
        print(
            json.dumps(
                {
                    "status": plan["status"],
                    "input_id": input_id,
                    "plan_sha256": hashlib.sha256(content).hexdigest(),
                    "counts": plan["counts"],
                    "output_under_ignored_work": True,
                    "candidate_written": candidate is not None,
                    "full_enable_ready": False,
                },
                indent=2,
            )
        )
        return 0
    finally:
        if tempdir:
            tempdir.cleanup()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, KeyError, OSError, subprocess.CalledProcessError) as exc:
        raise SystemExit("refusing Wwise ABI generation: " + str(exc))
