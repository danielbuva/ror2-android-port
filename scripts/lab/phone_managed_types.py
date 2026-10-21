"""Resolve an explicitly selected metadata group; never load inspected assemblies.

This is investigation support, not a scripting runtime or linker-root producer.
Missing forwarding/base dependencies refuse rather than becoming absent types.
"""


class MetadataUniverse:
    def __init__(self, inventory, group):
        if inventory.get("schema") != 2 or inventory.get("executes_inputs") is not False:
            raise ValueError("Expected non-executing scoped metadata schema 2")
        selected = [row for row in inventory["assemblies"] if row["group"] == group]
        if not selected:
            raise ValueError("No assemblies in selected metadata group")
        self.assemblies = {}
        self.names = {}
        self.types = {}
        self.exports = {}
        for row in selected:
            identity = row["assembly_identity"]
            if identity in self.assemblies or row["assembly"] in self.names:
                raise ValueError("Ambiguous assembly in selected metadata group")
            self.assemblies[identity] = row
            self.names[row["assembly"]] = identity
            for values, index in ((row["types"], self.types), (row["exported_types"], self.exports)):
                for item in values:
                    key = (identity, item["name"])
                    if key in self.types or key in self.exports:
                        raise ValueError("Ambiguous type metadata")
                    index[key] = item

    def scope_identity(self, owner, scope):
        if not isinstance(scope, dict):
            raise ValueError("Missing metadata scope")
        identity = scope["assembly_identity"]
        source = self.assemblies[owner]
        if scope["kind"] == "ModuleDefinition":
            if identity != owner or scope["name"] != source["module_name"]:
                raise ValueError("Foreign local-module scope")
        elif scope["kind"] == "AssemblyNameReference":
            if identity not in source["references"]:
                raise ValueError("Undeclared assembly reference")
        else:
            raise ValueError("Unsupported metadata scope")
        if identity not in self.assemblies:
            raise ValueError("Missing exact assembly dependency")
        return identity

    def resolve(self, identity, name):
        """Return a definition and exact forwarding path, or a known absent type.

        Each scope must resolve within this group, including its exact version.
        A caller must explicitly handle a missing assembly separately from a
        missing class; neither short names nor another group fill dependencies.
        """
        trail = []
        seen = set()
        while True:
            if identity not in self.assemblies:
                raise ValueError("Missing exact assembly dependency")
            key = (identity, name)
            if key in seen:
                raise ValueError("Cyclic type forwarding")
            seen.add(key)
            if key in self.types:
                return {"assembly_identity": identity, "name": name, "definition": self.types[key], "forwarders": trail}
            item = self.exports.get(key)
            if item is None:
                if trail:
                    raise ValueError("Forwarded definition is missing")
                return None
            parent = item
            ancestry = set()
            while parent["declaring_type"] is not None:
                parent_name = parent["declaring_type"]
                if parent_name in ancestry or not parent["name"].startswith(parent_name + "/"):
                    raise ValueError("Invalid exported nesting")
                ancestry.add(parent_name)
                parent = self.exports.get((identity, parent_name))
                if parent is None or parent["scope"] != item["scope"]:
                    raise ValueError("Missing or conflicting exported parent")
            if parent["is_forwarder"] is not True or item["scope"]["kind"] != "AssemblyNameReference":
                raise ValueError("Unsupported non-forwarding export")
            trail.append({"assembly_identity": identity, "name": name})
            identity = self.scope_identity(identity, item["scope"])

    def derives_from(self, identity, name, base_identity, base_name):
        """Prove managed inheritance, including forwarding; never infer native bases."""
        target = self.resolve(base_identity, base_name)
        if target is None:
            raise ValueError("Missing base definition")
        target_key = (target["assembly_identity"], target["name"])
        seen = set()
        while True:
            item = self.resolve(identity, name)
            if item is None:
                raise ValueError("Missing inheritance definition")
            key = (item["assembly_identity"], item["name"])
            if key in seen:
                raise ValueError("Cyclic inheritance")
            seen.add(key)
            if key == target_key:
                return True
            definition = item["definition"]
            name = definition["base_type"]
            if name is None:
                return False
            identity = self.scope_identity(item["assembly_identity"], definition["base_scope"])


def inspect_file(metadata, group, output):
    """Qualify every forwarding entry in one explicit, immutable inventory."""
    import hashlib
    import json
    from pathlib import Path

    metadata = Path(metadata)
    data = metadata.read_bytes()
    universe = MetadataUniverse(json.loads(data), group)
    resolved = []
    for identity, name in universe.exports:
        item = universe.resolve(identity, name)
        if item is None:
            raise ValueError("Forwarded definition is missing")
        resolved.append({"from_assembly": identity, "name": name, "to_assembly": item["assembly_identity"], "hops": len(item["forwarders"])})
    result = {
        "schema": 1,
        "executes_inputs": False,
        "root_generation_qualified": False,
        "metadata_sha256": hashlib.sha256(data).hexdigest(),
        "group": group,
        "assemblies": len(universe.assemblies),
        "definitions": len(universe.types),
        "exported_types": len(universe.exports),
        "resolved": resolved,
    }
    if metadata.read_bytes() != data:
        raise ValueError("Metadata input changed during inspection")
    with Path(output).open("x") as stream:
        stream.write(json.dumps(result, indent=2) + "\n")
    return result


if __name__ == "__main__":
    import sys

    if len(sys.argv) != 4:
        raise SystemExit("Expected METADATA.json GROUP NEW_REPORT.json")
    inspect_file(*sys.argv[1:])
