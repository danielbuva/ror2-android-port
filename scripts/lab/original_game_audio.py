#!/usr/bin/env python3
"""Build and stage the original audio owner for one explicit request variant."""

from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path
import sys


HERE = Path(__file__).resolve().parent
PRODUCER_PATH = HERE / "original_game_audio_produce.py"
STAGER_PATH = HERE / "original_game_audio_stage.py"


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load authored owner: {path.name}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--variant", choices=("default-off", "requested"), default="default-off")
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--unity-contents", type=Path, required=True)
    parser.add_argument("--mono", type=Path, required=True)
    parser.add_argument("--csc", type=Path, required=True)
    parser.add_argument("--artifact-output", type=Path, required=True)
    parser.add_argument("--dotnet", type=Path)
    parser.add_argument("--managed-producer", type=Path)
    parser.add_argument("--android-source", type=Path)
    parser.add_argument("--android-os-string-source", type=Path)
    parser.add_argument("--native-library", type=Path)
    parser.add_argument("--abi-native-plugin", type=Path)
    parser.add_argument("--llvm-nm", type=Path)
    parser.add_argument("--request", type=Path)
    parser.add_argument("--input-contract", type=Path)
    parser.add_argument("--request-id")
    parser.add_argument("--stage-receipt", type=Path)
    parser.add_argument("--stage-root", type=Path)
    parser.add_argument("--prefab", type=Path)
    parser.add_argument("--bank-index", type=Path)
    parser.add_argument("--adapted-init", type=Path)
    parser.add_argument("--init-receipt", type=Path)
    args = parser.parse_args()
    try:
        producer = load(PRODUCER_PATH, "audio_owner_producer")
        stager = load(STAGER_PATH, "audio_owner_stager")
        common = (
            args.project.resolve(strict=True),
            args.unity_contents.resolve(strict=True),
            args.mono.resolve(strict=True),
            args.csc.resolve(strict=True),
        )
        output = args.artifact_output.resolve(strict=False)
        if args.variant == "default-off":
            result = producer.compile_default_off(*common, output)
            receipt = stager.stage(args.project, output / "artifact-manifest.json", None, None)
        else:
            requested = {
                "dotnet": args.dotnet,
                "managed_producer": args.managed_producer,
                "android_source": args.android_source,
                "android_os_string_source": args.android_os_string_source,
                "native_library": args.native_library,
                "abi_native_plugin": args.abi_native_plugin,
                "llvm_nm": args.llvm_nm,
                "request_path": args.request,
                "input_contract_path": args.input_contract,
                "stage_receipt_path": args.stage_receipt,
                "stage_root": args.stage_root,
                "prefab": args.prefab,
                "bank_index": args.bank_index,
                "adapted_init": args.adapted_init,
                "init_receipt": args.init_receipt,
            }
            missing = [name for name, value in requested.items() if value is None and name not in {"request_path", "input_contract_path"}]
            if (args.request is None) != (args.input_contract is None):
                missing.append("request and input contract must be supplied together")
            if args.request is None and not args.request_id:
                missing.append("request-id (to generate the noncircular contract and request during this invocation)")
            if missing:
                parser.error("requested variant requires: " + ", ".join(missing))
            result = producer.compile_requested(
                *common,
                args.dotnet.resolve(strict=True),
                args.managed_producer.resolve(strict=True),
                args.android_source.resolve(strict=True),
                args.android_os_string_source.resolve(strict=True),
                args.native_library.resolve(strict=True),
                args.abi_native_plugin.resolve(strict=True),
                args.llvm_nm.resolve(strict=True),
                args.request.resolve(strict=True) if args.request else None,
                args.input_contract.resolve(strict=True) if args.input_contract else None,
                args.stage_receipt.resolve(strict=True),
                args.stage_root.resolve(strict=True),
                args.prefab.resolve(strict=True),
                args.bank_index.resolve(strict=True),
                args.adapted_init.resolve(strict=True),
                args.init_receipt.resolve(strict=True),
                output,
                args.request_id,
            )
            request_file = args.request.resolve(strict=True) if args.request else output / "generated/request.json"
            receipt = stager.stage(args.project, output / "artifact-manifest.json", request_file, args.stage_receipt)
    except (OSError, ValueError, RuntimeError) as error:
        print(f"audio owner staging refused: {error}", file=sys.stderr)
        return 2
    print(f"compiled owner variant={result['variant']} references={result.get('reference_count', 'request-bound')}")
    print(f"project staged requested={receipt['requested']} runtime_accepted={receipt['runtime_accepted']} audible={receipt['audible']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
