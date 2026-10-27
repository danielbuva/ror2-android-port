"""Bounded, read-only UnityFS 7/8 and serialized-v22 input access.

Uses Python's standard library on the host and Android. Format knowledge was
cross-checked against pinned UnityPy 1.25.3; no game object implementation is
included. Only the two most recently read decompressed blocks are retained.
"""

import bisect
import hashlib
import io
import struct


LIMIT = 128 * 1024 * 1024  # largest scene member today: Soul1 sharedAssets, 75 MiB


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def exact(stream, count):
    if not 0 <= count <= LIMIT:
        raise ValueError("read exceeds bounded input limit")
    data = stream.read(count)
    if len(data) != count:
        raise ValueError("truncated input")
    return data


def unpack(stream, fmt):
    return struct.unpack(fmt, exact(stream, struct.calcsize(fmt)))


def string(stream):
    value = bytearray()
    for _ in range(4096):
        byte = exact(stream, 1)
        if byte == b"\0":
            return value.decode("utf-8")
        value.extend(byte)
    raise ValueError("unterminated input string")


def align(stream, boundary=4):
    stream.seek((stream.tell() + boundary - 1) // boundary * boundary)


def decompress(data, size, flags):
    """Decode bounded raw/LZ4 blocks, including overlapping match copies."""
    if not 0 <= size <= LIMIT:
        raise ValueError("oversized output block")
    method = flags & 63
    if method == 0:
        if len(data) != size:
            raise ValueError("raw block size differs")
        return data
    if method not in (2, 3):
        raise ValueError("unqualified bundle compression")
    output = bytearray()
    cursor = 0

    def length(base):
        nonlocal cursor
        if base == 15:
            while True:
                if cursor >= len(data):
                    raise ValueError("truncated LZ4 length")
                extra = data[cursor]
                cursor += 1
                base += extra
                if base > size:
                    raise ValueError("LZ4 length exceeds output")
                if extra != 255:
                    break
        return base

    while cursor < len(data):
        token = data[cursor]
        cursor += 1
        literals = length(token >> 4)
        if cursor + literals > len(data) or len(output) + literals > size:
            raise ValueError("invalid LZ4 literal extent")
        output.extend(data[cursor : cursor + literals])
        cursor += literals
        if cursor == len(data):
            break
        if cursor + 2 > len(data):
            raise ValueError("truncated LZ4 match")
        distance = int.from_bytes(data[cursor : cursor + 2], "little")
        cursor += 2
        count = length(token & 15) + 4
        if distance == 0 or distance > len(output) or len(output) + count > size:
            raise ValueError("invalid LZ4 match extent")
        # Copy repeated spans rather than one Python iteration per output byte.
        start = len(output) - distance
        pattern = output[start : start + min(distance, count)]
        output.extend((pattern * ((count + distance - 1) // distance))[:count])
    if len(output) != size:
        raise ValueError("decompressed size differs")
    return bytes(output)


class Bundle:
    def __init__(self, path):
        self.path = path
        self.cache = {}
        with path.open("rb") as stream:
            if string(stream) != "UnityFS":
                raise ValueError("not UnityFS")
            (version,) = unpack(stream, ">I")
            string(stream)  # player version
            engine = string(stream)
            if version not in (7, 8) or not engine.startswith("2021.3."):
                raise ValueError("unqualified UnityFS version")
            size, compressed, expanded, flags = unpack(stream, ">QIII")
            information_bytes = compressed
            if size != path.stat().st_size or flags & ~0x2FF:
                raise ValueError("unsupported bundle header")
            align(stream, 16)
            start = stream.tell()
            if flags & 128:
                stream.seek(size - compressed)
            info = io.BytesIO(decompress(exact(stream, compressed), expanded, flags))
            data_start = start if flags & 128 else stream.tell()
            if flags & 512:
                data_start = (data_start + 15) // 16 * 16
            exact(info, 16)
            (count,) = unpack(info, ">I")
            if count > 200000:
                raise ValueError("excessive block count")
            self.blocks = []
            self.bounds = []
            total = 0
            for _ in range(count):
                expanded, compressed, block_flags = unpack(info, ">IIH")
                if max(expanded, compressed) > LIMIT or expanded == 0:
                    raise ValueError("invalid block size")
                self.bounds.append(total)
                self.blocks.append((data_start, expanded, compressed, block_flags))
                data_start += compressed
                total += expanded
            if data_start > size - (information_bytes if flags & 128 else 0):
                raise ValueError("blocks exceed bundle")
            (count,) = unpack(info, ">I")
            if count > 100000:
                raise ValueError("excessive member count")
            self.members = {}
            for _ in range(count):
                offset, length, node_flags = unpack(info, ">QQI")
                name = string(info)
                if name in self.members or offset + length > total:
                    raise ValueError("duplicate or escaped bundle member")
                self.members[name] = (offset, length, node_flags)
            if info.read(1):
                raise ValueError("trailing block metadata")

    def read(self, offset, size):
        if not 0 <= size <= LIMIT or offset < 0:
            raise ValueError("unbounded bundle read")
        result = bytearray()
        with self.path.open("rb") as stream:
            while len(result) < size:
                index = bisect.bisect_right(self.bounds, offset) - 1
                if not 0 <= index < len(self.blocks):
                    raise ValueError("read outside bundle")
                position, expanded, compressed, flags = self.blocks[index]
                if index not in self.cache:
                    stream.seek(position)
                    block = decompress(exact(stream, compressed), expanded, flags)
                    if len(self.cache) == 2:
                        self.cache.pop(next(iter(self.cache)))
                    self.cache[index] = block
                start = offset - self.bounds[index]
                count = min(size - len(result), expanded - start)
                if count <= 0:
                    raise ValueError("nonprogressing bundle read")
                result.extend(self.cache[index][start : start + count])
                offset += count
        return bytes(result)

    def member(self, name):
        offset, size, _ = self.members[name]
        return Member(self, offset, size)


class Member(io.RawIOBase):
    def __init__(self, bundle, offset, size):
        self.bundle, self.offset, self.size, self.position = bundle, offset, size, 0

    def readable(self):
        return True

    def seekable(self):
        return True

    def tell(self):
        return self.position

    def seek(self, offset, whence=0):
        if whence not in (0, 1, 2):
            raise ValueError("invalid seek origin")
        position = offset + (0 if whence == 0 else self.position if whence == 1 else self.size)
        if not 0 <= position <= self.size:
            raise ValueError("seek outside member")
        self.position = position
        return position

    def read(self, size=-1):
        count = self.size - self.position if size < 0 else min(size, self.size - self.position)
        result = self.bundle.read(self.offset + self.position, count)
        self.position += count
        return result
