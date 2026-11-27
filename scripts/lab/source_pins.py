"""Check and refresh public recipe pins without opening any local game inputs."""

import argparse
import ast
from collections import Counter, defaultdict
from contextlib import ExitStack
from dataclasses import dataclass
from hashlib import sha256
import json
import os
from pathlib import Path
import posixpath
import re
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[2]
REPO_PREFIXES = ("recipe/", "scripts/", "tools/", "environment/", "smoke/", "android/")
# These manifests describe a historical checkout or serialized output ledger.
HISTORICAL = {"recipe/owner-j850-code.json", "recipe/owner-player-registry.json", "recipe/inherited-state.json"}
AUDIO_RECIPE = "recipe/original-audio-owner-sources.json"
AUDIO_SOURCE = "tools/unity/support/audio/"
PYTHON_BINDINGS = {
    "scripts/lab/original_game_audio_produce.py": {
        "OWNER_SOURCE_HASHES": AUDIO_SOURCE,
        "OWNER_ANCESTOR_MANIFEST_SHA256": AUDIO_RECIPE,
    },
    "scripts/lab/native_view_camera_build_hook.py": {"HASHES": {"r4_manifest_sha256": AUDIO_RECIPE}},
    "scripts/lab/shader_translucent.py": {"EXPECTED_HELPERS": "scripts/lab/"},
}
PATH_MAPS = {
    "source_files": "",
    "tool_sources": "",
    "public_profile_source_hashes": "",
    "owner_source_hashes": AUDIO_SOURCE,
    "authored_helpers": "scripts/lab/",
}
DIGEST = re.compile(r"[0-9a-f]{64}")
# Supplier selectors consumed by release_graph.suppliers. Player texture
# selectors are the only profile_sha256 fields with that same meaning.
SELECTORS = (b"record", b"source_profile_sha256", b"provider_profile_sha256", b"shader_record", b"profile_sha256")
SELECTOR_KEYS = tuple(b'"' + key + b'"' for key in SELECTORS)
SELECTOR = re.compile(rb'"(' + b"|".join(SELECTORS) + rb')"\s*:\s*"([0-9a-f]{64})"')
EXPLICIT = (
    b"recipe/",
    b"scripts/",
    b"tools/",
    b"environment/",
    b"smoke/",
    b"android/",
    b'.json"',
    b'"source_paths"',
    b'"owner_source_hashes"',
    b'"obj_import"',
    b'"graphics_template_sha256"',
    b'"generator_sha256"',
    b'"authored_helpers"',
)
JSON_TOKEN = re.compile(rb'"(?:[^"\\]|\\.)*"|[^\s{}\[\],:]+|[{}\[\],:]')


def git(root, *args):
    return subprocess.check_output(["git", "-C", str(root), *args])


def tracked(root, revision=None):
    args = ("ls-tree", "-rz", revision) if revision else ("ls-files", "--stage", "-z")
    files = {}
    for row in git(root, *args).split(b"\0"):
        if not row:
            continue
        details, path = row.split(b"\t", 1)
        mode, kind, oid = details.decode().split()
        if revision:
            if kind != "blob":
                continue
        else:
            oid, stage = kind, oid
            if stage != "0":
                raise ValueError(f"resolve the unmerged path {os.fsdecode(path)} before checking pins")
        if mode in ("100644", "100755"):
            files[os.fsdecode(path)] = oid
    return files


class Blobs:
    def __init__(self, root, stack):
        self.process = stack.enter_context(subprocess.Popen(["git", "-C", str(root), "cat-file", "--batch"], stdin=subprocess.PIPE, stdout=subprocess.PIPE))

    def read(self, oid):
        self.process.stdin.write(oid.encode() + b"\n")
        self.process.stdin.flush()
        fields = self.process.stdout.readline().split()
        if len(fields) != 3 or fields[1] != b"blob":
            raise ValueError(f"cannot read tracked blob {oid}")
        size = int(fields[2])
        source = self.process.stdout.read(size)
        if len(source) != size or self.process.stdout.read(1) != b"\n":
            raise ValueError(f"incomplete tracked blob {oid}")
        return source


def safe_path(root, name):
    path = root / name
    if path.resolve() != path or not path.is_file():
        raise ValueError(f"tracked source is missing or symlinked: {name}")
    return path


class Snapshot:
    def __init__(self, root, revision, blobs):
        self.root = root
        self.files = tracked(root, revision)
        self.blobs = blobs if revision else None

    def read(self, name):
        if self.blobs:
            return self.blobs.read(self.files[name])
        return safe_path(self.root, name).read_bytes()


@dataclass(frozen=True)
class Pin:
    source: str
    current: str
    location: tuple
    size: int | None = None
    alternatives: tuple[str, ...] = ()

    @property
    def name(self):
        return "/".join(map(str, self.location))


