"""Build a private owner APK with an authored pre-Unity payload bootstrap.

Inputs are explicit ignored local state. No Unity Editor, game compilation,
runtime replacement or current game-build mutation occurs. Generated APKs/data
contain protected owner inputs and must never be committed or published here.
"""

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import secrets
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
CODE_ENTRIES = {
    "lib/arm64-v8a/libil2cpp.so",
    "lib/arm64-v8a/lib_burst_generated.so",
    "assets/bin/Data/Managed/Metadata/global-metadata.dat",
}


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


def code_paths(request):
    """Select a complete produced cohort, never replay fallbacks."""
    if "code" not in request:
        return {}
    if not isinstance(request["code"], dict) or not CODE_ENTRIES <= set(request["code"]):
        raise ValueError("all native, metadata and Burst code outputs required")
    if set(request["code"]) != CODE_ENTRIES:
        sdk = module("_owner_sdk_package", SOURCE.parent / "accepted-output/sdk_package.py")
        if set(request["code"]) != CODE_ENTRIES | sdk.SDK_ENTRIES:
            raise ValueError("complete SDK Android cohort required alongside code outputs")
    return request["code"]


def code_sources(request):
    sources = {}
    for name, value in code_paths(request).items():
        path = Path(value)
        if not path.is_absolute() or path != path.resolve(strict=True) or not path.is_file():
            raise ValueError("canonical produced code file required")
        sources[name] = {"path": str(path), "bytes": path.stat().st_size, "sha256": sha(path)}
    return sources


def explain_drift(pins, row):
    """Check retained qualification evidence; never read historical game files.

    Producer receipts establish provenance/causation for human review. Here we
    bind those receipts to one target, two current runs and a complete extent
    map, checking every current extent against the actual assembly supplier.
    """
    evidence = []

    def digest(value):
        if not isinstance(value, str) or len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
            raise ValueError("drift evidence requires SHA-256 pins")
        return value

    def receipt(value, *, qualification=True):
        path = Path(value["path"])
        if not path.is_absolute() or path != path.resolve(strict=True) or not path.is_file() or sha(path) != digest(value["sha256"]):
            raise ValueError("drift receipt pin differs")
        evidence.append({"path": str(path), "sha256": value["sha256"]})
        document = json.loads(path.read_text())
        if document.get("success") is False:
            raise ValueError("failed drift evidence")
        if qualification:
            if document["success"] is not True or document["path"] != row["path"]:
                raise ValueError("drift receipt failed or target differs")
            if not document["evidence"]:
                raise ValueError("raw producer/lineage evidence required")
            for raw in document["evidence"]:
                receipt(raw, qualification=False)
        return document

    def output(value):
        if type(value["bytes"]) is not int or value["bytes"] < 0:
            raise ValueError("invalid drift output size")
        return value["bytes"], digest(value["sha256"])

    historical = receipt(pins["historical_exact"])
    current = receipt(pins["current_deterministic"])
    if digest(historical["producer_sha256"]) != digest(current["producer_sha256"]):
        raise ValueError("historical and current drift producers differ")
    if output(historical) != (row["target_bytes"], row["target_sha256"]):
        raise ValueError("historical production is not exact to the target")
    if len(current["runs"]) < 2:
        raise ValueError("two current deterministic runs required")
    run_ids = set()
    for run in current["runs"]:
        if not isinstance(run["id"], str) or not run["id"].strip() or run["id"] in run_ids:
            raise ValueError("distinct current production run IDs required")
        run_ids.add(run["id"])
        if output(run) != (row["bytes"], row["sha256"]):
            raise ValueError("current deterministic production differs")
    mapping = receipt(pins["difference_map"])
    inputs = mapping["inputs"]
    if not inputs:
        raise ValueError("named original input differences required")
    for pair in inputs:
        identities = []
        for kind in ("historical", "current"):
            original = pair[kind]
            if original is None:
                identities.append(None)
                continue
            name = original["path"]
            if not isinstance(name, str) or not name or name.startswith("/") or "\\" in name or any(p in ("", ".", "..") for p in name.split("/")):
                raise ValueError("original drift input must name a relative game path")
            identities.append((name, *output(original)))
        if identities[0] == identities[1]:
            raise ValueError("drift must name a changed original input")
    old_end = new_end = 0
    changed = False
    with Path(row["source"]).open("rb") as stream:
        for operation in mapping["operations"]:
            old, new = operation["historical_range"], operation["current_range"]
            if any(not isinstance(r, list) or len(r) != 2 or any(type(v) is not int for v in r) for r in (old, new)):
                raise ValueError("invalid drift extent range")
            if old[0] != old_end or new[0] != new_end or not old[0] <= old[1] <= row["target_bytes"] or not new[0] <= new[1] <= row["bytes"]:
                raise ValueError("drift extent gap, overlap or bounds differ")
            old_hash, new_hash = digest(operation["historical_sha256"]), digest(operation["current_sha256"])
            if old[0] == old[1] and new[0] == new[1]:
                raise ValueError("empty drift operation")
            equal = old[1] - old[0] == new[1] - new[0] and old_hash == new_hash
            if not equal:
                changed = True
                origins = operation["inputs"]
                if not origins or any(type(i) is not int or not 0 <= i < len(inputs) for i in origins) or not operation["reason"].strip():
                    raise ValueError("changed output extent lacks named input lineage")
            digest_value = hashlib.sha256()
            remaining = new[1] - new[0]
            while remaining:
                chunk = stream.read(min(remaining, 65536))
                if not chunk:
                    raise ValueError("current drift output truncated")
                digest_value.update(chunk)
                remaining -= len(chunk)
            if digest_value.hexdigest() != new_hash:
                raise ValueError("current drift extent hash differs")
            old_end, new_end = old[1], new[1]
    if not changed or (old_end, new_end) != (row["target_bytes"], row["bytes"]):
        raise ValueError("drift map must explain both complete outputs")
    return evidence


