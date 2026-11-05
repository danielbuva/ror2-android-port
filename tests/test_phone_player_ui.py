"""Authored graph, schema and SDK-declaration contracts; no game/SDK inputs."""

from contextlib import closing
import copy
import importlib.util
import io
from pathlib import Path
import struct
import tempfile
from types import SimpleNamespace as N
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("source_player_ui", ROOT / "tools/phone-build/accepted-output/player_ui.py")
U = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(U)


def fake(pid, kind, fields):
    return N(
        path_id=pid,
        type=N(value=kind),
        node=N(m_Type={1: "GameObject", 224: "RectTransform", 114: "MonoBehaviour"}[kind]),
        read_typetree=lambda: copy.deepcopy(fields),
        typ=dict(class_id=kind),
    )


def pointer(pid=0, file=0):
    return dict(m_FileID=file, m_PathID=pid)


def graph_fixture():
    objects = {}
    for pid, name, parent, children in [(1, "Original", 0, [11, 21]), (10, "Play", 2, []), (20, "Quit", 2, [])]:
        components = [pid + 1] + ([pid + 2] if pid != 1 else [])
        objects[pid] = fake(pid, 1, dict(m_Name=name, m_IsActive=True, m_Component=[dict(component=pointer(c)) for c in components]))
        objects[pid + 1] = fake(pid + 1, 224, dict(m_GameObject=pointer(pid), m_Father=pointer(parent), m_Children=[pointer(c) for c in children]))
        if pid != 1:
            objects[pid + 2] = fake(pid + 2, 114, dict(m_GameObject=pointer(pid), m_Script=pointer(91, 1)))
    return N(objects=objects)


