"""Restore Animator parameter names that AssetRipper left as hashed placeholders.

The shipped clip binding retains the original CRC32 attribute and Animator
type ID. Only a unique parameter from the imported original controllers may
replace that placeholder; unknown hashes remain visible for later analysis.
"""

from collections import defaultdict
from pathlib import Path
import re
import zlib


PARAMETER = re.compile(r"^  - m_Name: (.+)$", re.M)
PLACEHOLDER = re.compile(r"^(    attribute: )typetree_0x([0-9A-Fa-f]+)_[^\r\n]+$", re.M)


def repair(project: Path, io=None):
    from composition_io import StageIO

    if io is None:
        io = StageIO(project)
        io.project = project
    root = project / "Assets/WholeGame"
    names = defaultdict(set)
    for controller in io.glob(root, "**/*.controller"):
        for name in PARAMETER.findall(io.read_text(controller, errors="replace")):
            names[zlib.crc32(name.encode("utf-8"))].add(name)

    changed = []
    unresolved = []
    for clip in io.glob(root, "**/*.anim"):
        source = io.read_text(clip, errors="replace")

        def replace(match):
            original_hash = int(match[2], 16)
            candidates = names[original_hash]
            # The serialized clip itself must independently identify this as
            # an Animator (class 95) float binding with the same hash.
            binding = re.search(r"^      attribute: " + str(original_hash) + r"\n      script: \{fileID: 0\}\n      typeID: 95$", source, re.M)
            if len(candidates) != 1 or not binding:
                unresolved.append((str(clip.relative_to(root)), match[2]))
                return match[0]
            name = next(iter(candidates))
            changed.append((str(clip.relative_to(root)), match[2], name))
            return match[1] + name

        repaired = PLACEHOLDER.sub(replace, source)
        if repaired != source:
            io.apply(clip, repaired)
    return {"repaired": changed, "unresolved": unresolved}
