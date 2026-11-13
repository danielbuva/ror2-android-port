"""Real authored source metadata through mocked shader compilation and emission."""

from contextlib import ExitStack, nullcontext
from copy import deepcopy
import io
import hashlib
import json
from pathlib import Path
import struct
import sys
import tempfile
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

from test_shader_context import fixture, F

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools/phone-build/accepted-output"))
import object_produce as O
import payload_shader_records as A
import shader_context as C
import shader_prefab as H
import shader_produce as P
import shader_sdk as SDK
import unity_write as W


class SupplierTypeMetadataTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.pc, self.sdk, self.legacy, self.public = (self.root / name for name in ("pc", "sdk", "legacy", "public"))
        for directory in (self.pc, self.sdk, self.legacy, self.public):
            directory.mkdir()
        for sdk in (self.sdk, self.legacy):
            for name in ("MacOS/Unity", "Tools/UnityShaderCompiler", "Resources/unity_builtin_extra"):
                path = sdk / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"authored SDK fixture")
        self.codec = self.root / "codec"
        self.codec.write_bytes(b"authored codec fixture")
        self.body, schema = fixture()
        raw = F.serialized(self.body, schema, path_id=77, class_id=48)
        stream = io.BytesIO(raw)
        stream.size = len(raw)
        layout = W.read_serialized(stream)
        typ = layout["types"][0]
        typ.update(hash=bytes(range(16)), dependencies=[3, 7], stripped=1)
        # A third descriptor differs only in dependency metadata.
        layout["types"] = [typ, {**typ, "dependencies": [3, 8]}]
        layout["objects"] = [
            dict(path_id=pid, type_id=int(pid == 99), offset=i * ((len(self.body) + 7) // 8 * 8), bytes=len(self.body)) for i, pid in enumerate((77, 88, 99))
        ]
        layout.pop("data_offset")
        layout.pop("bytes")
        self.source = self.pc / "source.assets"
        with self.source.open("wb") as stream:
            W.write_serialized(stream, layout, lambda row: io.BytesIO(self.body))
        self.source_pin = dict(path=self.source.name, member=self.source.name, **self.pin(self.source))
        self.shader = {
            "m_ParsedForm": {
                "m_Name": "Legacy Shaders/Particles/Alpha Blended Premultiply",
                "m_FallbackName": "Particles/Alpha Blended Premultiply",
                "m_PropInfo": {},
                "m_KeywordNames": [],
                "m_KeywordFlags": [],
                "m_SubShaders": [],
            },
            "m_CompileInfo": {"m_Snippets": []},
            "m_Dependencies": [],
        }
        self.objects = [
            NS(
                path_id=pid,
                assets_file=NS(name=self.source.name),
                type=NS(name="Shader"),
                serialized_type=NS(node=schema),
                read_typetree=lambda: deepcopy(self.shader),
                get_raw_data=lambda: self.body,
            )
            for pid in (77, 88, 99)
        ]
        asset = NS(name=self.source.name, objects={obj.path_id: obj for obj in self.objects})
        self.environment = NS(objects=self.objects, assets=[asset])
        self.connection = NS(capabilities=[], preprocess=lambda *a, **k: dict(success=True, snippets=[], records=[]))
        self.sources = NS(dummy_shader_source=lambda *a: ("authored Shader", "SingleTexture"))
        self.compiler = NS(compiler=lambda *a, **k: nullcontext(self.connection))
        stack = self.enterContext(ExitStack())
        modules = {
            "UnityPy": NS(load=lambda *a: self.environment),
            "UnityPy.helpers.TypeTreeHelper": NS(write_typetree=self.write_tree),
            "UnityPy.streams": NS(EndianBinaryWriter=lambda **k: NS(bytes=b"")),
        }
        stack.enter_context(patch.dict(sys.modules, modules))
        stack.enter_context(patch.object(P, "includes", return_value=("authored includes", b"")))
        original_module = P.module
        stack.enter_context(
            patch.object(
                P,
                "module",
                side_effect=lambda name, path: self.compiler if "compiler" in name else self.sources if "source" in name else original_module(name, path),
            )
        )
        stack.enter_context(patch.object(W, "codec", side_effect=lambda *a: nullcontext(None)))
        stack.enter_context(patch.object(SDK, "sdk_source", side_effect=lambda *a: deepcopy(self.shader)))
        stack.enter_context(patch.object(SDK, "compile_body", side_effect=lambda *a, **k: (self.body, deepcopy(self.shader), None)))

    def write_tree(self, tree, node, writer):
        writer.bytes = self.body

    def pin(self, path):
        return dict(bytes=path.stat().st_size, sha256=P.sha(path))

    def origin(self, pid=77):
        return dict(self.source_pin, path_id=pid, body_sha256=hashlib.sha256(self.body).hexdigest())

    def sdk_pins(self, root=None):
        root = root or self.sdk
        return {name: self.pin(root / name) for name in ("MacOS/Unity", "Tools/UnityShaderCompiler", "Resources/unity_builtin_extra")}

    def target(self, pid):
        return dict(bundle="authored-output", member="CAB-output", path_id=pid, bytes=len(self.body), sha256=hashlib.sha256(self.body).hexdigest())

    def profile(self, value):
        path = self.root / "profile.json"
        path.write_text(json.dumps(value))
        return path

    def assert_pack(self, output, result, source_ids):
        self.assertTrue(result["success"])
        rows = [json.loads(line) for line in (output / "index.jsonl").read_text().splitlines()]
        types = json.loads((output / "types.json").read_text())
        self.assertEqual(len(rows), len(source_ids))
        for row, pid in zip(rows, source_ids, strict=True):
            typ = O.source_record_type(self.source, self.source.name, pid, 48)
            self.assertEqual(types[row["type_id"]], O.json_layout(typ))
        self.assertEqual(result["outputs"]["types.json"], self.pin(output / "types.json"))
        return rows, types

    def test_postprocessing_emits_complete_deduplicated_final_descriptors(self):
        profile = dict(
            input_id=A.INPUT_ID,
            source=self.source_pin,
            sdk=self.sdk_pins(),
            includes_sha256="authored includes",
            template_inputs={},
            exporter_revision="authored",
            settings={},
            shaders=[
                dict(
                    path_id=pid,
                    source_sha256=self.origin(pid)["body_sha256"],
                    source_filename="fixture.shader",
                    template="SingleTexture",
                    outputs=[self.target(i + 1)],
                )
                for i, pid in enumerate((77, 88, 99))
            ],
        )
        path = self.profile(profile)
        output = self.root / "post"
        with (
            patch.object(A, "postprocessing_tree", side_effect=lambda *a: deepcopy(self.shader)),
            patch.object(A.subprocess, "check_output", return_value=b"authored license"),
        ):
            result = A.produce_postprocessing(path, profile, P.sha(path), self.pc, self.sdk, self.public, output, self.codec, P.sha(self.codec))
        rows, types = self.assert_pack(output, result, [77, 88, 99])
        self.assertEqual([row["type_id"] for row in rows], [0, 0, 1])
        self.assertEqual(len(types), 2)

    def test_prefab_emits_original_descriptors_for_each_selected_shader(self):
        profile = dict(
            input_id=A.INPUT_ID,
            sdk=self.sdk_pins(),
            includes_sha256="authored includes",
            settings={"tier0": {}},
            shader_links=[],
            records=[dict(kind="sdk", sdk_shader=207, original=self.origin(pid), outputs=[self.target(i + 1)]) for i, pid in enumerate((77, 88, 99))],
        )
        path = self.profile(profile)
        output = self.root / "prefab"
        with patch.object(H, "prefab_selections", return_value={}):
            result = H.produce(path, P.sha(path), self.pc, self.sdk, None, self.codec, P.sha(self.codec), output)
        rows, types = self.assert_pack(output, result, [77, 88, 99])
        self.assertEqual([row["type_id"] for row in rows], [0, 0, 1])
        self.assertEqual(len(types), 2)

    def test_standard_aliases_keep_the_original_descriptor(self):
        profile = dict(
            input_id=A.INPUT_ID,
            source_type=self.origin(),
            sdk_shader=207,
            prefab_no_fog=True,
            materials=[],
            compiler_sdk=self.sdk_pins(),
            compiler_includes_sha256="authored includes",
            settings={"tier0": {}},
            outputs=[self.target(i) for i in (1, 2, 3)],
        )
        path = self.profile(profile)
        output = self.root / "standard"
        with patch.object(A, "legacy_particle_selections", return_value={}):
            result = A.produce_standard(path, P.sha(path), self.pc, self.sdk, output, self.codec, P.sha(self.codec))
        rows, types = self.assert_pack(output, result, [77] * 3)
        self.assertEqual([row["type_id"] for row in rows], [0, 0, 0])
        self.assertEqual(len(types), 1)

    def test_barrier_both_bodies_keep_the_original_descriptor(self):
        profile = dict(
            input_id=A.INPUT_ID,
            source_type=self.origin(),
            compiler_sdk=self.sdk_pins(),
            legacy_sdk=self.sdk_pins(self.legacy),
            compiler_includes_sha256="authored includes",
            legacy_includes_sha256="authored includes",
            template_inputs={},
            exporter_revision="authored",
            settings={"tier0": {}, "caching_preprocessor": False},
            source_filename="fixture.shader",
            outputs=[self.target(1), self.target(2)],
        )
        path = self.profile(profile)
        output = self.root / "barrier"
        addresses = {
            0x10335A3E8: struct.pack("<II", 0x00702842, 0x15),
            0x101B24EFC: struct.pack("<I", 0x528003E8),
            0x10003AF0C: bytes.fromhex("00008052c0035fd6"),
        }
        with (
            patch.object(P, "sdk_read", side_effect=lambda image, address, size: addresses.get(address, bytes(size))),
            patch.object(P, "construct", side_effect=lambda *a: deepcopy(self.shader)),
            patch.object(A.subprocess, "check_output", return_value=b"authored license"),
        ):
            result = A.produce(path, P.sha(path), self.pc, self.sdk, self.legacy, self.public, output, self.codec, P.sha(self.codec))
        rows, types = self.assert_pack(output, result, [77, 77])
        self.assertEqual([row["type_id"] for row in rows], [0, 0])
        self.assertEqual(len(types), 1)

    def test_context_aliases_keep_the_common_source_descriptor(self):
        provider = self.root / "provider"
        provider.mkdir()
        (provider / "objects.bin").write_bytes(self.body)
        source = dict(member="CAB-provider", path_id=11, bytes=len(self.body), sha256=self.origin()["body_sha256"])
        profile = dict(
            input_id=A.INPUT_ID,
            sdk=self.sdk_pins(),
            includes_sha256="authored includes",
            source_type=self.origin(),
            provider_profile_sha256="authored",
            provider_bundle="authored-provider",
            settings={},
            records=[dict(kind="sdk", sdk_shader=207, source_record=source, outputs=[self.target(1), self.target(2)])],
        )
        path = self.profile(profile)
        output = self.root / "context"
        snippets = [(pid, dict(m_Code="authored", m_IncludesHash={f"bytes[{i}]": 0 for i in range(16)})) for pid in (17, 29)]
        with (
            patch.object(C.O, "record_packs", return_value=({("CAB-provider", 11): (provider, dict(source, offset=0))}, [])),
            patch.object(C.O, "check_record_packs"),
            patch.object(SDK, "sdk_source", return_value={"m_CompileInfo": {"m_Snippets": snippets}}),
            patch.object(P, "editor_hash", return_value=bytes(16)),
        ):
            result = C.produce(path, P.sha(path), self.pc, self.sdk, None, provider, "authored", output, comparison="diagnostic")
        self.assert_pack(output, result, [77, 77])


if __name__ == "__main__":
    unittest.main()
