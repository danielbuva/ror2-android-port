"""Produce qualified uncompressed Texture2D bodies/pixels from owner PC bundles."""

import argparse
from array import array
import hashlib
import importlib.util
import json
from pathlib import Path
import resource
import shutil
import struct
import subprocess
import sys
import time


def module(name):
    spec = importlib.util.spec_from_file_location("_texture_" + name, Path(__file__).with_name(name + ".py"))
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


BUNDLE = module("unity_bundle")
MESH = module("mesh_produce")


def dxt1_rgb(data, width, height):
    """Decode a BC1 top mip to RGB, retaining logical dimensions and row order."""
    if type(width) is not int or type(height) is not int or not 0 < width <= 8192 or not 0 < height <= 8192 or width * height * 3 > BUNDLE.LIMIT:
        raise ValueError("unqualified DXT1 dimensions")
    columns, rows = (width + 3) // 4, (height + 3) // 4
    if len(data) < columns * rows * 8:
        raise ValueError("truncated DXT1 top mip")
    output = bytearray(width * height * 3)

    def colour(value):
        red, green, blue = value >> 11, (value >> 5) & 63, value & 31
        return ((red << 3) | (red >> 2), (green << 2) | (green >> 4), (blue << 3) | (blue >> 2))

    for by in range(rows):
        for bx in range(columns):
            first, second, selectors = struct.unpack_from("<HHI", data, (by * columns + bx) * 8)
            a, b = colour(first), colour(second)
            palette = [a, b]
            if first > second:
                palette.extend((tuple((2 * x + y) // 3 for x, y in zip(a, b)), tuple((x + 2 * y) // 3 for x, y in zip(a, b))))
            else:
                palette.extend((tuple((x + y) // 2 for x, y in zip(a, b)), (0, 0, 0)))
            for y in range(min(4, height - by * 4)):
                for x in range(min(4, width - bx * 4)):
                    offset = ((by * 4 + y) * width + bx * 4 + x) * 3
                    output[offset : offset + 3] = bytes(palette[(selectors >> (2 * (y * 4 + x))) & 3])
    return bytes(output)


def dilate_rgba(data, width, height):
    """Extend source RGB by cardinal Manhattan jump flooding; preserve alpha."""
    if (
        type(width) is not int
        or type(height) is not int
        or not 0 < width <= 8192
        or not 0 < height <= 8192
        or width * height * 4 > BUNDLE.LIMIT
        or len(data) != width * height * 4
    ):
        raise ValueError("unqualified RGBA dilation dimensions")
    count = width * height
    coordinates = array("i", (index if data[index * 4 + 3] else -1 for index in range(count)))
    transparent = array("i", (index for index in range(count) if not data[index * 4 + 3]))
    for jump in (16, 8, 4, 2, 1):
        updated = array("i", coordinates)
        for index in transparent:
            x, y = index % width, index // width
            seed = coordinates[index]
            distance = abs(seed % width - x) + abs(seed // width - y) if seed >= 0 else count + width + height
            neighbors = (
                index - jump if x >= jump else -1,
                index + jump if x + jump < width else -1,
                index - jump * width if y >= jump else -1,
                index + jump * width if y + jump < height else -1,
            )
            for neighbor in neighbors:
                if neighbor < 0 or coordinates[neighbor] < 0:
                    continue
                candidate = coordinates[neighbor]
                candidate_distance = abs(candidate % width - x) + abs(candidate // width - y)
                if candidate_distance < distance:
                    seed, distance = candidate, candidate_distance
            updated[index] = seed
        coordinates = updated
    output = bytearray(data)
    for index in transparent:
        seed = coordinates[index]
        if seed >= 0:
            output[index * 4 : index * 4 + 3] = data[seed * 4 : seed * 4 + 3]
    return bytes(output)


def text(value):
    encoded = value.encode("utf-8")
    return struct.pack("<I", len(encoded)) + encoded + bytes(-len(encoded) % 4)


def field(body, fields, name):
    start, size = fields[name]
    if start < 0 or size < 0 or start + size > len(body):
        raise ValueError("texture field escapes source body")
    return body[start : start + size]


def body_output(body, fields, pixels, target, operation):
    required = {"m_Name", "m_CompleteImageSize", "m_TextureFormat", "m_IsAlphaChannelOptional", "m_LightmapFormat", "image data", "m_StreamData"}
    if set(fields) != required:
        raise ValueError("unknown texture field selection")
    for name in required:
        field(body, fields, name)
    replacements = {
        "m_Name": text(target["name"]),
        "m_CompleteImageSize": struct.pack("<I", len(pixels)),
        "m_IsAlphaChannelOptional": bytes([target["alpha_optional"]]) + field(body, fields, "m_IsAlphaChannelOptional")[1:],
        "m_LightmapFormat": struct.pack("<i", target["usage"]),
        "image data": struct.pack("<I", len(pixels)) + pixels + bytes(-len(pixels) % 4) if target["inline"] else bytes(4),
    }
    if operation in {"dxt1-rgb", "dxt1-rgb-jpeg"}:
        replacements["m_TextureFormat"] = struct.pack("<i", 3)
    stream = target["stream"]
    if target["inline"] or not pixels:
        if stream != {"offset": 0, "size": 0, "path": ""}:
            raise ValueError("unexpected empty texture stream")
    elif stream["size"] != len(pixels):
        raise ValueError("texture stream extent differs from produced pixels")
    replacements["m_StreamData"] = struct.pack("<QI", stream["offset"], stream["size"]) + text(stream["path"])
    result = bytearray()
    end = 0
    for name, (start, size) in sorted(fields.items(), key=lambda item: item[1][0]):
        if start < end:
            raise ValueError("overlapping texture fields")
        result.extend(body[end:start])
        result.extend(replacements.get(name, body[start : start + size]))
        end = start + size
    result.extend(body[end:])
    return bytes(result)


def pixels_input(bundle, body, selected, jpeg_codec=None):
    location = selected["pixels"]
    if location["member"] is None:
        start = location["offset"]
        if start < 0 or location["bytes"] < 0 or start + location["bytes"] > len(body):
            raise ValueError("texture pixels escape original body")
        pixels = body[start : start + location["bytes"]]
    else:
        stream = bundle.member(location["member"])
        stream.seek(location["offset"])
        pixels = BUNDLE.exact(stream, location["bytes"])
    if len(pixels) != location["bytes"] or hashlib.sha256(pixels).hexdigest() != location["sha256"]:
        raise ValueError("original texture pixels drift")
    operation = selected["operation"]
    if operation == "copy":
        return pixels
    if operation == "dilate-rgba":
        return dilate_rgba(pixels, selected["width"], selected["height"])
    if operation in {"dxt1-rgb", "dxt1-rgb-jpeg"}:
        pixels = dxt1_rgb(pixels, selected["width"], selected["height"])
        if operation == "dxt1-rgb":
            return pixels
    if operation in {"rgb-jpeg", "dxt1-rgb-jpeg"}:
        if jpeg_codec is None:
            raise ValueError("pinned public JPEG codec required")
        result = subprocess.run([str(jpeg_codec), str(selected["width"]), str(selected["height"])], input=pixels, capture_output=True, timeout=120)
        if result.returncode != 0 or len(result.stdout) != selected["width"] * selected["height"] * 3:
            raise ValueError("public JPEG codec failed or returned a different pixel extent")
        return result.stdout
    raise ValueError("unqualified texture operation")


def produce(profile_path, profile_sha256, pc, output, jpeg_codec=None, jpeg_codec_sha256=None):
    if BUNDLE.sha(profile_path) != profile_sha256:
        raise ValueError("texture profile drift")
    profile = json.loads(profile_path.read_text())
    if set(profile) != {"input_id", "bundles"} or profile["input_id"] != MESH.INPUT_ID:
        raise ValueError("unknown texture input")
    pc = pc.resolve(strict=True)
    needs_jpeg = any(
        texture["operation"] in {"rgb-jpeg", "dxt1-rgb-jpeg"} for bundle in profile["bundles"] for member in bundle["members"] for texture in member["textures"]
    )
    if needs_jpeg or jpeg_codec is not None or jpeg_codec_sha256 is not None:
        if jpeg_codec is None or jpeg_codec_sha256 is None:
            raise ValueError("pinned public JPEG codec required")
        jpeg_codec = jpeg_codec.resolve(strict=True)
        if jpeg_codec.is_relative_to(pc) or BUNDLE.sha(jpeg_codec) != jpeg_codec_sha256:
            raise ValueError("public JPEG codec drift or overlap with original input")
    parent = output.parent.resolve(strict=True)
    output = parent / output.name
    if output.name in ("", ".", "..") or output.exists() or output.is_symlink() or parent.is_relative_to(pc) or pc.is_relative_to(output):
        raise ValueError("texture output must be new and outside original input")
    expected = sum(
        target["bytes"] + (target["pixel_bytes"] if not target["inline"] else 0)
        for bundle in profile["bundles"]
        for member in bundle["members"]
        for texture in member["textures"]
        for target in texture["outputs"]
    )
    if shutil.disk_usage(parent).free < expected + 2 * 1024**3:
        raise ValueError("insufficient texture output capacity")
    output.mkdir()
    started = time.monotonic()
    receipt = {"success": False, "input_id": MESH.INPUT_ID, "profile_sha256": profile_sha256, "objects": 0, "object_bytes": 0, "resource_bytes": 0}
    if jpeg_codec is not None:
        receipt["jpeg_codec_sha256"] = jpeg_codec_sha256
    try:
        with (output / "objects.bin").open("xb") as objects, (output / "resources.bin").open("xb") as resources, (output / "index.jsonl").open("x") as index:
            for selected_bundle in profile["bundles"]:
                path = MESH.safe_input(pc, selected_bundle["path"])
                before = path.stat()
                if BUNDLE.sha(path) != selected_bundle["sha256"]:
                    raise ValueError("original texture bundle drift")
                bundle = BUNDLE.Bundle(path)
                for selected_member in selected_bundle["members"]:
                    member = bundle.member(selected_member["name"])
                    for selected in selected_member["textures"]:
                        member.seek(selected["offset"])
                        body = BUNDLE.exact(member, selected["bytes"])
                        if hashlib.sha256(body).hexdigest() != selected["sha256"]:
                            raise ValueError("original texture body drift")
                        pixels = pixels_input(bundle, body, selected, jpeg_codec)
                        pixel_sha = hashlib.sha256(pixels).hexdigest()
                        for target in selected["outputs"]:
                            if pixel_sha != target["pixel_sha256"] or len(pixels) != target["pixel_bytes"]:
                                raise ValueError("produced texture pixels differ from accepted hash")
                            result = body_output(body, selected["fields"], pixels, target, selected["operation"])
                            digest = hashlib.sha256(result).hexdigest()
                            if len(result) != target["bytes"] or digest != target["sha256"]:
                                raise ValueError("produced texture body differs from accepted hash")
                            row = {
                                "bundle": target["bundle"],
                                "member": target["member"],
                                "path_id": target["path_id"],
                                "offset": objects.tell(),
                                "bytes": len(result),
                                "sha256": digest,
                            }
                            objects.write(result)
                            if not target["inline"] and pixels:
                                row["resource"] = {"offset": resources.tell(), "bytes": len(pixels), "sha256": pixel_sha, "stream": target["stream"]}
                                resources.write(pixels)
                                receipt["resource_bytes"] += len(pixels)
                            index.write(json.dumps(row, sort_keys=True) + "\n")
                            receipt["objects"] += 1
                            receipt["object_bytes"] += len(result)
                after = path.stat()
                if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns) or BUNDLE.sha(path) != selected_bundle["sha256"]:
                    raise ValueError("original texture input changed during production")
        with (output / "objects.bin").open("rb") as objects, (output / "resources.bin").open("rb") as resources, (output / "index.jsonl").open() as index:
            for line in index:
                row = json.loads(line)
                for stream, extent in ((objects, row), (resources, row.get("resource"))):
                    if extent is not None:
                        stream.seek(extent["offset"])
                        if hashlib.sha256(BUNDLE.exact(stream, extent["bytes"])).hexdigest() != extent["sha256"]:
                            raise ValueError("persisted texture extent drift")
        if jpeg_codec is not None and BUNDLE.sha(jpeg_codec) != jpeg_codec_sha256:
            raise ValueError("public JPEG codec changed during production")
        receipt["outputs"] = {
            name: {"bytes": (output / name).stat().st_size, "sha256": BUNDLE.sha(output / name)} for name in ("objects.bin", "resources.bin", "index.jsonl")
        }
        receipt["success"] = True
        return receipt
    except Exception as error:
        receipt["error"] = type(error).__name__ + ": " + str(error)
        raise
    finally:
        receipt["seconds"] = time.monotonic() - started
        receipt["peak_rss_bytes"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * (1 if sys.platform == "darwin" else 1024)
        (output / "result.json").write_text(json.dumps(receipt, indent=2) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--profile-sha256", required=True)
    parser.add_argument("--pc", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--jpeg-codec", type=Path)
    parser.add_argument("--jpeg-codec-sha256")
    args = parser.parse_args()
    produce(args.profile, args.profile_sha256, args.pc, args.output, args.jpeg_codec, args.jpeg_codec_sha256)


if __name__ == "__main__":
    main()
