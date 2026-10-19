"""R9 destination-only full Unity build and exhaustive, non-normalized comparisons."""

from contextlib import contextmanager
import hashlib
import os
from pathlib import Path
import re
import shlex
import shutil
import zipfile

from common import RECIPE, ROOT, now, read, run, sha, write


def refuse_open_editors(destination, work):
    """Unity owns its project lock; never delete it. A lock left behind after the editor
    exited is stale only when no process holds it open."""
    projects = {destination.resolve(), (work / "lab-project").resolve(), (ROOT / "work/lab-project").resolve()}
    for lock in (project / "Temp/UnityLockfile" for project in projects):
        if lock.exists() and run(["/usr/sbin/lsof", "-t", str(lock)], check=False).stdout.strip():
            raise RuntimeError("Close the destination and working-project Unity editors (UnityLockfile held)")
    for command in run(["/bin/ps", "-axo", "command"]).stdout.decode().splitlines():
        # ps does not preserve quoting around paths with spaces. Match both spellings.
        if re.search(r"(?:^|/)Unity(?:\s|$)", command) and any(
            "-projectPath " + spelling in command for project in projects for spelling in (str(project), shlex.quote(str(project)), '"' + str(project) + '"')
        ):
            raise RuntimeError("Close the destination and working-project Unity editors before R9")


@contextmanager
def build_lock(destination):
    lock = destination / ".rebuild/unity-build.lock"
    lock.parent.mkdir(parents=True, exist_ok=True)
    try:
        descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as error:
        raise RuntimeError("R9 build already active or interrupted; inspect unity-build.lock before retrying") from error
    try:
        os.write(descriptor, str(os.getpid()).encode())
        os.close(descriptor)
        yield
    finally:
        lock.unlink()


def reference_apk(work):
    """BASELINE names device-verified bytes; current-build alone is not such evidence."""
    text = (ROOT / "docs/BASELINE.md").read_text()
    match = re.search(r"\| APK \| `([0-9a-f]{64})`", text)
    if not match:
        raise RuntimeError("BASELINE must name the full device-verified APK hash")
    expected = match[1]
    receipts = [work / "device/installed.json", work / "config/current-build.json"] + sorted((work / "build-cache").glob("*/result.json"))
    for receipt in receipts:
        if receipt.is_file():
            try:
                row = read(receipt)
            except (OSError, ValueError):
                continue
            if not isinstance(row, dict):
                continue
            if row.get("apk_sha256") == expected:
                apk = Path(row["apk"])
                if not apk.is_absolute():
                    apk = work.parent / apk
                if apk.is_file() and sha(apk) == expected:
                    return apk
    raise RuntimeError("Device-verified BASELINE APK missing or changed; restore its local receipt/artifact")


def debug_signing_key(work):
    # Match the real editor's isolated Android home. Never mint a new signing
    # identity: an in-place install must retain the existing app/profile.
    key = work.parent / ".local/android-user/.android/debug.keystore"
    if not key.is_file() or key.is_symlink():
        raise RuntimeError("Existing lab debug signing key required under the input clone's .local/android-user/.android")
    return key


def preflight_destination(destination=None, work=None):
    """Read-only R9 host gate; deliberately excludes device/live preflight receipts."""
    from common import WORK
    from build_entry_rebuild import validate_bindings
    from composition_io import StageIO
    from rebuild import safe_destination

    work = Path(work or WORK).resolve()
    input_id = read(work / "config/accepted-input.json")["input_id"]
    if not re.fullmatch("[0-9a-f]{64}", input_id):
        raise RuntimeError("Invalid accepted input ID")
    destination = safe_destination(destination, input_id, work)
    refuse_open_editors(destination, work)
    if (destination / ".rebuild/unity-build.lock").exists():
        raise RuntimeError("R9 build already active or interrupted")
    StageIO(work, destination).preflight()
    provenance = read(work / "receipts/provenance-map.json")
    from rebuild import relative_path

    for path in provenance:
        relative_path(path)
    bindings = validate_bindings(destination, work, input_id, provenance=provenance)
    if not bindings["equal"]:
        raise RuntimeError("R9 requires passing validate-bindings")
    destination_manifest(destination, input_id)
    reference = reference_apk(work)
    debug_signing_key(work)
    return dict(success=True, destination=str(destination), reference_apk=str(reference), bindings=bindings)


