#!/usr/bin/env python3
"""Offline, no-game synthetic transformation and preservation tests."""

from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import types
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1] / "work/tests/wwise-android-abi"
DOTNET = Path(os.environ.get("WWISE_DOTNET") or shutil.which("dotnet") or "")
CECIL = Path(os.environ.get("WWISE_CECIL") or "")
OS_REWRITE = {
    "assembly": "ShapeFixture",
    "type": "AkSoundEngine",
    "method": "StringFromIntPtrOSString",
    "return_type": "System.String",
    "parameter_types": ["System.IntPtr"],
    "expected_target": "System.String AkSoundEngine::StringFromIntPtrWString(System.IntPtr)",
    "replacement_target": "System.String AkSoundEngine::StringFromIntPtrString(System.IntPtr)",
    "expected_instruction_count": 3,
    "android_source": "synthetic/android/AkSoundEngine.cs",
    "reason": "synthetic method-body rewrite contract",
}


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_generator():
    path = HERE / "generate.py"
    module = types.ModuleType("wwise_abi_generate")
    module.__file__ = str(path)
    exec(compile(path.read_text(), str(path), "exec"), module.__dict__)
    return module


def marshal_name(info):
    if info is None:
        return []
    if info["kind"] == "ArrayMarshalInfo":
        name = "LPArray"
    else:
        name = info["properties"]["NativeType"]
    return ["UnmanagedType." + name]


def declaration(row):
    args = []
    for p in row["parameters"]:
        typ = p["type"][:-1] if p["type"].endswith("&") else p["type"]
        args.append(
            {
                "type": typ,
                "direction": p["direction"],
                "marshal": marshal_name(p["marshal"]),
                "attributes": sorted(x for x in p["attributes"].split(", ") if x != "None"),
                "custom_attributes": p["customAttributes"],
            }
        )
    return {
        "entrypoint": row["entrypoint"],
        "library": row["library"],
        "calling_convention": row["calling_convention"],
        "charset": row["charset"],
        "best_fit_mapping": row["best_fit_mapping"],
        "throw_on_unmappable_char": row["throw_on_unmappable_char"],
        "raw_pinvoke_flags": row["raw_pinvoke_flags"],
        "exact_spelling": "true" if row["exact_spelling"] else "default",
        "set_last_error": "true" if row["set_last_error"] else "default",
        "return": row["return_type"],
        "return_marshal": marshal_name(row["return_marshal"]),
        "return_attributes": row["return_attributes"],
        "method_custom_attributes": row["method_custom_attributes"],
        "return_custom_attributes": row["return_custom_attributes"],
        "args": args,
    }


