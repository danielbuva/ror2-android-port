"""Read-only Steam-update comparison; never accepts or transforms unknown input."""

from common import *
from collections import Counter


def compare_surfaces(before, after):
    old, new = ({x["file"]: x for x in rows} for rows in (before, after))
    result = {"added_assemblies": sorted(new.keys() - old.keys()), "removed_assemblies": sorted(old.keys() - new.keys()), "assemblies": []}
    for name in sorted(old.keys() & new.keys()):
        a, b = old[name], new[name]
        left, right = ({t["name"]: t for t in row["surface"]["types"]} for row in (a, b))
        row = dict(
            file=name,
            same_bytes=a["sha256"] == b["sha256"],
            same_identity=a["surface"]["name"] == b["surface"]["name"],
            added_types=sorted(right.keys() - left.keys()),
            removed_types=sorted(left.keys() - right.keys()),
            changed_type_contracts=[],
            changed_field_order=[],
            added_fields=[],
            removed_fields=[],
            changed_fields=[],
            added_methods=[],
            removed_methods=[],
            changed_method_contracts=[],
            changed_method_bodies=[],
            unchanged_method_bodies=0,
            old_references=a["surface"]["references"],
            new_references=b["surface"]["references"],
        )
        for typename in sorted(left.keys() & right.keys()):
            x, y = left[typename], right[typename]
            if x["contract"] != y["contract"]:
                row["changed_type_contracts"].append(typename)
            if x["fieldOrder"] != y["fieldOrder"]:
                row["changed_field_order"].append(typename)
            fields_a, fields_b = ({f["name"]: f for f in t["fields"]} for t in (x, y))
            row["added_fields"] += [typename + "::" + n for n in sorted(fields_b.keys() - fields_a.keys())]
            row["removed_fields"] += [typename + "::" + n for n in sorted(fields_a.keys() - fields_b.keys())]
            row["changed_fields"] += [typename + "::" + n for n in sorted(fields_a.keys() & fields_b.keys()) if fields_a[n] != fields_b[n]]
            methods_a, methods_b = ({m["name"]: m for m in t["methods"]} for t in (x, y))
            row["added_methods"] += sorted(methods_b.keys() - methods_a.keys())
            row["removed_methods"] += sorted(methods_a.keys() - methods_b.keys())
            for method in sorted(methods_a.keys() & methods_b.keys()):
                u, v = methods_a[method], methods_b[method]
                if u["contract"] != v["contract"]:
                    row["changed_method_contracts"].append(method)
                if u["body"] != v["body"]:
                    row["changed_method_bodies"].append(method)
                else:
                    row["unchanged_method_bodies"] += 1
        result["assemblies"].append(row)
    return result


def guard_comparison(before, after, receipt):
    def methods(rows):
        asm = next(x for x in rows if x["file"] == "RoR2.dll")
        return {m["name"]: m for t in asm["surface"]["types"] for m in t["methods"]}

    a, b = methods(before), methods(after)
    return [
        dict(
            method=name,
            old_exists=name in a,
            new_exists=name in b,
            same_contract=name in a and name in b and a[name]["contract"] == b[name]["contract"],
            same_body=name in a and name in b and a[name]["body"] == b[name]["body"],
        )
        for name in receipt["methods"]
    ]


