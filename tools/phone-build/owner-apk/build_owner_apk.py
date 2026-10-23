"""Build a private owner APK with an authored pre-Unity payload bootstrap.

Inputs are explicit ignored local state. No Unity Editor, game compilation,
runtime replacement or current game-build mutation occurs. Generated APKs/data
contain protected owner inputs and must never be committed or published here.
"""

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import time
import zipfile


SOURCE = Path(__file__).resolve().parent
PROFILE = "93789f88d8fff178e31e1a4b78bc5cf735bb63f6e17d8bfd4518474dbff99d4a"
ART = "6f73ee2c7a9d6544b5f2972832b12a7aed3f98cf9ba00fc04b218502f65ea4ff"
RESERVE = 8 * 1024**3


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


PACKET = module("_owner_packet", SOURCE.parent / "accepted-output/package.py")
ASSEMBLY = module("_owner_assembly", SOURCE.parent / "accepted-output/assemble.py")
MANIFEST = module("_owner_manifest", SOURCE / "binary_manifest.py")


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def build(request_path, output):
    request = json.loads(Path(request_path).read_text())
    fields = {"manifest", "manifest_sha256", "targets", "frontend", "java", "android_jar", "d8_jar", "wire_helper"}
    if set(request) != fields or request["manifest_sha256"] != PROFILE:
        raise ValueError("unsupported owner APK request/profile")
    roots = {key: Path(request[key]).resolve(strict=True) for key in fields - {"manifest_sha256"}}
    output = Path(output).absolute()
    for selected in (roots["targets"], roots["frontend"], SOURCE):
        if output.resolve().is_relative_to(selected) or selected.is_relative_to(output.resolve()):
            raise ValueError("owner APK output overlaps source inputs")
    _, profile = PACKET.profile(roots["manifest"], PROFILE)
    if sha(roots["frontend"] / "background.png") != ART:
        raise ValueError("approved launcher art pin differs")
    wire = module("_owner_wire", roots["wire_helper"])
    output.mkdir(mode=0o700)
    started = time.monotonic()
    result = {
        "schema": 1,
        "success": False,
        "profile": PROFILE,
        "installs": 0,
        "editor_actions": 0,
        "game_compilations": 0,
        "public_distribution_qualified": False,
    }
    try:
        tracked = [
            SOURCE / n
            for n in ("PayloadStore.java", "PayloadBootstrapActivity.java", "index.html", "owner-host.js", "binary_manifest.py", "build_owner_apk.py")
        ]
        tracked += [roots["frontend"] / n for n in ("app.js", "controller.js", "style.css", "background.png")]
        tracked += [Path(PACKET.__file__), Path(ASSEMBLY.__file__)]
        tracked += [roots[k] for k in ("java", "android_jar", "d8_jar", "wire_helper", "manifest")]
        result["inputs"] = {str(p): {"bytes": p.stat().st_size, "sha256": sha(p)} for p in tracked}

        def run(command, label):
            with (output / (label + ".log")).open("x") as log:
                subprocess.run([str(x) for x in command], stdout=log, stderr=subprocess.STDOUT, check=True, timeout=180)

        classes, dex = output / "classes", output / "dex"
        classes.mkdir()
        dex.mkdir()
        run(
            [
                roots["java"].with_name("javac"),
                "-source",
                "8",
                "-target",
                "8",
                "-classpath",
                roots["android_jar"],
                "-d",
                classes,
                SOURCE / "PayloadStore.java",
                SOURCE / "PayloadBootstrapActivity.java",
            ],
            "javac",
        )
        jar = output / "bootstrap.jar"
        with zipfile.ZipFile(jar, "x") as archive:
            for path in sorted(classes.rglob("*.class")):
                archive.writestr(zipfile.ZipInfo(path.relative_to(classes).as_posix(), (2020, 1, 1, 0, 0, 0)), path.read_bytes())
        run(
            [
                roots["java"],
                "-Xmx512m",
                "-cp",
                roots["d8_jar"],
                "com.android.tools.r8.D8",
                "--min-api",
                "22",
                "--lib",
                roots["android_jar"],
                "--output",
                dex,
                jar,
            ],
            "dex",
        )
        if {p.name for p in dex.iterdir()} != {"classes.dex"}:
            raise ValueError("bootstrap requires exactly one authored DEX")
        apk_rows = {r["path"][4:]: r for r in profile["targets"] if r["path"].startswith("apk/") and not ASSEMBLY.obsolete_signature(r["path"][4:])}
        manifest_row = apk_rows["AndroidManifest.xml"]
        patched = MANIFEST.patch(PACKET.verify(roots["targets"], manifest_row).read_bytes(), wire)
        (output / "AndroidManifest.xml").write_bytes(patched)
        payload = [r for r in profile["targets"] if r["path"].startswith("payload/") and not r["path"].endswith(".manifest")]
        index = {"schema": 1, "profile": PROFILE, "files": [{"name": r["path"][8:], "bytes": r["bytes"], "sha256": r["sha256"]} for r in payload]}
        index_bytes = (json.dumps(index, sort_keys=True, separators=(",", ":")) + "\n").encode()
        next_dex = "classes" + str(1 + sum(n.endswith(".dex") and n.startswith("classes") for n in apk_rows)) + ".dex"
        if next_dex in apk_rows:
            raise ValueError("authored DEX name collides")
        expected = {}
        unsigned = output / "owner-unsigned.apk"
        with unsigned.open("xb") as raw, zipfile.ZipFile(raw, "w", allowZip64=False) as archive:

            def entry(name, *, source=None, data=None, expected_sha=None, expected_bytes=None):
                if shutil.disk_usage(output).free < RESERVE or time.monotonic() - started > 1800:
                    raise RuntimeError("owner APK storage reserve/deadline reached")
                if name in expected:
                    raise ValueError("duplicate owner APK entry")
                info = zipfile.ZipInfo(name, (2020, 1, 1, 0, 0, 0))
                info.external_attr = 0o100644 << 16
                info.file_size = len(data) if data is not None else source.stat().st_size
                info.compress_type = zipfile.ZIP_STORED if name == "resources.arsc" else zipfile.ZIP_DEFLATED
                info._compresslevel = 9
                if info.compress_type == zipfile.ZIP_STORED:
                    padding = (-(raw.tell() + 30 + len(name.encode()) + 4)) % 4
                    info.extra = struct.pack("<HH", 0xD935, padding) + b"\0" * padding
                digest = hashlib.sha256()
                size = 0
                with archive.open(info, "w") as destination:
                    if data is not None:
                        destination.write(data)
                        digest.update(data)
                        size = len(data)
                    else:
                        with source.open("rb") as original:
                            while chunk := original.read(65536):
                                destination.write(chunk)
                                digest.update(chunk)
                                size += len(chunk)
                value = digest.hexdigest()
                if (expected_sha is not None and value != expected_sha) or (expected_bytes is not None and size != expected_bytes):
                    raise ValueError("owner APK source bytes differ")
                expected[name] = {"bytes": size, "sha256": value}

            for name, row in apk_rows.items():
                if name == "AndroidManifest.xml":
                    entry(name, data=patched)
                else:
                    entry(name, source=PACKET.verify(roots["targets"], row), expected_sha=row["sha256"], expected_bytes=row["bytes"])
            entry(next_dex, source=dex / "classes.dex")
            for name in ("app.js", "controller.js", "style.css", "background.png"):
                entry("assets/owner-bootstrap/ui/" + name, source=roots["frontend"] / name)
            for name in ("index.html", "owner-host.js"):
                entry("assets/owner-bootstrap/ui/" + name, source=SOURCE / name)
            entry("assets/owner-bootstrap/payload-index.json", data=index_bytes)
            for row in payload:
                entry(
                    "assets/owner-bootstrap/data/" + row["path"][8:],
                    source=PACKET.verify(roots["targets"], row),
                    expected_sha=row["sha256"],
                    expected_bytes=row["bytes"],
                )
        with zipfile.ZipFile(unsigned) as archive:
            if set(archive.namelist()) != set(expected) or len(archive.infolist()) != len(expected):
                raise ValueError("owner APK membership differs")
            for name, row in expected.items():
                with archive.open(name) as stream:
                    if hashlib.file_digest(stream, "sha256").hexdigest() != row["sha256"]:
                        raise ValueError("owner APK independent readback differs")
        for name, row in result["inputs"].items():
            if sha(Path(name)) != row["sha256"]:
                raise ValueError("owner preparation input changed")
        result.update(
            success=True,
            apk_sha256=sha(unsigned),
            apk_bytes=unsigned.stat().st_size,
            original_entries_preserved=len(apk_rows) - 1,
            original_entry_changed="AndroidManifest.xml",
            new_dex=next_dex,
            entries_verified=len(expected),
            runtime_payload_files=len(payload),
            runtime_payload_bytes=sum(r["bytes"] for r in payload),
            il2cpp_or_original_dex_changed=False,
            signed=False,
            device_qualified=False,
        )
        return result
    except Exception as error:
        result.update(error_type=type(error).__name__, error=str(error))
        raise
    finally:
        result["seconds"] = time.monotonic() - started
        (output / "result.json").write_text(json.dumps(result, indent=2) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.request, args.output)))


if __name__ == "__main__":
    main()
