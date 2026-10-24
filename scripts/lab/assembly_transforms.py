"""Reproduce the reviewed plugin transforms in disposable local scratch; work is read-only."""

import json
import os
from pathlib import Path
import shutil
import tempfile

from common import RECIPE, ROOT, WORK, game, read, run, sha


MODES = {
    "--optional-presentation-guard": ("RoR2.dll",),
    "--wwise-unavailable": ("AK.Wwise.Unity.API.dll", "AK.Wwise.Unity.MonoBehaviour.dll"),
}


def arguments(names):
    return [token for name in names for token in ("{original:" + name + "}", "{output:" + name + "}", "{sha256:" + name + "}")] + ["{managed}"]


def load_recipe():
    recipe = read(RECIPE / "assembly-transforms.json")
    if recipe["schema"] != 1 or [step["mode"] for step in recipe["steps"]] != list(MODES):
        raise RuntimeError("Unsupported assembly transform sequence")
    for step in recipe["steps"]:
        names = MODES[step["mode"]]
        if step["arguments"] != arguments(names) or set(step["inputs"]) != set(names) or set(step["outputs"]) != set(names):
            raise RuntimeError("Unsupported assembly transform arguments or membership")
    sources = {p.relative_to(ROOT).as_posix(): sha(p) for p in sorted((ROOT / "tools/assembly-transforms").iterdir()) if p.suffix in {".cs", ".csproj"}}
    if sources != recipe["tool_sources"]:
        raise RuntimeError("AssemblyProbe source drift")
    return recipe


class RebuiltAssemblyDrift(RuntimeError):
    def __init__(self, name, expected, actual, checked):
        super().__init__("Rebuilt assembly drift: " + name)
        self.difference = {"assembly": name, "reason": "rebuilt_sha256", "expected": expected, "actual": actual}
        self.checked = checked


def generate(managed, temporary, recipe, *, dotnet=None, unity_editor=None):
    """Replay J563 into caller-owned scratch; never write inputs or checkout tool outputs."""
    editor = Path(unity_editor if unity_editor is not None else os.environ["UNITY_EDITOR"])
    cecil = editor.parent.parent / "MonoBleedingEdge/lib/mono/gac/Mono.Cecil/0.11.1.0__0738eb9f132ed756/Mono.Cecil.dll"
    if sha(cecil) != recipe["cecil_sha256"]:
        raise RuntimeError("Mono.Cecil drift")
    inputs = {name: value for step in recipe["steps"] for name, value in step["inputs"].items()}
    original = temporary / "original"
    original.mkdir()
    for source in managed.glob("*.dll"):
        shutil.copyfile(source, original / source.name)
    for name, expected in inputs.items():
        if sha(original / name) != expected:
            raise RuntimeError("Copied original assembly drift: " + name)
    dotnet = Path(dotnet) if dotnet is not None else Path.home() / ".local/share/dotnet/dotnet"
    tool = temporary / "tool"
    # Build an isolated copy of the tool sources: the checkout may hold obj/ and bin/ from
    # ordinary probe_tool builds, which MSBuild would otherwise compile alongside.
    sources = temporary / "src"
    shutil.copytree(ROOT / "tools/assembly-transforms", sources, ignore=shutil.ignore_patterns("obj", "bin"))
    # This tool has no package references; keep restore configuration and caches
    # local as well, without consulting or initializing a user's NuGet config.
    nuget_config = temporary / "NuGet.Config"
    nuget_config.write_text("<configuration><packageSources><clear /></packageSources></configuration>\n")
    environment = dict(os.environ)
    environment.update(
        DOTNET_CLI_HOME=str(temporary / "dotnet-home"),
        NUGET_PACKAGES=str(temporary / "nuget"),
        NUGET_HTTP_CACHE_PATH=str(temporary / "nuget-http"),
        NUGET_PLUGINS_CACHE_PATH=str(temporary / "nuget-plugins"),
        TMPDIR=str(temporary),
        TMP=str(temporary),
        TEMP=str(temporary),
        DOTNET_CLI_TELEMETRY_OPTOUT="1",
        DOTNET_SKIP_FIRST_TIME_EXPERIENCE="1",
        DOTNET_CLI_WORKLOAD_UPDATE_NOTIFY_DISABLE="true",
        MSBUILDDISABLENODEREUSE="1",
        DOTNET_CLI_USE_MSBUILD_SERVER="0",
    )
    process = dict(timeout=120, cwd=temporary, env=environment)
    run(
        [
            dotnet,
            "build",
            sources / "AssemblyProbe.csproj",
            "-o",
            tool,
            "-p:CecilPath=" + str(cecil),
            "-p:RestoreConfigFile=" + str(nuget_config),
            "-p:UseSharedCompilation=false",
            "--nologo",
        ],
        **process,
    )
    checked = 0
    for step in recipe["steps"]:
        tokens = {"{managed}": original}
        for name, expected in step["inputs"].items():
            tokens.update({"{original:" + name + "}": original / name, "{output:" + name + "}": temporary / name, "{sha256:" + name + "}": expected})
        run([dotnet, tool / "AssemblyProbe.dll", step["mode"]] + [tokens[token] for token in step["arguments"]], **process)
        for name, expected in step["outputs"].items():
            actual = sha(temporary / name)
            checked += 1
            if actual != expected:
                raise RebuiltAssemblyDrift(name, expected, actual, checked)
    return {name: temporary / name for step in recipe["steps"] for name in step["outputs"]}