def is_hash(value):
    return isinstance(value, str) and DIGEST.fullmatch(value)


def repo_path(value, document, files, *, prefix="", relative=False):
    if not isinstance(value, str):
        return None
    value = value.removeprefix("${repo}/").removeprefix("repo/")
    if prefix:
        value = posixpath.normpath(prefix + value)
    if value in files or value.startswith(REPO_PREFIXES):
        return value
    # Some recipe consumers resolve a bare profile filename beside themselves.
    if relative and "/" not in value and value.endswith(".json"):
        candidate = posixpath.join(posixpath.dirname(document), value)
        if candidate in files:
            return candidate
    return None


def json_pins(value, document, files, loc=()):
    """Discover whole-file pins from their path declarations and known schemas."""
    if isinstance(value, list):
        for i, row in enumerate(value):
            yield from json_pins(row, document, files, (*loc, i))
    if not isinstance(value, dict):
        return
    section = loc[-1] if loc else None
    for key, child in value.items():
        where = (*loc, key)
        if isinstance(child, (dict, list)):
            yield from json_pins(child, document, files, where)
            continue
        if not is_hash(child):
            continue
        path = None
        if section in PATH_MAPS:
            path = repo_path(key, document, files, prefix=PATH_MAPS[section])
        elif section == "helpers" and document.startswith("recipe/shader-"):
            path = repo_path(key, document, files, prefix="scripts/lab/")
        elif key == "sha256":
            # A named external root (SDK, staged APK, etc.) defines a different namespace.
            if value.get("root") not in (None, "repo", "repository"):
                continue
            for label in ("path", "profile", "template"):
                path = repo_path(value.get(label), document, files, relative=True)
                if path:
                    break
            if not path:
                path = repo_path(section, document, files)
        elif key in {"source_sha256", "recipe_sha256", "owner_source_sha256", "generator_recipe_sha256"}:
            path = repo_path(value.get(key.removesuffix("_sha256")), document, files, relative=True)
            if not path and key == "source_sha256" and section == "obj_import":
                path = "tools/phone-build/accepted-output/mesh_obj.c"
        elif key == "generator_sha256":
            path = repo_path(value.get("generator"), document, files, prefix="scripts/lab/")
        elif key == "graphics_template_sha256" and document == "recipe/project-inputs.json":
            path = "smoke/ProjectSettings/GraphicsSettings.asset"
        elif section == "tools" and document.startswith("recipe/shader-") and re.fullmatch(r"shader_[a-z_]+_sha256", key):
            path = "scripts/lab/" + key.removesuffix("_sha256") + ".py"
        elif key.startswith(REPO_PREFIXES):
            path = repo_path(key, document, files)
        if path:
            size = value.get("bytes") if key == "sha256" else None
            yield Pin(path, child, where, size if type(size) is int else None)


def python_pins(data, mappings):
    """Read the existing reviewed Python bindings as literals, without importing them."""
    starts = [0]
    for line in data.splitlines(keepends=True):
        starts.append(starts[-1] + len(line))

    def literal(node, target):
        raw = ast.literal_eval(node)
        if not is_hash(raw):
            raise ValueError("invalid tracked source hash literal")
        return Pin(target, raw, (starts[node.lineno - 1] + node.col_offset, starts[node.end_lineno - 1] + node.end_col_offset))

    assignments = {
        target.id: node.value for node in ast.parse(data).body if isinstance(node, ast.Assign) for target in node.targets if isinstance(target, ast.Name)
    }
    for name, source in mappings.items():
        node = assignments[name]
        if isinstance(node, ast.Dict):
            for key_node, value in zip(node.keys, node.values):
                key = ast.literal_eval(key_node)
                if isinstance(source, str):
                    yield literal(value, posixpath.normpath(source + key))
                elif key in source:
                    yield literal(value, source[key])
        else:
            yield literal(node, source)


def recipe_provider(name):
    return name.startswith("recipe/owner-") and name.endswith((".json", ".jsonl.gz"))


def json_document(name):
    return name.startswith(("recipe/", "environment/", "tools/phone-build/")) and name.endswith(".json")


def json_spans(value, data, replacements):
    """Map changed scalar fields to byte ranges while preserving the source formatting."""
    tokens = iter(JSON_TOKEN.finditer(data))
    edits = {}

    def visit(node, loc=()):
        token = next(tokens)
        if isinstance(node, dict):
            for i, (key, child) in enumerate(node.items()):
                if i:
                    next(tokens)  # comma
                next(tokens)  # key
                next(tokens)  # colon
                visit(child, (*loc, key))
            next(tokens)  # closing brace
        elif isinstance(node, list):
            for i, child in enumerate(node):
                if i:
                    next(tokens)  # comma
                visit(child, (*loc, i))
            next(tokens)  # closing bracket
        elif loc in replacements:
            edits[token.span()] = replacements[loc]

    visit(value)
    if len(edits) != len(replacements):
        raise ValueError("could not locate every changed JSON pin")
    return edits


