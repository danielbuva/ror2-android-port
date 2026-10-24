"""Current lab-only APK iteration: fresh Unity export, raw member splice, owner signing.

Never used for release acceptance. A normal build establishes the packaging
anchor; content/package drift requires another normal build, not a guessed patch.
"""

import copy
import hashlib
import os
from pathlib import Path, PurePosixPath
import shutil
import struct
import zipfile

from common import read, run, sha, write
from build_timing import PhaseTiming

NATIVE = "lib/arm64-v8a/libil2cpp.so"
METADATA = "assets/bin/Data/Managed/Metadata/global-metadata.dat"
GRADLE = "Library/Bee/Android/Prj/IL2CPP/Gradle"


def signature(name):
    upper = name.upper()
    return upper.startswith("META-INF/") and (upper == "META-INF/MANIFEST.MF" or upper.endswith((".SF", ".RSA", ".DSA", ".EC")))


def member_hash(archive, name):
    h = hashlib.sha256()
    with archive.open(name) as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def safe_name(name):
    path = PurePosixPath(name)
    return bool(name) and not path.is_absolute() and ".." not in path.parts and "\\" not in name and str(path) == name


def packaging_inputs(gradle):
    """Java, manifests, Android resources and JARs must retain the anchor bytes.

    ProjectSettings/Packages/plugins/build templates are also covered by the
    frozen-payload input gate. Exported IL2CPP build.gradle tasks differ from
    internal tasks, so they are not a Java/resource equivalence oracle.
    """
    gradle = Path(gradle)
    result = {}
    for module in ("launcher", "unityLibrary"):
        for folder in ("src/main", "libs"):
            root = gradle / module / folder
            for path in sorted(root.rglob("*")):
                relative = path.relative_to(gradle).as_posix()
                if any(part in {"assets", "jniLibs", "jniStaticLibs", "Il2CppOutputProject"} for part in path.relative_to(root).parts):
                    continue
                if path.is_symlink():
                    raise RuntimeError("Export packaging inputs refuse symlinks")
                if path.is_file():
                    result[relative] = sha(path)
    if not {"launcher/src/main/AndroidManifest.xml", "unityLibrary/src/main/AndroidManifest.xml"} <= result.keys():
        raise RuntimeError("Complete Android packaging manifests required")
    return result


def export_members(gradle):
    result = {}
    for module in ("launcher", "unityLibrary"):
        for folder, prefix in (("assets", "assets/"), ("jniLibs", "lib/")):
            root = Path(gradle) / module / "src/main" / folder
            for path in sorted(root.rglob("*")):
                if path.is_symlink():
                    raise RuntimeError("Exported player data refuses symlinks")
                if path.is_file():
                    name = prefix + path.relative_to(root).as_posix()
                    if name in result or not safe_name(name):
                        raise RuntimeError("Ambiguous or unsafe exported APK member")
                    result[name] = path
    if not {NATIVE, METADATA, "assets/bin/Data/globalgamemanagers", "assets/bin/Data/boot.config"} <= result.keys():
        raise RuntimeError("Fresh export is missing complete IL2CPP/player data")
    native = result[NATIVE].open("rb")
    with native:
        header = native.read(20)
    if header[:7] != b"\x7fELF\x02\x01\x01" or len(header) != 20 or struct.unpack_from("<HH", header, 16) != (3, 183):
        raise RuntimeError("Fresh library must be an ARM64 ELF shared object")
    return result


