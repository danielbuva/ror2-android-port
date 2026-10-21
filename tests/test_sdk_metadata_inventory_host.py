import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


class SdkMetadataInventoryHostTests(unittest.TestCase):
    def test_metadata_reader_does_not_execute_throwing_attribute_constructor(self):
        repo = Path(__file__).resolve().parents[1]
        dotnet = Path.home() / ".local/share/dotnet/dotnet"
        cecil = Path(
            "/Applications/Unity/Hub/Editor/2021.3.45f2/Unity.app/Contents/MonoBleedingEdge/lib/mono/gac/Mono.Cecil/0.11.1.0__0738eb9f132ed756/Mono.Cecil.dll"
        )
        if not dotnet.is_file() or not cecil.is_file():
            self.skipTest("Optional .NET SDK/exact-editor Cecil are absent")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = root / "NuGet.Config"
            config.write_text("<configuration><packageSources><clear /></packageSources></configuration>")
            fixture = root / "fixture"
            fixture.mkdir()
            (fixture / "Fixture.csproj").write_text(
                '<Project Sdk="Microsoft.NET.Sdk"><PropertyGroup><TargetFramework>net10.0</TargetFramework></PropertyGroup></Project>'
            )
            (fixture / "Fixture.cs").write_text(
                'namespace UnityEngine { public sealed class NativeClassAttribute:System.Attribute { public NativeClassAttribute(string name) { throw new System.Exception("Input code executed"); } } }\n'
                '[UnityEngine.NativeClass("Native::Authored")] public class Authored : Parent {} public class Parent { public class Nested {} }\n'
            )
            facade = root / "facade"
            facade.mkdir()
            (facade / "Facade.csproj").write_text(
                '<Project Sdk="Microsoft.NET.Sdk"><PropertyGroup><TargetFramework>net10.0</TargetFramework></PropertyGroup>'
                '<ItemGroup><Reference Include="Fixture"><HintPath>../fixture-out/Fixture.dll</HintPath></Reference></ItemGroup></Project>'
            )
            (facade / "Facade.cs").write_text(
                "[assembly:System.Runtime.CompilerServices.TypeForwardedTo(typeof(Parent))]\npublic class ExternalChild : Authored {}\n"
            )
            shutil.copytree(repo / "tools/phone-build/metadata", root / "reader")
            env = dict(os.environ)
            env.update(
                DOTNET_CLI_HOME=str(root / "dotnet-home"),
                NUGET_PACKAGES=str(root / "nuget"),
                DOTNET_CLI_TELEMETRY_OPTOUT="1",
                DOTNET_SKIP_FIRST_TIME_EXPERIENCE="1",
                MSBUILDDISABLENODEREUSE="1",
                DOTNET_CLI_USE_MSBUILD_SERVER="0",
            )

            def call(command, *, check=True):
                return subprocess.run([str(x) for x in command], cwd=root, env=env, capture_output=True, text=True, timeout=120, check=check)

            for project, output, extra in (
                (fixture / "Fixture.csproj", root / "fixture-out", []),
                (facade / "Facade.csproj", root / "facade-out", []),
                (root / "reader/MetadataInventory.csproj", root / "reader-out", ["-p:CecilPath=" + str(cecil)]),
            ):
                call([dotnet, "build", project, "-o", output, "-p:RestoreConfigFile=" + str(config), "-p:UseSharedCompilation=false", *extra, "--nologo"])
            inputs = root / "inputs.json"
            inputs.write_text(
                json.dumps(
                    {
                        "assemblies": [
                            {"group": "fixture", "path": str(root / output / name)}
                            for output, name in [("fixture-out", "Fixture.dll"), ("facade-out", "Facade.dll")]
                        ]
                    }
                )
            )
            command = [dotnet, root / "reader-out/MetadataInventory.dll", inputs, root / "report.json"]
            call(command)
            report = json.loads((root / "report.json").read_text())
            self.assertEqual(report["schema"], 2)
            self.assertIs(report["executes_inputs"], False)
            inventory, forwarding = report["assemblies"]
            item = next(row for row in inventory["types"] if row["name"] == "Authored")
            self.assertEqual(item["base_type"], "Parent")
            self.assertEqual(item["base_scope"], {"kind": "ModuleDefinition", "name": "Fixture.dll", "assembly_identity": inventory["assembly_identity"]})
            self.assertEqual(item["native_attributes"][0]["arguments"][0]["value"], "Native::Authored")
            external = next(row for row in forwarding["types"] if row["name"] == "ExternalChild")
            self.assertEqual(external["base_type"], "Authored")
            self.assertEqual(external["base_scope"], {"kind": "AssemblyNameReference", "name": "Fixture", "assembly_identity": inventory["assembly_identity"]})
            self.assertIn(inventory["assembly_identity"], forwarding["references"])
            exported = {row["name"]: row for row in forwarding["exported_types"]}
            self.assertTrue(exported["Parent"]["is_forwarder"])
            self.assertIsNone(exported["Parent"]["declaring_type"])
            self.assertEqual(exported["Parent/Nested"]["declaring_type"], "Parent")
            self.assertEqual(exported["Parent/Nested"]["scope"], exported["Parent"]["scope"])
            self.assertEqual(exported["Parent"]["scope"]["assembly_identity"], inventory["assembly_identity"])
            original = (root / "report.json").read_bytes()
            self.assertNotEqual(call(command, check=False).returncode, 0)
            self.assertEqual((root / "report.json").read_bytes(), original)
