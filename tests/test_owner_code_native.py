"""Native owner refuses mismatched metadata, source drift and unsafe outputs."""

import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch

PATH = Path(__file__).resolve().parents[1] / "tools/phone-build/owner-code/native.py"
SPEC = importlib.util.spec_from_file_location("owner_code_native", PATH)
NATIVE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(NATIVE)


class OwnerCodeNativeTests(unittest.TestCase):
    def test_source_expansion_is_bounded_and_hash_checked(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            data = b"// independent native owner fixture\n"
            packed = root / "fixture.cpp.gz"
            packed.write_bytes(gzip.compress(data))
            row = {
                "path": str(packed),
                "provider_sha256": NATIVE.sha(packed),
                "bytes": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
                "compressed": True,
            }
            NATIVE.expand(row, root / "exact.cpp")
            self.assertEqual((root / "exact.cpp").read_bytes(), data)
            with self.assertRaisesRegex(ValueError, "exceeds"):
                NATIVE.expand(row | {"bytes": len(data) - 1}, root / "failed.cpp")
            self.assertEqual(gzip.decompress(packed.read_bytes()), data)
            packed.write_bytes(gzip.compress(data + b"drift"))
            with self.assertRaisesRegex(ValueError, "provider drift"):
                NATIVE.expand(row, root / "drift.cpp")
            self.assertFalse((root / "drift.cpp").exists())

    def test_metadata_and_source_membership_bound_to_same_converter(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            source = root / "Fixture.cpp"
            source.write_text("// independently authored fixture\n")
            metadata = root / "metadata.dat"
            metadata.write_bytes(struct.pack("<II", 0xFAB11BAF, 31))
            receipt = root / "converter.json"
            rows = {
                "cpp/Fixture.cpp": {"bytes": source.stat().st_size, "sha256": NATIVE.sha(source)},
                "data/Metadata/global-metadata.dat": {"bytes": metadata.stat().st_size, "sha256": NATIVE.sha(metadata)},
            }
            receipt.write_text(json.dumps({"exit_code": 0, "inputs_unchanged": True, "files": rows}))
            profile = {"jobs": [{"generated": "Fixture.cpp"}]}
            providers, actual = NATIVE.converter_inputs(receipt, NATIVE.sha(receipt), root, metadata, profile, False)
            self.assertEqual(set(providers), {"Fixture.cpp"})
            self.assertEqual(actual, rows["data/Metadata/global-metadata.dat"])
            metadata.write_bytes(struct.pack("<II", 0xFAB11BAF, 29))
            with self.assertRaisesRegex(ValueError, "same converter"):
                NATIVE.converter_inputs(receipt, NATIVE.sha(receipt), root, metadata, profile, False)
            with self.assertRaisesRegex(ValueError, "membership differs"):
                NATIVE.converter_inputs(receipt, NATIVE.sha(receipt), root, metadata, {"jobs": []}, False)

    def test_new_output_and_path_bindings_cannot_escape(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            source = root / "source"
            source.mkdir()
            with self.assertRaisesRegex(ValueError, "overlap"):
                NATIVE.disjoint(source / "output", [source])
            alias = root / "alias"
            alias.symlink_to(source, target_is_directory=True)
            with self.assertRaisesRegex(ValueError, "canonical"):
                NATIVE.canonical(alias)
            with self.assertRaisesRegex(ValueError, "relative"):
                NATIVE.arguments([{"root": "sdk", "path": "../escape"}], {"sdk": source})
            with self.assertRaisesRegex(ValueError, "unbound"):
                NATIVE.arguments(["@unknown.rsp"], {})
            self.assertEqual(NATIVE.arguments([{"root": "output", "path": ".", "prefix": "-I"}], {"output": root}), ["-I" + str(root)])

    def test_failed_tool_has_terminal_process_receipt(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            (root / "logs").mkdir()
            (root / "tmp").mkdir()
            with self.assertRaisesRegex(RuntimeError, "native stage failed"):
                NATIVE.invoke([sys.executable, "-c", "print('failure witness');raise SystemExit(7)"], root, "failed")
            self.assertIn("failure witness", (root / "logs/failed.log").read_text())
            self.assertEqual(json.loads((root / "logs/failed.process.json").read_text())["exit_code"], 7)

    def test_implicit_ndk_linker_and_header_drift_refuse(self):
        with tempfile.TemporaryDirectory() as temporary:
            sdk = Path(temporary).resolve()
            names = [
                "Unity.app/Contents/il2cpp/libil2cpp/fixture.h",
                "Unity.app/Contents/il2cpp/external/fixture.c",
                "PlaybackEngines/AndroidPlayer/NDK/bin/clang++",
                "PlaybackEngines/AndroidPlayer/NDK/bin/objcopy",
                "PlaybackEngines/AndroidPlayer/NDK/bin/ld.bfd",
                "PlaybackEngines/AndroidPlayer/NDK/sysroot/usr/include/fixture.h",
                "PlaybackEngines/AndroidPlayer/NDK/source.properties",
                "PlaybackEngines/AndroidPlayer/Variations/il2cpp/Development/StaticLibs/arm64-v8a/baselib.a",
            ]
            rows = {}
            for name in names:
                path = sdk / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("independent SDK boundary fixture: " + name)
                rows[name] = NATIVE.sha(path)
            profile = {
                "compiler": names[2],
                "objcopy": names[3],
                "sdk_files": len(rows),
                "sdk_digest": hashlib.sha256(json.dumps(rows, sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
            }
            self.assertEqual(NATIVE.sdk_files(sdk, profile), rows)
            for name in names[4:6]:
                path = sdk / name
                original = path.read_bytes()
                path.write_bytes(original + b"drift")
                with self.assertRaisesRegex(ValueError, "SDK source/tool cohort differs"):
                    NATIVE.sdk_files(sdk, profile)
                path.write_bytes(original)

    def test_provider_change_after_planning_has_failed_terminal_result(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            work, sdk, sources = [root / n for n in ("work", "sdk", "sources")]
            for path in (work, sdk, sources, root / "game"):
                path.mkdir()
            source = sources / "Fixture.cpp"
            source.write_text("// independently authored source\n")
            metadata = root / "metadata.dat"
            metadata.write_bytes(struct.pack("<II", 0xFAB11BAF, 31))
            receipt = root / "converter.json"
            receipt.write_text(
                json.dumps(
                    {
                        "exit_code": 0,
                        "inputs_unchanged": True,
                        "files": {
                            "cpp/Fixture.cpp": {"bytes": source.stat().st_size, "sha256": NATIVE.sha(source)},
                            "data/Metadata/global-metadata.dat": {"bytes": metadata.stat().st_size, "sha256": NATIVE.sha(metadata)},
                        },
                    }
                )
            )
            profile = root / "profile.json"
            profile.write_text(
                json.dumps(
                    {
                        "input_id": "fixture",
                        "compiler": "compiler",
                        "arguments": [["SOURCE", "-o", "OBJECT"]],
                        "jobs": [{"arguments": 0, "generated": "Fixture.cpp"}],
                        "link": [{"object": 0}, "-o", "LIBRARY"],
                    }
                )
            )
            request = {
                "owner_work": str(work),
                "sdk_install": str(sdk),
                "converter_receipt": str(receipt),
                "converter_receipt_sha256": NATIVE.sha(receipt),
                "sources": str(sources),
                "sources_compressed": False,
                "metadata": str(metadata),
                "output": str(work / "output"),
            }
            original_plan = NATIVE.plan

            def mutate_after_plan(*args):
                result = original_plan(*args)
                source.write_text("// changed provider\n")
                return result

            with (
                patch.object(NATIVE, "PROFILE", profile),
                patch.object(NATIVE, "PROFILE_SHA", NATIVE.sha(profile)),
                patch.object(NATIVE, "sdk_files", return_value={}),
                patch.object(NATIVE, "input_state", return_value=("fixture", root / "game", {})),
                patch.object(NATIVE, "plan", side_effect=mutate_after_plan),
            ):
                with self.assertRaisesRegex(ValueError, "converter providers changed"):
                    NATIVE.run(request, plan_only=True)
            result = json.loads((work / "output/result.json").read_text())
            self.assertFalse(result["success"])
            self.assertEqual(result["compile_tasks"], 0)

    def test_profile_pins_exact_compile_link_closure(self):
        self.assertEqual(NATIVE.sha(NATIVE.PROFILE), NATIVE.PROFILE_SHA)
        profile = json.loads(NATIVE.PROFILE.read_text())
        self.assertEqual(len(profile["arguments"]), 6)
        self.assertEqual(len(profile["jobs"]), 825)
        objects = [v["object"] for v in profile["link"] if isinstance(v, dict) and "object" in v]
        self.assertEqual(sorted(objects), list(range(825)))
        self.assertEqual(sum("generated" in j for j in profile["jobs"]), 687)
        self.assertEqual(sum("lump" in j for j in profile["jobs"]), 67)
        self.assertNotIn("/Users/", NATIVE.PROFILE.read_text())


if __name__ == "__main__":
    unittest.main()