def destination_manifest(destination, input_id):
    """Match the payload source and APK descriptor before any Unity invocation."""
    from rebuild import relative_path

    pointer = read(destination / ".rebuild/catalog-inputs/integration-latest.json")["path"]
    if not pointer.startswith("destination/"):
        raise RuntimeError("R9 requires regenerated R3 manifest")
    relative = pointer.removeprefix("destination/")
    relative_path(relative)
    source = destination / relative / "manifest.json"
    if not source.resolve().is_relative_to(destination / ".rebuild/catalog-inputs"):
        raise RuntimeError("R3 manifest outside destination catalog inputs")
    manifest = read(source)
    bootstrap = read(destination / "Assets/LabLoadingScene/Resources/WholeCatalogBootstrap.json")
    if manifest.get("input_id") != input_id or bootstrap.get("input_id") != input_id:
        raise RuntimeError("R3 manifest/bootstrap input mismatch")
    attempt = manifest.get("attempt")
    if not isinstance(attempt, str) or not attempt or attempt != bootstrap.get("attempt"):
        raise RuntimeError("R3 manifest/bootstrap attempt mismatch; rerun R3 and R7 before R9")
    return manifest


def reimport_errors(scratch):
    """Classify errors logged while pass 2 reimported dependents against pass 1's fresh import.

    Any error absent from the fresh import makes R9 unequal; it is reported, never hidden."""
    errors = read(scratch / "lab-build/script-imports.json").get("errors")
    if not isinstance(errors, list) or any(not isinstance(error, str) for error in errors):
        raise RuntimeError("Destination reimport error record missing")
    fresh = (scratch / "editor-repair.log").read_text(errors="replace")
    new = sorted({error for error in errors if not error or error not in fresh})
    return dict(count=len(errors), distinct=len(set(errors)), new=new, all_in_fresh_import=not new)


