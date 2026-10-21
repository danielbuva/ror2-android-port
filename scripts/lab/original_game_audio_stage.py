#!/usr/bin/env python3
"""Hash-gated staging for the authored original-audio runtime cohort.

This is the final project-input step after the ordinary migration and assembly
transforms. It consumes a build producer's explicit artifact manifest; it does
not discover a candidate by timestamp, rewrite authored source, or modify the
accepted game installation. Copied files become Unity project inputs, so the
normal project cache digest includes the selected audio variant.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import tempfile

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = "original-game-audio-artifact-set-r1"
RECEIPT_SCHEMA = "original-game-audio-project-stage-r1"
HASH = re.compile(r"^[0-9a-f]{64}$")
DEFAULT_ROLES = frozenset({"observer", "core", "bootstrap"})
OPT_IN_ROLES = frozenset({"api", "game", "native", "banks"})
RESTORE_ROLES = frozenset({"restore_api", "restore_game"})
DEFAULT_TARGETS = {
    "observer": "Assets/LabLoadingScene/Plugins/OriginalOwnerProbeObserver.dll",
    "core": "Assets/LabLoadingScene/Plugins/GameAudioOriginalCore.dll",
    "bootstrap": "Assets/LabLoadingScene/Plugins/GameAudioOriginalBootstrap.dll",
    "api": "Assets/LabLoadingScene/Plugins/AK.Wwise.Unity.API.dll",
    "game": "Assets/LabLoadingScene/Plugins/RoR2.dll",
    "restore_api": "Assets/LabLoadingScene/Plugins/AK.Wwise.Unity.API.dll",
    "restore_game": "Assets/LabLoadingScene/Plugins/RoR2.dll",
}
NEW_ASSEMBLY_META = frozenset({target + ".meta" for role, target in DEFAULT_TARGETS.items() if role in {"observer", "core", "bootstrap"}})
NATIVE_TARGET = "Assets/Plugins/Android/arm64-v8a/libAkSoundEngine.so"
NATIVE_META = NATIVE_TARGET + ".meta"
LINEAGE = {
    "accepted_input_id": "6af7ed94619fe1b4346974b4486afa03a8d1625a7820e92da0ff74d57208fe88",
    "accepted_game_sha256": "a5f7d83c7e6872fdd6099fdc299adb7d4fa03cbf465e526d6f5efcc35c2c281d",
    "guarded_game_input_sha256": "3124a2ed9cf458acee78b1beaf969590b184be452e2b3aa5a8852df82ff95d30",
    "raw_api_sha256": "564b74ec232e81af8fa4b65c17537a4d05890d9181281eab0bc28bd441a3a781",
    "adapted_api_sha256": "2bd973178c99bfcb4d20510e2d1eac7efa9dd6d698237f2edfa486171bc2f272",
    "observed_api_sha256": "7ec842ee2244590f9227c44280ebbb4a0debf9b83ad1958c045d68dec47e0af9",
    "composed_api_sha256": "9a3f9911697b4ce28a955dff09f618e0f2662083e56eeb28ff5b6ecc02b588f3",
    "composed_game_sha256": "1034a747e31a3b79554b9cb06f941c7acabaa9e0ee82c2a00abc4b24f9327c1c",
    "native_library_sha256": "bb5879b4eb38b81dc3830a1662ba467b60b595e7fedb88a1301d3161f8ab9304",
    "stage_receipt_sha256": "8fe02400a7ab0905ae21b728e702d7ef2c4dcf8646f77f631682a81bda0ab88c",
}
PREVIOUS_COMPOSED_API_SHA256 = "793f22866c85bbcf104f20f5c1f619062eaad9f5414a217b602fe758c71e01b9"
PREVIOUS_LINEAGE = {
    "accepted_input_id": "6af7ed94619fe1b4346974b4486afa03a8d1625a7820e92da0ff74d57208fe88",
    "accepted_game_sha256": "a5f7d83c7e6872fdd6099fdc299adb7d4fa03cbf465e526d6f5efcc35c2c281d",
    "guarded_game_input_sha256": "3124a2ed9cf458acee78b1beaf969590b184be452e2b3aa5a8852df82ff95d30",
    "raw_api_sha256": "564b74ec232e81af8fa4b65c17537a4d05890d9181281eab0bc28bd441a3a781",
    "adapted_api_sha256": "2bd973178c99bfcb4d20510e2d1eac7efa9dd6d698237f2edfa486171bc2f272",
    "observed_api_sha256": "7ec842ee2244590f9227c44280ebbb4a0debf9b83ad1958c045d68dec47e0af9",
    "composed_api_sha256": PREVIOUS_COMPOSED_API_SHA256,
    "composed_game_sha256": "1034a747e31a3b79554b9cb06f941c7acabaa9e0ee82c2a00abc4b24f9327c1c",
    "native_library_sha256": "bb5879b4eb38b81dc3830a1662ba467b60b595e7fedb88a1301d3161f8ab9304",
    "stage_receipt_sha256": "8fe02400a7ab0905ae21b728e702d7ef2c4dcf8646f77f631682a81bda0ab88c",
}
ALLOWED_RESTORE_PREIMAGES = {
    "restore_api": frozenset({PREVIOUS_COMPOSED_API_SHA256, LINEAGE["composed_api_sha256"]}),
    "restore_game": frozenset({LINEAGE["composed_game_sha256"]}),
}
RESTORE_HASHES = {
    "restore_api": "107295e478a58ef295a83228111f375c536861bc9081f482d638c59899bf495c",
    "restore_game": "3124a2ed9cf458acee78b1beaf969590b184be452e2b3aa5a8852df82ff95d30",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def safe_relative(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("manifest path must be a string")
    path = PurePosixPath(value)
    if path.is_absolute() or not path.parts or ".." in path.parts or "\\" in value or path.as_posix() != value:
        raise ValueError(f"unsafe manifest path: {value!r}")
    return value


def no_symlink_path(path: Path, *, allow_missing: bool = False) -> None:
    absolute = Path(os.path.abspath(path))
    cursor = Path(absolute.anchor)
    for part in absolute.parts[1:]:
        cursor /= part
        try:
            if stat.S_ISLNK(cursor.lstat().st_mode):
                raise ValueError(f"symlink component refused: {cursor}")
        except FileNotFoundError:
            if not allow_missing:
                raise


def verify_request(manifest: dict, request_path: Path | None) -> dict:
    request = manifest.get("request")
    if not isinstance(request, dict) or type(request.get("requested")) is not bool:
        raise ValueError("artifact manifest must state request.requested as a boolean")
    if not request["requested"]:
        if request_path is not None:
            raise ValueError("a request file was supplied but the artifact set is default-off")
        return {"requested": False, "request_sha256": None}
    if request_path is None:
        raise ValueError("requested audio variant requires an explicit request file")
    no_symlink_path(request_path)
    raw = request_path.read_bytes()
    value = json.loads(raw)
    if not isinstance(value, dict) or value.get("schema") != "game-audio-original-runtime-request-r2":
        raise ValueError("unsupported runtime request schema")
    if value.get("requested") is not True:
        raise ValueError("request file must explicitly opt in")
    if value.get("request_id") != request.get("request_id"):
        raise ValueError("request identity does not match compiled artifact set")
    if value.get("build_input_contract_sha256") != request.get("build_input_contract_sha256"):
        raise ValueError("request build-input contract differs from compiled artifact set")
    if not HASH.fullmatch(str(request.get("build_input_contract_sha256", ""))):
        raise ValueError("request build-input contract hash is malformed")
    return {"requested": True, "request_sha256": hashlib.sha256(raw).hexdigest()}


def verify_bank_receipt(receipt_path: Path, rows: list[dict]) -> str:
    no_symlink_path(receipt_path)
    raw = receipt_path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != LINEAGE["stage_receipt_sha256"]:
        raise ValueError("bank stage receipt is not the exact accepted 153-bank cohort")
    receipt = json.loads(raw)
    outputs = receipt.get("outputs")
    if (
        receipt.get("schema") != "original-game-wwise-bank-cohort-r1"
        or receipt.get("accepted_input_id") != LINEAGE["accepted_input_id"]
        or receipt.get("requested_banks") != 153
        or not isinstance(outputs, list)
        or len(outputs) != 154
    ):
        raise ValueError("bank stage receipt has the wrong input or cohort cardinality")
    expected = {}
    for row in outputs:
        filename = row.get("filename")
        if not isinstance(filename, str) or Path(filename).name != filename or filename in expected:
            raise ValueError("bank stage receipt has an invalid or duplicate output name")
        expected[filename] = row
    if "Init.bnk" not in expected or sum(name != "Init.bnk" for name in expected) != 153:
        raise ValueError("bank receipt must bind Init plus 153 original bank names")
    actual = {}
    for row in rows:
        filename = row.get("filename")
        if not isinstance(filename, str) or PurePosixPath(row["target_relative"]).name != filename:
            raise ValueError("bank target filename differs from stage receipt row")
        if filename in actual:
            raise ValueError("duplicate staged bank filename")
        actual[filename] = row
    if set(actual) != set(expected):
        raise ValueError("staged bank names differ from the exact accepted receipt")
    for filename, row in expected.items():
        staged = actual[filename]
        if row.get("sha256") != staged["sha256"] or row.get("size_bytes") != staged.get("size_bytes"):
            raise ValueError(f"staged bank differs from accepted receipt: {filename}")
    return hashlib.sha256(raw).hexdigest()


def validate_plugin_metadata(rows: list[dict]) -> dict[str, str]:
    metadata = [row for row in rows if row["role"] == "metadata"]
    guids: dict[str, str] = {}
    for row in metadata:
        content = row["source_path"].read_text(encoding="utf-8")
        match = re.search(r"(?m)^guid: ([0-9a-f]{32})$", content)
        if not content.startswith("fileFormatVersion: 2\n") or not match or "PluginImporter:" not in content:
            raise ValueError(f"invalid Unity plugin importer metadata: {row['source_relative']}")
        guid = match.group(1)
        if guid in guids:
            raise ValueError("plugin importer GUID is duplicated in artifact set")
        guids[guid] = row["target_relative"]
    return guids


def read_artifacts(manifest_path: Path, request_path: Path | None, stage_receipt_path: Path | None) -> tuple[dict, list[dict], dict]:
    no_symlink_path(manifest_path)
    work_root = (ROOT / "work").resolve(strict=True)
    if not manifest_path.resolve(strict=True).is_relative_to(work_root):
        raise ValueError("artifact manifest must be under ignored work/")
    manifest_bytes = manifest_path.read_bytes()
    manifest = json.loads(manifest_bytes)
    if not isinstance(manifest, dict) or manifest.get("schema") != SCHEMA:
        raise ValueError("unsupported original-audio artifact manifest")
    lineage = manifest.get("lineage")
    if not isinstance(lineage, dict):
        raise ValueError("artifact set must include its complete source lineage")
    if manifest.get("accepted_input_id") != LINEAGE["accepted_input_id"] or lineage.get("accepted_input_id") != LINEAGE["accepted_input_id"]:
        raise ValueError("artifact set is not bound to the accepted input")
    for key, expected in LINEAGE.items():
        if key != "accepted_input_id" and not HASH.fullmatch(str(expected)):
            raise ValueError(f"current audio lineage pin is not finalized: {key}")
        if key != "accepted_input_id" and lineage.get(key) != expected:
            raise ValueError(f"artifact lineage differs from current accepted transformation: {key}")
    request = verify_request(manifest, request_path)
    if request["requested"] and stage_receipt_path is None:
        raise ValueError("opt-in staging requires the exact accepted bank stage receipt")
    if not request["requested"] and stage_receipt_path is not None:
        raise ValueError("default-off staging must not consume bank receipt or require bank inputs")
    source_root_value = manifest.get("source_root")
    if source_root_value is None:
        artifacts_root = manifest_path.parent.resolve(strict=True)
        if not artifacts_root.is_relative_to(work_root):
            raise ValueError("manifest-relative artifacts must resolve under ignored work/")
    else:
        if source_root_value == ".":
            artifacts_root = (ROOT / "work").resolve(strict=True)
        else:
            source_root_value = safe_relative(source_root_value)
            artifacts_root = (ROOT / "work" / source_root_value).resolve(strict=True)
        work_root = (ROOT / "work").resolve(strict=True)
        if not artifacts_root.is_dir() or not artifacts_root.is_relative_to(work_root):
            raise ValueError("artifact source_root must resolve to a directory under ignored work/")
        no_symlink_path(artifacts_root)
    outputs = manifest.get("outputs")
    if not isinstance(outputs, list) or not outputs:
        raise ValueError("artifact manifest has no outputs")
    rows: list[dict] = []
    seen_targets: set[str] = set()
    roles: set[str] = set()
    for item in outputs:
        if not isinstance(item, dict):
            raise ValueError("artifact row must be an object")
        source_rel = safe_relative(item.get("source"))
        target_rel = safe_relative(item.get("target"))
        role = item.get("role")
        if not isinstance(role, str) or not role:
            raise ValueError("artifact role is missing")
        if target_rel in seen_targets:
            raise ValueError(f"duplicate target: {target_rel}")
        seen_targets.add(target_rel)
        source = artifacts_root / source_rel
        no_symlink_path(source)
        if not source.is_file() or not HASH.fullmatch(str(item.get("sha256", ""))):
            raise ValueError(f"artifact source/hash invalid: {source_rel}")
        if sha256(source) != item["sha256"]:
            raise ValueError(f"artifact bytes differ from manifest: {source_rel}")
        needs_request = item.get("requires_request", False)
        if type(needs_request) is not bool:
            raise ValueError("requires_request must be boolean")
        if needs_request and not request["requested"]:
            raise ValueError(f"default-off artifact set includes opt-in output: {role}")
        roles.add(role)
        rows.append({**item, "source_path": source, "source_relative": source_rel, "target_relative": target_rel})
    if roles - (DEFAULT_ROLES | OPT_IN_ROLES | RESTORE_ROLES | {"metadata"}):
        raise ValueError("artifact set contains an unknown output role")
    if not DEFAULT_ROLES.issubset(roles):
        raise ValueError("default-off artifact set must include observer/core/bootstrap")
    for role, target in DEFAULT_TARGETS.items():
        matches = [row for row in rows if row["role"] == role]
        if role in DEFAULT_ROLES and (len(matches) != 1 or matches[0]["target_relative"] != target):
            raise ValueError(f"artifact set must contain exactly one {role} assembly at its owned target")
        if request["requested"] and role in {"api", "game"} and (len(matches) != 1 or matches[0]["target_relative"] != target):
            raise ValueError(f"opt-in artifact set must contain exactly one {role} transformation at its owned target")
        if request["requested"] and role in {"api", "game"} and matches[0]["sha256"] != LINEAGE[f"composed_{role}_sha256"]:
            raise ValueError(f"opt-in {role} bytes differ from the current declared composed lineage")
    for role, target in (("restore_api", DEFAULT_TARGETS["api"]), ("restore_game", DEFAULT_TARGETS["game"])):
        matches = [row for row in rows if row["role"] == role]
        if matches and (
            len(matches) != 1 or matches[0]["target_relative"] != target or matches[0].get("preimage_sha256") not in ALLOWED_RESTORE_PREIMAGES[role]
        ):
            raise ValueError("default-off restoration lacks an exact declared predecessor target/preimage")
        if matches and matches[0]["sha256"] != RESTORE_HASHES[role]:
            raise ValueError(f"default-off restoration bytes are not the exact accepted {role} output")
    for target in NEW_ASSEMBLY_META:
        if not any(row["role"] == "metadata" and row["target_relative"] == target for row in rows):
            raise ValueError(f"new authored plugin assembly is missing importer metadata: {target}")
    expected_meta = NEW_ASSEMBLY_META | ({NATIVE_META} if request["requested"] else set())
    actual_meta = {row["target_relative"] for row in rows if row["role"] == "metadata"}
    if actual_meta != expected_meta:
        raise ValueError("plugin importer metadata membership differs from the owned assembly set")
    restore_present = roles & RESTORE_ROLES
    if restore_present and restore_present != RESTORE_ROLES:
        raise ValueError("default-off restoration must include both ordinary guarded game/API outputs")
    if not request["requested"] and any(role in OPT_IN_ROLES for role in roles):
        raise ValueError("default-off artifact set must not require API/game transformation or native/bank inputs")
    if request["requested"] and not (OPT_IN_ROLES | DEFAULT_ROLES).issubset(roles):
        raise ValueError("opt-in artifact set must include all exact API/game/native/bank outputs")
    if request["requested"]:
        banks = [row for row in rows if row["role"] == "banks"]
        if len(banks) != 154:
            raise ValueError("opt-in artifact set must stage Init plus all 153 named banks")
        if any(not row["target_relative"].startswith("Assets/StreamingAssets/Audio/GeneratedSoundBanks/Android/") for row in banks):
            raise ValueError("bank payload target is outside the exact Android Wwise cohort directory")
        receipt_sha = verify_bank_receipt(stage_receipt_path, banks)
        native = [row for row in rows if row["role"] == "native"]
        if len(native) != 1 or native[0]["sha256"] != LINEAGE["native_library_sha256"] or native[0]["target_relative"] != NATIVE_TARGET:
            raise ValueError("opt-in artifact set must contain the exact accepted ARM64 native library")
    if manifest.get("runtime_accepted") is not False or manifest.get("audible") is not False:
        raise ValueError("staging producer cannot accept runtime/audio readiness claims")
    plugin_guids = validate_plugin_metadata(rows)
    return (
        manifest,
        rows,
        {
            **request,
            "artifact_manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
            "stage_receipt_sha256": receipt_sha if request["requested"] else None,
            "plugin_guids": plugin_guids,
        },
    )


def install_one(project: Path, item: dict) -> dict:
    target = project / item["target_relative"]
    no_symlink_path(target, allow_missing=True)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        if target.is_symlink() or not target.is_file():
            raise ValueError(f"staging target is not a regular file: {item['target_relative']}")
        current = sha256(target)
        if current != item.get("preimage_sha256") and current != item["sha256"]:
            raise ValueError(f"project target drift; refusing overwrite: {item['target_relative']}")
        if current == item["sha256"]:
            return {"target": item["target_relative"], "sha256": current, "status": "already-identical"}
    elif item.get("preimage_sha256") not in (None, ""):
        raise ValueError(f"expected preimage is missing: {item['target_relative']}")
    with tempfile.NamedTemporaryFile(prefix=".original-audio-", dir=target.parent, delete=False) as tmp:
        temporary = Path(tmp.name)
        with item["source_path"].open("rb") as src:
            for block in iter(lambda: src.read(1024 * 1024), b""):
                tmp.write(block)
        tmp.flush()
        os.fsync(tmp.fileno())
    if sha256(temporary) != item["sha256"]:
        temporary.unlink(missing_ok=True)
        raise ValueError(f"staged copy hash mismatch: {item['target_relative']}")
    os.replace(temporary, target)
    return {"target": item["target_relative"], "sha256": item["sha256"], "status": "staged"}


def inspect_previous_stage(project: Path, receipt_path: Path) -> tuple[dict | None, list[Path]]:
    """Recognize this stager's prior receipt before changing its owned inputs."""
    native = project / NATIVE_TARGET
    bank_root = project / "Assets/StreamingAssets/Audio/GeneratedSoundBanks/Android"
    existing_payload: list[Path] = []
    for path in (native, project / NATIVE_META):
        if path.exists() or path.is_symlink():
            existing_payload.append(path)
    if bank_root.exists() or bank_root.is_symlink():
        no_symlink_path(bank_root)
        if not bank_root.is_dir():
            raise ValueError("Android bank payload path is not a directory")
        for path in bank_root.rglob("*"):
            if path.is_symlink():
                raise ValueError("symlink inside Android bank payload directory")
            if path.is_file():
                # Unity creates these importer sidecars after the first refresh.
                # They are editor-owned, excluded from StreamingAssets payload,
                # and deliberately neither overwritten nor deleted by this owner.
                if path.name.endswith(".bnk.meta"):
                    continue
                existing_payload.append(path)
            else:
                raise ValueError("unexpected directory or non-file entry inside Android bank payload directory")
    if not receipt_path.exists():
        if existing_payload:
            raise ValueError("unreceipted native or bank payload exists; refusing to overwrite or remove it")
        return None, []
    previous = json.loads(receipt_path.read_text(encoding="utf-8"))
    if (
        not isinstance(previous, dict)
        or previous.get("schema") != RECEIPT_SCHEMA
        or previous.get("accepted_input_id") != LINEAGE["accepted_input_id"]
        or previous.get("lineage") not in (LINEAGE, PREVIOUS_LINEAGE)
        or type(previous.get("requested")) is not bool
        or not isinstance(previous.get("outputs"), list)
        or not HASH.fullmatch(str(previous.get("artifact_manifest_sha256", "")))
    ):
        raise ValueError("existing original-audio stage receipt is unknown; preserve it and use a fresh project")
    rows = previous["outputs"]
    targets: dict[str, dict] = {}
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("target"), str):
            raise ValueError("existing stage receipt has malformed output rows")
        target = safe_relative(row["target"])
        if target in targets or not HASH.fullmatch(str(row.get("sha256", ""))):
            raise ValueError("existing stage receipt has duplicate targets or malformed hashes")
        targets[target] = row
        path = project / target
        no_symlink_path(path)
        if not path.is_file() or sha256(path) != row["sha256"]:
            raise ValueError(f"existing staged file differs from its receipt: {target}")
    expected_base = {target for role, target in DEFAULT_TARGETS.items() if role in DEFAULT_ROLES}
    expected_base.update(target + ".meta" for target in tuple(expected_base))
    if not expected_base.issubset(targets):
        raise ValueError("existing stage receipt does not contain its complete owner cohort")
    api_target, game_target = DEFAULT_TARGETS["api"], DEFAULT_TARGETS["game"]
    composed_api = previous["lineage"]["composed_api_sha256"]
    composed_game = previous["lineage"]["composed_game_sha256"]
    allowed_targets = set(expected_base) | {api_target, game_target}
    optional_targets = {NATIVE_TARGET, NATIVE_META}
    bank_targets = {target for target in targets if target.startswith("Assets/StreamingAssets/Audio/GeneratedSoundBanks/Android/")}
    meta_guids: dict[str, str] = {}
    for target in targets:
        if not target.endswith(".meta"):
            continue
        content = (project / target).read_text(encoding="utf-8")
        match = re.search(r"(?m)^guid: ([0-9a-f]{32})$", content)
        if not match or match.group(1) in meta_guids:
            raise ValueError("previous stage receipt has malformed or duplicate plugin GUID ownership")
        meta_guids[match.group(1)] = target
    if previous.get("plugin_guids") != meta_guids:
        raise ValueError("previous stage receipt plugin GUID ownership differs from its exact metadata files")
    if previous["requested"]:
        request_id = previous.get("request_id")
        request_sha = previous.get("request_sha256")
        if not isinstance(request_id, str) or not re.fullmatch(r"[0-9a-f]{32}", request_id) or not HASH.fullmatch(str(request_sha or "")):
            raise ValueError("previous opt-in receipt lacks a valid request identity")
        if previous.get("stage_receipt_sha256") != LINEAGE["stage_receipt_sha256"]:
            raise ValueError("previous opt-in receipt is not bound to the exact accepted bank cohort")
        if not optional_targets.issubset(targets) or len(bank_targets) != 154:
            raise ValueError("previous opt-in receipt does not own the complete native and 154-file bank cohort")
        bank_dir = "Assets/StreamingAssets/Audio/GeneratedSoundBanks/Android"
        if any(PurePosixPath(target).parent.as_posix() != bank_dir for target in bank_targets):
            raise ValueError("previous opt-in receipt owns a bank outside the direct Android cohort directory")
        if targets[NATIVE_TARGET]["sha256"] != LINEAGE["native_library_sha256"]:
            raise ValueError("previous opt-in receipt native library differs from the accepted pin")
        if targets.get(api_target, {}).get("sha256") != composed_api or targets.get(game_target, {}).get("sha256") != composed_game:
            raise ValueError("previous opt-in receipt API/game outputs differ from its exact declared lineage")
        bank_names = {PurePosixPath(target).name for target in bank_targets}
        if len(bank_names) != 154 or "Init.bnk" not in bank_names or any(not name.endswith(".bnk") for name in bank_names):
            raise ValueError("previous opt-in receipt bank names are not the exact unique cohort shape")
        allowed_targets.update(optional_targets | bank_targets)
        if set(targets) != allowed_targets:
            raise ValueError("previous opt-in receipt has outputs outside its exact owned cohort")
        remove = [project / target for target in sorted(optional_targets | bank_targets)]
        if set(existing_payload) != set(remove):
            raise ValueError("native or bank files exist outside the previous receipt's owned payload")
        return previous, remove
    if optional_targets.intersection(targets) or bank_targets or existing_payload:
        raise ValueError("default-off receipt conflicts with leftover native or bank payload")
    ordinary_pair = {api_target, game_target}
    if set(targets) not in (expected_base, expected_base | ordinary_pair):
        raise ValueError("existing default-off receipt has outputs outside its exact owner/restoration cohort")
    if bool(ordinary_pair & set(targets)) and not ordinary_pair.issubset(targets):
        raise ValueError("existing default-off receipt has an incomplete ordinary API/game restoration pair")
    if ordinary_pair.issubset(targets) and (
        targets[api_target]["sha256"] != RESTORE_HASHES["restore_api"] or targets[game_target]["sha256"] != RESTORE_HASHES["restore_game"]
    ):
        raise ValueError("previous default-off receipt does not own the exact ordinary API/game pair")
    return previous, []


