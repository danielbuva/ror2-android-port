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
                    if key in index:
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
            if key in self.types and key in self.exports:
                raise ValueError("Ambiguous type definition and forwarding metadata")
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

    def bind_current_providers(self, providers):
        """Bind every selected module to current, hash-checked provider bytes."""
        import hashlib
        from pathlib import Path

        modules = {}
        for row in self.assemblies.values():
            module = row["module_name"]
            pin = providers.get(module)
            if pin is None or pin["path"] != row["path"] or pin["sha256"] != row["sha256"]:
                raise ValueError("Metadata provider path/hash differs")
            if module in modules:
                raise ValueError("Ambiguous current metadata module")
            if hashlib.sha256(Path(pin["path"]).read_bytes()).hexdigest() != pin["sha256"]:
                raise ValueError("Current CLR provider drift")
            modules[module] = row
        if set(modules) != set(providers):
            raise ValueError("Current metadata provider inventory incomplete")
        self.modules = modules

    def registry(self, identity):
        module, namespace, name = identity
        row = self.modules.get(module)
        if row is None:
            raise ValueError("registry module absent from current providers")
        signature = {
            "kind": "named",
            "name": (namespace + "." if namespace else "") + name.replace("+", "/"),
            "scope": {"kind": "ModuleDefinition", "name": module, "assembly_identity": row["assembly_identity"]},
        }
        self.definition(signature)
        return signature

    def scoped_signature(self, owner, signature, arguments=()):
        kind = signature["kind"]
        if kind == "named":
            identity = self.scope_identity(owner, signature["scope"])
            resolved = self.resolve(identity, signature["name"])
            if resolved is None:
                raise ValueError("Scoped field definition absent")
            identity = resolved["assembly_identity"]
            return {
                "kind": "named",
                "name": resolved["name"],
                "scope": {"kind": "ModuleDefinition", "name": self.assemblies[identity]["module_name"], "assembly_identity": identity},
            }
        if kind == "generic_parameter":
            position = signature["position"]
            if signature["owner"] != "Type" or type(position) is not int or not 0 <= position < len(arguments):
                raise ValueError("Unbound generic field parameter")
            return arguments[position]
        if kind == "array":
            return {**signature, "element": self.scoped_signature(owner, signature["element"], arguments)}
        if kind == "generic_instance":
            return {
                **signature,
                "definition": self.scoped_signature(owner, signature["definition"], arguments),
                "arguments": [self.scoped_signature(owner, value, arguments) for value in signature["arguments"]],
            }
        raise ValueError("Unsupported field signature")

    def definition(self, signature):
        named = signature["definition"] if signature["kind"] == "generic_instance" else signature
        if named["kind"] != "named":
            raise ValueError("Named scoped type required")
        scope = named["scope"]
        identity = scope["assembly_identity"]
        if scope["kind"] != "ModuleDefinition" or identity not in self.assemblies or scope["name"] != self.assemblies[identity]["module_name"]:
            raise ValueError("Canonical scoped signature required")
        key = (identity, named["name"])
        if key in self.exports:
            raise ValueError("Ambiguous type definition and forwarding metadata")
        typ = self.types.get(key)
        if typ is None:
            raise ValueError("Scoped type absent")
        arguments = signature.get("arguments", [])
        if len(arguments) != len(typ["generic_parameters"]):
            raise ValueError("Unbound or mismatched generic type")
        return key, typ, arguments

    def hierarchy(self, signature):
        seen = set()
        while signature is not None:
            key, typ, arguments = self.definition(signature)
            if key in seen:
                raise ValueError("cyclic scoped type hierarchy")
            seen.add(key)
            yield signature, key, typ, arguments
            base = typ["base_signature"]
            signature = self.scoped_signature(key[0], base, arguments) if base else None

    def field(self, signature, name):
        matches = []
        native = self.modules.get("UnityEngine.CoreModule.dll")
        for _, key, typ, arguments in self.hierarchy(signature):
            for field in typ["fields"]:
                if field["name"] == name and not field["is_static"] and not field["is_not_serialized"]:
                    matches.append(self.scoped_signature(key[0], field["signature"], arguments))
            # Unity's native object root ends serialized managed-field lookup.
            # Its framework base is not another serialized field provider; SDK
            # references there can differ from the selected AOT framework.
            if native is not None and key == (native["assembly_identity"], "UnityEngine.Object"):
                break
        if len(matches) != 1:
            raise ValueError("serialized field absent or ambiguous")
        return matches[0]

    def field_type(self, owner_registry, path):
        signature = self.registry(owner_registry)
        parts = iter(path)
        for part in parts:
            if part == "Array":
                index = next(parts, None)
                if not isinstance(index, str) or not index.isdecimal():
                    raise ValueError("serialized collection index absent")
                if signature["kind"] == "array" and signature["rank"] == 1:
                    signature = signature["element"]
                elif signature["kind"] == "generic_instance":
                    key, _, arguments = self.definition(signature)
                    if key[1] != "System.Collections.Generic.List`1" or len(arguments) != 1:
                        raise ValueError("unsupported serialized collection")
                    # Require the actual framework List, never a same-name game type.
                    assembly = self.assemblies[key[0]]["assembly"]
                    if assembly not in ("mscorlib", "System.Private.CoreLib"):
                        raise ValueError("serialized List scope is not a core provider")
                    signature = arguments[0]
                else:
                    raise ValueError("serialized collection signature differs")
            else:
                signature = self.field(signature, part)
        self.definition(signature)
        return signature

    def assignable(self, declared, endpoint_registry):
        expected, _, expected_arguments = self.definition(declared)
        native = self.modules.get("UnityEngine.CoreModule.dll")
        native_root = (native["assembly_identity"], "UnityEngine.Object") if native else None
        for _, key, _, arguments in self.hierarchy(self.registry(endpoint_registry)):
            if key == expected and arguments == expected_arguments:
                return True
            if key == native_root:
                # Two native-object branches cannot meet above UnityEngine.Object.
                # Prove the requested branch reaches that exact bound root before
                # rejecting a catalog sibling. Framework contracts still require
                # their complete, exact assembly dependencies.
                for _, declared_key, _, _ in self.hierarchy(declared):
                    if declared_key == native_root:
                        return False
        return False

    def prove_field_endpoint(self, owner_registry, path, endpoint_registry):
        declared = self.field_type(owner_registry, path)
        if not self.assignable(declared, endpoint_registry):
            raise ValueError("current CLR endpoint is not assignable to serialized field")
        return {"field_signature": declared, "endpoint_registry_identity": list(endpoint_registry)}


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
