"""Discover original texture bodies for native copy or BC3 transcoding."""

import argparse
from collections import defaultdict
from hashlib import sha256
import io
import json
from pathlib import Path
import struct

import bundle_preload as preload
import texture_produce as texture


def texture_record(bundle, body, typ, position, identity, relative, member, trees, source_bc3):
    tree = typ["tree"]
    if tree not in trees:
        trees[tree] = preload.A.SCHEMA.type_tree(io.BytesIO(tree))
    spans = preload.A.fields(body, trees[tree])[1]

    def field(name):
        return body[slice(*spans[(name,)])]

    def integer(name):
        return struct.unpack("<i", field(name))[0]

    fmt = integer("m_TextureFormat")
    cube = typ["class_id"] == 89
    if source_bc3 and (cube or fmt != 12):
        return None
    if not source_bc3 and fmt not in ((17, 24) if cube else (1,)):
        return None
    width, height, mips = map(integer, ("m_Width", "m_Height", "m_MipCount"))
    if min(width, height) < 1 or not 1 <= mips <= max(width, height).bit_length():
        return None
    faces = 6 if cube else 1
    if integer("m_ImageCount") != faces or integer("m_TextureDimension") != 2 or field("m_PlatformBlob") != bytes(4):
        return None
    if any(pid for _, pid in preload.pointers(body, typ, trees).values()):
        return None

    image_key = "image data" if ("image data",) in spans else "#894"
    image_offset = spans[(image_key,)][0]
    image_size = struct.unpack_from("<I", body, image_offset)[0]
    offset, size, length = struct.unpack_from("<QII", field("m_StreamData"))
    path = field("m_StreamData")[16 : 16 + length].decode("utf-8")
    if (size and (image_size or not path)) or (not size and (offset or path)):
        return None
    stride = integer("m_CompleteImageSize")
    if source_bc3:
        try:
            texture.source_bc_extents(stride, width, height, fmt, mips)
        except ValueError:
            return None
        expected = stride
    elif cube:
        expected = sum(((max(1, width >> level) + 3) // 4) ** 2 * 16 if fmt == 24 else max(1, width >> level) ** 2 * 8 for level in range(mips))
        if width != height or width > 8192 or width & (width - 1):
            return None
    else:
        expected = sum(max(1, width >> level) * max(1, height >> level) for level in range(mips))
    if stride != expected or (size or image_size) != expected * faces:
        return None

    resource = path.rsplit("/", 1)[-1] if size else None
    if resource:
        stream = bundle.member(resource)
        stream.seek(offset)
        pixels = texture.BUNDLE.exact(stream, size)
    else:
        inline = field(image_key)
        pixels = inline[4 : 4 + image_size]
    digest = sha256(body).hexdigest()
    pixel_digest = sha256(pixels).hexdigest()
    fields = {}
    operation = "source-bc3-etc" if source_bc3 else "cube-preserve" if cube else "copy"
    names = ["m_Name", "m_CompleteImageSize", "m_TextureFormat", "m_IsAlphaChannelOptional", "m_LightmapFormat", "image data", "m_StreamData"]
    if cube or source_bc3:
        names.extend(("m_MipCount", "m_ColorSpace"))
    for name in names:
        start, end = spans[(image_key if name == "image data" else name,)]
        fields[name] = [start, end - start]
    name_size = struct.unpack_from("<I", field("m_Name"))[0]
    target = dict(
        bundle=relative,
        member=member,
        path_id=identity,
        bytes=len(body),
        sha256=digest,
        name=field("m_Name")[4 : 4 + name_size].decode("utf-8"),
        pixel_sha256=pixel_digest,
        pixel_bytes=len(pixels),
        inline=not size,
        stream=dict(offset=offset, size=size, path=path),
        alpha_optional=bool(field("m_IsAlphaChannelOptional")[0]),
        usage=integer("m_LightmapFormat"),
    )
    if cube or source_bc3:
        target.update(mips=mips, colour_space=integer("m_ColorSpace"))
    if source_bc3:
        normal = target["usage"] == 3
        target_bytes = expected // 2 if normal else expected
        target.update(sha256=None, pixel_sha256=None, pixel_bytes=target_bytes)
        if normal:
            target.update(usage=4, alpha_optional=True)
        if size:
            target["stream"]["size"] = target_bytes
        else:
            target["bytes"] += target_bytes - expected
    elif texture.body_output(body, fields, pixels, target, operation) != body:
        return None
    return dict(
        path_id=identity,
        offset=position,
        bytes=len(body),
        sha256=digest,
        fields=fields,
        pixels=dict(member=resource, offset=offset if size else image_offset + 4, bytes=len(pixels), sha256=pixel_digest),
        operation=operation,
        width=width,
        height=height,
        outputs=[target],
    )


def discover(pc, coverage, source_bc3=False):
    candidates = defaultdict(lambda: defaultdict(set))
    for row in preload.json_rows(coverage):
        relative, member, identity = row["source"]
        if row["status"] == "missing" and relative.endswith(".bundle"):
            candidates[relative][member].add(identity)
    bundles = []
    trees = {}
    for relative, members in sorted(candidates.items()):
        path = texture.MESH.safe_input(pc, relative)
        bundle = texture.BUNDLE.Bundle(path)
        selections = []
        for member, identities in sorted(members.items()):
            stream = bundle.member(member)
            metadata = texture.O.W.read_serialized(stream)
            selected = []
            for obj in metadata["objects"]:
                identity = obj["path_id"]
                typ = metadata["types"][obj["type_id"]]
                if identity not in identities or typ["class_id"] not in (28, 89) or "tree" not in typ:
                    continue
                position = metadata["data_offset"] + obj["offset"]
                stream.seek(position)
                body = texture.BUNDLE.exact(stream, obj["bytes"])
                record = texture_record(bundle, body, typ, position, identity, relative, member, trees, source_bc3)
                if record is not None:
                    selected.append(record)
            if selected:
                selections.append(dict(name=member, textures=selected))
        if selections:
            bundles.append(dict(path=relative, sha256=texture.BUNDLE.sha(path), members=selections))
    return dict(input_id=texture.MESH.INPUT_ID, bundles=bundles)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pc", type=Path)
    parser.add_argument("coverage", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source-bc3", action="store_true", help="select BC3 originals for Android ETC production")
    args = parser.parse_args()
    pc = args.pc.resolve(strict=True)
    if args.output.resolve().is_relative_to(pc):
        raise ValueError("Texture profile output overlaps original input")
    profile = discover(pc, args.coverage, args.source_bc3)
    with args.output.open("x") as output:
        json.dump(profile, output)
        output.write("\n")
