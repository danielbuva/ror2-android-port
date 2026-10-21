from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


def find_repo_root() -> Path:
    marker = Path("tools/unity/support/audio/managed-producer/tools/owner-api/OwnerApiCecilTransform.csproj")
    for parent in Path(__file__).resolve().parents:
        if (parent / marker).is_file():
            return parent
    raise RuntimeError("repository root not found from test path")


ROOT = find_repo_root()
TOOL_PROJECT = ROOT / "tools/unity/support/audio/managed-producer/tools/owner-api/OwnerApiCecilTransform.csproj"
FIXTURE = Path(__file__).resolve().parent / "fixtures/original_audio/OwnerApiPreTermInjectionHarness.cs"
UNITY_CONTENTS = Path("/Applications/Unity/Hub/Editor/2021.3.45f2/Unity.app/Contents")
MONO = UNITY_CONTENTS / "MonoBleedingEdge/bin/mono"
CSC = UNITY_CONTENTS / "MonoBleedingEdge/lib/mono/msbuild/Current/bin/Roslyn/csc.exe"
CECIL = UNITY_CONTENTS / "MonoBleedingEdge/lib/mono/gac/Mono.Cecil/0.11.1.0__0738eb9f132ed756/Mono.Cecil.dll"


class OriginalAudioPreTermTransformTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.dotnet = shutil.which("dotnet")
        if cls.dotnet is None or not all(path.is_file() for path in (MONO, CSC, CECIL)):
            raise unittest.SkipTest("pinned Unity Mono/Roslyn/Cecil and dotnet toolchain unavailable")

    @staticmethod
    def dotnet_environment(temp: Path) -> dict[str, str]:
        return {
            **os.environ,
            "DOTNET_NOLOGO": "1",
            "DOTNET_CLI_TELEMETRY_OPTOUT": "1",
            "DOTNET_CLI_HOME": str(temp / "dotnet-home"),
            "NUGET_PACKAGES": str(temp / "nuget-packages"),
            "TMPDIR": str(temp),
            "TMP": str(temp),
            "TEMP": str(temp),
        }

    def test_production_owner_api_injection_guards_both_admitted_term_branches(self) -> None:
        with tempfile.TemporaryDirectory(prefix="original-audio-owner-term-") as temp_name:
            temp = Path(temp_name)
            transform_output = temp / "transform"
            transform_obj = temp / "obj-transform"
            built = subprocess.run(
                [
                    self.dotnet,
                    "build",
                    str(TOOL_PROJECT),
                    "--nologo",
                    "-p:CecilPath=" + str(CECIL),
                    "-p:OutputPath=" + str(transform_output) + "/",
                    "-p:BaseIntermediateOutputPath=" + str(transform_obj) + "/",
                ],
                capture_output=True,
                text=True,
                check=False,
                env=self.dotnet_environment(temp),
            )
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            transform = transform_output / "OwnerApiCecilTransform.dll"
            self.assertTrue(transform.is_file(), "production owner API transform output missing")
            harness_dir = temp / "harness"
            harness_dir.mkdir()
            project = harness_dir / "OwnerApiPreTermInjectionHarness.csproj"
            project.write_text(
                """<Project Sdk=\"Microsoft.NET.Sdk\"><PropertyGroup><OutputType>Exe</OutputType><TargetFramework>net10.0</TargetFramework><ImplicitUsings>enable</ImplicitUsings><Nullable>enable</Nullable></PropertyGroup><ItemGroup><Reference Include=\"Mono.Cecil\"><HintPath>CECIL_PATH</HintPath></Reference><Reference Include=\"OwnerApiCecilTransform\"><HintPath>TRANSFORM_PATH</HintPath></Reference></ItemGroup></Project>""".replace(
                    "CECIL_PATH", str(CECIL)
                ).replace("TRANSFORM_PATH", str(transform)),
                encoding="utf-8",
            )
            shutil.copyfile(FIXTURE, harness_dir / FIXTURE.name)
            harness_obj = temp / "obj-harness"
            harness_output = temp / "harness-output"
            harness_built = subprocess.run(
                [
                    self.dotnet,
                    "build",
                    str(project),
                    "--nologo",
                    "-p:OutputPath=" + str(harness_output) + "/",
                    "-p:BaseIntermediateOutputPath=" + str(harness_obj) + "/",
                ],
                capture_output=True,
                text=True,
                check=False,
                env=self.dotnet_environment(temp),
            )
            self.assertEqual(harness_built.returncode, 0, harness_built.stdout + harness_built.stderr)
            executed = subprocess.run(
                [self.dotnet, str(harness_output / "OwnerApiPreTermInjectionHarness.dll"), str(transform)],
                capture_output=True,
                text=True,
                check=False,
                env=self.dotnet_environment(temp),
            )
            self.assertEqual(executed.returncode, 0, executed.stdout + executed.stderr)
            self.assertIn("PASS actual owner API transform injection", executed.stdout)


if __name__ == "__main__":
    unittest.main()
