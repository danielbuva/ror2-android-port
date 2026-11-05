"""Public host packaging contract, not private-builder or phone acceptance.

The SDK-backed cases compile the real OwnerInstaller with authored collaborators,
then inspect the manifest and defined receiver class from the same unsigned APK.
Missing pinned SDK/JDK tools are explicit skips, never packaged-artifact proof.
"""

import importlib.util
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest
import xml.etree.ElementTree as ET
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "tools/phone-build/managed-host"
JAVA_PACKAGE = "dev.ror2lab.phonebuildhostfixture"
APPLICATION_IDS = (JAVA_PACKAGE, "dev.ror2lab.installertest", "dev.ror2lab.authoredtool")


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


STAGE = load("receiver_contract_stage", SOURCE / "stage.py")
INSPECT = load("receiver_contract_inspect", SOURCE / "inspect_manifest.py")
COLLABORATORS = {
    "ToolHostActivity.java": """public class ToolHostActivity {
        public static void updateInstallCheckpoint(android.content.Context app,String state,String message){}
        public static void updateInstallDiagnostic(android.content.Context app,String stage,String callback,boolean match){}
        public static void updateInstallReceiverDiagnostic(android.content.Context app,String registration,boolean entered){}
    }""",
    "OwnerBuildService.java": """public class OwnerBuildService {
        public static boolean isRunning(){return false;}
        public static void launch(android.content.Context app,String action){}
    }""",
    "OwnerAlphaInstall.java": """public class OwnerAlphaInstall {
        public static final String PACKAGE="dev.ror2lab.alpha";
        public static boolean pending(android.content.Context app){return false;}
        public static void prepare(android.content.Context app,java.io.File apk,String hash,android.content.pm.PackageInfo next,android.content.pm.PackageInfo current){}
        public static void complete(android.content.Context app,android.content.pm.PackageInfo actual){}
        public static boolean recover(android.content.Context app){return false;}
    }""",
}


def packaging_tools():
    player = Path("/Applications/Unity/Hub/Editor/2021.3.45f2/PlaybackEngines/AndroidPlayer")
    sdk = Path(os.environ.get("ANDROID_HOME") or os.environ.get("ANDROID_SDK_ROOT") or player / "SDK")
    java_home = Path(os.environ.get("JAVA_HOME") or player / "OpenJDK")
    javac = java_home / "bin/javac"
    if not javac.is_file():
        found = shutil.which("javac")
        if not found:
            return None
        javac = Path(found)
    build = sdk / "build-tools/34.0.0"
    result = dict(
        javac=javac,
        java=javac.with_name("java"),
        android=sdk / "platforms/android-33/android.jar",
        aapt=build / "aapt",
        d8=build / "lib/d8.jar",
        dexdump=build / "dexdump",
    )
    return result if all(path.is_file() for path in result.values()) else None


class ReceiverArchiveTests(unittest.TestCase):
    def test_shared_public_archive_includes_nested_receiver(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            classes = root / "classes"
            for name in ("OwnerInstaller.class", "OwnerInstaller$Result.class", "ToolHostActivity$1.class"):
                path = classes / JAVA_PACKAGE.replace(".", "/") / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"authored class placeholder; not executed")
            (classes / "unrelated.txt").write_text("not a class")
            archive = root / "classes.jar"
            STAGE.archive_java_classes(classes, archive)
            with zipfile.ZipFile(archive) as result:
                self.assertEqual(len(result.namelist()), 3)
                self.assertIn(JAVA_PACKAGE.replace(".", "/") + "/OwnerInstaller$Result.class", result.namelist())
        builder = (SOURCE / "build_fixture.py").read_text()
        self.assertIn("staging.archive_java_classes(classes, jar)", builder)

    def test_all_public_application_id_variants_qualify_before_packaging(self):
        with tempfile.TemporaryDirectory() as temporary:
            for package in APPLICATION_IDS:
                with self.subTest(package=package):
                    target = Path(temporary) / "AndroidManifest.xml"
                    STAGE.tool_manifest(SOURCE / "AndroidManifest.xml", target, package, game_package="dev.ror2lab.alpha")
                    manifest = ET.parse(target).getroot()
                    self.assertEqual(manifest.attrib["package"], package)
                    receiver = manifest.find("application/receiver")
                    android = "{" + INSPECT.ANDROID + "}"
                    self.assertEqual(receiver.attrib[android + "name"], INSPECT.RECEIVER)
                    self.assertEqual(receiver.attrib[android + "exported"], "false")