def check(request):
    """Inventory final assembly inputs; byte equality never establishes provenance."""
    if request["manifest_sha256"] != PROFILE:
        raise ValueError("unsupported owner APK request/profile")
    _, profile = PACKET.profile(Path(request["manifest"]), PROFILE)
    code = code_paths(request)
    drift = request.get("drift", {})
    if not isinstance(drift, dict):
        raise ValueError("drift must map content target paths to pinned proofs")
    targets = Path(request["targets"]).resolve()
    startup = {}
    if "startup_metadata" in request:
        supplied = request["startup_metadata"]
        producer = module("_owner_startup", SOURCE.parent / "accepted-output/startup_metadata.py")
        startup = producer.verify(supplied["path"], supplied["sha256"])
        if set(startup) & set(drift):
            raise ValueError("startup metadata cannot also claim input drift")
    entries, omitted = [], []
    for target in profile["targets"]:
        name = target["path"]
        if name.startswith("apk/"):
            apk_name = name[4:]
            if ASSEMBLY.obsolete_signature(apk_name):
                omitted.append(name)
                continue
        elif name.startswith("payload/"):
            apk_name = None
            if name.endswith(".manifest"):
                omitted.append(name)
                continue
        else:
            raise ValueError("unsupported owner APK target path")
        produced = apk_name in code
        row = {
            "path": name,
            "owner": "code" if produced else "content" if code else "replay-control",
            "target_bytes": target["bytes"],
            "target_sha256": target["sha256"],
        }
        try:
            if produced:
                path = Path(code[apk_name])
                if not path.is_absolute() or path != path.resolve():
                    raise ValueError("canonical produced code file required")
            else:
                path = PACKET.safe(targets, name)
            row["source"] = str(path)
            if not path.exists():
                row["status"] = "missing"
            elif not path.is_file():
                raise ValueError("assembly input must be a regular file")
            else:
                row.update(bytes=path.stat().st_size, sha256=sha(path))
                equal = row["bytes"] == target["bytes"] and row["sha256"] == target["sha256"]
                row.update(status="ready" if produced or equal else "mismatch", target_equal=equal)
                if name in startup:
                    item = startup[name]
                    if (row["bytes"], row["sha256"]) != (item["bytes"], item["sha256"]):
                        raise ValueError("assembly startup bytes differ from regenerated metadata")
                    if not equal:
                        row["status"] = "generated-metadata"
                if name in drift:
                    if produced or equal:
                        raise ValueError("drift proof requires changed content, not code or exact output")
                    row["drift_evidence"] = explain_drift(drift[name], row)
                    row["status"] = "drift-explained"
        except (OSError, ValueError, TypeError, KeyError, AttributeError) as error:
            row.update(status="invalid", error=str(error))
        entries.append(row)
    selected = {row["path"][4:] for row in entries if row["owner"] == "code"}
    if selected != set(code):
        raise ValueError("produced code cohort not present in target profile")
    if set(drift) - {row["path"] for row in entries if row["owner"] != "code"}:
        raise ValueError("drift proof target not in content selection")
    if set(startup) - {row["path"] for row in entries if row["owner"] != "code"}:
        raise ValueError("startup metadata target not in content selection")
    blocked = [row["path"] for row in entries if row["status"] not in ("ready", "drift-explained", "generated-metadata")]
    return {
        "assembly_ready": not blocked,
        "selection": "produced-code-and-sdk" if len(code) > len(CODE_ENTRIES) else "produced-code" if code else "replay-control",
        "blocked_entries": blocked,
        "exact_count": sum(row.get("target_equal") is True and row["status"] == "ready" for row in entries),
        "drift_explained_count": sum(row["status"] == "drift-explained" for row in entries),
        "generated_metadata_count": sum(row["status"] == "generated-metadata" for row in entries),
        "code_comparison_required": [row["path"] for row in entries if row["owner"] == "code" and row.get("target_equal") is False],
        "entries": entries,
        "omitted_entries": omitted,
        "device_qualified": False,
        "source_provenance_verified": False,
    }


