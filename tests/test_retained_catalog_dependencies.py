"""Exercise production ownership/selection seams with authored Unity lifetime doubles."""

import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

from test_native_commerce_release_order import braced_block, repo_root


ROOT = repo_root()
RUNTIME = ROOT / "tools/unity/runtime"
FIXTURE = ROOT / "tests/fixtures/retained_catalog_dependencies_host.cs"


def production_host(*, unload_mutant=False):
    whole = (RUNTIME / "catalog/WholeCatalogComposed.cs").read_text()
    body = (RUNTIME / "catalog/BodyCatalogBoundary.cs").read_text()
    teleporter = (RUNTIME / "stage/TeleporterWorldBoundary.cs").read_text()
    selection = (RUNTIME / "session/SurvivorSelectionBoundary.cs").read_text()
    audio = (ROOT / "tools/unity/support/audio/core/GameAudioOriginalOwner.cs").read_text()
    # Compile the complete new owner, actual public transitions, and actual
    # cleanup/selection methods. Unrelated catalog/editor code stays outside
    # this seam; the host doubles never implement the production lease policy.
    start = whole.index("    static string originalAudioLeaseIdentity;")
    end = whole.index("    delegate bool ExtractSubObjectKey", start)
    methods = [
        braced_block(whole, signature)
        for signature in (
            "public static string RetainForOriginalAudioOwner(string expectedInputId)",
            "public static bool ReleaseOriginalAudioOwnerLease(string expectedIdentity)",
            "public static IEnumerator Prepare()",
            "public static void Release()",
        )
    ]
    cleanup = braced_block(body, "void CleanupBodyCatalog()")
    if unload_mutant:
        guard = "!WholeCatalogComposed.ParkRetainedDependency(artifactBundle)"
        if cleanup.count(guard) != 1:
            raise AssertionError("Manual release seam changed")
        cleanup = cleanup.replace(guard, "true")
    register = braced_block(body, "public IEnumerator RegisterBodyCatalog()")
    manual_load = re.search(
        r'if \(!WholeCatalogComposed.TakeRetainedDependency\("commando-prefab-lab", out coordinator.artifactBundle\)\)'
        r"\s*coordinator.artifactBundle\s*=\s*AssetBundle.LoadFromFile\([^;]+;",
        register,
    )
    if manual_load is None:
        raise AssertionError("Manual acquisition seam changed")
    return (
        FIXTURE.read_text()
        + "\npublic static partial class GameAudioOriginalOwner {\n"
        + braced_block(audio, "public static bool CanReleaseCatalogLease(bool managerInitClaimed, bool nativeInitAttemptObserved, bool termsReturned)")
        + "\n}\n"
        + "\npublic static partial class WholeCatalogComposed {\n"
        + whole[start:end]
        + "\n".join(methods)
        + "\n}\npublic sealed partial class PortSession {\n"
        + cleanup
        + "\n".join(
            braced_block(selection, signature)
            for signature in (
                "void EnsureOfflineUnlockPreview()",
                "static string SurvivorUnlockName(SurvivorDef survivor)",
                "bool IsOrdinarySurvivorAvailable(SurvivorDef survivor)",
                "SurvivorDef[] OrdinarySurvivorChoices()",
            )
        )
        + "\npublic void AcquireBody() { var coordinator = this;\n"
        + manual_load.group()
        + "\n}\npublic sealed partial class TeleporterWorldSession {\n"
        + braced_block(teleporter, "public IEnumerator PreloadObjectiveBundle()")
        + braced_block(teleporter, "public void ReleaseObjectiveBundlePreload()")
        + "\n}\n}\n"
    )


def execute_host(source, scenario):
    editor = Path(os.environ.get("UNITY_EDITOR_PATH", "/Applications/Unity/Hub/Editor/2021.3.45f2/Unity.app/Contents"))
    mono = editor / "MonoBleedingEdge/bin/mono"
    compiler = editor / "MonoBleedingEdge/lib/mono/msbuild/Current/bin/Roslyn/csc.exe"
    newtonsoft = editor / "Managed/Newtonsoft.Json.dll"
    if not all(path.is_file() for path in (mono, compiler, newtonsoft)):
        raise unittest.SkipTest("pinned Unity Mono/Roslyn and JSON library are unavailable")
    with tempfile.TemporaryDirectory(prefix="retained-catalog-host-") as temporary:
        scratch = Path(temporary).resolve()
        production = scratch / "RetainedCatalogHost.cs"
        executable = scratch / "RetainedCatalogHost.exe"
        production.write_text(source)
        shutil.copyfile(newtonsoft, scratch / newtonsoft.name)
        environment = os.environ.copy()
        environment.update(TMPDIR=str(scratch), TMP=str(scratch), TEMP=str(scratch))
        compiled = subprocess.run(
            [str(mono), str(compiler), "-nologo", "-langversion:7.3", "-target:exe", "-out:" + str(executable), "-r:" + str(newtonsoft), str(production)],
            cwd=scratch,
            env=environment,
            capture_output=True,
            text=True,
            timeout=60,
        )
        if compiled.returncode:
            raise AssertionError(compiled.stdout + compiled.stderr)
        return subprocess.run([str(mono), str(executable), scenario], cwd=scratch, env=environment, capture_output=True, text=True, timeout=30)


class RetainedCatalogDependenciesTests(unittest.TestCase):
    def run_scenario(self, name):
        result = execute_host(production_host(), name)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return json.loads(result.stdout)

    def test_two_restarts_keep_original_prefabs_and_provider_ownership(self):
        self.assertEqual(self.run_scenario("restart"), {"sessions": 3, "body_loads": 1, "provider_loads": 1, "releases": 1})

    def test_termination_defers_only_until_session_cleanup_and_default_off_unloads(self):
        self.assertEqual(self.run_scenario("termination"), {"active_term": True, "early_refusal": True, "default_off": True})

    def test_invalid_graph_identity_handle_and_package_refuse_without_release(self):
        result = self.run_scenario("refusals")
        self.assertEqual(result, {"checks": 18})

    def test_old_manual_unload_reproduces_actual_selection_failure(self):
        result = execute_host(production_host(unload_mutant=True), "restart")
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Original free survivor choices unavailable", result.stderr)


if __name__ == "__main__":
    unittest.main()