class PlayerUiTests(unittest.TestCase):
    def test_source_common_strings_outside_script_hash_subset_are_resolved(self):
        tree = bytearray(U.S._tree([U.S._node("MonoBehaviour", "Base", -1, 0), U.S._node("int", "value", 4)]))
        struct.pack_into("<I", tree, 8 + 32 + 8, 0x80000000 | 778)
        expected = U.node_from_tree(bytes(tree)).m_Children[0].m_Name
        self.assertEqual(U.S.tree_nodes(U.explicit_tree(bytes(tree)))[1]["name"], expected)

    def test_hierarchy_and_new_component_relationships_use_independent_ids(self):
        asset = graph_fixture()
        selected = dict(
            root_path_id=1,
            root_name="Menu",
            text_identity="text",
            hidden_names=[],
            enabled_names=[],
            buttons=[dict(name="Play", token="PLAY", suffix=""), dict(name="Quit", token="QUIT", suffix="")],
        )
        with patch.object(U, "identity", side_effect=lambda obj, scripts: "RoR2:RoR2.UI.HGButton" if obj.type.value == 114 else obj.node.m_Type):
            graph, rows, extras = U.graph_records(asset, {}, selected, dict(PLAY="Play", QUIT="Quit"))
        self.assertEqual(len(graph), 3)
        self.assertEqual(len(rows), 6)  # Two original unsupported scripts removed.
        self.assertEqual([r["id"] for r in extras], [7, 8, 9])
        roots = {r["path"]: r for r in rows if r["identity"] == "GameObject"}
        self.assertEqual(roots["$"]["fields"]["m_Name"], "Menu")
        self.assertFalse(roots["$"]["fields"]["m_IsActive"])
        for extra in extras:
            components = roots[extra["path"]]["fields"]["m_Component"]
            self.assertEqual(components[-1], dict(component=pointer(extra["id"])))
        root_transform = next(r for r in rows if r["path"] == "$" and r["identity"] == "RectTransform")
        self.assertEqual(root_transform["fields"]["m_Children"], [pointer(5), pointer(6)])

    def test_hierarchy_rejects_duplicate_children(self):
        asset = graph_fixture()
        asset.objects[2] = fake(2, 224, dict(m_GameObject=pointer(1), m_Father=pointer(), m_Children=[pointer(11), pointer(11)]))
        with self.assertRaisesRegex(ValueError, "multiply owned"):
            U.hierarchy(asset, 1)

    def test_saved_build_ids_relocate_graph_without_changing_content(self):
        rows = [
            dict(id=1, path="$", identity="GameObject", fields=dict(component=pointer(2), external=pointer(2, 1), null=pointer(), alignment=5)),
            dict(id=2, path="$", identity="Widget", fields=dict(owner=pointer(1), text="source-owned")),
        ]
        saved = [dict(id=2, path="$", identity="GameObject"), dict(id=1, path="$", identity="Widget")]
        U.assign_saved_ids(rows, saved)
        self.assertEqual([row["identity"] for row in rows], ["Widget", "GameObject"])
        self.assertEqual(rows[0]["fields"], dict(owner=pointer(2), text="source-owned"))
        self.assertEqual(rows[1]["fields"], dict(component=pointer(1), external=pointer(2, 1), null=pointer(), alignment=5))
        for invalid, message in [
            (saved[:1], "cohort"),
            ([saved[0], dict(saved[1], identity="Different")], "source graph"),
            ([saved[0], dict(saved[1], id=2)], "complete player allocation"),
        ]:
            with self.subTest(message=message), self.assertRaisesRegex(ValueError, message):
                U.assign_saved_ids(copy.deepcopy(rows), invalid)

    def test_saved_external_ids_append_new_provider_without_changing_destinations(self):
        files = ["registry", "new-source-sprite", "existing-sprite"]
        fields = [dict(local=pointer(17), new=pointer(1, 2), existing=pointer(23, 3), value=3)]
        U.assign_saved_external_order(fields, files, ["registry", "existing-sprite"])
        self.assertEqual(files, ["registry", "existing-sprite", "new-source-sprite"])
        self.assertEqual(fields, [dict(local=pointer(17), new=pointer(1, 3), existing=pointer(23, 2), value=3)])
        for saved in (["unknown"], ["registry", "registry"]):
            with self.assertRaisesRegex(ValueError, "resolved providers"):
                U.assign_saved_external_order(fields, files, saved)

    def test_only_typed_pointer_structures_are_relocated(self):
        value = dict(reference=pointer(41, 2), scalar=41, partial=dict(m_PathID=41, unrelated=2), array=[pointer(0)])
        U.map_pointers(value, lambda p: pointer(p["m_PathID"] + 1, p["m_FileID"]))
        self.assertEqual(value["reference"], pointer(42, 2))
        self.assertEqual(value["array"], [pointer(1)])
        self.assertEqual(value["scalar"], 41)
        self.assertEqual(value["partial"], dict(m_PathID=41, unrelated=2))

    def test_copied_sprites_require_identity_and_geometry(self):
        a = dict(m_Name="authored", m_RenderDataKey=[17, 19], m_Rect=[0, 0, 3, 4], m_Offset=[0, 0], m_Border=[0] * 4, m_PixelsToUnits=100, m_Pivot=[0.5, 0.5])
        self.assertTrue(U.same_sprite(a, copy.deepcopy(a)))
        for key in ("m_RenderDataKey", "m_Rect", "m_Name"):
            b = copy.deepcopy(a)
            b[key] = "different"
            self.assertFalse(U.same_sprite(a, b))

    def test_unresolved_provider_fails_and_duplicate_destinations_are_ambiguous(self):
        linker = object.__new__(U.Linker)
        linker.aliases = {("member", 1): [("one", 1, ""), ("two", 1, "")]}
        linker.store = N(assets={})
        with self.assertRaisesRegex(ValueError, "ambiguous"):
            linker.choose(("member", 1))
        with self.assertRaisesRegex(ValueError, "declared source"):
            linker.choose(("unknown", 2))

    def test_graphic_material_reserves_its_provider_before_image_sprite(self):
        linker = object.__new__(U.Linker)
        linker.ui, linker.externals = object(), []
        linker.choose = lambda key, role=None: ("material" if role == "NativeUiMaterial" else "sprite", 1)
        row = dict(
            identity="UnityEngine.UI:UnityEngine.UI.Image",
            typ=dict(class_id=114),
            fields=dict(m_Material=pointer(41, 2), m_Sprite=pointer(42, 2), m_Script=pointer()),
        )
        with patch.object(U, "reference_key", side_effect=lambda asset, ptr: ("original", ptr["m_PathID"])):
            fields = linker.fields(row, set(), {("UnityEngine.UI.dll", "UnityEngine.UI", "Image"): 17})
        self.assertEqual(linker.externals, ["material", "sprite", "globalgamemanagers.assets"])
        self.assertEqual(fields, dict(m_Material=pointer(1, 1), m_Sprite=pointer(1, 2), m_Script=pointer(17, 3)))
        self.assertEqual(row["fields"]["m_Material"], pointer(41, 2))

    def test_sdk_defaults_are_derived_not_fixed_constants(self):
        texts = {
            "Navigation.cs": "public enum Mode { Automatic=12 } defaultNav.m_Mode = Mode.Automatic;",
            "Selectable.cs": "public enum Transition { None, Custom, Last } private Transition m_Transition = Transition.Custom; private bool m_Interactable = false;",
            "AnimationTriggers.cs": 'private const string kState = "AuthoredFocus"; private string m_NormalTrigger = kState;',
            "Button.cs": "private ButtonClickedEvent m_OnClick = new ButtonClickedEvent();",
        }
        with tempfile.TemporaryDirectory() as tmp, closing(U.Sources(Path(tmp))) as source:
            root = Path(tmp)
            for name, text in texts.items():
                (root / name).write_text(text)
            pins = {name: source.pin(root / name) for name in texts}
            result = U.sdk_defaults(source, root, pins)
            self.assertEqual(result, dict(mode=12, transition=1, interactable=False, animations=dict(m_NormalTrigger="AuthoredFocus")))
            (root / "Button.cs").write_text("changed")
            with self.assertRaisesRegex(ValueError, "hash/size"):
                U.sdk_defaults(source, root, pins)

    def test_shared_texture_output_requires_complete_freshly_derived_byte_equality(self):
        tree = U.S._tree([U.S._node("Texture2D", "Base", -1, 0), U.S._node("int", "value", 4)])
        obj = N(node=U.node_from_tree(tree), typ=dict(class_id=28, stripped=0, script_type=-1, hash=bytes(16), tree=tree))
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            name = "a" * 32
            U.write_object(root, name, obj, dict(value=17), [], reuse_existing=True)
            original = (root / name).read_bytes()
            U.write_object(root, name, obj, dict(value=17), [], reuse_existing=True)
            self.assertEqual((root / name).read_bytes(), original)
            with self.assertRaisesRegex(ValueError, "shared UI media bytes differ"):
                U.write_object(root, name, obj, dict(value=18), [], reuse_existing=True)
            self.assertEqual((root / name).read_bytes(), original)
            with self.assertRaises(FileExistsError):
                U.write_object(root, name, obj, dict(value=17), [])
            alias = "b" * 32
            (root / alias).symlink_to(root / name)
            with self.assertRaisesRegex(ValueError, "redirected"):
                U.write_object(root, alias, obj, dict(value=17), [], reuse_existing=True)

    def test_bounded_source_reader_round_trips_an_authored_native_record(self):
        fields = [U.S._node("GameObject", "Base", -1, 0), U.S._node("int", "value", 4)]
        tree = U.S._tree(fields)
        node = U.node_from_tree(tree)
        body = U.encode(dict(value=-27), node)
        layout = dict(
            engine="2021.3.45f2",
            platform=13,
            trees=True,
            types=[dict(class_id=1, stripped=0, script_type=-1, hash=bytes(16), tree=tree, dependencies=[])],
            objects=[dict(path_id=17, type_id=0, offset=0, bytes=len(body))],
            scripts=[],
            externals=[],
            ref_types=[],
            user="",
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "authored.assets"
            with path.open("wb") as stream:
                U.W.write_serialized(stream, layout, lambda _: io.BytesIO(body))
            with closing(U.Sources(tmp)) as source:
                asset = source.asset_file(path, "authored")
                self.assertEqual(asset.objects[17].read_typetree(), dict(value=-27))
                self.assertEqual(asset.objects[17].get_raw_data(), body)
                self.assertEqual(len(asset.nodes), 1)
                stripped = Path(tmp) / "authored-stripped.assets"
                layout["trees"] = False
                with stripped.open("wb") as stream:
                    U.W.write_serialized(stream, layout, lambda _: io.BytesIO(body))
                copied = source.asset_file(stripped, "matching-native")
                self.assertEqual(copied.objects[17].read_typetree(), dict(value=-27))
                layout["types"][0]["hash"] = bytes([1]) * 16
                other = Path(tmp) / "different-native.assets"
                with other.open("wb") as stream:
                    U.W.write_serialized(stream, layout, lambda _: io.BytesIO(body))
                with self.assertRaisesRegex(ValueError, "no transfer schema"):
                    source.asset_file(other, "different-native").objects[17].read_typetree()
                source.recheck()
                handle = asset.stream
            self.assertTrue(handle.closed)

    def test_script_hash_api_delegates_to_schema_and_keeps_absent_type_semantics(self):
        with patch.dict("sys.modules", {"dnfile": N()}):
            reader = U.S._RegistryTypes(Path("."), {}, lambda *args: None, None, {})
        identity = ("Fixture.dll", "Lab", "Probe")
        with (
            closing(reader),
            patch.object(reader, "script_schema", return_value=None) as schema,
            patch.object(U.S, "properties_hash", return_value=bytes(range(16))) as hashing,
        ):
            self.assertEqual(reader.script_hash(identity, {}), bytes(16))
            hashing.assert_not_called()
            schema.return_value = b"authored schema"
            self.assertEqual(reader.script_hash(identity, {}), bytes(range(16)))
            hashing.assert_called_once_with("Probe", "Lab", "Fixture.dll", b"authored schema", None)


if __name__ == "__main__":
    unittest.main()
