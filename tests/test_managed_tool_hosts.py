"""Run the authored embedding shims against substitute public ABIs, without tool binaries."""

import os
from pathlib import Path
import platform
import shutil
import subprocess
import tempfile
import unittest

SOURCE = Path(__file__).resolve().parents[1] / "tools/phone-build/managed-host"


class ManagedToolHostTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if platform.system() != "Linux" or not shutil.which("cc"):
            raise unittest.SkipTest("Linux /proc and native C compiler required")
        cls.temporary = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temporary.name)
        for name in ("NativePythonHost", "NativeDotnetMuxer"):
            subprocess.run(
                ["cc", "-Wall", "-Wextra", "-Werror", str(SOURCE / (name + ".c")), "-ldl", "-o", str(cls.root / name)], check=True, capture_output=True
            )
        python = cls.root / "python.c"
        python.write_text(r"""
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <stddef.h>
#include <string.h>
void *PyInitConfig_Create(void) { return getenv("FIXTURE_CREATE_FAIL") ? NULL : (void*)0x1234; }
void PyInitConfig_Free(void *p) { if(p==(void*)0x1234) puts("PY_FREE"); }
int PyInitConfig_SetInt(void *p,const char *name,int64_t value) {
    (void)p; printf("PY_INT %s=%lld\n",name,(long long)value);
    return getenv("FIXTURE_SET_FAIL") ? -1 : 0;
}
int PyInitConfig_SetStr(void *p,const char *name,const char *value) {
    (void)p; printf("PY_STR %s=%s\n",name,value);return 0;
}
int PyInitConfig_SetStrList(void *p,const char *name,size_t count,char *const *items) {
    (void)p; printf("PY_LIST %s=%zu\n",name,count);
    for(size_t i=0;i<count;i++) printf("PY_ITEM %s_%zu=%s\n",name,i,items[i]);
    return 0;
}
int PyInitConfig_GetError(void *p,const char **error) { (void)p; *error="authored configuration failure";return 1; }
int Py_InitializeFromInitConfig(void *p) { (void)p; puts("PY_INITIALIZE");return getenv("FIXTURE_INIT_FAIL") ? -1 : 0; }
int Py_RunMain(void) { puts("PY_RUN");return getenv("FIXTURE_PY_EXIT") ? atoi(getenv("FIXTURE_PY_EXIT")) : 0; }
""")
        dotnet = cls.root / "dotnet.c"
        dotnet.write_text(r"""
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <stddef.h>
#include <string.h>
struct parameters {size_t size;const char *host;const char *root;};
struct framework {size_t size;const char *name;const char *version;const char *path;};
struct environment {size_t size;const char *version;const char *commit;size_t sdk_count;const void *sdks;size_t count;const struct framework *frameworks;};
int32_t hostfxr_get_dotnet_environment_info(const char *root,void *reserved,void (*callback)(const struct environment *,void *),void *context){
    if(reserved) return -9;
    struct framework f={sizeof(f),"Microsoft.NETCore.App",getenv("FIXTURE_ENUM_VERSION")?getenv("FIXTURE_ENUM_VERSION"):"8.0.32",root};
    struct environment e={sizeof(e),"authored","authored",0,NULL,1,&f};
    callback(getenv("FIXTURE_BAD_ENUM") ? NULL : &e,context);return 0;
}
int32_t hostfxr_initialize_for_dotnet_command_line(int argc,const char **argv,const struct parameters *p,void **handle){
    printf("NET_HOST=%s\nNET_ROOT=%s\nNET_ARGC=%d\n",p->host,p->root,argc);
    for(int i=0;i<argc;i++) printf("NET_ARG_%d=%s\n",i,argv[i]);
    if(getenv("FIXTURE_INIT_FAIL")) return -11;
    *handle=(void*)0x1234;return 0;
}
int32_t hostfxr_get_runtime_property_value(void *handle,const char *name,const char **value) {
    (void)handle;
    const char *v=getenv(!strcmp(name,"FX_DEPS_FILE")?"FIXTURE_CORE_DEPS":"FIXTURE_TPA");
    if(!v) return -1;
    *value=v;return 0;
}
int32_t hostfxr_set_runtime_property_value(void *handle,const char *name,const char *value) {
    (void)handle;printf("NET_PROPERTY %s=%s\n",name,value);return getenv("FIXTURE_PROPERTY_FAIL")?-1:0;
}
int32_t hostfxr_run_app(void *handle){(void)handle;puts("NET_RUN");return getenv("FIXTURE_NET_EXIT")?atoi(getenv("FIXTURE_NET_EXIT")):0;}
int32_t hostfxr_close(void *handle){(void)handle;puts("NET_CLOSE");return 0;}
""")
        for name, path in (("python", python), ("dotnet", dotnet)):
            subprocess.run(["cc", "-shared", "-fPIC", str(path), "-o", str(cls.root / ("lib" + name + ".so"))], check=True, capture_output=True)

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def execute(self, name, arguments, extra=None, *, configured=True):
        env = {k: v for k, v in os.environ.items() if not k.startswith(("FIXTURE_", "ROR2LAB_BUILD_"))}
        if configured:
            env.update(ROR2LAB_BUILD_DOTNET_ROOT="/authored framework", ROR2LAB_BUILD_HOSTFXR=str(self.root / "libdotnet.so"))
        env.update(extra or {})
        return subprocess.run([str(self.root / name), *map(str, arguments)], env=env, capture_output=True, text=True, timeout=10)

    def python(self, extra=None, arguments=None):
        return self.execute("NativePythonHost", arguments or [self.root / "libpython.so", "/authored home", "script path.py", "argument space"], extra)

    def test_muxer_points_corelib_at_framework_data_before_running(self):
        framework = self.root / "authored framework"
        framework.mkdir(exist_ok=True)
        (framework / "System.Private.CoreLib.dll").write_bytes(b"authored data fixture")
        original = "/app/A.dll:/installed/native/System.Private.CoreLib.dll:/app/B.dll"
        env = {"FIXTURE_CORE_DEPS": str(framework / "Microsoft.NETCore.App.deps.json"), "FIXTURE_TPA": original}
        p = self.execute("NativeDotnetMuxer", ["app.dll"], env)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn("NET_PROPERTY TRUSTED_PLATFORM_ASSEMBLIES=/app/A.dll:" + str(framework / "System.Private.CoreLib.dll") + ":/app/B.dll", p.stdout)
        self.assertLess(p.stdout.index("NET_PROPERTY"), p.stdout.index("NET_RUN"))
        p = self.execute("NativeDotnetMuxer", ["app.dll"], env | {"FIXTURE_PROPERTY_FAIL": "1"})
        self.assertEqual(p.returncode, 72)
        self.assertNotIn("NET_RUN", p.stdout)

    def test_python_opaque_api_receives_isolation_paths_and_arguments(self):
        p = self.python()
        self.assertEqual(p.returncode, 0, p.stderr)
        for value in (
            "isolated=1",
            "use_environment=0",
            "site_import=0",
            "write_bytecode=0",
            "parse_argv=0",
            "safe_path=1",
            "module_search_paths_set=1",
            "buffered_stdio=0",
        ):
            self.assertIn("PY_INT " + value, p.stdout)
        for value in (
            "PY_STR home=/authored home",
            "PY_STR run_filename=script path.py",
            "PY_LIST module_search_paths=2",
            "PY_ITEM module_search_paths_0=/authored home/lib/python3.14",
            "PY_ITEM module_search_paths_1=/authored home/lib/python3.14/lib-dynload",
            "PY_LIST argv=2",
            "PY_ITEM argv_0=script path.py",
            "PY_ITEM argv_1=argument space",
            "PY_INITIALIZE",
            "PY_FREE",
            "PY_RUN",
        ):
            self.assertIn(value, p.stdout)
        self.assertIn("PYTHON_HOST_EXIT=0", p.stderr)
        self.assertIn("PYTHON_MAPS_END", p.stderr)

    def test_python_configuration_failure_frees_and_never_runs(self):
        for flag in ("FIXTURE_SET_FAIL", "FIXTURE_INIT_FAIL"):
            with self.subTest(flag=flag):
                p = self.python({flag: "1"})
                self.assertEqual(p.returncode, 69, p.stderr)
                self.assertEqual(p.stdout.count("PY_FREE"), 1)
                self.assertNotIn("PY_RUN", p.stdout)
                self.assertIn("authored configuration failure", p.stderr)

    def test_python_creation_and_library_failures_refuse(self):
        self.assertEqual(self.python({"FIXTURE_CREATE_FAIL": "1"}).returncode, 68)
        self.assertEqual(self.python(arguments=[self.root / "absent.so", "/home", "script.py"]).returncode, 66)
        self.assertEqual(self.execute("NativePythonHost", []).returncode, 64)

    def test_python_script_exit_is_preserved(self):
        p = self.python({"FIXTURE_PY_EXIT": "19"})
        self.assertEqual(p.returncode, 19)
        self.assertIn("PYTHON_HOST_EXIT=19", p.stderr)
        self.assertIn("PYTHON_MAPS_END", p.stderr)

    def test_dotnet_enumeration_uses_api_result_without_stdout_diagnostics(self):
        p = self.execute("NativeDotnetMuxer", ["--list-runtimes"], {"FIXTURE_ENUM_VERSION": "9.9.9"})
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(p.stdout, "Microsoft.NETCore.App 9.9.9 [/authored framework]\n")
        self.assertIn("DOTNET_HOST_UID=", p.stderr)
        self.assertIn("DOTNET_MAPS_END", p.stderr)

    def test_dotnet_incomplete_enumeration_refuses(self):
        p = self.execute("NativeDotnetMuxer", ["--list-runtimes"], {"FIXTURE_BAD_ENUM": "1"})
        self.assertEqual(p.returncode, 68)

    def test_dotnet_exec_forwards_application_arguments_root_and_exit(self):
        p = self.execute("NativeDotnetMuxer", ["exec", "app path.dll", "arg space"], {"FIXTURE_NET_EXIT": "17"})
        self.assertEqual(p.returncode, 17)
        for value in (
            "NET_HOST=" + str(self.root / "NativeDotnetMuxer"),
            "NET_ROOT=/authored framework",
            "NET_ARGC=3",
            "NET_ARG_0=exec",
            "NET_ARG_1=app path.dll",
            "NET_ARG_2=arg space",
            "NET_RUN",
            "NET_CLOSE",
        ):
            self.assertIn(value, p.stdout)

    def test_dotnet_exec_preserves_runtime_configuration_option(self):
        p = self.execute("NativeDotnetMuxer", ["exec", "--runtimeconfig", "config path.json", "app.dll"])
        self.assertEqual(p.returncode, 0, p.stderr)
        for value in ("NET_ARGC=4", "NET_ARG_0=exec", "NET_ARG_1=--runtimeconfig", "NET_ARG_2=config path.json", "NET_ARG_3=app.dll"):
            self.assertIn(value, p.stdout)

    def test_dotnet_failed_initialization_never_runs_invalid_context(self):
        p = self.execute("NativeDotnetMuxer", ["exec", "app.dll"], {"FIXTURE_INIT_FAIL": "1"})
        self.assertEqual(p.returncode, 69)
        self.assertNotIn("NET_RUN", p.stdout)
        self.assertNotIn("NET_CLOSE", p.stdout)

    def test_dotnet_requires_explicit_configuration_and_complete_invocation(self):
        self.assertEqual(self.execute("NativeDotnetMuxer", ["app.dll"], configured=False).returncode, 64)
        self.assertEqual(self.execute("NativeDotnetMuxer", ["exec"]).returncode, 64)


if __name__ == "__main__":
    unittest.main()
