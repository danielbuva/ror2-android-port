"""Authored CLR fixtures exercise the non-executing scoped field inventory."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class MetadataFieldTests(unittest.TestCase):
    def test_scoped_arrays_generics_and_inherited_fields_are_recorded(self):
        dotnet = Path.home() / ".local/share/dotnet/dotnet"
        editor = Path(os.environ.get("UNITY_EDITOR", "/absent/Contents/MacOS/Unity"))
        cecil = editor.parents[1] / "MonoBleedingEdge/lib/mono/gac/Mono.Cecil/0.11.1.0__0738eb9f132ed756/Mono.Cecil.dll"
        if not dotnet.is_file() or not cecil.is_file():
            self.skipTest("exact SDK Cecil and host .NET are unavailable")
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            source = base / "source"
            shutil.copytree(ROOT / "tools/phone-build/metadata", source, ignore=shutil.ignore_patterns("bin", "obj"))
            (source / "Fixture.cs").write_text(
                "namespace Authored { public class Parent<T> { public T target = default!; } "
                "public class Child : Parent<System.String> { public int[] values = []; "
                "public System.Collections.Generic.List<Child> children = []; "
                "[System.NonSerialized] public Child transient = null!; public static int shared; } }"
            )
            output = base / "tool"
            command = [
                str(dotnet),
                "build",
                str(source / "MetadataInventory.csproj"),
                "-o",
                str(output),
                "-p:CecilPath=" + str(cecil),
                "-p:UseSharedCompilation=false",
                "--nologo",
            ]
            built = subprocess.run(command, capture_output=True, text=True, timeout=120)
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            assembly = output / "MetadataInventory.dll"
            request, report = base / "input.json", base / "output.json"
            request.write_text(json.dumps({"assemblies": [{"group": "fixture", "path": str(assembly)}]}))
            inspected = subprocess.run([str(dotnet), str(assembly), str(request), str(report)], capture_output=True, text=True, timeout=30)
            self.assertEqual(inspected.returncode, 0, inspected.stdout + inspected.stderr)
            inventory = json.loads(report.read_text())
            self.assertFalse(inventory["executes_inputs"])
            row = inventory["assemblies"][0]
            types = {item["name"]: item for item in row["types"]}
            child, parent = types["Authored.Child"], types["Authored.Parent`1"]
            fields = {field["name"]: field for field in child["fields"]}
            self.assertEqual(fields["values"]["signature"]["kind"], "array")
            self.assertEqual(fields["values"]["signature"]["element"]["name"], "System.Int32")
            signature = fields["children"]["signature"]
            self.assertEqual(signature["kind"], "generic_instance")
            self.assertEqual(signature["arguments"][0]["scope"]["assembly_identity"], row["assembly_identity"])
            self.assertTrue(fields["transient"]["is_not_serialized"])
            self.assertTrue(fields["shared"]["is_static"])
            self.assertEqual(child["base_signature"]["arguments"][0]["name"], "System.String")
            self.assertEqual(parent["fields"][0]["signature"], {"kind": "generic_parameter", "owner": "Type", "position": 0})
            self.assertEqual(parent["generic_parameters"], [{"name": "T", "position": 0}])


if __name__ == "__main__":
    unittest.main()