def sign(request_path, output):
    """Align/sign on the owner host, retaining one private key across builds."""
    request = json.loads(Path(request_path).read_text())
    if set(request) - {"keytool"} != {"unsigned", "java", "zipalign", "apksigner_jar", "key_directory"}:
        raise ValueError("explicit owner signing inputs required")
    inputs = {name: Path(request[name]).resolve(strict=True) for name in ("unsigned", "java", "zipalign", "apksigner_jar")}
    if "keytool" in request:
        inputs["keytool"] = Path(request["keytool"]).resolve(strict=True)
    keys = Path(request["key_directory"])
    output = Path(output).absolute()
    if not keys.is_absolute() or keys != keys.resolve() or output.resolve().is_relative_to(keys) or keys.is_relative_to(output.resolve()):
        raise ValueError("canonical durable key directory separate from build output required")
    if shutil.disk_usage(output.parent).free < 2 * inputs["unsigned"].stat().st_size + 2 * 1024**3:
        raise RuntimeError("owner signing storage reserve unavailable")
    keys.mkdir(mode=0o700, exist_ok=True)
    if keys.stat().st_mode & 0o077:
        raise ValueError("owner key directory must be private")
    key, password = keys / "owner.p12", keys / "password"
    if key.is_symlink() or password.is_symlink() or (key.exists() and not password.is_file()):
        raise ValueError("owner signing key/password state differs")
    output.mkdir(mode=0o700)
    before = {name: sha(path) for name, path in inputs.items()}
    result = {"success": False, "signed": False, "new_owner_key": not key.exists(), "installs": 0}
    started = time.monotonic()
    try:
        if not password.exists():
            with password.open("xb") as stream:
                os.chmod(password, 0o600)
                stream.write(secrets.token_urlsafe(40).encode())
        if password.stat().st_mode & 0o077 or not password.read_bytes():
            raise ValueError("owner password must be a nonempty private file")
        environment = dict(os.environ, ROR2_OWNER_SIGNING_PASSWORD=password.read_text())

        def run(label, command):
            with (output / (label + ".log")).open("xb") as log:
                subprocess.run(
                    list(map(str, command)), env=environment, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT, check=True, timeout=600
                )

        keytool = inputs.get("keytool", inputs["java"].with_name("keytool"))
        credentials = ["-keystore", key, "-storepass:env", "ROR2_OWNER_SIGNING_PASSWORD"]
        if not key.exists():
            run(
                "create-key",
                [
                    keytool,
                    "-genkeypair",
                    "-alias",
                    "owner",
                    "-dname",
                    "CN=Local Owner",
                    "-storetype",
                    "PKCS12",
                    *credentials,
                    "-keypass:env",
                    "ROR2_OWNER_SIGNING_PASSWORD",
                    "-keyalg",
                    "RSA",
                    "-keysize",
                    "2048",
                    "-validity",
                    "3650",
                    "-noprompt",
                ],
            )
            os.chmod(key, 0o600)
        if key.stat().st_mode & 0o077:
            raise ValueError("owner keystore must be private")
        run("check-key", [keytool, "-list", "-alias", "owner", *credentials])
        key_before, password_before = sha(key), sha(password)
        aligned, signed = output / "aligned.apk", output / "signed.apk"
        run("align", [inputs["zipalign"], "-P", "16", "4", inputs["unsigned"], aligned])
        run(
            "sign",
            [
                inputs["java"],
                "-jar",
                inputs["apksigner_jar"],
                "sign",
                "--ks",
                key,
                "--ks-key-alias",
                "owner",
                "--ks-pass",
                "env:ROR2_OWNER_SIGNING_PASSWORD",
                "--key-pass",
                "env:ROR2_OWNER_SIGNING_PASSWORD",
                "--v4-signing-enabled",
                "false",
                "--out",
                signed,
                aligned,
            ],
        )
        run("verify-signature", [inputs["java"], "-jar", inputs["apksigner_jar"], "verify", "--verbose", "--print-certs", signed])
        run("verify-alignment", [inputs["zipalign"], "-c", "-P", "16", "4", signed])

        def entries(apk):
            with zipfile.ZipFile(apk) as archive:
                rows = {}
                for item in archive.infolist():
                    if ASSEMBLY.obsolete_signature(item.filename):
                        continue
                    if item.filename in rows:
                        raise ValueError("duplicate APK entry")
                    with archive.open(item) as stream:
                        rows[item.filename] = (item.file_size, hashlib.file_digest(stream, "sha256").hexdigest())
                return rows

        if entries(inputs["unsigned"]) != entries(signed):
            raise ValueError("owner signing changed an APK content entry")
        if before != {name: sha(path) for name, path in inputs.items()} or key_before != sha(key) or password_before != sha(password):
            raise ValueError("owner signing input/key changed")
        result.update(success=True, signed=True, apk_sha256=sha(signed), apk_bytes=signed.stat().st_size)
        return result
    except Exception as error:
        result.update(error_type=type(error).__name__, error=str(error))
        raise
    finally:
        result["seconds"] = time.monotonic() - started
        (output / "result.json").write_text(json.dumps(result, indent=2) + "\n")