def write_anchor(work, project, result):
    if not result.get("success") or result.get("iteration"):
        return
    gradle = Path(project) / GRADLE
    if not gradle.is_dir():
        return
    # Save the precise assets/lib coverage, including plugin libraries that are
    # packaged elsewhere and must remain untouched by the export overlay.
    members = export_members(gradle)
    with zipfile.ZipFile(result["apk"]) as archive:
        if not set(members) <= set(archive.namelist()):
            raise RuntimeError("Normal APK does not contain its generated export members")
        hashes = {name: member_hash(archive, name) for name in members}
    write(
        Path(work) / "config/iteration-base.json",
        {
            "schema": 1,
            "apk": result["apk"],
            "apk_sha256": result["apk_sha256"],
            "request_id": result["request_id"],
            "input_id": result["input_id"],
            "graphics_api": result["graphics_api"],
            "packaging_inputs": packaging_inputs(gradle),
            "overlay_members": sorted(members),
            "overlay_hashes": hashes,
            "source": result.get("source"),
        },
    )


def validate_anchor(work, input_id, api):
    anchor = read(Path(work) / "config/iteration-base.json")
    if anchor.get("schema") != 1 or anchor.get("input_id") != input_id or anchor.get("graphics_api") != api:
        raise RuntimeError("Iteration anchor identity changed; run a normal whole-catalog build")
    if set(anchor.get("overlay_hashes", {})) != set(anchor["overlay_members"]):
        raise RuntimeError("Iteration anchor lacks complete member hashes; run a normal build")
    apk = Path(anchor["apk"])
    if not apk.resolve().is_relative_to(Path(work).resolve()) or sha(apk) != anchor["apk_sha256"]:
        raise RuntimeError("Iteration anchor APK missing or changed")
    return anchor


def splice(base, output, replacements, removed=()):
    """Copy unchanged compressed records verbatim, avoiding 700 MB recompression.

    ZIP offsets are rebuilt; obsolete v1 entries and the v2/v3 signing block are
    discarded. zipalign/apksigner must run after this unsigned transformation.
    """
    base, output = Path(base), Path(output)
    if output.exists() or output.resolve() == base.resolve():
        raise RuntimeError("Splice output must be new")
    if any(not safe_name(name) or signature(name) for name in replacements):
        raise RuntimeError("Unsafe replacement member")
    with zipfile.ZipFile(base) as source, base.open("rb") as raw, output.open("xb") as stream, zipfile.ZipFile(stream, "w", allowZip64=True) as target:
        infos = source.infolist()
        names = [info.filename for info in infos]
        if len(names) != len(set(names)) or any(not safe_name(name.rstrip("/")) for name in names):
            raise RuntimeError("Ambiguous or unsafe base APK")
        for info in infos:
            name = info.filename
            if signature(name) or name in removed or name in replacements:
                continue
            raw.seek(info.header_offset)
            header = raw.read(30)
            if len(header) != 30 or header[:4] != b"PK\x03\x04" or info.flag_bits & (1 | 8):
                # Android Gradle outputs currently have neither encryption nor
                # data descriptors. Refuse unknown record layouts.
                raise RuntimeError("Unsupported base ZIP record")
            name_len, extra_len = struct.unpack_from("<HH", header, 26)
            remaining = name_len + extra_len + info.compress_size
            cloned = copy.copy(info)
            cloned.header_offset = stream.tell()
            stream.write(header)
            while remaining:
                block = raw.read(min(4 * 1024 * 1024, remaining))
                if not block:
                    raise RuntimeError("Truncated base APK member")
                stream.write(block)
                remaining -= len(block)
            target.filelist.append(cloned)
            target.NameToInfo[name] = cloned
            target.start_dir = stream.tell()
        for name, path in sorted(replacements.items()):
            previous = source.NameToInfo.get(name)
            info = zipfile.ZipInfo(name)
            info.compress_type = previous.compress_type if previous else zipfile.ZIP_STORED
            info.external_attr = previous.external_attr if previous else 0o100644 << 16
            with Path(path).open("rb") as incoming, target.open(info, "w", force_zip64=True) as outgoing:
                shutil.copyfileobj(incoming, outgoing, 4 * 1024 * 1024)
        target._didModify = True  # raw preserved records also need a new central directory


def android_tools():
    root = Path(os.environ["ANDROID_HOME"]) / "build-tools/34.0.0"
    if not all((root / name).is_file() for name in ("zipalign", "apksigner")):
        raise RuntimeError("Pinned Android build-tools 34.0.0 required")
    return root


