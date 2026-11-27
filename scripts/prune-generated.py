#!/usr/bin/env python3
"""Discard bulky, rebuildable build outputs under ignored work/.

Current. Every agent runs this when it finishes a build/run task (AGENTS.md
"Storage hygiene"). It removes only regenerable binaries: superseded
build-cache entries, staged symbol packages, APK/AAB/symbol/libil2cpp copies,
payload copies and Unity Library/Bee/il2cppOutput trees inside experiment, coordination and old
rebuild roots. Receipts, logs, captures, JSON evidence and recipes stay.
Finished session-memory heaps are disposable after successful analysis; removed
build-lane leftovers are disposable with their owner's removal receipt. Cold
storage symlinks are unlinked only, never deleted through.

Protected: every APK SHA-256 named in PORTING_STATE.md, docs/BASELINE.md,
docs/history-retention.md, the codex coordination lock, current-build, iteration-base and
device receipts (plus --keep-sha256), and anything modified more recently than
--min-age-hours (so it is safe to run while a build holds the editor), and
anything inside a directory containing a `.prune-keep` file (for costly
private oracles or packets you still need). A removed build-cache entry keeps its result.json under
work/cleanup-analysis/pruned-build-cache/<key>/; a removed experiment binary
leaves an adjacent <name>.retired.json marker. Rebuild from the recorded source
commit if an old candidate is ever needed again.

Defaults to a dry-run plan; --apply deletes and writes a ledger.
--dedupe scans only for verified APFS clones of duplicate files at least 64 MiB
and 30 minutes old. --aggressive includes dedupe after retiring stand-alone APKs
and compressing evidence. It uses a 48-hour minimum for APKs and evidence,
preserves immutable history, and measures volume free space on apply.
--supersede OLD --by NEW marks a physical generated run as replaced by the
latest direct result.json or *.done.json with success=true. After 24 hours,
unchanged receipt-bound markers let generated outputs ignore historical manifest
pins, never state/baseline/device/coordination-lock pins or .prune-keep. Evidence
and authored files remain; this does not delete arbitrary run directories.
Build-cache protection uses pinned state/baseline APKs, current build/base
entries, latest installed APKs, newest worker and lane builds, their frozen
payload references, explicit keeps and the age guard. Stale `.prune-keep` markers, nested content
hashes and historical device sync lists do not pin cache entries. The cache age
guard defaults to three hours; other generated outputs retain the 24-hour guard.
"""

import argparse
from collections import defaultdict
import ctypes
import errno
import fcntl
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import time
from pathlib import Path
import struct
import uuid

from lab.evidence_files import compressed_path

ROOT = Path(__file__).resolve().parent.parent
PROTECTION_CHECKOUT = None
HASH = re.compile(r"\b[0-9a-f]{64}\b")
PROTECTION_DOCS = ("PORTING_STATE.md", "docs/BASELINE.md", "docs/history-retention.md")
PROTECTION_RECEIPTS = ("coordination/codex-runtime.lock", "config/current-build.json", "config/iteration-base.json")
BINARY_SUFFIXES = (".apk", ".aab", ".obb")
BULKY_DIRS = {"payload", "il2cppOutput", "Bee"}
LARGE_BINARY = 32 * 1024 * 1024
SCAN_ROOTS = ("experiments", "coordination", "rebuild")
KEEP_MARKER = ".prune-keep"
SUPERSEDED_MARKER = ".superseded-by"
IMMUTABLE_DIRS = {"immutable-history", "retired-storage"}
EXTRA_APK_ROOTS = {"device", "lab-build"}
TRACE_NAMES = {"admission.jsonl", "exceptions.jsonl", "input-trace.jsonl", "phase-resources.jsonl"}
AGGRESSIVE_KINDS = {"old APK", "trace compression"}
DEDUPE_MIN_SIZE = 64 << 20
DEDUPE_MIN_AGE = 30 * 60


def evidence_trace(path):
    return (
        path.suffix == ".snap"
        or path.name in TRACE_NAMES
        or (
            path.suffix == ".jsonl"
            and (re.search(r"(?:^|[.-])thermal\.jsonl$", path.name) or path.name.startswith("owner-unplugged-") or path.name.endswith(".samples.jsonl"))
        )
    )


def apfs_allocation(path):
    """Return (private bytes, clone references) when APFS reports both."""
    if sys.platform != "darwin":
        return None
    # getattrlist(2): ATTR_CMN_RETURNED_ATTRS and ATTR_CMNEXT_PRIVATESIZE,
    # ATTR_CMNEXT_CLONE_REFCNT. FSOPT_ATTR_CMN_EXTENDED | FSOPT_NOFOLLOW.
    private_size, clone_refcount = 0x0008, 0x1000
    mask = private_size | clone_refcount
    request = struct.pack("=HH5I", 5, 0, 0x80000000, 0, 0, 0, mask)
    layout = struct.Struct("=6IQI")
    result = ctypes.create_string_buffer(layout.size)
    if ctypes.CDLL(None).getattrlist(os.fsencode(path), request, result, ctypes.c_size_t(layout.size), ctypes.c_ulong(0x21)):
        return None
    size, _, _, _, _, returned, private, refs = layout.unpack(result)
    if size != layout.size or returned & mask != mask:
        return None
    return private, refs


def apfs_sharing(path, info):
    """Return possible sharing, or None if the filesystem exposes no answer."""
    allocation = apfs_allocation(path)
    if allocation is None:
        return None
    private, refs = allocation
    return refs > 1 or private < info.st_blocks * 512


def volume_available(work):
    # POSIX df's available column reflects the backing volume, including clone
    # sharing, open but unlinked files and activity from other processes.
    row = subprocess.check_output(["df", "-kP", str(work)], text=True).splitlines()[-1]
    return int(row.split()[3]) * 1024


def file_identity(info):
    return [info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns]


