"""Source OBJ import arithmetic for the existing Mesh owner.

Original attributes, public MikkTSpace, robust normalization and the SDK's
16-vertex cache policy determine all output geometry. The UV-density statistic
uses the original importer area comparator through the pinned public BSD sort.
No saved model, SDK object body, vertex table or target scalar is an input.
"""

import hashlib
import json
import math
from pathlib import Path
import struct
import subprocess


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def f(value):
    return struct.unpack("<f", struct.pack("<f", value))[0]


epsilon = f(1e-5)
E = f(0.001)
ANGLE = f(math.radians(5))


class Native:
    def __init__(self, root, expected):
        self.root = Path(root).resolve(strict=True)
        self.program = self.root / "mesh-obj"
        self.receipt = self.root / "result.json"
        if self.program.is_symlink() or self.receipt.is_symlink():
            raise ValueError("redirected OBJ helper input")
        result = json.loads(self.receipt.read_text())
        if (
            set(expected) != {"source_sha256", "providers"}
            or not result.get("success")
            or result.get("source_sha256") != expected["source_sha256"]
            or result.get("providers") != expected["providers"]
            or sha(Path(__file__).with_name("mesh_obj.c")) != expected["source_sha256"]
        ):
            raise ValueError("OBJ helper source receipt differs")
        self.pins = {self.receipt: sha(self.receipt), self.program: result["output_sha256"]}
        self.finish()

    def finish(self):
        if any(sha(path) != pin for path, pin in self.pins.items()):
            raise ValueError("OBJ helper changed during production")

    def run(self, operation, data, size):
        self.finish()
        result = subprocess.run([str(self.program), operation], input=data, capture_output=True, timeout=90)
        if result.returncode or len(result.stdout) != size:
            raise ValueError("OBJ native helper failed: " + operation)
        self.finish()
        return result.stdout

    def sort(self, values):
        count = len(values)
        data = struct.pack("<I", count) + struct.pack("<" + "f" * count, *values)
        return list(struct.unpack("<" + "f" * count, self.run("area-order", data, count * 4)))

    def tangents(self, vertices, indices):
        count = len(vertices) // 48
        data = struct.pack("<II", count, len(indices)) + vertices + struct.pack("<" + "I" * len(indices), *indices)
        return self.run("tangents", data, len(indices) * 16)


def robust(v):
    v = [x if abs(x) > epsilon else 0.0 for x in v]
    axis = 1 if abs(v[1]) > abs(v[0]) else 0
    if abs(v[2]) > abs(v[axis]):
        axis = 2
    scale = abs(v[axis])
    if not scale:
        return [0.0, 1.0, 0.0]
    other = [i for i in range(3) if i != axis]
    ratios = [f(v[i] / scale) for i in other]
    s = f(f(f(ratios[0] * ratios[0]) + f(ratios[1] * ratios[1])) + 1.0)
    length = f(math.sqrt(s))
    gain = f(1.0 / length)
    out = [0.0] * 3
    out[axis] = math.copysign(gain, v[axis])
    for i, q in zip(other, ratios):
        out[i] = f(q * gain)
    return out


def optimize(triangles, vertices, cache_size=16):
    adj = [[] for _ in vertices]
    degree = [0 for _ in vertices]
    for i, t in enumerate(triangles):
        for v in t:
            adj[v].append(i)
            degree[v] += 1
    buckets = [[] for _ in range(max(degree) + 1)]
    for v, n in enumerate(degree):
        if n:
            buckets[n].insert(0, v)
    queues = [[], []]
    pos = [0, 0]
    for i, t in enumerate(triangles):
        ones = sum(degree[v] == 1 for v in t)
        if ones:
            queues[ones == 1].append(i)
    done = set()
    cache = []
    out = []
    while len(done) < len(triangles):
        choice = None
        best = (-1, -1)
        for v in cache:
            for i in adj[v]:
                t = triangles[i]
                score = (sum(x in cache for x in t), sum(4096 >> ((degree[x] * 4) & 31) for x in t))
                if score > best:
                    best = score
                    choice = i
        if choice is None:
            for q in range(2):
                while pos[q] < len(queues[q]):
                    i = queues[q][pos[q]]
                    pos[q] += 1
                    if i not in done:
                        choice = i
                        break
                if choice is not None:
                    break
        if choice is None:
            v = next(bucket[0] for bucket in buckets[1:] if bucket)
            choice = adj[v][0]
        assert choice not in done
        done.add(choice)
        t = triangles[choice]
        out.extend(t)
        for v in t:
            old = degree[v]
            adj[v] = [i for i in adj[v] if i != choice]
            buckets[old].remove(v)
            degree[v] = len(adj[v])
            if degree[v]:
                buckets[degree[v]].insert(0, v)
        for v in t:
            if degree[v] == 1:
                i = adj[v][0]
                ones = sum(degree[x] == 1 for x in triangles[i])
                if ones in (1, 2):
                    queues[ones == 1].append(i)
        cache = [x for x in cache if x not in t] + list(t)
        cache = cache[-cache_size:]
    return out