def stage(project: Path, manifest_path: Path, request_path: Path | None, stage_receipt_path: Path | None) -> dict:
    project = project.resolve(strict=True)
    if not project.is_dir():
        raise ValueError("project must be an existing directory")
    no_symlink_path(project)
    manifest, rows, pins = read_artifacts(manifest_path, request_path, stage_receipt_path)
    receipt_path = project / "Assets/StreamingAssets/Lab/OriginalGameAudioStageReceipt.json"
    no_symlink_path(receipt_path, allow_missing=True)
    previous, remove_after_stage = inspect_previous_stage(project, receipt_path)
    if pins["requested"]:
        # The requested generation still owns the native and bank payload. The
        # prior receipt is validated for preimage ownership but nothing is removed.
        remove_after_stage = []
    if previous is not None:
        previous_outputs = {row["target"]: row["sha256"] for row in previous["outputs"]}
        for item in rows:
            target = item["target_relative"]
            existing = project / target
            prior_hash = previous_outputs.get(target)
            if existing.exists() and prior_hash is not None and sha256(existing) == prior_hash:
                supplied_preimage = item.get("preimage_sha256")
                if supplied_preimage not in (None, prior_hash):
                    raise ValueError(f"artifact preimage conflicts with prior stage ownership: {target}")
                item["preimage_sha256"] = prior_hash
    target_metas = {row["target_relative"] for row in rows if row["role"] == "metadata"}
    existing_guids = set()
    for meta in project.rglob("*.meta"):
        if meta.relative_to(project).as_posix() in target_metas:
            continue
        try:
            match = re.search(r"(?m)^guid: ([0-9a-f]{32})$", meta.read_text(encoding="utf-8"))
        except (UnicodeDecodeError, OSError):
            continue
        if match:
            existing_guids.add(match.group(1))
    if existing_guids.intersection(pins["plugin_guids"]):
        raise ValueError("plugin importer GUID collides with an existing project GUID")
    # Validate every destination before the first write, so drift cannot result
    # in a partially applied new generation.
    for item in rows:
        target = project / item["target_relative"]
        no_symlink_path(target, allow_missing=True)
        if target.exists():
            if not target.is_file() or target.is_symlink():
                raise ValueError(f"invalid staging target: {item['target_relative']}")
            if sha256(target) not in (item.get("preimage_sha256"), item["sha256"]):
                raise ValueError(f"project target drift; refusing generation: {item['target_relative']}")
    planned = []
    for item in rows:
        target = project / item["target_relative"]
        already_identical = target.is_file() and sha256(target) == item["sha256"]
        planned.append({"target": item["target_relative"], "sha256": item["sha256"], "status": "already-identical" if already_identical else "staged"})
    receipt = {
        "schema": RECEIPT_SCHEMA,
        "accepted_input_id": manifest["accepted_input_id"],
        "lineage": manifest["lineage"],
        "requested": pins["requested"],
        "request_id": manifest.get("request", {}).get("request_id") if pins["requested"] else None,
        "request_sha256": pins["request_sha256"],
        "artifact_manifest_sha256": pins["artifact_manifest_sha256"],
        "stage_receipt_sha256": pins["stage_receipt_sha256"],
        "plugin_guids": pins["plugin_guids"],
        "artifact_set_id": manifest.get("artifact_set_id"),
        "outputs": planned,
        "runtime_accepted": False,
        "audible": False,
    }
    if previous is not None and not pins["requested"] and previous["requested"] and not remove_after_stage:
        raise ValueError("requested-to-default transition lacks its complete receipt-owned payload")
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    encoded = (json.dumps(receipt, sort_keys=True, indent=2) + "\n").encode()
    staged = [install_one(project, item) for item in rows]
    if staged != planned:
        raise ValueError("project target changed during audio staging")
    for path in remove_after_stage:
        path.unlink()
    with tempfile.NamedTemporaryFile(prefix=".original-audio-receipt-", dir=receipt_path.parent, delete=False) as stream:
        temporary = Path(stream.name)
        stream.write(encoded)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, receipt_path)
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--artifact-manifest", type=Path, required=True)
    parser.add_argument("--request", type=Path)
    parser.add_argument("--stage-receipt", type=Path)
    args = parser.parse_args()
    try:
        result = stage(args.project, args.artifact_manifest, args.request, args.stage_receipt)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        parser.error(str(error))
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