def execute_build(destination, work, api):
    """Unity half of build.build; no live preflight, payload/cache or pointer writes."""
    from build import stage_android_assets, validate_staged_runtime_sources
    from composition_io import StageIO
    from rebuild import safe_destination

    input_id = read(work / "config/accepted-input.json")["input_id"]
    destination = safe_destination(destination, input_id, work)
    refuse_open_editors(destination, work)
    with build_lock(destination):
        io = StageIO(work, destination)
        # The coordinator also runs this before lock acquisition. Direct callers
        # still require the same binding/input gate, without the active-lock check.
        io.preflight()
        from build_entry_rebuild import validate_bindings

        bindings = validate_bindings(destination, work, input_id, provenance=read(work / "receipts/provenance-map.json"))
        if not bindings["equal"]:
            raise RuntimeError("R9 requires passing validate-bindings")
        manifest = destination_manifest(destination, input_id)
        # R8 staged editor code can predate this checkout; refresh authored Android tools.
        stage_android_assets(destination, io=io)
        io.flush()
        scratch = destination / ".rebuild/unity" / now()
        scratch.mkdir(parents=True)
        # WholeCatalogBuild enforces this owned subtree for its manifest.
        target = scratch / "experiments/whole-catalog/manifest.json"
        write(target, manifest)
        write(scratch / "whole-catalog-build.json", dict(manifest=str(target)))
        shutil.copyfile(destination / ".rebuild/composition/scene-probe-build.json", scratch / "scene-probe-build.json")
        from script_audit import build_selection

        write(scratch / "build-selection.json", dict(assets=build_selection(manifest, read(scratch / "scene-probe-build.json"))))
        from build import validate_runtime_support

        validate_staged_runtime_sources(destination, work=scratch)
        validate_runtime_support(destination, read(scratch / "scene-probe-build.json"))
        # R9 supplies the public smoke baseline, never a private PlayerSettings body.
        settings = destination / "ProjectSettings/ProjectSettings.asset"
        if not settings.exists():
            shutil.copyfile(ROOT / "smoke/ProjectSettings/ProjectSettings.asset", settings)
        request_id = now()
        write(scratch / "build-request.json", dict(request_id=request_id, api=api, reusePayload=False))
        (scratch / "graphics-api.txt").write_text(api)
        env = os.environ.copy()
        env.update(
            ANDROID_SDK_HOME=str(scratch / "android-user"),
            ANDROID_USER_HOME=str(scratch / "android-user/.android"),
            GRADLE_USER_HOME=str(scratch / "gradle"),
        )
        signing_copy = Path(env["ANDROID_USER_HOME"]) / "debug.keystore"
        signing_copy.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(debug_signing_key(work), signing_copy)
        signing_copy.chmod(0o600)

        def editor(method, log):
            return [
                os.environ["UNITY_EDITOR"],
                "-batchmode",
                "-quit",
                "-projectPath",
                str(destination),
                "-buildTarget",
                "Android",
                "-executeMethod",
                method,
                "-labWorkRoot",
                str(scratch),
                "-logFile",
                str(scratch / log),
            ]

        # Pass 1 reimports the managed DLLs and exits, so the recompilation it triggers
        # settles when pass 2 starts (J577 follow-up). Pass 2 gates and builds.
        repair = editor("LabBuild.RepairDestinationPlugins", "editor-repair.log")
        command = editor("LabBuild.BuildDestination", "editor.log")
        write(scratch / "invocation.json", dict(commands=[repair, command], input_id=input_id, request_id=request_id))
        refuse_open_editors(destination, work)
        process = run(repair, cwd=destination, env=env, timeout=14400, check=False)
        marker = scratch / "plugin-reimport.json"
        if process.returncode or not marker.is_file() or read(marker).get("request_id") != request_id or not read(marker).get("plugins"):
            raise RuntimeError("Destination plugin reimport pass failed; inspect " + str(scratch / "editor-repair.log"))
        refuse_open_editors(destination, work)
        process = run(command, cwd=destination, env=env, timeout=14400, check=False)
        result_path = scratch / "lab-build/result.json"
        if not result_path.is_file():
            raise RuntimeError("Unity produced no terminal receipt; inspect " + str(scratch / "editor.log"))
        result = read(result_path)
        if process.returncode or result.get("request_id") != request_id or not result.get("success") or result.get("errors", 0):
            raise RuntimeError("Destination Unity build failed; inspect " + str(result_path))
        audit = read(scratch / "lab-build/script-audit.json")
        if audit.get("schema") != 1 or not audit.get("uiValid"):
            raise RuntimeError("Destination script audit missing or failed")
        result["script_audit"] = audit
        result["reimport_errors"] = reimport_errors(scratch)
        apk = Path(result["apk"])
        if not apk.resolve().is_relative_to(scratch) or not apk.is_file():
            raise RuntimeError("Unity APK outside destination run or missing")
        payload = scratch / "generated-android-data"
        if not (payload / "whole-catalog.json").is_file():
            raise RuntimeError("Full destination content build did not produce whole-catalog.json")
        result.update(
            apk_sha256=sha(apk),
            input_id=input_id,
            graphics_api=api,
            payload_directory=str(payload),
            payload={path.name: sha(path) for path in sorted(payload.iterdir()) if path.is_file()},
        )
        write(scratch / "result.json", result)
        return result


GUID_LINE = re.compile(rb"(?m)^guid: [0-9a-f]{32}\r?\n")


def folder_status(target, current):
    """Unity mints folder importers at import; only their GUID line may differ (J575)."""
    if not current.is_file() or not current.with_suffix("").is_dir():
        return None
    folder = target.with_suffix("")
    if folder.is_dir() and target.is_file() and GUID_LINE.sub(b"", target.read_bytes()) == GUID_LINE.sub(b"", current.read_bytes()):
        return "folder_guid_minted"
    if not folder.exists() and not any(path.is_file() for path in current.with_suffix("").rglob("*")):
        return "empty_folder_absent"
    return None


