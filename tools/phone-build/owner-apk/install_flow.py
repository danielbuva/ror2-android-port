"""Durable UI checkpoints over the signed release's existing producer graph.

Checkpoints are progress, not proof: producers revalidate their own cached output
receipts on every launch. Only APK/signing outputs with recorded byte hashes may
be skipped. No installer consent or installation success is synthesized here.
"""

import hashlib
import json
import os
from pathlib import Path
import tempfile
import time
import subprocess

STAGES = ("admission", "staging", "assembly", "textures", "native", "apk", "signing", "install")
PRODUCTION = STAGES[2:5]


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        raise ValueError("checkpoint cannot be a symlink")
    fd, temporary = tempfile.mkstemp(prefix=".checkpoint-", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as stream:
            json.dump(value, stream, sort_keys=True, allow_nan=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        # Durability includes the directory entry, not just the temporary file.
        fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    finally:
        Path(temporary).unlink(missing_ok=True)


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def validate_plan(plan, index, descriptor):
    """The public bundle validator owns field/path validation; verify the DAG."""
    stages = plan.get("stages", [])
    if [row.get("id") for row in stages] != list(STAGES):
        raise ValueError("signed install plan must contain the eight ordered stages")
    selected = {}
    for position, row in enumerate(stages):
        jobs = row.get("jobs")
        if not isinstance(jobs, list) or len(set(jobs)) != len(jobs):
            raise ValueError("unique stage producer jobs required")
        if jobs and row["id"] not in PRODUCTION:
            raise ValueError("producer jobs belong only to assembly, textures or native")
        for name in jobs:
            if name in selected or name not in index["files"]:
                raise ValueError("stage job must occur exactly once in the verified bundle")
            selected[name] = position
    needed = set()

    def visit(name, active):
        if name in active:
            raise ValueError("cyclic release producer dependency")
        if name not in selected:
            raise ValueError("release producer missing from signed stage plan")
        if name in needed:
            return
        needed.add(name)
        for dependency in descriptor(name).get("needs", []):
            if dependency not in selected or selected[dependency] > selected[name]:
                raise ValueError("producer dependency follows its consumer stage")
            visit(dependency, active | {name})

    for row in index["entries"].values():
        visit(row["job"], set())
    if needed != set(selected):
        raise ValueError("stage plan contains jobs outside the release dependency closure")
    return {name: stages[position]["id"] for name, position in selected.items()}


class Pipeline:
    def __init__(self, inputs, release, input_sha256, plan, *, emit=lambda value: None, clock=time.monotonic):
        self.inputs = Path(inputs).resolve()
        self.path = self.inputs / "install-checkpoint.json"
        self.clock, self.emit = clock, emit
        self.active_since = None
        identity = {"release": release, "input_sha256": input_sha256, "plan": plan}
        self.identity = hashlib.sha256(json.dumps(identity, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        self.state = {
            "schema": 1,
            "id": self.identity,
            "status": "running",
            "current_stage": None,
            "first_failure": None,
            "elapsed_seconds": 0.0,
            "stages": [
                {
                    "id": row["id"],
                    "label": row["title"],
                    "status": "pending",
                    "completed": 0,
                    "total": len(row["jobs"]) if row["id"] in PRODUCTION else 1,
                    "elapsed_seconds": 0.0,
                }
                for row in plan["stages"]
            ],
        }
        if self.path.exists():
            if self.path.is_symlink():
                raise ValueError("checkpoint cannot be a symlink")
            previous = json.loads(self.path.read_text())
            if previous.get("schema") == 1 and previous.get("id") == self.identity:
                self.state = previous
                for row in self.state["stages"]:
                    if row["status"] == "running":
                        row["status"] = "interrupted"
                if self.state["status"] in {"running", "paused"}:
                    self.state["status"] = "interrupted"
        self.persist()

    def row(self, stage):
        return next(row for row in self.state["stages"] if row["id"] == stage)

    def tick(self):
        if self.active_since is not None:
            now = self.clock()
            seconds = max(0, now - self.active_since)
            self.row(self.state["current_stage"])["elapsed_seconds"] += seconds
            self.state["elapsed_seconds"] += seconds
            self.active_since = now

    def persist(self):
        self.tick()
        self.state["updated_at"] = time.time()
        write_json(self.path, self.state)
        self.emit(self.snapshot())

    def snapshot(self):
        value = json.loads(json.dumps(self.state))
        telemetry = self.inputs / "thermal-state.json"
        if telemetry.is_file() and not telemetry.is_symlink():
            try:
                value["telemetry"] = json.loads(telemetry.read_text())
            except (ValueError, OSError):
                pass  # The independent thermal supervisor still refuses sensor loss.
        return value

    def begin(self, stage, total=None):
        self.tick()
        if self.state["status"] in {"failed", "cancelled", "interrupted"}:
            # A retry has a new first failure; an earlier admission failure must
            # not be hidden behind the previous attempt's later failing stage.
            self.state["first_failure"] = None
        row = self.row(stage)
        row.update(status="running", completed=0)
        if total is not None:
            row["total"] = total
        self.state.update(status="running", current_stage=stage)
        self.active_since = self.clock()
        self.persist()

    def progress(self, completed, total=None):
        row = self.row(self.state["current_stage"])
        if total is not None:
            row["total"] = total
        row["completed"] = min(max(0, completed), row["total"])
        self.persist()

    def complete(self, stage):
        self.tick()
        self.active_since = None
        row = self.row(stage)
        row.update(status="complete" if row["total"] else "not_required", completed=row["total"])
        if self.state.get("first_failure") and self.state["first_failure"]["stage"] == stage:
            self.state["first_failure"] = None
        self.persist()

    def fail(self, error):
        self.tick()
        self.active_since = None
        stage = self.state["current_stage"] or "admission"
        reason = (str(error) or type(error).__name__)[:240]
        if isinstance(error, subprocess.CalledProcessError):
            reason = "Source producer exited with code " + str(error.returncode) + "; private producer log retained."
        self.row(stage)["status"] = "failed"
        if self.state["first_failure"] is None:
            self.state["first_failure"] = {"stage": stage, "reason": reason}
        self.state["status"] = "failed"
        self.persist()

    def perform(self, stage, action):
        self.begin(stage)
        try:
            result = action()
            self.complete(stage)
            return result
        except Exception as error:
            self.fail(error)
            raise

    def await_install(self):
        self.active_since = None
        self.state.update(status="awaiting_install", current_stage="install", first_failure=None)
        self.row("install")["status"] = "awaiting_consent"
        self.persist()

    def artifacts(self, stage, paths):
        rows = {}
        for path in paths:
            path = Path(path)
            if path.is_symlink() or path.resolve(strict=True) != path or not path.is_relative_to(self.inputs):
                raise ValueError("checkpoint artifact escapes private input root")
            rows[path.relative_to(self.inputs).as_posix()] = digest(path)
        self.row(stage)["artifacts"] = rows
        self.persist()

    def reusable(self, stage):
        row = self.row(stage)
        artifacts = row.get("artifacts")
        if not artifacts:
            return False
        for name, expected in artifacts.items():
            path = self.inputs / name
            try:
                if path.resolve(strict=True) != path or not path.is_relative_to(self.inputs) or digest(path) != expected:
                    return False
            except OSError:
                return False
        return True
