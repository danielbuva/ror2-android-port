"""Authored cloned-graph contracts; no original assets or SDK required."""

import copy
import importlib.util
from pathlib import Path
from types import SimpleNamespace as N
import unittest

ROOT = Path(__file__).resolve().parents[1]


def load(name, file):
    spec = importlib.util.spec_from_file_location(name, ROOT / "tools/phone-build/accepted-output" / file)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


H = load("source_hud", "player_hud.py")
U = load("source_hud_ui", "player_ui.py")


def ptr(pid=0, file=0):
    return dict(m_FileID=file, m_PathID=pid)


def fixture():
    definitions = {
        1: (1, "GameObject", dict(m_Name="Original", m_IsActive=False, m_Component=[dict(component=ptr(2)), dict(component=ptr(3))])),
        2: (224, "RectTransform", dict(m_GameObject=ptr(1), m_Father=ptr(), m_Children=[])),
        3: (114, "Fixture.Widget", dict(m_GameObject=ptr(1), target=ptr(2), external=ptr(99, 1))),
    }
    objects = {
        pid: N(
            path_id=pid,
            type=N(value=kind),
            ident=identity,
            typ=dict(class_id=kind),
            node=N(m_Type=identity),
            read_typetree=lambda fields=fields: copy.deepcopy(fields),
        )
        for pid, (kind, identity, fields) in definitions.items()
    }
    asset = N(name="authored-member", objects=objects, externals=[dict(path="archive:/original-supplier/original-supplier")])
    api = N(require=U.require, hierarchy=U.hierarchy, map_pointers=U.map_pointers, reference_key=U.reference_key, identity=lambda obj, scripts: obj.ident)
    return asset, api


class HudGraphTests(unittest.TestCase):
    def test_two_instances_relocate_their_own_components_and_attach_reciprocally(self):
        asset, api = fixture()
        graph = H.Graph(api, N(assets={asset.name: asset}), {})
        a = graph.clone(asset, 1, "first")
        b = graph.clone(asset, 1, "second", a)
        self.assertEqual(a["fields"]["m_Name"], "Original(Clone)")
        rows, ids = graph.finalize()
        byid = {row["id"]: row for row in rows}
        self.assertEqual(len(rows), 6)
        for instance in ("first", "second"):
            go = ids["object", instance, 1]
            transform = ids["object", instance, 2]
            component = ids["object", instance, 3]
            self.assertEqual(byid[component]["fields"]["m_GameObject"], ptr(go))
            self.assertEqual(byid[component]["fields"]["target"], ptr(transform))
            self.assertEqual(byid[component]["fields"]["external"], ptr(99, 1))
        self.assertEqual(byid[ids["object", "second", 2]]["fields"]["m_Father"], ptr(ids["object", "first", 2]))
        self.assertEqual(byid[ids["object", "first", 2]]["fields"]["m_Children"], [ptr(ids["object", "second", 2])])
        self.assertEqual(asset.objects[1].read_typetree()["m_Name"], "Original")
        self.assertEqual(b["fields"]["m_Name"], "Original(Clone)")

    def test_shared_binding_dict_is_not_relocated_twice(self):
        asset, api = fixture()
        graph = H.Graph(api, N(assets={asset.name: asset}), {})
        root = graph.clone(asset, 1, "one")
        original = graph.component(root, "Widget")
        authored = graph.add(root, "Fixture.Authored", dict(target=original["fields"]["target"]))
        self.assertIs(authored["fields"]["target"], original["fields"]["target"])
        rows, ids = graph.finalize()
        for row in rows:
            if "target" in row["fields"]:
                self.assertEqual(row["fields"]["target"], ptr(ids["object", "one", 2]))

    def test_component_lookup_accepts_a_component_owner_and_duplicate_clone_refuses(self):
        asset, api = fixture()
        graph = H.Graph(api, N(assets={asset.name: asset}), {})
        root = graph.clone(asset, 1, "one")
        widget = graph.component(root, "Widget")
        self.assertEqual(graph.component(widget, "RectTransform")["key"], ("object", "one", 2))
        with self.assertRaisesRegex(ValueError, "duplicate clone"):
            graph.clone(asset, 1, "one")


if __name__ == "__main__":
    unittest.main()
