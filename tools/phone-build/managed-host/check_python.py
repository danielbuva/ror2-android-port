"""Import the staged phone producers with the same isolated application path."""

import importlib
import json
from pathlib import Path
import runpy
import sys


def check(runtime, plan):
    if not (sys.flags.isolated and sys.flags.no_site and sys.flags.safe_path):
        raise RuntimeError("Toolhost import check requires an isolated interpreter")
    packages = str(runtime / "python/lib/player-packages")
    if packages not in sys.path:
        sys.path.append(packages)
    for name in plan["stdlib_modules"]:
        importlib.import_module(name)
    for name in plan["modules"]:
        module = importlib.import_module(name)
        # Native module imports use a staged alias to a PackageManager library.
        if not Path(module.__file__).is_relative_to(packages):
            raise ImportError("Module is outside the staged runtime: " + name)
    search_path = sys.path[:]
    loaded = set(sys.modules)
    dispatcher = runpy.run_path(str(runtime / plan["release_dispatcher"]))
    sources = {*plan["entries"], *("repo/" + name for name in dispatcher["PRODUCERS"])}
    sys.path[:] = search_path
    for source in sorted(sources):
        for name in sys.modules.keys() - loaded:
            module_path = getattr(sys.modules[name], "__file__", None)
            if module_path and Path(module_path).is_relative_to(runtime / "repo"):
                del sys.modules[name]
        try:
            if source in plan["entry_paths"]:
                sys.path.insert(0, str(runtime / plan["entry_paths"][source]))
            runpy.run_path(str(runtime / source))
        except ImportError as error:
            raise ImportError(f"{source}: {error}") from error
        finally:
            sys.path[:] = search_path
    return {"entry_points": len(sources), "modules": len(plan["modules"])}


if __name__ == "__main__":
    runtime, manifest = (Path(argument).resolve(strict=True) for argument in sys.argv[1:])
    print(json.dumps(check(runtime, json.loads(manifest.read_text())["python_imports"])))
