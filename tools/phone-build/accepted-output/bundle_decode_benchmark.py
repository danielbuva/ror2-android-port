"""Compare two pinned UnityFS decoders without emitting a replacement bundle."""

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import resource
import sys
import time


def load_decoder(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    decoder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(decoder)
    return decoder


def compare(path, baseline, candidate):
    started = time.monotonic()
    bundle = candidate.Bundle(path)
    decoded = hashlib.sha256()
    decoders = (baseline.decompress, candidate.decompress)
    cpu_ns = [0, 0]
    decoded_bytes = 0
    with path.open("rb") as stream:
        for index, (position, expanded, compressed, flags) in enumerate(bundle.blocks):
            stream.seek(position)
            data = candidate.exact(stream, compressed)
            outputs = [None, None]
            # Alternate first use of the same compressed bytes to balance cache effects.
            first = index % 2
            for decoder in (first, 1 - first):
                decode = decoders[decoder]
                start = time.process_time_ns()
                outputs[decoder] = decode(data, expanded, flags)
                cpu_ns[decoder] += time.process_time_ns() - start
            if outputs[0] != outputs[1]:
                raise ValueError(f"decoder output mismatch at block {index}")
            decoded.update(outputs[0])
            decoded_bytes += len(outputs[0])
    return dict(
        blocks=len(bundle.blocks),
        decoded_bytes=decoded_bytes,
        decoded_sha256=decoded.hexdigest(),
        baseline_cpu_seconds=cpu_ns[0] / 1e9,
        candidate_cpu_seconds=cpu_ns[1] / 1e9,
        elapsed_seconds=time.monotonic() - started,
        peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * (1 if sys.platform == "darwin" else 1024),
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path)
    parser.add_argument("baseline", type=Path)
    parser.add_argument("receipt", type=Path)
    args = parser.parse_args()
    baseline = load_decoder("baseline_unity_bundle", args.baseline)
    candidate = load_decoder("candidate_unity_bundle", Path(__file__).with_name("unity_bundle.py"))
    args.receipt.write_text(json.dumps(compare(args.bundle, baseline, candidate)) + "\n")


if __name__ == "__main__":
    main()