@unittest.skipUnless(DOTNET.is_file() and CECIL.is_file(), "source scripts/env.sh and select the Unity-bundled Mono.Cecil with WWISE_CECIL")
class WriterRoundTripTests(unittest.TestCase):
    def setUp(self):
        ROOT.mkdir(parents=True, exist_ok=True)
        (ROOT / "work").mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix="wwise-v6-synthetic-", dir=ROOT / "work")
        self.root = Path(self.temp.name)
        self.repo = self.root / "test-repo"
        (self.repo / "work/config").mkdir(parents=True)
        (self.repo / "work/game-install").mkdir(parents=True)
        (self.repo / ".gitignore").write_text("work/\n")
        subprocess.run(["git", "init", "-q"], cwd=self.repo, check=True)
        (self.repo / "work/config/local.json").write_text(json.dumps({"game_path": str(self.repo / "work/game-install")}))
        self.tool = self.root / "inspector"
        self.writer = self.root / "writer-test-only"
        self.fixture_dir = self.root / "fixture"
        for argv in (
            [
                str(DOTNET),
                "build",
                str(HERE / "CecilAbiTool.csproj"),
                "-o",
                str(self.tool),
                "-p:BaseIntermediateOutputPath=" + str(self.root / "obj-inspector") + os.sep,
                "-p:CecilPath=" + str(CECIL),
                "-p:UseSharedCompilation=false",
                "--nologo",
            ],
            [
                str(DOTNET),
                "build",
                str(HERE / "CecilAbiWriter.csproj"),
                "-o",
                str(self.writer),
                "-p:BaseIntermediateOutputPath=" + str(self.root / "obj-writer") + os.sep,
                "-p:CecilPath=" + str(CECIL),
                "-p:DefineConstants=WWISE_TEST_ONLY",
                "-p:UseSharedCompilation=false",
                "--nologo",
            ],
            [
                str(DOTNET),
                "build",
                str(HERE / "synthetic/ShapeFixture.csproj"),
                "-o",
                str(self.fixture_dir),
                "-p:BaseIntermediateOutputPath=" + str(self.root / "obj-fixture") + os.sep,
                "-p:UseSharedCompilation=false",
                "--nologo",
            ],
        ):
            result = subprocess.run(argv, cwd=self.root, text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assembly = self.fixture_dir / "ShapeFixture.dll"
        self.rows = self.inspect(self.assembly)

    def tearDown(self):
        self.temp.cleanup()

    def test_android_declaration_parser_rejects_unencoded_method_attributes(self):
        module = load_generator()
        source = self.root / "android-declaration.cs"
        source.write_text(
            '[global::Fixture.Marker(7)]\n[global::System.Runtime.InteropServices.DllImport("lib", EntryPoint="x")]\npublic static extern int X();\n'
        )
        with self.assertRaisesRegex(ValueError, "unsupported extra Android method/return custom attribute"):
            module.parse_android_source(source)

    def test_production_policy_keeps_audio_disabled_and_all_unavailable_imports(self):
        policy_path = HERE.parents[1] / "recipe/wwise-android-abi.json"
        policy = json.loads(policy_path.read_text())
        self.assertEqual(policy["status"], "draft-incomplete-android-only")
        self.assertFalse(policy["enable_production_audio"])
        self.assertEqual(policy["counts"]["unavailable_imports"], 11)
        self.assertEqual(len(policy["unavailable"]), 11)
        self.assertEqual(len(policy["managed_call_rewrites"]), 1)
        rewrite = policy["managed_call_rewrites"][0]
        self.assertEqual(rewrite["method"], "StringFromIntPtrOSString")
        self.assertEqual(rewrite["expected_target"], "System.String AkSoundEngine::StringFromIntPtrWString(System.IntPtr)")
        self.assertEqual(rewrite["replacement_target"], "System.String AkSoundEngine::StringFromIntPtrString(System.IntPtr)")

    def test_identical_plan_and_candidate_paths_refuse_before_publication(self):
        module = load_generator()
        output = self.repo / "work/same-output.dll"
        with self.assertRaisesRegex(ValueError, "plan and candidate output paths must be distinct on this filesystem"):
            module.assert_distinct_outputs(output, output)
        self.assertFalse(output.exists())

    def test_portable_basename_contract_rejects_case_and_normalization_aliases_early(self):
        module = load_generator()
        for name in ("final-plan.local.json", "candidate_v1.dll", "a-1.json", "a" * 128):
            module.validate_output_basename(Path(name))
        invalid_names = (
            "Uppercase.json",
            "café-plan.json",
            "cafe\u0301-plan.json",
            "trailing-dot.",
            "double..dot.json",
            "_leading.json",
            "-leading.json",
            "x" * 129,
        )
        for name in invalid_names:
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, "lowercase ASCII artifact"):
                module.validate_output_basename(Path(name))

        # Verify invalid Unicode leaves are rejected before the accepted-input
        # gate or any source/plugin analysis is reached. This is the same
        # composed/decomposed pair that can alias on normalization-insensitive
        # APFS even when the volume is case-sensitive.
        argv = [
            "generate.py",
            "--android-source",
            "unused.cs",
            "--android-os-string-source",
            "unused-os-string.cs",
            "--native-so",
            "unused.so",
            "--llvm-nm",
            "unused-nm",
            "--output",
            str(self.repo / "work/café.json"),
            "--candidate",
            str(self.repo / "work/cafe\u0301.json"),
        ]
        with patch("sys.argv", argv), patch.object(module, "accepted_managed_input", side_effect=AssertionError("input analysis must not run")):
            with self.assertRaisesRegex(ValueError, "lowercase ASCII artifact"):
                module.main()

    def test_existing_parent_aliases_are_refused_for_missing_leaves(self):
        module = load_generator()
        parent = self.repo / "work"
        # Existing parent spellings may alias even though the leaf targets are
        # both missing; samefile catches this independent of leaf name rules.
        primary_parent = parent / "ExistingParent"
        primary_parent.mkdir()
        alternate_parent = parent / "existingparent"
        if not alternate_parent.exists():
            alternate_parent.mkdir()
        parent_output = primary_parent / "missing-plan.json"
        parent_candidate = alternate_parent / "missing-plan.json"
        self.assertFalse(parent_output.exists())
        self.assertFalse(parent_candidate.exists())
        if os.path.samefile(primary_parent, alternate_parent):
            with self.assertRaisesRegex(ValueError, "distinct on this filesystem"):
                module.assert_distinct_outputs(parent_output, parent_candidate)
        else:
            module.assert_distinct_outputs(parent_output, parent_candidate)
        self.assertFalse(parent_output.exists())
        self.assertFalse(parent_candidate.exists())

    def inspect(self, assembly: Path):
        result = subprocess.run(
            [str(DOTNET), str(self.tool / "CecilAbiTool.dll"), "--inspect-pinvoke", str(assembly)], cwd=self.root, text=True, capture_output=True
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return json.loads(result.stdout)["imports"]

    def build_plan(self):
        by_name = {r["entrypoint"]: r for r in self.rows}
        self.assertEqual(set(by_name), {"game-string", "pointer", "byref", "in", "out", "sz-array", "rank-two", "sized-array", "sized-array-return"})
        mapped = []
        for row in self.rows:
            game = declaration(row)
            target = json.loads(json.dumps(game))
            target_name = row["entrypoint"]
            rewrites = []
            if target_name == "game-string":
                target_name = "android-string"
                target["entrypoint"] = target_name
                target["args"][0]["marshal"] = ["UnmanagedType.LPStr"]
                rewrites = [0]
            mapped.append(
                {"source_entrypoint": row["entrypoint"], "target_entrypoint": target_name, "parameter_lpstr_indices": rewrites, "game": game, "android": target}
            )
        plan = {
            "schema": 1,
            "status": "draft_incomplete_android_candidate",
            "full_enable_ready": False,
            "input_assembly_sha256": digest(self.assembly.read_bytes()),
            "counts": {"source_imports": len(mapped), "mapped_imports": len(mapped)},
            "imports": mapped,
            "unavailable": [],
            "managed_call_rewrites": [OS_REWRITE],
            "android_os_string_source_sha256": "0" * 64,
        }
        return plan

    def invoke_writer(self, plan_path: Path, output: Path, assembly: Path | None = None, mode: str = "--synthetic-test"):
        policy = self.repo / "work/synthetic-policy.json"
        policy.write_text(
            json.dumps({"schema": 1, "profile": "synthetic-test", "official_android_os_string_source_sha256": "0" * 64, "managed_call_rewrites": [OS_REWRITE]})
        )
        return subprocess.run(
            [str(DOTNET), str(self.writer / "CecilAbiWriter.dll"), mode, str(assembly or self.assembly), str(plan_path), str(policy), str(output)],
            cwd=self.repo,
            text=True,
            capture_output=True,
        )

    def test_successful_transformation_round_trip_and_path_guards(self):
        plan = self.build_plan()
        plan_path = self.repo / "work/synthetic-plan.json"
        plan_path.write_text(json.dumps(plan, sort_keys=True, indent=2))
        candidate = self.repo / "work/candidate.dll"
        result = self.invoke_writer(plan_path, candidate)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(candidate.is_file())
        self.assertIn('"mapped":9', result.stdout)
        self.assertIn('"managed_call_rewrites":1', result.stdout)
        self.assertIn(b"fixture-payload-v1", candidate.read_bytes())

        after = {r["entrypoint"]: r for r in self.inspect(candidate)}
        self.assertIn("android-string", after)
        self.assertNotIn("game-string", after)
        self.assertEqual(marshal_name(after["android-string"]["parameters"][0]["marshal"]), ["UnmanagedType.LPStr"])
        for name in ("pointer", "byref", "in", "out", "sz-array", "rank-two", "sized-array", "sized-array-return"):
            self.assertIn(name, after)
            before = next(r for r in self.rows if r["entrypoint"] == name)
            self.assertEqual(after[name]["parameters"], before["parameters"])
            self.assertEqual(after[name]["return_marshal"], before["return_marshal"])
        for key in ("method_custom_attributes", "return_custom_attributes"):
            self.assertTrue(after["android-string"][key])
            self.assertTrue(after["android-string"][key][0]["raw_blob_base64"])
        self.assertTrue(after["android-string"]["parameters"][0]["customAttributes"][0]["raw_blob_base64"])
        # Successful writer re-opened and compared layout, field/method/return/
        # parameter attribute blobs, IL, locals, EH, and resource fingerprints.

        # Tamper only with the expected Android custom-attribute payload. The
        # writer must reject after writing its sibling temporary, and clean it.
        changed = json.loads(json.dumps(plan))
        string_row = next(x for x in changed["imports"] if x["source_entrypoint"] == "game-string")
        string_row["android"]["args"][0]["custom_attributes"][0]["raw_blob_base64"] = "AA=="
        tampered = self.repo / "work/tampered-plan.json"
        tampered.write_text(json.dumps(changed, sort_keys=True, indent=2))
        refused_output = self.repo / "work/refused.dll"
        refused = self.invoke_writer(tampered, refused_output)
        self.assertNotEqual(refused.returncode, 0)
        self.assertIn("custom-attribute payload mismatch", refused.stderr)
        self.assertFalse(refused_output.exists())
        self.assertFalse(list(refused_output.parent.glob("refused.dll.tmp-*")))

        inside_install = self.repo / "work/game-install/should-not-write.dll"
        refused_path = self.invoke_writer(plan_path, inside_install)
        self.assertNotEqual(refused_path.returncode, 0)
        self.assertIn("inside the configured accepted game installation", refused_path.stderr)
        self.assertFalse(inside_install.exists())

        link = self.repo / "work/link"
        link.symlink_to(self.repo / "work", target_is_directory=True)
        symlink_output = link / "symlink-output.dll"
        refused_link = self.invoke_writer(plan_path, symlink_output)
        self.assertNotEqual(refused_link.returncode, 0)
        self.assertIn("symlink", refused_link.stderr.lower())
        self.assertFalse((self.repo / "work/symlink-output.dll").exists())

        no_clobber = self.invoke_writer(plan_path, candidate)
        self.assertNotEqual(no_clobber.returncode, 0)
        self.assertIn("overwrite", no_clobber.stderr.lower())

        # Same native kind, changed ArrayMarshalInfo.Size must be rejected by
        # the reopened-output comparator rather than passing as LPArray.
        changed_marshal_output = self.repo / "work/changed-marshal.dll"
        changed_marshal = self.invoke_writer(plan_path, changed_marshal_output, mode="--synthetic-corrupt-reopened-array-marshal")
        self.assertNotEqual(changed_marshal.returncode, 0)
        self.assertIn("P/Invoke MarshalInfo metadata changed", changed_marshal.stderr)
        self.assertFalse(changed_marshal_output.exists())
        self.assertFalse(list(changed_marshal_output.parent.glob("changed-marshal.dll.tmp-*")))

        changed_return_output = self.repo / "work/changed-return-marshal.dll"
        changed_return = self.invoke_writer(plan_path, changed_return_output, mode="--synthetic-corrupt-reopened-return-array-marshal")
        self.assertNotEqual(changed_return.returncode, 0)
        self.assertIn("P/Invoke MarshalInfo metadata changed", changed_return.stderr)
        self.assertFalse(changed_return_output.exists())
        self.assertFalse(list(changed_return_output.parent.glob("changed-return-marshal.dll.tmp-*")))

    def test_managed_decoder_rewrite_rejects_unexpected_body_call_and_overload(self):
        plan = self.build_plan()
        for mode, expected_error in (
            ("WRONG_REWRITE_OPERAND", "Managed OS-string method signature/body/call operand differs"),
            ("WRONG_REWRITE_BODY", "Managed OS-string method signature/body/call operand differs"),
            ("WRONG_REWRITE_SIGNATURE", "Managed rewrite method signature differs from policy"),
            ("WRONG_REWRITE_OVERLOAD", "Managed rewrite method has unexpected overloads"),
        ):
            with self.subTest(mode=mode):
                variant_dir = self.root / mode
                built = subprocess.run(
                    [
                        str(DOTNET),
                        "build",
                        str(HERE / "synthetic/ShapeFixture.csproj"),
                        "-o",
                        str(variant_dir),
                        "-p:BaseIntermediateOutputPath=" + str(self.root / ("obj-" + mode)) + os.sep,
                        "-p:DefineConstants=" + mode,
                        "-p:UseSharedCompilation=false",
                        "--nologo",
                    ],
                    cwd=self.root,
                    text=True,
                    capture_output=True,
                )
                self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
                variant = variant_dir / "ShapeFixture.dll"
                variant_plan = json.loads(json.dumps(plan))
                variant_plan["input_assembly_sha256"] = digest(variant.read_bytes())
                plan_path = self.repo / "work" / (mode + ".json")
                plan_path.write_text(json.dumps(variant_plan, sort_keys=True, indent=2))
                output = self.repo / "work" / (mode + ".dll")
                refused = self.invoke_writer(plan_path, output, assembly=variant)
                self.assertNotEqual(refused.returncode, 0, refused.stdout)
                self.assertIn(expected_error, refused.stderr)
                self.assertFalse(output.exists())
                self.assertFalse(list(output.parent.glob(output.name + ".tmp-*")))

    def test_nonvector_rank_one_arrays_are_refused(self):
        helper = self.root / "nonvector-helper"
        built = subprocess.run(
            [
                str(DOTNET),
                "build",
                str(HERE / "synthetic/nonvector/NonVectorFixture.csproj"),
                "-o",
                str(helper),
                "-p:BaseIntermediateOutputPath=" + str(self.root / "obj-nonvector") + os.sep,
                "-p:CecilPath=" + str(CECIL),
                "-p:UseSharedCompilation=false",
                "--nologo",
            ],
            cwd=self.root,
            text=True,
            capture_output=True,
        )
        self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
        nonvector = self.root / "NonVector.dll"
        created = subprocess.run(
            [str(DOTNET), str(helper / "NonVectorFixture.dll"), str(self.assembly), str(nonvector)], cwd=self.root, text=True, capture_output=True
        )
        self.assertEqual(created.returncode, 0, created.stdout + created.stderr)
        refused = subprocess.run(
            [str(DOTNET), str(self.tool / "CecilAbiTool.dll"), "--inspect-pinvoke", str(nonvector)], cwd=self.root, text=True, capture_output=True
        )
        self.assertNotEqual(refused.returncode, 0)
        self.assertIn("non-vector rank-one array", refused.stderr)
        plan = self.build_plan()
        plan["input_assembly_sha256"] = digest(nonvector.read_bytes())
        plan_path = self.repo / "work/nonvector-plan.json"
        plan_path.write_text(json.dumps(plan, sort_keys=True, indent=2))
        candidate = self.repo / "work/nonvector-candidate.dll"
        writer_refusal = self.invoke_writer(plan_path, candidate, nonvector)
        self.assertNotEqual(writer_refusal.returncode, 0)
        self.assertIn("non-vector rank-one array", writer_refusal.stderr)
        self.assertFalse(candidate.exists())


class AcceptedInputBindingTests(unittest.TestCase):
    def setUp(self):
        temp_root = HERE.parents[1] / "work/tests"
        temp_root.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix="wwise-input-binding-", dir=temp_root)
        self.base = Path(self.temp.name)
        self.repo = self.base / "repo"
        self.work = self.repo / "work"
        self.game = self.work / "game-install"
        (self.work / "config").mkdir(parents=True)
        (self.work / "inventory").mkdir(parents=True)
        (self.game / "Risk of Rain 2_Data/Managed").mkdir(parents=True)
        (self.repo / "recipe").mkdir(parents=True)
        (self.work / "config/local.json").write_text(json.dumps({"game_path": str(self.game)}))
        self.managed = self.game / "Risk of Rain 2_Data/Managed/AK.Wwise.Unity.API.dll"
        self.managed.write_bytes(b"synthetic accepted API placeholder")
        self.module = load_generator()
        input_id = self.module.POLICY["accepted_input_id"]
        api_sha = self.module.POLICY["retained_managed_sha256"]
        self.write_input_records(input_id, api_sha)
        self.module.ROOT = self.repo
        self.module.WORK = self.work
        self.sha_patch = patch.object(self.module, "sha", side_effect=lambda p: api_sha if Path(p) == self.managed else "0" * 64)
        self.sha_patch.start()
        self.addCleanup(self.sha_patch.stop)

    def tearDown(self):
        self.temp.cleanup()

    def write_input_records(self, input_id, api_sha):
        (self.work / "config/accepted-input.json").write_text(json.dumps({"input_id": input_id}))
        (self.work / "inventory/files.json").write_text(
            json.dumps(
                {
                    "input_id": input_id,
                    "files": [{"path": "Risk of Rain 2_Data/Managed/AK.Wwise.Unity.API.dll", "sha256": api_sha}],
                }
            )
        )
        (self.repo / "recipe/original-assemblies.json").write_text(
            json.dumps(
                {
                    "input_id": input_id,
                    "assemblies": [{"source": "AK.Wwise.Unity.API.dll", "sha256": api_sha}],
                }
            )
        )

    def argv(self, output, candidate):
        return [
            "generate.py",
            "--android-source",
            "unused.cs",
            "--android-os-string-source",
            "unused-os-string.cs",
            "--native-so",
            "unused.so",
            "--llvm-nm",
            "unused-nm",
            "--output",
            str(output),
            "--candidate",
            str(candidate),
        ]

    def test_consistent_but_wrong_input_id_refuses_before_output_paths(self):
        wrong_id = "a" * 64
        self.write_input_records(wrong_id, self.module.POLICY["retained_managed_sha256"])
        output = self.work / "must-not-be-created.json"
        candidate = self.work / "must-not-be-created.dll"
        with patch("sys.argv", self.argv(output, candidate)):
            with self.assertRaisesRegex(ValueError, "differs from this reviewed Wwise ABI profile"):
                self.module.main()
        self.assertFalse(output.exists())
        self.assertFalse(candidate.exists())

    def test_correct_input_preserves_existing_output_refusal(self):
        output = self.work / "existing-plan.json"
        candidate = self.work / "candidate.dll"
        original = b"preserve existing bytes\n"
        output.write_bytes(original)
        with patch("sys.argv", self.argv(output, candidate)):
            with self.assertRaisesRegex(ValueError, "refusing to overwrite or follow output"):
                self.module.main()
        self.assertEqual(output.read_bytes(), original)
        self.assertFalse(candidate.exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