def check_update():
    from inventory import inspect
    from boundaries import probe_tool

    preserved = read(WORK / "inputs/latest-preserved.json")
    baseline = Path(preserved["path"])
    receipt = read(baseline / "receipt.json")
    if not receipt["success"] or receipt["input_id"] != preserved["input_id"]:
        raise RuntimeError("Verified preserved Steam input required")
    out = WORK / "experiments/input-migration" / now()
    out.mkdir(parents=True)
    # Use a separate inventory: accepted files, reconstruction selection and live
    # lab project must remain attributable to their existing input generation.
    original_acceptance = sha(WORK / "config/accepted-input.json")
    original_inventory = sha(WORK / "inventory/files.json")
    inspect(full=True, base=game(), out=out / "inventory")
    new_inventory = read(out / "inventory/files.json")
    old_inventory = read(baseline / "metadata/files.json")
    a, b = ({x["path"]: x for x in r["files"]} for r in (old_inventory, new_inventory))
    changed = [n for n in sorted(a.keys() & b.keys()) if a[n]["sha256"] != b[n]["sha256"]]
    command = probe_tool()
    surfaces = []
    for folder, name, expected in [(Path(receipt["game_path"]), "baseline", a), (game(), "update", b)]:
        output = out / (name + "-surface.json")
        output.write_bytes(run(command + ["--migration-surface", folder / "Risk of Rain 2_Data/Managed"], timeout=180).stdout)
        rows = read(output)
        for row in rows:
            path = "Risk of Rain 2_Data/Managed/" + row["file"]
            if path not in expected or row["sha256"] != expected[path]["sha256"]:
                raise RuntimeError("Managed input changed during review: " + path)
        surfaces.append(rows)
    comparison = compare_surfaces(*surfaces)
    write(out / "managed-comparison.json", comparison)
    # This receipt identifies the exact optional transformations used by the
    # retained integrated composition, rather than all changed game methods.
    guards = WORK / "experiments/scene-runtime/20261008T163328.528634Z/optional-presentation-transformation.json"
    guard_rows = guard_comparison(*surfaces, read(guards))
    write(out / "optional-guard-comparison.json", guard_rows)
    native_old = {x["path"]: x for x in read(baseline / "metadata/native.json")}
    native_new = {x["path"]: x for x in read(out / "inventory/native.json")}
    middleware = [
        dict(
            path=n,
            same_bytes=n in a and n in b and a[n]["sha256"] == b[n]["sha256"],
            old_versions=native_old.get(n, {}).get("versions"),
            new_versions=native_new.get(n, {}).get("versions"),
        )
        for n in sorted(a.keys() | b.keys())
        if any(k in n.lower() for k in ("rewired", "burst", "collection", "wwise", "aksound")) and n.lower().endswith(".dll")
    ]
    write(out / "middleware-comparison.json", middleware)
    # Reject concurrent Steam writes; do not bless a mixture of depot generations.
    live = {str(p.relative_to(game())): (p.stat().st_size, p.stat().st_mtime_ns) for p in game().rglob("*") if p.is_file()}
    recorded = {r["path"]: (r["size"], r["mtime_ns"]) for r in new_inventory["files"]}
    if live != recorded:
        raise RuntimeError("Steam files changed during migration review; wait for update completion")
    if original_acceptance != sha(WORK / "config/accepted-input.json") or original_inventory != sha(WORK / "inventory/files.json"):
        raise RuntimeError("Read-only migration review changed accepted selection")
    ror2 = next(x for x in comparison["assemblies"] if x["file"] == "RoR2.dll")
    summary = dict(
        success=True,
        scope="Read-only compatibility review; no input acceptance, transformations or device changes",
        old_input=receipt["input_id"],
        new_input=new_inventory["input_id"],
        old_build=old_inventory["steam"]["buildid"],
        new_build=new_inventory["steam"]["buildid"],
        old_unity=old_inventory["unity_versions"],
        new_unity=new_inventory["unity_versions"],
        added_files=len(b.keys() - a.keys()),
        removed_files=len(a.keys() - b.keys()),
        changed_files=len(changed),
        changed_categories=dict(Counter(b[n]["category"] for n in changed)),
        added_assemblies=comparison["added_assemblies"],
        removed_assemblies=comparison["removed_assemblies"],
        exact_assemblies=sum(x["same_bytes"] for x in comparison["assemblies"]),
        game_changes={k: len(ror2[k]) for k in ("added_types", "removed_types", "changed_fields", "added_methods", "removed_methods", "changed_method_bodies")},
        unchanged_optional_guards=sum(x["same_contract"] and x["same_body"] for x in guard_rows),
        optional_guards=len(guard_rows),
        editor_pin_matches=new_inventory["unity_versions"] == [toolchain()["unity_version"]],
        tool_sources={p.name: sha(p) for p in [ROOT / "tools/assembly-transforms/MigrationSurface.cs", Path(__file__)]},
    )
    write(out / "result.json", summary)
    write(out.parent / "latest.json", dict(path=str(out.relative_to(ROOT)), success=True))
    print(json.dumps(summary, indent=2))
