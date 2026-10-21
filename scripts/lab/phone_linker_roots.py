"""Generate only SDK-native metadata; project root inputs remain captured."""

from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil


SCENE_PROJECT_FIELDS = ("serializedTypes", "typesInScenes")
PROJECT_FIELDS = (*SCENE_PROJECT_FIELDS, "forceIncludeModules", "forceExcludeModules")
SCENE_FIELDS = {"managedAssemblyName", "nativeClass", "fullManagedTypeName", "moduleName", "usedInScenes"}
NATIVE_FIELDS = ("name", "qualifiedName", "nativeNamespace", "module", "baseName", "baseModule")
EDITOR_DATA = "native-roots/EditorToUnityLinkerData.json"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def scene_subset(value):
    """Select only scene fields; captured module-policy/native values are not read."""
    if not isinstance(value, dict) or set(value) not in (set(SCENE_PROJECT_FIELDS), set(PROJECT_FIELDS), set(PROJECT_FIELDS) | {"allNativeTypes"}):
        raise ValueError("Unknown captured project-root schema")
    if value["serializedTypes"] != []:
        raise ValueError("Nonempty serialized-type roots need separate qualification")
    if not isinstance(value["typesInScenes"], list) or not value["typesInScenes"]:
        raise ValueError("Missing captured scene usage")
    for row in value["typesInScenes"]:
        if not isinstance(row, dict) or set(row) != SCENE_FIELDS:
            raise ValueError("Unknown captured scene-usage schema")
        if any(not isinstance(row[key], str) for key in SCENE_FIELDS - {"usedInScenes"}):
            raise ValueError("Malformed captured scene type identity")
        if not row["nativeClass"] and not row["fullManagedTypeName"]:
            raise ValueError("Empty captured scene type identity")
        if not isinstance(row["usedInScenes"], list) or any(not isinstance(scene, str) for scene in row["usedInScenes"]):
            raise ValueError("Malformed captured scene names")
    return {name: deepcopy(value[name]) for name in SCENE_PROJECT_FIELDS}


def project_subset(value):
    """Select project fields without reading the captured native-table value."""
    if not isinstance(value, dict) or set(value) not in (set(PROJECT_FIELDS), set(PROJECT_FIELDS) | {"allNativeTypes"}):
        raise ValueError("Unknown captured project-root schema")
    result = scene_subset(value)
    for name in ("forceIncludeModules", "forceExcludeModules"):
        modules = value[name]
        if not isinstance(modules, list) or any(not isinstance(m, str) or not m for m in modules) or len(set(modules)) != len(modules):
            raise ValueError("Malformed captured module policy")
        result[name] = deepcopy(modules)
    if set(value["forceIncludeModules"]) & set(value["forceExcludeModules"]):
        raise ValueError("Conflicting captured module policy")
    return result


def native_types(registry):
    if not isinstance(registry, dict):
        raise ValueError("Expected an SDK metadata object")
    rows = registry.get("records")
    if registry.get("executes_sdk") is not False or registry.get("root_generation_qualified") is not False or not isinstance(rows, list) or not rows:
        raise ValueError("Expected independently extracted SDK metadata")
    pointers, names = {}, set()
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("Expected an SDK native identity object")
        if any(not isinstance(row.get(key), str) for key in NATIVE_FIELDS) or not row["name"] or not row["module"] or row.get("base_resolved") is not True:
            raise ValueError("Incomplete SDK native identity")
        if type(row.get("self")) is not int or row["self"] <= 0 or type(row.get("parent")) is not int or row["parent"] < 0:
            raise ValueError("Malformed SDK native pointer identity")
        qualified = (row["nativeNamespace"] + "::" if row["nativeNamespace"] else "") + row["name"]
        if row["qualifiedName"] != qualified or qualified in names or row["self"] in pointers:
            raise ValueError("Ambiguous SDK native identity")
        pointers[row["self"]] = row
        names.add(qualified)
    for row in rows:
        parent = pointers.get(row["parent"])
        if row["parent"] and parent is None:
            raise ValueError("Unresolved SDK native parent")
        expected = (parent["name"], parent["module"]) if parent else ("", "")
        if (row["baseName"], row["baseModule"]) != expected:
            raise ValueError("SDK native base fields contradict pointer identity")
    complete = set()
    for row in rows:
        chain, pointer = set(), row["self"]
        while pointer and pointer not in complete:
            if pointer in chain:
                raise ValueError("Cyclic SDK native hierarchy")
            chain.add(pointer)
            pointer = pointers[pointer]["parent"]
        complete.update(chain)
    return [{key: row[key] for key in NATIVE_FIELDS} for row in sorted(rows, key=lambda item: item["qualifiedName"])]


