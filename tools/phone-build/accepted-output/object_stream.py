"""Bounded disk-backed storage for the complete native object producer.

The caller verifies source bodies before insertion. Only a small prefix and
extent metadata stay resident; canonical serialization and resource emission
read bounded extents. The caller owns the output and closes this store at exit.
"""

import hashlib
from pathlib import Path
import tempfile


MAX_MEMBER_BYTES = 8 * 1024**3
CHUNK = 128 * 1024


class ExtentReader:
    def __init__(self, stream, offset, size):
        self.stream, self.offset, self.size, self.position = stream, offset, size, 0

    def read(self, count=-1):
        count = self.size - self.position if count is None or count < 0 else min(count, self.size - self.position)
        self.stream.seek(self.offset + self.position)
        data = self.stream.read(count)
        self.position += len(data)
        return data


class StoredRecord(dict):
    """Existing graph/preload readers can request one complete body at a time."""

    def __init__(self, store, **metadata):
        super().__init__(metadata)
        self.store = store

    def __getitem__(self, key):
        if key == "body":
            data = self.store.reader(self).read()
            if len(data) != self["body_bytes"]:
                raise ValueError("truncated staged object body")
            return data
        return super().__getitem__(key)


class Store:
    def __init__(self, output):
        self.temporary = tempfile.TemporaryDirectory(prefix="native-stream-", dir=output)
        self.root = Path(self.temporary.name)
        self.file = (self.root / "bodies").open("w+b")
        self.next_file = 0

    def close(self):
        self.file.close()
        self.temporary.cleanup()

    def append(self, member, identity, body, typ):
        self.file.seek(0, 2)
        offset = self.file.tell()
        self.file.write(body)
        return StoredRecord(
            self,
            member=member,
            path_id=identity,
            prefix=body[:32],
            body_bytes=len(body),
            staged_offset=offset,
            sha256=hashlib.sha256(body).hexdigest(),
            type=typ,
        )

    def reader(self, row):
        return ExtentReader(self.file, row["staged_offset"], row["body_bytes"])

    def allocate(self):
        path = self.root / str(self.next_file)
        self.next_file += 1
        return path


def resource(path, extents, alignment, writer, per_record_limit):
    """Verify/copy original pack extents without retaining a complete resource."""
    with path.open("xb") as output:
        for offset, source_path, selected in sorted(extents, key=lambda row: row[0]):
            size = selected["bytes"]
            if offset < output.tell():
                raise ValueError("overlapping produced resource extents")
            if not 0 <= selected["offset"] or not 0 <= size <= per_record_limit or offset + size > MAX_MEMBER_BYTES:
                raise ValueError("produced resource exceeds bounded bundle capacity")
            writer.zeros(output, offset - output.tell())
            digest = hashlib.sha256()
            with source_path.open("rb") as source:
                source.seek(selected["offset"])
                remaining = size
                while remaining:
                    part = source.read(min(remaining, CHUNK))
                    if not part:
                        raise ValueError("truncated produced record extent")
                    remaining -= len(part)
                    digest.update(part)
                    output.write(part)
            if digest.hexdigest() != selected["sha256"]:
                raise ValueError("produced record extent drift")
        if alignment:
            writer.zeros(output, -output.tell() % alignment)
        return output.tell()