def open_inodes(*paths):
    """Include open descriptors and mapped files, using device/inode identity."""
    args = ["/usr/sbin/lsof", "-nP", "-F0fDi"]
    if paths:
        args.extend(("--", *paths))
    result = subprocess.run(args, capture_output=True)
    if result.stderr:
        raise RuntimeError("lsof could not enumerate open files")
    # A pathname query returns 1 when any requested path has no match,
    # even if other requested paths produced records.
    if not (paths and result.returncode == 1):
        result.check_returncode()
    opened = set()
    device = None
    for field in result.stdout.split(b"\0"):
        field = field.lstrip(b"\n")
        if field.startswith(b"f"):
            device = None
        elif field.startswith(b"D"):
            device = int(field[1:], 16)
        elif field.startswith(b"i") and device is not None:
            opened.add((device, int(field[1:])))
    return opened


def dedupe_digest(path, info):
    # Bind the full read to the scanned inode, including after the last byte.
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK), "rb") as stream:
        identity = file_identity(info)
        if file_identity(os.fstat(stream.fileno())) != identity:
            return None
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
        if file_identity(os.fstat(stream.fileno())) == identity:
            return digest
    return None


def duplicate_plan(work, excluded=()):
    if sys.platform != "darwin" or apfs_allocation(work) is None:
        return []
    sizes = defaultdict(list)
    excluded = set(excluded)
    volume = work.stat().st_dev
    cutoff = time.time() - DEDUPE_MIN_AGE
    blocked_flags = stat.UF_IMMUTABLE | stat.SF_IMMUTABLE | stat.UF_APPEND | stat.SF_APPEND
    for root in (work, ROOT / ".local/build-lanes"):
        if root.is_symlink() or root in excluded:
            continue
        for base, dirs, files in os.walk(root):
            here = Path(base)
            dirs[:] = [d for d in dirs if d not in IMMUTABLE_DIRS and here / d not in excluded]
            for name in files:
                path = here / name
                if path in excluded:
                    continue
                try:
                    info = path.lstat()
                except FileNotFoundError:
                    continue
                if (
                    stat.S_ISREG(info.st_mode)
                    and info.st_dev == volume
                    and info.st_size >= DEDUPE_MIN_SIZE
                    and info.st_nlink == 1
                    and not getattr(info, "st_flags", 0) & blocked_flags
                    and info.st_mtime < cutoff
                ):
                    # The compression xattr describes the source's physical
                    # stream. Mixing storage formats can invalidate the clone.
                    sizes[(info.st_size, getattr(info, "st_flags", 0) & stat.UF_COMPRESSED)].append((path, info))
    groups = [group for group in sizes.values() if len(group) > 1]
    if not groups:
        return []
    opened = open_inodes()
    items = []
    for group in groups:
        candidates = []
        for path, info in sorted(group):
            if (info.st_dev, info.st_ino) not in opened:
                allocation = apfs_allocation(path)
                if allocation is not None:
                    candidates.append((path, info, allocation[0]))
        # A fully shared target offers no data blocks to reclaim. Still
        # allow it to serve as the first copy when another has private data.
        if not any(private for _, _, private in candidates[1:]):
            continue
        first = {}
        for path, info, private in candidates:
            try:
                digest = dedupe_digest(path, info)
            except (FileNotFoundError, PermissionError):
                continue
            if digest is None:
                continue
            source, source_identity = first.setdefault(digest, (path, file_identity(info)))
            if source == path or private == 0:
                continue
            items.append(
                {
                    "kind": "duplicate APFS clone",
                    "path": path,
                    "source": source,
                    "bytes": info.st_size,
                    "sha256": digest,
                    "identity": file_identity(info),
                    "source_identity": source_identity,
                    "atime_ns": info.st_atime_ns,
                }
            )
    return items


def clone_duplicate(item):
    path, source = item["path"], item["source"]

    def unchanged():
        return all(
            candidate.resolve() == candidate and file_identity(candidate.lstat()) == identity
            for candidate, identity in ((source, item["source_identity"]), (path, item["identity"]))
        )

    def skipped(reason):
        item["skipped"] = reason

    try:
        if not unchanged():
            return skipped("source or target changed after hashing")
        original = path.lstat()
        libc = ctypes.CDLL(None, use_errno=True)
        with tempfile.TemporaryDirectory(prefix=".prune-clone-", dir=path.parent) as temp:
            clone = Path(temp) / "clone"
            # CLONE_NOFOLLOW. Unlike cp -c, clonefile never falls back to copying.
            if libc.clonefile(os.fsencode(source), os.fsencode(clone), 1):
                error = ctypes.get_errno()
                if error in (errno.ENOTSUP, errno.EXDEV):
                    return skipped("filesystem refused APFS cloning")
                raise OSError(error, os.strerror(error))
            # COPYFILE_METADATA | COPYFILE_NOFOLLOW copies target stat, ACL and
            # xattrs onto the clone without touching the data fork.
            if libc.copyfile(os.fsencode(path), os.fsencode(clone), None, 7 | (3 << 18)):
                error = ctypes.get_errno()
                raise OSError(error, os.strerror(error))
            if dedupe_digest(clone, clone.lstat()) != item["sha256"]:
                return skipped("clone failed full SHA-256 verification")
            os.utime(clone, ns=(item["atime_ns"], original.st_mtime_ns))
            preserved = clone.lstat()
            metadata = ("st_mode", "st_uid", "st_gid", "st_flags", "st_mtime_ns", "st_birthtime")
            if any(getattr(original, key) != getattr(preserved, key) for key in metadata) or preserved.st_atime_ns != item["atime_ns"]:
                return skipped("clone could not preserve target metadata")
            if open_inodes(source, path):
                return skipped("source or target open by a process")
            if not unchanged():
                return skipped("source or target changed before publish")
            os.replace(clone, path)
            item["action"] = "cloned"
    except FileNotFoundError:
        skipped("source or target disappeared")
    except (OSError, RuntimeError, subprocess.CalledProcessError) as error:
        item["error"] = str(error)


