"""Authored record fixtures for the original-record stage context owner."""

import copy
import hashlib
import json
import tempfile
from unittest.mock import patch
import importlib.util
from pathlib import Path
from types import SimpleNamespace as N
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("stage_contexts_test", ROOT / "tools/phone-build/accepted-output/stage_contexts.py")
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)


def ptr(pid=0, file=0):
    return dict(m_FileID=file, m_PathID=pid)


def obj(pid, kind, **fields):
    return N(path_id=pid, type=N(value=kind), read_typetree=lambda: copy.deepcopy(fields))


def fixture():
    rows = [
        obj(1, 1, m_Name="Root", m_IsActive=True),
        obj(2, 1, m_Name="Child", m_IsActive=False),
        obj(11, 4, m_GameObject=ptr(1), m_Father=ptr(), m_Children=[ptr(12)]),
        obj(12, 4, m_GameObject=ptr(2), m_Father=ptr(11), m_Children=[]),
        obj(21, 114, m_GameObject=ptr(2), m_SceneId=dict(m_Value=37)),
        obj(22, 114, m_GameObject=ptr(2), toggleGroups=[dict(minEnabled=1, maxEnabled=2, objects=[ptr(2), ptr()])]),
    ]
    return N(objects={r.path_id: r for r in rows}, name="original", externals=[])