def compose(project, registry):
    result = project_subset(project)
    result["allNativeTypes"] = native_types(registry)
    return result


def stage_support(destination, request, captured, source_root, *, module_configuration=None):
    """Stage SDK bytes and authored readers, never an extracted native table."""
    from phone_registry import BINARY_SHA256, PROFILE

    destination, source_root = map(Path, (destination, source_root))
    if (
        not isinstance(request, dict)
        or set(request) != {"binary", "sha256"}
        or not isinstance(request["binary"], str)
        or not Path(request["binary"]).is_absolute()
    ):
        raise ValueError("Select an explicit owner SDK binary and hash")
    binary = Path(request["binary"]).resolve(strict=True)
    if request["sha256"] != BINARY_SHA256 or sha(binary) != BINARY_SHA256:
        raise ValueError("Unqualified SDK registry binary")
    if (destination / "inputs/EditorToUnityLinkerData.json").exists():
        raise ValueError("Captured native table must not be staged")
    project = scene_subset(captured) if module_configuration is not None else project_subset(captured)
    (destination / "registry").mkdir()
    for name in ("phone_registry.py", "phone_registry_literals.py"):
        shutil.copyfile(source_root / "scripts/lab" / name, destination / "registry" / name)
    shutil.copyfile(binary, destination / "registry/owner-sdk")
    if sha(destination / "registry/owner-sdk") != BINARY_SHA256:
        raise ValueError("SDK changed while staging")
    shutil.copyfile(__file__, destination / "phone_linker_roots.py")
    with (destination / "project-root-data.json").open("x") as stream:
        stream.write(json.dumps(project, indent=2) + "\n")
    return {
        "profile": PROFILE,
        "sdk_binary_sha256": BINARY_SHA256,
        "native_order": "qualifiedName-ordinal",
        "project_roots_from_desktop": True,
        "captured_native_table_staged": False,
        **({"module_policy": module_configuration} if module_configuration is not None else {}),
    }


def project_data(stage, configuration):
    project = json.loads((stage / "project-root-data.json").read_text())
    fields = SCENE_PROJECT_FIELDS if "module_policy" in configuration else PROJECT_FIELDS
    if set(project) != set(fields):
        raise ValueError("Staged project fields include foreign/native/policy data")
    policy = None
    if "module_policy" in configuration:
        specification = importlib.util.spec_from_file_location("_linker_module_policy", stage / "phone_module_policy.py")
        reader = importlib.util.module_from_spec(specification)
        specification.loader.exec_module(reader)  # Authored tool, not SDK code.
        policy = reader.evaluate_stage(stage / "module-policy")
        expected = {
            "profile": reader.PROFILE,
            "captured_policy_staged": False,
            "package_closure_validated": True,
            "enabled_package_count": len(policy["enabledPackages"]),
        }
        if configuration["module_policy"] != expected:
            raise ValueError("Unqualified module-policy configuration")
        project = scene_subset(project) | {name: policy[name] for name in PROJECT_FIELDS[2:]}
    return project_subset(project), policy


