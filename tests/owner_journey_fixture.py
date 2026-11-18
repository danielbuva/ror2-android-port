"""Reusable synthetic owner journey; crypto, packaging and Android are test boundaries.

The real pipeline, producer dispatcher, issued ledger and receipt checks run unchanged.
No game data, real keys, APKs or installation are created.
"""

from contextlib import contextmanager
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
from unittest.mock import Mock, patch
from tests.test_phone_install_flow import F, U, J


@contextmanager
def owner_journey():
    installed_version = 0
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary).resolve()
        inputs, runtime, native, repo = [root / name for name in ("inputs", "runtime", "native", "repo")]
        for directory in (inputs, runtime, native, repo):
            directory.mkdir()
        script = "tools/phone-build/accepted-output/record_produce.py"
        jobs = ("recipe/assembly.json", "recipe/textures.json")
        descriptors = {
            jobs[0]: {
                "schema": 1,
                "script": script,
                "arguments": ["${output}", "${inputs}/attempt-count.txt"],
                "outputs": {},
                "artifacts": {"intermediate": "result"},
            },
            jobs[1]: {
                "schema": 1,
                "script": script,
                "arguments": ["${output}", "${inputs}/attempt-count.txt"],
                "outputs": {"payload/synthetic.txt": "result"},
                "needs": [jobs[0]],
            },
        }
        manifest = {
            "schema": 1,
            "game_version": "synthetic-version",
            "files": [{"path": "original.txt", "bytes": 8, "sha256": __import__("hashlib").sha256(b"authored").hexdigest()}],
        }
        contents = {name: json.dumps(value).encode() for name, value in descriptors.items()}
        contents["recipe/inputs.json"] = json.dumps(manifest).encode()
        contents[script] = (
            b"import pathlib,sys\np=pathlib.Path(sys.argv[1]);p.mkdir();(p/'result').write_text('synthetic result');f=pathlib.Path(sys.argv[2]);f.write_text((f.read_text() if f.exists() else '')+'attempt\\n')\n"
        )
        for name, value in contents.items():
            path = repo / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(value)
        selected = {
            "schema": 1,
            "required_inputs": "recipe/inputs.json",
            "workspace_bytes": 0,
            "configuration": {"bindings": {"originals": "."}},
            "stages": [],
        }
        for stage in F.STAGES:
            selected["stages"].append(
                {"id": stage, "title": stage.title(), "jobs": [jobs[0]] if stage == "assembly" else [jobs[1]] if stage == "textures" else []}
            )
        index = {
            "schema": 1,
            "files": {name: F.digest(repo / name) for name in contents},
            "entries": {"payload/synthetic.txt": {"job": jobs[1], "recipe_files": list(jobs), "producer_files": [script]}},
            "install_plan": selected,
        }
        release = {
            "version": "synthetic-1",
            "version_code": 2,
            "application_id": "dev.ror2lab.alpha",
            "data_schema": {"writes": 1, "reads": [1]},
            "minimum_installer_version": 3,
            "bundle_sha256": "a" * 64,
            "entries": {"payload/synthetic.txt": U.public().entry_dependencies(index, "payload/synthetic.txt")},
        }
        candidate = {"release": release, "envelope": {}, "bundle": {"url": "https://github.com/example/synthetic/releases/download/one/public-tools.zip"}}
        request = inputs / "update-request.json"
        U.write_json(
            request,
            {
                "action": "install-prepare",
                "application_id": release["application_id"],
                "installed_version": installed_version,
                "installed_release_version": installed_version,
                "installer_version": 3,
                "installer_package": "dev.ror2lab.phonebuildhostfixture",
                "installer_signer_sha256": "c" * 64,
            },
        )
        U.write_json(
            runtime / "release-trust.json",
            {"repository": "example/synthetic", "application_id": release["application_id"], "keys": {"synthetic": "mocked signature boundary"}},
        )
        module = U.module

        def dispatch(*args, **kwargs):
            return J.Dispatcher(*args, **kwargs, python=[sys.executable])

        def modules(name, path):
            return SimpleNamespace(Dispatcher=dispatch) if name == "owner_update_jobs" else module(name, path)

        events = []
        original_write = U.write_json

        def record(path, value):
            original_write(path, value)
            if path.name == "update-state.json":
                events.append(copy.deepcopy(value))

        def assemble(release, outputs, *args, flow, issued, binding, **kwargs):
            data = Path(outputs["payload/synthetic.txt"]).read_bytes()
            assert data == b"synthetic result"
            output = inputs / "work/releases" / ("authored-stream-" + str(issued) + ".bin")
            flow.perform("apk", lambda: output.write_bytes(data))

            def sign():
                digest = hashlib.sha256(data).hexdigest()
                # Signer identity matches the Android PackageInfo authored test double.
                signer = hashlib.sha256(b"same-key").hexdigest()
                ready = dict(
                    apk=str(output),
                    sha256=digest,
                    bytes=len(data),
                    application_id=release["application_id"],
                    version_code=issued,
                    release=copy.deepcopy(release),
                    signer_sha256=signer,
                    payload_sha256=digest,
                    **binding,
                )
                U.ALPHA.bind(inputs / "work/releases", issued, apk_sha256=digest, payload_sha256=digest, signer_sha256=signer)
                return ready

            return flow.perform("signing", sign)

        def run(action, installed=None):
            context = json.loads(request.read_text())
            context["action"] = action
            if installed:
                context.update(installed_version=installed["version_code"], installed_release_version=installed["release"]["version_code"])
            original_write(request, context)
            U.run(request, runtime, native, transport=Mock())
            return json.loads((inputs / "update-state.json").read_text())

        is_file = Path.is_file

        def keys(path):
            return True if path in {inputs / "signing/owner/owner.p12", inputs / "signing/owner/password"} else is_file(path)

        with (
            patch.object(U, "latest", return_value=candidate),
            patch.object(U, "acquire", return_value=(repo, index)),
            patch.object(U.public(), "verify_envelope", side_effect=lambda *args: candidate["release"]),
            patch.object(U, "module", side_effect=modules),
            patch.object(U, "assemble_sign", side_effect=assemble),
            patch.object(U, "toolchain_identity", return_value="d" * 64),
            patch.object(U, "write_json", side_effect=record),
            patch.object(U.shutil, "disk_usage", return_value=SimpleNamespace(free=10 * 1024**3)),
            patch.object(Path, "is_file", keys),
        ):
            yield SimpleNamespace(
                root=root, inputs=inputs, runtime=runtime, native=native, repo=repo, release=release, candidate=candidate, index=index, events=events, run=run
            )
