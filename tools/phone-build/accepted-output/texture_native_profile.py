"""Discover original texture bodies for native copy or BC transcoding."""

import argparse
from collections import defaultdict
from hashlib import sha256
import importlib.util
import io
import json
from pathlib import Path
import struct


def module(name):
    spec = importlib.util.spec_from_file_location("_texture_profile_" + name, Path(__file__).with_name(name + ".py"))
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


preload = module("bundle_preload")
texture = module("texture_produce")

NATIVE_2D_PIXEL_BYTES = {1: 1, 3: 3, 4: 4, 5: 4}


def texture_record(bundle, body, typ, position, identity, relative, member, trees, source_operation):
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
    usage = integer("m_LightmapFormat")
    if source_operation:
        if (
            cube != (source_operation in texture.SOURCE_BC_CUBE_OPERATIONS)
            or fmt != texture.SOURCE_BC_ETC_FORMATS[source_operation]
            or (fmt == 10 and usage not in (0, 6))
        ):
            return None
    elif fmt not in (texture.CUBE_NATIVE_PIXEL_BYTES.keys() | {24} if cube else NATIVE_2D_PIXEL_BYTES):
        return None
    width, height, mips = map(integer, ("m_Width", "m_Height", "m_MipCount"))
    image_count = integer("m_ImageCount")
    empty = not cube and source_operation is None and (width, height, mips) == (0, 0, 1) and (fmt, image_count) in ((1, 1), (4, 0))
    if not empty and (min(width, height) < 1 or not 1 <= mips <= max(width, height).bit_length()):
        return None
    faces = 6 if cube else 1
    if (not empty and image_count != faces) or integer("m_TextureDimension") != 2 or field("m_PlatformBlob") != bytes(4):
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
    if empty:
        expected = 0
    elif source_operation:
        try:
            if fmt == 29:
                if stride <= 0:
                    return None
                encoded_stride = sum(texture.source_bc_layout(width, height, 12, mips)[1])
            else:
                texture.source_bc_extents(stride, width, height, fmt, mips)
                encoded_stride = stride
        except ValueError:
            return None
        expected = stride
    elif cube:
        try:
            expected = texture.native_cube_stride(width, height, fmt, mips)
        except ValueError:
            return None
    else:
        expected = NATIVE_2D_PIXEL_BYTES[fmt] * sum(max(1, width >> level) * max(1, height >> level) for level in range(mips))
    if stride != expected or (size or image_size) != expected * faces:
        return None

    resource = path.rsplit("/", 1)[-1] if size else None
    if resource:
        with bundle.member(resource) as stream:
            stream.seek(offset)
            pixels = texture.BUNDLE.exact(stream, size)
    else:
        inline = field(image_key)
        pixels = inline[4 : 4 + image_size]
    digest = sha256(body).hexdigest()
    pixel_digest = sha256(pixels).hexdigest()
    fields = {}
    operation = source_operation or ("cube-preserve" if cube else "copy")
    names = ["m_Name", "m_CompleteImageSize", "m_TextureFormat", "m_IsAlphaChannelOptional", "m_LightmapFormat", "image data", "m_StreamData"]
    if cube or source_operation:
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
        usage=usage,
    )
    if cube or source_operation:
        target.update(mips=mips, colour_space=integer("m_ColorSpace"))
    if source_operation:
        normal = not cube and fmt in (12, 25, 29) and usage == 3
        encoded = encoded_stride * faces
        target_bytes = encoded // 2 if normal else encoded
        target.update(sha256=None, pixel_sha256=None, pixel_bytes=target_bytes)
        if normal:
            target.update(usage=4, alpha_optional=True)
        if size:
            target["stream"]["size"] = target_bytes
        else:
            target["bytes"] += ((target_bytes + 3) & ~3) - ((image_size + 3) & ~3)
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


def discover(pc, coverage, source_operation=None, schema_witnesses=()):
    candidates = defaultdict(lambda: defaultdict(set))
    for row in preload.json_rows(coverage):
        relative, member, identity = row["source"]
        if row["status"] == "missing" and (relative.endswith(".bundle") or schema_witnesses):
            candidates[relative][member].add(identity)
    witnesses = texture.texture_witnesses(pc, schema_witnesses)
    bundles = []
    trees = {}
    for relative, members in sorted(candidates.items()):
        path = texture.MESH.safe_input(pc, relative)
        resources = None if relative.endswith(".bundle") else {}
        selections = []
        with texture.texture_source(pc, path, resources, discover=True) as bundle:
            for member, identities in sorted(members.items()):
                stream = bundle.member(member)
                metadata = texture.O.W.read_serialized(stream)
                selected = []
                for obj in metadata["objects"]:
                    identity = obj["path_id"]
                    typ = metadata["types"][obj["type_id"]]
                    if identity not in identities or typ["class_id"] not in (28, 89):
                        continue
                    if resources is not None:
                        typ = texture.witnessed_texture_type(typ, witnesses)
                    if "tree" not in typ:
                        continue
                    position = metadata["data_offset"] + obj["offset"]
                    stream.seek(position)
                    body = texture.BUNDLE.exact(stream, obj["bytes"])
                    record = texture_record(bundle, body, typ, position, identity, relative, member, trees, source_operation)
                    if record is not None:
                        selected.append(record)
                if selected:
                    selections.append(dict(name=member, textures=selected))
        if selections:
            source = dict(path=relative, sha256=texture.BUNDLE.sha(path), members=selections)
            if resources is not None:
                source["resources"] = resources
            bundles.append(source)
    profile = dict(input_id=texture.MESH.INPUT_ID, bundles=bundles)
    if any("resources" in source for source in bundles):
        profile["schema_witnesses"] = schema_witnesses
    return profile


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pc", type=Path)
    parser.add_argument("coverage", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--schema-witnesses", type=Path, help="pinned original bundle selectors for standalone texture class schemas")
    compression = parser.add_mutually_exclusive_group()
    compression.add_argument("--source-bc1", action="store_const", dest="source_operation", const="source-bc1-etc", help="select BC1 colour originals for ETC1")
    compression.add_argument("--source-bc3", action="store_const", dest="source_operation", const="source-bc3-etc", help="select BC3 originals for Android ETC")
    compression.add_argument("--source-bc7", action="store_const", dest="source_operation", const="source-bc7-etc", help="select BC7 originals for Android ETC")
    compression.add_argument(
        "--source-bc3-crunch",
        action="store_const",
        dest="source_operation",
        const="source-bc3-crunch-etc",
        help="select DXT5Crunched originals for Android ETC",
    )
    compression.add_argument(
        "--source-bc1-cube", action="store_const", dest="source_operation", const="source-bc1-cube-etc", help="select opaque BC1 Cubemap originals for ETC1"
    )
    compression.add_argument(
        "--source-bc7-cube", action="store_const", dest="source_operation", const="source-bc7-cube-etc", help="select BC7 Cubemap originals for ETC2 RGBA8"
    )
    args = parser.parse_args()
    pc = args.pc.resolve(strict=True)
    if args.output.resolve().is_relative_to(pc):
        raise ValueError("Texture profile output overlaps original input")
    witnesses = json.loads(args.schema_witnesses.read_bytes()) if args.schema_witnesses else ()
    profile = discover(pc, args.coverage, args.source_operation, witnesses)
    with args.output.open("x") as output:
        json.dump(profile, output)
        output.write("\n")