def protected_docs(authoritative):
    for root in dict.fromkeys((ROOT, PROTECTION_CHECKOUT or ROOT)):
        for name in PROTECTION_DOCS[:2] if authoritative else PROTECTION_DOCS:
            yield root / name


def tree_size(path):
    if path.is_symlink() or path.is_file():
        return path.lstat().st_size
    total = 0
    for base, _, files in os.walk(path):
        for name in files:
            try:
                total += os.lstat(os.path.join(base, name)).st_size
            except OSError:
                pass
    return total


def newest_mtime(path):
    newest = path.lstat().st_mtime
    if path.is_dir() and not path.is_symlink():
        for base, dirs, files in os.walk(path):
            for name in dirs + files:
                try:
                    newest = max(newest, os.lstat(os.path.join(base, name)).st_mtime)
                except OSError:
                    pass
    return newest


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def protected_state(work, extra, *, authoritative=False):
    hashes, paths = set(extra), set()
    for path in protected_docs(authoritative):
        if path.is_file():
            hashes |= set(HASH.findall(path.read_text(errors="replace")))
    receipts = [work / PROTECTION_RECEIPTS[0]] if authoritative else [work / name for name in PROTECTION_RECEIPTS]
    if authoritative:
        receipts += list(protected_docs(authoritative=True))
    receipts += sorted((work / "device").glob("*.json")) + sorted((work / "device").glob("*/*.json"))
    for path in receipts:
        if not path.is_file():
            continue
        text = path.read_text(errors="replace")
        hashes |= set(HASH.findall(text))
        references = re.findall(r'["`](/[^"`]+|work/[^"`]+)["`]', text)
        if authoritative:
            references += re.findall(r'(?<![\w/])work/[^\s"`<>)\],;]+', text)
        for reference in references:
            candidate = Path(reference)
            candidate = candidate if candidate.is_absolute() else ROOT / candidate
            resolved = candidate.resolve()
            # Shallow roots such as work/experiments would protect everything.
            for witness in (candidate, resolved):
                if (witness.is_relative_to(work) and len(witness.relative_to(work).parts) >= (2 if authoritative else 3)) or (
                    witness.is_relative_to(ROOT / ".local/build-lanes") and len(witness.relative_to(ROOT / ".local/build-lanes").parts) >= 1
                ):
                    paths.add(resolved)
                    break
    return hashes, paths


def kept(path, work):
    """A `.prune-keep` file in a directory (or any parent under work/) protects it."""
    current = path if path.is_dir() else path.parent
    while current.is_relative_to(work):
        if (current / KEEP_MARKER).exists():
            return True
        current = current.parent
    return False


def read_receipt(path):
    try:
        value = json.loads(path.read_text())
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def run_directory(value, work):
    """Only physical run/version directories in the existing generated roots."""
    path = Path(value)
    path = path if path.is_absolute() else ROOT / path
    if not path.is_relative_to(work) or ".." in path.parts:
        raise ValueError("supersession requires a run directory under work")
    relative = path.relative_to(work)
    if len(relative.parts) < 2 or relative.parts[0] not in SCAN_ROOTS:
        raise ValueError("supersession requires an experiment, coordination or rebuild run")
    if not path.is_dir() or any(part.is_symlink() for part in (path, *path.parents) if part.is_relative_to(work)):
        raise ValueError("supersession requires physical directories, not symlinks")
    return path


def success_receipt(run):
    candidates = set(run.glob("*.done.json")) | {run / "result.json"}
    candidates = [path for path in candidates if path.exists() or path.is_symlink()]
    if not candidates or any(path.is_symlink() or not path.is_file() for path in candidates):
        raise ValueError("replacement needs a regular success receipt")
    receipt = max(candidates, key=lambda path: (path.stat().st_mtime_ns, path.name))
    if read_receipt(receipt).get("success") is not True:
        raise ValueError("replacement's latest receipt must report success true")
    return receipt


def supersede(old, new, work):
    old, new = run_directory(old, work), run_directory(new, work)
    if old == new or old.is_relative_to(new) or new.is_relative_to(old):
        raise ValueError("superseded and replacement runs must be disjoint")
    receipt = success_receipt(new)
    marker = {"replacement": str(new.relative_to(ROOT)), "receipt": str(receipt.relative_to(ROOT)), "receipt_sha256": sha256(receipt)}
    # Exclusive creation never follows a marker link or silently resets its age.
    with (old / SUPERSEDED_MARKER).open("x") as stream:
        stream.write(json.dumps(marker, indent=2) + "\n")
    return marker


def superseded_ready(run, work, hashes, paths, cutoff):
    """Fail closed on stale receipt identity, new writes or authoritative pins."""
    try:
        run = run_directory(run, work)
        marker_path = run / SUPERSEDED_MARKER
        if marker_path.is_symlink() or not marker_path.is_file():
            return False
        marker = read_receipt(marker_path)
        replacement = run_directory(marker["replacement"], work)
        if run == replacement or run.is_relative_to(replacement) or replacement.is_relative_to(run):
            return False
        receipt = success_receipt(replacement)
        if str(receipt.relative_to(ROOT)) != marker["receipt"] or sha256(receipt) != marker["receipt_sha256"]:
            return False
        if newest_mtime(run) >= min(cutoff, time.time() - 24 * 3600):
            return False
        if kept(run, work) or any(run.rglob(KEEP_MARKER)) or is_protected_path(run, paths):
            return False
        for path in run.rglob("*"):
            if path.is_symlink():
                return False
            if path.is_file() and path.name.endswith(BINARY_SUFFIXES) and (sha256(path) in hashes or any(h[:12] in str(path.parent) for h in hashes)):
                return False
        return True
    except (OSError, ValueError, KeyError, TypeError):
        return False


