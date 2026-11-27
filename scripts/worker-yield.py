#!/usr/bin/env python3
"""Decide how many orchestrated workers actually speed development up.

More workers only help while they do not compete for what is scarce: the Codex
quota, the three test devices and the one exact Unity editor. This report
measures each workstream over a trailing window and says KEEP, WATCH or PARK,
so the orchestrator (or the dispatcher, via --write) can size the active set
to what pays off instead of to what is possible.

Inputs are the local orchestrator directory (ignored `.local/orchestrator`):
`logs/<workstream>-<timestamp>.jsonl` (Codex turns and token usage),
`status/<workstream>.md` (the worker's own status lines, which name the PRs it
merged), `status/budget.log` (device grants) and `park/` (parked workers), plus
squash merges on `origin/main` whose subject ends in `(#N)`.

    scripts/worker-yield.py                 # report for the last 3 days
    scripts/worker-yield.py --days 7
    scripts/worker-yield.py --write         # also write status/worker-yield.md
                                            # and alert on newly failing workers

Rules (all over the window; tokens are weighted as in usage.py):
- PARK: spent at least MIN_TOKENS and merged nothing; or costs more than
  PARK_RATIO x the fleet median per merged PR while also escalating or holding
  devices heavily (it slows the workers it competes with).
- WATCH: costs more than WATCH_RATIO x the median per merged PR.
- KEEP: everything else. Too little spend to judge is reported as NEW.
Budget: Codex usage is capped per week, so worker count is ultimately set by
spend. Put the owner's chosen daily spend (millions of weighted tokens) in
`<orchestrator>/budget-daily`. The report compares the active workers' recent
daily spend with it and lists who to park, worst cost per PR first, to fit.
Without that file it only reports quota failures and asks for a budget.
"""

import argparse
import collections
import datetime
import json
import re
import statistics
import subprocess
import sys
from pathlib import Path

UTC = datetime.timezone.utc
ROOT = Path(__file__).resolve().parents[1]
MIN_TOKENS = 5e6
WATCH_RATIO = 1.5
PARK_RATIO = 2.0
HEAVY_ESCALATIONS = 5
HEAVY_DEVICE_GRANTS = 10
STAMP = re.compile(r"^(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d)")
MERGED_PR = re.compile(r"(?:MERGED|[Mm]erged|[Ll]anded|DONE)[^#\n]{0,40}#(\d{2,5})|#(\d{2,5})[^\n]{0,25}(?:merged|landed|MERGED)")
GRANT = re.compile(r"dispatcher: granted (\S+) to (\S+)")
QUOTA = "hit your usage limit"


def weighted(usage):
    cached = usage.get("cached_input_tokens", 0)
    return usage["input_tokens"] - cached + 0.1 * cached + usage["output_tokens"]


def workstream_of(log_name):
    return re.sub(r"-\d{8}T\d{6}Z?\.jsonl$", "", log_name)


def stamp_of(line):
    match = STAMP.match(line)
    if not match:
        return None
    return datetime.datetime.fromisoformat(match[1]).replace(tzinfo=UTC)


def day_of(timestamp):
    return datetime.datetime.fromtimestamp(timestamp, UTC).strftime("%Y-%m-%d")


def read_logs(orchestrator, since, now):
    """Tokens, thread count and quota failures per workstream and per day."""
    tokens = collections.Counter()
    last_day = collections.Counter()
    threads = collections.Counter()
    day_tokens = collections.Counter()
    day_workers = collections.defaultdict(set)
    quota_days = set()
    quota_hits = 0
    for log in sorted((orchestrator / "logs").glob("*.jsonl")):
        modified = log.stat().st_mtime
        if modified < since.timestamp():
            continue
        name = workstream_of(log.name)
        threads[name] += 1
        day = day_of(modified)
        for line in log.read_text(errors="replace").splitlines():
            if '"turn.completed"' in line:
                try:
                    spent = weighted(json.loads(line)["usage"])
                except (ValueError, KeyError):
                    continue
                tokens[name] += spent
                if modified >= now.timestamp() - 86400:
                    last_day[name] += spent
                day_tokens[day] += spent
                day_workers[day].add(name)
            elif QUOTA in line and '"turn.failed"' in line:
                quota_hits += 1
                quota_days.add(day)
    return tokens, last_day, threads, day_tokens, day_workers, quota_hits, quota_days


