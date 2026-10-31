"""Local-only, manifest-pinned owner input import; no network or game knowledge.

The caller obtains the manifest from its verified public recipe. FolderSource and
ZipSource consume user-selected/staged inputs; StreamSource adapts a SAF inventory
and binary opener without requiring source filesystem paths. Import roots must be
app-private and dedicated to this manifest. Only whole, hash-verified files are
checkpoints. Interrupted partial files are restarted, never trusted or appended.
"""

from contextlib import contextmanager
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import stat
import unicodedata
import zipfile
import importlib.util as _atomic_import

_atomic_spec = _atomic_import.spec_from_file_location("owner_atomic_io", Path(__file__).with_name("atomic_io.py"))
ATOMIC = _atomic_import.module_from_spec(_atomic_spec)
_atomic_spec.loader.exec_module(ATOMIC)


CHUNK = 64 * 1024
MAX_FILES = 100_000
MAX_MANIFEST_BYTES = 32 * 1024 * 1024
DEFAULT_RESERVE = 2 * 1024**3
SHA256 = re.compile(r"[0-9a-f]{64}\Z")


def relative(value):
    """Reject path aliases, traversal, Windows paths and ambiguous Unicode."""
    if (
        not isinstance(value, str)
        or not value
        or len(value.encode("utf-8")) > 4096
        or value != unicodedata.normalize("NFC", value)
        or any(ord(c) < 32 or ord(c) == 127 for c in value)
        or "\\" in value
        or ":" in value
        or any(p in {"", ".", ".."} for p in value.split("/"))
    ):
        raise ValueError("unsafe relative input path")
    return value


def integer(value, label):
    if type(value) is not int or value < 0 or value > 2**63 - 1:
        raise ValueError(label + " must be a nonnegative 63-bit integer")
    return value


def paths(names):
    seen, nodes = set(), {}
    for name in names:
        key = relative(name).casefold()
        if key in seen:
            raise ValueError("duplicate or case-aliased input path")
        seen.add(key)
        parts = name.split("/")
        for index in range(1, len(parts) + 1):
            node = "/".join(parts[:index])
            if nodes.setdefault(node.casefold(), node) != node:
                raise ValueError("case-aliased input directory")
    for name in seen:
        parts = name.split("/")
        if any("/".join(parts[:i]) in seen for i in range(1, len(parts))):
            raise ValueError("input path is both file and directory")


def validate_manifest(manifest):
    if not isinstance(manifest, dict) or set(manifest) != {"schema", "game_version", "files"} or type(manifest["schema"]) is not int or manifest["schema"] != 1:
        raise ValueError("required-input manifest schema 1 required")
    version = manifest["game_version"]
    if not isinstance(version, str) or not version.strip() or len(version) > 128 or any(ord(c) < 32 for c in version):
        raise ValueError("explicit game version required")
    rows = manifest["files"]
    if not isinstance(rows, list) or not rows or len(rows) > MAX_FILES:
        raise ValueError("bounded nonempty required-input file list required")
    result = {}
    for row in rows:
        if not isinstance(row, dict) or set(row) != {"path", "bytes", "sha256"}:
            raise ValueError("input requires exactly path, bytes and sha256")
        name = relative(row["path"])
        integer(row["bytes"], "input size")
        if not isinstance(row["sha256"], str) or SHA256.fullmatch(row["sha256"]) is None:
            raise ValueError("lowercase SHA-256 required")
        if name in result:
            raise ValueError("duplicate input path")
        result[name] = dict(row)
    paths(result)
    integer(sum(row["bytes"] for row in rows), "total input size")
    return {"schema": 1, "game_version": version, "files": [result[name] for name in sorted(result)]}