def payload_cache_key(cache_root, value):
    if isinstance(value, str):
        path = Path(value).resolve()
        if path.name == "payload" and path.parent.parent == cache_root:
            return path.parent.name
    return None


def cache_protected_state(work, extra):
    """Select live cache references, never nested payload/member hash lists."""
    hashes = {digest: "explicit --keep-sha256" for digest in extra}
    keys = {}
    for path in protected_docs(authoritative=True):
        if path.is_file():
            hashes.update({digest: "APK pinned in " + path.name for digest in HASH.findall(path.read_text(errors="replace"))})
    cache_root = (work / "build-cache").resolve()
    for name in ("current-build", "iteration-base"):
        receipt = read_receipt(work / "config" / (name + ".json"))
        # These two receipts point at a single cache entry, even when they also
        # describe hundreds of input, overlay and payload member hashes.
        apk = receipt.get("apk")
        if apk:
            path = Path(apk)
            path = (path if path.is_absolute() else ROOT / path).resolve()
            if path.is_relative_to(cache_root) and len(path.relative_to(cache_root).parts) >= 2:
                key = path.relative_to(cache_root).parts[0]
                keys[key] = keys[key] + "; " + name + " cache entry" if key in keys else name + " cache entry"
        elif receipt.get("key"):
            keys[receipt["key"]] = name + " cache entry"
        payload_key = payload_cache_key(cache_root, receipt.get("payload_directory"))
        if payload_key:
            keys.setdefault(payload_key, name + " payload reference")
    for name in ("whole-catalog-code-base", "whole-catalog-uncompressed-base"):
        key = read_receipt(work / (name + ".json")).get("build_key")
        if isinstance(key, str) and Path(key).name == key and key not in {"", ".", ".."}:
            keys.setdefault(key, name + " frozen payload")
    if work == ROOT / "work":
        for path in (ROOT / ".local/build-lanes").glob("*/latest-build.json"):
            apk = read_receipt(path).get("apk")
            if isinstance(apk, str) and Path(apk).parent.parent == cache_root and Path(apk).resolve() == Path(apk):
                keys.setdefault(Path(apk).parent.name, "latest build for lane " + path.parent.name)
    # installed.json is overwritten by the install owner; attempts and sync
    # receipts are not evidence that an APK remains installed.
    installed = {}
    legacy = read_receipt(work / "device/installed.json")
    for path in [work / "device/installed.json", *sorted((work / "device").glob("*/installed.json"))]:
        if path.is_file():
            receipt = read_receipt(path)
            identity = receipt.get("serial", str(path.parent))
            # Match device_context.receipt_directory: scoped receipts supersede
            # legacy receipts for that device only after migration activation.
            if path.parent != work / "device" and identity == legacy.get("serial") and not (path.parent / ".device-context-active.json").is_file():
                continue
            installed[identity] = receipt
    for receipt in installed.values():
        digest = receipt.get("apk_sha256")
        if digest:
            hashes.setdefault(digest, "latest installed APK (device receipt)")
    # Current handoffs are the worker-owned candidate references, unlike stale
    # markers left by every previous build. Retain just the newest extant build
    # referenced by each handoff, whether it names the cache key or APK hash.
    candidates = []
    for path in cache_root.glob("*/result.json"):
        if path.parent.is_symlink() or not any(path.parent.glob("*.apk")):
            continue
        receipt = read_receipt(path)
        candidates.append((path.stat().st_mtime, path.parent.name, receipt.get("apk_sha256")))
    for handoff in (ROOT / ".local/orchestrator/handoff").glob("*.md"):
        text = handoff.read_text(errors="replace")
        matches = [entry for entry in candidates if entry[1] in text or entry[2] and entry[2] in text]
        if matches:
            _, key, _ = max(matches)
            keys.setdefault(key, "newest build for worker " + handoff.stem)
    return hashes, keys


def is_protected_path(path, paths):
    resolved = path.resolve()
    return any(resolved == p or resolved.is_relative_to(p) or p.is_relative_to(resolved) for p in paths)


