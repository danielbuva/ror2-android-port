"""Compare the owner-derived pixel and object bytes against a pinned Android reference."""

import argparse
from collections import defaultdict
from contextlib import closing
import ctypes
import hashlib
import json
from pathlib import Path
import random
import subprocess
import time
from types import SimpleNamespace
from unittest.mock import patch

import lz4.block
from UnityPy.enums.TextureFormat import TextureFormat

import player_ui


T = player_ui.T
READER = player_ui.W.B
SEED = 20261127
STRATA = {
    "etc1": 12,
    "etc1-mips": 9,
    "cube-hdr": 2,
    "sdk-rgba": 9,
    "sdk-rgba-mips": 8,
    "copy": 9,
    "dilate-rgba": 1,
}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def source_pairs(audit, recipes):
    """Join explicit selectors and body hashes before choosing the sample."""
    targets = {}
    with (audit / "objects.jsonl").open() as stream:
        for line in stream:
            row = json.loads(line)
            if row["class_id"] in (28, 89) and row.get("source"):
                targets[tuple(row["target"])] = row
    pools = defaultdict(dict)
    for recipe in recipes:
        for bundle in json.loads(recipe.read_text())["bundles"]:
            for member in bundle["members"]:
                for texture in member["textures"]:
                    operation = texture["operation"]
                    if operation not in STRATA or max(texture["width"], texture["height"]) > 256:
                        continue
                    for target in texture["outputs"]:
                        key = (target["bundle"], target["member"], target["path_id"])
                        row = targets.get(key)
                        source = [bundle["path"], member["name"], texture["path_id"]]
                        if row and row["target_sha256"] == target["sha256"] and row["source_sha256"] == texture["sha256"] and row["source"] == source:
                            pools[operation].setdefault(key, (bundle, member["name"], texture, target))
    rng = random.Random(SEED)
    for operation, count in STRATA.items():
        choices = list(pools[operation].values())
        rng.shuffle(choices)
        bundles = set()
        sources = set()
        diverse, remaining = [], []
        for pair in choices:
            bundle, member, texture, _ = pair
            source = (bundle["path"], member, texture["path_id"])
            if source in sources:
                continue
            sources.add(source)
            group = remaining if source[0] in bundles else diverse
            group.append(pair)
            bundles.add(source[0])
        if len(sources) < count:
            raise ValueError(f"{operation}: only {len(sources)} of {count} hash-matched sources")
        yield from (diverse + remaining)[:count]


def read_pixels(asset, fields):
    inline = bytes(fields["image data"])
    stream = fields["m_StreamData"]
    if stream["size"]:
        if inline:
            raise ValueError("target has both inline and streamed image bytes")
        with asset.bundle.member(stream["path"].rsplit("/", 1)[-1]) as storage:
            storage.seek(stream["offset"])
            return READER.exact(storage, stream["size"])
    return inline


class Etcpak:
    """Host-only adapter for the pinned public encoder's BGRA block entry point."""

    def __init__(self, library, etc):
        self.encode_block = ctypes.CDLL(str(library.resolve(strict=True))).encode_block
        self.encode_block.argtypes = (ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int)
        self.encode_block.restype = None
        self.etc = str(etc)

    def encode(self, rgba, width, height, alpha):
        if width % 4 or height % 4 or len(rgba) != width * height * 4:
            raise ValueError("etcpak expects complete 4x4 blocks")
        bgra = bytearray(rgba)
        bgra[0::4], bgra[2::4] = rgba[2::4], rgba[0::4]
        encoded = bytearray()
        block = ctypes.create_string_buffer(16)
        for by in range(0, height, 4):
            for bx in range(0, width, 4):
                start = (by * width + bx) * 4
                pixels = b"".join(bgra[row : row + 16] for row in range(start, start + width * 16, width * 4))
                self.encode_block(pixels, block, alpha)
                encoded.extend(block.raw[: 16 if alpha else 8])
        return bytes(encoded)

    def rgba(self, rgba, width, height, sdk, etc_codec):
        return self.encode(rgba, width, height, True)

    def run(self, args, **kwargs):
        if args[0] != self.etc or args[-1] not in ("rgb", "normal"):
            return subprocess.run(args, **kwargs)
        width, height = map(int, args[1:3])
        rgb = kwargs["input"]
        rgba = bytearray(width * height * 4)
        rgba[0::4], rgba[1::4], rgba[2::4] = rgb[0::3], rgb[1::3], rgb[2::3]
        rgba[3::4] = b"\xff" * (width * height)
        return SimpleNamespace(returncode=0, stdout=self.encode(rgba, width, height, False))


