#!/usr/bin/env python3
"""Signed public transformations, never owner inputs or generated game files.

Verification is public-key-only and uses the fixed RFC 8017 encoding, so the
Android Python host needs no OpenSSL executable. Signing delegates to OpenSSL
with an explicitly provisioned external private key; this module creates none.
"""

import argparse
import base64
import hashlib
import hmac
import importlib.util
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import tempfile
import zipfile


def _module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


RELEASE = _module("owner_release_contract", Path(__file__).with_name("release.py"))
MAX_JSON_BYTES = 8 * 1024 * 1024
MAX_PUBLIC_FILE_BYTES = 64 * 1024 * 1024
MAX_BUNDLE_BYTES = 512 * 1024 * 1024
INDEX = "bundle-index.json"
SOURCE_SUFFIXES = {
    ".py",
    ".java",
    ".c",
    ".h",
    ".cs",
    ".cpp",
    ".js",
    ".json",
    ".jsonl",
    ".xml",
    ".html",
    ".css",
    ".md",
    ".txt",
    ".sh",
    ".yml",
    ".yaml",
    ".props",
    ".targets",
    ".asmdef",
    ".csproj",
    ".patch",
    ".rsp",
    ".bat",
    ".config",
    ".template",
    ".cmake",
    ".gradle",
}
LAUNCHER_ART_SHA256 = "6f73ee2c7a9d6544b5f2972832b12a7aed3f98cf9ba00fc04b218502f65ea4ff"
PUBLISHING_SOURCE_FILES = {
    "environment/toolchain.json",
    "recipe/owner-app-host-tools.json",
    "scripts/lab/phone_apk.py",
    *{
        "scripts/lab/" + name + ".py"
        for name in (
            "owner_assemblies",
            "assembly_transforms",
            "rebuild",
            "common",
            "composition_io",
            "catalog_rebuild",
            "scene_rebuild",
            "build_entry_rebuild",
            "project_input_rebuild",
            "importer_rebuild",
            "shader_rebuild",
        )
    },
    *{
        "tools/phone-build/owner-apk/" + name
        for name in (
            "build_owner_apk.py",
            "binary_manifest.py",
            "PayloadStore.java",
            "PayloadBootstrapActivity.java",
            "index.html",
            "owner-host.js",
            "release.py",
            "alpha_policy.py",
            "ProfileStore.java",
            "ProfileRetentionProvider.java",
            "public_release.py",
            "updates.py",
            "release_jobs.py",
            "install_inputs.py",
            "install_flow.py",
            "game_import.py",
        )
    },
    *{"tools/phone-build/accepted-output/" + name + ".py" for name in ("package", "assemble", "sdk_package", "sdk_inputs")},
    "tools/phone-build/owner-code/native.py",
    *{"launcher/" + name for name in ("app.js", "controller.js", "style.css", "background.png", "PROVENANCE.md")},
    *{
        "tools/phone-build/managed-host/" + name
        for name in (
            "AndroidManifest.xml",
            "ToolHostActivity.java",
            "OwnerInstaller.java",
            "OwnerAlphaInstall.java",
            "OwnerUpdateState.java",
            "OwnerBuildService.java",
            "OwnerInputImport.java",
            "OwnerInputSource.java",
            "NativePythonHost.c",
            "NativeDotnetMuxer.c",
            "NativeJavaHost.c",
            "stage.py",
            "build_fixture.py",
            "run_profile.py",
            "release-trust.json",
            "README.md",
        )
    },
}


def alpha_schema(value):
    """Only the currently implemented native profile protocol may be published."""
    RELEASE.ALPHA.data_schema(value)
    if value != {"writes": 1, "reads": [1]}:
        raise ValueError("alpha publication supports only data_schema writes 1 / reads [1]; native migration is not implemented")
    return {"writes": 1, "reads": [1]}


def publication_policy(application_id, minimum_installer_version, data_schema):
    RELEASE.ALPHA.identity(application_id)
    if type(minimum_installer_version) is not int or not 3 <= minimum_installer_version <= RELEASE.ALPHA.MAX_VERSION_CODE:
        raise ValueError("alpha publication requires installer version 3 or later")
    return alpha_schema(data_schema)


def validate_alpha_release(body):
    """Publication policy is stricter than the reusable legacy release contract."""
    RELEASE.validate(body, RELEASE.ALPHA.MAX_VERSION_CODE, body.get("application_id"), 0)
    publication_policy(body["application_id"], body["minimum_installer_version"], body.get("data_schema"))


