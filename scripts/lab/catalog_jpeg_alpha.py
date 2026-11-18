"""Restore source pixels where JPEG export discarded a texture channel."""

from collections import defaultdict
from hashlib import sha256
from io import BytesIO
from math import isqrt
from pathlib import Path
import re

from common import game, sha


JPEG = {".jpg", ".jpeg"}
DXT5_NORMAL = 3
PLATFORM_ENTRY = re.compile(r"^  - serializedVersion: \d+\n    buildTarget: (\S+)\n(?:    [^\n]*\n)+", re.M)


def lossless_pixels(image, usage):
    """Decode packed normals for Unity's existing NormalMap importer."""
    if image.getchannel("A").getextrema() == (255, 255):
        return None
    if usage != DXT5_NORMAL:
        return image

    from PIL import Image

    packed_red, green, _, packed_alpha = image.split()
    red_bytes, green_bytes = packed_alpha.tobytes(), green.tobytes()
    # The source stores normal X in alpha and Y in green. Reconstruct positive Z
    # before Unity repacks the normal for Android. The original red becomes alpha.
    blue = bytes((255 + isqrt(max(0, 255**2 - (2 * x - 255) ** 2 - (2 * y - 255) ** 2))) // 2 for x, y in zip(red_bytes, green_bytes, strict=True))
    return Image.merge("RGBA", (packed_alpha, green, Image.frombytes("L", image.size, blue), packed_red))


def texture_importer(text, packed_normal):
    texture_type = re.search(r"^  textureType: (\d+)$", text, re.M)
    if not texture_type or (texture_type[1] == "1") != packed_normal:
        raise ValueError("Source normal packing does not match the staged importer")
    if packed_normal:
        return text
    # Alpha is a shader channel. RGB dilation into zero-alpha pixels changes the
    # original RGB lookup even though the PNG contains all four channels.
    text, alpha = re.subn(r"^  alphaUsage: \d+$", "  alphaUsage: 1", text, flags=re.M)
    text, dilation = re.subn(r"^  alphaIsTransparency: [01]$", "  alphaIsTransparency: 0", text, flags=re.M)
    if alpha != 1 or dilation != 1:
        raise ValueError("Missing or ambiguous texture alpha importer settings")
    platforms = {entry[1]: entry for entry in PLATFORM_ENTRY.finditer(text)}
    settings = platforms.get("Android") or platforms["DefaultTexturePlatform"]
    # The Android automatic ETC2 format quantizes the recovered ramp's alpha.
    # Preserve all RGBA channels for ordinary textures in this affected cohort.
    fields = {
        "buildTarget": "Android",
        "textureFormat": "4",  # TextureImporterFormat.RGBA32
        "textureCompression": "0",
        "crunchedCompression": "0",
        "allowsAlphaSplitting": "0",
        "overridden": "1",
    }
    android = re.sub(r"^    (\w+): [^\n]*$", lambda line: f"    {line[1]}: {fields[line[1]]}" if line[1] in fields else line[0], settings[0], flags=re.M)
    start = settings.start() if "Android" in platforms else settings.end()
    return text[:start] + android + text[settings.end() :]


def stage(io, manifest, catalog):
    """Join staged paths to original catalog bundle/container identities, then write."""
    import UnityPy

    inventory = io.read(io.work / "inventory/files.json")
    if manifest["input_id"] != inventory["input_id"] or inventory["input_id"] != io.read(io.work / "config/accepted-input.json")["input_id"]:
        raise ValueError("JPEG recovery requires the accepted catalog and inventory")
    inputs = defaultdict(list)
    for row in inventory["files"]:
        inputs[Path(row["path"]).name].append(row)

    locations = {row["id"]: row for row in catalog["locations"]}
    by_bundle = defaultdict(dict)
    staged = {}
    for row in manifest["locations"]:
        target = row["path"]
        if Path(target).suffix.lower() not in JPEG or not row["type"].startswith("UnityEngine.Texture2D,"):
            continue
        original = locations[row["id"]]
        owner = locations[original["dependencies"][0]]["internalId"].replace("\\", "/").rsplit("/", 1)[-1]
        source = original["internalId"].casefold()
        if target in staged and staged[target] != (owner, source):
            raise ValueError("Ambiguous source texture for " + target)
        staged[target] = owner, source
        by_bundle[owner][target] = source

    game_root = game(io.work)
    prepared = []
    rows = []
    for owner, targets in sorted(by_bundle.items()):
        if len(inputs[owner]) != 1:
            raise ValueError("Missing or ambiguous original texture bundle " + owner)
        record = inputs[owner][0]
        bundle = game_root / record["path"]
        if sha(bundle) != record["sha256"]:
            raise ValueError("Original texture bundle drift " + owner)
        wanted = set(targets.values())
        sources = defaultdict(dict)
        for obj in UnityPy.load(str(bundle)).objects:
            if obj.type.name != "AssetBundle":
                continue
            for address, info in obj.read().m_Container:
                key = address.casefold()
                if key in wanted:
                    asset = info.asset.deref()
                    if asset.type.name == "Texture2D":
                        sources[key][asset.assets_file.name, asset.path_id] = asset
        for target, key in sorted(targets.items()):
            if len(sources[key]) != 1:
                raise ValueError("Missing or ambiguous original Texture2D container record for " + target)
            (member, path_id), asset = next(iter(sources[key].items()))
            texture = asset.read()
            usage = texture.m_LightmapFormat
            image = texture.image.convert("RGBA")
            alpha = image.getchannel("A")
            row = dict(path=target, source=record["path"], source_sha256=record["sha256"], member=member, path_id=path_id, usage=usage)
            row.update(nonopaque_pixels=image.width * image.height - alpha.histogram()[255], alpha_sha256=sha256(alpha.tobytes()).hexdigest())
            rows.append(row)
            pixels = lossless_pixels(image, usage)
            if pixels is None:
                continue
            path = io.project / target
            if not io.is_file(path):
                raise ValueError("Missing staged JPEG texture " + target)
            meta = path.with_name(path.name + ".meta")
            importer = texture_importer(io.read_text(meta), usage == DXT5_NORMAL)
            png = BytesIO()
            pixels.save(png, "PNG")
            data = png.getvalue()
            row.update(png_sha256=sha256(data).hexdigest(), rgba_sha256=sha256(pixels.tobytes()).hexdigest())
            prepared.append((path, meta, importer, data))

    # The pinned TextureImporter reads PNG by signature. Keep the existing Unity
    # asset paths and GUIDs used by bundle maps, serialized materials and scenes.
    for path, meta, importer, data in prepared:
        if io.read_bytes(path) != data:
            io.apply(path, data)
        if io.read_text(meta) != importer:
            io.apply(meta, importer)
    receipt = dict(input_id=inventory["input_id"], checked=len(rows), restored=len(prepared), rows=rows)
    io.write(io.project / ".rebuild/catalog-jpeg-alpha.json", receipt)
    return dict(checked=len(rows), restored=len(prepared))
