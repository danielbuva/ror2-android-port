"""Bounded UnityFS and serialized-v22 construction from supplied object records.

This module writes structure, not game content. Callers supply independently
produced bodies/resources and source-derived type metadata. No accepted bundle
or compressed target block is an input to the writer.
"""

from contextlib import contextmanager
import importlib.util
import io
import os
from pathlib import Path
import selectors
import signal
import struct
import subprocess
import tempfile
import time


_spec = importlib.util.spec_from_file_location("_write_bundle", Path(__file__).with_name("unity_bundle.py"))
B = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(B)


def zero_string(value):
    data = value.encode("utf-8")
    if b"\0" in data or len(data) >= 4096:
        raise ValueError("invalid serialized string")
    return data + b"\0"


def padding(stream, boundary):
    stream.write(bytes(-stream.tell() % boundary))


def type_record(row, trees, reference=False):
    """Encode Unity's native/script identity plus an original embedded tree."""
    data = struct.pack("<iBh", row["class_id"], row["stripped"], row["script_type"])
    if row["class_id"] == 114 or (reference and row["script_type"] >= 0):
        script = row["script_id"]
        if len(script) != 16:
            raise ValueError("invalid script identity")
        data += script
    if len(row["hash"]) != 16:
        raise ValueError("invalid type identity")
    data += row["hash"]
    if trees:
        tree = row["tree"]
        if len(tree) < 8:
            raise ValueError("missing type tree")
        count, length = struct.unpack_from("<II", tree)
        if not 0 < count <= 100000 or len(tree) != 8 + count * 32 + length or len(tree) > B.LIMIT:
            raise ValueError("invalid type-tree extent")
        data += tree
        if reference:
            data += b"".join(zero_string(row[name]) for name in ("class", "namespace", "assembly"))
        else:
            dependencies = row["dependencies"]
            data += struct.pack("<I", len(dependencies)) + b"".join(struct.pack("<i", item) for item in dependencies)
    return data


def read_serialized(member):
    """Read structural metadata only; return bodies as extents, never literals.

    Useful for original-input discovery and independent writer qualification.
    A production caller must derive its target relationships independently.
    """
    member.seek(0)
    header = B.exact(member, 48)
    metadata, size, offset, unknown = struct.unpack_from(">Iqqq", header, 20)
    if header[:20] != struct.pack(">IIII", 0, 0, 22, 0) + bytes(4) or unknown or size != member.size or not 48 + metadata <= offset <= size:
        raise ValueError("unqualified serialized-v22 header")
    stream = io.BytesIO(B.exact(member, metadata))
    engine = B.string(stream)
    if not engine.startswith("2021.3."):
        raise ValueError("unqualified serialized engine")
    (platform,) = B.unpack(stream, "<i")
    (trees,) = B.unpack(stream, "<?")

    def types(reference=False):
        (count,) = B.unpack(stream, "<I")
        if count > 100000:
            raise ValueError("excessive serialized type count")
        rows = []
        for _ in range(count):
            class_id, stripped, script_type = B.unpack(stream, "<iBh")
            row = {"class_id": class_id, "stripped": stripped, "script_type": script_type}
            if class_id == 114 or (reference and script_type >= 0):
                row["script_id"] = B.exact(stream, 16)
            row["hash"] = B.exact(stream, 16)
            if trees:
                start = stream.tell()
                nodes, length = B.unpack(stream, "<II")
                if not 0 < nodes <= 100000 or 8 + nodes * 32 + length > B.LIMIT:
                    raise ValueError("invalid serialized tree")
                B.exact(stream, nodes * 32 + length)
                row["tree"] = stream.getbuffer()[start : stream.tell()].tobytes()
                if reference:
                    row.update({name: B.string(stream) for name in ("class", "namespace", "assembly")})
                else:
                    (dependencies,) = B.unpack(stream, "<I")
                    if dependencies > 100000:
                        raise ValueError("excessive type dependencies")
                    row["dependencies"] = list(B.unpack(stream, "<" + "i" * dependencies))
            rows.append(row)
        return rows

    definitions = types()
    (count,) = B.unpack(stream, "<I")
    if count > 2000000:
        raise ValueError("excessive serialized object count")
    objects = []
    identities = set()
    for _ in range(count):
        B.align(stream)
        path_id, start, length, type_id = B.unpack(stream, "<qqIi")
        if path_id in identities or not 0 <= type_id < len(definitions) or start < 0 or offset + start + length > size:
            raise ValueError("invalid serialized object extent")
        identities.add(path_id)
        objects.append({"path_id": path_id, "offset": start, "bytes": length, "type_id": type_id})
    (count,) = B.unpack(stream, "<I")
    if count > 2000000:
        raise ValueError("excessive serialized script count")
    scripts = []
    for _ in range(count):
        (file_id,) = B.unpack(stream, "<i")
        B.align(stream)
        (path_id,) = B.unpack(stream, "<q")
        scripts.append((file_id, path_id))
    (count,) = B.unpack(stream, "<I")
    if count > 100000:
        raise ValueError("excessive serialized external count")
    externals = []
    for _ in range(count):
        empty = B.string(stream)
        guid = B.exact(stream, 16)
        (kind,) = B.unpack(stream, "<i")
        externals.append({"empty": empty, "guid": guid, "type": kind, "path": B.string(stream)})
    references = types(True)
    user = B.string(stream)
    if stream.read(1):
        raise ValueError("trailing serialized metadata")
    return {
        "engine": engine,
        "platform": platform,
        "trees": trees,
        "types": definitions,
        "objects": objects,
        "scripts": scripts,
        "externals": externals,
        "ref_types": references,
        "user": user,
        "data_offset": offset,
        "bytes": size,
    }


