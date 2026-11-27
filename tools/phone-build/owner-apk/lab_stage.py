"""Run an existing converter owner against pinned input already in the toolhost."""

import argparse
import importlib.util
import json
from pathlib import Path
import resource
import shutil
import subprocess
import sys
import time

SPEC = importlib.util.spec_from_file_location("phone_stage_release_jobs", Path(__file__).with_name("release_jobs.py"))
JOBS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(JOBS)
ACCEPTED_OUTPUT = "tools/phone-build/accepted-output/"
SCOREBOARD = ACCEPTED_OUTPUT + "whole_game_scoreboard.py"
PRODUCER_SUPPORT = {SCOREBOARD: tuple(ACCEPTED_OUTPUT + name for name in ("unity_bundle.py", "unity_write.py"))}
PRODUCERS = {name for name in JOBS.PRODUCERS if name.startswith(ACCEPTED_OUTPUT)} | PRODUCER_SUPPORT.keys()
UPDATES = JOBS.UPDATES


def load_stage(path):
    stage = json.loads(Path(path).read_bytes())
    if set(stage) - {"scoreboard"} != {"producer", "input_root", "input_pins", "arguments", "artifacts"}:
        raise ValueError("explicit converter stage descriptor required")
    if stage["producer"] not in PRODUCERS:
        raise ValueError("stage must select an existing converter producer")
    UPDATES.relative(stage["input_root"])
    if not isinstance(stage["input_pins"], dict) or not isinstance(stage["artifacts"], dict) or not stage["input_pins"] or not stage["artifacts"]:
        raise ValueError("stage requires input pins and expected artifacts")
    for name, expected in stage["input_pins"].items():
        UPDATES.relative(name)
        if not isinstance(expected, str) or len(expected) != 64 or any(char not in "0123456789abcdef" for char in expected):
            raise ValueError("stage input must have a SHA-256 pin")
    for name in stage["artifacts"].values():
        UPDATES.relative(name)
    if "scoreboard" in stage:
        UPDATES.relative(stage["scoreboard"])
    if not isinstance(stage["arguments"], list):
        raise ValueError("stage requires a producer argument vector")
    for argument in stage["arguments"]:
        if isinstance(argument, str):
            continue
        if not isinstance(argument, dict) or len(argument) != 1 or not argument.keys() <= {"inputs", "output", "repo", "native", "runtime"}:
            raise ValueError("stage path argument requires one known root")
        for name in argument.values():
            if name != ".":
                UPDATES.relative(name)
    return stage


def run(stage, repo, owner_input, output, native, runtime, python, receipt):
    started = time.monotonic()
    free_before = shutil.disk_usage(output.parent).free
    result = dict(success=False, producer=stage["producer"])
    try:
        inputs = UPDATES.within(owner_input, stage["input_root"], exists=True)
        for name, expected in stage["input_pins"].items():
            if UPDATES.RELEASE.digest(UPDATES.within(inputs, name, exists=True)) != expected:
                raise ValueError("staged input hash differs: " + name)
        roots = dict(inputs=inputs, output=output, repo=repo, native=native, runtime=runtime)
        arguments = []
        for argument in stage["arguments"]:
            if isinstance(argument, str):
                arguments.append(argument)
            else:
                ((root, name),) = argument.items()
                arguments.append(str(roots[root] if name == "." else UPDATES.within(roots[root], name)))
        producer = UPDATES.within(repo, stage["producer"], exists=True)
        if producer.name == "bundle_preload.py" and "--inputs" in arguments:
            arguments.extend(("--workers", "1"))
        log = output.parent / "producer.log"
        with log.open("wb") as stream:
            cwd = inputs if stage["producer"] == SCOREBOARD else repo
            observed = subprocess.run([*python, str(producer), *arguments], cwd=cwd, stdout=stream, stderr=subprocess.STDOUT)
        if observed.returncode:
            with log.open("rb") as stream:
                stream.seek(max(0, stream.seek(0, 2) - 4096))
                lines = stream.read().decode(errors="replace").splitlines()
            raise RuntimeError(f"producer exit {observed.returncode}" + (": " + lines[-1][:500] if lines else ""))
        artifacts = {}
        for key, name in stage["artifacts"].items():
            path = UPDATES.within(output, name, exists=True)
            artifacts[key] = dict(sha256=UPDATES.RELEASE.digest(path), bytes=path.stat().st_size)
        if "scoreboard" in stage:
            path = UPDATES.within(output, stage["scoreboard"], exists=True)
            UPDATES.write_json(receipt.parent / "scoreboard.json", json.loads(path.read_bytes()))
        result.update(success=True, artifacts=artifacts)
    except (OSError, RuntimeError, ValueError) as error:
        result["first_failure"] = str(error)
    finally:
        result.update(
            elapsed_seconds=time.monotonic() - started,
            child_peak_rss_bytes=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss * (1 if sys.platform == "darwin" else 1024),
            free_bytes_before=free_before,
            free_bytes_after=shutil.disk_usage(output.parent).free,
        )
        UPDATES.write_json(receipt, result)
    return int(not result["success"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("stage", "repo", "owner_input", "output", "native", "runtime", "receipt"):
        parser.add_argument(name, type=Path)
    parser.add_argument("python", nargs=3)
    args = vars(parser.parse_args())
    args["stage"] = load_stage(args["stage"])
    return run(**args)


if __name__ == "__main__":
    raise SystemExit(main())