class PackagedReceiverSdkTests(unittest.TestCase):
    def setUp(self):
        self.tools = packaging_tools()
        if self.tools is None:
            self.skipTest("Pinned Android 33/build-tools 34.0.0 packaging SDK or JDK unavailable; no artifact proof")
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def command(self, phase, *arguments):
        try:
            result = subprocess.run(list(map(str, arguments)), stdin=subprocess.DEVNULL, capture_output=True, timeout=120)
        except (OSError, subprocess.TimeoutExpired):
            raise AssertionError(phase + " did not complete") from None
        self.assertEqual(result.returncode, 0, phase + " failed; raw tool output withheld")
        return result.stdout

    def package(self, application_id, *, wrong_receiver=False):
        sources = [SOURCE / "OwnerInstaller.java"]
        for name, body in COLLABORATORS.items():
            path = self.root / name
            path.write_text("package " + JAVA_PACKAGE + ";\n" + body)
            sources.append(path)
        classes = self.root / "classes"
        classes.mkdir()
        self.command(
            "javac", self.tools["javac"], "-source", "8", "-target", "8", "-parameters", "-bootclasspath", self.tools["android"], "-d", classes, *sources
        )
        jar = self.root / "classes.jar"
        STAGE.archive_java_classes(classes, jar)
        dex = self.root / "dex"
        dex.mkdir()
        self.command(
            "D8",
            self.tools["java"],
            "-cp",
            self.tools["d8"],
            "com.android.tools.r8.D8",
            "--min-api",
            "24",
            "--lib",
            self.tools["android"],
            "--output",
            dex,
            jar,
        )
        source_manifest = self.root / "AndroidManifest.xml"
        STAGE.tool_manifest(SOURCE / "AndroidManifest.xml", source_manifest, application_id, game_package="dev.ror2lab.alpha")
        if wrong_receiver:
            # Reproduce a package-remap regression while leaving the actual Java
            # namespace untouched. This APK is inspected on the host, never run.
            tree = ET.parse(source_manifest)
            tree.getroot().find("application/receiver").set("{" + INSPECT.ANDROID + "}name", ".OwnerInstaller$Result")
            tree.write(source_manifest, encoding="utf-8", xml_declaration=True)
        apk = self.root / "receiver-contract.apk"
        self.command("AAPT", self.tools["aapt"], "package", "-f", "-M", source_manifest, "-I", self.tools["android"], "-F", apk)
        with zipfile.ZipFile(apk, "a", zipfile.ZIP_DEFLATED) as archive:
            archive.write(dex / "classes.dex", "classes.dex")
        with zipfile.ZipFile(apk) as archive:
            observed = INSPECT.binary_manifest(archive.read("AndroidManifest.xml"), 3, package=application_id)
            self.assertEqual(INSPECT.packaged_receiver_definition(archive, archive.infolist()), "defined")
            packaged_dex = self.root / "packaged-classes.dex"
            packaged_dex.write_bytes(archive.read("classes.dex"))
        output = self.command("dexdump", self.tools["dexdump"], "-f", packaged_dex).decode("utf-8", errors="strict")
        # Only class definitions count, not a string or type reference in DEX.
        definitions = set(re.findall(r"^\s*Class descriptor\s*:\s*'([^']+)'", output, re.MULTILINE))
        self.assertTrue(definitions, "DEX class definitions were not observed")
        return observed, definitions

    def exact_contract(self, application_id):
        observed, definitions = self.package(application_id)
        self.assertEqual(observed["receiver_declaration"], "exact")
        self.assertEqual(observed["receiver_exported"], "false")
        self.assertEqual(observed["receiver_enabled"], "true")
        self.assertEqual(observed["application_enabled"], "true")
        self.assertIn("L" + INSPECT.RECEIVER.replace(".", "/") + ";", definitions, "Packaged receiver must name a class defined in the same APK")

    def test_original_application_id_packaged_manifest_matches_dex(self):
        self.exact_contract(APPLICATION_IDS[0])

    def test_disposable_application_id_packaged_manifest_matches_dex(self):
        self.exact_contract(APPLICATION_IDS[1])

    def test_authored_application_id_packaged_manifest_matches_dex(self):
        self.exact_contract(APPLICATION_IDS[2])

    def test_relative_receiver_regression_does_not_match_defined_class(self):
        observed, definitions = self.package(APPLICATION_IDS[1], wrong_receiver=True)
        self.assertEqual(observed["receiver_declaration"], "misqualified")
        self.assertNotIn("L" + APPLICATION_IDS[1].replace(".", "/") + "/OwnerInstaller$Result;", definitions)
        self.assertIn("L" + INSPECT.RECEIVER.replace(".", "/") + ";", definitions)


if __name__ == "__main__":
    unittest.main()
