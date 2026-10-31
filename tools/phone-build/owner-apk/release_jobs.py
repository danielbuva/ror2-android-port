"""Dispatch signed public job recipes to the existing source-only phone producers.

A job executes an existing Python owner through the installed interpreter, never a
shell or downloaded native executable. Private outputs/intermediates stay in the
owner workspace. Incomplete producer cohorts fail rather than selecting replay.
"""

import hashlib
import importlib.util
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("release_job_updates", HERE / "updates.py")
UPDATES = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(UPDATES)

PRODUCERS = {
    "tools/phone-build/owner-code/run_android.py",
    "tools/phone-build/owner-code/produce.py",
    "tools/phone-build/owner-code/native.py",
    *{
        "tools/phone-build/accepted-output/" + name + ".py"
        for name in (
            "avatar_produce",
            "mesh_produce",
            "object_produce",
            "record_produce",
            "shader_produce",
            "texture_produce",
            "player_data",
            "sdk_package",
            "payload_shader_records",
        )
    },
}
TOKEN = re.compile(r"\$\{([^}]+)\}")


def validate_jobs(index, release, read_job):
    """Require every final entry and all transitive jobs in its signed closure."""
    for entry, row in index["entries"].items():
        if read_job(row["job"]).get("outputs", {}).get(entry) is None:
            raise ValueError("release entry is not produced by its declared job")
        seen = set()

        def visit(name, active):
            if name in active:
                raise ValueError("cyclic release producer dependency")
            if name in seen:
                return
            seen.add(name)
            job = read_job(name)
            if set(job) - {"request", "needs", "artifacts"} != {"schema", "script", "arguments", "outputs"} or job["schema"] != 1:
                raise ValueError("explicit source producer job schema required")
            if job["script"] not in PRODUCERS or name not in row["recipe_files"] or job["script"] not in row["producer_files"]:
                raise ValueError("existing source producer and complete signed job closure required")
            if not isinstance(job["arguments"], list) or not job["arguments"] or not all(isinstance(v, str) for v in job["arguments"]):
                raise ValueError("producer argument vector required; shell commands are forbidden")
            if not isinstance(job["outputs"], dict) or not isinstance(job.get("artifacts", {}), dict) or not (job["outputs"] or job.get("artifacts")):
                raise ValueError("explicit producer output/artifact map required")
            for output, path in job["outputs"].items():
                if output not in release["entries"]:
                    raise ValueError("producer output not selected in release")
                UPDATES.relative(path)
            for path in job.get("artifacts", {}).values():
                UPDATES.relative(path)
            needs = job.get("needs", [])
            if not isinstance(needs, list) or len(set(needs)) != len(needs):
                raise ValueError("unique producer dependencies required")
            for required in needs:
                visit(required, active | {name})

        visit(row["job"], set())


