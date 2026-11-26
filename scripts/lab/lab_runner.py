"""Comment-driven lab runner: run a fixed menu of lab jobs for owner "/lab ..." comments.

The lab-runner workflow copies this file from origin/main and runs it standalone (stdlib only) on the
owner's self-hosted runner, so a branch can change what a job builds but never what the runner allows.
Each job gets its own worktree of the requested ref, an atomic orchestrator device lease when it uses a
device, and a sanitized result comment (public repository: no paths, serials, storage IDs or emails).
Raw output stays local under work/coordination/lab-runner/<run>/. See docs/LAB_RUNNER.md.
"""

import importlib.util
import json
import os
import re
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

# The workflow copies both files from the same pinned origin/main commit.
# Explicit sibling loading also works under python -I (no ambient PYTHONPATH).
_TRANSPORT_SPEC = importlib.util.spec_from_file_location("lab_adb_transport", Path(__file__).with_name("adb_transport.py"))
_TRANSPORT = importlib.util.module_from_spec(_TRANSPORT_SPEC)
_TRANSPORT_SPEC.loader.exec_module(_TRANSPORT)

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


def battery_refusal(level, current_now, temp_tenths, charge_override=False):
    """The user's battery rule: no run above 85 %, while charging at >= 80 %, or when the battery is warm.

    ``charge_override`` is the owner's explicit choice (``battery_charge_override`` in the ignored
    ``work/config/lab-runner.json``) to run plugged-in devices above the charge limit; the
    temperature rule always applies.
    """
    if not charge_override and level > 85:
        return f"battery at {level} % (> 85 %)"
    if not charge_override and level >= 80 and current_now > 0:
        return "battery is actually charging at >= 80 %"
    if temp_tenths > 350:
        return f"battery at {temp_tenths / 10:.1f} C (> 35 C)"
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
        self.charge_override = bool(self.config.get("battery_charge_override", False))
        self.adb = shutil.which("adb", path="/opt/homebrew/bin") or "adb"
        self.leases = self.repo / ".local/orchestrator/leases"
        self.resume_state = None
        self.reattached = False

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
        if self.charge_override:
            env["LAB_BATTERY_CHARGE_OVERRIDE"] = "1"  # child device tools honour the owner's choice
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
        try:
            readonly = args in (("dumpsys", "battery"), ("cat", "/sys/class/power_supply/battery/current_now"))
            return _TRANSPORT.AdbTransport(self.adb, serial).run("shell", *args, label="runner-observation", timeout=30, idempotent=readonly).decode().strip()
        except (_TRANSPORT.AdbError, UnicodeError):
            raise CommandError("device observation unavailable") from None

    def battery(self, serial):
        dump = self.adb_sh(serial, "dumpsys", "battery")
        values = dict(re.findall(r"^\s*(level|temperature):\s*(\d+)", dump, re.M))
        current = self.adb_sh(serial, "cat", "/sys/class/power_supply/battery/current_now")
        if set(values) != {"level", "temperature"} or not re.fullmatch(r"-?[0-9]+", current):
            raise CommandError("device battery observation incomplete")
        return int(values["level"]), int(current), int(values["temperature"])

    def take_lease(self, alias, serial, *, workstream="lab-runner"):
        lease = self.leases / serial
        try:
            lease.mkdir(parents=True)
        except FileExistsError:
            if self.resume_state is None:
                raise CommandError(f"device {alias} is leased; retry after its owner releases it") from None
            owner = json.loads((lease / "lab-runner.json").read_bytes())
            retained = json.loads((lease / "retain.json").read_bytes())
            state = json.loads(self.resume_state.read_bytes())
            if owner.get("workstream") != workstream or retained.get("state") != str(self.resume_state) or retained.get("job") != state.get("job"):
                raise CommandError("emission retained lease identity mismatch")
            try:
                os.kill(owner["pid"], 0)
            except ProcessLookupError:
                pass
            else:
                raise CommandError("emission previous runner is still alive")
            try:
                (lease / "resume-claim").mkdir()
            except FileExistsError:
                raise CommandError("emission lease already has a resume claimant") from None
            self.reattached = True
        (lease / "lab-runner.json").write_text(json.dumps({"workstream": workstream, "pid": os.getpid(), "run": self.run_id}))
        if self.reattached:
            (lease / "resume-claim").rmdir()
        return lease

    def require_grant(self, serial, workstream):
        grant = self.leases.parent / "devqueue" / (serial + ".granted")
        if not grant.is_file() or grant.read_text().strip() != workstream:
            raise CommandError("local packaging device grant required")

    def stop_unity_adb(self, checkout):
        if self.run([self.adb, "kill-server"], checkout, timeout=15, extra_env={"ANDROID_ADB_SERVER_PORT": "5038"}):
            raise CommandError("could not stop Unity ADB server")

    def admit_battery(self, serial, *, heavy=False):
        for sample in range(3):
            level, current, temperature = self.battery(serial)
            if heavy and level < 30:
                return f"battery at {level} % (< 30 % for phone producers)"
            refusal = battery_refusal(level, current, temperature, self.charge_override)
            if level > 85 or temperature > 350 or not refusal:
                return refusal
            if sample != 2:
                time.sleep(10)
        return refusal  # Three positive-current observations, ten seconds apart.

    def worktree(self, ref, *, local_ref=False):
        path = self.repo / ".local/worktrees" / f"lab-run-{self.run_id}"
        git = ["git", "-C", str(self.repo)]
        if local_ref:
            if not re.fullmatch(r"[0-9a-f]{40}", ref):
                raise CommandError("local device run requires a full commit hash")
        else:
            if self.run(git + ["fetch", "-q", "origin", ref], self.repo, timeout=600) != 0:
                raise CommandError(f"cannot fetch ref `{ref}`")
            ref = "FETCH_HEAD"
        if self.run(git + ["worktree", "add", "-q", "--detach", str(path), ref], self.repo, timeout=600) != 0:
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
                rows.append(
                    f"{alias}: battery {level} %, {temp / 10:.1f} C, current {current}; {battery_refusal(level, current, temp, self.charge_override) or 'admitted'}"
                )
            except Exception as error:  # an unreachable device is a status, not a failure
                rows.append(f"{alias}: unreachable ({type(error).__name__})")
        return "\n".join(rows)

    def execute(self, request, *, local_checkout=None, workstream=None, local_ref=False):
        if request["job"] == "status":
            return 0, self.status()
        serial = None
        if request["device"]:
            serial = self.devices.get(request["device"])
            if not serial:
                raise CommandError(f"unknown device alias; configured: {', '.join(sorted(self.devices)) or 'none'}")
        checkout = local_checkout or self.worktree(request["ref"], local_ref=local_ref)
        toolhosts = self.repo / "work/coordination/lab-runner/toolhost"
        lease = None
        try:
            if serial:
                if workstream:
                    self.require_grant(serial, workstream)
                    lease = self.take_lease(request["device"], serial, workstream=workstream)
                    self.stop_unity_adb(checkout)
                else:
                    lease = self.take_lease(request["device"], serial)
                heavy = request["job"] == "toolhost" or "--emission-request" in request["args"]
                refusal = None if self.reattached else self.admit_battery(serial, heavy=heavy)
                if refusal:
                    raise CommandError(f"device {request['device']} not admitted: {refusal}")
            py = str(checkout / ".local/lab-venv/bin/python")
            job, args = request["job"], request["args"]
            device_args = ["--device", serial] if serial else []
            if job == "toolhost":
                if "local_toolhost" in request:
                    from toolhost_build import execute

                    inputs, plan, output = request["local_toolhost"]
                    result = execute(inputs, plan, output, runner=self, serial=serial, lease=lease, transport_module=_TRANSPORT, package=TEST_PACKAGE)
                    return 0, result
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
                extra["LAB_RUNNER_LEASE"] = str(lease)
                extra["LAB_CANONICAL_ROOT"] = str(self.repo)
            code = self.run(argv, checkout, extra_env=extra)
            return code, None
        finally:
            if lease:  # only a device this job leased; a refused lease belongs to another worker's live run
                try:
                    _TRANSPORT.AdbTransport(self.adb, serial).run(
                        "shell",
                        "input",
                        "keyevent",
                        "KEYCODE_SLEEP",
                        label="runner-display-sleep",
                        timeout=30,
                        idempotent=True,
                    )
                except _TRANSPORT.AdbError:
                    with self.log.open("a") as log:
                        log.write("WARNING: device display sleep unverified\n")
                finally:
                    if not (lease / "retain.json").exists():
                        shutil.rmtree(lease, ignore_errors=True)
            if local_checkout is None:
                self.run(["git", "-C", str(self.repo), "worktree", "remove", "--force", str(checkout)], self.repo, timeout=600)
            self.run([sys.executable, "scripts/prune-generated.py", "--apply"], self.repo, timeout=1800)


