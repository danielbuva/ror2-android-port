"""Project-setting projection over legitimate native manager schemas."""

import copy
import json
import re
import struct
import sys

PATHS = {
    "PlayerSettings": "ProjectSettings",
    "InputManager": "InputManager",
    "AudioManager": "AudioManager",
    "GraphicsSettings": "GraphicsSettings",
    "TimeManager": "TimeManager",
    "PhysicsManager": "DynamicsManager",
    "QualitySettings": "QualitySettings",
    "NavMeshProjectSettings": "NavMeshAreas",
    "Physics2DSettings": "Physics2DSettings",
}
RAW = {"TagManager", "VFXManager", "DelayedCallManager", "RuntimeInitializeOnLoadManager", "StreamingManager"}


def yaml_settings(raw):
    # SafeLoader is the pure Python implementation, including on Android.
    import yaml

    if yaml.__version__ != "6.0.3":
        raise ValueError("unqualified project-settings parser")
    text = re.sub(r"^%.*\n|^---[^\n]*\n", "", raw.decode(), flags=re.M)

    class Integer(int):
        pass

    class Loader(yaml.SafeLoader):
        pass

    def integer(loader, node):
        value = Integer(yaml.SafeLoader.construct_yaml_int(loader, node))
        value.source_text = node.value
        return value

    Loader.add_constructor("tag:yaml.org,2002:int", integer)
    value = yaml.load(text, Loader=Loader)
    if not isinstance(value, dict) or len(value) != 1:
        raise ValueError("project settings need one native root")
    return next(iter(value.values()))


def project(value, selected):
    if isinstance(value, dict):
        if set(value) == {"m_FileID", "m_PathID"}:
            return dict(m_FileID=0, m_PathID=0) if selected == {"fileID": 0} else copy.deepcopy(value)
        return {key: project(child, selected[key]) if isinstance(selected, dict) and key in selected else copy.deepcopy(child) for key, child in value.items()}
    if isinstance(value, list):
        selected = getattr(selected, "source_text", selected)
        if isinstance(selected, str) and re.fullmatch("[a-fA-F0-9]*", selected) and all(isinstance(x, int) for x in value):
            raw = bytes.fromhex(selected)
            return list(struct.unpack("<" + "I" * (len(raw) // 4), raw))
        if not isinstance(selected, list):
            return copy.deepcopy(value)
        if not selected:
            return []
        if not value:
            raise ValueError("no source settings element schema")
        return [project(value[min(i, len(value) - 1)], child) for i, child in enumerate(selected)]
    if isinstance(value, str):
        return "" if selected is None else str(selected) if isinstance(selected, (str, int, float)) else value
    if isinstance(value, bool):
        return bool(selected)
    if isinstance(value, (int, float)) and isinstance(selected, (int, float)):
        return selected
    return value


def single(text, pattern, message, require):
    values = re.findall(pattern, text, re.M)
    require(len(values) == 1, message)
    return values[0]


def produce(U, store, inputs, originals):
    root = store.root
    previous = list(sys.path)
    try:
        sys.path.insert(0, str(root / "scripts/lab"))
        bridge = U.module("_manager_bridge", root / "scripts/lab/nova_bridge.py")
        staging = U.module("_manager_staging", root / "scripts/lab/project_input_rebuild.py")
    finally:
        sys.path[:] = previous
    hashes = U.module("_manager_hashes", root / "tools/phone-build/accepted-output/shader_produce.py")
    cache = {}

    def parse(name):
        if name not in cache:
            path = root / ("smoke/ProjectSettings/" + name + ".asset")
            raw = path.read_bytes()
            if name == "InputManager":
                raw = bridge.insert_axes(raw.decode(), bridge.nova_axes()).encode()
            if name == "GraphicsSettings":
                raw = staging.graphics_settings(raw, inputs["project"]["graphics_template_sha256"])
            cache[name] = yaml_settings(raw)
        return cache[name]

    build = (root / "android/Assets/Editor/LabBuild.cs").read_text()
    out = {}
    for name, obj in originals.items():
        fields = store.native_fields(obj)
        if name in RAW:
            out[name] = fields
        elif name in PATHS:
            settings = parse(PATHS[name])
            fields = project(fields, settings)
            if name == "QualitySettings":
                fields["m_CurrentQuality"] = settings["m_PerPlatformDefaultQuality"]["Android"]
            if name == "PlayerSettings":
                for field in ("companyName", "productName"):
                    fields[field] = single(build, r"PlayerSettings\." + field + r'="([^"]+)"', "public player identity differs", U.require)
                U.require(
                    "PlayerSettings.enableFrameTimingStats=true;" in build and "PlayerSettings.colorSpace=ColorSpace.Linear;" in build,
                    "public player capability policy differs",
                )
                fields.update(enableFrameTimingStats=True, m_ActiveColorSpace=1, mobileMTRenderingBaked=bool(settings["mobileMTRendering"]["Android"]))
                fields["qualitySettingsNames"] = [row["name"] for row in parse("QualitySettings")["m_QualitySettings"]]
                fields["productGUID"] = {f"data[{i}]": int(settings["productGUID"][i * 8 : (i + 1) * 8][::-1], 16) for i in range(4)}
                app_id = single(
                    build, r'PlayerSettings\.SetApplicationIdentifier\(BuildTargetGroup\.Android,"([^"]+)"\)', "public app identifier differs", U.require
                )
                fields["AID"] = {f"bytes[{i}]": v for i, v in enumerate(hashes.spooky(app_id.encode()))}
            if name == "GraphicsSettings":
                for index, row in enumerate(settings["m_TierSettings"], 1):
                    fields[f"m_TierSettings_Tier{index}"] = project(fields[f"m_TierSettings_Tier{index}"], row["m_Settings"])
            out[name] = fields
    return out, cache, hashes
