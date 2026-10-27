"""Real binary-XML retention policy with authored fixtures; no APKs or keys."""

import ast
import copy
import importlib.util
import inspect
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


M = load("retention_manifest_fixture", ROOT / "tests/test_owner_binary_manifest.py")
OWNER = load("retention_apk_owner", ROOT / "tools/phone-build/owner-apk/build_owner_apk.py")
ALPHA = "dev.ror2lab.alpha"
ANDROID = M.PATCH.ANDROID
NONE = M.NONE
POLICY = {"schema": 1, "installer_package": "dev.authored.installer", "installer_certificate_sha256": "c" * 64, "data_schema": {"writes": 1, "reads": [1]}}


def extended_manifest(*, utf8=True, attributes=(), children=()):
    """Add independently encoded attributes/components to the authored XML."""
    data = M.authored_manifest(utf8=utf8, application_name=".AuthoredApplication")
    chunks = list(M.WIRE._chunks(data, 8, len(data)))
    pool = next(row for row in chunks if row[0] == 1)
    strings = list(M.WIRE._strings(data, *pool[1:]))
    resource = next(row for row in chunks if row[0] == 0x180)
    resources = list(struct.unpack_from("<" + "I" * ((resource[3] - 8) // 4), data, resource[1] + 8))

    def index(value):
        if value not in strings:
            strings.append(value)
        return strings.index(value)

    def attribute(name, value, kind=3, resource=0):
        key = index(name)
        resources.extend([0] * max(0, key + 1 - len(resources)))
        resources[key] = resource or resources[key]
        number = index(value) if kind == 3 else value
        return struct.pack("<IIIHBBI", index(ANDROID), key, number if kind == 3 else NONE, 8, 0, kind, number)

    additions = {}
    for tag, name, value, kind, resource in attributes:
        additions.setdefault(tag, []).append(attribute(name, value, kind, resource))
    child_bytes = b""
    for tag, attrs in children:
        selected = index(tag)
        rows = [attribute(*row) for row in attrs]
        block = b"".join(rows)
        opening = struct.pack("<HHIII", 0x102, 16, 36 + len(block), 1, NONE)
        opening += struct.pack("<IIHHHHHH", NONE, selected, 20, 20, len(rows), 0, 0, 0) + block
        child_bytes += opening + struct.pack("<HHIIIII", 0x103, 16, 24, 1, NONE, NONE, selected)
    encoded = []
    for kind, start, header, size in chunks:
        raw = data[start : start + size]
        if kind in (1, 0x180):
            encoded.append((kind, None))
            continue
        if kind == 0x102:
            tag = strings[struct.unpack_from("<I", raw, header + 4)[0]]
            selected = additions.pop(tag, [])
            if selected:
                raw = bytearray(raw)
                count = struct.unpack_from("<H", raw, header + 12)[0]
                struct.pack_into("<H", raw, header + 12, count + len(selected))
                raw += b"".join(selected)
                struct.pack_into("<I", raw, 4, len(raw))
                raw = bytes(raw)
        if kind == 0x103 and strings[struct.unpack_from("<I", raw, header + 4)[0]] == "application":
            encoded.append((0, child_bytes))
        encoded.append((kind, raw))
    assert not additions
    new_pool = M.PATCH.string_pool(strings, utf8)
    new_resources = struct.pack("<HHI", 0x180, 8, 8 + 4 * len(resources)) + struct.pack("<" + "I" * len(resources), *resources)
    body = b"".join(new_pool if kind == 1 else new_resources if kind == 0x180 else raw for kind, raw in encoded)
    return struct.pack("<HHI", 3, 8, 8 + len(body)) + body


def retained(data, **options):
    return M.PATCH.patch(data, M.WIRE, **dict(application_id=ALPHA, version_code=101, retention=True, **options))


class AlphaBinaryRetentionTests(unittest.TestCase):
    def test_exact_provider_privacy_and_launch_gate_preserve_original_metadata(self):
        for utf8 in (True, False):
            original = extended_manifest(utf8=utf8, attributes=[("application", "allowBackup", 1, 0x12, 0x01010280)])
            before = M.read(original)[2]
            after = M.read(retained(original))[2]
            attrs = lambda node: node["attributes"]
            root = after[0]
            self.assertEqual(attrs(root)[(None, "package")], ALPHA)
            self.assertEqual(attrs(root)[(ANDROID, "versionCode")], 101)
            app = next(node for node in after if node["tag"] == "application")
            self.assertEqual(attrs(app)[(ANDROID, "allowBackup")], 0)
            self.assertEqual(attrs(app)[(ANDROID, "name")], "dev.owner.authoredfixture.AuthoredApplication")
            providers = [node for node in after if node["tag"] == "provider"]
            self.assertEqual(len(providers), 1)
            self.assertEqual(
                attrs(providers[0]),
                {
                    (ANDROID, "name"): "dev.ror2owner.bootstrap.ProfileRetentionProvider",
                    (ANDROID, "authorities"): ALPHA + ".retention",
                    (ANDROID, "exported"): 1,
                    (ANDROID, "multiprocess"): 0,
                    (ANDROID, "grantUriPermissions"): 0,
                },
            )
            unity = next(node for node in after if node["tag"] == "activity" and attrs(node).get((ANDROID, "name")) == M.PATCH.UNITY)
            self.assertEqual(attrs(unity)[(ANDROID, "exported")], 0)
            self.assertEqual(attrs(unity)[(ANDROID, "configChanges")], 0x700)
            markers = lambda nodes: [attrs(node) for node in nodes if node["tag"] == "meta-data"]
            self.assertEqual(markers(after), markers(before))
            launcher = next(node for node in after if node["tag"] == "category" and attrs(node).get((ANDROID, "name")) == "android.intent.category.LAUNCHER")
            self.assertEqual(attrs(launcher["parents"][-2])[(ANDROID, "name")], M.PATCH.BOOTSTRAP)

    def test_retention_requires_explicit_alpha_package_and_positive_issued_version(self):
        for package, code in ((None, 1), ("dev.ror2lab.arm64", 1), (ALPHA, None), (ALPHA, 0), (ALPHA, True)):
            with self.subTest(package=package, code=code), self.assertRaises(ValueError):
                M.PATCH.patch(M.authored_manifest(), M.WIRE, application_id=package, version_code=code, retention=True)

    def test_custom_process_backup_agent_and_alias_are_refused(self):
        for tag, name, value, resource in (
            ("application", "process", ":other", 0x01010011),
            ("activity", "process", ":other", 0x01010011),
            ("application", "backupAgent", ".BackupAgent", 0x0101027F),
        ):
            data = extended_manifest(attributes=[(tag, name, value, 3, resource)])
            with self.subTest(tag=tag, name=name), self.assertRaises(ValueError):
                retained(data)
        alias = extended_manifest(children=[("activity-alias", [("name", ".Alias", 3, 0x01010003)])])
        with self.assertRaisesRegex(ValueError, "alias"):
            retained(alias)

    def test_provider_name_and_authority_collisions_including_authority_lists_refuse(self):
        for name, authority in (
            ("dev.ror2owner.bootstrap.ProfileRetentionProvider", "dev.other.authority"),
            ("dev.authored.OtherProvider", ALPHA + ".retention"),
            ("dev.authored.OtherProvider", ALPHA + ".retention;dev.other.authority"),
        ):
            data = extended_manifest(children=[("provider", [("name", name, 3, 0x01010003), ("authorities", authority, 3, 0x01010018)])])
            with self.subTest(name=name, authority=authority), self.assertRaisesRegex(ValueError, "collid"):
                retained(data)

    def test_duplicate_backup_attributes_refuse_instead_of_selecting_one(self):
        data = extended_manifest(attributes=[("application", "allowBackup", 1, 0x12, 0x01010280)] * 2)
        with self.assertRaisesRegex(ValueError, "duplicate backup"):
            retained(data)


class AlphaBuildPolicyTests(unittest.TestCase):
    def test_actual_installer_certificate_and_only_native_schema_one_are_admitted(self):
        self.assertEqual(OWNER.retention_policy(POLICY), POLICY)
        for field, value in (
            ("schema", True),
            ("installer_package", ALPHA),
            ("installer_package", "../other"),
            ("installer_certificate_sha256", ""),
            ("installer_certificate_sha256", "C" * 64),
            ("data_schema", {"writes": 2, "reads": [1, 2]}),
            ("data_schema", {"writes": 1, "reads": [1, 2]}),
        ):
            policy = copy.deepcopy(POLICY)
            policy[field] = value
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                OWNER.retention_policy(policy)
        with self.assertRaises(ValueError):
            OWNER.retention_policy(dict(POLICY, extra="unbound"))

    def test_alpha_build_missing_issued_version_refuses_before_output_or_dispatch(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            request = {name: str(root / "unused" / name) for name in ("manifest", "targets", "frontend", "java", "android_jar", "d8_jar", "wire_helper")}
            request.update(manifest_sha256="a" * 64, application_id=ALPHA, retention_policy=POLICY)
            path, output = root / "request.json", root / "output"
            path.write_text(json.dumps(request))
            with (
                patch.object(OWNER, "check", side_effect=AssertionError("assembly dispatched without issued version")) as check,
                patch.object(OWNER.subprocess, "run") as run,
            ):
                with self.assertRaisesRegex(ValueError, "version"):
                    OWNER.build(path, output)
                check.assert_not_called()
                run.assert_not_called()
            self.assertFalse(output.exists())

    def test_build_wiring_compiles_owners_and_packages_the_exact_checked_policy(self):
        # No compiler/APK creation is executed. Inspect the production AST rather
        # than searching comments or accepting another unbound policy variable.
        tree = ast.parse(inspect.getsource(OWNER.build))
        calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)]
        compile_call = next(
            node
            for node in calls
            if isinstance(node.func, ast.Name)
            and node.func.id == "run"
            and len(node.args) == 2
            and isinstance(node.args[1], ast.Constant)
            and node.args[1].value == "javac"
        )
        sources = {node.right.value for node in compile_call.args[0].elts if isinstance(node, ast.BinOp) and isinstance(node.right, ast.Constant)}
        self.assertTrue({"PayloadStore.java", "PayloadBootstrapActivity.java", "ProfileStore.java", "ProfileRetentionProvider.java"} <= sources)
        manifest = next(node for node in calls if isinstance(node.func, ast.Attribute) and ast.unparse(node.func) == "MANIFEST.patch")
        self.assertEqual(ast.unparse(next(row.value for row in manifest.keywords if row.arg == "retention")), "policy is not None")
        entry = next(
            node
            for node in calls
            if isinstance(node.func, ast.Name)
            and node.func.id == "entry"
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and node.args[0].value == "assets/owner-bootstrap/retention-policy.json"
        )
        dumps = next(node for node in ast.walk(entry) if isinstance(node, ast.Call) and ast.unparse(node.func) == "json.dumps")
        self.assertEqual(ast.unparse(dumps.args[0]), "policy")
        self.assertTrue(next(row.value.value for row in dumps.keywords if row.arg == "sort_keys"))
        self.assertEqual(
            ast.unparse(
                next(
                    node.value
                    for node in ast.walk(tree)
                    if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == "policy" for target in node.targets)
                )
            ),
            "retention_policy(request['retention_policy']) if request.get('retention_policy') is not None else None",
        )
