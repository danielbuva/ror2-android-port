"""Authored, from-scratch TextAsset bundle probe, never a game content builder."""

import hashlib
import json
import os
from pathlib import Path
import subprocess

from UnityPy.helpers.Tpk import get_typetree_node
from UnityPy.helpers.TypeTreeHelper import write_typetree
from UnityPy.helpers.TypeTreeNode import TypeTreeNode
from UnityPy.helpers.UnityVersion import UnityVersion
from UnityPy.streams import EndianBinaryWriter


VERSION = "2021.3.45f2"
PAYLOAD = "phone-owned-content-fixture-v1\n"
ASSET = "assets/phone-fixture.txt"


def _object(class_id, value):
    writer = EndianBinaryWriter(endian="<")
    tree = get_typetree_node(class_id, UnityVersion.from_str(VERSION))
    write_typetree(value, tree, writer)
    return writer.bytes


def _type_tree(class_id):
    nodes = get_typetree_node(class_id, UnityVersion.from_str(VERSION)).to_dict_list()
    tree = TypeTreeNode.from_list([{k: v for k, v in node.items() if k != "m_Children"} for node in nodes])
    for node in tree.traverse():
        node.m_TypeFlags = 1 if node.m_Type == "Array" else 0
        node.m_RefTypeHash = 0
    return tree


def make_bundle():
    """Build only two native object types, using public UnityPy type schemas.

    No editor output, game input, template bundle or imported type hash is read.
    Zero type hashes are experimental inputs; embedded public type trees let
    Unity independently check the resulting native object serialization.
    """
    pointer = {"m_FileID": 0, "m_PathID": 2}
    info = {"preloadIndex": 0, "preloadSize": 1, "asset": pointer}
    values = [
        (
            142,
            {
                "m_Name": "phone-fixture",
                "m_PreloadTable": [pointer],
                "m_Container": [(ASSET, info)],
                "m_MainAsset": {"preloadIndex": 0, "preloadSize": 0, "asset": {"m_FileID": 0, "m_PathID": 0}},
                "m_RuntimeCompatibility": 1,
                "m_AssetBundleName": "phone-fixture",
                "m_Dependencies": [],
                "m_IsStreamedSceneAssetBundle": False,
                "m_ExplicitDataLayout": 0,
                "m_PathFlags": 0,
                "m_SceneHashes": [],
            },
        ),
        (49, {"m_Name": "phone-fixture", "m_Script": PAYLOAD}),
    ]
    body = EndianBinaryWriter(endian="<")
    objects = []
    for class_id, value in values:
        body.align_stream(8)
        raw = _object(class_id, value)
        objects.append((body.Position, len(raw)))
        body.write_bytes(raw)

    meta = EndianBinaryWriter(endian="<")
    meta.write_string_to_null(VERSION)
    meta.write_int(13)  # BuildTarget.Android, not a change to the game target.
    meta.write_boolean(True)
    meta.write_int(len(values))
    for class_id, _ in values:
        meta.write_int(class_id)
        meta.write_boolean(False)
        meta.write_short(-1)
        meta.write_bytes(bytes(16))
        _type_tree(class_id).dump_blob(meta, 22)
        meta.write_int(0)  # Type dependencies are present with type trees only.
    meta.write_int(len(objects))
    for index, (offset, size) in enumerate(objects):
        # Alignment is relative to the serialized file, whose header is 48 B.
        meta.align_stream(4)
        meta.write_long(index + 1)
        meta.write_long(offset)
        meta.write_u_int(size)
        meta.write_int(index)
    for _ in range(3):
        meta.write_int(0)  # Script types, externals, reference types.
    meta.write_string_to_null("")
    data_offset = (48 + meta.Length + 15) // 16 * 16
    serialized = EndianBinaryWriter()
    for value in (0, 0, 22, 0):
        serialized.write_u_int(value)
    serialized.write_bytes(bytes(4))  # Little-endian metadata, reserved.
    serialized.write_u_int(meta.Length)
    serialized.write_long(data_offset + body.Length)
    serialized.write_long(data_offset)
    serialized.write_long(0)
    serialized.write_bytes(meta.bytes)
    serialized.align_stream(16)
    serialized.write_bytes(body.bytes)

    directory = EndianBinaryWriter()
    directory.write_bytes(bytes(16))
    directory.write_int(1)
    directory.write_u_int(serialized.Length)
    directory.write_u_int(serialized.Length)
    directory.write_u_short(0)  # Uncompressed data block.
    directory.write_int(1)
    directory.write_long(0)
    directory.write_long(serialized.Length)
    directory.write_u_int(4)  # Serialized file node.
    directory.write_string_to_null("CAB-phone-build-fixture")
    bundle = EndianBinaryWriter()
    bundle.write_string_to_null("UnityFS")
    bundle.write_u_int(7)
    bundle.write_string_to_null("5.x.x")
    bundle.write_string_to_null(VERSION)
    size_position = bundle.Position
    bundle.write_long(0)
    bundle.write_u_int(directory.Length)
    bundle.write_u_int(directory.Length)
    bundle.write_u_int(0x40)
    bundle.align_stream(16)
    bundle.write_bytes(directory.bytes)
    bundle.write_bytes(serialized.bytes)
    total = bundle.Length
    bundle.Position = size_position
    bundle.write_long(total)
    return bundle.bytes