def compare(args):
    started = time.monotonic()
    if READER.sha(args.apk) != args.apk_sha256:
        raise ValueError("reference APK hash differs")
    bundles = {row["bundle"]: row["reference_sha256"] for row in json.loads((args.audit / "target-hashes.json").read_text())}
    if any(READER.sha(args.payload / name) != sha for name, sha in bundles.items()):
        raise ValueError("reference payload hashes differ")
    sdk = {"pixels": str(args.pixel_tool), "command": [str(args.sdk_adapter), str(args.sdk_library)], "environment": {}}
    etcpak = Etcpak(args.etcpak, args.etc)
    py_decode = READER.decompress

    def decode(data, size, flags):
        if flags & 63 in (2, 3):
            decoded = lz4.block.decompress(data, uncompressed_size=size)
            if len(decoded) != size:
                raise ValueError("decompressed size differs")
            return decoded
        return py_decode(data, size, flags)

    rows = []
    with closing(player_ui.Sources(args.payload)) as reference, closing(player_ui.Sources(args.pc)) as original, patch.object(READER, "decompress", decode):
        for bundle, member, texture, target in source_pairs(args.audit, args.recipes):
            if target["bundle"] not in bundles:
                raise ValueError("target bundle missing from the verified reference audit")
            source = original.asset_file(args.pc / bundle["path"], (bundle["path"], member), bundle, member=member)
            body = source.objects[texture["path_id"]].get_raw_data()
            asset = reference.asset_file(args.payload / target["bundle"], (target["bundle"], target["member"]), member=target["member"])
            obj = asset.objects[target["path_id"]]
            raw = obj.get_raw_data()
            if digest(raw) != target["sha256"] or digest(body) != texture["sha256"]:
                raise ValueError("source or reference object body differs")
            fields = obj.read_typetree()
            expected = read_pixels(asset, fields)
            if len(expected) != target["pixel_bytes"] or digest(expected) != target["pixel_sha256"] or fields["m_StreamData"] != target["stream"]:
                raise ValueError("reference image bytes or storage descriptor differ")
            selected = {**texture, "outputs": [target]}
            operation = texture["operation"]
            current = T.pixels_input(source.bundle, body, selected, args.jpeg, args.etc, sdk)
            rebuilt_body = T.body_output(body, texture["fields"], current, target, operation)
            fmt = TextureFormat(fields["m_TextureFormat"])
            alternate = None
            if fmt.value in (34, 47):
                # Scope the substitute to the codec boundary. The shipped producer still
                # owns the decode, channel policy, mip filtering, tail padding and faces.
                with patch.object(T, "subprocess", SimpleNamespace(run=etcpak.run)), patch.object(T, "sdk_encode_rgba", etcpak.rgba):
                    alternate = T.pixels_input(source.bundle, body, selected, args.jpeg, args.etc, sdk)
            if len(current) != len(expected) or (alternate is not None and len(alternate) != len(expected)):
                raise ValueError("encoder output extent differs")
            rows.append(
                {
                    "source": [bundle["path"], member, texture["path_id"]],
                    "source_bundle_sha256": bundle["sha256"],
                    "source_body_sha256": texture["sha256"],
                    "target": [target["bundle"], target["member"], target["path_id"]],
                    "target_body_sha256": target["sha256"],
                    "target_pixel_sha256": target["pixel_sha256"],
                    "operation": operation,
                    "class_id": obj.type.value,
                    "format": fmt.name,
                    "width": texture["width"],
                    "height": texture["height"],
                    "mips": fields["m_MipCount"],
                    "pixel_bytes": len(expected),
                    "current_pixel_sha256": digest(current),
                    "current_pixel_exact": current == expected,
                    "current_body_exact": rebuilt_body == raw,
                    "etcpak_pixel_sha256": None if alternate is None else digest(alternate),
                    "etcpak_pixel_exact": None if alternate is None else alternate == expected,
                }
            )
    by_format = defaultdict(list)
    for row in rows:
        by_format[row["format"]].append(row)
    counts = {
        fmt: {
            "sample": len(group),
            "current_exact": sum(row["current_pixel_exact"] for row in group),
            "current_body_exact": sum(row["current_body_exact"] for row in group),
            "etcpak_sample": sum(row["etcpak_pixel_exact"] is not None for row in group),
            "etcpak_exact": sum(row["etcpak_pixel_exact"] is True for row in group),
        }
        for fmt, group in sorted(by_format.items())
    }
    tools = [args.etc, args.jpeg, args.pixel_tool, args.etcpak, args.sdk_adapter, args.sdk_library]
    return {
        "apk_sha256": args.apk_sha256,
        "reference_bundles": bundles,
        "recipe_hashes": {path.name: READER.sha(path) for path in args.recipes},
        "tool_hashes": {path.name: READER.sha(path) for path in tools},
        "seed": SEED,
        "counts": counts,
        "rows": rows,
        "seconds": time.monotonic() - started,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("pc", "apk", "payload", "audit", "etc", "jpeg", "pixel-tool", "sdk-adapter", "sdk-library", "etcpak", "output"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    parser.add_argument("--apk-sha256", required=True)
    parser.add_argument("--recipes", nargs="+", type=Path, required=True)
    args = parser.parse_args()
    result = compare(args)
    with args.output.open("x") as stream:
        json.dump(result, stream, indent=2)
        stream.write("\n")
    print(json.dumps(result["counts"], indent=2))


if __name__ == "__main__":
    main()
