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
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HASH = re.compile(r"\b[0-9a-f]{64}\b")
PROTECTION_DOCS = ("PORTING_STATE.md", "docs/BASELINE.md", "docs/history-retention.md")
PROTECTION_RECEIPTS = ("coordination/codex-runtime.lock", "config/current-build.json", "config/iteration-base.json")
BINARY_SUFFIXES = (".apk", ".aab", ".obb")
BULKY_DIRS = {"payload", "il2cppOutput", "Bee"}
LARGE_BINARY = 32 * 1024 * 1024
SCAN_ROOTS = ("experiments", "coordination", "rebuild")
KEEP_MARKER = ".prune-keep"
SUPERSEDED_MARKER = ".superseded-by"


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
    for name in PROTECTION_DOCS[:2] if authoritative else PROTECTION_DOCS:
        path = ROOT / name
        if path.is_file():
            hashes |= set(HASH.findall(path.read_text(errors="replace")))
    receipts = [work / PROTECTION_RECEIPTS[0]] if authoritative else [work / name for name in PROTECTION_RECEIPTS]
    if authoritative:
        receipts += [ROOT / name for name in PROTECTION_DOCS[:2]]
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
            # Shallow roots such as work/experiments would protect everything.
            if (candidate.is_relative_to(work) and len(candidate.relative_to(work).parts) >= (2 if authoritative else 3)) or (
                candidate.is_relative_to(ROOT / ".local/build-lanes") and len(candidate.relative_to(ROOT / ".local/build-lanes").parts) >= 1
            ):
                paths.add(candidate.resolve())
    return hashes, paths


def kept(path, work):
    """A `.prune-keep` file in a directory (or any parent under work/) protects it."""
    current = path if path.is_dir() else path.parent
    while current.is_relative_to(work) and current != work:
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
    for name in PROTECTION_DOCS[:2]:
        path = ROOT / name
        if path.is_file():
            hashes.update({digest: "APK pinned in " + name for digest in HASH.findall(path.read_text(errors="replace"))})
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
    def __init__(self, work, hashes, paths, min_age_hours, cache_protection=None, cache_min_age_hours=None, superseded_protection=None):
        self.work, self.hashes, self.paths = work, hashes, paths
        self.cutoff = time.time() - min_age_hours * 3600
        self.cache_cutoff = time.time() - (min_age_hours if cache_min_age_hours is None else cache_min_age_hours) * 3600
        self.items, self.kept = [], []
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
        if not root.is_dir():
            return
        for base, dirs, files in os.walk(root):
            here = Path(base)
            superseded_run = next(
                (
                    parent
                    for parent in (here, *here.parents)
                    if parent.is_relative_to(root) and ((parent / SUPERSEDED_MARKER).exists() or (parent / SUPERSEDED_MARKER).is_symlink())
                ),
                None,
            )
            if superseded_run is not None and not superseded_ready(superseded_run, self.work, self.authoritative_hashes, self.authoritative_paths, self.cutoff):
                self.keep(superseded_run, "supersession not eligible or protected")
                dirs.clear()
                continue
            paths = self.authoritative_paths if superseded_run else self.paths
            extra = (
                {"superseded_run": str(superseded_run.relative_to(ROOT)), "superseded_marker_sha256": sha256(superseded_run / SUPERSEDED_MARKER)}
                if superseded_run
                else {}
            )
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
                if protected_here or is_protected_path(path, paths):
                    self.keep(path, "protected APK set")
                elif self.old(path):
                    self.add(path, "generated binary", receipt_protection=not superseded_run, **extra)


def apply(plan, work, ledger_path):
    retired_receipts = work / "cleanup-analysis/pruned-build-cache"
    reason = "Rebuildable generated output discarded by scripts/prune-generated.py; rebuild from the recorded source commit"
    supersessions = {}
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
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    ledger_path.write_text(json.dumps([{**i, "path": str(i["path"].relative_to(ROOT))} for i in plan], indent=2) + "\n")


def main():
    global ROOT
    # Linked worktrees share the canonical ignored work/ and build-lane owners.
    ROOT = Path(subprocess.check_output(["git", "-C", str(ROOT), "rev-parse", "--path-format=absolute", "--git-common-dir"], text=True).strip()).parent
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--work-dir", default=str(ROOT / "work"))
    parser.add_argument("--min-age-hours", type=float, default=24.0)
    parser.add_argument("--cache-min-age-hours", type=float, default=3.0, help="Age guard for superseded build-cache entries only")
    parser.add_argument("--keep-sha256", action="append", default=[], help="Additional APK SHA-256 to protect")
    parser.add_argument("--apply", action="store_true", help="Delete the planned items (default: print the plan only)")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--supersede", metavar="OLD", help="Mark a generated run/version as replaced; no deletion")
    parser.add_argument("--by", metavar="NEW", help="Replacement run with a passing receipt")
    args = parser.parse_args()
    work = Path(args.work_dir).resolve()
    if not work.is_dir() or not work.is_relative_to(ROOT):
        sys.exit("work directory must exist inside this checkout")
    if args.supersede or args.by:
        if not args.supersede or not args.by or args.apply:
            parser.error("--supersede OLD requires --by NEW and cannot be combined with --apply")
        try:
            print(json.dumps(supersede(args.supersede, args.by, work)))
        except (OSError, ValueError) as error:
            parser.error(str(error))
        return
    # No lock check: the --min-age-hours guard already excludes anything a running build writes.
    hashes, paths = protected_state(work, args.keep_sha256)
    planner = Planner(
        work,
        hashes,
        paths,
        args.min_age_hours,
        cache_protected_state(work, args.keep_sha256),
        args.cache_min_age_hours,
        protected_state(work, args.keep_sha256, authoritative=True),
    )
    planner.build_cache()
    planner.lab_build()
    planner.lanes()
    planner.snapshots()
    for name in SCAN_ROOTS:
        planner.scan(name)
    total = sum(i["bytes"] for i in planner.items)
    summary = {
        "mode": "apply" if args.apply else "plan",
        "protected_hashes": len(hashes),
        "cache_protected_hashes": len(planner.cache_hashes),
        "cache_protected_keys": len(planner.cache_keys),
        "items": len(planner.items),
        "bytes": total,
        "gib": round(total / (1 << 30), 1),
        "kept": len(planner.kept),
    }
    if args.apply:
        ledger = work / "cleanup-analysis" / ("prune-" + time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()) + ".json")
        apply(planner.items, work, ledger)
        summary["ledger"] = str(ledger.relative_to(ROOT))
    if args.json:
        print(json.dumps({**summary, "kept_items": planner.kept, "plan": [{**i, "path": str(i["path"].relative_to(ROOT))} for i in planner.items]}, indent=2))
    else:
        by_kind = {}
        for item in planner.items:
            by_kind.setdefault(item["kind"], [0, 0])
            by_kind[item["kind"]][0] += 1
            by_kind[item["kind"]][1] += item["bytes"]
        for kind, (count, size) in sorted(by_kind.items()):
            print(f"{kind}: {count} items, {size / (1 << 30):.1f} GiB")
        print(json.dumps(summary))


if __name__ == "__main__":
    main()