def signer_digest(apk):
    import re

    output = run([android_tools() / "apksigner", "verify", "--print-certs", apk]).stdout.decode()
    digests = re.findall(r"Signer #\d+ certificate SHA-256 digest: ([0-9a-f]+)", output)
    if len(digests) != 1:
        raise RuntimeError("Exactly one APK signer required")
    return digests[0]


def assemble_export(work, export, output, anchor):
    from unity_rebuild import debug_signing_key

    timing = PhaseTiming()
    with timing.phase("export_validation"):
        if packaging_inputs(export) != anchor["packaging_inputs"]:
            raise RuntimeError("Java/manifest/resource packaging changed; normal build required")
        members = export_members(export)
        changed = {name: path for name, path in members.items() if sha(path) != anchor["overlay_hashes"].get(name)}
        previous = set(anchor["overlay_members"])
        # Changing the generated player file set is valid: remove obsolete data
        # rather than leaving stale metadata/resources behind.
        removed = previous - set(members)
    unsigned, aligned = output.with_suffix(".unsigned.apk"), output.with_suffix(".aligned.apk")
    try:
        with timing.phase("splice"):
            splice(anchor["apk"], unsigned, changed, removed)
        with timing.phase("zipalign"):
            run([android_tools() / "zipalign", "-f", "-p", "4", unsigned, aligned], timeout=180)
        with timing.phase("sign"):
            run(
                [
                    android_tools() / "apksigner",
                    "sign",
                    "--ks",
                    debug_signing_key(Path(work).resolve()),
                    "--ks-key-alias",
                    "androiddebugkey",
                    "--ks-pass",
                    "pass:android",
                    "--key-pass",
                    "pass:android",
                    "--v4-signing-enabled",
                    "true",
                    "--out",
                    output,
                    aligned,
                ],
                timeout=180,
            )
        with timing.phase("verify_signature"):
            if signer_digest(output) != signer_digest(anchor["apk"]):
                raise RuntimeError("Iteration APK signing identity differs from anchor")
            run([android_tools() / "zipalign", "-c", "-p", "4", output], timeout=180)
    finally:
        unsigned.unlink(missing_ok=True)
        aligned.unlink(missing_ok=True)
    return {
        "base_apk_sha256": anchor["apk_sha256"],
        "overlay_members": sorted(members),
        "changed_members": sorted(changed),
        "changed_bytes": sum(path.stat().st_size for path in changed.values()),
        "removed_members": sorted(removed),
        "timing": timing.report(),
        "acceptance": "iteration only; normal full build required for acceptance",
    }


def compare_members(first, second):
    def inventory(path):
        result = {}
        with zipfile.ZipFile(path) as archive:
            for info in archive.infolist():
                if signature(info.filename):
                    continue
                if info.filename in result:
                    raise RuntimeError("Duplicate APK member")
                result[info.filename] = {"sha256": member_hash(archive, info), "bytes": info.file_size}
        return result

    a, b = inventory(first), inventory(second)
    changed = sorted(name for name in a.keys() & b.keys() if a[name] != b[name])
    return {
        "equal": a == b,
        "first_members": len(a),
        "second_members": len(b),
        "changed": changed,
        "only_first": sorted(a.keys() - b.keys()),
        "only_second": sorted(b.keys() - a.keys()),
        "members": {name: {"first": a.get(name), "second": b.get(name)} for name in changed},
    }


def compare_builds(first, second):
    for receipt in (first, second):
        if not receipt.get("success") or sha(receipt["apk"]) != receipt["apk_sha256"]:
            raise RuntimeError("Comparison needs successful builds and unchanged APKs")
    for field in ("source", "input_id", "graphics_api"):
        if not first.get(field) or first[field] != second.get(field):
            raise RuntimeError("Comparison builds differ in " + field)
    return compare_members(first["apk"], second["apk"])
