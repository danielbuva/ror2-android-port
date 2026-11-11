import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / "work"


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def toolchain():
    return read(ROOT / "environment/toolchain.json")