def toolhost_summary(out):
    result = json.loads((out / "result.json").read_text()) if (out / "result.json").is_file() else {}
    return f"success={result.get('success')} apk_sha256={result.get('apk_sha256') or result.get('tool_apk_sha256')} dir=$LAB_TOOLHOST_ROOT/{out.name}"


def installer_signer_source(output):
    receipt = json.loads((output / "result.json").read_bytes())
    source = json.loads((output / "command.json").read_bytes())
    remote = source["retained_tool_key"]
    if (
        receipt.get("success") is not True
        or receipt.get("package") != TEST_PACKAGE
        or receipt.get("source_commit") != output.name
        or source.get("source_commit") != receipt.get("source_commit")
        or not re.fullmatch(r"[0-9a-f]{64}", receipt.get("signer_sha256") or "")
        or not re.fullmatch(r"/data/local/tmp/[A-Za-z0-9_-]+/owner-tool-key", remote)
    ):
        raise CommandError("installer-test signing backup source differs")
    return remote, receipt["signer_sha256"]


def retain_installer_signer(runner, checkout, device, workstream, output):
    """Copy only the existing installer-test signer while the granted Thor is leased."""
    remote, certificate = installer_signer_source(output)
    spec = importlib.util.spec_from_file_location("lab_installer_toolhost", Path(__file__).with_name("installer_toolhost.py"))
    fixture = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fixture)
    serial = runner.devices[device]
    runner.require_grant(serial, workstream)
    lease = runner.take_lease(device, serial, workstream=workstream)
    try:
        runner.stop_unity_adb(checkout)

        def fetch(name, stream):
            command = [runner.adb, "-s", serial, "exec-out", "cat", remote + "/" + name]
            if subprocess.run(command, stdout=stream, stderr=subprocess.DEVNULL, timeout=30).returncode:
                raise CommandError("installer-test signing backup transfer failed")

        fixture.backup_signing_key(runner.repo / "work" / fixture.KEY_DIR, Path(os.environ["JAVA_HOME"]) / "bin/java", certificate, fetch)
    finally:
        (lease / "lab-runner.json").unlink()
        lease.rmdir()


