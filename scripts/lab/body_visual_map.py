"""Generate owned runtime bindings from the accepted CharacterBody initializer.

Only the field/path pairs are emitted into the ignored Unity project. The
original decompilation and game asset names never enter tracked source.
"""

import json
import re
from pathlib import Path


LOAD = re.compile(
    r'asyncOperationHandle = (LegacyResourcesAPI|Addressables)\.'
    r'(?:LoadAsync|LoadAssetAsync)<GameObject>\("([^"]+)"\);\s*'
    r'asyncOperationHandle\.Completed \+= delegate\(AsyncOperationHandle<GameObject> x\)\s*'
    r'\{\s*(\w+) = x\.Result;\s*\};')


def extract(source: str):
    start = source.index('public static void Resolve()')
    end = source.index('\n\t\t}\n', start)
    method = source[start:end]
    rows = LOAD.findall(method)
    calls = method.count('LoadAsync<GameObject>') + method.count('LoadAssetAsync<GameObject>')
    if not rows or len(rows) != calls or len({field for _, _, field in rows}) != len(rows):
        raise RuntimeError('Original CharacterBody visual-reference initializer changed')
    for _, _, field in rows:
        if not re.search(r'\bpublic static GameObject ' + re.escape(field) + r';', source):
            raise RuntimeError('Original temporary visual field changed: ' + field)
    return rows


def generate(source: Path, destination: Path, input_id: str, legacy_aliases: dict, manifest: dict):
    rows = extract(source.read_text())
    keys = {entry['key'] for entry in manifest['keys'] if isinstance(entry['key'], str)}
    missing = []
    for kind, path, field in rows:
        key = legacy_aliases.get(path) if kind == 'LegacyResourcesAPI' else path
        if not key or key not in keys:
            missing.append(field)
    source_rows = ',\n'.join('  new string[] {' + ','.join(json.dumps(value) for value in row) + '}' for row in rows)
    code = ('// Generated from the accepted original CharacterBody.AssetReferences.Resolve.\n'
            'public static class OriginalBodyVisualMap {\n'
            ' public const string InputId = ' + json.dumps(input_id) + ';\n'
            ' public static readonly string[][] Rows = new string[][] {\n' + source_rows + '\n };\n}\n')
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(code)
    return {'rows': len(rows), 'unlocated_fields': missing}