def generate(stage, output, configuration):
    """Run authored SDK readers at the actual stripping invocation boundary."""
    stage, output = map(Path, (stage, output))
    if (stage / "inputs/EditorToUnityLinkerData.json").exists():
        raise ValueError("Captured native table present in the SDK-native mode")
    project, policy = project_data(stage, configuration)
    specification = importlib.util.spec_from_file_location("_linker_registry_reader", stage / "registry/phone_registry.py")
    reader = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(reader)  # Authored Python tool, not SDK code.
    expected = {
        "profile": reader.PROFILE,
        "sdk_binary_sha256": reader.BINARY_SHA256,
        "native_order": "qualifiedName-ordinal",
        "project_roots_from_desktop": True,
        "captured_native_table_staged": False,
        **({"module_policy": configuration["module_policy"]} if policy is not None else {}),
    }
    if configuration != expected:
        raise ValueError("Unqualified native-root configuration")
    destination = output / "native-roots"
    destination.mkdir(parents=True, exist_ok=False)
    registry = reader.inspect(stage / "registry/owner-sdk", destination / "sdk-registry.json")
    generated = compose(project, registry)
    if policy is not None:
        with (destination / "module-policy.json").open("x") as stream:
            stream.write(json.dumps(policy, indent=2) + "\n")
    with (destination / "EditorToUnityLinkerData.json").open("x") as stream:
        stream.write(json.dumps(generated, indent=2) + "\n")
    result = {
        **expected,
        "native_types_origin": "owner-sdk",
        "complete_editor_root_generation": False,
        "project_data_sha256": sha(stage / "project-root-data.json"),
        "registry_sha256": sha(destination / "sdk-registry.json"),
        "editor_data_sha256": sha(destination / "EditorToUnityLinkerData.json"),
        "counts": {"native_types": len(generated["allNativeTypes"]), "types_in_scenes": len(project["typesInScenes"])},
        **(
            {"module_policy_sha256": sha(destination / "module-policy.json"), "module_policy_reader_sha256": sha(stage / "phone_module_policy.py")}
            if policy is not None
            else {}
        ),
    }
    with (destination / "receipt.json").open("x") as stream:
        stream.write(json.dumps(result, indent=2) + "\n")
    return result


def verify(stage, output, result):
    stage, output = map(Path, (stage, output))
    configuration = json.loads((stage / "plan.json").read_text())["native_registry"]
    destination = output / "native-roots"
    if (
        not isinstance(result, dict)
        or result != json.loads((destination / "receipt.json").read_text())
        or any(result.get(key) != value for key, value in configuration.items())
    ):
        raise ValueError("Native-root receipt/configuration drift")
    if result.get("native_types_origin") != "owner-sdk" or result.get("complete_editor_root_generation") is not False:
        raise ValueError("Native-root source/scope differs")
    if (stage / "inputs/EditorToUnityLinkerData.json").exists():
        raise ValueError("Captured native table was staged")
    for name, path in (
        ("project_data_sha256", stage / "project-root-data.json"),
        ("registry_sha256", destination / "sdk-registry.json"),
        ("editor_data_sha256", destination / "EditorToUnityLinkerData.json"),
    ):
        if sha(path) != result[name]:
            raise ValueError("Generated native-root data drift")
    registry = json.loads((destination / "sdk-registry.json").read_text())
    if (
        registry["profile"] != configuration["profile"]
        or registry["binary_sha256"] != configuration["sdk_binary_sha256"]
        or sha(stage / "registry/owner-sdk") != configuration["sdk_binary_sha256"]
    ):
        raise ValueError("Native-root SDK input drift")
    if registry["reader_sha256"] != sha(stage / "registry/phone_registry.py") or registry["literal_reader_sha256"] != sha(
        stage / "registry/phone_registry_literals.py"
    ):
        raise ValueError("Native-root decoder source drift")
    project, policy = project_data(stage, configuration)
    if policy is not None and (
        result.get("module_policy_sha256") != sha(destination / "module-policy.json")
        or result.get("module_policy_reader_sha256") != sha(stage / "phone_module_policy.py")
        or policy != json.loads((destination / "module-policy.json").read_text())
    ):
        raise ValueError("Generated module-policy data/source drift")
    generated = compose(project, registry)
    if result["counts"] != {"native_types": len(generated["allNativeTypes"]), "types_in_scenes": len(project["typesInScenes"])}:
        raise ValueError("Native-root receipt counts differ")
    if json.loads((destination / "EditorToUnityLinkerData.json").read_text()) != generated:
        raise ValueError("Generated native-root projection differs")
    return result
