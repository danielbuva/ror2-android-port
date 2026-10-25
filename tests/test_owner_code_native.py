"""Native owner refuses mismatched metadata, source drift and unsafe outputs."""

import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

PATH = Path(__file__).resolve().parents[1] / "tools/phone-build/owner-code/native.py"
SPEC = importlib.util.spec_from_file_location("owner_code_native", PATH)
NATIVE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(NATIVE)


class OwnerCodeNativeTests(unittest.TestCase):
    def compiled_fixture(self, root):
        old_sdk, sdk, folder, output = [root / name for name in ("old-sdk", "sdk", "compiled", "relink")]
        for directory in (old_sdk, sdk, folder / "objects", folder / "job-results"):
            directory.mkdir(parents=True)
        for selected in (old_sdk, sdk):
            for name in ("sdk.c", "header.c"):
                (selected / name).write_text("// independent SDK witness\n")
        profile = {
            "input_id": "independent fixture",
            "compiler": "tools/clang",
            "arguments": [["-O2", "-c", "SOURCE", "-o", "OBJECT"]],
            "jobs": [{"sdk": "sdk.c", "arguments": 0}, {"generated": "Fixture.cpp", "arguments": 0}, {"lump": ["header.c"], "arguments": 0}],
            "link": ["-shared", {"object": 0}, {"object": 1}, {"object": 2}, "-o", "LIBRARY"],
        }
        old, current = NATIVE.plan(profile, old_sdk, folder), NATIVE.plan(profile, sdk, output)
        old["link"][1:4] = reversed(old["link"][1:4])
        generated = hashlib.sha256(b"independent generated source").hexdigest()
        inputs = {
            "sdk": {"sdk.c": NATIVE.sha(sdk / "sdk.c"), "header.c": NATIVE.sha(sdk / "header.c")},
            "sources": {"Fixture.cpp": {"path": str(sdk / "frame.gz"), "sha256": generated, "compressed": True}},
            "metadata": {"sha256": "independent metadata witness"},
            "converter_receipt_sha256": "independent converter witness",
            "android_tools": {str(sdk / "libclang.so"): "independent tool hash"},
            "linux_tools": None,
        }
        previous = {**inputs, "sources": {"Fixture.cpp": {**inputs["sources"]["Fixture.cpp"], "path": str(old_sdk / "frame.gz")}}}
        previous["android_tools"] = {str(old_sdk / "libclang.so"): "independent tool hash"}
        for index, job in enumerate(old["jobs"]):
            obj = folder / "objects" / (str(index) + ".o")
            obj.write_bytes(("independent compiled witness " + str(index)).encode())
            digest = (
                generated
                if index == 1
                else hashlib.sha256(NATIVE.lump_source(old["wrappers"][job["source"]]).encode()).hexdigest()
                if index == 2
                else NATIVE.sha(job["source"])
            )
            NATIVE.write(
                folder / "job-results" / (str(index) + ".json"), {"source_sha256": digest, "output_sha256": NATIVE.sha(obj), "bytes": obj.stat().st_size}
            )
        for name, value in {
            "plan": old,
            "inputs": previous,
            "result": {"success": True, "phase": "native-built", "input_id": profile["input_id"], "compile_tasks": 3},
        }.items():
            NATIVE.write(folder / (name + ".json"), value)
        return folder, current, profile, sdk, inputs

    def test_relink_admits_complete_owned_objects_across_roots_without_changing_compile_policy(self):
        with tempfile.TemporaryDirectory() as temporary:
            fixture = self.compiled_fixture(Path(temporary).resolve())
            rows = NATIVE.compiled_jobs(*fixture)
            self.assertEqual(len(rows), 3)
            self.assertEqual(rows[1][0].read_bytes(), b"independent compiled witness 1")

    def test_relocated_reused_lump_keeps_original_compile_hash_and_can_be_reused_again(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            folder, current, profile, sdk, inputs = self.compiled_fixture(root)
            rows = NATIVE.compiled_jobs(folder, current, profile, sdk, inputs)
            old_receipt = json.loads((folder / "job-results/2.json").read_text())
            self.assertEqual(rows[2][1]["source_sha256"], old_receipt["source_sha256"])
            self.assertEqual(rows[2][1]["lump_sdk_root"], str(root / "old-sdk"))
            continued = Path(current["library"]).parent
            for directory in (continued / "job-results", continued / "objects"):
                directory.mkdir(parents=True)
            for index, (obj, row) in enumerate(rows):
                NATIVE.os.link(obj, continued / "objects" / (str(index) + ".o"))
                NATIVE.write(continued / "job-results" / (str(index) + ".json"), row)
            for name, value in {
                "plan": current,
                "inputs": inputs,
                "result": {"success": True, "phase": "native-built", "input_id": profile["input_id"], "compile_tasks": 0, "reused_compile_tasks": 3},
            }.items():
                NATIVE.write(continued / (name + ".json"), value)
            readmitted = NATIVE.compiled_jobs(continued, NATIVE.plan(profile, sdk, root / "another-link"), profile, sdk, inputs)
            self.assertEqual(readmitted[2][1], rows[2][1])
            self.assertEqual(json.loads((folder / "job-results/2.json").read_text()), old_receipt)
            changed = {**rows[2][1], "lump_sdk_root": str(sdk)}
            (continued / "job-results/2.json").write_text(json.dumps(changed))
            with self.assertRaisesRegex(ValueError, "object/source receipt"):
                NATIVE.compiled_jobs(continued, NATIVE.plan(profile, sdk, root / "another-link"), profile, sdk, inputs)

    def test_relink_refuses_object_drift_or_changed_compilation_flags(self):
        with tempfile.TemporaryDirectory() as temporary:
            fixture = self.compiled_fixture(Path(temporary).resolve())
            fixture[1]["jobs"][0]["argv"].append("-fno-exceptions")
            with self.assertRaisesRegex(ValueError, "command policy"):
                NATIVE.compiled_jobs(*fixture)
            fixture[1]["jobs"][0]["argv"].pop()
            (fixture[0] / "objects/1.o").write_bytes(b"changed compiled input")
            with self.assertRaisesRegex(ValueError, "object/source"):
                NATIVE.compiled_jobs(*fixture)

    def test_relink_refuses_incomplete_compilation_and_changed_source_cohort(self):
        with tempfile.TemporaryDirectory() as temporary:
            fixture = self.compiled_fixture(Path(temporary).resolve())
            fixture[4]["sources"]["Fixture.cpp"]["sha256"] = "changed source witness"
            with self.assertRaisesRegex(ValueError, "source cohort"):
                NATIVE.compiled_jobs(*fixture)
            (fixture[0] / "result.json").write_text(json.dumps({"input_id": fixture[2]["input_id"], "compile_tasks": 2}))
            with self.assertRaisesRegex(ValueError, "complete original compilation"):
                NATIVE.compiled_jobs(*fixture)

    def test_active_timeout_subtracts_pause_when_parent_cannot_sample(self):
        child = Mock(args=["independent compiler"], poll=Mock(side_effect=[None, None, 0]))
        child.wait.side_effect = NATIVE.subprocess.TimeoutExpired(child.args, 0.1)
        record = {}
        # Parent sees only before/after a 100 second guard STOP interval.
        with patch.object(NATIVE, "paused_seconds", side_effect=[(10, 4), (10, 4), (111, 104), (112, 104)]):
            self.assertEqual(NATIVE.wait_active(child, 3, Path("clock"), record), 0)
        self.assertEqual(record, {"active_seconds": 2, "paused_seconds": 100})
        with patch.object(NATIVE, "paused_seconds", side_effect=[(10, 4), (14, 4)]):
            child.poll.return_value = None
            child.poll.side_effect = None
            with self.assertRaises(NATIVE.subprocess.TimeoutExpired):
                NATIVE.wait_active(child, 3, Path("clock"), {})

    def test_pause_clock_preserves_existing_pause_and_refuses_invalid_or_reset_state(self):
        with tempfile.TemporaryDirectory() as temporary:
            clock = Path(temporary) / "clock"
            clock.write_text(json.dumps({"paused_seconds": 7, "paused_at": 12}))
            with patch.object(NATIVE, "elapsed_clock", return_value=20):
                self.assertEqual(NATIVE.paused_seconds(clock), (20, 15))
            for total, at in [(-1, None), (True, None), (0, float("nan")), (0, 21)]:
                clock.write_text(json.dumps({"paused_seconds": total, "paused_at": at}))
                with patch.object(NATIVE, "elapsed_clock", return_value=20), self.assertRaises(ValueError):
                    NATIVE.paused_seconds(clock)
        for samples in [[(10, 4), (11, 3)], [(10, 4), (11, 6)]]:
            with patch.object(NATIVE, "paused_seconds", side_effect=samples), self.assertRaisesRegex(ValueError, "reset or exceeds"):
                NATIVE.wait_active(Mock(), 100, Path("clock"), {})

    def test_resume_reuses_498_receipts_and_only_compiles_missing_jobs(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            sdk, failed, output = [root / n for n in ("sdk", "failed", "continued")]
            for directory in (sdk, failed / "objects", failed / "job-results", root / "game", root / "sources"):
                directory.mkdir(parents=True)
            source = sdk / "fixture.c"
            source.write_bytes(b"independent SDK translation unit")
            receipt, metadata = root / "converter.json", root / "metadata.dat"
            receipt.write_text("independent converter witness")
            metadata.write_bytes(b"independent metadata witness")
            profile = {
                "input_id": "fixture",
                "compiler": "tools/clang",
                "objcopy": "tools/objcopy",
                "arguments": [["-c", "SOURCE", "-o", "OBJECT"]],
                "jobs": [{"sdk": "fixture.c", "arguments": 0} for _ in range(500)],
                "link": ["-shared", *[{"object": i} for i in range(500)], "-o", "LIBRARY"],
            }
            old = NATIVE.plan(profile, sdk, failed)
            inputs = {
                "inventory": {},
                "sdk": {},
                "converter_receipt_sha256": NATIVE.sha(receipt),
                "sources": {},
                "metadata": {},
                "android_tools": None,
                "linux_tools": None,
            }
            for index in range(498):
                obj = failed / "objects" / (str(index) + ".o")
                obj.write_bytes(("compiled fixture " + str(index)).encode())
                NATIVE.write(
                    failed / "job-results" / (str(index) + ".json"),
                    {"source_sha256": NATIVE.sha(source), "output_sha256": NATIVE.sha(obj), "bytes": obj.stat().st_size},
                )
            # A timed-out output is never a reusable object without its receipt.
            (failed / "objects/498.o").write_bytes(b"failed partial object")
            original_result = {"success": False, "phase": "compiling", "input_id": "fixture", "compile_tasks": 498}
            for name, value in {"plan": old, "inputs": inputs, "result": original_result}.items():
                NATIVE.write(failed / (name + ".json"), value)
            request = {
                "owner_work": str(root),
                "sdk_install": str(sdk),
                "converter_receipt": str(receipt),
                "converter_receipt_sha256": NATIVE.sha(receipt),
                "sources": str(root / "sources"),
                "sources_compressed": False,
                "metadata": str(metadata),
                "output": str(output),
                "resume": str(failed),
                "compile_timeout_seconds": 7200,
            }
            invoked = []

            def invoke(argv, where, name, **kwargs):
                invoked.append(name)
                if name.isdigit():
                    self.assertEqual(kwargs["timeout"], 7200)
                    Path(argv[-1]).write_bytes(b"fresh missing object")
                elif name == "link":
                    Path(argv[-1]).write_bytes(b"unstripped fixture")
                elif name == "strip":
                    header = bytearray(64)
                    header[:6] = b"\x7fELF\x02\x01"
                    struct.pack_into("<HH", header, 16, 3, 183)
                    Path(argv[-1]).write_bytes(header)

            with (
                patch.object(NATIVE, "input_state", return_value=("fixture", root / "game", {})),
                patch.object(NATIVE, "sdk_files", return_value={}),
                patch.object(NATIVE, "converter_inputs", return_value=({}, {})),
                patch.object(NATIVE.shutil, "disk_usage", return_value=SimpleNamespace(free=10 * 1024**3)),
                patch.object(NATIVE, "invoke", side_effect=invoke),
            ):
                # Metadata result must carry the validated source receipt hash.
                with patch.object(NATIVE, "converter_inputs", return_value=({}, {"sha256": "metadata witness"})):
                    inputs["metadata"] = {"sha256": "metadata witness"}
                    (failed / "inputs.json").write_text(json.dumps(inputs))
                    for selection in ([], [True], [-1], [500], [497, 497]):
                        with self.assertRaisesRegex(ValueError, "measurement job indexes"):
                            NATIVE.run({**request, "output": str(root / "invalid-measure"), "measure_jobs": selection}, profile=profile)
                        self.assertFalse((root / "invalid-measure").exists())
                    measured_output = root / "measurement"
                    measured = NATIVE.run({**request, "output": str(measured_output), "measure_jobs": [497, 499]}, profile=profile)
                    self.assertEqual(invoked, ["497", "499"])
                    self.assertEqual((measured["phase"], measured["compile_tasks"], measured["reused_compile_tasks"]), ("native-measured", 2, 0))
                    self.assertFalse((measured_output / "libil2cpp.so").exists())
                    self.assertNotEqual((measured_output / "objects/497.o").stat().st_ino, (failed / "objects/497.o").stat().st_ino)
                    with self.assertRaisesRegex(ValueError, "complete original compilation"):
                        NATIVE.compiled_jobs(measured_output, NATIVE.plan(profile, sdk, root / "measurement-relink"), profile, sdk, inputs)
                    invoked.clear()
                    result = NATIVE.run(request, profile=profile)
            self.assertEqual(invoked, ["498", "499", "link", "strip"])
            self.assertEqual((result["compile_tasks"], result["reused_compile_tasks"]), (2, 498))
            self.assertEqual(json.loads((failed / "result.json").read_text()), original_result)
            self.assertEqual((failed / "objects/498.o").read_bytes(), b"failed partial object")
            self.assertEqual((output / "objects/497.o").stat().st_ino, (failed / "objects/497.o").stat().st_ino)
            self.assertEqual(len(NATIVE.compiled_jobs(output, NATIVE.plan(profile, sdk, root / "relink"), profile, sdk, inputs)), 500)

    def test_resume_refuses_missing_receipts_and_changed_providers_but_allows_corrected_link(self):
        with tempfile.TemporaryDirectory() as temporary:
            fixture = self.compiled_fixture(Path(temporary).resolve())
            folder, current, profile, sdk, inputs = fixture
            old = json.loads((folder / "plan.json").read_text())
            old["link"][1:4] = reversed(old["link"][1:4])
            (folder / "plan.json").write_text(json.dumps(old))
            (folder / "result.json").write_text(json.dumps({"success": False, "phase": "compiling", "input_id": profile["input_id"], "compile_tasks": 2}))
            (folder / "job-results/2.json").unlink()
            self.assertEqual(len(NATIVE.compiled_jobs(*fixture, resume=True)), 2)
            inputs["sources"]["Fixture.cpp"]["sha256"] = "changed"
            with self.assertRaisesRegex(ValueError, "source cohort"):
                NATIVE.compiled_jobs(*fixture, resume=True)
            inputs["sources"]["Fixture.cpp"]["sha256"] = json.loads((folder / "inputs.json").read_text())["sources"]["Fixture.cpp"]["sha256"]
            current["link"].append("-changed-link-option")
            self.assertEqual(len(NATIVE.compiled_jobs(*fixture, resume=True)), 2)
            current["jobs"][0]["argv"].append("-changed-compile-option")
            with self.assertRaisesRegex(ValueError, "command policy"):
                NATIVE.compiled_jobs(*fixture, resume=True)
            current["jobs"][0]["argv"].pop()
            (folder / "job-results/1.json").unlink()
            with self.assertRaisesRegex(ValueError, "job receipts"):
                NATIVE.compiled_jobs(*fixture, resume=True)

    def test_burst_ndk_layout_keeps_original_target_data_and_selects_linux_bfd(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            sdk = root / "sdk"
            original = sdk / "PlaybackEngines/AndroidPlayer/NDK"
            data = original / "toolchains/llvm/prebuilt/darwin-x86_64"
            data.mkdir(parents=True)
            (original / "source.properties").write_text("independent SDK properties")
            for name in ("lib", "lib64", "include", "sysroot", "aarch64-linux-android"):
                (data / name).mkdir()
            tools = {}
            for role in ("clang", "linker", "objcopy"):
                path = root / role
                path.write_bytes(b"independent GNU tool witness")
                tools[role] = str(path)
            ndk = NATIVE.burst_ndk(sdk, tools, root / "layout")
            host = ndk / "toolchains/llvm/prebuilt/linux-x86_64"
            self.assertEqual((host / "bin/ld").resolve(), Path(tools["linker"]))
            self.assertEqual((host / "sysroot").resolve(), data / "sysroot")
            self.assertEqual((original / "source.properties").read_text(), "independent SDK properties")

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

    def test_target_link_keeps_recorded_sdk_and_generated_order(self):
        profile = {
            "jobs": [
                {"sdk": "first.c", "arguments": 0},
                {"sdk": "second.c", "arguments": 0},
                {"generated": "Removed.cpp", "arguments": 1},
                {"generated": "Z.cpp", "arguments": 1},
                {"generated": "A.cpp", "arguments": 1},
            ],
            "link": ["-shared", {"object": 3}, {"object": 1}, {"object": 2}, {"object": 4}, {"object": 0}, "-llog"],
        }
        result = NATIVE.generated_profile(profile, {"cpp/A.cpp": {}, "cpp/C.cpp": {}, "cpp/Z.cpp": {}})
        self.assertEqual([row.get("generated") for row in result["jobs"]], [None, None, "A.cpp", "C.cpp", "Z.cpp"])
        self.assertEqual(result["link"], ["-shared", {"object": 4}, {"object": 1}, {"object": 2}, {"object": 3}, {"object": 0}, "-llog"])
        self.assertEqual(profile["link"][1], {"object": 3})

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
