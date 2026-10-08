"""Whole shipped catalog discovery; no readiness whitelist or entitlement grants."""
from common import *
from scene_closure import REFERENCE
from collections import Counter, deque
import re


def read_catalog(path):
    data = read(path)
    if data.get('schemaVersion') == 2:
        for row in data['locations']:
            # Shared arrays stay shared; flattening the shipped graph costs hundreds of MB.
            row['dependencies'] = data['dependencySets'][row['dependencySet']]
    return data


def catalog_path(out):
    receipt = out/'catalog-metadata.json'
    if not receipt.exists():
        return out/'source-catalog.json'
    record = read(receipt)
    path = (out/record['filename']).resolve()
    if out.resolve() not in path.parents or sha(path) != record['sha256']:
        raise RuntimeError('Catalog metadata receipt mismatch')
    return path


def catalog_roots(data, categories):
    keys = {row['key']: set(row['locations']) for row in data['keys'] if row.get('keyType', 'System.String') == 'System.String'}
    labels = {row['name']: row['key'] for row in data['labels']}
    missing = set(categories) - labels.keys()
    if missing:
        raise RuntimeError('Original provider categories absent: ' + str(sorted(missing)))
    packs = []
    roots = set()
    for provider in data['providers']:
        label = 'ContentPack:' + provider['identifier']
        if label not in keys:
            raise RuntimeError('Original provider label absent: ' + label)
        groups = {name: sorted(keys[label] & keys.get(labels[name], set())) for name in categories}
        roots.update(location for group in groups.values() for location in group)
        packs.append(dict(provider, label=label, categories=groups))
    return packs, roots


def resolve_path(internal_id, source_paths, folded_paths=None):
    """Only the exporter's punctuation replacement; ambiguous results stay unresolved."""
    if internal_id in source_paths:
        return internal_id, 'exact'
    path = Path(internal_id)
    sanitized = str(path.with_name(path.stem.replace(',', '_').strip()+path.suffix))
    if sanitized in source_paths:
        return sanitized, 'exported-filename'
    folded = folded_paths.get(sanitized.casefold(), []) if folded_paths is not None else [p for p in source_paths if p.casefold() == sanitized.casefold()]
    if len(folded) == 1:
        return folded[0], 'exported-filename-case'
    return None, 'unresolved-conversion'