class Planner:
    def __init__(self, work, hashes, paths, min_age_hours, cache_protection=None, cache_min_age_hours=None, superseded_protection=None, *, aggressive=False):
        self.work, self.hashes, self.paths = work, hashes, paths
        self.cutoff = time.time() - min_age_hours * 3600
        self.cache_cutoff = time.time() - (min_age_hours if cache_min_age_hours is None else cache_min_age_hours) * 3600
        self.items, self.kept = [], []
        self.aggressive_cutoff = min(self.cutoff, time.time() - 48 * 3600) if aggressive else None
        self.authoritative_hashes, self.authoritative_paths = (
            superseded_protection if superseded_protection is not None else protected_state(work, [], authoritative=True)
        )
        self.cache_hashes, self.cache_keys = cache_protection if cache_protection is not None else cache_protected_state(work, [])

    def old(self, path):
        return newest_mtime(path) < self.cutoff

    def keep(self, path, reason):
        self.kept.append({"path": str(path.relative_to(ROOT)), "reason": reason})

    def lanes(self):
        """Retire only old, stopped managed lanes, through their normal owner."""
        sys.path.insert(0, str(ROOT / "scripts/lab"))
        from build_lock import host_build_lock

        removed = [read_receipt(p) for p in (self.work / "coordination/build-lanes").glob("*/removed.json")]
        root = ROOT / ".local/build-lanes"
        for lane in sorted(root.iterdir()) if root.is_dir() and not root.is_symlink() else []:
            if lane.name.startswith(".") or not lane.is_dir():
                continue
            marker = lane / "lane.json"
            lock = lane.parent / ".locks" / (lane.name + ".lock")
            if max(marker.stat().st_mtime if marker.exists() else 0, lock.stat().st_mtime if lock.exists() else 0) >= self.cutoff:
                self.keep(lane, "recent build lane operation; shared APFS blocks")
                continue
            if not self.old(lane) or lane.is_symlink() and not self.old(lane.resolve()):
                self.keep(lane, "recent build lane; shared APFS blocks")
                continue
            receipts = [lane / "server.json", lane / "checkout/work/editor/lab-process.json"]
            live = False
            for receipt in receipts:
                if receipt.is_file():
                    pid = json.loads(receipt.read_text())["pid"]
                    try:
                        os.kill(pid, 0)
                        live = True
                    except ProcessLookupError:
                        pass
                    except PermissionError:
                        live = True
            if live:
                self.keep(lane, "build lane has a live owned process")
                continue
            try:
                with host_build_lock(lane.parent / ".locks" / (lane.name + ".lock"), operation="inspect stale build lane", timeout=0):
                    pass
            except TimeoutError:
                self.keep(lane, "build lane lock is held")
                continue
            facts = read_receipt(marker)
            removal = any(
                r.get("removed") is True
                and r.get("name") == lane.name
                and r.get("checkout") == str(lane / "checkout")
                and all(r.get(k) == v for k, v in facts.items())
                for r in removed
            )
            if removal:
                self.add(lane, "removed build lane")
            elif marker.is_file() and not lane.is_symlink():
                self.add(lane, "build lane", name=lane.name)
            else:
                self.keep(lane, "no matching lane removal receipt")

    def snapshots(self):
        """Keep capture receipts; discard only heaps with successful analysis."""
        analyzed = set()
        for receipt in (self.work / "coordination").glob("*/*.done.json"):
            result = read_receipt(receipt)
            if result.get("success") is not True or result.get("compare_returncode", 0) != 0:
                continue
            for row in result.get("exports", [result]):
                snapshot = row.get("snapshot", {})
                if row.get("returncode") == 0:
                    analyzed.add((snapshot.get("file"), snapshot.get("sha256"), snapshot.get("bytes")))
        for run in sorted((self.work / "device").glob("*/experiments/session-memory/*")):
            if not run.is_dir():
                continue
            # Never delete through a symlink above the run; that link may own other runs.
            if any(p.is_symlink() for p in run.parents if p != self.work and p.is_relative_to(self.work)):
                continue
            result = read_receipt(run / "result.json")
            manifest = read_receipt(run / "memory-snapshots.json")
            heaps = sorted(run.glob("*.snap"))
            identities = {r.get("file"): r for r in manifest.values() if isinstance(r, dict)}
            if not isinstance(result.get("success"), bool) or not heaps:
                self.keep(run, "snapshot run is unfinished")
                continue
            if not self.old(run) or run.is_symlink() and not self.old(run.resolve()):
                self.keep(run, "recent snapshot run")
                continue
            if not all(
                (p.name, identities.get(p.name, {}).get("sha256"), p.stat().st_size) in analyzed and identities.get(p.name, {}).get("bytes") == p.stat().st_size
                for p in heaps
            ):
                self.keep(run, "snapshot analysis missing or mismatched")
                continue
            if run.is_symlink():
                self.add(run, "analyzed snapshot run link")
            else:
                for heap in heaps:
                    self.add(heap, "analyzed heap snapshot")

    def add(self, path, kind, receipt_protection=True, **extra):
        boundary = self.work if path.is_relative_to(self.work) else ROOT
        if (
            kept(path, boundary)
            or any(path.rglob(KEEP_MARKER))
            or path.is_symlink()
            and any((p / KEEP_MARKER).exists() for p in (path.resolve(), *path.resolve().parents))
        ):
            self.keep(path, KEEP_MARKER)
            return
        if self.aggressive_cutoff is not None and path.is_dir() and not path.is_symlink():
            if any(any(path.rglob(name)) for name in IMMUTABLE_DIRS) or any(path.rglob("*.apk")):
                self.keep(path, "contains immutable history or separately managed APKs")
                return
        if receipt_protection and is_protected_path(path, self.paths):
            self.keep(path, "named by a protection receipt")
            return
        self.items.append({"path": path, "kind": kind, "bytes": tree_size(path), **extra})

    def build_cache(self):
        root = self.work / "build-cache"
        if root.is_symlink() or not root.is_dir():
            return
        cache_root = root.resolve()
        entries = {}
        reasons = {}
        for entry in sorted(root.iterdir()):
            if not entry.is_dir() or entry.is_symlink():
                continue
            receipt = read_receipt(entry / "result.json")
            entries[entry] = receipt
            apk_hash = receipt.get("apk_sha256")
            if apk_hash in self.cache_hashes:
                reasons[entry.name] = self.cache_hashes[apk_hash] + ": " + apk_hash[:12]
            elif entry.name in self.cache_keys:
                reasons[entry.name] = self.cache_keys[entry.name]
            elif newest_mtime(entry) >= self.cache_cutoff:
                reasons[entry.name] = "recent"
            elif self.aggressive_cutoff is not None and (kept(entry, self.work) or any(entry.rglob(KEEP_MARKER))):
                reasons[entry.name] = KEEP_MARKER
        for entry, receipt in entries.items():
            if entry.name in reasons:
                payload_key = payload_cache_key(cache_root, receipt.get("payload_directory"))
                if payload_key:
                    reasons.setdefault(payload_key, "payload referenced by " + entry.name)
        for entry, receipt in entries.items():
            receipt_path = entry / "result.json"
            if entry.name in reasons:
                self.keep(entry, reasons[entry.name])
            elif tree_size(entry) - (receipt_path.stat().st_size if receipt_path.is_file() else 0) > 1 << 20:
                # Cache retention is an explicit bounded set. Oracle/payload
                # .prune-keep markers outside build-cache keep their semantics.
                self.items.append({"path": entry, "kind": "build-cache entry", "bytes": tree_size(entry), "apk_sha256": receipt.get("apk_sha256")})

    def lab_build(self):
        root = self.work / "lab-build"
        for entry in sorted(root.glob("symbols-*")) if root.is_dir() else []:
            if is_protected_path(entry, self.paths):
                self.keep(entry, "named by a protection receipt")
            elif self.old(entry):
                self.add(entry, "staged symbol package")
            else:
                self.keep(entry, "recent")

    def apk_protected(self, path, *, superseded=False):
        hashes = self.authoritative_hashes if superseded else self.hashes
        paths = self.authoritative_paths if superseded else self.paths
        if is_protected_path(path, paths):
            return True
        if any(h[:12] in str(path.parent) for h in hashes):
            return True
        return sha256(path) in hashes

    def scan(self, name):
        root = self.work / name
        if root.is_symlink() or not root.is_dir():
            return
        supersessions = {}
        for base, dirs, files in os.walk(root):
            here = Path(base)
            dirs[:] = [d for d in dirs if d not in IMMUTABLE_DIRS]
            if KEEP_MARKER in files or (here / KEEP_MARKER).exists():
                dirs.clear()
                continue
            superseded_run = next(
                (
                    parent
                    for parent in (here, *here.parents)
                    if parent.is_relative_to(root) and ((parent / SUPERSEDED_MARKER).exists() or (parent / SUPERSEDED_MARKER).is_symlink())
                ),
                None,
            )
            extra = {}
            if superseded_run is not None:
                # Full-tree age/protection checks and APK hashes are per run,
                # not per visited directory. apply() independently rechecks.
                if superseded_run not in supersessions:
                    ready = superseded_ready(superseded_run, self.work, self.authoritative_hashes, self.authoritative_paths, self.cutoff)
                    supersessions[superseded_run] = (
                        {"superseded_run": str(superseded_run.relative_to(ROOT)), "superseded_marker_sha256": sha256(superseded_run / SUPERSEDED_MARKER)}
                        if ready
                        else None
                    )
                extra = supersessions[superseded_run]
                if extra is None:
                    self.keep(superseded_run, "supersession not eligible or protected")
                    dirs.clear()
                    continue
            paths = self.authoritative_paths if superseded_run else self.paths
            protected_here = any(
                f.endswith(BINARY_SUFFIXES) and self.apk_protected(here / f, superseded=bool(superseded_run)) for f in files if not (here / f).is_symlink()
            )
            for d in list(dirs):
                path = here / d
                unity_library = d == "Library" and (here / "Assets").is_dir()
                if path.is_symlink() or not (d in BULKY_DIRS or unity_library):
                    continue
                dirs.remove(d)
                if protected_here or is_protected_path(path, paths):
                    self.keep(path, "beside a protected APK")
                elif self.old(path):
                    self.add(path, "generated directory", receipt_protection=not superseded_run, **extra)
            for f in files:
                path = here / f
                if path.is_symlink() or f.endswith(".retired.json"):
                    continue
                binary = f.endswith(BINARY_SUFFIXES) or f.endswith("symbols.zip")
                library = f.endswith(".so") and path.stat().st_size >= LARGE_BINARY
                if not (binary or library):
                    continue
                if self.aggressive_cutoff is not None and path.suffix == ".apk":
                    # The aggressive sweep applies one APK age guard and
                    # records a digest for revalidation before unlinking.
                    continue
                if protected_here or is_protected_path(path, paths):
                    self.keep(path, "protected APK set")
                elif self.old(path):
                    self.add(path, "generated binary", receipt_protection=not superseded_run, **extra)

    def aggressive_files(self):
        """Select old standalone APKs and losslessly compressible evidence."""
        planned = {item["path"] for item in self.items}
        volume = self.work.stat().st_dev
        apk_roots = {*SCAN_ROOTS, *EXTRA_APK_ROOTS}
        hashes = self.hashes | self.authoritative_hashes
        paths = self.paths | self.authoritative_paths
        supersessions = {}
        for base, dirs, files in os.walk(self.work):
            here = Path(base)
            if (here / KEEP_MARKER).exists():
                dirs.clear()
                continue
            dirs[:] = [d for d in dirs if d not in IMMUTABLE_DIRS and (here / d) not in planned and not (here / d).is_symlink()]
            for name in files:
                path = here / name
                apk = path.suffix == ".apk" and path.relative_to(self.work).parts[0] in apk_roots
                if path in planned or not (apk or evidence_trace(path)):
                    continue
                try:
                    info = path.lstat()
                    if not stat.S_ISREG(info.st_mode) or info.st_dev != volume or info.st_mtime >= self.aggressive_cutoff:
                        continue
                    item = {"path": path, "bytes": info.st_size, "identity": file_identity(info)}
                    if apk:
                        marked = next((p for p in path.parents if p.is_relative_to(self.work) and os.path.lexists(p / SUPERSEDED_MARKER)), None)
                        if marked is not None:
                            if marked not in supersessions:
                                supersessions[marked] = superseded_ready(marked, self.work, self.authoritative_hashes, self.authoritative_paths, self.cutoff)
                            if not supersessions[marked]:
                                self.keep(path, "supersession not eligible or protected")
                                continue
                            item.update(superseded_run=str(marked.relative_to(ROOT)), superseded_marker_sha256=sha256(marked / SUPERSEDED_MARKER))
                        if is_protected_path(path, paths) or any(digest[:12] in str(path.parent) for digest in hashes):
                            self.keep(path, "protected APK set")
                            continue
                        digest = sha256(path)
                        if digest in hashes:
                            self.keep(path, "pinned APK hash")
                            continue
                        self.items.append(dict(item, kind="old APK", apk_sha256=digest))
                    elif info.st_blocks * 512 > 4096 and not os.path.lexists(compressed_path(path)):
                        sharing = apfs_sharing(path, info)
                        if info.st_nlink > 1 or sharing:
                            self.keep(path, "evidence may share allocated blocks")
                        else:
                            self.items.append(dict(item, kind="trace compression", apfs_sharing=sharing))
                except FileNotFoundError:
                    continue  # An active run may clean up its own scratch.

    def rebuild_outputs(self):
        """Retire generated output copies from terminal, unpinned R9 attempts."""
        hashes = self.hashes | self.authoritative_hashes
        paths = self.paths | self.authoritative_paths
        for receipt in (self.work / "rebuild").glob("*/*/.rebuild/unity/*/result.json"):
            run = receipt.parent
            result = read_receipt(receipt)
            payload = run / "generated-android-data"
            recorded_payload = result.get("payload_directory")
            digest = result.get("apk_sha256")
            members = result.get("payload")
            if (
                receipt.resolve() != receipt
                or IMMUTABLE_DIRS.intersection(run.relative_to(self.work).parts)
                or result.get("success") is not True
                or not isinstance(recorded_payload, str)
                or Path(recorded_payload).parts[-4:] != payload.parts[-4:]
                or not isinstance(digest, str)
                or not HASH.fullmatch(digest)
                or digest in hashes
                or not isinstance(members, dict)
                or is_protected_path(run, paths)
                or not self.old(run)
            ):
                continue
            cache = run / "gradle/caches"
            if cache.is_dir() and cache.resolve() == cache:
                self.add(cache, "isolated R9 Gradle cache")
            if not payload.is_dir() or payload.resolve() != payload:
                continue
            for bundle in payload.iterdir():
                if bundle.is_symlink() or not bundle.is_file() or bundle.suffix or bundle.name not in members:
                    continue
                with bundle.open("rb") as stream:
                    if stream.read(8) != b"UnityFS\0":
                        continue
                self.add(bundle, "receipted R9 Unity bundle")


