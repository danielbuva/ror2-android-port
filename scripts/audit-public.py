#!/usr/bin/env python3
"""Check the Git index for common private captures and identifiers; print no values."""
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATTERNS = {
    'personal home path': rb'/(?:Users|home)/[A-Za-z0-9_.-]+/',
    'concrete storage UUID': rb'(?i)/mnt/expand/[0-9a-f]{8}-[0-9a-f-]{27,}',
    'UUID': rb'(?i)\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b',
    'private key': rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',
    'email': rb'[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}',
    'device/account identifier value': rb'(?i)"(?:serial|device_serial|uniqueId|displayUniqueId|accountId|steamId)"\s*:\s*"(?!AUTHORIZED_SERIAL"|REDACTED")[^"\n]+"',
}
PUBLIC_ENVIRONMENT = {
    'environment/ENVIRONMENT_REPORT.md', 'environment/lab-config.example.json',
    'environment/paths.env.example', 'environment/turnip-target.json',
}
PRIVATE_SUFFIXES = {'.apk', '.aab', '.dll', '.exe', '.bundle', '.assets', '.bank',
                    '.wem', '.so', '.dylib', '.keystore', '.jks', '.log', '.png'}


def violations(path, data):
    found = []
    if path.startswith(('work/', '.local/', 'logs/', 'screenshots/')):
        found.append('private output directory')
    if path.startswith('environment/') and path not in PUBLIC_ENVIRONMENT:
        found.append('unreviewed environment capture')
    if Path(path).suffix.lower() in PRIVATE_SUFFIXES:
        found.append('binary, middleware, or raw capture')
    for label, pattern in PATTERNS.items():
        if re.search(pattern, data):
            found.append(label)
    return found


def main():
    paths = subprocess.check_output(['git', 'ls-files', '-z'], cwd=ROOT).split(b'\0')
    failures = []
    for encoded in filter(None, paths):
        path = encoded.decode()
        data = subprocess.check_output(['git', 'show', ':' + path], cwd=ROOT)
        for label in violations(path, data):
            failures.append(f'{path}: {label}')
    print('\n'.join(failures) if failures else 'Public index audit passed (pattern checks; not a complete IP/secret review).')
    return bool(failures)


if __name__ == '__main__':
    sys.exit(main())