def analyze(source, export, index, helper, native_overrides=None):
    data = read_catalog(source)
    categories = list(dict.fromkeys(re.findall(r'FindLocationsThenAddLoadOperation(?:<[^>]+>)?\(AddressablesLabels\.(\w+)', helper)))
    if len(categories) != 29:
        raise RuntimeError('Original provider category contract changed; review before conversion')
    packs, roots = catalog_roots(data, categories)
    locations = {row['id']: row for row in data['locations']}
    if len(locations) != len(data['locations']):
        raise RuntimeError('Duplicate catalog location identity')
    for row in locations.values():
        if not set(row['dependencies']) <= locations.keys():
            raise RuntimeError('Broken original catalog dependency')
    # Indexed source identity, rather than a filesystem search per resource.
    paths = set(index.values())
    folded_paths = {}
    for path in paths:
        folded_paths.setdefault(path.casefold(), []).append(path)
    converted = {}
    unresolved = []
    for row in locations.values():
        if not row['internalId'].startswith('Assets/'):
            continue
        path, reason = resolve_path(row['internalId'], paths, folded_paths)
        if native_overrides and str(row['id']) in native_overrides:
            converted[row['id']] = native_overrides[str(row['id'])]
        elif path:
            converted[row['id']] = dict(source=path, resolution=reason)
        else:
            unresolved.append(dict(id=row['id'], internalId=row['internalId'], type=row['type'],
                                   owning_bundle=row['dependencies'][0] if row['dependencies'] else None,
                                   dependency_count=len(row['dependencies']), category=reason, catalog_root=row['id'] in roots))
    key_locations = {row['key']: row['locations'] for row in data['keys'] if row.get('keyType', 'System.String') == 'System.String'}
    # Serialized references and runtime AssetReference keys are different edges.
    pending = deque(converted[identity]['source'] for identity in sorted(roots) if identity in converted)
    seen = set()
    issues = []
    soft_edges = []
    scripts = set()
    total_bytes = 0
    suffixes = Counter()
    while pending:
        relative = pending.popleft()
        if relative in seen:
            continue
        seen.add(relative)
        path = export / relative
        if not path.is_file():
            issues.append(dict(source=relative, category='indexed-source-file-missing'))
            continue
        total_bytes += path.stat().st_size
        suffixes[path.suffix] += 1
        if path.suffix in {'.dll', '.cs'}:
            scripts.add(relative)
            continue
        with path.open('rb') as stream:
            if stream.read(5) != b'%YAML':
                continue
        text = path.read_text()
        for guid in {g for _, g, _ in REFERENCE.findall(text) if g and not g.startswith('0000000000000000')}:
            target = index.get(guid)
            if target:
                pending.append(target)
            else:
                issues.append(dict(source=relative, guid=guid, category='serialized-guid-missing'))
        for guid in set(re.findall(r'm_AssetGUID:\s*([a-f0-9]{32})', text)):
            targets = key_locations.get(guid, [])
            resolved = [converted[x]['source'] for x in targets if x in converted]
            soft_edges.append(dict(source=relative, key=guid, locations=targets, resolved=resolved))
            pending.extend(resolved)
            if not targets:
                issues.append(dict(source=relative, key=guid, category='asset-reference-key-missing'))
            elif len(resolved) != len(targets):
                issues.append(dict(source=relative, key=guid, locations=targets, category='asset-reference-conversion-unresolved'))
    summary = dict(
        keys=len(data['keys']), locations=len(locations), providers=len(packs),
        provider_categories=len(categories), catalog_roots=len(roots),
        resolved_roots=len(roots & converted.keys()),
        root_types=dict(Counter(locations[x]['type'].split(',')[0] if locations[x]['type'] else 'unresolved-type' for x in roots)),
        converted_locations=len(converted), unresolved_locations=len(unresolved),
        unresolved_root_locations=[row['id'] for row in unresolved if row['catalog_root']],
        closure_files=len(seen), closure_bytes=total_bytes, closure_suffixes=dict(suffixes),
        soft_reference_edges=len(soft_edges), issues=dict(Counter(row['category'] for row in issues)),
        quarantine=[],
        scope='Host metadata/serialized closure only. Unresolved conversion is not incompatibility. No loading, registration, gameplay, ownership or Android acceptance.',
    )
    return dict(summary=summary, packs=packs, roots=sorted(roots), converted=converted,
                unresolved=unresolved, files=sorted(seen), scripts=sorted(scripts),
                soft_edges=soft_edges, issues=issues)


def native_candidates(records, exports):
    """A typed original container identity must have one matching exported owner."""
    result = []
    issues = []
    for row in records:
        candidates = exports.get((str(Path(row['address']).parent), row['type'], row['name']), [])
        if len(candidates) == 1:
            result.append(dict(source=candidates[0], name=row['name'], type=row['type'],
                               native_path_id=row['path_id'], serialized_file=row['serialized_file']))
        else:
            issues.append(dict(native=row, candidates=candidates,
                               category='ambiguous-exported-object' if candidates else 'exported-object-unresolved'))
    return result, issues