def compress_trace(path, info):
    target = compressed_path(path)
    zstd = shutil.which("zstd")
    if zstd is None:
        raise RuntimeError("zstd is required to compress retained evidence")
    with tempfile.NamedTemporaryFile(prefix=".prune-", dir=path.parent) as temporary:
        subprocess.run([zstd, "-q", "-6", "--check", "-c", "--", str(path)], stdout=temporary, check=True)
        compressed = os.fstat(temporary.fileno())
        if compressed.st_blocks >= info.st_blocks:
            return {"skipped": "compression does not reduce allocated bytes"}
        subprocess.run([zstd, "-qt", "--", temporary.name], check=True)
        os.utime(temporary.name, ns=(info.st_atime_ns, info.st_mtime_ns))
        if file_identity(path.lstat()) != file_identity(info):
            return {"skipped": "source changed during compression"}
        # Publish atomically without overwriting any existing archive. If
        # interrupted here, the original and the verified archive both remain.
        os.link(temporary.name, target)
        path.unlink()
        return {"action": "compressed", "zstd_bytes": compressed.st_size}


def apply_aggressive(item, work, hashes, paths):
    path = item["path"]
    try:
        info = path.lstat()
        if file_identity(info) != item["identity"] or path.resolve() != path or kept(path, work):
            item["skipped"] = "source changed or became protected after planning"
        elif item["kind"] == "trace compression":
            if info.st_nlink > 1 or apfs_sharing(path, info):
                item["skipped"] = "evidence may share allocated blocks"
            else:
                item.update(compress_trace(path, info))
        elif item["apk_sha256"] in hashes or is_protected_path(path, paths):
            item["skipped"] = "APK became pinned after planning"
        else:
            path.unlink()
            item["action"] = "deleted"
    except FileNotFoundError:
        item["skipped"] = "already removed by concurrent cleanup"
    except FileExistsError:
        item["skipped"] = "compressed evidence already exists"
    except (OSError, RuntimeError, subprocess.CalledProcessError) as error:
        item["error"] = str(error)


