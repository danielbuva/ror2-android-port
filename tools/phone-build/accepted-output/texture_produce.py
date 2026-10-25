"""Produce qualified Texture2D bodies/pixels from owner PC bundles."""

import argparse
from array import array
from concurrent.futures import ThreadPoolExecutor
import hashlib
import importlib.util
import json
import math
import os
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


def dxt1_rgb(data, width, height, force_four_colours=False):
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
            if first > second or force_four_colours:
                palette.extend((tuple((2 * x + y) // 3 for x, y in zip(a, b)), tuple((x + 2 * y) // 3 for x, y in zip(a, b))))
            else:
                palette.extend((tuple((x + y) // 2 for x, y in zip(a, b)), (0, 0, 0)))
            for y in range(min(4, height - by * 4)):
                for x in range(min(4, width - bx * 4)):
                    offset = ((by * 4 + y) * width + bx * 4 + x) * 3
                    output[offset : offset + 3] = bytes(palette[(selectors >> (2 * (y * 4 + x))) & 3])
    return bytes(output)


def rgba_source(data, width, height, texture_format):
    """Decode the qualified PC formats to logical bottom-up RGBA bytes."""
    if type(width) is not int or type(height) is not int or not 0 < width <= 8192 or not 0 < height <= 8192 or width * height * 4 > BUNDLE.LIMIT:
        raise ValueError("unqualified source RGBA dimensions")
    count = width * height
    if texture_format == 4:
        if len(data) != count * 4:
            raise ValueError("unqualified RGBA32 extent")
        return data
    columns, rows = (width + 3) // 4, (height + 3) // 4
    if texture_format in (10, 12):
        stride = 16 if texture_format == 12 else 8
        if len(data) < columns * rows * stride:
            raise ValueError("truncated BC source")
        colours = b"".join(data[q + 8 : q + 16] for q in range(0, columns * rows * 16, 16)) if texture_format == 12 else data
        rgb = dxt1_rgb(colours, width, height, texture_format == 12)
    elif texture_format == 3:
        if len(data) != count * 3:
            raise ValueError("unqualified RGB24 extent")
        rgb = data
    elif texture_format == 9:
        if len(data) != count * 2:
            raise ValueError("unqualified R16 extent")
        rgb = bytearray(count * 3)
        rgb[0::3] = data[1::2]
    else:
        raise ValueError("unqualified source texture format")
    rgba = bytearray(count * 4)
    rgba[0::4], rgba[1::4], rgba[2::4], rgba[3::4] = rgb[0::3], rgb[1::3], rgb[2::3], bytes([255]) * count
    if texture_format in (10, 12):
        for by in range(rows):
            for bx in range(columns):
                start = (by * columns + bx) * stride
                if texture_format == 10:
                    first, second, selectors = struct.unpack_from("<HHI", data, start)
                    if first > second or not selectors & (selectors >> 1) & 0x55555555:
                        continue
                    alpha = [255, 255, 255, 0]
                    bits, mask = 2, 3
                else:
                    first, second = data[start : start + 2]
                    alpha = [first, second]
                    if first > second:
                        alpha += [((7 - i) * first + i * second) // 7 for i in range(1, 7)]
                    else:
                        alpha += [((5 - i) * first + i * second) // 5 for i in range(1, 5)] + [0, 255]
                    selectors = int.from_bytes(data[start + 2 : start + 8], "little")
                    bits, mask = 3, 7
                for y in range(min(4, height - by * 4)):
                    for x in range(min(4, width - bx * 4)):
                        rgba[((by * 4 + y) * width + bx * 4 + x) * 4 + 3] = alpha[(selectors >> (bits * (y * 4 + x))) & mask]
    return bytes(rgba)


def rgb_channels(rgba):
    rgb = bytearray(len(rgba) // 4 * 3)
    rgb[0::3], rgb[1::3], rgb[2::3] = rgba[0::4], rgba[1::4], rgba[2::4]
    return bytes(rgb)


def normal_rgb(rgba):
    """Unpack original AG normal coordinates using an integer square root."""
    rgb = bytearray(len(rgba) // 4 * 3)
    for q in range(0, len(rgba), 4):
        green, alpha = rgba[q + 1], rgba[q + 3]
        blue = (math.isqrt(max(0, 255**2 - (2 * alpha - 255) ** 2 - (2 * green - 255) ** 2)) + 255) // 2
        offset = q // 4 * 3
        rgb[offset : offset + 3] = bytes((alpha, green, blue))
    return bytes(rgb)


def jpeg_rgb(pixels, width, height, codec):
    if codec is None:
        raise ValueError("pinned public JPEG codec required")
    result = subprocess.run([str(codec), str(width), str(height)], input=pixels, capture_output=True, timeout=120)
    if result.returncode != 0 or len(result.stdout) != width * height * 3:
        raise ValueError("public JPEG codec failed or returned a different pixel extent")
    return result.stdout


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
    elif operation in {"alpha8-etc2", "sdk-rgba"}:
        replacements["m_TextureFormat"] = struct.pack("<i", 47)
    elif operation == "etc1":
        replacements["m_TextureFormat"] = struct.pack("<i", 34)
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


def sdk_inputs(path, pin, pc):
    if path is None or pin is None or BUNDLE.sha(path) != pin:
        raise ValueError("pinned SDK texture toolchain required or drifted")
    value = json.loads(path.read_text())
    if set(value) != {"command", "environment", "pixels", "inputs"} or not value["inputs"]:
        raise ValueError("unknown SDK texture toolchain")
    command = value["command"]
    if not isinstance(command, list) or len(command) < 2 or any(not isinstance(s, str) or not s or "\0" in s for s in command):
        raise ValueError("invalid explicit SDK texture command")
    if not isinstance(value["environment"], dict) or set(value["environment"]) - {"LD_LIBRARY_PATH"}:
        raise ValueError("unknown SDK texture environment")
    for name, expected in value["inputs"].items():
        item = Path(name)
        if not item.is_absolute() or not item.is_file() or item.resolve(strict=True).is_relative_to(pc) or BUNDLE.sha(item) != expected:
            raise ValueError("SDK texture tool input drift or overlap with original input")
    if any(name not in value["inputs"] for name in (command[0], command[-1], value["pixels"])):
        raise ValueError("SDK texture executable/library/decoder is not pinned")
    return value


def sdk_encode_rgba(rgba, width, height, sdk, etc_codec):
    """Combine native EAC alpha and bounded independent SDK ETC2 colour bands."""
    if etc_codec is None:
        raise ValueError("pinned public ETC codec required for SDK RGBA alpha")
    alpha = subprocess.run([str(etc_codec), str(width), str(height), "alpha8"], input=rgba[3::4], capture_output=True, timeout=120)
    if alpha.returncode or len(alpha.stdout) != width * height:
        raise ValueError("public ETC codec failed or returned a different pixel extent")
    band_height = min(max(4, ((height + 15) // 16) * 4), max(4, (262144 // width) // 4 * 4))

    def encode(row):
        rows = min(band_height, height - row)
        encoded = subprocess.run(
            [*sdk["command"], str(width), str(rows), "1", "0"],
            env={**os.environ, **sdk["environment"]},
            input=memoryview(rgba)[row * width * 4 : (row + rows) * width * 4],
            capture_output=True,
            timeout=120,
        )
        if encoded.returncode or len(encoded.stdout) != width * rows // 2:
            raise ValueError("SDK texture codec failed or returned a different extent")
        return encoded.stdout

    if height <= band_height:
        colours = encode(0)
    else:
        colours = bytearray()
        with ThreadPoolExecutor(max_workers=2) as workers:
            for row in range(0, height, band_height * 4):
                jobs = [workers.submit(encode, selected) for selected in range(row, min(height, row + band_height * 4), band_height)]
                for job in jobs:
                    colours.extend(job.result())
    output = bytearray(width * height)
    for offset in range(0, len(output), 16):
        output[offset : offset + 8] = alpha.stdout[offset : offset + 8]
        output[offset + 8 : offset + 16] = colours[offset // 2 : offset // 2 + 8]
    return bytes(output)


def pixels_input(bundle, body, selected, jpeg_codec=None, etc_codec=None, sdk=None):
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
    if operation == "sdk-rgba":
        if sdk is None:
            raise ValueError("pinned SDK texture toolchain required")
        width, height = selected["width"], selected["height"]
        fmt = struct.unpack("<i", field(body, selected["fields"], "m_TextureFormat"))[0]
        if fmt in (12, 25):
            top_bytes = ((width + 3) // 4) * ((height + 3) // 4) * 16
            if len(pixels) < top_bytes:
                raise ValueError("truncated BC top mip")
            decoded = subprocess.run(
                [sdk["pixels"], str(width), str(height), *(["bc3"] if fmt == 12 else [])], input=pixels[:top_bytes], capture_output=True, timeout=120
            )
            if decoded.returncode or len(decoded.stdout) != width * height * 4:
                raise ValueError("native BC decoder failed or returned a different extent")
            rgba = decoded.stdout
        else:
            rgba = rgba_source(pixels, width, height, fmt)
        if 0 in rgba[3::4]:
            dilated = subprocess.run([sdk["pixels"], str(width), str(height), "dilate"], input=rgba, capture_output=True, timeout=120)
            if dilated.returncode or len(dilated.stdout) != width * height * 4:
                raise ValueError("native pixel dilation failed or returned a different extent")
            rgba = dilated.stdout
        return sdk_encode_rgba(rgba, width, height, sdk, etc_codec)
    if operation in {"alpha8-etc2", "etc1"}:
        if etc_codec is None:
            raise ValueError("pinned public ETC codec required")
        width, height = selected["width"], selected["height"]
        count = width * height
        mode, output_size = "alpha8", count
        if operation == "alpha8-etc2":
            if len(pixels) != count:
                raise ValueError("unqualified Alpha8 source extent")
        else:
            fmt = struct.unpack("<i", field(body, selected["fields"], "m_TextureFormat"))[0]
            normal = struct.unpack("<i", field(body, selected["fields"], "m_LightmapFormat"))[0] == 3
            rgba = rgba_source(pixels, width, height, fmt)
            if normal:
                pixels = normal_rgb(rgba)
            else:
                if not selected["jpeg"] and 0 in rgba[3::4]:
                    rgba = dilate_rgba(rgba, width, height)
                pixels = rgb_channels(rgba)
            if selected["jpeg"]:
                pixels = jpeg_rgb(pixels, width, height, jpeg_codec)
            mode, output_size = "normal" if normal else "rgb", count // 2
        result = subprocess.run([str(etc_codec), str(width), str(height), mode], input=pixels, capture_output=True, timeout=120)
        if result.returncode != 0 or len(result.stdout) != output_size:
            raise ValueError("public ETC codec failed or returned a different pixel extent")
        return result.stdout
    if operation == "dilate-rgba":
        return dilate_rgba(pixels, selected["width"], selected["height"])
    if operation in {"dxt1-rgb", "dxt1-rgb-jpeg"}:
        pixels = dxt1_rgb(pixels, selected["width"], selected["height"])
        if operation == "dxt1-rgb":
            return pixels
    if operation in {"rgb-jpeg", "dxt1-rgb-jpeg"}:
        return jpeg_rgb(pixels, selected["width"], selected["height"], jpeg_codec)
    raise ValueError("unqualified texture operation")


def produce(
    profile_path,
    profile_sha256,
    pc,
    output,
    jpeg_codec=None,
    jpeg_codec_sha256=None,
    etc_codec=None,
    etc_codec_sha256=None,
    sdk_toolchain=None,
    sdk_toolchain_sha256=None,
):
    if BUNDLE.sha(profile_path) != profile_sha256:
        raise ValueError("texture profile drift")
    profile = json.loads(profile_path.read_text())
    if set(profile) != {"input_id", "bundles"} or profile["input_id"] != MESH.INPUT_ID:
        raise ValueError("unknown texture input")
    pc = pc.resolve(strict=True)
    needs_sdk = any(texture["operation"] == "sdk-rgba" for bundle in profile["bundles"] for member in bundle["members"] for texture in member["textures"])
    sdk = sdk_inputs(sdk_toolchain, sdk_toolchain_sha256, pc) if needs_sdk or sdk_toolchain is not None or sdk_toolchain_sha256 is not None else None
    needs_jpeg = any(
        texture["operation"] in {"rgb-jpeg", "dxt1-rgb-jpeg"} or (texture["operation"] == "etc1" and texture["jpeg"])
        for bundle in profile["bundles"]
        for member in bundle["members"]
        for texture in member["textures"]
    )
    if needs_jpeg or jpeg_codec is not None or jpeg_codec_sha256 is not None:
        if jpeg_codec is None or jpeg_codec_sha256 is None:
            raise ValueError("pinned public JPEG codec required")
        jpeg_codec = jpeg_codec.resolve(strict=True)
        if jpeg_codec.is_relative_to(pc) or BUNDLE.sha(jpeg_codec) != jpeg_codec_sha256:
            raise ValueError("public JPEG codec drift or overlap with original input")
    needs_etc = any(
        texture["operation"] in {"alpha8-etc2", "etc1", "sdk-rgba"}
        for bundle in profile["bundles"]
        for member in bundle["members"]
        for texture in member["textures"]
    )
    if needs_etc or etc_codec is not None or etc_codec_sha256 is not None:
        if etc_codec is None or etc_codec_sha256 is None:
            raise ValueError("pinned public ETC codec required")
        etc_codec = etc_codec.resolve(strict=True)
        if etc_codec.is_relative_to(pc) or BUNDLE.sha(etc_codec) != etc_codec_sha256:
            raise ValueError("public ETC codec drift or overlap with original input")
    parent = output.parent.resolve(strict=True)
    output = parent / output.name
    if output.name in ("", ".", "..") or output.exists() or output.is_symlink() or parent.is_relative_to(pc) or pc.is_relative_to(output):
        raise ValueError("texture output must be new and outside original input")
    if sdk and any(Path(name).is_relative_to(output) for name in sdk["inputs"]):
        raise ValueError("texture output overlaps SDK toolchain")
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
    if etc_codec is not None:
        receipt["etc_codec_sha256"] = etc_codec_sha256
    if sdk is not None:
        receipt["sdk_toolchain_sha256"] = sdk_toolchain_sha256
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
                        pixels = pixels_input(bundle, body, selected, jpeg_codec, etc_codec, sdk)
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
        if etc_codec is not None and BUNDLE.sha(etc_codec) != etc_codec_sha256:
            raise ValueError("public ETC codec changed during production")
        if sdk is not None and sdk_inputs(sdk_toolchain, sdk_toolchain_sha256, pc) != sdk:
            raise ValueError("SDK texture toolchain changed during production")
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
    parser.add_argument("--etc-codec", type=Path)
    parser.add_argument("--etc-codec-sha256")
    parser.add_argument("--sdk-toolchain", type=Path)
    parser.add_argument("--sdk-toolchain-sha256")
    args = parser.parse_args()
    produce(
        args.profile,
        args.profile_sha256,
        args.pc,
        args.output,
        args.jpeg_codec,
        args.jpeg_codec_sha256,
        args.etc_codec,
        args.etc_codec_sha256,
        args.sdk_toolchain,
        args.sdk_toolchain_sha256,
    )


if __name__ == "__main__":
    main()