def reconcile():
    out = ROOT/read(WORK/'experiments/whole-catalog/latest.json')['path']
    export = ROOT/read(WORK/'config/reconstruction.json')['projects'][0]
    closure = read(out/'host-closure.json')
    index = read(out/'source-guid-index.json')
    metadata = read_catalog(catalog_path(out))
    native = ROOT/read(out/'native-latest.json')['path']
    # Unity class IDs are source serialization tags, independent of filename extensions.
    class_names = {1:'GameObject', 21:'Material', 28:'Texture2D', 43:'Mesh', 48:'Shader',
                   74:'AnimationClip', 89:'Cubemap', 90:'Avatar', 213:'Sprite', 687078895:'SpriteAtlas',
                   115:'MonoScript', 114:'MonoBehaviour', 142:'AssetBundle', 258:'LightProbes',
                   128:'Font', 152:'MovieTexture', 329:'VideoClip', 83:'AudioClip'}
    exported = {}
    for relative in set(index.values()):
        path = export/relative
        if not path.is_file():
            continue
        with path.open('rb') as stream:
            prefix = stream.read(16384)
        text = prefix.decode(errors='replace') if prefix.startswith(b'%YAML') else ''
        header = re.search(r'^--- !u!(\d+)', text, re.M)
        name = re.search(r'^  m_Name: (.*)$', text, re.M)
        if header and name:
            kind = class_names.get(int(header[1]))
            object_name = name[1]
            if object_name.startswith('"'):
                object_name = json.loads(object_name)
            elif object_name.startswith("'") and object_name.endswith("'"):
                object_name = object_name[1:-1].replace("''", "'")
        elif path.suffix.lower() in {'.png', '.tga', '.jpg', '.bmp', '.exr'}:
            kind, object_name = 'Texture2D', path.stem
        else:
            continue
        if kind:
            exported.setdefault((str(Path(relative).parent), kind, object_name), []).append(relative)
    containers = {}
    for receipt in native.glob('*.json'):
        if not receipt.stem.isdigit():
            continue
        data = read(receipt)
        for row in data['containers']:
            if 'type' in row:
                containers.setdefault((data['location'], row['address'].casefold(), row['type']), []).append(row)
    conversions = {}
    issues = []
    for row in closure['unresolved']:
        owner = row.get('owning_bundle', (row.get('dependencies') or [None])[0])
        if owner is None or not row['type']:
            continue
        kind = row['type'].split(',')[0].rsplit('.', 1)[-1]
        original = containers.get((owner, row['internalId'].casefold(), kind), [])
        if not original:
            issues.append(dict(location=row['id'], category='typed-native-container-unresolved'))
            continue
        objects, failures = native_candidates(original, exported)
        if failures or len(objects) != 1:
            issues.append(dict(location=row['id'], category='typed-native-export-unresolved',
                               objects=objects, failures=failures, requires_subobject_selection=len(objects)>1))
            continue
        conversions[str(row['id'])] = dict(source=objects[0]['source'], resolution='original-typed-container',
                                           native=objects[0], original_internal_id=row['internalId'])
    write(out/'native-conversions.json', dict(conversions=conversions, issues=issues, quarantine=[]))
    assembly_hash = sha(game()/'Risk of Rain 2_Data/Managed/RoR2.dll')
    key = digest(dict(input=assembly_hash, ilspy='11.0.0.9375', args='project-referencepath-csharp9-v2'))
    helper = WORK/'decompiled/RoR2'/key[:16]/'RoR2.ContentManagement/AddressablesLoadHelper.cs'
    result = analyze(catalog_path(out), export, index, helper.read_text(), conversions)
    result['source_catalog_sha256'] = closure['source_catalog_sha256']
    result['metadata_sha256'] = sha(catalog_path(out))
    result['input_id'] = closure['input_id']
    result['native_conversion_count'] = len(conversions)
    write(out/'reconciled-closure.json', result)
    print(json.dumps(dict(result['summary'], original_typed_conversions=len(conversions)), indent=2))


def audit():
    out = WORK/'experiments/whole-catalog'/now()
    out.mkdir(parents=True)
    export = ROOT/read(WORK/'config/reconstruction.json')['projects'][0]
    # The accepted decompilation location is receipted by recovery.py.
    assembly_hash = sha(game()/'Risk of Rain 2_Data/Managed/RoR2.dll')
    expected_hash = next(row['sha256'] for row in read(WORK/'inventory/files.json')['files'] if row['path'] == 'Risk of Rain 2_Data/Managed/RoR2.dll')
    if assembly_hash != expected_hash:
        raise RuntimeError('Original input drift; review and explicitly accept before conversion')
    decompile_key = digest(dict(input=assembly_hash, ilspy='11.0.0.9375', args='project-referencepath-csharp9-v2'))
    candidates = [path.parent/'RoR2.ContentManagement/AddressablesLoadHelper.cs'
                  for path in (WORK/'decompiled/RoR2').glob('*/result.json')
                  if read(path).get('success') and read(path).get('input_sha256') == assembly_hash
                  and read(path).get('cache_key') == decompile_key]
    if len(candidates) != 1:
        raise RuntimeError('Expected one accepted original load helper; review input selection')
    helper = candidates[0]
    export_catalog(out)
    source = out/'source-catalog.json'
    # Generated index only caches original GUID metadata, never supplies a readiness filter.
    index = {}
    for meta in (export/'Assets').rglob('*.meta'):
        match = re.search(r'^guid:\s*([a-f0-9]{32})', meta.read_text(errors='replace'), re.M)
        if not match:
            continue
        relative = str(Path(str(meta)[:-5]).relative_to(export))
        if match[1] in index:
            raise RuntimeError('Ambiguous exported GUID identity')
        index[match[1]] = relative
    result = analyze(source, export, index, helper.read_text())
    result['input_id'] = read(WORK/'inventory/files.json')['input_id']
    result['source_catalog_sha256'] = sha(export/'Assets/StreamingAssets/aa/catalog.json')
    result['metadata_sha256'] = sha(source)
    result['helper_sha256'] = sha(helper)
    write(out/'host-closure.json', result)
    write(out/'source-guid-index.json', index)
    write(out.parent/'latest.json', dict(path=str(out.relative_to(ROOT)), status='host-audit'))
    print(json.dumps(result['summary'], indent=2))


