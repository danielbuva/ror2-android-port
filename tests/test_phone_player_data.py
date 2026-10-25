"""Authored fixtures for the SDK/converter player-data target-tree boundary."""

import hashlib
import importlib.util
import io
import json
from pathlib import Path
import shutil
import struct
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("player_data", ROOT / "tools/phone-build/accepted-output/player_data.py")
P = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(P)


def pin(data):
    return len(data), hashlib.sha256(data).hexdigest()


def font_fixture(pc):
    """Authored native bodies; expected player metadata is packed independently."""
    source_bodies = [
        bytearray(b"authored material".ljust(148, b"!")),
        bytearray(b"authored texture".ljust(120, b"?")),
        bytearray(b"authored font bytes".ljust(192, b"~")),
    ]
    struct.pack_into("<iq", source_bodies[0], 20, 3, 10101)
    struct.pack_into("<iq", source_bodies[0], 76, 0, -27)
    struct.pack_into("<iq", source_bodies[2], 32, 0, -91)
    struct.pack_into("<iq", source_bodies[2], 48, 0, -27)
    bodies = [bytearray(body) for body in source_bodies]
    struct.pack_into("<iq", bodies[0], 20, 1, 10101)
    struct.pack_into("<iq", bodies[0], 76, 0, 2)
    struct.pack_into("<iq", bodies[2], 32, 0, 1)
    struct.pack_into("<iq", bodies[2], 48, 0, 2)
    types = [
        {"class_id": kind, "stripped": 0, "script_type": -1, "hash": bytes([index + 1]) * 16, "tree": struct.pack("<II", 1, 0) + bytes(32), "dependencies": []}
        for index, kind in enumerate((21, 28, 128))
    ]
    source_ids = (-91, -27, -93)
    offsets = (0, 152, 272)
    externals = [{"empty": "", "guid": bytes([index + 5]) * 16, "type": 0, "path": "authored dependency " + str(index)} for index in range(3)]
    source_layout = {
        "engine": "2021.3.45f2",
        "platform": 19,
        "trees": True,
        "types": types,
        "objects": [
            {"path_id": identity, "offset": offset, "bytes": len(body), "type_id": index}
            for index, (identity, offset, body) in enumerate(zip(source_ids, offsets, source_bodies))
        ],
        "scripts": [],
        "externals": externals,
        "ref_types": [],
        "user": "source-only metadata",
    }
    serialized = io.BytesIO()
    P.W.write_serialized(serialized, source_layout, lambda row: io.BytesIO(source_bodies[row["type_id"]]))
    data = serialized.getvalue()
    source = pc / "authored-font.bundle"
    with source.open("wb") as stream:
        P.W.write_bundle(stream, [("CAB-authored-font", 4, len(data), lambda: io.BytesIO(data))], lambda body, method: body, flags=0x40)
    # Independent v22 destination header/type/object/external records, no writer.
    meta = bytearray(b"2021.3.45f2\0" + struct.pack("<i?I", 13, False, 3))
    for index, kind in enumerate((21, 28, 128)):
        meta.extend(struct.pack("<iBh", kind, 0, -1) + bytes([index + 1]) * 16)
    meta.extend(struct.pack("<I", 3))
    for index, (offset, body) in enumerate(zip(offsets, bodies)):
        meta.extend(bytes(-len(meta) % 4))
        meta.extend(struct.pack("<qqIi", index + 1, offset, len(body), index))
    meta.extend(struct.pack("<II", 0, 1) + b"\0" + bytes([7]) * 16 + struct.pack("<i", 0) + b"authored dependency 2\0" + struct.pack("<I", 0) + b"\0")
    expected = bytearray(struct.pack(">IIII", 0, 0, 22, 0) + bytes(4) + struct.pack(">Iqqq", len(meta), 4096 + 272 + len(bodies[2]), 4096, 0))
    expected.extend(meta)
    expected.extend(bytes(4096 - len(expected)))
    expected.extend(bodies[0] + bytes(4) + bodies[1] + bodies[2])
    references = [
        [{"offset": 20, "from": [3, 10101], "to": [1, 10101]}, {"offset": 76, "from": [0, -27], "to": [0, 2]}],
        [],
        [{"offset": 32, "from": [0, -91], "to": [0, 1]}, {"offset": 48, "from": [0, -27], "to": [0, 2]}],
    ]
    selected = {
        "file": "authored-font-player",
        "source": {"path": source.name, "bytes": source.stat().st_size, "sha256": P.sha(source), "member": "CAB-authored-font"},
        "externals": [2],
        "objects": [
            {
                "source_path_id": source_id,
                "path_id": index + 1,
                "bytes": len(before),
                "source_sha256": pin(before)[1],
                "sha256": pin(after)[1],
                "references": refs,
            }
            for index, (source_id, before, after, refs) in enumerate(zip(source_ids, source_bodies, bodies, references))
        ],
    }
    return selected, bytes(expected)


class PlayerDataTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.pc, self.sdk, self.converter, self.output = [self.root / name for name in ("pc", "sdk", "converter", "new")]
        self.pc.mkdir()
        (self.pc / "owner.bin").write_bytes(b"original installation must remain unchanged")
        self.projects = ["Assembly-CSharp.dll", "Newtonsoft.Json.dll", "Authored.Game.dll", "MCPForUnity.Runtime.dll"]
        scripting = {
            "names": ["UnityEngine.CoreModule.dll", "UnityEngine.ClusterInputModule.dll", "Authored.Game.dll", "Assembly-CSharp.dll"],
            "types": [2, 2, 16, 16],
        }
        original_rows = [
            {"assemblyName": assembly, "nameSpace": "Authored", "className": "Start", "methodName": "Run", "loadTypes": 0, "isUnityClass": False}
            for assembly in ("Authored.Game", "Assembly-CSharp", "UnavailablePlatform")
        ]
        initializers = {"root": original_rows}
        self.profile = {"input_id": P.INPUT_ID, "sources": {}, "outputs": {}, "project_assemblies": self.projects}
        for name, value in (("ScriptingAssemblies.json", scripting), ("RuntimeInitializeOnLoads.json", initializers)):
            source = self.pc / name
            source.write_text(json.dumps(value))
            self.profile["sources"][name] = {"path": name, "bytes": source.stat().st_size, "sha256": P.sha(source)}
        expected_initializers = [
            {"assemblyName": "Assembly-CSharp", "nameSpace": "", "className": name, "methodName": method, "loadTypes": 0, "isUnityClass": False}
            for name, method in (
                ("PortSession", "Init"),
                ("CharacterDirectionProbe", "Init"),
                ("ControllerAddressProbe", "Init"),
                ("EntityStateTickProbe", "Init"),
                ("WholeCatalogBootstrap", "Initialize"),
            )
        ] + [original_rows[1], original_rows[0]]
        self.generated = {
            "ScriptingAssemblies.json": json.dumps(
                {"names": ["UnityEngine.CoreModule.dll"] + self.projects, "types": [2, 16, 16, 16, 16]}, separators=(",", ":")
            ).encode(),
            "RuntimeInitializeOnLoads.json": (json.dumps({"root": expected_initializers}, separators=(",", ":")) + "\n").encode(),
        }
        self.profile["font"], font_bytes = font_fixture(self.pc)
        self.generated[self.profile["font"]["file"]] = font_bytes
        self.profile["outputs"] = {name: {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()} for name, data in self.generated.items()}
        self.profile_path = self.root / "profile.json"
        self.profile_path.write_text(json.dumps(self.profile))
        self.profile_hash = P.sha(self.profile_path)
        self.bodies = {P.DEFAULT: b"authored SDK defaults\0", **{name: ("authored resource " + name).encode() for name in P.RESOURCES}}
        for name, body in self.bodies.items():
            file = (self.sdk / "Data" if name == P.DEFAULT else self.converter / "data") / name.removeprefix("Managed/")
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_bytes(body)
        self.resources = {name: pin(data) for name, data in self.bodies.items() if name != P.DEFAULT}
        self.receipt = {
            "exit_code": 0,
            "inputs_unchanged": True,
            "input_assemblies": 90,
            "files": {"data/" + name.removeprefix("Managed/"): {"bytes": size, "sha256": digest} for name, (size, digest) in self.resources.items()},
        }
        self.save_receipt()
        for mocker in (
            patch.dict(P.SDK.FILES, {"Data/" + P.DEFAULT: pin(self.bodies[P.DEFAULT])}),
            patch.object(P, "RESOURCES", self.resources),
            patch.object(P, "RESERVE", 0),
        ):
            mocker.start()
            self.addCleanup(mocker.stop)

    def save_receipt(self):
        (self.converter / "result.json").write_text(json.dumps(self.receipt))
        self.receipt_hash = P.sha(self.converter / "result.json")

    def produce(self, output=None):
        return P.produce(self.profile_path, self.profile_hash, self.pc, self.sdk, self.converter, self.receipt_hash, output or self.output)

    def failed(self):
        self.assertFalse(json.loads((self.output / "result.json").read_text())["success"])

    def test_source_only_complete_target_tree_and_receipt(self):
        before = (self.pc / "owner.bin").read_bytes()
        result = self.produce()
        self.assertTrue(result["success"])
        self.assertEqual(set(result["files"]), {P.TARGET + name for name in self.bodies | self.generated})
        self.assertEqual(json.loads((self.output / "result.json").read_text()), result)
        for name, body in self.bodies.items():
            self.assertEqual((self.output / (P.TARGET + name)).read_bytes(), body)
            row = result["files"][P.TARGET + name]
            self.assertEqual((row["bytes"], row["sha256"]), pin(body))
            self.assertEqual(row["source_role"], "sdk" if name == P.DEFAULT else "converter")
        for name, body in self.generated.items():
            self.assertEqual((self.output / (P.TARGET + name)).read_bytes(), body)
        self.assertEqual((self.pc / "owner.bin").read_bytes(), before)
        with self.assertRaisesRegex(ValueError, "must be new"):
            self.produce()

    def test_receipt_drift_failure_membership_and_resource_hash_fail_closed(self):
        mutations = ("pin", "failure", "changed-inputs", "missing", "comparison-hash")
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                receipt = json.loads(json.dumps(self.receipt))
                if mutation == "failure":
                    receipt["exit_code"] = 1
                elif mutation == "changed-inputs":
                    receipt["inputs_unchanged"] = False
                elif mutation == "missing":
                    receipt["files"].pop(next(iter(receipt["files"])))
                elif mutation == "comparison-hash":
                    receipt["files"][next(iter(receipt["files"]))]["sha256"] = "0" * 64
                (self.converter / "result.json").write_text(json.dumps(receipt))
                receipt_hash = "0" * 64 if mutation == "pin" else P.sha(self.converter / "result.json")
                output = self.root / mutation
                with self.assertRaises(ValueError):
                    P.produce(self.profile_path, self.profile_hash, self.pc, self.sdk, self.converter, receipt_hash, output)
                self.assertFalse(json.loads((output / "result.json").read_text())["success"])

    def test_source_drift_and_missing_provider_have_no_target_fallback(self):
        source = self.converter / "data" / next(iter(self.resources)).removeprefix("Managed/")
        for missing in (False, True):
            with self.subTest(missing=missing):
                output = self.root / ("missing" if missing else "drift")
                source.unlink() if missing else source.write_bytes(b"changed provider")
                with self.assertRaises((ValueError, FileNotFoundError)):
                    self.produce(output)
                self.assertFalse(json.loads((output / "result.json").read_text())["success"])

    def test_output_disjointness_and_redirection_leave_sources_untouched(self):
        for root in (self.pc, self.sdk, self.converter):
            with self.subTest(root=root), self.assertRaisesRegex(ValueError, "separate"):
                self.produce(root / "new")
            self.assertFalse((root / "new").exists())
        alias = self.root / "redirected"
        alias.symlink_to(self.pc, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "separate"):
            self.produce(alias / "new")
        provider = self.sdk / "Data" / P.DEFAULT
        other = self.root / "other"
        provider.rename(other)
        provider.symlink_to(other)
        with self.assertRaisesRegex(ValueError, "redirected"):
            self.produce()
        self.failed()
        self.assertEqual(other.read_bytes(), self.bodies[P.DEFAULT])

    def test_readback_and_source_changes_are_detected(self):
        copy = shutil.copyfile
        for target in ("output", "source", "receipt"):
            with self.subTest(target=target):
                output = self.root / target

                def corrupt(source, destination):
                    result = copy(source, destination)
                    if source.name == P.DEFAULT:
                        selected = destination if target == "output" else source if target == "source" else self.converter / "result.json"
                        selected.write_bytes(b"changed during production")
                    return result

                with patch.object(P.shutil, "copyfile", side_effect=corrupt), self.assertRaises(ValueError):
                    self.produce(output)
                self.assertFalse(json.loads((output / "result.json").read_text())["success"])
                (self.sdk / "Data" / P.DEFAULT).write_bytes(self.bodies[P.DEFAULT])
                self.save_receipt()

    def test_original_metadata_identity_and_recipe_drift_refuse(self):
        with self.assertRaisesRegex(ValueError, "profile drift"):
            P.produce(self.profile_path, "0" * 64, self.pc, self.sdk, self.converter, self.receipt_hash, self.output)
        self.assertFalse(self.output.exists())
        for mutation in ("original", "order", "path"):
            with self.subTest(mutation=mutation):
                profile = json.loads(json.dumps(self.profile))
                if mutation == "original":
                    source = self.pc / "ScriptingAssemblies.json"
                    old = source.read_bytes()
                    source.write_bytes(b"changed PC metadata")
                elif mutation == "order":
                    profile["project_assemblies"].reverse()
                else:
                    profile["sources"]["ScriptingAssemblies.json"]["path"] = "../profile.json"
                self.profile_path.write_text(json.dumps(profile))
                self.profile_hash = P.sha(self.profile_path)
                output = self.root / mutation
                with self.assertRaises(ValueError):
                    self.produce(output)
                self.assertFalse(json.loads((output / "result.json").read_text())["success"])
                if mutation == "original":
                    source.write_bytes(old)

    def test_font_source_object_reference_and_output_metadata_drift_refuse(self):
        for mutation in ("bundle", "body", "reference", "metadata", "memory-bound"):
            with self.subTest(mutation=mutation):
                profile = json.loads(json.dumps(self.profile))
                font = profile["font"]
                if mutation == "bundle":
                    font["source"]["sha256"] = "0" * 64
                elif mutation == "body":
                    font["objects"][0]["source_sha256"] = "0" * 64
                elif mutation == "reference":
                    font["objects"][0]["references"][0]["from"][0] = 2
                elif mutation == "metadata":
                    font["externals"] = [1]
                else:
                    font["objects"][0]["bytes"] = P.W.B.LIMIT
                self.profile_path.write_text(json.dumps(profile))
                self.profile_hash = P.sha(self.profile_path)
                output = self.root / mutation
                with self.assertRaises(ValueError):
                    self.produce(output)
                self.assertFalse(json.loads((output / "result.json").read_text())["success"])


if __name__ == "__main__":
    unittest.main()
