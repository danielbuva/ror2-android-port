"""Authored fake-server/update contracts, no game input, APK, key or device.

Cryptography is mocked only at verify_signature; RFC RSA verification is tested
independently in test_public_release. These tests do not claim signing/install.
"""

import base64
import copy
import fcntl
import hashlib
import http.server
import importlib.util
import io
import json
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
import urllib.parse
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "tools/phone-build/owner-apk"


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


U = load("tested_owner_updates", PATH / "updates.py")
J = load("tested_release_jobs", PATH / "release_jobs.py")
P = U.public()
SCRIPT = "tools/phone-build/accepted-output/record_produce.py"
JOB = "recipe/authored-release-job.json"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def encoded(value):
    return json.dumps(value, sort_keys=True).encode()


def fixture(script=None):
    script = script or b"import pathlib,sys\np=pathlib.Path(sys.argv[1]);p.mkdir();(p/'complete').write_text('authored output')\n"
    job = {"schema": 1, "script": SCRIPT, "arguments": ["${output}"], "outputs": {"payload/authored": "complete"}}
    contents = {JOB: encoded(job), SCRIPT: script}
    return archive_fixture(contents, {"payload/authored": {"recipe_files": [JOB], "producer_files": [SCRIPT], "job": JOB}})


def archive_fixture(contents, entries):
    index = {"schema": 1, "files": {name: sha(data) for name, data in contents.items()}, "entries": entries}
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, data in contents.items():
            archive.writestr(name, data)
        archive.writestr("bundle-index.json", encoded(index))
    bundle = buffer.getvalue()
    release = {
        "version": "authored-2",
        "version_code": 2,
        "application_id": "dev.ror2lab.alpha",
        "minimum_installer_version": 1,
        "bundle_sha256": sha(bundle),
        "entries": {name: P.entry_dependencies(index, name) for name in entries},
    }
    return release, index, bundle


class FakeGitHub:
    """HTTP loopback only in tests; production URLs still pass GitHub validation."""

    def __init__(self, release, bundle):
        signature = {"algorithm": "SHA256withRSA", "key_id": "authored", "value": base64.b64encode(b"mocked-crypto-boundary").decode()}
        self.paths = {"/release.json": encoded(release), "/release.sig": encoded(signature), "/public-tools.zip": bundle}
        self.metadata = {
            "draft": False,
            "prerelease": False,
            "tag_name": "owner-v2",
            "assets": [
                {
                    "name": name,
                    "size": len(self.paths["/" + name]),
                    "browser_download_url": "https://github.com/example/owner/releases/download/owner-v2/" + name,
                }
                for name in ("release.json", "release.sig", "public-tools.zip")
            ],
        }
        self.paths["/latest"] = encoded(self.metadata)
        self.requests = []
        owner = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                owner.requests.append(self.path)
                data = owner.paths[self.path]
                self.send_response(200)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def log_message(self, *args):
                pass

        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

        class Transport(U.GitHubTransport):
            def open(self, url):
                self.allowed(url)
                path = "/" + urllib.parse.urlsplit(url).path.rsplit("/", 1)[-1]
                return urllib.request.urlopen("http://127.0.0.1:" + str(owner.server.server_port) + path, timeout=5)

        self.transport = Transport("example/owner")

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *args):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()


class UpdateTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.inputs, self.runtime, self.native = [self.root / name for name in ("inputs", "runtime", "native")]
        for path in (self.inputs, self.runtime, self.native):
            path.mkdir()
        self.request = {"action": "release-check", "application_id": "dev.ror2lab.alpha", "installed_version": 1, "installer_version": 1}
        U.write_json(self.inputs / "update-request.json", self.request)
        U.write_json(
            self.runtime / "release-trust.json",
            {"repository": "example/owner", "application_id": "dev.ror2lab.alpha", "keys": {"authored": "public key mocked only at RSA boundary"}},
        )
        self.release, self.index, self.bundle = fixture()
        message = U.RELEASE.signed_bytes(self.release)

        def signature(actual, signature, key):
            if actual != message or signature != b"mocked-crypto-boundary":
                raise ValueError("release signature invalid")

        self.verifier = patch.object(P, "verify_signature", side_effect=signature)
        self.verifier.start()
        self.addCleanup(self.verifier.stop)
        self.addCleanup(self.temporary.cleanup)

    def run_check(self, server):
        U.run(self.inputs / "update-request.json", self.runtime, self.native, transport=server.transport)
        return P.load_json((self.inputs / "update-state.json").read_bytes())

    def test_detached_fake_server_check_and_no_download_until_build_consent(self):
        with FakeGitHub(self.release, self.bundle) as server:
            state = self.run_check(server)
            self.assertEqual(state["state"], "UPDATE_AVAILABLE")
            self.assertEqual(state["changed_entries"], ["payload/authored"])
            self.assertNotIn("/public-tools.zip", server.requests)
            self.assertEqual(set(server.requests), {"/latest", "/release.json", "/release.sig"})
            self.assertFalse((self.inputs / "installed-release.json").exists())
            self.request["installed_version"] = 2
            U.write_json(self.inputs / "update-request.json", self.request)
            self.assertEqual(self.run_check(server)["state"], "UP_TO_DATE")

    def test_signature_failure_never_downloads_or_executes_tools(self):
        with FakeGitHub(self.release, self.bundle) as server:
            tampered = dict(self.release, version="tampered")
            server.paths["/release.json"] = encoded(tampered)
            with self.assertRaisesRegex(ValueError, "signature"):
                self.run_check(server)
            self.assertNotIn("/public-tools.zip", server.requests)
            self.assertEqual(P.load_json((self.inputs / "update-state.json").read_bytes())["state"], "ERROR")
            self.assertFalse((self.inputs / "release-candidate.json").exists())

    def test_context_refuses_rollback_package_and_installer_upgrade(self):
        for field, value in (("installed_version", 3), ("application_id", "other.package"), ("installer_version", 0)):
            request = dict(self.request, **{field: value})
            with self.subTest(field=field), self.assertRaises(ValueError):
                U.verify_context(self.release, request)

    def test_installed_manifest_diff_reports_changed_removed_and_unknown_receipt(self):
        old = copy.deepcopy(self.release)
        old["version_code"] = 1
        old["entries"]["payload/removed"] = dict(old["entries"]["payload/authored"])
        U.write_json(self.inputs / "installed-release.json", {"application_id": old["application_id"], "version_code": 1, "release": old})
        result = U.installed_changes(self.release, self.request, self.inputs)
        self.assertEqual(result["changed_entries"], [])
        self.assertEqual(result["removed_entries"], ["payload/removed"])
        self.assertTrue(result["installed_manifest_known"])
        self.request["installed_version"] = 0
        self.assertFalse(U.installed_changes(self.release, self.request, self.inputs)["installed_manifest_known"])

    def test_process_lock_refuses_duplicate_without_overwriting_running_state(self):
        U.write_json(self.inputs / "update-state.json", {"state": "BUILDING"})
        with (self.inputs / ".release-update.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with self.assertRaisesRegex(ValueError, "already running"):
                U.run(self.inputs / "update-request.json", self.runtime, self.native)
        self.assertEqual(P.load_json((self.inputs / "update-state.json").read_bytes())["state"], "BUILDING")

    def test_unprovisioned_trust_never_contacts_server(self):
        U.write_json(self.runtime / "release-trust.json", {"repository": "example/owner", "application_id": "dev.ror2lab.alpha", "keys": {}})
        with FakeGitHub(self.release, self.bundle) as server:
            with self.assertRaisesRegex(ValueError, "not provisioned"):
                self.run_check(server)
            self.assertEqual(server.requests, [])

    def test_bundle_download_hash_failure_and_interruption_leave_no_extracted_tools(self):
        with FakeGitHub(self.release, self.bundle) as server:
            candidate = U.latest(server.transport, {"authored": "fixture public key"})
            server.paths["/public-tools.zip"] = b"incorrect tools"
            with self.assertRaisesRegex(ValueError, "size/hash"):
                U.acquire(candidate, self.root / "downloads", server.transport, lambda *args: None)
            self.assertEqual(list((self.root / "downloads").iterdir()), [])
            with patch.object(server.transport, "open", side_effect=OSError("connection interrupted")):
                with self.assertRaisesRegex(OSError, "interrupted"):
                    U.acquire(candidate, self.root / "downloads", server.transport, lambda *args: None)
            self.assertEqual(list((self.root / "downloads").iterdir()), [])

    def test_url_policy_rejects_offsite_credentials_downgrade_and_foreign_repo(self):
        transport = U.GitHubTransport("example/owner")
        for url in ("http://github.com/x", "https://other.invalid/x", "https://user:password" + chr(64) + "github.com/x", "https://github.com:444/x"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                transport.allowed(url)
        with self.assertRaises(ValueError):
            transport.asset_url("https://github.com/another/repo/releases/download/x/release.json", "release.json")

    def test_safe_extraction_and_rejection_before_exposing_any_files(self):
        archive = self.root / "tools.zip"
        archive.write_bytes(self.bundle)
        self.assertEqual(U.extract_bundle(archive, self.root / "verified", self.release), self.index)
        self.assertEqual((self.root / "verified" / SCRIPT).read_bytes(), zipfile.ZipFile(archive).read(SCRIPT))
        for kind in ("traversal", "duplicate", "symlink", "extra", "hash"):
            buffer = io.BytesIO()
            with zipfile.ZipFile(io.BytesIO(self.bundle)) as original, zipfile.ZipFile(buffer, "w") as bad:
                for item in original.infolist():
                    bad.writestr(item, b"corrupt" if kind == "hash" and item.filename == SCRIPT else original.read(item))
                if kind == "traversal":
                    bad.writestr("../outside", b"bad")
                elif kind == "duplicate":
                    with __import__("warnings").catch_warnings():
                        __import__("warnings").simplefilter("ignore", UserWarning)
                        bad.writestr(JOB, b"bad")
                elif kind == "symlink":
                    link = zipfile.ZipInfo("link")
                    link.external_attr = (stat.S_IFLNK | 0o777) << 16
                    bad.writestr(link, "../outside")
                elif kind == "extra":
                    bad.writestr("unindexed.py", b"bad")
            archive.write_bytes(buffer.getvalue())
            release = dict(self.release, bundle_sha256=sha(buffer.getvalue()))
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                U.extract_bundle(archive, self.root / ("bad-" + kind), release)
            self.assertFalse((self.root / ("bad-" + kind)).exists())
        self.assertFalse((self.root / "outside").exists())

    def test_incremental_dispatch_executes_source_once_reuses_and_recovers_corruption(self):
        archive = self.root / "tools.zip"
        archive.write_bytes(self.bundle)
        repo = self.root / "verified"
        U.extract_bundle(archive, repo, self.release)
        dispatcher = J.Dispatcher(repo, self.index, self.release, self.inputs, self.runtime, self.native, {}, "c" * 64, python=[sys.executable])
        context = {key: self.request[key] for key in ("application_id", "installed_version", "installer_version")}
        options = dict(**context, input_sha256="c" * 64, root=self.inputs / "cache", produce=dispatcher.produce)
        first = U.RELEASE.rebuild(self.release, **options)
        self.assertEqual(first["rebuilt"], ["payload/authored"])
        self.assertEqual(Path(first["outputs"]["payload/authored"]).read_text(), "authored output")
        self.assertEqual(U.RELEASE.rebuild(self.release, **options)["rebuilt"], [])
        Path(first["outputs"]["payload/authored"]).write_text("corrupted cache")
        self.assertEqual(U.changed_entries(self.release, self.inputs / "cache", "c" * 64), ["payload/authored"])
        # Complete job artifacts are independently rehashed and may safely refill cache.
        self.assertEqual(U.RELEASE.rebuild(self.release, **options)["rebuilt"], ["payload/authored"])
        self.assertEqual(Path(first["outputs"]["payload/authored"]).read_text(), "authored output")
        self.assertEqual((dispatcher.runtime / "repo").resolve(), repo)

    def test_producer_refusal_keeps_existing_output_and_installed_receipt(self):
        archive = self.root / "tools.zip"
        release, index, bundle = fixture(b"raise RuntimeError('authored failure')\n")
        archive.write_bytes(bundle)
        repo = self.root / "verified"
        U.extract_bundle(archive, repo, release)
        dispatcher = J.Dispatcher(repo, index, release, self.inputs, self.runtime, self.native, {}, "c" * 64, python=[sys.executable])
        cached = self.inputs / "cache/payload/authored"
        cached.parent.mkdir(parents=True)
        cached.write_text("previous good")
        installed = self.inputs / "installed-release.json"
        installed.write_text("previous installed receipt")
        with self.assertRaises(__import__("subprocess").CalledProcessError):
            U.RELEASE.rebuild(
                release,
                installer_version=1,
                application_id=release["application_id"],
                installed_version=1,
                input_sha256="c" * 64,
                root=self.inputs / "cache",
                produce=dispatcher.produce,
            )
        self.assertEqual(cached.read_text(), "previous good")
        self.assertEqual(installed.read_text(), "previous installed receipt")

    def test_mutable_inventory_pins_are_explicitly_refused_not_silently_skipped(self):
        for name in ("work/config/local.json", "work/inventory/files.json"):
            U.write_json(self.inputs / "input-hashes.json", {name: "f" * 64})
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, "immutable originals/tools"):
                U.input_identity(self.inputs, {})

    def test_missing_owner_key_refuses_before_downloading_or_signing(self):
        (self.inputs / "original.txt").write_text("authored original")
        U.write_json(self.inputs / "input-hashes.json", {"original.txt": U.RELEASE.digest(self.inputs / "original.txt")})
        U.write_json(self.inputs / "update-config.json", {"manifest": "manifest.json", "key_directory": "keys"})
        self.request["action"] = "release-build"
        U.write_json(self.inputs / "update-request.json", self.request)
        with FakeGitHub(self.release, self.bundle) as server:
            with self.assertRaisesRegex(ValueError, "key lost"):
                self.run_check(server)
            self.assertNotIn("/public-tools.zip", server.requests)
        self.assertFalse((self.inputs / "keys").exists())
        self.assertFalse((self.inputs / "owner-apk-ready.json").exists())

    def test_declared_results_allow_private_scratch_links_but_never_linked_outputs(self):
        output = self.root / "job-output"
        output.mkdir()
        (output / "complete").write_text("authored complete file")
        (output / "sdk-view").symlink_to(self.runtime, target_is_directory=True)
        job = {"outputs": {"payload/authored": "complete"}, "artifacts": {}}
        self.assertEqual(J.Dispatcher.files_in(output, job), {"complete": sha(b"authored complete file")})
        (output / "complete").unlink()
        (output / "complete").symlink_to(self.inputs / "update-request.json")
        with self.assertRaisesRegex(ValueError, "symlink"):
            J.Dispatcher.files_in(output, job)

    def test_job_graph_rejects_cycle_missing_closure_and_unknown_command(self):
        job = {"schema": 1, "script": SCRIPT, "arguments": ["${output}"], "outputs": {"payload/authored": "complete"}}
        for kind in ("cycle", "closure", "command"):
            changed = copy.deepcopy(job)
            if kind == "cycle":
                changed["needs"] = [JOB]
            elif kind == "closure":
                changed["needs"] = ["recipe/missing-job.json"]
            else:
                changed["script"] = "/bin/sh"
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                J.validate_jobs(self.index, self.release, lambda name: changed if name == JOB else job)

    def test_orphaned_producer_retains_process_lock_until_it_exits(self):
        code = b"import pathlib,sys,time\np=pathlib.Path(sys.argv[1]);p.mkdir();i=pathlib.Path(sys.argv[2]);(i/'started').write_text('ready');deadline=time.monotonic()+10\nwhile not (i/'continue').exists() and time.monotonic()<deadline:time.sleep(.01)\n(p/'complete').write_text('authored result')\n"
        job = {"schema": 1, "script": SCRIPT, "arguments": ["${output}", "${inputs}"], "outputs": {"payload/authored": "complete"}}
        release, index, bundle = archive_fixture({SCRIPT: code, JOB: encoded(job)}, self.index["entries"])
        archive = self.root / "lock-tools.zip"
        archive.write_bytes(bundle)
        repo = self.root / "lock-tools"
        U.extract_bundle(archive, repo, release)
        U.write_json(self.root / "lock-release.json", release)
        parent_code = f"""import importlib.util,json,pathlib,sys

def load(name,path):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
u=load('lock_updates',{str(PATH / "updates.py")!r})
j=load('lock_jobs',{str(PATH / "release_jobs.py")!r})
r=json.loads(pathlib.Path({str(self.root / "lock-release.json")!r}).read_text())
i=json.loads(pathlib.Path({str(repo / "bundle-index.json")!r}).read_text())
def execute(*args,**kwargs):
 d=j.Dispatcher({str(repo)!r},i,r,{str(self.inputs)!r},{str(self.runtime)!r},{str(self.native)!r},{{}},'c'*64,python=[sys.executable]);d.produce('payload/authored',r['entries']['payload/authored'],pathlib.Path({str(self.root / "lock-output")!r}))
u._run=execute
u.run({str(self.inputs / "update-request.json")!r},{str(self.runtime)!r},{str(self.native)!r})
"""
        parent = subprocess.Popen([sys.executable, "-c", parent_code], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            deadline = time.monotonic() + 5
            while not (self.inputs / "started").exists() and time.monotonic() < deadline and parent.poll() is None:
                time.sleep(0.01)
            self.assertTrue((self.inputs / "started").exists())
            parent.terminate()
            parent.wait(timeout=5)
            with (self.inputs / ".release-update.lock").open("a") as lock:
                with self.assertRaises(BlockingIOError):
                    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                (self.inputs / "continue").touch()
                deadline = time.monotonic() + 5
                while True:
                    try:
                        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                        break
                    except BlockingIOError:
                        if time.monotonic() >= deadline:
                            self.fail("exited producer did not release update lock")
                        time.sleep(0.01)
        finally:
            (self.inputs / "continue").touch()
            if parent.poll() is None:
                parent.kill()
                parent.wait(timeout=5)
            parent.communicate(timeout=5)

    def test_prerequisite_artifact_and_digest_dispatch_reuse_on_second_process(self):
        first = "recipe/first-job.json"
        second = "recipe/second-job.json"
        # Only authored Python doubles; actual mesh source dispatch is separate.
        script = b"import hashlib,pathlib,sys\np=pathlib.Path(sys.argv[1]);p.mkdir()\nif len(sys.argv)>2:\n s=pathlib.Path(sys.argv[2]);assert hashlib.sha256(s.read_bytes()).hexdigest()==sys.argv[3];(p/'complete').write_bytes(s.read_bytes()+b' consumed')\nelse:(p/'receipt').write_text('authored prerequisite')\n"
        one = {"schema": 1, "script": SCRIPT, "arguments": ["${output}"], "outputs": {}, "artifacts": {"receipt": "receipt"}}
        two = {
            "schema": 1,
            "script": SCRIPT,
            "arguments": ["${output}", "${job:" + first + ":receipt}", "${sha256:" + first + ":receipt}"],
            "outputs": {"payload/authored": "complete"},
            "needs": [first],
        }
        release, index, bundle = archive_fixture(
            {first: encoded(one), second: encoded(two), SCRIPT: script},
            {"payload/authored": {"recipe_files": [first, second], "producer_files": [SCRIPT], "job": second}},
        )
        archive = self.root / "prerequisites.zip"
        archive.write_bytes(bundle)
        repo = self.root / "prerequisites"
        U.extract_bundle(archive, repo, release)
        arguments = (repo, index, release, self.inputs, self.runtime, self.native, {}, "c" * 64)
        dispatcher = J.Dispatcher(*arguments, python=[sys.executable])
        dispatcher.produce("payload/authored", release["entries"]["payload/authored"], self.root / "first")
        self.assertEqual((self.root / "first").read_text(), "authored prerequisite consumed")
        second_dispatcher = J.Dispatcher(*arguments, python=[sys.executable])
        with patch.object(J.subprocess, "run", side_effect=AssertionError("unchanged jobs must be reused")):
            second_dispatcher.produce("payload/authored", release["entries"]["payload/authored"], self.root / "second")
        self.assertEqual((self.root / "second").read_bytes(), (self.root / "first").read_bytes())
        self.assertEqual(second_dispatcher.completed[first], dispatcher.completed[first])
        (dispatcher.completed[first] / "receipt").unlink()
        recovered = J.Dispatcher(*arguments, python=[sys.executable])
        recovered.produce("payload/authored", release["entries"]["payload/authored"], self.root / "recovered")
        self.assertNotEqual(recovered.completed[first], dispatcher.completed[first])
        self.assertEqual((self.root / "recovered").read_bytes(), (self.root / "first").read_bytes())

    def test_two_entries_only_changed_recipe_rebuilds_and_removed_entry_not_selected(self):
        contents = {SCRIPT: b"import pathlib,sys\np=pathlib.Path(sys.argv[1]);p.mkdir();(p/'complete').write_text(sys.argv[2])\n"}
        entries = {}
        for name in ("one", "two"):
            path = "recipe/" + name + ".json"
            contents[path] = encoded({"schema": 1, "script": SCRIPT, "arguments": ["${output}", name], "outputs": {"payload/" + name: "complete"}})
            entries["payload/" + name] = {"recipe_files": [path], "producer_files": [SCRIPT], "job": path}
        options = dict(
            installer_version=1, application_id=self.release["application_id"], installed_version=1, input_sha256="c" * 64, root=self.inputs / "cache"
        )
        for revision in range(3):
            if revision == 1:
                job = P.load_json(contents["recipe/two.json"])
                job["arguments"][-1] = "two updated"
                contents["recipe/two.json"] = encoded(job)
            if revision == 2:
                del entries["payload/one"]
            release, index, bundle = archive_fixture(contents, entries)
            archive = self.root / ("revision" + str(revision) + ".zip")
            archive.write_bytes(bundle)
            repo = self.root / ("revision" + str(revision))
            U.extract_bundle(archive, repo, release)
            dispatcher = J.Dispatcher(repo, index, release, self.inputs, self.runtime, self.native, {}, "c" * 64, python=[sys.executable])
            result = U.RELEASE.rebuild(release, produce=dispatcher.produce, **options)
            self.assertEqual(result["rebuilt"], [["payload/one", "payload/two"], ["payload/two"], []][revision])
        self.assertEqual(set(result["outputs"]), {"payload/two"})
        self.assertTrue((self.inputs / "cache/payload/one").exists())  # Retained, never selected by directory scan.
        self.assertEqual((self.inputs / "cache/payload/two").read_text(), "two updated")

    def test_real_mesh_owner_runs_through_dispatcher_on_authored_fixture(self):
        mesh = load("update_authored_mesh_fixture", ROOT / "tests/test_phone_mesh_producer.py")
        body, schema, _ = mesh.authored_mesh()
        pc = self.inputs / "pc"
        pc.mkdir()
        source = pc / "authored.bundle"
        source.write_bytes(mesh.bundle([("CAB-authored", mesh.serialized(body, schema), 4)]))
        profile = {
            "input_id": mesh.P.INPUT_ID,
            "bundles": [
                {
                    "path": source.name,
                    "sha256": U.RELEASE.digest(source),
                    "members": [
                        {
                            "name": "CAB-authored",
                            "meshes": [
                                {
                                    "path_id": -123,
                                    "sha256": sha(body),
                                    "outputs": [
                                        {
                                            "bundle": "authored-target",
                                            "member": "CAB-target",
                                            "path_id": 789,
                                            "sha256": sha(body),
                                            "bytes": len(body),
                                            "ops": {},
                                        }
                                    ],
                                }
                            ],
                        }
                    ],
                }
            ],
            "excluded": [],
        }
        profile_path = "recipe/authored-mesh-profile.json"
        script = "tools/phone-build/accepted-output/mesh_produce.py"
        job = {
            "schema": 1,
            "script": script,
            "arguments": [
                "--profile",
                "${repo}/" + profile_path,
                "--profile-sha256",
                sha(encoded(profile)),
                "--pc",
                "${input:originals}",
                "--output",
                "${output}",
            ],
            "outputs": {"payload/authored-record-fixture": "objects.bin"},
        }
        producers = ["tools/phone-build/accepted-output/" + name for name in ("mesh_produce.py", "unity_mesh.py", "unity_bundle.py")]
        contents = {name: (ROOT / name).read_bytes() for name in producers}
        contents.update({JOB: encoded(job), profile_path: encoded(profile)})
        entries = {"payload/authored-record-fixture": {"recipe_files": [JOB, profile_path], "producer_files": producers, "job": JOB}}
        release, index, bundle = archive_fixture(contents, entries)
        archive = self.root / "real-producer.zip"
        archive.write_bytes(bundle)
        repo = self.root / "real-producer"
        U.extract_bundle(archive, repo, release)
        dispatcher = J.Dispatcher(
            repo, index, release, self.inputs, self.runtime, self.native, {"bindings": {"originals": "pc"}}, "d" * 64, python=[sys.executable]
        )
        output = self.root / "private-output"
        dispatcher.produce("payload/authored-record-fixture", release["entries"]["payload/authored-record-fixture"], output)
        self.assertEqual(output.read_bytes(), body)
        self.assertEqual(U.RELEASE.digest(source), profile["bundles"][0]["sha256"])


if __name__ == "__main__":
    unittest.main()