def export_catalog(out, template='ExportCatalog.cs.txt', filename='source-catalog.json'):
    """Read the shipped schema through the already pinned, idle lab editor."""
    export = ROOT/read(WORK/'config/reconstruction.json')['projects'][0]
    code = (ROOT/'tools/catalog'/template).read_text()
    code = code.replace('CATALOG', json.dumps(str(export/'Assets/StreamingAssets/aa/catalog.json')))
    code = code.replace('OUTPUT', json.dumps(str(out/filename)))
    client = '''import asyncio,json
from pathlib import Path
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
async def main():
 request=json.loads(Path(__file__).with_suffix('.json').read_text())
 async with streamablehttp_client('http://127.0.0.1:8080/mcp') as (r,w,_):
  async with ClientSession(r,w) as session:
   await session.initialize()
   instances=json.loads((await session.read_resource('mcpforunity://instances')).contents[0].text)['instances']
   matches=[row for row in instances if row['name']=='lab-project']
   if len(matches)!=1:raise RuntimeError('Expected one connected lab editor')
   await session.call_tool('set_active_instance',{'instance':matches[0]['id']})
   project=(await session.read_resource('mcpforunity://project/info')).model_dump(mode='json')
   if request['project'] not in json.dumps(project):raise RuntimeError('Selected project mismatch')
   response=(await session.call_tool('execute_code',{'action':'execute','code':request['code']})).model_dump(mode='json')
   Path(request['response']).write_text(json.dumps(response,indent=2))
   if response.get('isError') or response.get('structuredContent',{}).get('success') is not True:raise RuntimeError(str(response))
asyncio.run(main())
'''
    script = out/(Path(template).stem+'-query.py')
    script.write_text(client)
    write(script.with_suffix('.json'), dict(project=str(WORK/'lab-project'), code=code, response=str(out/(Path(template).stem+'-query-result.json'))))
    run([ROOT/'.local/tools/unity-mcp/Server/.venv/bin/python', script], timeout=180)


def contracts():
    out = ROOT/read(WORK/'experiments/whole-catalog/latest.json')['path']
    destination = out/('runtime-contracts-'+now())
    destination.mkdir()
    export_catalog(destination, 'ExportRuntimeContracts.cs.txt', 'runtime-contracts.json')
    runtime = read(destination/'runtime-contracts.json')
    imported = {(row['guid'], str(row['fileId'])): row for row in runtime['scripts']}
    export = ROOT/read(WORK/'config/reconstruction.json')['projects'][0]
    remaps = read(WORK/'config/hud-ui-remaps.json')
    if remaps['input_id'] != read(WORK/'config/accepted-input.json')['input_id'] or remaps['source_UI_sha256'] != sha(export/'Assets/Plugins/UnityEngine.UI.dll'):
        raise RuntimeError('Existing measured UI remaps do not belong to this input')
    ui_remaps = {row['from']: row for row in remaps['rows']}
    index = read(out/'source-guid-index.json')
    closure = read(out/'reconciled-closure.json')
    contracts = {}
    for relative in closure['files']:
        path = export/relative
        if not path.is_file():
            continue
        with path.open('rb') as stream:
            if stream.read(5) != b'%YAML':
                continue
        text = path.read_text()
        for file_id, guid in re.findall(r'm_Script: \{fileID: (-?\d+), guid: ([a-f0-9]{32}), type: \d+\}', text):
            key = guid+':'+file_id
            row = contracts.setdefault(key, dict(guid=guid, file_id=file_id, source_script=index.get(guid), consumers=[]))
            row['consumers'].append(relative)
            found = imported.get((guid, file_id))
            row['imported'] = found
            row['status'] = 'bound' if found and found['type'] else 'binding-unresolved'
            prior = ui_remaps.get('{fileID: '+file_id+', guid: '+guid+', type: 3}')
            if row['status'] != 'bound' and prior:
                target = re.search(r'fileID: (-?\d+), guid: ([a-f0-9]{32})', prior['to'])
                measured = imported.get((target[2], target[1])) if target else None
                if not measured or measured['type'] != prior['type']:
                    raise RuntimeError('Measured package UI binding regressed')
                row['remap'] = prior
                row['target_imported'] = measured
                row['status'] = 'binding-remap-verified'
    result = dict(contracts=list(contracts.values()),
                  summary=dict(Counter(row['status'] for row in contracts.values())),
                  initializers=runtime['initializers'], quarantine=[],
                  scope='Imported MonoScript identities and original initializer dependency graph. No content registration or platform checks invoked; remaps need typed validation.')
    write(destination/'result.json', result)
    write(out/'contracts-latest.json', dict(path=str(destination.relative_to(ROOT))))
    print(json.dumps(dict(result['summary'], initializers=len(runtime['initializers'])), indent=2))


