#!/bin/sh
cd "$(dirname "$0")/.."
. scripts/env.sh
exec /opt/homebrew/bin/python3 scripts/doctor.py "$@"