def load_json(data):
    """Reject ambiguous duplicate keys, nonfinite numbers and oversized input."""
    if isinstance(data, bytes):
        if len(data) > MAX_JSON_BYTES:
            raise ValueError("JSON size limit exceeded")
        data = data.decode("utf-8")
    if not isinstance(data, str) or len(data.encode("utf-8")) > MAX_JSON_BYTES:
        raise ValueError("bounded JSON text required")

    def pairs(rows):
        result = {}
        for key, value in rows:
            if key in result:
                raise ValueError("duplicate JSON field")
            result[key] = value
        return result

    def constant(_):
        raise ValueError("finite JSON values required")

    return json.loads(data, object_pairs_hook=pairs, parse_constant=constant)


def public_path(name):
    if not isinstance(name, str) or not name or len(name) > 1024 or "\\" in name or ":" in name:
        raise ValueError("canonical relative public path required")
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts or str(path) != name or any(ord(c) < 32 or ord(c) == 127 for c in name):
        raise ValueError("canonical relative public path required")
    if path.parts[0] in {".git", ".local", "work", "logs", "screenshots"}:
        raise ValueError("private path cannot enter a public bundle")
    return name


def public_source_path(name, digest):
    """The download surface is authored source/configuration, never game blobs."""
    public_path(name)
    _sha256(digest)
    path = PurePosixPath(name)
    if name == "launcher/background.png" and digest == LAUNCHER_ART_SHA256:
        return name
    if path.suffix.lower() in SOURCE_SUFFIXES or path.name.lower() in {"license", "copying", "notice", "makefile"}:
        return name
    if name.startswith("recipe/") and name.endswith(".jsonl.gz"):
        return name
    if name.startswith("recipe/templates/") and path.suffix == ".meta":
        return name
    raise ValueError("only reviewed public source/configuration/license files may be bundled: " + name)


def _sha256(value):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
        raise ValueError("lowercase SHA-256 required")
    return value


def _der(data, tag):
    if len(data) < 2 or data[0] != tag:
        raise ValueError("invalid trusted RSA SPKI encoding")
    length, start = data[1], 2
    if length & 128:
        count = length & 127
        if not 1 <= count <= 2 or len(data) < 2 + count or data[2] == 0:
            raise ValueError("noncanonical DER length")
        length, start = int.from_bytes(data[2 : 2 + count], "big"), 2 + count
        if length < 128:
            raise ValueError("noncanonical DER length")
    if start + length > len(data):
        raise ValueError("truncated trusted RSA key")
    return data[start : start + length], data[start + length :]


def _integer(data):
    value, rest = _der(data, 2)
    if not value or value[0] & 128 or (len(value) > 1 and value[0] == 0 and not value[1] & 128):
        raise ValueError("canonical positive RSA integer required")
    return int.from_bytes(value, "big"), rest


def public_numbers(pem):
    """Read only RSA SubjectPublicKeyInfo; private keys/certificates are refused."""
    if isinstance(pem, str):
        pem = pem.encode("ascii")
    if not isinstance(pem, bytes) or len(pem) > 16384:
        raise ValueError("bounded trusted RSA public key required")
    match = re.fullmatch(rb"\s*-----BEGIN PUBLIC KEY-----\s+([A-Za-z0-9+/=\s]+)-----END PUBLIC KEY-----\s*", pem)
    if not match:
        raise ValueError("trusted X509 SubjectPublicKeyInfo PEM required")
    try:
        encoded = base64.b64decode(re.sub(rb"\s", b"", match[1]), validate=True)
    except ValueError as error:
        raise ValueError("invalid trusted public key base64") from error
    sequence, trailing = _der(encoded, 48)
    algorithm, rest = _der(sequence, 48)
    if trailing or algorithm != bytes.fromhex("06092a864886f70d0101010500"):
        raise ValueError("RSA encryption SPKI algorithm required")
    bits, trailing = _der(rest, 3)
    if trailing or not bits or bits[0] != 0:
        raise ValueError("canonical RSA key bit string required")
    key, trailing = _der(bits[1:], 48)
    modulus, rest = _integer(key)
    exponent, rest = _integer(rest)
    if trailing or rest or not 2048 <= modulus.bit_length() <= 8192 or modulus % 2 == 0 or not 3 <= exponent <= 0xFFFFFFFF or exponent % 2 == 0:
        raise ValueError("RSA 2048-8192 bit public key required")
    return modulus, exponent