# LabBuild.Build creates this scene with NewScene and saves it on every build (J592).
REBUILT_SCENES = {"Assets/Lab.unity"}
SCENE_HEADER = re.compile(rb"(?m)^--- !u!(\d+) &(-?\d+)\r?\n")
LOCAL_REFERENCE = re.compile(rb"\{fileID: (-?\d+)\}")


def scene_objects(data):
    """Map each local file ID to a structural name: GameObject name, or component class and owner."""
    parts = SCENE_HEADER.split(data)
    if b"stripped" in parts[0] or len(parts) < 4:
        return None
    documents = {parts[i + 1]: (parts[i], parts[i + 2]) for i in range(1, len(parts), 3)}
    if len(documents) != (len(parts) - 1) // 3:
        return None
    names = {}
    for local, (class_id, body) in documents.items():
        if class_id == b"1":
            match = re.search(rb"(?m)^  m_Name: (.*)$", body)
            if not match:
                return None
            names[local] = b"GameObject:" + match[1]
    for local, (class_id, body) in documents.items():
        if local in names:
            continue
        owner = re.search(rb"m_GameObject: \{fileID: (-?\d+)\}", body)
        if owner:
            if owner[1] not in names:
                return None
            names[local] = class_id + b":" + names[owner[1]]
        elif int(local) < 100:
            # Scene settings objects (1–4) keep their fixed IDs.
            names[local] = b"settings:" + local
        else:
            return None
    if len(set(names.values())) != len(names):
        return None

    def rename(body):
        return LOCAL_REFERENCE.sub(lambda m: b"{fileID: " + (names[m[1]] if m[1] != b"0" else b"0") + b"}", body)

    try:
        return parts[0], {names[local]: (class_id, rename(body)) for local, (class_id, body) in documents.items()}
    except KeyError:
        return None


def scene_ids_renumbered(target, current):
    """Equal only if one consistent renaming of local file IDs maps every object, field and reference."""
    if not target.is_file() or not current.is_file():
        return None
    a, b = scene_objects(target.read_bytes()), scene_objects(current.read_bytes())
    return "local_ids_renumbered" if a is not None and a == b else None


SERIALIZED_VERSION = re.compile(rb"^  serializedVersion: \d+\r?\n$")


def serialized_version_moved(target, current, export_source):
    """Unity's reserialization of an export-form native asset moves only its top-level serializedVersion line (J553, J592).

    The destination must still hold the recorded export bytes; the working file must be
    exactly those bytes with that one line at another position.
    """
    if export_source is None or not target.is_file() or not current.is_file() or not export_source.is_file():
        return None
    a, b = target.read_bytes(), current.read_bytes()
    if a != export_source.read_bytes() or len(a) != len(b):
        return None
    left, right = a.splitlines(keepends=True), b.splitlines(keepends=True)
    moved = [line for line in left if SERIALIZED_VERSION.match(line)]
    if len(left) != len(right) or len(moved) != 1:
        return None
    i, j = left.index(moved[0]), right.index(moved[0]) if moved[0] in right else -1
    if j < 0 or i == j or right.count(moved[0]) != 1:
        return None
    rest = left[:i] + left[i + 1 :]
    return "serialized_version_moved" if right[:j] + right[j + 1 :] == rest else None


def export_source(row, export):
    for evidence in row.get("evidence", []):
        path = evidence.get("export_path")
        if export is not None and path and "serializedVersion" in evidence.get("method", ""):
            source = (export / path).resolve()
            if source.is_relative_to(export.resolve()):
                return source
    return None


def compare_files(destination, project, paths, provenance, export=None):
    rows = []
    for path in sorted(paths):
        target, current = destination / path, project / path
        actual = sha(target) if target.is_file() else None
        expected = sha(current) if current.is_file() else None
        status = (
            "identical"
            if actual is not None and actual == expected
            else (path.endswith(".meta") and folder_status(target, current))
            or (path in REBUILT_SCENES and scene_ids_renumbered(target, current))
            or serialized_version_moved(target, current, export_source(provenance[path], export))
            or "different"
        )
        rows.append(
            dict(
                path=path,
                destination_sha256=actual,
                current_sha256=expected,
                provenance_sha256=provenance[path]["sha256"],
                status=status,
                provenance_matches=actual == provenance[path]["sha256"],
            )
        )
    statuses = ("identical", "folder_guid_minted", "empty_folder_absent", "local_ids_renumbered", "serialized_version_moved", "different")
    return dict(rows=rows, counts={status: sum(row["status"] == status for row in rows) for status in statuses})