def splice(data, edits):
    chunks = []
    previous = 0
    for (start, end), value in sorted(edits.items()):
        if start < previous:
            raise ValueError("overlapping source pin bindings")
        chunks.extend((data[previous:start], json.dumps(value).encode()))
        previous = end
    chunks.append(data[previous:])
    return b"".join(chunks)


class Plan:
    def __init__(self, snapshot, bases, blobs):
        self.snapshot = snapshot
        self.bindings = {}
        self.digests = {}
        self.external = {}
        self.issues = []
        self.stale = defaultdict(Counter)
        self.outputs = {}
        self.results = {}
        self.visiting = set()
        providers = defaultdict(set)
        selectors = {}
        for name in sorted(snapshot.files):
            if not (recipe_provider(name) or json_document(name) or name in PYTHON_BINDINGS):
                continue
            data = snapshot.read(name)
            if recipe_provider(name):
                digest = sha256(data).hexdigest()
                self.digests[name] = (digest, len(data))
                providers[digest].add(name)
            if name in PYTHON_BINDINGS:
                pins = list(python_pins(data, PYTHON_BINDINGS[name]))
            elif json_document(name) and name not in HISTORICAL:
                pins = self.read_json_bindings(name, data, selectors)
            else:
                continue
            if pins:
                self.bindings[name] = pins
        unresolved = {old for pins in selectors.values() for old, _, _ in pins} - providers.keys()
        if unresolved:
            self.find_prior_providers(bases, blobs, unresolved, providers)
        for name, fields in selectors.items():
            for old, key, span in fields:
                candidates = providers[old]
                if candidates:
                    source, *others = sorted(candidates, reverse=True)
                    self.bindings.setdefault(name, []).append(Pin(source, old, span, alternatives=tuple(others)))
                else:
                    self.issues.append(f"{name} {key}: unresolved tracked provider for {old}")
        for name in sorted(self.bindings):
            self.resolve(name)

    def read_json_bindings(self, name, data, selectors):
        pins = []
        if name.startswith("recipe/shader-") or any(marker in data for marker in EXPLICIT):
            value = json.loads(data)
            pins = list(json_pins(value, name, self.snapshot.files))
            if name == "recipe/native-view-camera-transform.json":
                pins.extend(Pin(source, value["source_sha256"][role], ("source_sha256", role)) for role, source in value["source_paths"].items())
        # Track only whole-file selectors here. The serialized object SHA and
        # size in the same row refer to produced or original bytes.
        derived_selector_hashes = 0
        matches = SELECTOR.finditer(data) if any(key in data for key in SELECTOR_KEYS) else ()
        for match in matches:
            old, key = match[2].decode(), match[1].decode()
            if key != "profile_sha256" or name == "recipe/owner-player-data.json":
                start, end = match.span(2)
                selectors.setdefault(name, []).append((old, key, (start - 1, end + 1)))
                derived_selector_hashes += key.endswith("sha256")
        unbound = data.count(b'"sha256"') + data.count(b'_sha256"') - sum(str(pin.location[-1]).endswith("sha256") for pin in pins) - derived_selector_hashes
        if unbound > 0:
            self.external[name] = unbound
        return pins

    def find_prior_providers(self, bases, blobs, unresolved, providers):
        checked = set()
        for base in bases:
            for name, oid in tracked(self.snapshot.root, base).items():
                if not recipe_provider(name) or (self.snapshot.blobs and self.snapshot.files.get(name) == oid) or (name, oid) in checked:
                    continue
                checked.add((name, oid))
                old = sha256(blobs.read(oid)).hexdigest()
                if old in unresolved:
                    providers[old].add(name)

    def resolve(self, name):
        if name in self.results:
            return self.results[name]
        if name in self.visiting:
            raise ValueError(f"tracked source pin cycle at {name}")
        if name not in self.snapshot.files:
            return None
        self.visiting.add(name)
        edits, fields = {}, {}
        for pin in self.bindings.get(name, ()):
            result = self.resolve(pin.source)
            if pin.alternatives:
                results = {result, *(self.resolve(source) for source in pin.alternatives)} - {None}
                matching = next((entry for entry in results if entry[0] == pin.current), None)
                if matching is None and len(results) > 1:
                    self.issues.append(f"{name} {pin.name}: ambiguous tracked providers for {pin.current}")
                    continue
                result = matching or next(iter(results), None)
            if result is None:
                self.issues.append(f"{name} {pin.name}: missing tracked source {pin.source}")
                continue
            digest, size = result
            if pin.current == digest and (pin.size is None or pin.size == size):
                continue
            self.stale[name][pin.source] += 1
            if type(pin.location[0]) is int and len(pin.location) == 2 and all(type(i) is int for i in pin.location):
                edits[pin.location] = digest
            else:
                fields[pin.location] = digest
                if pin.size is not None:
                    fields[(*pin.location[:-1], "bytes")] = size
        if edits or fields:
            data = self.snapshot.read(name)
            if fields:
                edits.update(json_spans(json.loads(data), data, fields))
            updated = splice(data, edits)
            self.outputs[name] = (data, updated)
            result = sha256(updated).hexdigest(), len(updated)
        elif name in self.digests:
            result = self.digests[name]
        else:
            data = self.snapshot.read(name)
            result = sha256(data).hexdigest(), len(data)
        self.visiting.remove(name)
        self.results[name] = result
        return result

    def report(self, show_external):
        for name, sources in sorted(self.stale.items()):
            for source, count in sorted(sources.items()):
                print(f"Stale: {name} <- {source} ({count} pins)")
        for issue in sorted(set(self.issues)):
            print(issue, file=sys.stderr)
        if show_external:
            for name, count in sorted(self.external.items()):
                print(f"Outside tracked-source resolution: {name} ({count} SHA fields)")
        print(f"{len(self.stale)} files with stale derived pins. {sum(self.external.values())} other SHA fields require their input or output witness.")

    def write(self, root, commit=None, ref=None):
        if commit:
            head = git(root, "rev-parse", "HEAD").decode().strip()
            branch = subprocess.run(["git", "-C", str(root), "symbolic-ref", "-q", "HEAD"], capture_output=True, text=True).stdout.strip()
            if head != commit or branch != ref:
                print("Check out the outgoing branch and run ./dev pins refresh.", file=sys.stderr)
                return False
            index = tracked(root)
        for name, (original, _) in self.outputs.items():
            if safe_path(root, name).read_bytes() != original or (commit and index.get(name) != self.snapshot.files[name]):
                print(f"Preserving local edits to {name}. Run ./dev pins refresh after reviewing them.", file=sys.stderr)
                return False
        for name, (_, updated) in sorted(self.outputs.items()):
            target = root / name
            with tempfile.NamedTemporaryFile(dir=target.parent, prefix=".pins-", delete=False) as stream:
                temporary = Path(stream.name)
                try:
                    stream.write(updated)
                    stream.close()
                    temporary.chmod(target.stat().st_mode & 0o777)
                    temporary.replace(target)
                finally:
                    temporary.unlink(missing_ok=True)
            print(f"Refreshed {name}")
        return True