def ledger_item(item):
    return {key: str(value.relative_to(ROOT)) if isinstance(value, Path) else value for key, value in item.items()}


def apply(plan, work, ledger_path, *, aggressive=False, dedupe=False, extra_hashes=()):
    retired_receipts = work / "cleanup-analysis/pruned-build-cache"
    reason = "Rebuildable generated output discarded by scripts/prune-generated.py; rebuild from the recorded source commit"
    supersessions = {}
    if aggressive:
        hashes, paths = protected_state(work, extra_hashes)
        authoritative_hashes, authoritative_paths = protected_state(work, extra_hashes, authoritative=True)
        hashes |= authoritative_hashes
        paths |= authoritative_paths
    if aggressive or dedupe:
        before = volume_available(work)
    for item in plan:
        path = item["path"]
        if not path.exists() and not path.is_symlink():
            continue
        if "superseded_run" in item:
            run = ROOT / item["superseded_run"]
            if run not in supersessions:
                hashes, paths = protected_state(work, [], authoritative=True)
                supersessions[run] = (
                    superseded_ready(run, work, hashes, paths, time.time() - 24 * 3600) and sha256(run / SUPERSEDED_MARKER) == item["superseded_marker_sha256"]
                )
            if not supersessions[run]:
                item["skipped"] = "supersession changed or became protected after planning"
                continue
        if item["kind"] in AGGRESSIVE_KINDS:
            apply_aggressive(item, work, hashes, paths)
            continue
        if item["kind"] == "build lane":
            from build_lanes import remove

            try:
                remove(item["name"], root=ROOT)
            except TimeoutError:
                item["skipped"] = "lane became active after planning"
            continue
        if item["kind"] == "build-cache entry":
            keep = retired_receipts / path.name
            keep.mkdir(parents=True, exist_ok=True)
            for small in list(path.glob("*.json")):
                shutil.copy2(small, keep / small.name)
            shutil.rmtree(path)
        else:
            marker = path.with_name(path.name + ".retired.json")
            try:
                if path.is_symlink():
                    path.unlink()
                elif path.is_dir():
                    shutil.rmtree(path)
                else:
                    path.unlink()
            except FileNotFoundError:
                if path.exists():
                    raise
                item["skipped"] = "already removed by concurrent cleanup"
                continue
            if item["kind"] != "staged symbol package":
                marker.write_text(
                    json.dumps(
                        {"kind": "discarded generated output", "path": str(path.relative_to(ROOT)), "bytes": item["bytes"], "reason": reason},
                        indent=2,
                    )
                    + "\n"
                )
    if dedupe:
        clones = duplicate_plan(work)
        for item in clones:
            clone_duplicate(item)
        plan.extend(clones)
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    items = [ledger_item(item) for item in plan]
    if aggressive or dedupe:
        after = volume_available(work)
        measurements = {
            "volume_available_before_bytes": before,
            "volume_available_after_bytes": after,
            "volume_available_delta_bytes": after - before,
            "volume_available_delta_gib": round((after - before) / (1 << 30), 3),
            "compression_sharing_unknown": sum(i["kind"] == "trace compression" and i["apfs_sharing"] is None for i in items),
            "errors": sum("error" in i for i in items),
        }
        if dedupe:
            measurements["cloned_files"] = sum(i.get("action") == "cloned" for i in items)
        ledger_path.write_text(json.dumps({**measurements, "items": items}, indent=2) + "\n")
        return measurements
    ledger_path.write_text(json.dumps(items, indent=2) + "\n")