def local_packaging(path, *, dry_run=False, detach=False):
    request = json.loads(Path(path).read_bytes())
    repo = Path(request["repo"]).resolve()
    checkout = Path(request["checkout"]).resolve()
    done = Path(request["done_file"])
    workstream = request["workstream"]
    if not done.is_absolute() or done != done.resolve() or not done.is_relative_to(repo / "work") or done.exists():
        raise ValueError("packaging-new-absolute-work-done-file-required")
    runner = Runner(repo, {})
    result = {"success": False, "log": str(runner.log)}
    if not (dry_run or detach):

        def interrupt(number, frame):
            raise InterruptedError("packaging runner interrupted")

        for sig in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
            signal.signal(sig, interrupt)
    try:
        device = request["device"]
        operation = request.get("operation", "packaging")
        if operation not in ("packaging", "acquisition", "toolhost"):
            raise CommandError("unknown local packaging operation")
        build_toolhost = operation == "toolhost"
        retain_signer = request.get("backup_installer_key", False)
        if not isinstance(retain_signer, bool) or (retain_signer and not build_toolhost):
            raise CommandError("installer-test signing backup requires a Thor toolhost request")
        cached_signer = request.get("toolhost_source_commit") if build_toolhost else None
        if cached_signer is not None and (not retain_signer or not isinstance(cached_signer, str) or not re.fullmatch(r"[0-9a-f]{40}", cached_signer)):
            raise CommandError("installer-test signing backup requires a full cached source commit")
        if not re.fullmatch(r"[a-z0-9-]+", workstream) or device not in runner.devices or (build_toolhost and device != "thor"):
            raise CommandError("invalid local packaging workstream or configured device")
        common_dir = subprocess.check_output(["git", "-C", checkout, "rev-parse", "--path-format=absolute", "--git-common-dir"], text=True).strip()
        if Path(common_dir).resolve() != (repo / ".git").resolve():
            raise CommandError("packaging checkout must belong to the canonical repository")
        command = parse_command("/lab script device=" + device + " -- scripts/lab-alpha-packaging.py")
        if operation == "acquisition":
            command["args"].extend(["--acquisition-request", str(Path(path).resolve())])
        else:
            command["args"].extend(["--package-only", "--qualify-install-prompts"])
        toolhosts = repo / "work/coordination/lab-runner/toolhost"
        inputs = request.get("toolhost_inputs") if build_toolhost else None
        if inputs is not None:
            if retain_signer:
                raise CommandError("explicit toolhost stages use the retained signer and do not provide a signing backup")
            from toolhost_build import digest, read_plan, verify_apk

            plan = read_plan(inputs, checkout)
            stage, files, _, _, cache_key, commit = plan
            output = toolhosts / cache_key
        elif cached_signer is not None:
            output = toolhosts / cached_signer
        if dry_run or detach:
            if inputs is not None:
                code = 0  # The exact stage, checkout and host provider pins were read above.
            elif cached_signer is not None:
                installer_signer_source(output)
                code = 0
            elif build_toolhost:
                builder = repo / runner.config.get("toolhost_builder", "work/coordination/lab-runner-toolhost/build.py")
                code = runner.run([sys.executable, str(builder), "--help"], checkout)
            else:
                code = runner.run([sys.executable, *command["args"], "--dry-run"], checkout, extra_env={"LAB_TOOLHOST_ROOT": str(toolhosts)})
            if code:
                raise CommandError("packaging precheck failed; see private log")
            if dry_run:
                print("PASS alpha-packaging host precheck")
                return 0
            with runner.log.open("a") as log:
                subprocess.Popen(
                    [
                        "bash",
                        "-c",
                        'source "$1" && shift && exec "$@"',
                        "lab-packaging",
                        str(checkout / "scripts/env.sh"),
                        sys.executable,
                        str(Path(__file__).resolve()),
                        "--packaging-request",
                        str(Path(path).resolve()),
                    ],
                    cwd=checkout,
                    stdin=subprocess.DEVNULL,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    start_new_session=True,
                )
            print("WAITING done-file " + str(done), flush=True)
            return 0
        if inputs is not None:
            receipt_path = output / "result.json"
            apk = output / "signed.apk"
            receipt = json.loads(receipt_path.read_bytes()) if receipt_path.is_file() else {}
            identity = dict(source_commit=commit, package=TEST_PACKAGE, signer_sha256=inputs["signer_sha256"], cache_key=cache_key)
            if receipt.get("success") is True and apk.is_file() and digest(apk) == receipt.get("apk_sha256"):
                write_receipt = any(receipt.get(key) != value for key, value in identity.items())
                if write_receipt:
                    build = json.loads((output / "build-receipt.json").read_bytes())
                    verify_apk(apk, stage, files, build, inputs, TEST_PACKAGE)
                code = 0
                result["cached"] = True
            else:
                command.update(job="toolhost", local_toolhost=(inputs, plan, output))
                code, receipt = runner.execute(command, local_checkout=checkout, workstream=workstream)
                write_receipt = True
            if code == 0:
                receipt.update(identity)
            if write_receipt:
                with tempfile.TemporaryDirectory(dir=output) as directory:
                    temporary = Path(directory) / receipt_path.name
                    temporary.write_text(json.dumps(receipt, indent=2) + "\n")
                    temporary.replace(receipt_path)
            (output / ".prune-keep").touch()
            result["toolhost"] = toolhost_summary(output)
        elif cached_signer is not None:
            retain_installer_signer(runner, checkout, device, workstream, output)
            result["signing_key_backed_up"] = True
            code = 0
        elif build_toolhost:
            runner.require_grant(runner.devices[device], workstream)
            code, summary = runner.toolhost(checkout, toolhosts)
            if code == 0:
                commit = subprocess.check_output(["git", "-C", checkout, "rev-parse", "HEAD"], text=True).strip()
                output = toolhosts / commit
                receipt = json.loads((output / "result.json").read_bytes())
                if receipt.get("success") is not True or not (output / "signed.apk").is_file():
                    raise CommandError("toolhost builder did not produce a successful APK receipt")
                (output / ".prune-keep").touch()
                result["toolhost"] = summary.splitlines()[0]
                if retain_signer:
                    retain_installer_signer(runner, checkout, device, workstream, output)
                    result["signing_key_backed_up"] = True
        else:
            code, _ = runner.execute(command, local_checkout=checkout, workstream=workstream)
        result.update(success=code == 0, exitcode=code)
    except (KeyError, OSError, RuntimeError, ValueError, subprocess.SubprocessError) as error:
        result["error"] = str(error)
        if dry_run or detach:
            print(str(error) + ". Private log: " + str(runner.log), file=sys.stderr)
            return 1
    finally:
        if not (dry_run or detach):
            done.parent.mkdir(parents=True, exist_ok=True)
            temporary = done.with_suffix(done.suffix + ".tmp")
            temporary.write_text(json.dumps(result, indent=2) + "\n")
            temporary.replace(done)
            print("WAITING done-file " + str(done), flush=True)
    return int(not result["success"])


