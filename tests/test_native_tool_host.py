"""Execute the native hosting ABI against an authored substitute, never .NET/game code."""

import os
from pathlib import Path
import platform
import shutil
import subprocess
import tempfile
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "tools/phone-build/native-host"


class NativeToolHostTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if platform.system() != "Linux" or not shutil.which("cc"):
            raise unittest.SkipTest("Linux /proc and native C compiler required")
        cls.directory = tempfile.TemporaryDirectory()
        cls.root = Path(cls.directory.name)
        cls.host = cls.root / "host"
        subprocess.run(["cc", "-Wall", "-Wextra", "-Werror", str(SOURCE / "NativeToolHost.c"), "-ldl", "-o", str(cls.host)], check=True, capture_output=True)
        fixture = cls.root / "fixture.c"
        fixture.write_text(
            r"""
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
struct parameters {size_t size; const char *host_path; const char *dotnet_root;};
int32_t hostfxr_initialize_for_dotnet_command_line(int argc, const char **argv, const struct parameters *p, void **h) {
    if(p->size != sizeof(*p) || !p->host_path || !p->dotnet_root) return -101;
    printf("FORWARDED_HOST=%s\nFORWARDED_ROOT=%s\nFORWARDED_ARGC=%d\n",p->host_path,p->dotnet_root,argc);
    for(int i=0;i<argc;i++) printf("FORWARDED_ARG_%d=%s\n",i,argv[i]);
    if(getenv("FIXTURE_INITIALIZE_FAIL")) return -102;
    *h=(void *)(uintptr_t)0x1234;
    return 0;
}
int32_t hostfxr_run_app(void *h) {
    if(h != (void *)(uintptr_t)0x1234) return 103;
    puts("FIXTURE_RUN");
    return getenv("FIXTURE_EXIT") ? atoi(getenv("FIXTURE_EXIT")) : 0;
}
int32_t hostfxr_close(void *h) {
    if(h != (void *)(uintptr_t)0x1234) return 104;
    puts("FIXTURE_CLOSE"); return 0;
}
"""
        )
        cls.library = cls.root / "libfixture.so"
        subprocess.run(["cc", "-shared", "-fPIC", str(fixture), "-o", str(cls.library)], check=True, capture_output=True)

    @classmethod
    def tearDownClass(cls):
        cls.directory.cleanup()

    def run_host(self, *arguments, environment=None):
        env = {k: v for k, v in os.environ.items() if not k.startswith("FIXTURE_")}
        env.update(environment or {})
        return subprocess.run([str(self.host), *map(str, arguments)], env=env, capture_output=True, text=True, timeout=10)

    def test_arguments_root_and_actual_host_path_reach_hostfxr(self):
        alias = self.root / "host-alias"
        alias.symlink_to(self.host)
        try:
            p = subprocess.run(
                [str(alias), str(self.library), "/authored framework", "app.dll", "space value", "--literal"], capture_output=True, text=True, timeout=10
            )
        finally:
            alias.unlink()
        self.assertEqual(p.returncode, 0, p.stderr)
        for expected in (
            "FORWARDED_HOST=" + str(self.host),
            "FORWARDED_ROOT=/authored framework",
            "FORWARDED_ARGC=3",
            "FORWARDED_ARG_0=app.dll",
            "FORWARDED_ARG_1=space value",
            "FORWARDED_ARG_2=--literal",
            "HOST_INITIALIZE=0",
            "HOST_RUN=0",
            "FIXTURE_CLOSE",
            "HOST_MAPS_BEGIN",
            "HOST_MAPS_END",
        ):
            self.assertIn(expected, p.stdout)

    def test_bad_invocation_and_missing_library_refuse_before_initialization(self):
        self.assertEqual(self.run_host().returncode, 64)
        p = self.run_host(self.root / "absent.so", "/framework", "app.dll")
        self.assertEqual(p.returncode, 66)
        self.assertNotIn("HOST_INITIALIZE=", p.stdout)

    def test_incomplete_hosting_abi_refuses(self):
        source = self.root / "incomplete.c"
        source.write_text("int irrelevant(void) { return 0; }\n")
        library = self.root / "incomplete.so"
        subprocess.run(["cc", "-shared", "-fPIC", str(source), "-o", str(library)], check=True, capture_output=True)
        p = self.run_host(library, "/framework", "app.dll")
        self.assertEqual(p.returncode, 67)
        self.assertNotIn("HOST_INITIALIZE=", p.stdout)

    def test_initialization_failure_never_runs_or_closes_an_invalid_context(self):
        p = self.run_host(self.library, "/framework", "app.dll", environment={"FIXTURE_INITIALIZE_FAIL": "1"})
        self.assertEqual(p.returncode, 68)
        self.assertIn("HOST_INITIALIZE=-102", p.stdout)
        self.assertNotIn("FIXTURE_RUN", p.stdout)
        self.assertNotIn("FIXTURE_CLOSE", p.stdout)

    def test_managed_exit_is_preserved_and_context_is_closed(self):
        p = self.run_host(self.library, "/framework", "app.dll", environment={"FIXTURE_EXIT": "23"})
        self.assertEqual(p.returncode, 23)
        self.assertIn("HOST_RUN=23", p.stdout)
        self.assertIn("FIXTURE_CLOSE", p.stdout)
        self.assertIn("HOST_MAPS_END", p.stdout)


class NativeToolHostScopeTests(unittest.TestCase):
    def test_fixture_is_separate_target33_without_permissions(self):
        root = ET.parse(SOURCE / "AndroidManifest.xml").getroot()
        android = "{http://schemas.android.com/apk/res/android}"
        self.assertEqual(root.get("package"), "dev.ror2lab.phonebuildhostfixture")
        self.assertEqual(root.find("uses-sdk").get(android + "targetSdkVersion"), "33")
        self.assertEqual(root.findall("uses-permission"), [])
        self.assertEqual(root.find("application").get(android + "extractNativeLibs"), "true")


if __name__ == "__main__":
    unittest.main()
