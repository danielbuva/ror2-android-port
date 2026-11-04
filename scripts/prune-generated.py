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


def protected_state(work, extra):
    hashes, paths = set(extra), set()
    for name in PROTECTION_DOCS:
        path = ROOT / name
        if path.is_file():
            hashes |= set(HASH.findall(path.read_text(errors="replace")))
    receipts = [work / name for name in PROTECTION_RECEIPTS]
    receipts += sorted((work / "device").glob("*.json")) + sorted((work / "device").glob("*/*.json"))
    for path in receipts:
        if not path.is_file():
            continue
        text = path.read_text(errors="replace")
        hashes |= set(HASH.findall(text))
        for match in re.finditer(r'"(/[^"]+|work/[^"]+)"', text):
            candidate = Path(match[1])
            candidate = candidate if candidate.is_absolute() else ROOT / candidate
            # Shallow roots such as work/experiments would protect everything.
            if (candidate.is_relative_to(work) and len(candidate.relative_to(work).parts) >= 3) or (
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


def is_protected_path(path, paths):
    resolved = path.resolve()
    return any(resolved == p or resolved.is_relative_to(p) or p.is_relative_to(resolved) for p in paths)


class Planner:
    def __init__(self, work, hashes, paths, min_age_hours):
        self.work, self.hashes, self.paths = work, hashes, paths
        self.cutoff = time.time() - min_age_hours * 3600
        self.items, self.kept = [], []

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

    def add(self, path, kind, **extra):
        boundary = self.work if path.is_relative_to(self.work) else ROOT
        if (
            kept(path, boundary)
            or any(path.rglob(KEEP_MARKER))
            or path.is_symlink()
            and any((p / KEEP_MARKER).exists() for p in (path.resolve(), *path.resolve().parents))
        ):
            self.keep(path, KEEP_MARKER)
            return
        if is_protected_path(path, self.paths):
            self.keep(path, "named by a protection receipt")
            return
        self.items.append({"path": path, "kind": kind, "bytes": tree_size(path), **extra})

    def build_cache(self):
        root = self.work / "build-cache"
        if not root.is_dir():
            return
        for entry in sorted(root.iterdir()):
            if not entry.is_dir() or entry.is_symlink():
                continue
            receipt = entry / "result.json"
            apk_hash = None
            if receipt.is_file():
                try:
                    apk_hash = json.loads(receipt.read_text()).get("apk_sha256")
                except (OSError, ValueError):
                    pass
            if apk_hash in self.hashes:
                self.keep(entry, "protected APK " + apk_hash[:12])
            elif is_protected_path(entry, self.paths):
                self.keep(entry, "named by a protection receipt")
            elif not self.old(entry):
                self.keep(entry, "recent")
            elif tree_size(entry) - (receipt.stat().st_size if receipt.is_file() else 0) > 1 << 20:
                self.add(entry, "build-cache entry", apk_sha256=apk_hash)

    def lab_build(self):
        root = self.work / "lab-build"
        for entry in sorted(root.glob("symbols-*")) if root.is_dir() else []:
            if is_protected_path(entry, self.paths):
                self.keep(entry, "named by a protection receipt")
            elif self.old(entry):
                self.add(entry, "staged symbol package")
            else:
                self.keep(entry, "recent")

    def apk_protected(self, path):
        if is_protected_path(path, self.paths):
            return True
        if any(h[:12] in str(path.parent) for h in self.hashes):
            return True
        return sha256(path) in self.hashes

    def scan(self, name):
        root = self.work / name
        if not root.is_dir():
            return
        for base, dirs, files in os.walk(root):
            here = Path(base)
            protected_here = any(f.endswith(BINARY_SUFFIXES) and self.apk_protected(here / f) for f in files if not (here / f).is_symlink())
            for d in list(dirs):
                path = here / d
                unity_library = d == "Library" and (here / "Assets").is_dir()
                if path.is_symlink() or not (d in BULKY_DIRS or unity_library):
                    continue
                dirs.remove(d)
                if protected_here or is_protected_path(path, self.paths):
                    self.keep(path, "beside a protected APK")
                elif self.old(path):
                    self.add(path, "generated directory")
            for f in files:
                path = here / f
                if path.is_symlink() or f.endswith(".retired.json"):
                    continue
                binary = f.endswith(BINARY_SUFFIXES) or f.endswith("symbols.zip")
                library = f.endswith(".so") and path.stat().st_size >= LARGE_BINARY
                if not (binary or library):
                    continue
                if protected_here or is_protected_path(path, self.paths):
                    self.keep(path, "protected APK set")
                elif self.old(path):
                    self.add(path, "generated binary")


def apply(plan, work, ledger_path):
    retired_receipts = work / "cleanup-analysis/pruned-build-cache"
    reason = "Rebuildable generated output discarded by scripts/prune-generated.py; rebuild from the recorded source commit"
    for item in plan:
        path = item["path"]
        if not path.exists() and not path.is_symlink():
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
    parser.add_argument("--keep-sha256", action="append", default=[], help="Additional APK SHA-256 to protect")
    parser.add_argument("--apply", action="store_true", help="Delete the planned items (default: print the plan only)")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    work = Path(args.work_dir).resolve()
    if not work.is_dir() or not work.is_relative_to(ROOT):
        sys.exit("work directory must exist inside this checkout")
    # No lock check: the --min-age-hours guard already excludes anything a running build writes.
    hashes, paths = protected_state(work, args.keep_sha256)
    planner = Planner(work, hashes, paths, args.min_age_hours)
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
        print(json.dumps({**summary, "plan": [{**i, "path": str(i["path"].relative_to(ROOT))} for i in planner.items]}, indent=2))
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