def read_status(orchestrator, since, merged):
    """PRs each worker reports merging, and its escalations, from its own status lines."""
    prs = collections.defaultdict(set)
    escalations = collections.Counter()
    for status in sorted((orchestrator / "status").glob("*.md")):
        name = status.stem
        for line in status.read_text(errors="replace").splitlines():
            when = stamp_of(line)
            if when is None or when < since or "dispatcher" in line or "orchestrator:" in line:
                continue
            if "ESCALATE" in line or "BLOCKED" in line:
                escalations[name] += 1
            for first, second in MERGED_PR.findall(line):
                number = first or second
                if number in merged:
                    prs[name].add(number)
    return prs, escalations


def read_grants(orchestrator, since):
    grants = collections.Counter()
    devices = set()
    budget = orchestrator / "status" / "budget.log"
    if budget.exists():
        for line in budget.read_text(errors="replace").splitlines():
            when = stamp_of(line)
            match = GRANT.search(line)
            if when and match and when >= since:
                devices.add(match[1])
                grants[match[2]] += 1
    return grants, devices


def merged_prs(since, ref="origin/main"):
    """{PR number: (UTC day, non-docs lines changed)} for squash merges since the cutoff."""
    out = subprocess.run(
        ["git", "log", ref, f"--since={since.isoformat()}", "--numstat", "--format=%x00%ct %s"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    result = {}
    for block in out.split("\0")[1:]:
        header, *rows = block.splitlines()
        stamp, _, subject = header.partition(" ")
        match = re.search(r"\(#(\d+)\)$", subject)
        if not match:
            continue
        lines = 0
        for row in rows:
            parts = row.split("\t")
            if len(parts) == 3 and parts[0].isdigit() and not (parts[2].startswith("docs/") or parts[2].endswith(".md")):
                lines += int(parts[0]) + int(parts[1])
        result[match[1]] = (day_of(int(stamp)), lines)
    return result


def verdicts(tokens, prs, escalations, grants):
    rows = {}
    costs = [tokens[w] / len(prs[w]) for w in tokens if prs[w] and tokens[w] >= MIN_TOKENS]
    median = statistics.median(costs) if costs else 0.0
    for name in sorted(set(tokens) | set(prs)):
        spent, merged = tokens[name], len(prs[name])
        cost = spent / merged if merged else None
        heavy = escalations[name] >= HEAVY_ESCALATIONS or grants[name] >= HEAVY_DEVICE_GRANTS
        if spent < MIN_TOKENS:
            verdict = "NEW" if not merged else "KEEP"
        elif not merged:
            verdict = "PARK"
        elif median and cost > PARK_RATIO * median and heavy:
            verdict = "PARK"
        elif median and cost > WATCH_RATIO * median:
            verdict = "WATCH"
        else:
            verdict = "KEEP"
        rows[name] = (spent, merged, cost, verdict)
    return rows, median


def report(orchestrator, days, merged=None, now=None):
    now = now or datetime.datetime.now(UTC)
    since = now - datetime.timedelta(days=days)
    merged = merged_prs(since) if merged is None else merged
    tokens, last_day, threads, day_tokens, day_workers, quota_hits, quota_days = read_logs(orchestrator, since, now)
    prs, escalations = read_status(orchestrator, since, merged)
    grants, devices = read_grants(orchestrator, since)
    rows, median = verdicts(tokens, prs, escalations, grants)
    parked = {p.name for p in (orchestrator / "park").glob("*")} if (orchestrator / "park").exists() else set()

    out = [f"# Worker yield, last {days} day(s) to {now:%Y-%m-%d %H:%M} UTC", ""]
    out.append(f"Fleet median: {median / 1e6:.1f}M weighted tokens per merged PR.")
    out.append("")
    out.append("| Workstream | State | Mtok | Threads | Merged PRs | Mtok/PR | Code lines | Device grants | Escalations | Verdict |")
    out.append("| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |")
    for name, (spent, count, cost, verdict) in sorted(rows.items(), key=lambda item: -item[1][0]):
        lines = sum(merged[p][1] for p in prs[name])
        state = "parked" if name in parked else "active"
        shown = f"{cost / 1e6:.1f}" if cost else "-"
        out.append(
            f"| {name} | {state} | {spent / 1e6:.1f} | {threads[name]} | {count} | {shown} | {lines} | {grants[name]} | {escalations[name]} | {verdict} |"
        )
    out += ["", "| UTC day | Active workers | Merged PRs | Mtok | Quota hit |", "| --- | ---: | ---: | ---: | --- |"]
    merged_by_day = collections.Counter(day for day, _ in merged.values())
    for day in sorted(set(day_tokens) | set(merged_by_day)):
        hit = "yes" if day in quota_days else ""
        out.append(f"| {day} | {len(day_workers[day])} | {merged_by_day[day]} | {day_tokens[day] / 1e6:.1f} | {hit} |")
    out.append("")
    budget_file = orchestrator / "budget-daily"
    budget = float(budget_file.read_text().strip()) * 1e6 if budget_file.exists() else None
    if quota_hits:
        out.append(f"Quota: {quota_hits} turn(s) failed on the usage limit in this window.")
    active = {name: row for name, row in rows.items() if name not in parked}
    daily = sum(last_day[name] for name in active)
    if budget is None:
        out.append(
            f"Active workers spent {daily / 1e6:.0f}M in the last 24 h. Set budget-daily to the spend the owner "
            "accepts; until then size the set by the verdicts and device contention alone."
        )
    elif daily > budget:
        over = daily - budget
        cut = []
        ranked = sorted(active.items(), key=lambda item: -(item[1][2] or float("inf")))
        for name, row in ranked:
            if over <= 0:
                break
            cut.append(name)
            over -= last_day[name]
        out.append(
            f"Over budget: active workers spent {daily / 1e6:.0f}M in the last 24 h against {budget / 1e6:.0f}M. Park, worst cost per PR first: {', '.join(cut)}."
        )
    else:
        out.append(f"Within budget: {daily / 1e6:.0f}M in the last 24 h against {budget / 1e6:.0f}M.")
    device_users = [w for w in grants if w not in parked]
    if devices and len(device_users) > 2 * len(devices):
        out.append(
            f"Device-bound: {len(device_users)} unparked workers took grants on {len(devices)} device(s); more device workers add queue waits, not throughput."
        )
    actionable = sorted(name for name, row in rows.items() if row[3] == "PARK" and name not in parked)
    return "\n".join(out) + "\n", actionable


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--orchestrator", type=Path, default=ROOT / ".local" / "orchestrator")
    parser.add_argument("--days", type=float, default=3)
    parser.add_argument("--write", action="store_true", help="write status/worker-yield.md and alert on new PARK verdicts")
    args = parser.parse_args()
    text, actionable = report(args.orchestrator, args.days)
    print(text, end="")
    if args.write:
        status = args.orchestrator / "status"
        (status / "worker-yield.md").write_text(text)
        seen_file = status / ".worker-yield-alerted"
        seen = set(seen_file.read_text().split()) if seen_file.exists() else set()
        new = [name for name in actionable if name not in seen]
        if new:
            stamp = datetime.datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
            with (status / "orchestrator-alerts.md").open("a") as alerts:
                alerts.write(f"{stamp} worker-yield: PARK recommended for {', '.join(new)} (see status/worker-yield.md)\n")
        seen_file.write_text("\n".join(sorted(seen | set(actionable))) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
