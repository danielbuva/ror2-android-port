"""Run the owner SDK's pinned Roslyn with the installed Android .NET launcher."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

from phone_managed_compile import INPUTS, RUNTIMES, sha
from public_transform_tools import GLOBALS


def python_command(script, *, isolated=False):
    """Start a child through the same CPython host as this process."""
    executable = Path(sys.executable)
    if sys.platform == "android" and executable.name == "libpythonhost.so":
        return [str(executable), str(executable.with_name("libpython3.14.so")), sys.prefix, str(script)]
    return [sys.executable, *(["-I"] if isolated else []), str(script)]


class SdkCompiler:
    def __init__(self, sdk, launcher, scratch):
        self.sdk = sdk
        self.contents = sdk / "Unity.app/Contents"
        self.launcher = launcher
        self.inputs = {self.contents / relative: digest for relative, digest in INPUTS.values()}
        self.verify()
        self.runtime_config = scratch / "sdk-roslyn.runtimeconfig.json"
        self.write_runtime_config(self.runtime_config, RUNTIMES["android"])

    @staticmethod
    def write_runtime_config(path, version):
        path.write_text(json.dumps({"runtimeOptions": {"framework": {"name": "Microsoft.NETCore.App", "version": version}}}) + "\n")

    def verify(self):
        if any(sha(path) != digest for path, digest in self.inputs.items()):
            raise ValueError("Pinned SDK Roslyn or core library drift")

    @property
    def corelib(self):
        return self.contents / INPUTS["refs/mscorlib.dll"][0]

    @property
    def command(self):
        return [
            str(self.launcher),
            "exec",
            "--runtimeconfig",
            str(self.runtime_config),
            str(self.contents / INPUTS["compiler/csc.dll"][0]),
            "-noconfig",
            "-nostdlib+",
        ]

    @property
    def tool_framework(self):
        (framework,) = sorted((Path(os.environ["ROR2LAB_BUILD_DOTNET_ROOT"]) / "shared/Microsoft.NETCore.App").glob("10.*"))
        return framework

    def tool_environment(self, env=None):
        result = dict(os.environ if env is None else env)
        result["LD_LIBRARY_PATH"] = os.pathsep.join(filter(None, (str(self.tool_framework), result.get("LD_LIBRARY_PATH"))))
        return result

    def tool(self, assembly, sources, cecil, *, env=None):
        """Compile authored Cecil tools for the installed .NET 10 framework."""
        runtime = self.tool_framework
        refs = sorted(p for p in runtime.glob("*.dll") if p.is_file())
        assembly.parent.mkdir(parents=True, exist_ok=True)
        imports = assembly.parent / "GlobalUsings.cs"
        imports.write_text(GLOBALS)
        args = ["-target:exe", "-nullable:enable", "-langversion:latest"]
        self.compile(assembly, [*sources, imports], [*refs, cecil], args, env=env)
        shutil.copyfile(cecil, assembly.with_name("Mono.Cecil.dll"))
        self.write_runtime_config(assembly.with_suffix(".runtimeconfig.json"), runtime.name)

    def compile(self, assembly, sources, refs, args, *, env=None):
        rsp = assembly.with_suffix(".rsp")
        rsp.write_text(
            "\n".join(
                [
                    *args,
                    "-deterministic+",
                    "-out:" + json.dumps(str(assembly)),
                    *["-r:" + json.dumps(str(path)) for path in refs],
                    *[json.dumps(str(path)) for path in sources],
                ]
            )
            + "\n"
        )
        log = assembly.with_suffix(".compile.log")
        with log.open("w") as stream:
            result = subprocess.run(self.command + ["@" + str(rsp)], env=env, stdout=stream, stderr=subprocess.STDOUT, timeout=180)
        if result.returncode:
            diagnostics = log.read_text().strip().splitlines()[-6:]
            raise RuntimeError(f"SDK Roslyn failed for {assembly.name} ({log}): " + "\n".join(diagnostics))
