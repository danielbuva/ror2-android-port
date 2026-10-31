"""Comment-driven lab runner: run a fixed menu of lab jobs for owner "/lab ..." comments.

The lab-runner workflow copies this file from origin/main and runs it standalone (stdlib only) on the
owner's self-hosted runner, so a branch can change what a job builds but never what the runner allows.
Each job gets its own worktree of the requested ref, an atomic orchestrator device lease when it uses a
device, and a sanitized result comment (public repository: no paths, serials, storage IDs or emails).
Raw output stays local under work/coordination/lab-runner/<run>/. See docs/LAB_RUNNER.md.
"""

import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import time
from pathlib import Path

USAGE = """`/lab <job> [ref=<branch|sha>] [device=<alias>] [-- args...]`
jobs: `status`, `host-tests`, `preflight`, `doctor`, `dev <action> ...`, `script <repo path .py> ...`, `toolhost`"""
JOBS = {"status", "host-tests", "preflight", "doctor", "dev", "script", "toolhost"}
DEV_ACTIONS = {
    "build", "install", "run", "logs", "screenshot", "crash", "storage", "inspect", "test",
    "check-baseline", "sync-data", "perf", "graphics", "diagnostics", "lane", "preflight", "doctor",
}  # fmt: skip
SCRIPT_ROOTS = ("tools/", "scripts/", "recipe/", "tests/")
REF = re.compile(r"^(?!.*\.\.)[A-Za-z0-9][A-Za-z0-9._/-]{0,199}$")
COMMENT_LIMIT = 60000
TAIL_LINES = 150
JOB_TIMEOUT = 5 * 3600
TEST_PACKAGE = "dev.ror2lab.installertest"  # disposable identity; never the lab or toolhost packages


class CommandError(ValueError):
    pass


def parse_command(body):
    """Parse the first line of a comment into a job request; raise CommandError when it is not allowed."""
    line = body.strip().splitlines()[0] if body.strip() else ""
    try:
        words = shlex.split(line)
    except ValueError as error:
        raise CommandError(f"cannot parse command: {error}") from None
    if len(words) < 2 or words[0] != "/lab":
        raise CommandError("not a /lab command")
    job, rest = words[1], words[2:]
    if job not in JOBS:
        raise CommandError(f"unknown job `{job}`")
    request = {"job": job, "ref": "main", "device": None, "args": []}
    while rest and rest[0] != "--" and "=" in rest[0] and rest[0].split("=", 1)[0] in ("ref", "device"):
        key, value = rest.pop(0).split("=", 1)
        request[key] = value
    if rest and rest[0] == "--":
        rest.pop(0)
    request["args"] = rest
    if not REF.match(request["ref"]):
        raise CommandError("invalid ref")
    if request["device"] is not None and not re.fullmatch(r"[a-z0-9-]{1,32}", request["device"]):
        raise CommandError("invalid device alias")
    if job == "dev":
        if not rest or rest[0] not in DEV_ACTIONS:
            raise CommandError(f"`dev` needs an allowed action: {', '.join(sorted(DEV_ACTIONS))}")
        if any(a == "--device" or a.startswith("--device=") for a in rest):
            raise CommandError("pass the device as device=<alias>, not --device")
    if job == "toolhost" and (rest or request["device"]):
        raise CommandError("`toolhost` takes only ref=; its local builder chooses and leases the build phone")
    if job == "script":
        if not rest:
            raise CommandError("`script` needs a repository path")
        path = rest[0]
        if path.startswith("/") or ".." in Path(path).parts or not path.endswith(".py") or not path.startswith(SCRIPT_ROOTS):
            raise CommandError(f"script must be a .py file under {', '.join(SCRIPT_ROOTS)}")
    return request