class StageContextsTests(unittest.TestCase):
    def test_binary_and_yaml_adapters_produce_the_same_runtime_graph(self):
        from tests.test_source_identity_metadata import _game_object, _transform, _network_identity, _toggle_controller, ProductionSourceIdentityReaderTests

        yaml = _game_object(1, "Root") + _game_object(2, "Child", False) + _transform(11, 1, 0, 0, (12,)) + _transform(12, 2, 11, 0)
        yaml += _network_identity(21, 2, 37) + _toggle_controller(22, 2, [([2, 0], 1, 2)])
        expected = ProductionSourceIdentityReaderTests().read_synthetic(yaml)
        actual = M.I.from_records(*M.graph_records(fixture(), None), expected["source_scene_sha256"])
        self.assertEqual(actual, expected)
        self.assertFalse(actual["network_identities"][0]["active_self"])

    def test_authored_global_suppression_does_not_change_other_source_flags(self):
        records = M.graph_records(fixture(), dict(required=["Root"], optional=["Absent"]))
        self.assertFalse(records[0]["1"]["active_self"])
        self.assertFalse(records[0]["2"]["active_self"])
        with self.assertRaisesRegex(ValueError, "global source roots differ"):
            M.graph_records(fixture(), dict(required=["Missing"], optional=[]))

    def test_provenance_binds_member_policy_and_producer_without_changing_graph(self):
        records = M.graph_records(fixture(), None)
        a = M.identity_metadata(records, "a" * 64, "b" * 64, "c" * 64)
        for source, policy, producer in [("d" * 64, "b" * 64, "c" * 64), ("a" * 64, "d" * 64, "c" * 64), ("a" * 64, "b" * 64, "d" * 64)]:
            b = M.identity_metadata(records, source, policy, producer)
            self.assertNotEqual(a["source_scene_sha256"], b["source_scene_sha256"])
            self.assertEqual(a["network_identities"], b["network_identities"])
            self.assertEqual(a["toggle_controllers"], b["toggle_controllers"])
        self.assertEqual(a["source_hash_representation"], "canonical-source-identity-graph-v1")

    def test_population_resolves_external_pools_and_preserves_bonus_hierarchy(self):
        asset = fixture()
        asset.externals = [dict(path="archive:/pool/owner")]
        fields = dict(
            ignoreArtifactsThatRebuildCards=True,
            contentSourceMixLimitOverride=False,
            contentInteractableOnlySourceMixLimitOverride=False,
            contentSourceMixLimitOverrideValue=7,
            contentInteractableOnlySourceMixLimitOverrideValue=9,
            sceneDirectorInteractibleCredits=23,
            sceneDirectorMonsterCredits=47,
            monsterDccsPool=ptr(91, 1),
            interactableDccsPool=ptr(92),
            bonusInteractibleCreditObjects=[dict(objectThatGrantsPointsIfEnabled=ptr(2), points=31)],
        )
        asset.objects[31] = obj(31, 114, **fields)
        asset.objects[32] = obj(
            32, 114, usePlacedSpawnPoints=False, expRewardCoefficient=1.0, eliteBias=2.0, spawnDistanceMultiplier=3.0, monsterSpawnTargetOverride=ptr()
        )
        pools = {("owner", 91): "monster-key", ("original", 92): "interactable-key"}
        value = M.population(asset, dict(classic_stage_info=31, scene_director=32), pools, *M.graph_records(fixture(), None)[:2])
        self.assertEqual(value["monsterDccsPool"], "monster-key")
        self.assertEqual(value["bonus_credits"], [dict(path="Root/Child", points=31)])
        self.assertEqual(value["fields"]["sceneDirectorMonsterCredits"], 47)
        asset.objects[32] = obj(
            32, 114, usePlacedSpawnPoints=False, expRewardCoefficient=1.0, eliteBias=2.0, spawnDistanceMultiplier=3.0, monsterSpawnTargetOverride=ptr(2)
        )
        with self.assertRaisesRegex(ValueError, "unsupported original monster target"):
            M.population(asset, dict(classic_stage_info=31, scene_director=32), pools, *M.graph_records(fixture(), None)[:2])

    def test_receipt_verification_rejects_changed_complete_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data = b"authored full-file fixture"
            (root / M.FILE).write_bytes(data)
            item = dict(bytes=len(data), sha256=hashlib.sha256(data).hexdigest())
            receipt = dict(success=True, source_only=True, files={M.FILE: item}, producer_pins={}, profile="fixture", profile_sha256="a" * 64, pc="fixture")
            path = root / "result.json"
            path.write_text(json.dumps(receipt))
            with patch.object(M, "produce", return_value=dict(files={M.FILE: item})):
                self.assertEqual(set(M.verify(path, M.P.sha(path))), {M.TARGET})
                (root / M.FILE).write_bytes(data + b"changed runtime field")
                with self.assertRaisesRegex(ValueError, "persisted stage context output differs"):
                    M.verify(path, M.P.sha(path))
            with patch.object(M, "produce", return_value=dict(files={M.FILE: dict(bytes=1, sha256="b" * 64)})):
                with self.assertRaisesRegex(ValueError, "regenerated source"):
                    M.verify(path, M.P.sha(path))

    def test_admission_accepts_only_the_complete_named_context_file(self):
        owner = M.U.module("_context_owner_test", ROOT / "tools/phone-build/owner-apk/build_owner_apk.py")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            prefix = "apk/assets/bin/Data/"
            (root / prefix).mkdir(parents=True)
            body = b"authored context"
            (root / M.TARGET).write_bytes(body)
            unknown = prefix + "globalgamemanagers"
            (root / unknown).write_bytes(b"incorrect manager")
            selected = {M.TARGET: dict(bytes=len(body), sha256=hashlib.sha256(body).hexdigest())}
            rows = [dict(path=name, bytes=1, sha256="0" * 64) for name in (M.TARGET, unknown)]
            request = dict(manifest="unused", manifest_sha256=owner.PROFILE, targets=str(root), stage_contexts=dict(path="fixture", sha256="a" * 64))
            with (
                patch.object(owner.PACKET, "profile", return_value=(b"", dict(targets=rows))),
                patch.object(owner, "module", return_value=N(verify=lambda *args: selected)),
            ):
                result = owner.check(request)
                self.assertEqual(result["generated_stage_context_count"], 1)
                self.assertEqual(result["exact_count"], 0)
                self.assertEqual(result["blocked_entries"], [unknown])
                (root / M.TARGET).write_bytes(body + b"modified field")
                self.assertIn(M.TARGET, owner.check(request)["blocked_entries"])

    def test_build_passes_both_generated_receipt_options_to_admission(self):
        owner = M.U.module("_context_owner_build_test", ROOT / "tools/phone-build/owner-apk/build_owner_apk.py")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            request = {key: str(root / "inputs" / key) for key in ("manifest", "targets", "frontend", "java", "android_jar", "d8_jar", "wire_helper")}
            request.update(
                manifest_sha256=owner.PROFILE, startup_metadata=dict(path="startup", sha256="a" * 64), stage_contexts=dict(path="contexts", sha256="b" * 64)
            )
            path = root / "request.json"
            path.write_text(json.dumps(request))
            with patch.object(owner, "check", return_value=dict(assembly_ready=False, entries=[])) as check:
                with self.assertRaisesRegex(ValueError, "inputs incomplete"):
                    owner.build(path, root / "output")
                check.assert_called_once_with(request)

    def test_single_precision_round_trip_preserves_exported_value(self):
        import struct

        value = struct.unpack("<f", struct.pack("<f", 0.1))[0]
        self.assertEqual(M.single(value), 0.1)
        self.assertEqual(struct.pack("<f", M.single(value)), struct.pack("<f", value))


if __name__ == "__main__":
    unittest.main()