def main():
    global ROOT, PROTECTION_CHECKOUT
    # Linked worktrees share the canonical ignored work/ and build-lane owners.
    checkout = ROOT
    PROTECTION_CHECKOUT = checkout
    ROOT = Path(subprocess.check_output(["git", "-C", str(checkout), "rev-parse", "--path-format=absolute", "--git-common-dir"], text=True).strip()).parent
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--work-dir", default=str(ROOT / "work"))
    parser.add_argument("--min-age-hours", type=float, default=24.0)
    parser.add_argument("--cache-min-age-hours", type=float, default=3.0, help="Age guard for superseded build-cache entries only")
    parser.add_argument("--keep-sha256", action="append", default=[], help="Additional APK SHA-256 to protect")
    parser.add_argument("--apply", action="store_true", help="Apply changes (default: print the plan only)")
    parser.add_argument("--dedupe", action="store_true", help="Clone byte-identical large files on APFS")
    parser.add_argument("--aggressive", action="store_true", help="Retire old unpinned APKs, compress old evidence and deduplicate")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--supersede", metavar="OLD", help="Mark a generated run/version as replaced; no deletion")
    parser.add_argument("--by", metavar="NEW", help="Replacement run with a passing receipt")
    args = parser.parse_args()
    work = Path(args.work_dir).resolve()
    if not work.is_dir() or not work.is_relative_to(ROOT):
        sys.exit("work directory must exist inside this checkout")
    if args.supersede or args.by:
        if not args.supersede or not args.by or args.apply or args.aggressive or args.dedupe:
            parser.error("--supersede OLD requires --by NEW and cannot be combined with pruning options")
        try:
            print(json.dumps(supersede(args.supersede, args.by, work)))
        except (OSError, ValueError) as error:
            parser.error(str(error))
        return
    if args.apply:
        cleanup = work / "cleanup-analysis"
        cleanup.mkdir(parents=True, exist_ok=True)
        with (cleanup / ".prune.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            return run(args, work)
    return run(args, work)


def run(args, work):
    hashes, paths = protected_state(work, args.keep_sha256)
    planner = Planner(
        work,
        hashes,
        paths,
        args.min_age_hours,
        cache_protected_state(work, args.keep_sha256),
        args.cache_min_age_hours,
        protected_state(work, args.keep_sha256, authoritative=True),
        aggressive=args.aggressive,
    )
    dedupe = args.dedupe or args.aggressive
    if not args.dedupe or args.aggressive:
        planner.build_cache()
        planner.lab_build()
        planner.lanes()
        if not args.aggressive:
            planner.snapshots()
        for name in SCAN_ROOTS:
            planner.scan(name)
        if args.aggressive:
            planner.rebuild_outputs()
            planner.aggressive_files()
    if dedupe and not args.apply:
        planner.items.extend(duplicate_plan(work, (item["path"] for item in planner.items)))
    measurements = {}
    if args.apply:
        stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
        prefix = "aggressive-" if args.aggressive else "dedupe-" if args.dedupe else ""
        ledger = work / "cleanup-analysis" / f"{prefix}prune-{stamp}-{uuid.uuid4().hex[:8]}.json"
        measurements = apply(planner.items, work, ledger, aggressive=args.aggressive, dedupe=dedupe, extra_hashes=args.keep_sha256) or {}
        measurements["ledger"] = str(ledger.relative_to(ROOT))
    total = sum(i["bytes"] for i in planner.items)
    summary = {
        "mode": "apply" if args.apply else "plan",
        "aggressive": args.aggressive,
        "dedupe": dedupe,
        "protected_hashes": len(hashes),
        "cache_protected_hashes": len(planner.cache_hashes),
        "cache_protected_keys": len(planner.cache_keys),
        "items": len(planner.items),
        "bytes": total,
        "gib": round(total / (1 << 30), 1),
        "kept": len(planner.kept),
        **measurements,
    }
    if args.json:
        print(json.dumps({**summary, "kept_items": planner.kept, "plan": [ledger_item(item) for item in planner.items]}, indent=2))
    else:
        by_kind = {}
        for item in planner.items:
            by_kind.setdefault(item["kind"], [0, 0])
            by_kind[item["kind"]][0] += 1
            by_kind[item["kind"]][1] += item["bytes"]
        for kind, (count, size) in sorted(by_kind.items()):
            print(f"{kind}: {count} items, {size / (1 << 30):.1f} GiB")
        print(json.dumps(summary))
    if summary.get("errors"):
        sys.exit(1)


if __name__ == "__main__":
    main()
