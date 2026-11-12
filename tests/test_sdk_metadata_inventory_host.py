import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
import importlib.util
import hashlib
from types import SimpleNamespace

from phone_managed_types import MetadataUniverse


class ManagedProductionReceiptTests(unittest.TestCase):
    def fixture(self, root):
        path = Path(__file__).resolve().parents[1] / "tools/phone-build/accepted-output/bundle_endpoints.py"
        spec = importlib.util.spec_from_file_location("managed_receipt_endpoints", path)
        endpoints = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(endpoints)

        def sha(path):
            return hashlib.sha256(Path(path).read_bytes()).hexdigest()

        def document(name, value):
            path = root / name
            path.write_text(json.dumps(value))
            return dict(path=str(path), bytes=path.stat().st_size, sha256=sha(path))

        gameplay = root / "Assembly-CSharp.dll"
        gameplay.write_bytes(b"authored updated gameplay fixture")
        shared = root / "Shared.dll"
        shared.write_bytes(b"authored unchanged fixture")
        providers = {p.name: dict(path=str(p), sha256=sha(p)) for p in (gameplay, shared)}
        base = document("base.json", {**providers, gameplay.name: dict(path="old-gameplay.dll", sha256="a" * 64)})
        manifest = document("providers.json", providers)
        receipt = dict(
            success=True,
            phase="gameplay-refreshed",
            providers_sha256=manifest["sha256"],
            provider_count=2,
            reused_provider_count=1,
            base_providers={k: base[k] for k in ("path", "sha256")},
            gameplay=providers[gameplay.name],
            phone_qualified=False,
            runtime_qualified=False,
        )
        owner = SimpleNamespace(O=SimpleNamespace(B=SimpleNamespace(sha=sha)))
        return endpoints, endpoints.InputPins(root, owner), document, manifest, receipt, providers

    def test_accepts_pinned_refresh_without_relabelling_receipt(self):
        with tempfile.TemporaryDirectory() as temporary:
            endpoints, pins, document, manifest, receipt, providers = self.fixture(Path(temporary))
            receipt_pin = document("receipt.json", receipt)
            self.assertEqual(endpoints.managed_production(pins, manifest, receipt_pin), providers)
            self.assertEqual(json.loads(Path(receipt_pin["path"]).read_bytes()), receipt)
            self.assertIn(Path(receipt["base_providers"]["path"]).resolve(), pins.files)
            pins.check()

    def test_relocates_unchanged_refresh_inputs_and_checks_staged_bytes(self):
        for missing in (False, True):
            with self.subTest(missing=missing), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                endpoints, pins, document, manifest, receipt, providers = self.fixture(root)
                receipt_pin = document("receipt.json", receipt)
                staged = root / "phone"
                staged.mkdir()
                paths = {}
                originals = {path.name: path.read_bytes() for path in root.iterdir() if path.is_file()}
                for name in originals:
                    source = root / name
                    paths[str(source)] = "phone/" + name
                    source.rename(staged / name)
                pins.relocate(document("input-paths.json", paths))
                self.assertEqual(endpoints.managed_production(pins, manifest, receipt_pin), providers)
                for value in providers.values():
                    path = pins.path(value["path"])
                    pins.add(path, dict(bytes=path.stat().st_size, sha256=value["sha256"]))
                self.assertEqual({name: (staged / name).read_bytes() for name in originals}, originals)
                pins.check()
                target = staged / "Shared.dll"
                if missing:
                    target.unlink()
                else:
                    target.write_bytes(b"changed staged provider")
                with self.assertRaises((ValueError, FileNotFoundError)):
                    pins.check()

    def test_rejects_unbound_or_incomplete_refresh(self):
        for changes, message in (
            (dict(success=False), "successful managed production"),
            (dict(phase="gameplay-assembly"), "successful managed production"),
            (dict(providers_sha256="a" * 64), "provider manifest differs"),
            (dict(providers_sha256=None), "provider manifest differs"),
            (dict(provider_count=3), "manifest/count differs"),
            (dict(reused_provider_count=0), "manifest/count differs"),
            (dict(gameplay=dict(path="Shared.dll", sha256="b" * 64)), "output differs"),
        ):
            with self.subTest(changes=changes), tempfile.TemporaryDirectory() as temporary:
                endpoints, pins, document, manifest, receipt, _ = self.fixture(Path(temporary))
                with self.assertRaisesRegex(ValueError, message):
                    endpoints.managed_production(pins, manifest, document("receipt.json", receipt | changes))

    def test_accepts_explicit_dependency_refresh_and_checks_its_binding(self):
        for mismatch in (None, "hash", "path"):
            with self.subTest(mismatch=mismatch), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                endpoints, pins, document, manifest, receipt, providers = self.fixture(root)
                base = document("base.json", {name: dict(path="old-" + name, sha256="a" * 64) for name in providers})
                receipt.update(
                    base_providers={k: base[k] for k in ("path", "sha256")},
                    reused_provider_count=0,
                    refreshed_providers={name: dict(value) for name, value in providers.items()},
                )
                if mismatch:
                    receipt["refreshed_providers"]["Shared.dll"]["sha256" if mismatch == "hash" else "path"] = (
                        "b" * 64 if mismatch == "hash" else "Assembly-CSharp.dll"
                    )
                    with self.assertRaisesRegex(ValueError, "output differs: Shared.dll"):
                        endpoints.managed_production(pins, manifest, document("receipt.json", receipt))
                else:
                    self.assertEqual(endpoints.managed_production(pins, manifest, document("receipt.json", receipt)), providers)
                    pins.check()

    def test_rejects_changed_reused_provider_and_base_manifest(self):
        for changed_base in (False, True):
            with self.subTest(changed_base=changed_base), tempfile.TemporaryDirectory() as temporary:
                endpoints, pins, document, manifest, receipt, providers = self.fixture(Path(temporary))
                if changed_base:
                    Path(receipt["base_providers"]["path"]).write_text("{}")
                else:
                    providers["Shared.dll"]["sha256"] = "b" * 64
                    manifest = document("providers.json", providers)
                    receipt["providers_sha256"] = manifest["sha256"]
                with self.assertRaisesRegex(ValueError, "input differs|changed a reused provider"):
                    endpoints.managed_production(pins, manifest, document("receipt.json", receipt))


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
            resolver = MetadataUniverse(report, "fixture")
            self.assertEqual(resolver.resolve(forwarding["assembly_identity"], "Parent/Nested")["assembly_identity"], inventory["assembly_identity"])
            self.assertTrue(resolver.derives_from(forwarding["assembly_identity"], "ExternalChild", inventory["assembly_identity"], "Parent"))
            # The release owner compiles this same reader from source and emits
            # all current-provider declarations from the actual managed cohort.
            spec = importlib.util.spec_from_file_location("generated_bundle_endpoints", repo / "tools/phone-build/accepted-output/bundle_endpoints.py")
            endpoints = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(endpoints)
            import hashlib
            import sys

            sys.path.insert(0, str(repo / "tools/phone-build/accepted-output"))

            def pin(path):
                return dict(path=str(path), bytes=path.stat().st_size, sha256=hashlib.sha256(path.read_bytes()).hexdigest())

            def document(name, value):
                path = root / name
                path.write_text(json.dumps(value))
                return pin(path)

            # managed.run exposes an instrumented API with a physical filename
            # different from its actual CLR module name. Metadata owns identity.
            provider = (root / "fixture-out/instrumented-provider.dll").resolve()
            (root / "fixture-out/Fixture.dll").rename(provider)
            providers = {
                name: dict(path=str(path.resolve()), sha256=pin(path)["sha256"])
                for name, path in (("Fixture.dll", provider), ("Facade.dll", root / "facade-out/Facade.dll"))
            }
            registry_pin = pin(provider)
            registry_provider = str(root / "unavailable-provider.dll")
            request = dict(
                managed_providers=document("providers.json", providers),
                managed_receipt=document("managed-result.json", dict(success=True, phase="managed-produced")),
                registry_receipt=document(
                    "registry-result.json", dict(success=True, provider_pins={registry_provider: {k: registry_pin[k] for k in ("bytes", "sha256")}})
                ),
                provider_aliases=document("aliases.json", {registry_provider: str(provider)}),
                tools=dict(
                    dotnet=pin(dotnet),
                    compiler=pin(sorted((dotnet.parent / "sdk").glob("*/Roslyn/bincore/csc.dll"))[-1]),
                    cecil=pin(cecil),
                    references=[
                        pin(path) for path in sorted(sorted((dotnet.parent / "packs/Microsoft.NETCore.App.Ref").glob("*/ref/net10.0"))[-1].glob("*.dll"))
                    ],
                    runtimeconfig=pin(root / "reader-out/MetadataInventory.runtimeconfig.json"),
                ),
            )
            # Consume the original declarations after their host paths disappear.
            # The relocation map changes file lookup, preserving every input hash.
            staged = root / "phone-inputs"
            staged.mkdir()
            relocated = {}
            input_files = {Path(request[key]["path"]) for key in ("managed_providers", "managed_receipt", "registry_receipt", "provider_aliases")}
            input_files.update(Path(value["path"]) for value in providers.values())
            originals = {path: path.read_bytes() for path in input_files}
            for path in input_files:
                relocated[str(path)] = "phone-inputs/" + path.name
                path.rename(staged / path.name)
            request["input_paths"] = document("input-paths.json", relocated)
            staged_providers = {name: dict(value, path=str((staged / Path(value["path"]).name).resolve())) for name, value in providers.items()}
            provider = (staged / provider.name).resolve()
            request_path = root / "managed-request.json"
            request_path.write_text(json.dumps(request))
            generated = root / "generated"
            result = endpoints.generate_managed(request_path, generated)
            self.assertTrue(result["success"])
            self.assertEqual(result["managed_providers"], 2)
            self.assertEqual(json.loads((generated / "runtime-request.json").read_text())["managed"], staged_providers)
            self.assertEqual(json.loads((generated / "provider-aliases.json").read_text()), {registry_provider: str(provider)})
            self.assertEqual(json.loads((generated / "metadata.json").read_text())["assemblies"][0]["group"], "current")
            self.assertEqual({path: (staged / path.name).read_bytes() for path in input_files}, originals)
            provider.write_bytes(b"changed provider")
            with self.assertRaisesRegex(ValueError, "input differs"):
                endpoints.generate_managed(request_path, root / "refused")
            original = (root / "report.json").read_bytes()
            self.assertNotEqual(call(command, check=False).returncode, 0)
            self.assertEqual((root / "report.json").read_bytes(), original)