def minted_folder_references(destination):
    """Re-measure J575 on the GUIDs Unity actually minted in the destination."""
    from importer_rebuild import folder_references

    folders = {}
    for meta in (destination / "Assets").rglob("*.meta"):
        if meta.with_suffix("").is_dir():
            match = GUID_LINE.search(meta.read_bytes())
            if match:
                folders[meta.relative_to(destination).as_posix()] = match[0].split()[1].decode()
    return folder_references(destination, folders)


def apk_entries(path):
    entries = {}
    with zipfile.ZipFile(path) as archive:
        for info in archive.infolist():
            if info.filename in entries:
                raise RuntimeError("Duplicate APK entry: " + info.filename)
            with archive.open(info) as stream:
                digest = hashlib.file_digest(stream, "sha256").hexdigest()
            entries[info.filename] = dict(
                size=info.file_size,
                sha256=digest,
                timestamp=list(info.date_time),
                compressed_size=info.compress_size,
                compression=info.compress_type,
                extra_sha256=hashlib.sha256(info.extra).hexdigest(),
            )
    return entries


def serialized_types(data):
    from UnityPy.files.SerializedFile import SerializedFile
    from UnityPy.streams import EndianBinaryReader

    file = SerializedFile(EndianBinaryReader(data))
    return [(row.class_id, row.script_type_index, row.script_id, row.old_type_hash) for row in file.types]


def level0_difference(actual, expected):
    """Confirm script/type hash-only changes only if all other bytes are equal.

    UnityPy's pinned SerializedType reader supplies hash fields. A field pair must
    occur exactly once in each input before its byte range can be attributed.
    Original entry hashes remain in the report regardless of this diagnosis.
    """
    try:
        a_types, b_types = serialized_types(actual), serialized_types(expected)
    except Exception as error:
        return dict(classification="unexplained-scene-difference", parser_error=type(error).__name__)
    if len(a_types) != len(b_types) or len(actual) != len(expected):
        return dict(classification="unexplained-scene-layout-difference")
    a_mask, b_mask = bytearray(actual), bytearray(expected)
    fields = []
    for index, (a, b) in enumerate(zip(a_types, b_types)):
        if a[:2] != b[:2]:
            return dict(classification="unexplained-scene-type-table-difference")
        if a[2:] == b[2:]:
            continue
        # Only script-bearing types qualify for the known script hash variation.
        a_pair, b_pair = (a[2] or b"") + (a[3] or b""), (b[2] or b"") + (b[3] or b"")
        if not a[2] or not b[2] or len(a_pair) != 32 or len(b_pair) != 32 or actual.count(a_pair) != 1 or expected.count(b_pair) != 1:
            continue
        a_offset, b_offset = actual.index(a_pair), expected.index(b_pair)
        if a_offset != b_offset:
            continue
        a_mask[a_offset : a_offset + 32] = b"\0" * 32
        b_mask[b_offset : b_offset + 32] = b"\0" * 32
        fields.append(dict(type_index=index, offset=a_offset, destination=a_pair.hex(), reference=b_pair.hex()))
    return dict(
        classification="unity-script-type-hashes-only" if fields and a_mask == b_mask else "unexplained-scene-difference",
        script_type_hash_fields=fields,
        other_bytes_equal=a_mask == b_mask,
    )