def verify_signature(message, signature, public_key):
    """Strict RSASSA-PKCS1-v1_5/SHA-256 verification, never private operations."""
    modulus, exponent = public_numbers(public_key)
    size = (modulus.bit_length() + 7) // 8
    if not isinstance(signature, bytes) or len(signature) != size or int.from_bytes(signature, "big") >= modulus:
        raise ValueError("release signature invalid")
    digest_info = bytes.fromhex("3031300d060960864801650304020105000420") + hashlib.sha256(message).digest()
    expected = b"\x00\x01" + b"\xff" * (size - len(digest_info) - 3) + b"\x00" + digest_info
    actual = pow(int.from_bytes(signature, "big"), exponent, modulus).to_bytes(size, "big")
    if not hmac.compare_digest(expected, actual):
        raise ValueError("release signature invalid")


def verify_envelope(envelope, trusted_keys):
    """Verify using provisioned trust only; return the existing release body."""
    if isinstance(envelope, (str, bytes)):
        envelope = load_json(envelope)
    if not isinstance(envelope, dict) or set(envelope) != {"release", "signature"}:
        raise ValueError("explicit release envelope required")
    signature = envelope["signature"]
    if not isinstance(signature, dict) or set(signature) != {"algorithm", "key_id", "value"} or signature["algorithm"] != "SHA256withRSA":
        raise ValueError("SHA256withRSA release signature required")
    key_id = signature["key_id"]
    if not isinstance(key_id, str) or not re.fullmatch(r"[A-Za-z0-9_.-]{1,80}", key_id) or key_id not in trusted_keys:
        raise ValueError("release signing key is not trusted")
    if not isinstance(signature["value"], str) or len(signature["value"]) > 2048:
        raise ValueError("bounded release signature required")
    try:
        value = base64.b64decode(signature["value"], validate=True)
    except ValueError as error:
        raise ValueError("invalid release signature base64") from error
    body = envelope["release"]
    if not isinstance(body, dict):
        raise ValueError("release object required")
    RELEASE.validate(body, 2100000000, body.get("application_id"), 0)
    verify_signature(RELEASE.signed_bytes(body), value, trusted_keys[key_id])
    return body


def dependency_hash(files, job=None):
    if not isinstance(files, dict) or not files:
        raise ValueError("explicit dependency file closure required")
    for path, digest in files.items():
        public_path(path)
        _sha256(digest)
    value = {"files": files}
    if job is not None:
        if public_path(job) not in files:
            raise ValueError("job must belong to recipe dependency closure")
        value["job"] = job
    return hashlib.sha256(RELEASE.signed_bytes(value)).hexdigest()


def entry_dependencies(index, name):
    row = index["entries"][name]
    return {
        "recipe_sha256": dependency_hash({path: index["files"][path] for path in row["recipe_files"]}, row["job"]),
        "producer_sha256": dependency_hash({path: index["files"][path] for path in row["producer_files"]}),
    }


def validate_bundle_index(index, release):
    if (
        not isinstance(index, dict)
        or set(index) - {"install_plan"} != {"schema", "files", "entries"}
        or type(index["schema"]) is not int
        or index["schema"] != 1
    ):
        raise ValueError("public bundle index schema 1 required")
    if "install_plan" in index:
        installer = _module("public_install_inputs", Path(__file__).with_name("install_inputs.py"))
        installer.validate_plan(index["install_plan"], index["files"])
    if not isinstance(index["files"], dict) or not index["files"] or INDEX in index["files"]:
        raise ValueError("explicit public bundle files required")
    for path, digest in index["files"].items():
        public_source_path(path, digest)
        if any(str(parent) in index["files"] for parent in PurePosixPath(path).parents):
            raise ValueError("overlapping public bundle paths")
    if not isinstance(index["entries"], dict) or set(index["entries"]) != set(release["entries"]):
        raise ValueError("bundle outputs differ from signed release")
    for name, row in index["entries"].items():
        if not isinstance(row, dict) or set(row) != {"recipe_files", "producer_files", "job"}:
            raise ValueError("explicit output dependency closures and job required")
        for field in ("recipe_files", "producer_files"):
            paths = row[field]
            if not isinstance(paths, list) or not paths or any(not isinstance(path, str) for path in paths) or len(set(paths)) != len(paths):
                raise ValueError("nonempty distinct dependency file paths required")
            if any(path not in index["files"] for path in paths):
                raise ValueError("dependency file absent from public bundle")
        if entry_dependencies(index, name) != release["entries"][name]:
            raise ValueError("bundle dependency fingerprints differ from release")


