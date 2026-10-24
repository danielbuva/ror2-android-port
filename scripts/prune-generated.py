#!/usr/bin/env python3
"""Discard bulky, rebuildable build outputs under ignored work/.

Current. Every agent runs this when it finishes a build/run task (AGENTS.md
"Storage hygiene"). It removes only regenerable binaries: superseded
build-cache entries, staged symbol packages, APK/AAB/symbol/libil2cpp copies,
payload copies and Unity Library/Bee/il2cppOutput trees inside experiment and
coordination roots. Receipts, logs, captures, JSON evidence and recipes stay.

Protected: every APK SHA-256 named in PORTING_STATE.md, docs/BASELINE.md,
docs/history-retention.md, the codex coordination lock, current-build, iteration-base and
device receipts (plus --keep-sha256), and anything modified more recently than
--min-age-hours (so it is safe to run while a build holds the editor). A removed build-cache entry keeps its result.json under
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
SCAN_ROOTS = ("experiments", "coordination")


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
            if candidate.is_relative_to(work) and len(candidate.relative_to(work).parts) >= 3:
                paths.add(candidate.resolve())
    return hashes, paths


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

    def add(self, path, kind, **extra):
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
        if not path.exists():
            continue
        if item["kind"] == "build-cache entry":
            keep = retired_receipts / path.name
            keep.mkdir(parents=True, exist_ok=True)
            for small in list(path.glob("*.json")):
                shutil.copy2(small, keep / small.name)
            shutil.rmtree(path)
        else:
            marker = path.with_name(path.name + ".retired.json")
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()
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
