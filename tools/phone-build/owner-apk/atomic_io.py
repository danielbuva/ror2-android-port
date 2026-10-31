"""Durable private installer writes under the caller's existing operation lock.

A deterministic sibling belongs only to this target. Retrying replaces a killed
writer's partial bytes; it never promotes or appends them. Callers serialize the
same target (import/update locks or the Android foreground job owner). An error
following rename means durability is unconfirmed, not that old bytes survived.
"""

from contextlib import contextmanager
import json
import os
from pathlib import Path


def sync_directory(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def mkdirs(path):
    path = Path(path)
    if path.is_symlink():
        raise ValueError("private directory cannot be a symlink")
    if not path.exists():
        mkdirs(path.parent)
        path.mkdir(exist_ok=True, mode=0o700)
        sync_directory(path.parent)


def discard(path):
    """Best effort on an exceptional path; never mask the original I/O error."""
    try:
        Path(path).unlink(missing_ok=True)
    except OSError:
        pass  # A subsequent explicit retry discards this owned partial again.


def publish(temporary, destination):
    temporary, destination = Path(temporary), Path(destination)
    if temporary.is_symlink() or not temporary.is_file() or destination.is_symlink():
        raise ValueError("regular private atomic files required")
    with temporary.open("rb") as stream:
        os.fsync(stream.fileno())
    os.replace(temporary, destination)
    sync_directory(destination.parent)
    if temporary.parent != destination.parent:
        sync_directory(temporary.parent)


@contextmanager
def writer(path):
    path = Path(path)
    mkdirs(path.parent)
    if path.is_symlink() or (path.exists() and not path.is_file()):
        raise ValueError("private destination must be a regular file")
    temporary = path.with_name("." + path.name + ".pending")
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(fd, "wb") as stream:
            yield stream
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        sync_directory(path.parent)
    except BaseException:
        discard(temporary)
        raise


def write_json(path, value):
    data = (json.dumps(value, sort_keys=True, allow_nan=False) + "\n").encode("utf-8")
    with writer(path) as stream:
        stream.write(data)