class Dispatcher:
    def __init__(self, repo, index, release, inputs, runtime, native, config, input_sha256, *, python=None, progress=None):
        self.repo, self.inputs, self.runtime = [Path(p).resolve(strict=True) for p in (repo, inputs, runtime)]
        installed_runtime = self.runtime
        self.native = Path(native).resolve(strict=True)
        self.index, self.release, self.config, self.input_sha256 = index, release, config, input_sha256
        self.python = python or [str(self.native / "libpythonhost.so"), str(self.native / "libpython3.14.so"), str(self.runtime / "python")]
        self.completed, self.running, self.descriptors = {}, set(), {}
        self.progress = progress or (lambda name, reused: None)
        self.jobs_root = UPDATES.within(self.inputs, "work/releases/jobs")
        self.jobs_root.mkdir(parents=True, exist_ok=True)
        self.validate()
        # run_android resolves producers through runtime/repo; point it at the
        # newly verified source, not the installer APK's older bundled checkout.
        self.runtime = Path(tempfile.mkdtemp(prefix="runtime-", dir=self.jobs_root))
        for child in installed_runtime.iterdir():
            if child.name not in {"repo", "tmp", "home"}:
                (self.runtime / child.name).symlink_to(child, target_is_directory=child.is_dir())
        (self.runtime / "repo").symlink_to(self.repo, target_is_directory=True)
        (self.runtime / "tmp").mkdir()
        (self.runtime / "home").mkdir()

    def descriptor(self, name):
        if name not in self.descriptors:
            if name not in self.index["files"]:
                raise ValueError("job is absent from verified public bundle")
            self.descriptors[name] = UPDATES.public().load_json(UPDATES.within(self.repo, name, exists=True).read_bytes())
        return self.descriptors[name]

    def validate(self):
        validate_jobs(self.index, self.release, self.descriptor)

    def closure(self, name):
        """Union all declared consumers: a shared job cannot reuse weaker pins."""
        files = set()
        for row in self.index["entries"].values():
            if name in row["recipe_files"]:
                files.update(row["recipe_files"])
                files.update(row["producer_files"])
        if not files:
            raise ValueError("job has no signed dependency closure")
        return {path: self.index["files"][path] for path in sorted(files)}

    def verify_sources(self, files):
        for name, expected in files.items():
            if UPDATES.RELEASE.digest(UPDATES.within(self.repo, name, exists=True)) != expected:
                raise ValueError("verified public source changed before/during production: " + name)

    def expand(self, value, job, output, request_path):
        if isinstance(value, dict):
            return {key: self.expand(item, job, output, request_path) for key, item in value.items()}
        if isinstance(value, list):
            return [self.expand(item, job, output, request_path) for item in value]
        if not isinstance(value, str):
            return value
        roots = {
            "inputs": self.inputs,
            "repo": self.repo,
            "runtime": self.runtime,
            "native": self.native,
            "output": output,
            "output_relative": output.relative_to(self.inputs),
            "output_work_relative": output.relative_to(self.inputs / "work"),
            "request": request_path,
        }

        def replace(match):
            key = match.group(1)
            if key in roots:
                return str(roots[key])
            if key.startswith(("input:", "input_relative:")):
                binding = self.config.get("bindings", {}).get(key.split(":", 1)[1])
                selected = UPDATES.within(self.inputs, binding, exists=True)
                return str(selected.relative_to(self.inputs) if key.startswith("input_relative:") else selected)
            if key.startswith(("job:", "job_relative:", "sha256:")):
                parts = key.split(":")
                if len(parts) != 3 or parts[1] not in job.get("needs", []):
                    raise ValueError("artifact must name a declared job dependency")
                prior = self.descriptor(parts[1])
                artifact = prior.get("artifacts", {}).get(parts[2])
                if artifact is None:
                    raise ValueError("unknown producer artifact")
                selected = UPDATES.within(self.completed[parts[1]], artifact, exists=True)
                if parts[0] == "sha256":
                    if not selected.is_file():
                        raise ValueError("receipt hash requires a regular artifact file")
                    return UPDATES.RELEASE.digest(selected)
                return str(selected.relative_to(self.inputs) if parts[0] == "job_relative" else selected)
            raise ValueError("unknown release job substitution: " + key)

        result = TOKEN.sub(replace, value)
        if "${" in result:
            raise ValueError("malformed release job substitution")
        return result

    @staticmethod
    def files_in(output, job):
        """Hash declared results, not the producers' temporary SDK/tool views.

        Existing native/managed owners legitimately create scratch symlinks.
        Declared files and prerequisite artifacts must remain canonical, regular
        private results; a scratch link is never followed or cached as output.
        """
        files = {}
        for name in {*job["outputs"].values(), *job.get("artifacts", {}).values()}:
            selected = UPDATES.within(output, name, exists=True)
            paths = [selected, *selected.rglob("*")] if selected.is_dir() else [selected]
            for path in sorted(paths):
                if path.is_symlink():
                    raise ValueError("producer declared a symbolic-link artifact")
                if path.is_file():
                    files[path.relative_to(output).as_posix()] = UPDATES.RELEASE.digest(path)
                elif not path.is_dir():
                    raise ValueError("producer declared a nonregular artifact")
        return files

    def execute(self, name):
        if name in self.completed:
            return self.completed[name]
        if name in self.running:
            raise ValueError("cyclic release producer dependency")
        self.running.add(name)
        try:
            job = self.descriptor(name)
            for needed in job.get("needs", []):
                self.execute(needed)
            files = self.closure(name)
            self.verify_sources(files)
            identity = hashlib.sha256(UPDATES.RELEASE.signed_bytes({"job": name, "files": files, "input_sha256": self.input_sha256})).hexdigest()
            receipt_path = self.jobs_root / (identity + ".json")
            if receipt_path.exists():
                receipt = UPDATES.public().load_json(receipt_path.read_bytes())
                try:
                    cached = UPDATES.within(self.jobs_root, receipt["directory"], exists=True)
                    reusable = self.files_in(cached, job) == receipt["files"]
                except FileNotFoundError:
                    reusable = False
                if reusable:
                    self.completed[name] = cached
                    self.progress(name, True)
                    return cached
            attempt = Path(tempfile.mkdtemp(prefix=identity[:16] + "-", dir=self.jobs_root))
            output = attempt / "output"
            request_path = self.inputs / (".release-job-" + attempt.name + ".json")
            if "request" in job:
                UPDATES.write_json(request_path, self.expand(job["request"], job, output, request_path))
            arguments = self.expand(job["arguments"], job, output, request_path)
            # No shell, executable download, command string, or private-code module.
            command = [*self.python, str(UPDATES.within(self.repo, job["script"], exists=True)), *arguments]
            with (attempt / "producer.log").open("xb") as log:
                inherited_lock = os.environ.get("ROR2_OWNER_UPDATE_LOCK_FD")
                # Preserve the updater lock in the producer if its Python parent
                # is interrupted. The outer phone runner supervises its family.
                lock_fds = (int(inherited_lock),) if inherited_lock is not None else ()
                process = subprocess.Popen(command, cwd=self.repo, stdout=log, stderr=subprocess.STDOUT, pass_fds=lock_fds)
                try:
                    while True:
                        try:
                            result = process.wait(timeout=0.5)
                            if result:
                                raise subprocess.CalledProcessError(result, command)
                            break
                        except subprocess.TimeoutExpired:
                            self.progress(name, None)  # Persist elapsed time, not invented sub-job progress.
                except BaseException:
                    process.kill()
                    process.wait()
                    raise
            if not output.is_dir() or output.is_symlink():
                raise ValueError("producer did not create its private output directory")
            for relative in job["outputs"].values():
                if not UPDATES.within(output, relative, exists=True).is_file():
                    raise ValueError("producer did not create a complete selected file")
            for relative in job.get("artifacts", {}).values():
                UPDATES.within(output, relative, exists=True)
            self.verify_sources(files)
            outputs = self.files_in(output, job)
            UPDATES.write_json(receipt_path, {"directory": output.relative_to(self.jobs_root).as_posix(), "files": outputs})
            self.completed[name] = output
            self.progress(name, False)
            return output
        finally:
            self.running.remove(name)

    def produce(self, name, dependencies, destination):
        row = self.index["entries"][name]
        actual = UPDATES.public().entry_dependencies(self.index, name)
        if actual != dependencies:
            raise ValueError("producer dependencies differ from signed release")
        root = self.execute(row["job"])
        source = UPDATES.within(root, self.descriptor(row["job"])["outputs"][name], exists=True)
        if not source.is_file():
            raise ValueError("source producer output is incomplete")
        shutil.copyfile(source, destination)