def _tracked(root):
    result = {}
    for line in subprocess.check_output(["git", "ls-tree", "-rz", "HEAD"], cwd=root).split(b"\0"):
        if line:
            metadata, name = line.split(b"\t", 1)
            mode, kind, blob = metadata.decode("ascii").split()
            result[name.decode("utf-8")] = (mode, kind, blob)
    return result


def _blob(root, tracked, name):
    public_path(name)
    if name not in tracked or tracked[name][0] not in {"100644", "100755"} or tracked[name][1] != "blob":
        raise ValueError("committed regular public file required: " + name)
    size = int(subprocess.check_output(["git", "cat-file", "-s", tracked[name][2]], cwd=root))
    if size > MAX_PUBLIC_FILE_BYTES:
        raise ValueError("public source file size limit exceeded")
    return subprocess.check_output(["git", "cat-file", "blob", tracked[name][2]], cwd=root)


def build_bundle(repository, plan, output):
    """Build deterministic ZIP from HEAD blobs only, never untracked/work bytes.

    Plan: {schema: 1, files: [extra public files], entries: {output: closures},
    data_schema?: {writes: 1, reads: [1]}}. Publication requires data_schema;
    it has one authority in the signed release body, not a duplicate index field.
    Each closure has recipe_files, producer_files and a job JSON path. Explicit
    closures are reviewed release-author inputs, not guessed import discovery.
    """
    root, output = Path(repository).resolve(), Path(output)
    if (
        not isinstance(plan, dict)
        or set(plan) - {"install_plan", "data_schema"} != {"schema", "files", "entries"}
        or type(plan["schema"]) is not int
        or plan["schema"] != 1
    ):
        raise ValueError("release bundle plan schema 1 required")
    if not isinstance(plan["files"], list) or any(not isinstance(path, str) for path in plan["files"]) or not isinstance(plan["entries"], dict):
        raise ValueError("explicit public files and entries required")
    if "data_schema" in plan:
        alpha_schema(plan["data_schema"])
    selected = set(plan["files"])
    for row in plan["entries"].values():
        if not isinstance(row, dict) or set(row) != {"recipe_files", "producer_files", "job"}:
            raise ValueError("explicit output dependency closures and job required")
        for field in ("recipe_files", "producer_files"):
            if not isinstance(row[field], list) or any(not isinstance(path, str) for path in row[field]):
                raise ValueError("dependency file list required")
            selected.update(row[field])
    if "install_plan" in plan:
        selected.add(public_path(plan["install_plan"]["required_inputs"]))
        for stage in plan["install_plan"]["stages"]:
            selected.update(stage["jobs"])
    if INDEX in selected:
        raise ValueError("bundle index is generated, not supplied")
    tracked = _tracked(root)
    audit = _module("release_public_audit", Path(__file__).resolve().parents[3] / "scripts/audit-public.py")
    contents = {}
    for name in sorted(selected):
        data = _blob(root, tracked, name)
        public_source_path(name, hashlib.sha256(data).hexdigest())
        if audit.violations(name, data):
            raise ValueError("public source audit refused: " + name)
        contents[name] = data
        if sum(map(len, contents.values())) > MAX_BUNDLE_BYTES:
            raise ValueError("public source bundle size limit exceeded")
    index = {"schema": 1, "files": {name: hashlib.sha256(data).hexdigest() for name, data in contents.items()}, "entries": plan["entries"]}
    if "install_plan" in plan:
        index["install_plan"] = plan["install_plan"]
    dependencies = {name: entry_dependencies(index, name) for name in index["entries"]}
    body = {
        "version": "validation",
        "version_code": 1,
        "application_id": "dev.ror2lab.alpha",
        "minimum_installer_version": 1,
        "bundle_sha256": "0" * 64,
        "entries": dependencies,
    }
    RELEASE.validate(body, 1, body["application_id"], 0)
    validate_bundle_index(index, body)
    contents[INDEX] = RELEASE.signed_bytes(index) + b"\n"
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("xb") as stream, zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_STORED, allowZip64=False) as archive:
        for name, data in sorted(contents.items()):
            item = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0))
            item.create_system, item.external_attr = 3, 0o100644 << 16
            archive.writestr(item, data)
    return {"bundle_sha256": RELEASE.digest(output), "entries": dependencies, "index": index}


