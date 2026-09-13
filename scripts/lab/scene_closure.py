"""Read-only L4 reference closure; imported subassets remain an editor gate."""
from common import *
import re
from collections import deque, Counter

REFERENCE = re.compile(r'\{fileID:\s*(-?\d+)(?:,\s*guid:\s*([a-f0-9]{32}),\s*type:\s*(\d+))?\}')
HEADER = re.compile(r'^--- !u!\d+ &(-?\d+)', re.M)

def scene_closure():
    project = ROOT/read(WORK/'config/reconstruction.json')['projects'][0]
    out = WORK/'experiments/scene-closure'/now(); out.mkdir(parents=True)
    index = {}; duplicates = {}
    for meta in (project/'Assets').rglob('*.meta'):
        match = re.search(r'^guid:\s*([a-f0-9]{32})', meta.read_text(errors='replace'), re.M)
        if not match: continue
        guid = match.group(1); asset = Path(str(meta)[:-5])
        if guid in index: duplicates.setdefault(guid, [str(index[guid])]).append(str(asset))
        index[guid] = asset
    cache = {}
    def inspect(path):
        if path not in cache:
            with path.open('rb') as stream: prefix = stream.read(5)
            text = path.read_text(errors='replace') if prefix == b'%YAML' else ''
            cache[path] = (text, set(HEADER.findall(text)))
        return cache[path]
    roots = ['Assets/RoR2/Base/Scenes/loadingbasic/loadingbasic.unity',
             'Assets/RoR2/Base/Characters/Commando/CommandoBody.prefab']
    summaries = []
    for root in roots:
        queue = deque([project/root]); seen = set(); edges = []; issues = []; imports = []; scripts = []
        while queue:
            path = queue.popleft()
            if path in seen: continue
            seen.add(path)
            text, ids = inspect(path); relative = str(path.relative_to(project))
            for match in REFERENCE.finditer(text):
                file_id, guid, kind = match.groups()
                if file_id == '0': continue
                row = {'source': relative, 'fileID': file_id, 'guid': guid,
                       'line': text.count('\n', 0, match.start())+1}
                if not guid:
                    if file_id not in ids: issues.append(dict(row, category='missing-local-fileID'))
                    continue
                if guid.startswith('0000000000000000'): continue
                target = index.get(guid)
                if not target or not target.is_file():
                    issues.append(dict(row, category='unresolved-external-guid')); continue
                row['target'] = str(target.relative_to(project)); edges.append(row)
                if text[max(0, match.start()-12):match.start()].strip().endswith('m_Script:'):
                    scripts.append(row)
                target_text, target_ids = inspect(target)
                if target_text:
                    if file_id not in target_ids: issues.append(dict(row, category='missing-external-fileID'))
                else: imports.append(row)
                queue.append(target)
        report = {'root': root, 'files': sorted(str(p.relative_to(project)) for p in seen),
                  'bytes': sum(p.stat().st_size for p in seen), 'edges': edges,
                  'issues': issues, 'script_references': scripts,
                  'imported_subassets_requiring_editor_validation': imports,
                  'scope': 'Static serialized YAML closure; no runtime Addressables, native APIs, animation semantics or imported subasset validation'}
        write(out/(Path(root).stem+'.json'), report)
        summaries.append({'root': root, 'files': len(seen), 'bytes': report['bytes'],
                          'issues': dict(Counter(x['category'] for x in issues)),
                          'script_references': len(scripts), 'imported_references': len(imports)})
    result = {'input_id': read(WORK/'inventory/files.json')['input_id'], 'roots': summaries,
              'duplicate_guids': duplicates, 'evidence': str(out.relative_to(ROOT))}
    write(out/'result.json', result); write(out.parent/'latest.json', {'path': str(out.relative_to(ROOT))})
    print(json.dumps(result, indent=2))
