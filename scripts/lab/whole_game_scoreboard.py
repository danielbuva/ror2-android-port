"""Admit a whole-game scoreboard request through the lab CLI."""

import json
from hashlib import file_digest
from pathlib import Path, PurePosixPath
import re
import shlex
import subprocess
import sys

from common import ROOT

OWNER = ROOT / "tools/phone-build/accepted-output"
CENSUS_SECONDS = 900


def report(request):
    if request in (None, "lab"):
        raise ValueError("whole-game-scoreboard requires --target REQUEST.json")
    source = OWNER / "whole_game_scoreboard.py"
    return json.loads(subprocess.check_output([sys.executable, str(source), str(Path(request).resolve())]))


def installed_census(phone, installer, receipt, device, tour):
    """Read the retained signed APK inside its installer, then join JSON evidence."""
    phone.require_owned_installer()
    prefix = ("run-as", installer.PACKAGE)

    def private(*args, label):
        return phone.command("shell", shlex.join([*prefix, *args]), label=label, idempotent=True)

    def canonical(path):
        return PurePosixPath(private("readlink", "-f", path, label="nightly-census-path").decode().strip())

    home = canonical(".")
    fixture = json.loads(private("cat", "files/tool-host-report.json", label="nightly-census-toolhost"))
    runtime = canonical(fixture["dataDirectory"])
    native = canonical(fixture["nativeDirectory"])
    apk = canonical(receipt["apk"])
    digest = device.installed["apk_sha256"]
    package_path = phone.package_paths(installer.PACKAGE)[0].removeprefix("package:")
    if (
        fixture.get("success") is not True
        or fixture.get("ownerApk", {}).get("sha256") != digest
        or runtime.parent != home / "files"
        or not re.fullmatch(r"fixture-\d+", runtime.name)
        or not native.is_relative_to(PurePosixPath(package_path).parent)
        or not apk.is_relative_to(home / "files/owner-input/work/releases")
    ):
        raise installer.Failure("nightly-census-ownership-mismatch")

    relative = "nightly-census"
    scratch = home / "files/owner-input" / relative
    for name in ("whole_game_scoreboard.py", "unity_write.py", "unity_bundle.py", "phone_runner.py"):
        phone.put(relative + "/" + name, (OWNER / name).read_bytes())
    phone.put(
        relative + "/request.json",
        installer.encoded(
            {
                "schema": "whole-game-scoreboard-request-v1",
                "candidate": {"apk": {"path": str(apk), "sha256": digest}},
                "output": str(scratch / "census.json"),
            }
        ),
    )
    python = [str(native / "libpythonhost.so"), str(native / "libpython3.14.so"), str(runtime / "python")]
    command = [
        "sh",
        "-c",
        'export LD_LIBRARY_PATH="$1"; shift; exec "$@"',
        "census",
        f"{native}:{runtime / 'native-links'}",
        *python,
        str(scratch / "phone_runner.py"),
        "--timeout",
        str(CENSUS_SECONDS),
        "--receipt",
        str(scratch / "thermal.json"),
        "--samples",
        str(scratch / "resources.jsonl"),
        "--",
        *python,
        str(scratch / "whole_game_scoreboard.py"),
        str(scratch / "request.json"),
    ]
    diagnostics = installer.DIAGNOSTICS
    job = phone.transport.start_detached(
        command,
        label="nightly-census",
        root=str(scratch),
        shell_prefix=prefix,
        persist=lambda handle: diagnostics.write("census-job.json", installer.encoded(handle)),
    )
    terminal = phone.transport.wait_detached(job, diagnostics.directory, timeout=CENSUS_SECONDS + 60, label="nightly-census", transfer_logs=False)
    phone.transport.cleanup_detached(job)
    thermal = phone.read(relative + "/thermal.json")
    diagnostics.write("census-thermal.json", installer.encoded(thermal))
    if terminal.returncode or not thermal or thermal.get("success") is not True:
        raise installer.Failure("nightly-census-producer-failed")
    diagnostics.write("census-resources.jsonl", private("cat", str(scratch / "resources.jsonl"), label="nightly-census-resources"))
    census = phone.read(relative + "/census.json")
    if not census or census.get("apk_sha256") != digest:
        raise installer.Failure("nightly-census-apk-mismatch")
    diagnostics.write("census.json", installer.encoded(census))
    local_census = diagnostics.directory / "census.json"
    request = diagnostics.directory / "scoreboard-request.json"
    with local_census.open("rb") as stream:
        census_sha = file_digest(stream, "sha256").hexdigest()
    with tour.open("rb") as stream:
        tour_sha = file_digest(stream, "sha256").hexdigest()
    diagnostics.write(
        request.name,
        installer.encoded(
            {
                "schema": "whole-game-scoreboard-request-v1",
                "output": str(diagnostics.directory / "scoreboard.json"),
                "census": {"path": str(local_census), "sha256": census_sha},
                "device_receipts": [{"path": str(tour), "sha256": tour_sha}],
            }
        ),
    )
    report(request)
