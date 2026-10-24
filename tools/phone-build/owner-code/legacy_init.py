"""Execute the exact authored historical Init source after full owner admission.

Historical receipt compatibility only. New applications should use the current
source-driven wwise_init_platform owner. No runtime routing approval is inferred.
"""

import argparse
import importlib.util
import json
from pathlib import Path
import sys
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
SPEC = importlib.util.spec_from_file_location("owner_legacy_native_support", HERE / "native.py")
native = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(native)
TEMPLATE = ROOT / "tools/phone-build/legacy/transform_init.py.txt"
TEMPLATE_SHA = "91c72d254ba9473d93ffb18c4be2233be1781b6072b08571aed7f607e76e9b37"
INPUT_ID = "6af7ed94619fe1b4346974b4486afa03a8d1625a7820e92da0ff74d57208fe88"
BANK = "Risk of Rain 2_Data/StreamingAssets/Audio/GeneratedSoundBanks/Windows/Init.bnk"
BANK_SHA = "3182093b59cf48034b2715b224f3f217b34eaecf104d10940528ea20c4baffc6"


def run(work, output):
    work, output = native.canonical(work), Path(output)
    # The exact archived producer's root/path guard requires this repository layout.
    if work != ROOT / "work":
        raise ValueError("historical Init compatibility requires this checkout's owner work")
    state = native.input_state(work)
    if state[0] != INPUT_ID:
        raise ValueError("historical Init input is not the reviewed accepted inventory")
    source = native.canonical(state[1] / BANK)
    if native.sha(TEMPLATE) != TEMPLATE_SHA or native.sha(source) != BANK_SHA:
        raise ValueError("historical Init source/template drift")
    if not output.is_relative_to(work) or output == work:
        raise ValueError("new historical Init output must be inside owner work")
    tool_parent = work / "legacy-init-tools"
    native.disjoint(output, [state[1], source, TEMPLATE, work / "config", work / "inventory", tool_parent])
    output.mkdir(mode=0o700)
    result = {
        "schema": 1,
        "success": False,
        "input_id": state[0],
        "historical_source_sha256": TEMPLATE_SHA,
        "phone_qualified": False,
        "runtime_routing_qualified": False,
    }
    try:
        for name in ("logs", "tmp"):
            (output / name).mkdir()
        tool_parent.mkdir(exist_ok=True)
        if native.canonical(tool_parent) != tool_parent:
            raise ValueError("historical tool parent redirected")
        materialized = Path(tempfile.mkdtemp(prefix="owner-", dir=tool_parent)) / "transform_init.py"
        with materialized.open("xb") as stream:
            stream.write(TEMPLATE.read_bytes())
        if materialized.parents[3] != ROOT or native.sha(materialized) != TEMPLATE_SHA:
            raise ValueError("historical tool bytes/root layout differ")
        result["materialized_source"] = str(materialized)
        native.invoke(
            [sys.executable, "-I", "-B", str(materialized), str(source), str(output / "Init.bnk"), "--receipt", str(output / "receipt.json")],
            output,
            "historical-init",
        )
        receipt = json.loads((output / "receipt.json").read_text())
        if receipt["transform_sha256"] != TEMPLATE_SHA or receipt["input_sha256"] != BANK_SHA or native.sha(output / "Init.bnk") != receipt["output_sha256"]:
            raise ValueError("historical Init execution receipt differs")
        if (
            native.sha(TEMPLATE) != TEMPLATE_SHA
            or native.sha(materialized) != TEMPLATE_SHA
            or native.sha(source) != BANK_SHA
            or native.input_state(work) != state
        ):
            raise ValueError("historical Init inputs changed during execution")
        result.update(success=True, output_sha256=receipt["output_sha256"], receipt_sha256=native.sha(output / "receipt.json"))
    except BaseException as error:
        result.update(error_type=type(error).__name__, error=str(error))
        raise
    finally:
        native.write(output / "result.json", result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--owner-work", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(run(args.owner_work, args.output), indent=2))


if __name__ == "__main__":
    main()