def validate_catalog(value):
    """Reviewed complete fingerprints only; recognition never grants support."""
    if isinstance(value, dict) and value.get("schema") == 1:
        return {"schema": 2, "supported": [validate_manifest(value)], "recognized": []}
    if not isinstance(value, dict) or set(value) != {"schema", "supported", "recognized"} or type(value["schema"]) is not int or value["schema"] != 2:
        raise ValueError("input version catalog schema 2 required")
    if (
        not isinstance(value["supported"], list)
        or not 1 <= len(value["supported"]) <= 8
        or not isinstance(value["recognized"], list)
        or len(value["recognized"]) > 8
    ):
        raise ValueError("one to eight supported and at most eight recognition inventories required")
    result, versions, inventories = {"schema": 2}, set(), set()
    for kind in ("supported", "recognized"):
        result[kind] = []
        for supplied in value[kind]:
            manifest = validate_manifest(supplied)
            version = manifest["game_version"]
            inventory = hashlib.sha256(_encoded(manifest["files"])).hexdigest()
            if version in versions or inventory in inventories:
                raise ValueError("duplicate version or indistinguishable input fingerprints")
            versions.add(version)
            inventories.add(inventory)
            result[kind].append(manifest)
        result[kind].sort(key=lambda item: item["game_version"])
    return result


class VersionRefusal(ValueError):
    def __init__(self, report):
        self.report = report
        super().__init__(version_message(report))


def version_message(report):
    found = report.get("found_version") or "unknown (no complete reviewed fingerprint matched)"
    return (
        "Found version: "
        + found
        + ". Supported versions: "
        + ", ".join(report["supported_versions"])
        + ". "
        + (
            "The selected files match a supported reviewed inventory."
            if report["status"] == "supported"
            else "Input refused. Select a complete, unmodified supported PC installation or ask the release maintainer to review this version. Filenames and version labels are not proof; do not rename files to bypass this check."
        )
    )


def identify_version(source, catalog, *, control=None, progress=None):
    """One read per candidate path, no copies/writes and no label-based guesses."""
    catalog = validate_catalog(catalog)
    candidates = catalog["supported"] + catalog["recognized"]
    wanted = {}
    for manifest in candidates:
        for row in manifest["files"]:
            wanted.setdefault(row["path"], set()).add(row["bytes"])
    observed = {}

    def checkpoint():
        action = control() if control else None
        if action in {"pause", "cancel"}:
            raise _Stopped(action)
        if action not in {None, "continue"}:
            raise ValueError("invalid version-check control")

    for index, (name, sizes) in enumerate(sorted(wanted.items())):
        checkpoint()
        if name not in source.inventory:
            continue
        known_size = source.inventory[name]
        if known_size is not None and known_size not in sizes:
            observed[name] = {"bytes": known_size, "sha256": None}
            continue
        maximum, count, digest = max(sizes), 0, hashlib.sha256()
        with source.open(name) as stream:
            while True:
                checkpoint()
                chunk = stream.read(min(CHUNK, maximum - count + 1))
                if not chunk:
                    break
                count += len(chunk)
                if count > maximum:
                    break
                digest.update(chunk)
        observed[name] = {"bytes": count, "sha256": digest.hexdigest() if count <= maximum else None}
        if progress:
            progress({"status": "identifying", "current_path": name, "completed_files": index + 1, "total_files": len(wanted)})
    matched = [m for m in candidates if all(observed.get(r["path"]) == {"bytes": r["bytes"], "sha256": r["sha256"]} for r in m["files"])]
    result = {"status": "unknown", "found_version": None, "supported_versions": [m["game_version"] for m in catalog["supported"]], "manifest": None}
    if len(matched) > 1:
        result.update(status="ambiguous", found_version="ambiguous (multiple complete fingerprints matched)")
    elif matched:
        manifest = matched[0]
        if manifest in catalog["supported"]:
            result.update(status="supported", found_version=manifest["game_version"], manifest=manifest)
        else:
            result.update(status="unsupported", found_version=manifest["game_version"])
    result["message"] = version_message(result)
    return result


def select_version(source, catalog, **kwargs):
    result = identify_version(source, catalog, **kwargs)
    if result["status"] != "supported":
        raise VersionRefusal(result)
    return result["manifest"]