def build(request_path, output):
    request = json.loads(Path(request_path).read_text())
    fields = {"manifest", "manifest_sha256", "targets", "frontend", "java", "android_jar", "d8_jar", "wire_helper"}
    if set(request) - {"version_code", "code", "javac", "drift"} != fields or request["manifest_sha256"] != PROFILE:
        raise ValueError("unsupported owner APK request/profile")
    code = code_paths(request)
    version_code = request.get("version_code")
    if "version_code" in request and (type(version_code) is not int or not 1 <= version_code <= 2100000000):
        raise ValueError("owner version code must be between 1 and 2100000000")
    roots = {key: Path(request[key]).resolve() for key in fields - {"manifest_sha256"}}
    if "javac" in request:
        roots["javac"] = Path(request["javac"]).resolve()
    output = Path(output).absolute()
    for selected in (roots["targets"], roots["frontend"], SOURCE, *(Path(path).resolve() for path in code.values())):
        if output.resolve().is_relative_to(selected) or selected.is_relative_to(output.resolve()):
            raise ValueError("owner APK output overlaps source inputs")
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
        readiness = check(request)
        (output / "readiness.json").write_text(json.dumps(readiness, indent=2) + "\n")
        if not readiness["assembly_ready"]:
            raise ValueError("owner APK inputs incomplete; see readiness.json for every blocked entry")
        code = code_sources(request)
        roots = {key: path.resolve(strict=True) for key, path in roots.items()}
        _, profile = PACKET.profile(roots["manifest"], PROFILE)
        if sha(roots["frontend"] / "background.png") != ART:
            raise ValueError("approved launcher art pin differs")
        wire = module("_owner_wire", roots["wire_helper"])
        tracked = [
            SOURCE / n
            for n in ("PayloadStore.java", "PayloadBootstrapActivity.java", "index.html", "owner-host.js", "binary_manifest.py", "build_owner_apk.py")
        ]
        tracked += [roots["frontend"] / n for n in ("app.js", "controller.js", "style.css", "background.png")]
        tracked += [Path(PACKET.__file__), Path(ASSEMBLY.__file__)]
        if len(code) > len(CODE_ENTRIES):
            tracked.append(SOURCE.parent / "accepted-output/sdk_package.py")
        tracked += [roots[k] for k in ("java", "android_jar", "d8_jar", "wire_helper", "manifest")]
        tracked += [Path(row["path"]) for row in code.values()]
        drift_evidence = [pin for row in readiness["entries"] for pin in row.get("drift_evidence", [])]
        tracked += [Path(pin["path"]) for pin in drift_evidence]
        if "javac" in roots:
            tracked.append(roots["javac"])
        result["inputs"] = {str(p): {"bytes": p.stat().st_size, "sha256": sha(p)} for p in tracked}
        if any(result["inputs"][pin["path"]]["sha256"] != pin["sha256"] for pin in drift_evidence):
            raise ValueError("drift evidence changed after readiness check")
        # Availability and qualification are checked above. Bind assembly to the
        # actual current bytes, including the payload index used by Android.
        content = {row["path"]: {"path": row["path"], "bytes": row["bytes"], "sha256": row["sha256"]} for row in readiness["entries"]}

        def run(command, label):
            with (output / (label + ".log")).open("x") as log:
                subprocess.run([str(x) for x in command], stdout=log, stderr=subprocess.STDOUT, check=True, timeout=180)

        classes, dex = output / "classes", output / "dex"
        classes.mkdir()
        dex.mkdir()
        run(
            [
                roots.get("javac", roots["java"].with_name("javac")),
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
        apk_rows = {name[4:]: row for name, row in content.items() if name.startswith("apk/")}
        manifest_row = apk_rows["AndroidManifest.xml"]
        manifest_source = Path(code["AndroidManifest.xml"]["path"]) if "AndroidManifest.xml" in code else PACKET.verify(roots["targets"], manifest_row)
        manifest_bytes = manifest_source.read_bytes()
        if "AndroidManifest.xml" in code and hashlib.sha256(manifest_bytes).hexdigest() != code["AndroidManifest.xml"]["sha256"]:
            raise ValueError("owner APK source bytes differ")
        patched = MANIFEST.patch(manifest_bytes, wire, version_code=version_code)
        (output / "AndroidManifest.xml").write_bytes(patched)
        payload = [row for name, row in content.items() if name.startswith("payload/")]
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
                elif name in code:
                    produced = code[name]
                    entry(name, source=Path(produced["path"]), expected_sha=produced["sha256"], expected_bytes=produced["bytes"])
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
            original_entries_preserved=len(apk_rows) - len(set(code) | {"AndroidManifest.xml"}),
            original_entry_changed="AndroidManifest.xml",
            new_dex=next_dex,
            entries_verified=len(expected),
            runtime_payload_files=len(payload),
            runtime_payload_bytes=sum(r["bytes"] for r in payload),
            il2cpp_or_original_dex_changed=bool(code),
            code_entries=code,
            signed=False,
            device_qualified=False,
            requested_version_code=version_code,
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
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument("--request")
    selection.add_argument("--sign-request")
    selection.add_argument("--check-request", help="inventory final target-tree/code inputs without compiling, assembling or signing")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    if args.check_request:
        result = check(json.loads(Path(args.check_request).read_text()))
        with Path(args.output).open("x") as stream:
            json.dump(result, stream, indent=2)
            stream.write("\n")
        print(json.dumps({key: value for key, value in result.items() if key != "entries"}))
        return 0 if result["assembly_ready"] else 1
    print(json.dumps(sign(args.sign_request, args.output) if args.sign_request else build(args.request, args.output)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
