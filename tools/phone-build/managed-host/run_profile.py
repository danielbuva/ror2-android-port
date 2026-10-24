"""Private glue to execute the unchanged public producer under the isolated host."""

import sys
from pathlib import Path
import hashlib
import json
import os
import runpy

root = Path(sys.argv[1]).resolve(strict=True)
inputs = root.parent / "user-input"
selection = json.loads((inputs / "input-hashes.json").read_text())
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()


def check_inputs():
    actual = {p.name: sha(p) for p in (inputs / "Managed").iterdir() if p.is_file()}
    if actual != selection["files"] or len(actual) != 146:
        raise RuntimeError("owned Managed input cohort drift")
    if any(p.is_symlink() for p in (inputs / "Managed").iterdir()):
        raise RuntimeError("Managed links refused")


if sys.version_info[:3] != (3, 14, 8) or sys.flags.isolated != 1 or sys.flags.no_site != 1 or sys.flags.ignore_environment != 1 or not sys.dont_write_bytecode:
    raise RuntimeError("Python isolated build profile differs")
check_inputs()
sys.path.insert(0, str(root / "repo/scripts/lab"))
sys.argv = [
    str(root / "repo/scripts/lab/public_transform_tools.py"),
    "--managed",
    str(inputs / "Managed"),
    "--dest",
    str(root / "repo/work/rebuild/app-component-v1"),
    "--archives",
    str(root / "archives"),
    "--launcher",
    os.environ["ROR2LAB_BUILD_DOTNET_LAUNCHER"],
    "--host",
    "android8",
]
runpy.run_path(sys.argv[0], run_name="__main__")
check_inputs()
native = {name: module.__file__ for name, module in sorted(sys.modules.items()) if str(getattr(module, "__file__", "")).endswith(".so")}
(root / "python-profile-report.json").write_text(
    json.dumps(
        dict(
            success=True,
            version=sys.version,
            isolated=sys.flags.isolated,
            no_site=sys.flags.no_site,
            ignore_environment=sys.flags.ignore_environment,
            dont_write_bytecode=sys.dont_write_bytecode,
            native_modules=native,
            managed_files=len(selection["files"]),
        ),
        indent=2,
    )
    + "\n"
)