def _pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            raise ValueError("duplicate JSON field")
        result[key] = value
    return result


def load_manifest(data):
    if not isinstance(data, bytes) or len(data) > MAX_MANIFEST_BYTES:
        raise ValueError("bounded manifest bytes required")
    return validate_manifest(json.loads(data, object_pairs_hook=_pairs))


def _encoded(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def _root(path, *, create=False):
    path = Path(os.path.abspath(path))
    if any(part.is_symlink() for part in [path, *path.parents]):
        raise ValueError("symbolic-link import root refused")
    if create:
        ATOMIC.mkdirs(path)
    if not path.is_dir():
        raise ValueError("directory import root required")
    return path


def _within(root, name, *, parents=False):
    relative(name)
    current = root
    parts = name.split("/")
    for part in parts[:-1]:
        current /= part
        if current.is_symlink() or (current.exists() and not current.is_dir()):
            raise ValueError("non-directory or symbolic-link private parent refused")
        if parents and not current.exists():
            current.mkdir(exist_ok=True, mode=0o700)
            _sync_directory(current.parent)
    result = current / parts[-1]
    if result.is_symlink() or (result.exists() and not result.is_file()):
        raise ValueError("nonregular private input refused")
    return result


@contextmanager
def _open_beneath(root, name):
    """Open every component with NOFOLLOW, including a concurrently changed tree."""
    relative(name)
    flags = os.O_RDONLY | os.O_NOFOLLOW
    fd = os.open(root, flags | os.O_DIRECTORY)
    try:
        parts = name.split("/")
        for part in parts[:-1]:
            child = os.open(part, flags | os.O_DIRECTORY, dir_fd=fd)
            os.close(fd)
            fd = child
        child = os.open(parts[-1], flags | os.O_NONBLOCK, dir_fd=fd)
        try:
            if not stat.S_ISREG(os.fstat(child).st_mode):
                raise ValueError("regular input file required")
            stream = os.fdopen(child, "rb")
        except BaseException:
            os.close(child)
            raise
        with stream:
            yield stream
    finally:
        os.close(fd)


class StreamSource:
    """Inventory values are integer byte lengths, or None when SAF reports unknown.

    opener(relative_path) returns a fresh binary context manager. It must resolve
    only the selected, locally granted tree; this class never obtains URIs or
    permissions. Extras are inventoried/reported but never opened or copied.
    """

    def __init__(self, inventory, opener, *, game_version=None):
        if not isinstance(inventory, dict) or len(inventory) > MAX_FILES:
            raise ValueError("bounded source inventory required")
        paths(inventory)
        for size in inventory.values():
            if size is not None:
                integer(size, "source size")
        if game_version is not None and (not isinstance(game_version, str) or not game_version.strip() or len(game_version) > 128):
            raise ValueError("source version must be an explicit bounded string")
        self.inventory = dict(inventory)
        self.opener, self.game_version = opener, game_version

    def open(self, name):
        if name not in self.inventory:
            raise ValueError("file absent from selected source")
        return self.opener(name)


class FolderSource(StreamSource):
    def __init__(self, root, *, game_version=None):
        self.root = _root(root)
        inventory = {}
        for current, directories, files in os.walk(self.root, followlinks=False):
            for child in [*directories, *files]:
                entry = Path(current) / child
                mode = entry.lstat().st_mode
                if not stat.S_ISREG(mode) and not stat.S_ISDIR(mode):
                    raise ValueError("source symlink or special file refused")
                name = entry.relative_to(self.root).as_posix()
                relative(name)
                if stat.S_ISREG(mode):
                    inventory[name] = entry.stat().st_size
                    if len(inventory) > MAX_FILES:
                        raise ValueError("source inventory too large")
        super().__init__(inventory, lambda name: _open_beneath(self.root, name), game_version=game_version)


class ZipSource(StreamSource):
    """Seekable ZIP, including a local URI-backed descriptor; never extractall.

    Only stored/deflated regular entries are admitted. Sizes/hashes are checked
    against the recipe while streaming, not trusted from ZIP directory headers.
    Caller closes the source (or uses it as a context manager).
    """

    def __init__(self, archive, *, game_version=None):
        self.archive = zipfile.ZipFile(archive)
        try:
            entries = self.archive.infolist()
            if len(entries) > MAX_FILES:
                raise ValueError("archive inventory too large")
            inventory, seen, directories = {}, set(), set()
            for entry in entries:
                if entry.orig_filename != entry.filename:
                    raise ValueError("aliased archive filename")
                name = relative(entry.filename[:-1] if entry.is_dir() else entry.filename)
                if name.casefold() in seen:
                    raise ValueError("duplicate or case-aliased archive entry")
                seen.add(name.casefold())
                mode = entry.external_attr >> 16
                kind = stat.S_IFMT(mode)
                if (
                    kind not in {0, stat.S_IFDIR if entry.is_dir() else stat.S_IFREG}
                    or entry.flag_bits & 1
                    or entry.compress_type not in {zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED}
                ):
                    raise ValueError("unsupported archive entry type or compression")
                if entry.is_dir():
                    directories.add(name.casefold())
                else:
                    inventory[name] = entry.file_size
            paths(inventory)
            if any(name.casefold() in directories for name in inventory):
                raise ValueError("archive file/directory collision")
            file_names = {name.casefold() for name in inventory}
            for directory in directories:
                parts = directory.split("/")
                if any("/".join(parts[:i]) in file_names for i in range(1, len(parts))):
                    raise ValueError("archive directory is beneath a regular file")
            super().__init__(inventory, lambda name: self.archive.open(name, "r"), game_version=game_version)
        except BaseException:
            self.archive.close()
            raise

    def close(self):
        self.archive.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


class _Stopped(Exception):
    def __init__(self, action):
        self.action = action


def _sync_directory(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


class Importer:
    """Durable whole-file checkpoints in one dedicated app-private directory.

    Reconstruction budget is additional to remaining import bytes and reserve.
    progress receives JSON-compatible report snapshots. control returns None or
    'continue', 'pause', 'cancel', checked during hashing and every copied chunk.
    Cancellation deletes only this importer's partial file, retaining verified
    checkpoints for an explicit retry. The caller owns source grant persistence.
    """

    def __init__(self, manifest, private_root, *, reconstruction_bytes=0, reserve_bytes=DEFAULT_RESERVE, margin_ratio=0.05, free_bytes=None):
        self.manifest = validate_manifest(manifest)
        self.identity = hashlib.sha256(_encoded(self.manifest)).hexdigest()
        self.rows = {row["path"]: row for row in self.manifest["files"]}
        self.root = _root(private_root, create=True)
        self.files = _root(self.root / "files", create=True)
        self.staging = _root(self.root / "staging", create=True)
        self.reconstruction_bytes = integer(reconstruction_bytes, "reconstruction budget")
        self.reserve_bytes = integer(reserve_bytes, "free-space reserve")
        if type(margin_ratio) not in {int, float} or not math.isfinite(margin_ratio) or not 0 <= margin_ratio <= 1:
            raise ValueError("input margin ratio must be between zero and one")
        self.margin_ratio = margin_ratio
        self.free_bytes = free_bytes or (lambda: shutil.disk_usage(self.root).free)

    def _check(self):
        action = self.control() if self.control else None
        if action in {"pause", "cancel"}:
            raise _Stopped(action)
        if action not in {None, "continue"}:
            raise ValueError("control must return continue, pause or cancel")

    def _checkpoint(self):
        value = {"schema": 1, "manifest_sha256": self.identity, "status": self.report["status"], "completed": self.completed}
        ATOMIC.write_json(_within(self.root, "checkpoint.json"), value)

    def _emit(self, **changes):
        self.report.update(changes)
        self.report["completed_files"] = len(self.completed)
        self.report["completed_bytes"] = sum(row["bytes"] for row in self.completed.values())
        if self.progress:
            self.progress(json.loads(_encoded(self.report)))

    def _digest(self, stream, size, *, output=None, name=None):
        digest, count = hashlib.sha256(), 0
        while True:
            self._check()
            block = stream.read(min(CHUNK, size - count + 1))
            if not isinstance(block, bytes):
                raise ValueError("source must return binary bytes")
            if not block:
                break
            count += len(block)
            if count > size:
                return count, None
            digest.update(block)
            if output is not None:
                output.write(block)
            if name is not None:
                self._emit(current_path=name, current_bytes=count)
        return count, digest.hexdigest()

    def estimate(self, remaining_bytes):
        remaining_bytes = integer(remaining_bytes, "remaining import bytes")
        margin = self.reserve_bytes + math.ceil(remaining_bytes * self.margin_ratio)
        return {
            "remaining_input_bytes": remaining_bytes,
            "reconstruction_bytes": self.reconstruction_bytes,
            "margin_bytes": margin,
            "required_free_bytes": remaining_bytes + self.reconstruction_bytes + margin,
            "available_bytes": integer(self.free_bytes(), "available space"),
        }

    def verify(self, *, progress=None, control=None):
        """Rehash native-imported files in place, without copying or any URI.

        This is the Android bridge: native SAF/ZIP code atomically writes its
        hash-verified files directly to ``files/``; no duplicate spool is needed.
        Native code and Python must be serialized by their common job owner.
        """
        local = FolderSource(self.files)
        source = StreamSource(local.inventory, local.open)
        return self._execute(source, progress=progress, control=control, verify_only=True)

    def run(self, source, *, progress=None, control=None):
        return self._execute(source, progress=progress, control=control, verify_only=False)

    def _execute(self, source, *, progress, control, verify_only):
        self.progress, self.control, self.completed = progress, control, {}
        self.report = {
            "status": "validating",
            "manifest_sha256": self.identity,
            "game_version": self.manifest["game_version"],
            "source_game_version": source.game_version,
            "files_root": str(self.files),
            "missing": sorted(set(self.rows) - set(source.inventory)),
            "extra": sorted(set(source.inventory) - set(self.rows)),
            "mismatched": [],
            "version_mismatch": False,
            "total_files": len(self.rows),
            "total_bytes": sum(row["bytes"] for row in self.rows.values()),
            "current_path": None,
            "current_bytes": 0,
        }
        if isinstance(source, FolderSource) and (source.root == self.root or source.root in self.root.parents or self.root in source.root.parents):
            raise ValueError("source and private import root must be disjoint")
        lock = _within(self.root, "import.lock")
        fd = os.open(lock, os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW, 0o600)
        try:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise ValueError("another import owns the private root") from None
            return self._run(source, verify_only=verify_only)
        finally:
            os.close(fd)

    def _run(self, source, *, verify_only=False):
        partial, owned = None, False
        try:
            receipt = _within(self.root, "checkpoint.json")
            if receipt.exists():
                with receipt.open("rb") as stream:
                    raw = stream.read(MAX_MANIFEST_BYTES + 1)
                if len(raw) > MAX_MANIFEST_BYTES:
                    raise ValueError("checkpoint too large")
                # Corrupt/torn receipts never grant completion. A valid receipt
                # belonging to another recipe requires a new dedicated root.
                try:
                    prior = json.loads(raw, object_pairs_hook=_pairs)
                except (ValueError, UnicodeError):
                    prior = None
                if isinstance(prior, dict) and prior.get("manifest_sha256") not in {None, self.identity}:
                    raise ValueError("private root belongs to a different input manifest")
            owned = True
            for name, row in self.rows.items():
                self._check()
                destination = _within(self.files, name)
                if destination.exists():
                    with _open_beneath(self.files, name) as stream:
                        actual_size, actual_sha = self._digest(stream, row["bytes"], name=name)
                    if actual_size == row["bytes"] and actual_sha == row["sha256"]:
                        self.completed[name] = {"bytes": row["bytes"], "sha256": row["sha256"]}
                    elif verify_only and actual_size == row["bytes"]:
                        self.report["mismatched"].append({"path": name, "reason": "sha256", "expected": row["sha256"], "actual": actual_sha})
                source_size = source.inventory.get(name)
                if name in source.inventory and source_size is not None and source_size != row["bytes"]:
                    self.report["mismatched"].append({"path": name, "reason": "size", "expected": row["bytes"], "actual": source_size})
            self.report["version_mismatch"] = bool(self.report["mismatched"]) or source.game_version not in {None, self.manifest["game_version"]}
            self._emit()
            if self.report["missing"] or self.report["version_mismatch"]:
                self.report["status"] = "blocked"
                return self._finish()
            remaining = sum(row["bytes"] for name, row in self.rows.items() if name not in self.completed)
            if not verify_only:
                for name in self.rows:
                    _within(self.staging, hashlib.sha256(name.encode()).hexdigest() + ".part").unlink(missing_ok=True)
            self.report["space"] = self.estimate(remaining)
            if self.report["space"]["available_bytes"] < self.report["space"]["required_free_bytes"]:
                self.report["status"] = "insufficient-space"
                return self._finish()
            if verify_only:
                self.report["status"] = "complete" if len(self.completed) == len(self.rows) else "blocked"
                return self._finish()
            self.report["status"] = "copying"
            for name, row in self.rows.items():
                self._check()
                if name in self.completed:
                    continue
                partial = _within(self.staging, hashlib.sha256(name.encode()).hexdigest() + ".part")
                # Only this manifest owns the deterministic stage. Remove its old
                # incomplete bytes before refreshing the capacity estimate.
                partial.unlink(missing_ok=True)
                space = self.estimate(remaining)
                self.report["space"] = space
                if space["available_bytes"] < space["required_free_bytes"]:
                    self.report["status"] = "insufficient-space"
                    return self._finish()
                fd = os.open(partial, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
                with os.fdopen(fd, "wb") as output, source.open(name) as stream:
                    actual_size, actual_sha = self._digest(stream, row["bytes"], output=output, name=name)
                    output.flush()
                    os.fsync(output.fileno())
                if actual_size != row["bytes"] or actual_sha != row["sha256"]:
                    self.report["mismatched"].append(
                        {
                            "path": name,
                            "reason": "size" if actual_size != row["bytes"] else "sha256",
                            "expected": row["bytes"] if actual_size != row["bytes"] else row["sha256"],
                            "actual": actual_size if actual_size != row["bytes"] else actual_sha,
                        }
                    )
                    self.report["version_mismatch"] = True
                    partial.unlink()
                    partial = None
                    continue
                destination = _within(self.files, name, parents=True)
                ATOMIC.publish(partial, destination)
                partial = None
                self.completed[name] = {"bytes": row["bytes"], "sha256": row["sha256"]}
                remaining -= row["bytes"]
                self._checkpoint()
                self._emit(current_path=name, current_bytes=row["bytes"])
            self.report["status"] = "blocked" if self.report["mismatched"] else "complete"
            return self._finish()
        except _Stopped as stopped:
            if partial is not None:
                partial.unlink(missing_ok=True)
            self.report["status"] = "paused" if stopped.action == "pause" else "cancelled"
            return self._finish()
        except BaseException:
            if partial is not None:
                ATOMIC.discard(partial)
            self.report["status"] = "failed"
            if owned:
                try:
                    self._checkpoint()
                except OSError:
                    pass  # Retain the last durable checkpoint and original error.
            raise

    def _finish(self):
        self._checkpoint()
        self._emit(current_path=None, current_bytes=0)
        return json.loads(_encoded(self.report))