def compare_apks(destination, reference):
    actual, expected = apk_entries(destination), apk_entries(reference)
    rows = []
    for name in sorted(actual.keys() | expected.keys()):
        a, b = actual.get(name), expected.get(name)
        status = "added" if b is None else "missing" if a is None else "identical" if (a["size"], a["sha256"]) == (b["size"], b["sha256"]) else "different"
        classification = status
        if status == "different":
            if name.startswith("META-INF/"):
                classification = "signature-or-signing-metadata"
            elif name.endswith(("/globalgamemanagers", "/data.unity3d", "/boot.config")):
                classification = "unity-build-metadata-candidate"
            elif name.endswith(".so"):
                classification = "native-binary-difference"
            else:
                classification = "unexplained-content-difference"
        detail = None
        if status == "different" and name.endswith("/level0"):
            with zipfile.ZipFile(destination) as left, zipfile.ZipFile(reference) as right:
                detail = level0_difference(left.read(name), right.read(name))
            classification = detail["classification"]
        rows.append(
            dict(
                detail=detail,
                name=name,
                status=status,
                classification=classification,
                destination=a,
                reference=b,
                zip_metadata_different=a is not None
                and b is not None
                and any(a[key] != b[key] for key in ("timestamp", "compression", "compressed_size", "extra_sha256")),
            )
        )
    destination_hash, reference_hash = sha(destination), sha(reference)
    metadata_changes = sum(row["zip_metadata_different"] for row in rows)
    content_changes = sum(row["status"] != "identical" for row in rows)
    container_classification = (
        "byte-identical"
        if destination_hash == reference_hash
        else "entry-content-differences"
        if content_changes
        else "zip-metadata-or-container-signing-layout"
        if metadata_changes
        else "container-signing-or-layout-only"
    )
    return dict(
        destination_sha256=destination_hash,
        reference_sha256=reference_hash,
        container_classification=container_classification,
        zip_metadata_differences=metadata_changes,
        entries=rows,
        counts={status: sum(row["status"] == status for row in rows) for status in ("identical", "different", "added", "missing")},
        note="Candidate classifications do not excuse byte differences. Sizes, hashes and ZIP timestamps are retained; no normalization.",
    )


def accepted_export(work):
    projects = read(Path(work) / "config/reconstruction.json")["projects"]
    path = Path(projects[0])
    return Path(work).joinpath(*path.parts[1:]) if path.parts and path.parts[0] == "work" else ROOT / path


def unity_build(destination, work, input_id, provenance, compare_only=False):
    from build_entry_rebuild import validate_bindings
    from whole_catalog import build_integration
    from rebuild import STEPS, selected_paths

    bindings = validate_bindings(destination, work, input_id, provenance=provenance)
    if not bindings["equal"]:
        raise RuntimeError("R9 requires passing validate-bindings")
    reference = reference_apk(work)
    receipt = destination / ".rebuild/unity-build.json"
    if compare_only:
        build = read(receipt)["build"]
        if build["input_id"] != input_id or not Path(build["apk"]).resolve().is_relative_to(destination) or sha(build["apk"]) != build["apk_sha256"]:
            raise RuntimeError("Destination APK receipt drift")
    else:
        preflight_destination(destination, work)
        build = build_integration(destination=destination, work=work)
    groups = dict(
        r9_obligations=compare_files(destination, work / "lab-project", bindings["r9_obligations"], provenance),
        unity_import_deferred=compare_files(destination, work / "lab-project", bindings["unity_import_deferred"], provenance),
        # Host-placed importers must survive Unity's import unchanged (J603).
        importer_identities=compare_files(destination, work / "lab-project", selected_paths(STEPS["importer-identities"], provenance), provenance),
        unity_generated=compare_files(
            destination,
            work / "lab-project",
            {path for path, row in provenance.items() if row["producer"] == "unity-generated"} - selected_paths(STEPS["importer-identities"], provenance),
            provenance,
            export=accepted_export(work),
        ),
    )
    result = dict(
        build=build,
        reference_apk=str(reference),
        groups=groups,
        apk=compare_apks(Path(build["apk"]), reference),
        folder_guid_references=minted_folder_references(destination),
        scope="Project hashes gate R9; APK differences require operator review and both device checks.",
    )
    result["equal"] = (
        all(group["counts"]["different"] == 0 for group in groups.values())
        and not result["folder_guid_references"]["references"]
        and build.get("reimport_errors", {}).get("all_in_fresh_import", False)
    )
    if not compare_only:
        write(receipt, result)
    return result