def validate_publication(bundle_path, body):
    """Refuse a signed publication lacking runnable jobs or its assembly owner.

    This checks the public orchestration contract, not game/input/device
    readiness. Reviewed dependency lists still own non-Python/toolchain closure.
    """
    validate_alpha_release(body)
    if RELEASE.digest(bundle_path) != body["bundle_sha256"]:
        raise ValueError("public bundle changed before publication")
    with zipfile.ZipFile(bundle_path) as archive:
        index = load_json(archive.read(INDEX))
        validate_bundle_index(index, body)
        missing = PUBLISHING_SOURCE_FILES - index["files"].keys()
        if missing:
            raise ValueError("public bundle lacks installer/assembly/toolchain source: " + ", ".join(sorted(missing)))
        if "install_plan" not in index:
            raise ValueError("alpha publication requires a complete signed phone install plan")
        here = Path(__file__).resolve().parent
        jobs = _module("publisher_source_jobs", here / "release_jobs.py")
        jobs.validate_jobs(index, body, lambda name: load_json(archive.read(public_path(name))))
        if "install_plan" in index:
            flow = _module("publication_install_flow", here / "install_flow.py")
            flow.validate_plan(index["install_plan"], index, lambda name: load_json(archive.read(public_path(name))))
            inputs = _module("publication_install_inputs", here / "install_inputs.py")
            inputs.input_description(index["install_plan"], load_json(archive.read(index["install_plan"]["required_inputs"])))
        owner = _module("publisher_apk_owner", here / "build_owner_apk.py")
        if "install_plan" in index:
            owner.validate_source_payload(body["entries"])
        sdk = _module("publisher_sdk_owner", here.parent / "accepted-output/sdk_package.py")
        if not {"apk/" + name for name in owner.CODE_ENTRIES | sdk.SDK_ENTRIES} <= body["entries"].keys():
            raise ValueError("public release requires all native, metadata, Burst and Android SDK outputs")


def sign_envelope(body, key_id, private_key, public_key, *, openssl="openssl"):
    """Sign with explicitly supplied existing publisher material, then verify."""
    validate_alpha_release(body)
    public_numbers(public_key)
    with tempfile.TemporaryDirectory(prefix="public-release-sign-") as temporary:
        source, signature = Path(temporary) / "release-body.json", Path(temporary) / "signature"
        source.write_bytes(RELEASE.signed_bytes(body))
        subprocess.run(
            [openssl, "dgst", "-sha256", "-sign", str(Path(private_key).resolve(strict=True)), "-out", str(signature), str(source)],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=60,
            check=True,
        )
        envelope = {
            "release": body,
            "signature": {"algorithm": "SHA256withRSA", "key_id": key_id, "value": base64.b64encode(signature.read_bytes()).decode("ascii")},
        }
    verify_envelope(envelope, {key_id: public_key})
    return envelope


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", type=Path, default=Path(__file__).resolve().parents[3])
    parser.add_argument("--plan", required=True, help="reviewed plan path relative to repository HEAD")
    parser.add_argument("--output", type=Path, required=True, help="new public release directory")
    parser.add_argument("--version", required=True)
    parser.add_argument("--version-code", type=int, required=True)
    parser.add_argument("--minimum-installer-version", type=int, default=3)
    parser.add_argument("--application-id", default="dev.ror2lab.alpha")
    parser.add_argument("--key-id", required=True)
    parser.add_argument("--signing-key", type=Path, required=True)
    parser.add_argument("--public-key", type=Path, required=True)
    args = parser.parse_args()
    plan = load_json(_blob(args.repository, _tracked(args.repository), args.plan))
    schema = publication_policy(args.application_id, args.minimum_installer_version, plan.get("data_schema"))
    args.output.mkdir(parents=True)
    bundle = build_bundle(args.repository, plan, args.output / "public-tools.zip")
    body = {
        "version": args.version,
        "data_schema": schema,
        "version_code": args.version_code,
        "application_id": args.application_id,
        "minimum_installer_version": args.minimum_installer_version,
        "bundle_sha256": bundle["bundle_sha256"],
        "entries": bundle["entries"],
    }
    validate_publication(args.output / "public-tools.zip", body)
    envelope = sign_envelope(body, args.key_id, args.signing_key, args.public_key.read_bytes())
    (args.output / "release.json").write_bytes(RELEASE.signed_bytes(envelope["release"]) + b"\n")
    (args.output / "release.sig").write_bytes(RELEASE.signed_bytes(envelope["signature"]) + b"\n")
    print(json.dumps({"version": args.version, "version_code": args.version_code, "bundle_sha256": bundle["bundle_sha256"], "entries": len(bundle["entries"])}))


if __name__ == "__main__":
    main()