def add(values):
    result = 0.0
    for v in values:
        result = f(result + v)
    return result


def sub(a, b):
    return [f(x - y) for x, y in zip(a, b)]


def dot(a, b):
    return add([f(x * y) for x, y in zip(a, b)])


def area(v):
    a, b = sub(v[1], v[0]), sub(v[2], v[0])
    cross = [f(f(a[1] * b[2]) - f(a[2] * b[1])), f(f(a[2] * b[0]) - f(a[0] * b[2])), f(f(a[0] * b[1]) - f(a[1] * b[0]))]
    return f(f(math.sqrt(dot(cross, cross))) * 0.5)


def metric(vertices, indices, sort):
    triangles = [indices[k : k + 3] for k in range(0, len(indices), 3)]
    areas = sort([area([vertices[i][:3] for i in tri]) for tri in triangles])
    trim = areas[: len(areas) - len(indices) // 30]
    mean = f(add(trim) / len(trim))
    low = [x for x in trim if x < mean]
    std = f(math.sqrt(f(add([f(f(x - mean) * f(x - mean)) for x in low]) / len(low)))) if low else 0.0
    minimum = max(f(mean - std), E) if std >= 0.1 else E
    density = []
    filtered = {k: 0 for k in ("edge", "angle", "area", "uv", "ratio")}
    for tri in triangles:
        v = [vertices[i] for i in tri]
        p = [x[:3] for x in v]
        edges = [sub(p[2], p[0]), sub(p[1], p[0]), sub(p[2], p[1])]
        length = [f(math.sqrt(dot(e, e))) for e in edges]
        if min(length) < E:
            filtered["edge"] += 1
            continue
        a, b, c = length
        squares = [f(x * x) for x in length]
        cosines = [
            f(f(f(squares[1] + squares[0]) - squares[2]) / f(f(b + b) * a)),
            f(f(f(squares[0] + squares[2]) - squares[1]) / f(f(a + a) * c)),
            f(f(f(squares[1] + squares[2]) - squares[0]) / f(f(c + c) * b)),
        ]
        if any(f(math.acos(max(-1.0, min(1.0, x)))) < ANGLE for x in cosines):
            filtered["angle"] += 1
            continue
        world = area(p)
        u = sub(v[1][10:12], v[0][10:12])
        w = sub(v[2][10:12], v[0][10:12])
        uv = f(abs(f(f(u[0] * w[1]) - f(u[1] * w[0]))) * 0.5)
        if world < minimum:
            filtered["area"] += 1
            continue
        if uv < f(1e-9):
            filtered["uv"] += 1
            continue
        ratio = f(world / uv)
        if ratio <= E:
            filtered["ratio"] += 1
            continue
        density.append(ratio)
    if not density:
        return 1.0, dict(filtered=filtered, minimum_area=minimum)
    mean = f(add(density) / len(density))
    high = [x for x in density if x > mean]
    sd = f(math.sqrt(f(add([f(f(x - mean) * f(x - mean)) for x in high]) / len(high)))) if high else 0.0
    result = f(mean + sd)
    return result if result > E else 1.0, dict(filtered=filtered, minimum_area=minimum, mean=mean, upper_deviation=sd, retained=len(density))


def convert(data, index_data, native):
    """Import the admitted static float32 position/normal/tangent/UV0 layout."""
    if not data or len(data) % 48 or not index_data or len(index_data) % 6:
        raise ValueError("unsupported source OBJ mesh layout")
    count = len(data) // 48
    if count > 65535:
        raise ValueError("source OBJ mesh exceeds 16-bit vertex extent")
    indices = list(struct.unpack("<" + "H" * (len(index_data) // 2), index_data))
    if max(indices) >= count:
        raise ValueError("source OBJ index outside vertex data")
    # OBJ exports (c,b,a); native handedness conversion gives (c,a,b).
    rotated = [i for at in range(0, len(indices), 3) for i in (indices[at + 2], indices[at], indices[at + 1])]
    tangent_data = native.tangents(data, rotated)
    tangents = {}
    for at, index in enumerate(rotated):
        value = struct.unpack_from("<4f", tangent_data, at * 16)
        tangent = struct.pack("<4f", *robust(value[:3]), value[3])
        if index in tangents and tangents[index] != tangent:
            raise ValueError("source OBJ requires unsupported tangent vertex splitting")
        tangents[index] = tangent
    ordered = optimize([rotated[i : i + 3] for i in range(0, len(rotated), 3)], list(range(count)))
    vertices = list(dict.fromkeys(ordered))
    if len(vertices) != count:
        raise ValueError("source OBJ contains unreferenced vertices")
    remap = {index: at for at, index in enumerate(vertices)}
    ordered = [remap[index] for index in ordered]
    output = b"".join(data[i * 48 : i * 48 + 24] + tangents[i] + data[i * 48 + 40 : (i + 1) * 48] for i in vertices)
    decoded = [struct.unpack_from("<12f", output, i) for i in range(0, len(output), 48)]
    value, _ = metric(decoded, ordered, native.sort)
    return output, struct.pack("<" + "H" * len(ordered), *ordered), value