def native_inventory():
    """Read container object identities in bulk; never infer an FBX mesh from its filename."""
    import UnityPy
    out = ROOT/read(WORK/'experiments/whole-catalog/latest.json')['path']
    metadata = read_catalog(catalog_path(out))
    closure = read(out/'host-closure.json')
    locations = {row['id']: row for row in metadata['locations']}
    bundle_ids = sorted({row.get('owning_bundle', (row.get('dependencies') or [None])[0]) for row in closure['unresolved']} - {None})
    accepted = read(WORK/'inventory/files.json')
    if accepted['input_id'] != read(WORK/'config/accepted-input.json')['input_id']:
        raise RuntimeError('Input drift; native inspection requires accepted input')
    file_index = {}
    for row in accepted['files']:
        file_index.setdefault(Path(row['path']).name, []).append(row)
    destination = out/('native-containers-'+now())
    destination.mkdir()
    receipts = []
    errors = []
    object_errors = []
    for ordinal, identity in enumerate(bundle_ids):
        location = locations[identity]
        basename = location['internalId'].replace('\\', '/').rsplit('/', 1)[-1]
        matches = file_index.get(basename, [])
        try:
            if len(matches) != 1:
                raise RuntimeError('Ambiguous or absent legitimate bundle input')
            source = game()/matches[0]['path']
            if sha(source) != matches[0]['sha256']:
                raise RuntimeError('Original bundle drift; explicitly review and accept')
            environment = UnityPy.load(str(source))
            containers = []
            for obj in environment.objects:
                if obj.type.name != 'AssetBundle':
                    continue
                bundle = obj.read()
                for address, info in bundle.m_Container:
                    try:
                        asset = info.asset.deref()
                        containers.append(dict(address=address, type=asset.type.name,
                                               name=asset.peek_name(), path_id=asset.path_id,
                                               serialized_file=asset.assets_file.name))
                    except Exception as exception:
                        failure = dict(address=address, category='native-object-read-failed', error=str(exception))
                        containers.append(failure)
                        object_errors.append(dict(failure, location=identity))
            if not containers:
                raise RuntimeError('No original asset container records')
            receipt = dict(location=identity, source=matches[0]['path'], sha256=matches[0]['sha256'], containers=containers)
            write(destination/(str(identity)+'.json'), receipt)
            receipts.append(dict(location=identity, containers=len(containers), source_sha256=matches[0]['sha256']))
            del environment
        except Exception as exception:
            errors.append(dict(location=identity, category='native-container-inspection-failed', error=str(exception)))
        if ordinal % 40 == 0:
            write(destination/'progress.json', dict(inspected=ordinal+1, total=len(bundle_ids), failures=len(errors)))
            print(json.dumps(dict(inspected=ordinal+1, total=len(bundle_ids), failures=len(errors))), flush=True)
    result = dict(success=not errors and not object_errors, bundles=receipts, errors=errors, object_errors=object_errors, quarantine=[],
                  scope='Original binary container identities only; no engine loading, asset equivalence or Android acceptance')
    write(destination/'result.json', result)
    write(out/'native-latest.json', dict(path=str(destination.relative_to(ROOT))))
    print(json.dumps(dict(inspected=len(receipts), failures=len(errors), evidence=str(destination.relative_to(ROOT)))))
    if not result['success']:
        raise RuntimeError('Original container inspection incomplete; preserve and inspect its first failure')
