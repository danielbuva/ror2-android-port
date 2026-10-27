"""Current: isolated normal code-build and separate owned in-place installation.

Run only through /lab script. Build requires a new named lane and the exact
committed source. Install requires the runner's selected-device lease and a
hash-bound successful build receipt. Raw owner/subprocess output stays local.
No fast-build splice, full-build fallback, payload sync, reset or uninstall.
Installation hashes only receipt-bound payload members before and after -r.
"""

import argparse
import contextlib
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

import common
from session_memory_batch import _receipt_path, _runner_context


@contextlib.contextmanager
def private_output(log):
    """Capture Python and inherited child-process stdout/stderr, not just print."""
    sys.stdout.flush()
    sys.stderr.flush()
    saved = (os.dup(1), os.dup(2))
    try:
        os.dup2(log.fileno(), 1)
        os.dup2(log.fileno(), 2)
        with contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
            yield
    finally:
        log.flush()
        for target, original in zip((1, 2), saved):
            os.dup2(original, target)
            os.close(original)


def require_hash(value):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
        raise ValueError("An exact SHA-256 is required")
    return value


def require_source(expected):
    if not isinstance(expected, str) or not re.fullmatch(r"[0-9a-f]{40}", expected):
        raise ValueError("An exact source commit is required")
    result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=common.ROOT, capture_output=True, text=True, check=True)
    if result.stdout.strip() != expected:
        raise RuntimeError("Selected source commit differs")


def payload_map(value):
    if not isinstance(value, dict) or not value:
        raise ValueError("A nonempty payload manifest is required")
    if any(not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9_.-]+", name) or name in {".", ".."} for name in value):
        raise ValueError("Unsafe payload member name")
    for digest in value.values():
        require_hash(digest)
    return value


def local_file(value):
    path = Path(value)
    if not path.is_absolute() or path != path.resolve() or not path.is_relative_to(common.WORK.resolve()) or not path.is_file():
        raise ValueError("Artifact must be a regular file within canonical work")
    return path


def verify_artifact(artifact, source):
    if artifact.get("success") is not True or type(artifact.get("errors")) is not int or artifact["errors"] != 0:
        raise RuntimeError("Build lacks explicit success and zero errors")
    if (artifact.get("source") or {}).get("commit") != source or "iteration" in artifact:
        raise RuntimeError("Build is not the requested normal source-bound artifact")
    apk = local_file(artifact["apk"])
    if common.sha(apk) != require_hash(artifact.get("apk_sha256")):
        raise RuntimeError("Candidate APK bytes differ")
    return apk, payload_map(artifact.get("payload"))


def read_candidate(path, digest, source, lane):
    raw = _receipt_path(path, existing=True).read_bytes()
    if hashlib.sha256(raw).hexdigest() != require_hash(digest):
        raise RuntimeError("Candidate receipt bytes differ")
    receipt = json.loads(raw)
    if receipt.get("success") is not True or receipt.get("mode") != "build" or receipt.get("source_commit") != source or receipt.get("lane") != lane:
        raise RuntimeError("Candidate receipt identity differs")
    artifact = receipt["artifact"]
    apk, payload = verify_artifact(artifact, source)
    if common.digest(payload) != receipt.get("payload_sha256"):
        raise RuntimeError("Candidate payload binding differs")
    return receipt, apk, payload


def verify_live_payload(device, expected, sync, evidence):
    """Read only the approved manifest, using Device.sync's root/hash semantics.

    read_receipt(runtime.json) owns path grammar and fresh storage-backing
    validation. Do not replace it with an unchecked receipt or invoke sync:
    sync creates directories and repairs mismatches, which this gate forbids.
    """
    runtime = device.read_receipt("runtime.json")
    root = runtime["persistentDataPath"]
    evidence.update(runtime_path=root, files=[])
    if root != sync.get("runtime_path"):
        raise RuntimeError("Validated runtime root differs from synced cohort")
    for name, digest in sorted(expected.items()):
        remote = root + "/payload/" + name
        raw = device.sh("sha256sum", remote, check=False)
        evidence["files"].append({"name": name, "sha256sum": raw})
        fields = raw.split()
        if len(fields) != 2 or fields[1] != remote or fields[0] != digest:
            raise RuntimeError("Live payload member hash is unavailable or differs")
    evidence.update(verified=True, file_count=len(expected), payload_sha256=common.digest(expected))