def stage(destination):
    """Stage a new isolated project; refuse to overwrite any earlier attempt."""
    from common import ROOT

    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=False)
    assets = destination / "Assets"
    (assets / "Editor").mkdir(parents=True)
    (assets / "StreamingAssets").mkdir()
    for name, folder in (("ContentFixture.cs", assets), ("ContentFixtureBuilder.cs", assets / "Editor")):
        source = ROOT / "tools/phone-build" / name
        (folder / name).write_bytes(source.read_bytes())
    (destination / "Packages").mkdir()
    (destination / "Packages/manifest.json").write_text(
        '{"dependencies":{"com.unity.modules.assetbundle":"1.0.0","com.unity.modules.jsonserialize":"1.0.0","com.unity.modules.unitywebrequest":"1.0.0"}}\n'
    )
    (destination / "ProjectSettings").mkdir()
    (destination / "ProjectSettings/ProjectVersion.txt").write_text(
        "m_EditorVersion: " + VERSION + "\nm_EditorVersionWithRevision: " + VERSION + " (88f88f591b2e)\n"
    )
    data = make_bundle()
    (assets / "StreamingAssets/phone-fixture.bundle").write_bytes(data)
    receipt = {
        "schema": 1,
        "generator": "scripts/lab/phone_content.py",
        "unity": VERSION,
        "bundle_sha256": hashlib.sha256(data).hexdigest(),
        "game_inputs": False,
        "device_accepted": False,
        "sources": {
            name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
            for name in ("scripts/lab/phone_content.py", "tools/phone-build/ContentFixture.cs", "tools/phone-build/ContentFixtureBuilder.cs")
        },
    }
    (destination / "fixture-inputs.json").write_text(json.dumps(receipt, indent=2) + "\n")
    return receipt


def stage_action():
    from common import WORK, now

    destination = WORK / "rebuild/phone-content" / now() / "project"
    print(json.dumps({"project": str(destination), **stage(destination)}, indent=2))


def run_editor(project, *, build=False):
    """Use only the generated fixture and the primary checkout's build mutex."""
    from build_lock import host_build_lock
    from common import ROOT, WORK

    project = Path(project).resolve()
    if not project.is_relative_to((WORK / "rebuild/phone-content").resolve()):
        raise RuntimeError("Select an isolated phone-content project with --target")
    receipt = json.loads((project / "fixture-inputs.json").read_text())
    for name, expected in receipt["sources"].items():
        if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != expected:
            raise RuntimeError("Source changed; generate a new attempt: " + name)
    for name, relative in (("ContentFixture.cs", "Assets/ContentFixture.cs"), ("ContentFixtureBuilder.cs", "Assets/Editor/ContentFixtureBuilder.cs")):
        if (project / relative).read_bytes() != (ROOT / "tools/phone-build" / name).read_bytes():
            raise RuntimeError("Staged fixture source changed: " + name)
    if hashlib.sha256((project / "Assets/StreamingAssets/phone-fixture.bundle").read_bytes()).hexdigest() != receipt["bundle_sha256"]:
        raise RuntimeError("Generated fixture bundle changed")
    if build and subprocess.check_output(["git", "status", "--porcelain", "--", "tools/phone-build", "scripts/lab/phone_content.py"], cwd=ROOT):
        raise RuntimeError("Commit the fixture sources before building")
    common_dir = Path(subprocess.check_output(["git", "rev-parse", "--path-format=absolute", "--git-common-dir"], cwd=ROOT, text=True).strip())
    if common_dir.name != ".git":
        raise RuntimeError("Cannot locate the primary checkout build mutex")
    lock = common_dir.parent / "work/coordination/unity-build.lock"
    operation = "build" if build else "check"
    log = project.parent / ("editor-" + operation + ".log")
    method = "ContentFixtureBuilder.Build" if build else "ContentFixtureBuilder.Check"
    env = dict(os.environ)
    env["ANDROID_SDK_HOME"] = str(ROOT / ".local/phone-build-android")
    env["ANDROID_USER_HOME"] = str(ROOT / ".local/phone-build-android/.android")
    env["GRADLE_USER_HOME"] = str(ROOT / ".local/phone-build-gradle")
    Path(env["ANDROID_USER_HOME"]).mkdir(parents=True, exist_ok=True)
    args = [
        env["UNITY_EDITOR"],
        "-batchmode",
        "-nographics",
        "-quit",
        "-projectPath",
        str(project),
        "-buildTarget",
        "Android",
        "-executeMethod",
        method,
        "-logFile",
        str(log),
    ]
    with host_build_lock(lock, operation="Alpha phone content fixture " + operation, timeout=1):
        result = subprocess.run(args, env=env, capture_output=True, timeout=600)
    (project.parent / ("editor-" + operation + "-launch.txt")).write_bytes(result.stdout + result.stderr)
    outcome = {
        "exit_code": result.returncode,
        "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "log": str(log),
        "fixture_inputs": receipt,
    }
    (project.parent / ("editor-" + operation + "-receipt.json")).write_text(json.dumps(outcome, indent=2) + "\n")
    print(json.dumps(outcome, indent=2))
    if result.returncode:
        raise RuntimeError("Exact-editor fixture failed; inspect its retained log")
