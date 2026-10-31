"""Expose the existing source script registry as a receipt-pinned serialized phase."""

import argparse
import importlib.util
import io
import json
from pathlib import Path
import time

SPEC = importlib.util.spec_from_file_location("registry_player", Path(__file__).with_name("player_data.py"))
P = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(P)
NAME = "globalgamemanagers.assets"


def produce(profile_path, profile_sha256, pc, editor_resources, code_request, managed_production, output):
    profile_path = profile_path.resolve(strict=True)
    P.checked(profile_path, (profile_path.stat().st_size, profile_sha256))
    profile = json.loads(profile_path.read_text())
    if profile["input_id"] != P.INPUT_ID:
        raise ValueError("script registry input differs")
    pc = pc.resolve(strict=True)
    output = output.parent.resolve(strict=True) / output.name
    if output.exists() or output.is_symlink() or output.is_relative_to(pc) or pc.is_relative_to(output):
        raise ValueError("script registry output must be new and outside original input")
    output.mkdir()
    started = time.monotonic()
    receipt = {"success": False, "input_id": P.INPUT_ID, "profile_sha256": profile_sha256, "source_role": "pc-sdk-and-authored-script-registry"}
    try:
        value = P.registry_records(
            profile_path.parent,
            {"path": profile_path.name, "sha256": profile_sha256},
            pc,
            editor_resources,
            code_request,
            managed_production,
        )
        path = output / NAME
        with path.open("xb") as stream:
            P.W.write_serialized(stream, value["layout"], lambda row: io.BytesIO(value["bodies"][row["path_id"]]))
        for source, pin in value["provider_pins"].items():
            P.checked(Path(source), (pin["bytes"], pin["sha256"]))
        P.checked(profile_path, (profile_path.stat().st_size, profile_sha256))
        receipt.update(
            success=True,
            files={NAME: {"bytes": path.stat().st_size, "sha256": P.sha(path)}},
            scripts=len(value["script_ids"]),
            objects=len(value["layout"]["objects"]),
            provider_pins=value["provider_pins"],
        )
    except Exception as error:
        receipt["error"] = str(error)
        raise
    finally:
        receipt["seconds"] = time.monotonic() - started
        (output / "result.json").write_text(json.dumps(receipt, indent=2) + "\n")
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--profile-sha256", required=True)
    parser.add_argument("--pc", type=Path, required=True)
    parser.add_argument("--editor-resources", type=Path, required=True)
    parser.add_argument("--code-request", type=Path, required=True)
    parser.add_argument("--managed-production", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = produce(args.profile, args.profile_sha256, args.pc, args.editor_resources, args.code_request, args.managed_production, args.output)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