def run(mode, *, lane, expected_source_commit, receipt, candidate_receipt=None, expected_candidate_receipt_sha256=None, expected_current_apk_sha256=None):
    public = dict(success=False, mode=mode, phase="arguments")
    private = dict(mode=mode, lane=lane)
    path = None
    log_created = False
    try:
        if mode not in {"build", "install"} or not re.fullmatch(r"[a-z][a-z0-9-]{0,31}", lane or "") or lane == "canonical":
            raise ValueError("Use build/install and a named lane")
        path = _receipt_path(receipt)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.with_suffix(".log").open("x") as log:
            log_created = True
            with private_output(log):
                try:
                    public["phase"] = "source-identity"
                    require_source(expected_source_commit)
                    public["source_commit"] = expected_source_commit
                    if mode == "build":
                        import build_lanes as lanes

                        public["phase"] = "lane-create"
                        # Existing owner enforces 100 GiB and canonical cloning mutex.
                        facts = lanes.create(lane, root=common.ROOT)
                        private["lane_facts"] = facts
                        frozen = payload_map(common.read(Path(facts["checkout"]) / "work/whole-catalog-code-base.json")["payload"])
                        for phase, arguments in (
                            ("lane-editor-open", ["editor", "--target", "lab", "--action", "open"]),
                            ("lane-preflight", ["preflight", "--host-only"]),
                            ("normal-code-build", ["prototype", "--action", "whole-catalog-code-build"]),
                        ):
                            public["phase"] = phase
                            if lanes.dispatch(lane, arguments, root=common.ROOT) != 0:
                                raise RuntimeError("Lane owner failed")
                        public["phase"] = "published-artifact"
                        artifact = common.read(lanes.location(lane, common.ROOT) / "latest-build.json")
                        _, payload = verify_artifact(artifact, expected_source_commit)
                        if payload != frozen:
                            raise RuntimeError("Normal code-only build changed frozen payload")
                        require_source(expected_source_commit)
                        private["artifact"] = artifact
                        public.update(apk_sha256=artifact["apk_sha256"], payload_sha256=common.digest(payload), payload_file_count=len(payload))
                    else:
                        public.update(actual_device_payload_verified=False, payload_before_verified=False, payload_after_verified=False)
                        public["phase"] = "candidate-receipt"
                        candidate, apk, payload = read_candidate(candidate_receipt, expected_candidate_receipt_sha256, expected_source_commit, lane)
                        private["candidate_receipt_sha256"] = expected_candidate_receipt_sha256
                        public["phase"] = "runner-device-lease"
                        serial, _, _ = _runner_context(os.environ)
                        from device_context import command_selectors, set_command_selector
                        import alpha_stability_batch as owner

                        previous = command_selectors()
                        current = require_hash(expected_current_apk_sha256)
                        terminal_expected = current
                        admitted = False
                        try:
                            set_command_selector(serial, previous[1])
                            public["phase"] = "current-installed-identity"
                            device = owner._device(serial)
                            private["initial_readback"] = owner._idle_readback(device, current)
                            admitted = True
                            old = device.owned()
                            old_apk = local_file(old["apk"])
                            if common.sha(old_apk) != current:
                                raise RuntimeError("Current receipt APK bytes differ")
                            public["phase"] = "payload-cohort"
                            old_build = common.read(local_file(str(old_apk.parent / "result.json")))
                            if old_build.get("apk_sha256") != current or payload_map(old_build.get("payload")) != payload:
                                raise RuntimeError("Candidate differs from the current APK payload cohort")
                            sync = device.read_receipt("sync.json")
                            synced = {entry["name"]: entry["sha256"] for entry in sync["files"]}
                            runtime_payload = {name: value for name, value in payload.items() if Path(name).suffix != ".manifest"}
                            if not runtime_payload or len(synced) != len(sync["files"]) or synced != runtime_payload:
                                raise RuntimeError("Recorded selected-device payload cohort differs")
                            public["recorded_payload_cohort_matches"] = True
                            public["phase"] = "payload-before-readback"
                            private["payload_before"] = {}
                            verify_live_payload(device, runtime_payload, sync, private["payload_before"])
                            public["payload_before_verified"] = True
                            public["phase"] = "owned-in-place-install"
                            # ./dev selects the pinned SDK; Device.install owns -r,
                            # signature refusal, capacity, placement and receipts.
                            result = subprocess.run([str(common.ROOT / "dev"), "install", "--device", serial, "--apk", str(apk)], cwd=common.ROOT, check=False)
                            if result.returncode != 0:
                                raise RuntimeError("Owned in-place installation failed")
                            terminal_expected = candidate["artifact"]["apk_sha256"]
                            public.update(apk_sha256=terminal_expected, previous_apk_sha256=current)
                            public["phase"] = "payload-after-readback"
                            private["payload_after"] = {}
                            verify_live_payload(device, runtime_payload, sync, private["payload_after"])
                            public.update(
                                actual_device_payload_verified=True,
                                payload_after_verified=True,
                                runtime_payload_file_count=len(runtime_payload),
                                runtime_payload_sha256=common.digest(runtime_payload),
                                payload_sha256=common.digest(payload),
                                payload_file_count=len(payload),
                            )
                        finally:
                            try:
                                if admitted:
                                    prior_phase = public["phase"]
                                    public["phase"] = "terminal-readback"
                                    private["terminal_readback"] = owner._terminal_readback(serial, terminal_expected)
                                    public["terminal_idle_verified"] = True
                                    public["phase"] = prior_phase
                            finally:
                                set_command_selector(*previous)
                    public.update(success=True, phase="complete")
                except BaseException as error:
                    private["error"] = str(error)
    except BaseException as error:
        private["error"] = str(error)
    finally:
        if path is not None and log_created:
            private.update(public)
            common.write(path, private)
            public["report_sha256"] = common.sha(path)
    return public


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("build", "install"))
    parser.add_argument("--lane", required=True)
    parser.add_argument("--expected-source-commit", required=True)
    parser.add_argument("--receipt", required=True)
    parser.add_argument("--candidate-receipt")
    parser.add_argument("--expected-candidate-receipt-sha256")
    parser.add_argument("--expected-current-apk-sha256")
    args = parser.parse_args(argv)
    try:
        result = run(**vars(args))
    except BaseException:
        result = dict(success=False, phase="local-evidence-write")
    print(json.dumps(result, sort_keys=True))
    return 0 if result["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