def write_serialized(output, layout, body):
    """Write v22 metadata and stream object bodies in physical destination order.

    layout.objects preserves table order independently of physical offsets.
    body(row) returns a stream positioned at that independently produced record.
    Holes are zero padding; no body sorting or tail alignment is inferred.
    """
    meta = io.BytesIO()
    meta.write(zero_string(layout["engine"]))
    if not layout["engine"].startswith("2021.3."):
        raise ValueError("unqualified serialized engine")
    meta.write(struct.pack("<i?I", layout["platform"], layout["trees"], len(layout["types"])))
    for row in layout["types"]:
        meta.write(type_record(row, layout["trees"]))
    objects = layout["objects"]
    meta.write(struct.pack("<I", len(objects)))
    identities = set()
    for row in objects:
        if row["path_id"] in identities or not 0 <= row["type_id"] < len(layout["types"]) or row["offset"] < 0 or row["bytes"] < 0:
            raise ValueError("invalid destination object")
        identities.add(row["path_id"])
        padding(meta, 4)
        meta.write(struct.pack("<qqIi", row["path_id"], row["offset"], row["bytes"], row["type_id"]))
    meta.write(struct.pack("<I", len(layout["scripts"])))
    for file_id, path_id in layout["scripts"]:
        meta.write(struct.pack("<i", file_id))
        padding(meta, 4)
        meta.write(struct.pack("<q", path_id))
    meta.write(struct.pack("<I", len(layout["externals"])))
    for row in layout["externals"]:
        if len(row["guid"]) != 16:
            raise ValueError("invalid external GUID")
        meta.write(zero_string(row["empty"]) + row["guid"] + struct.pack("<i", row["type"]) + zero_string(row["path"]))
    meta.write(struct.pack("<I", len(layout["ref_types"])))
    for row in layout["ref_types"]:
        meta.write(type_record(row, layout["trees"], True))
    meta.write(zero_string(layout["user"]))
    data_offset = layout.get("data_offset", max(4096, (48 + meta.tell() + 15) // 16 * 16))
    end = max((row["offset"] + row["bytes"] for row in objects), default=0)
    file_size = layout.get("bytes", data_offset + end)
    if not 48 + meta.tell() <= data_offset or data_offset + end > file_size:
        raise ValueError("destination metadata or body exceeds file")
    output.write(struct.pack(">IIII", 0, 0, 22, 0) + bytes(4) + struct.pack(">Iqqq", meta.tell(), file_size, data_offset, 0))
    output.write(meta.getvalue())
    zeros(output, data_offset - output.tell())
    for row in sorted(objects, key=lambda item: item["offset"]):
        location = data_offset + row["offset"]
        if location < output.tell():
            raise ValueError("overlapping destination objects")
        zeros(output, location - output.tell())
        source = body(row)
        copy(source, output, row["bytes"])
    zeros(output, file_size - output.tell())


def zeros(stream, count):
    if count < 0:
        raise ValueError("negative padding")
    block = bytes(min(count, 128 * 1024))
    while count:
        n = min(count, len(block))
        stream.write(block[:n])
        count -= n


def copy(source, target, count):
    while count:
        n = min(count, 128 * 1024)
        target.write(B.exact(source, n))
        count -= n


class Codec:
    """One explicitly pinned native child, with bounded per-block I/O/teardown."""

    def __init__(self, path, sha256):
        self.path, self.sha256 = path, sha256
        if B.sha(path) != sha256:
            raise ValueError("bundle codec drift")
        self.child = subprocess.Popen([str(path)], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, start_new_session=True, bufsize=0)
        os.set_blocking(self.child.stdin.fileno(), False)
        os.set_blocking(self.child.stdout.fileno(), False)

    def transfer(self, stream, data=None, size=0):
        deadline = time.monotonic() + 60
        result = bytearray()
        position = 0
        with selectors.DefaultSelector() as selector:
            selector.register(stream, selectors.EVENT_READ if data is None else selectors.EVENT_WRITE)
            while len(result) < size if data is None else position < len(data):
                if not selector.select(max(0, deadline - time.monotonic())):
                    raise TimeoutError("bundle codec block deadline")
                if data is None:
                    chunk = os.read(stream.fileno(), min(size - len(result), 128 * 1024))
                    if not chunk:
                        raise ValueError("truncated bundle codec response")
                    result.extend(chunk)
                else:
                    position += os.write(stream.fileno(), data[position : position + 65536])
        return bytes(result)

    def __call__(self, data, method):
        if method == 0:
            return data
        # Worker method 9 selects HC9 shader segments; UnityFS flags stay 2/3.
        if method not in (2, 3, 9) or not 0 < len(data) <= B.LIMIT:
            raise ValueError("unqualified compression request")
        self.transfer(self.child.stdin, struct.pack("<II", len(data), method) + data)
        (size,) = struct.unpack("<I", self.transfer(self.child.stdout, size=4))
        if not 0 < size <= len(data) + len(data) // 255 + 16:
            raise ValueError("invalid bundle codec output size")
        encoded = self.transfer(self.child.stdout, size=size)
        if B.decompress(encoded, len(data), 3 if method == 9 else method) != data:
            raise ValueError("bundle codec roundtrip differs")
        return encoded

    def close(self):
        self.child.stdin.close()
        try:
            try:
                result = self.child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(self.child.pid, signal.SIGKILL)
                self.child.wait()
                raise TimeoutError("bundle codec exit deadline") from None
            if result:
                raise ValueError("bundle codec failed")
        finally:
            if self.child.poll() is None:
                os.killpg(self.child.pid, signal.SIGKILL)
                self.child.wait()
            self.child.stdout.close()
        if B.sha(self.path) != self.sha256:
            raise ValueError("bundle codec changed during production")


@contextmanager
def codec(path, sha256):
    child = Codec(path, sha256)
    try:
        yield child
    finally:
        child.close()


def write_bundle(output, members, compress, *, engine="2021.3.45f2", version=8, block_size=131072, flags=0x243):
    """Stream independent members into canonical UnityFS blocks and directory.

    members: ordered (name, flags, size, open_readable) tuples. Compression is
    injected so the generic writer has no Python/native-package dependency.
    The block directory is held in memory; compressed data uses one scratch file.
    """
    if version not in (7, 8) or not engine.startswith("2021.3.") or flags & ~0x2FF or not flags & 64 or not 0 < block_size <= B.LIMIT:
        raise ValueError("unqualified UnityFS layout")
    if flags & 63 not in (0, 2, 3):
        raise ValueError("unqualified UnityFS compression")
    method = flags & 63
    blocks, directory = [], []
    pending = bytearray()
    offset = 0
    names = set()
    with tempfile.TemporaryFile(dir=getattr(output, "name", None) and Path(output.name).parent) as scratch:

        def flush():
            encoded = compress(bytes(pending), method)
            selected = method
            if len(encoded) >= len(pending):
                encoded, selected = pending, 0
            scratch.write(encoded)
            blocks.append((len(pending), len(encoded), selected))
            pending.clear()

        for name, node_flags, size, open_source in members:
            if name in names or size < 0:
                raise ValueError("duplicate or invalid bundle member")
            zero_string(name)
            names.add(name)
            directory.append((offset, size, node_flags, name))
            offset += size
            with open_source() as source:
                remaining = size
                while remaining:
                    count = min(remaining, block_size - len(pending))
                    pending.extend(B.exact(source, count))
                    remaining -= count
                    if len(pending) == block_size:
                        flush()
                if source.read(1):
                    raise ValueError("bundle member exceeds declared extent")
        if pending:
            flush()
        info = bytes(16) + struct.pack(">I", len(blocks))
        info += b"".join(struct.pack(">IIH", *block) for block in blocks)
        info += struct.pack(">I", len(directory))
        info += b"".join(struct.pack(">QQI", start, size, node_flags) + zero_string(name) for start, size, node_flags, name in directory)
        if len(info) > B.LIMIT:
            raise ValueError("bundle directory exceeds limit")
        encoded_info = compress(info, method)
        head = b"UnityFS\0" + struct.pack(">I", version) + b"5.x.x\0" + zero_string(engine)
        start = (len(head) + 20 + 15) // 16 * 16
        data_start = start if flags & 128 else start + len(encoded_info)
        if flags & 512:
            data_start = (data_start + 15) // 16 * 16
        size = data_start + scratch.tell() + (len(encoded_info) if flags & 128 else 0)
        output.write(head + struct.pack(">QIII", size, len(encoded_info), len(info), flags))
        padding(output, 16)
        if not flags & 128:
            output.write(encoded_info)
        if flags & 512:
            padding(output, 16)
        scratch.seek(0)
        copy(scratch, output, sum(block[1] for block in blocks))
        if flags & 128:
            output.write(encoded_info)
    return {"bytes": size, "blocks": len(blocks), "members": len(directory)}
