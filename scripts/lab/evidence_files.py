"""Read retained evidence at its original path or as a Zstandard sidecar."""

from contextlib import contextmanager
from pathlib import Path
import subprocess


def compressed_path(path):
    return path.with_name(path.name + ".zst")


@contextmanager
def open_evidence(path):
    """Yield original bytes, including for receipt checks and explicit .zst paths."""
    path = Path(path)
    if path.suffix != ".zst":
        try:
            raw = path.open("rb")
        except FileNotFoundError:
            path = compressed_path(path)
        else:
            with raw:
                yield raw
            return
    # Open ourselves so missing input fails before launching a subprocess.
    with path.open("rb") as source, subprocess.Popen(["zstd", "-qdc"], stdin=source, stdout=subprocess.PIPE) as child:
        try:
            yield child.stdout
        except BaseException:
            child.kill()
            raise
        finally:
            child.stdout.close()
        if child.wait():
            raise OSError("Zstandard evidence could not be decoded")