def local_emission(path, *, dry_run=False, resume=False, restage=False, workstream=None):
    """Private request entry point; same script/worktree/lease owner as /lab."""
    request = json.loads(Path(path).read_bytes())
    configuration = request["runner"]
    repo = Path(configuration["repo"]).resolve()
    done = Path(request["done_file"])
    if not done.is_absolute() or done != done.resolve() or not done.is_relative_to(repo / "work") or done.exists():
        raise ValueError("emission-new-absolute-work-done-file-required")
    if dry_run:
        spec = importlib.util.spec_from_file_location("lab_toolhost_emission", Path(__file__).with_name("toolhost_emission.py"))
        operation = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(operation)
        _, files = operation.load_request(path)
        print(json.dumps(dict(success=True, dry_run=True, files=len(files))))
        return 0
    result = dict(success=False)
    runner = Runner(repo, {})
    if resume or restage:
        runner.resume_state = done.parent / "device-state.json"

    def interrupt(number, frame):
        raise InterruptedError("emission-runner-interrupted")

    previous = {number: signal.signal(number, interrupt) for number in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP)}
    try:
        local_ref = configuration.get("local_ref", False)
        if local_ref and (local_ref is not True or not workstream):
            raise CommandError("local emission commit requires a dispatcher workstream")
        command = "/lab script " + shlex.join(
            [
                "ref=" + configuration["ref"],
                "device=" + configuration["device"],
                "--",
                "scripts/lab-installer-updates.py",
                "--emission-request",
                str(Path(path).resolve()),
            ]
        )
        if resume:
            command += " --resume-emission"
        if restage:
            command += " --resume-emission --restage-emission" if not resume else " --restage-emission"
        code, _ = runner.execute(parse_command(command), workstream=workstream, local_ref=local_ref)
        operation = done.with_suffix(".operation.json")
        if operation.exists():
            result.update(json.loads(operation.read_bytes()))
        result.update(success=code == 0 and result.get("success") is True, exitcode=code)
    except BaseException as error:
        result.update(success=False, error=str(error) or type(error).__name__)
    finally:
        done.parent.mkdir(parents=True, exist_ok=True)
        temporary = done.with_suffix(done.suffix + ".tmp")
        temporary.write_text(json.dumps(result, indent=2) + "\n")
        temporary.replace(done)
        for number, handler in previous.items():
            signal.signal(number, handler)
        print("WAITING done-file " + str(done), flush=True)
    return 0 if result["success"] else 1


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
    if sys.argv[1:2] == ["--packaging-request"]:
        import argparse

        parser = argparse.ArgumentParser(description="Run the local alpha packaging gate through the shared device runner")
        parser.add_argument("--packaging-request", required=True)
        mode = parser.add_mutually_exclusive_group()
        mode.add_argument("--dry-run", action="store_true")
        mode.add_argument("--detach", action="store_true")
        arguments = parser.parse_args()
        sys.exit(local_packaging(arguments.packaging_request, dry_run=arguments.dry_run, detach=arguments.detach))
    if sys.argv[1:2] == ["--emission-request"]:
        import argparse

        parser = argparse.ArgumentParser(description="Current shared device runner: pinned bundle emission or signed-code conversion")
        parser.add_argument("--emission-request", required=True)
        parser.add_argument("--workstream", help="Require this dispatcher grant before taking the device lease")
        mode = parser.add_mutually_exclusive_group()
        mode.add_argument("--dry-run", action="store_true")
        mode.add_argument("--resume-emission", action="store_true")
        mode.add_argument("--restage-emission", action="store_true", help="Replace confirmed-terminal owned staging with newly pinned producers/inputs")
        mode.add_argument("--refresh-emission-manifest", metavar="CHECKOUT", help="Host-only: repin repo producers from a clean committed checkout")
        arguments = parser.parse_args()
        if arguments.refresh_emission_manifest:
            from toolhost_emission import refresh_manifest

            print(json.dumps(refresh_manifest(arguments.emission_request, arguments.refresh_emission_manifest)))
            sys.exit(0)
        sys.exit(
            local_emission(
                arguments.emission_request,
                dry_run=arguments.dry_run,
                resume=arguments.resume_emission,
                restage=arguments.restage_emission,
                workstream=arguments.workstream,
            )
        )
    sys.exit(main())