def check(work=None):
    work = Path(work or WORK).resolve()
    recipe = load_recipe()
    accepted = read(work / "config/accepted-input.json")
    project = work / "lab-project"
    generation = read(project / ".port-input.json")
    if accepted["input_id"] != recipe["input_id"] or generation["input_id"] != recipe["input_id"]:
        raise RuntimeError("Assembly transforms require the accepted generation")
    inputs = {name: value for step in recipe["steps"] for name, value in step["inputs"].items()}
    outputs = {name: value for step in recipe["steps"] for name, value in step["outputs"].items()}
    if generation["transformed_assemblies"] != outputs or any(generation["original_assemblies"].get(name) != value for name, value in inputs.items()):
        raise RuntimeError("Assembly generation hashes differ from recipe")
    managed = game(work) / "Risk of Rain 2_Data/Managed"
    for name, expected in inputs.items():
        if sha(managed / name) != expected:
            raise RuntimeError("Original assembly drift: " + name)
    cecil = Path(os.environ["UNITY_EDITOR"]).parent.parent / "MonoBleedingEdge/lib/mono/gac/Mono.Cecil/0.11.1.0__0738eb9f132ed756/Mono.Cecil.dll"
    if sha(cecil) != recipe["cecil_sha256"]:
        raise RuntimeError("Mono.Cecil drift")
    scratch = ROOT / ".local"
    resolved_scratch = scratch.resolve()
    installation = managed.parent.parent.resolve()
    if resolved_scratch != ROOT.resolve() / ".local" or any(tree == resolved_scratch or tree in resolved_scratch.parents for tree in (work, installation)):
        raise RuntimeError("Assembly scratch must be inside this clone and outside input trees")
    scratch.mkdir(exist_ok=True)
    differences = []
    checked = 0
    with tempfile.TemporaryDirectory(prefix="assembly-transforms-", dir=scratch) as directory:
        temporary = Path(directory)
        try:
            generate(managed, temporary, recipe)
        except RebuiltAssemblyDrift as error:
            return {"checked": error.checked, "differences": [error.difference]}
        checked = len(outputs)
        for name, expected in outputs.items():
            matches = list((project / "Assets").rglob(name))
            if len(matches) != 1:
                differences.append({"assembly": name, "reason": "project_placement", "count": len(matches)})
            elif sha(matches[0]) != expected:
                differences.append({"assembly": name, "reason": "project_sha256", "expected": expected, "actual": sha(matches[0])})
    return {"checked": checked, "differences": differences}


def check_action(work=None):
    result = check(work)
    print(json.dumps(result, indent=2))
    if result["differences"]:
        raise SystemExit(1)