def prior_versions(root, commit, base):
    # Compare the outgoing range base, main and immediate parents. A
    # digest-only selector never guesses from a name or from an external file.
    target = commit or "HEAD"
    versions = git(root, "rev-list", "--parents", "-1", target).decode().split()[1:]
    if base:
        versions.append(git(root, "rev-parse", "--verify", base).decode().strip())
    if not commit:
        versions.append(git(root, "rev-parse", "HEAD").decode().strip())
    main = subprocess.run(["git", "-C", str(root), "merge-base", target, "origin/main"], capture_output=True, text=True)
    if main.returncode == 0:
        versions.append(main.stdout.strip())
    return tuple(dict.fromkeys(versions))


def main(argv=None, *, root=ROOT):
    parser = argparse.ArgumentParser(prog="./dev pins", description="Current host tooling for tracked-source recipe pins.")
    parser.add_argument("command", choices=("check", "refresh"))
    parser.add_argument("--show-external", action="store_true", help="list files with SHA fields that need their original input or output witness")
    parser.add_argument("--base", help="prior Git revision for legacy digest-only profile selectors")
    parser.add_argument("--commit", help=argparse.SUPPRESS)
    parser.add_argument("--refresh-for-push", metavar="REF", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if (args.commit and args.command != "check") or (args.refresh_for_push and not args.commit):
        parser.error("commit checks use check; refresh-for-push requires an outgoing commit")
    try:
        with ExitStack() as stack:
            blobs = Blobs(root, stack)
            snapshot = Snapshot(root, args.commit, blobs)
            plan = Plan(snapshot, prior_versions(root, args.commit, args.base), blobs)
        plan.report(args.show_external)
        if plan.issues:
            return 1
        if not plan.outputs:
            return 0
        if args.command == "refresh":
            return 0 if plan.write(root) else 1
        if args.refresh_for_push:
            if plan.write(root, args.commit, args.refresh_for_push):
                print("Commit the refreshed files, then push again.", file=sys.stderr)
        else:
            print("Run ./dev pins refresh to update the tracked-source pins.", file=sys.stderr)
        return 1
    except (KeyError, OSError, SyntaxError, ValueError, subprocess.CalledProcessError) as error:
        print(f"Cannot check tracked-source pins: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
