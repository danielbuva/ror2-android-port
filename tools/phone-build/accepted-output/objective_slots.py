"""Join native objective startup failures to the matching signed player's serialized components."""

import argparse
import io
import json
from pathlib import Path
import struct

import catalog_compare as D
import record_produce as R


def fields(catalog, endpoint):
    owner, pid = endpoint
    _, typ, body = catalog.record(owner, (0, pid))
    tree, _ = D.schema(typ["tree"])
    return typ["class_id"], body, tree, D.pointers(body, tree)


class ObjectivePrefabs:
    def __init__(self, catalog):
        self.catalog = catalog
        self.assets = {}
        self.bundle_names = {}
        for bundle, members in catalog.bundles.items():
            if bundle == "@player":
                continue
            for member in members:
                _, layout, objects = catalog.members[member]
                for pid, row in objects.items():
                    if layout["types"][row["type_id"]]["class_id"] != 142:
                        continue
                    _, _, body = catalog.record(member, (0, pid))
                    name = D.C.text(io.BytesIO(body))
                    if bundle in self.bundle_names and self.bundle_names[bundle] != name:
                        raise ValueError("inconsistent AssetBundle name")
                    self.bundle_names[bundle] = name
                    if bundle == "commando-prefab-lab":
                        for asset, fid, root in D.container_table(body)[1]:
                            self.assets.setdefault(asset.lower(), set()).add(catalog.endpoint(member, (fid, root)))

    def endpoint(self, member, pointer):
        owner, row = self.catalog.resolve(member, pointer)
        return owner, row["path_id"]

    def describe(self, member, pointer, loaded):
        owner, pid = self.endpoint(member, pointer)
        bundle = self.catalog.names.get(owner)
        expected = self.bundle_names[bundle] if bundle else "@player"
        return dict(file_id=pointer[0], path_id=pid, member=owner, expected_bundle=expected, bundle_loaded=expected in loaded if bundle else None)

    def slot(self, failure, loaded):
        roots = self.assets.get(failure["asset"].lower(), set())
        if len(roots) != 1:
            raise ValueError("objective prefab container root missing or ambiguous")
        node = next(iter(roots))
        names = []
        route = [int(value) for value in failure["route"].split("/")] if failure["route"] else []
        for depth in range(len(route) + 1):
            owner, _ = node
            cls, body, tree, refs = fields(self.catalog, node)
            if cls != 1:
                raise ValueError("expected GameObject on objective route")
            start, end = R.fields(body, tree)[1][("m_Name",)]
            names.append(D.C.text(io.BytesIO(body[start:end])))
            components = [ptr for key, ptr in refs.items() if key[:2] == ("m_Component", "Array") and key[-1] == "component"]
            if depth == len(route):
                break
            transforms = []
            for ptr in components:
                member, row = self.catalog.resolve(owner, ptr)
                if self.catalog.members[member][1]["types"][row["type_id"]]["class_id"] in (4, 224):
                    transforms.append((member, row["path_id"]))
            if len(transforms) != 1:
                raise ValueError("objective GameObject does not have one Transform")
            transform = transforms[0]
            children = fields(self.catalog, transform)[3]
            index = route[depth]
            child = children.get(("m_Children", "Array", index), children.get(("#83", "Array", index)))
            if child is None:
                raise ValueError("objective sibling index absent")
            child = self.endpoint(transform[0], child)
            child_fields = fields(self.catalog, child)[3]
            node = self.endpoint(child[0], child_fields.get(("m_GameObject",), child_fields.get(("#374",))))
        if "/".join(names) != failure["hierarchy"] or len(components) != failure["componentCount"] or not 0 <= failure["slot"] < len(components):
            raise ValueError("native and serialized objective hierarchy or slots differ")
        pointer = components[failure["slot"]]
        owner, typ, body = self.catalog.record(node[0], pointer)
        result = dict(component=self.describe(node[0], pointer, loaded), class_id=typ["class_id"])
        if typ["class_id"] == 114:
            script = struct.unpack_from("<iq", body, 16)
            result["script"] = self.describe(owner, script, loaded) if any(script) else None
            result["script_identity"] = self.catalog.binding(owner, typ, body)
        return result


def join(catalog_request, run):
    def read(name):
        return json.loads((run / name).read_bytes())

    terminal = read("terminal.done.json")
    selection = read("movement-batch-selection.json")
    launch = read("launch.json")
    start = read("start-menu.json")
    report = read("terminal-capture/movement-batch-" + selection["id"] + ".json")
    for item in (start, report):
        if (
            item["id"] != selection["id"]
            or item["attempt"] != selection["attempt"]
            or str(item["pid"]) != str(launch["pid"])
            or item["session"] != start["session"]
        ):
            raise ValueError("objective report belongs to a different run")
    if not selection.get("diagnosticObjectiveStartup") or not report.get("diagnosticObjectiveStartup"):
        raise ValueError("objective startup diagnostic was not active")
    apk = D.pinned(terminal["apk"], terminal["apk_sha256"])
    if terminal["installed_idle"]["apk_sha256"] != terminal["apk_sha256"]:
        raise ValueError("installed APK differs from terminal receipt")
    paths = D.candidate_paths(json.loads(catalog_request.read_bytes()), apk)
    prefabs = ObjectivePrefabs(D.Catalog(paths, apk))
    diagnostic = report["objectiveStartup"]
    loaded = diagnostic["loadedBundles"]
    result = dict(
        apk_sha256=terminal["apk_sha256"],
        pid=report["pid"],
        attempt=report["attempt"],
        session=report["session"],
        report_id=report["id"],
        actors=diagnostic["actors"],
        loaded_bundles=loaded,
        failures=[],
    )
    for failure in diagnostic["failures"]:
        row = dict(failure)
        if failure["error"] == "Unbound component":
            try:
                row.update(prefabs.slot(failure, loaded))
            except (KeyError, ValueError, IndexError, TypeError, struct.error) as exc:
                row["join_error"] = str(exc)
        result["failures"].append(row)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog-request", type=Path, required=True)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = join(args.catalog_request, args.run)
    with args.output.open("x") as stream:
        json.dump(result, stream, indent=2)
        stream.write("\n")
    raise SystemExit(any("join_error" in row for row in result["failures"]))
