#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
source scripts/env.sh
uv venv --allow-existing .local/lab-venv
uv pip sync --python .local/lab-venv/bin/python tools/lab-requirements.txt
printf '%s\n' 'Lab dependencies ready. Configure work/config/local.json from environment/lab-config.example.json.'