def sanitize(text, secrets=()):
    """Remove private identifiers before text is posted to the public repository."""
    for secret in sorted((s for s in secrets if s), key=len, reverse=True):
        text = text.replace(secret, "<private>")
    text = re.sub(r"/(?:Users|home)/[^/\s]+", "~", text)
    text = re.sub(r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b", "<uuid>", text)
    text = re.sub(r"[\w.+-]+@[\w-]+\.[\w.-]+", "<email>", text)
    text = re.sub(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", "<ip>", text)
    text = re.sub(r"(?i)(gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})", "<token>", text)
    return text


def battery_refusal(level, current_now, temp_tenths):
    """The user's battery rule: no run above 85 %, while charging at >= 80 %, or when the battery is warm."""
    if level > 85:
        return f"battery at {level} % (> 85 %)"
    if level >= 80 and current_now > 0:
        return "battery is actually charging at >= 80 %"
    if temp_tenths >= 350:
        return f"battery at {temp_tenths / 10:.1f} C (>= 35 C)"
    return None


class Runner:
    def __init__(self, repo, env):
        self.repo = Path(repo).resolve()
        self.env = env
        self.run_id = env.get("LAB_RUN_ID", str(int(time.time())))
        self.out = self.repo / "work/coordination/lab-runner" / self.run_id
        self.out.mkdir(parents=True, exist_ok=True)
        self.log = self.out / "output.log"
        config = self.repo / "work/config/lab-runner.json"
        self.config = json.loads(config.read_text()) if config.is_file() else {}
        self.devices = self.config.get("devices", {})
        self.adb = shutil.which("adb", path="/opt/homebrew/bin") or "adb"
        self.leases = self.repo / ".local/orchestrator/leases"

    def secrets(self):
        return [*self.devices.values(), str(self.repo), str(Path.home())]

    def gh(self, *args):
        return subprocess.run(["gh", *args], capture_output=True, text=True, env=self.env)

    def comment(self, body):
        issue = self.env["LAB_ISSUE_NUMBER"]
        body = sanitize(body, self.secrets())[:COMMENT_LIMIT]
        self.gh("api", f"repos/{self.env['GITHUB_REPOSITORY']}/issues/{issue}/comments", "-f", f"body={body}")

    def react(self, content):
        cid = self.env.get("LAB_COMMENT_ID")
        if cid:
            self.gh("api", f"repos/{self.env['GITHUB_REPOSITORY']}/issues/comments/{cid}/reactions", "-f", f"content={content}")

    def run(self, argv, cwd, timeout=JOB_TIMEOUT, extra_env=None):
        env = dict(os.environ, **(extra_env or {}))
        env.pop("GH_TOKEN", None)  # lab jobs never see the workflow token
        with self.log.open("a") as log:
            log.write(f"$ {shlex.join(argv)}\n")
            log.flush()
            try:
                return subprocess.run(argv, cwd=cwd, stdout=log, stderr=subprocess.STDOUT, env=env, timeout=timeout).returncode
            except subprocess.TimeoutExpired:
                log.write(f"TIMEOUT after {timeout} s\n")
                return 124

    def adb_sh(self, serial, *args):
        result = subprocess.run([self.adb, "-s", serial, "shell", *args], capture_output=True, text=True, timeout=30)
        return result.stdout.strip()

    def battery(self, serial):
        dump = self.adb_sh(serial, "dumpsys", "battery")
        values = dict(re.findall(r"^\s*(level|temperature):\s*(\d+)", dump, re.M))
        current = self.adb_sh(serial, "cat", "/sys/class/power_supply/battery/current_now") or "0"
        return int(values.get("level", 0)), int(current) if current.lstrip("-").isdigit() else 0, int(values.get("temperature", 0))

    def take_lease(self, alias, serial):
        lease = self.leases / serial
        try:
            lease.mkdir(parents=True)
        except FileExistsError:
            holder = next((p.read_text()[:200] for p in lease.glob("*.json")), "unknown holder")
            raise CommandError(f"device {alias} is leased by another worker ({sanitize(holder, self.secrets())}); retry later") from None
        (lease / "lab-runner.json").write_text(json.dumps({"workstream": "lab-runner", "pid": os.getpid(), "run": self.run_id}))
        return lease

    def worktree(self, ref):
        path = self.repo / ".local/worktrees" / f"lab-run-{self.run_id}"
        git = ["git", "-C", str(self.repo)]
        if self.run(git + ["fetch", "-q", "origin", ref], self.repo, timeout=600) != 0:
            raise CommandError(f"cannot fetch ref `{ref}`")
        if self.run(git + ["worktree", "add", "-q", "--detach", str(path), "FETCH_HEAD"], self.repo, timeout=600) != 0:
            raise CommandError("cannot create the job worktree")
        (path / "work").symlink_to(self.repo / "work")
        (path / ".local").mkdir(exist_ok=True)
        (path / ".local/lab-venv").symlink_to(self.repo / ".local/lab-venv")
        return path

    def toolhost(self, checkout, toolhosts):
        """Build the phone toolhost from the checked-out commit with the owner's local builder (cached by commit)."""
        commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=checkout, capture_output=True, text=True).stdout.strip()
        out = toolhosts / commit
        if (out / "signed.apk").is_file() and (out / "result.json").is_file():
            return 0, "cached: " + toolhost_summary(out)
        builder = self.repo / self.config.get("toolhost_builder", "work/coordination/lab-runner-toolhost/build.py")
        if not builder.is_file():
            raise CommandError("the local toolhost builder is not installed yet; ask the orchestrator")
        shutil.rmtree(out, ignore_errors=True)
        out.mkdir(parents=True)
        code = self.run([sys.executable, str(builder), "--source", commit, "--out", str(out), "--package", TEST_PACKAGE], self.repo)
        return code, toolhost_summary(out) + "\n" + "\n".join(self.log.read_text(errors="replace").splitlines()[-40:])

    def status(self):
        free = shutil.disk_usage(self.repo).free / 2**30
        alias_of = {serial: alias for alias, serial in self.devices.items()}
        rows = [
            f"Host free space: {free:.0f} GiB",
            f"Leases held: {', '.join(sorted(alias_of.get(p.name, 'other') for p in self.leases.iterdir())) or 'none'}"
            if self.leases.is_dir()
            else "Leases held: none",
        ]
        for alias, serial in sorted(self.devices.items()):
            try:
                level, current, temp = self.battery(serial)
                rows.append(f"{alias}: battery {level} %, {temp / 10:.1f} C, current {current}; {battery_refusal(level, current, temp) or 'admitted'}")
            except Exception as error:  # an unreachable device is a status, not a failure
                rows.append(f"{alias}: unreachable ({type(error).__name__})")
        return "\n".join(rows)

    def execute(self, request):
        if request["job"] == "status":
            return 0, self.status()
        serial = None
        if request["device"]:
            serial = self.devices.get(request["device"])
            if not serial:
                raise CommandError(f"unknown device alias; configured: {', '.join(sorted(self.devices)) or 'none'}")
        checkout = self.worktree(request["ref"])
        toolhosts = self.repo / "work/coordination/lab-runner/toolhost"
        lease = None
        try:
            if serial:
                lease = self.take_lease(request["device"], serial)
                refusal = battery_refusal(*self.battery(serial))
                if refusal:
                    raise CommandError(f"device {request['device']} not admitted: {refusal}")
            py = str(checkout / ".local/lab-venv/bin/python")
            job, args = request["job"], request["args"]
            device_args = ["--device", serial] if serial else []
            if job == "toolhost":
                return self.toolhost(checkout, toolhosts)
            argv = {
                "host-tests": [py, "scripts/host-tests.py", *args],
                "preflight": ["./dev", "preflight", *args],
                "doctor": ["./dev", "doctor", *args],
                "dev": ["./dev", *args, *device_args],
                "script": [py, *args],
            }[job]
            extra = {"LAB_TOOLHOST_ROOT": str(toolhosts)}
            if serial:
                extra["LAB_DEVICE_SERIAL"] = serial
            code = self.run(argv, checkout, extra_env=extra)
            return code, None
        finally:
            if lease:  # only a device this job leased; a refused lease belongs to another worker's live run
                subprocess.run([self.adb, "-s", serial, "shell", "input", "keyevent", "KEYCODE_SLEEP"], capture_output=True, timeout=30)
                shutil.rmtree(lease, ignore_errors=True)
            self.run(["git", "-C", str(self.repo), "worktree", "remove", "--force", str(checkout)], self.repo, timeout=600)
            self.run([sys.executable, "scripts/prune-generated.py", "--apply"], self.repo, timeout=1800)


def toolhost_summary(out):
    result = json.loads((out / "result.json").read_text()) if (out / "result.json").is_file() else {}
    return f"success={result.get('success')} apk_sha256={result.get('apk_sha256') or result.get('tool_apk_sha256')} dir=$LAB_TOOLHOST_ROOT/{out.name}"


def main(env=os.environ):
    repo = env.get("LAB_REPO")
    if not repo:
        print("LAB_REPO is not set in the runner environment", file=sys.stderr)
        return 2
    owner = env.get("LAB_REPOSITORY_OWNER")
    if env.get("LAB_COMMENT_AUTHOR") != owner or env.get("LAB_AUTHOR_ASSOCIATION") != "OWNER":
        print("refused: only the repository owner may run lab jobs", file=sys.stderr)
        return 3
    runner = Runner(repo, dict(env))
    started = time.monotonic()
    try:
        request = parse_command(env.get("LAB_COMMENT_BODY", ""))
    except CommandError as error:
        runner.comment(f"**lab-runner refused:** {error}\n\n{USAGE}")
        return 1
    runner.react("eyes")
    try:
        code, summary = runner.execute(request)
    except CommandError as error:
        runner.comment(f"**lab-runner refused** `{request['job']}`: {error}")
        return 1
    tail = summary or "\n".join(runner.log.read_text(errors="replace").splitlines()[-TAIL_LINES:])
    tail = tail[-(COMMENT_LIMIT - 1000) :]
    verdict = "PASS" if code == 0 else f"FAIL (exit {code})"
    head = f"**lab-runner {verdict}** · `{request['job']} {shlex.join(request['args'])}` · ref `{request['ref']}`"
    head += f" · device `{request['device']}`" if request["device"] else ""
    head += f" · {time.monotonic() - started:.0f} s · run {runner.run_id}"
    runner.comment(f"{head}\n\n```\n{tail}\n```")
    runner.react("+1" if code == 0 else "-1")
    return code


if __name__ == "__main__":
    sys.exit(main())
