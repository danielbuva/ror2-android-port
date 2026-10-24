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
    def test_target_conversion_replaces_generated_units_and_rebuilds_link_closure(self):
        profile = {
            "jobs": [{"sdk": "sdk.c", "arguments": 0}, {"generated": "Old.cpp", "arguments": 4}, {"generated": "Old.c", "arguments": 5}],
            "link": ["-shared", {"object": 0}, {"object": 1}, {"object": 2}, "-llog"],
        }
        result = NATIVE.generated_profile(profile, {"cpp/New.cpp": {}, "cpp/Register.c": {}, "data/metadata.dat": {}})
        self.assertEqual(
            result["jobs"], [{"sdk": "sdk.c", "arguments": 0}, {"generated": "New.cpp", "arguments": 4}, {"generated": "Register.c", "arguments": 5}]
        )
        self.assertEqual(result["link"], ["-shared", {"object": 0}, {"object": 1}, {"object": 2}, "-llog"])
        self.assertEqual(profile["jobs"][1]["generated"], "Old.cpp")
        with self.assertRaisesRegex(ValueError, "no native"):
            NATIVE.generated_profile(profile, {"data/metadata.dat": {}})
        with self.assertRaisesRegex(ValueError, "nested"):
            NATIVE.generated_profile(profile, {"cpp/nested/New.cpp": {}})

    def test_json_tool_stdout_is_separate_from_runtime_diagnostics(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            (root / "logs").mkdir()
            (root / "tmp").mkdir()
            NATIVE.invoke(
                [sys.executable, "-c", "import sys;print('{\"value\":7}');print('diagnostic witness',file=sys.stderr)"], root, "query", separate_stderr=True
            )
            self.assertEqual(json.loads((root / "logs/query.log").read_text()), {"value": 7})
            self.assertEqual((root / "logs/query.stderr.log").read_text().strip(), "diagnostic witness")

    def test_linux_driver_child_is_quoted_and_policy_is_not_rewritten(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            (output / "logs").mkdir()
            tools = {
                "qemu": "/runner/qemu",
                "clang": "/owner tools/clang9",
                "linker": "/owner tools/ld.bfd",
                "loader_root": "/gnu",
                "library_dirs": ["/gnu/lib"],
            }
            calls = []

            def invoked(argv, where, name, **kwargs):
                calls.append((argv, kwargs))
                if name.endswith("-driver"):
                    (where / "logs" / (name + ".log")).write_text('driver diagnostics\n"/owner tools/clang9" "-cc1" "-Os" "-o" "/result/object.o"\n')

            with patch.object(NATIVE, "invoke", side_effect=invoked):
                NATIVE.linux_invoke(["sdk-clang", "-Os", "-target", "aarch64-linux-android22"], output, "compile", Path("/sdk"), tools, env={})
            self.assertIn("-Os", calls[0][0])
            self.assertIn("--sysroot=/sdk/PlaybackEngines/AndroidPlayer/NDK/toolchains/llvm/prebuilt/darwin-x86_64/sysroot", calls[0][0])
            self.assertEqual(calls[1][0][-5:], [tools["clang"], "-cc1", "-Os", "-o", "/result/object.o"])
            self.assertEqual(calls[1][1]["timeout"], 3600)

    def test_linux_driver_refuses_multiple_children_and_unexpected_compilers(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            (output / "logs").mkdir()
            tools = {"qemu": "/runner", "clang": "/clang9", "linker": "/ld.bfd", "loader_root": "/gnu", "library_dirs": ["/gnu/lib"]}
            for text in ['"/clang9" "-cc1"\n"/other" "input"\n', '"/other" "-cc1"\n']:
                with self.subTest(driver=text):

                    def invoked(argv, where, name, **kwargs):
                        self.assertTrue(name.endswith("-driver"))
                        (where / "logs" / (name + ".log")).write_text(text)

                    with patch.object(NATIVE, "invoke", side_effect=invoked), self.assertRaisesRegex(ValueError, "driver did not"):
                        NATIVE.linux_invoke(["sdk-clang"], output, "compile", Path("/sdk"), tools, env={})

    def test_linux_runtime_and_ndk_inputs_are_hashed(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            tools = {}
            for n in ("qemu", "clang", "linker", "objcopy"):
                p = root / n
                p.write_bytes(b"independent generic tool fixture")
                tools[n] = str(p)
            loader = root / "gnu"
            libs = loader / "lib"
            libs.mkdir(parents=True)
            library = libs / "libc.so.6"
            library.write_bytes(b"independent GNU runtime fixture")
            tools.update(loader_root=str(loader), library_dirs=[str(libs)])
            state = NATIVE.linux_tool_state(tools)
            library.write_bytes(b"changed runtime")
            self.assertNotEqual(NATIVE.linux_tool_state(tools), state)
            del tools["linker"]
            with self.assertRaisesRegex(ValueError, "explicit Linux runner"):
                NATIVE.linux_tool_state(tools)

    def test_android_link_keeps_original_target_and_explicit_static_runtime(self):
        tools = {"clang": "/installed/libclang.so", "linker": "/installed/liblld.so", "resource_dir": "/tools/clang/21"}
        sdk = Path("/owner/sdk")
        args = ["host-clang", "-target", "aarch64-linux-android22", "-Os", "-fuse-ld=bfd", "-static-libstdc++", "-Wl,--no-undefined", "source.o"]
        command = NATIVE.android_command(args, sdk, tools, link=True)
        self.assertEqual(command[0], tools["clang"])
        self.assertIn("-fintegrated-cc1", command)
        self.assertIn("aarch64-linux-android22", command)
        self.assertIn("-Os", command)
        self.assertIn("-Wl,--no-undefined", command)
        self.assertNotIn("-fuse-ld=bfd", command)
        self.assertNotIn("-static-libstdc++", command)
        self.assertIn("--ld-path=/installed/liblld.so", command)
        self.assertIn("--unwindlib=none", command)
        self.assertTrue(any(v.startswith(str(sdk)) and v.endswith("libc++_static.a") for v in command))
        self.assertTrue(any(v.startswith(str(sdk)) and v.endswith("libgcc.a") for v in command))

    def test_android_resource_inputs_are_bound_and_incomplete_selection_refuses(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            tools = {}
            for name in ("dotnet", "clang", "linker", "objcopy"):
                path = root / name
                path.write_bytes(b"authored tool stand-in")
                tools[name] = str(path)
            resources = root / "resources"
            resources.mkdir()
            header = resources / "fixture.h"
            header.write_text("// independent header")
            tools["resource_dir"] = str(resources)
            before = NATIVE.android_tool_state(tools)
            header.write_text("// changed header")
            self.assertNotEqual(NATIVE.android_tool_state(tools), before)
            with self.assertRaisesRegex(ValueError, "explicit Android"):
                NATIVE.android_tool_state({})

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
