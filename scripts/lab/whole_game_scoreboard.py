"""Admit a whole-game scoreboard request through the lab CLI."""

import json
from pathlib import Path
import subprocess
import sys

from common import ROOT


def report(request):
    if request in (None, "lab"):
        raise ValueError("whole-game-scoreboard requires --target REQUEST.json")
    source = ROOT / "tools/phone-build/accepted-output/whole_game_scoreboard.py"
    return json.loads(subprocess.check_output([sys.executable, str(source), str(Path(request).resolve())]))
