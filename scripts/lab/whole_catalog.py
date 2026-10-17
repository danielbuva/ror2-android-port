"""Whole shipped catalog discovery; no readiness whitelist or entitlement grants."""
from common import *
from scene_closure import REFERENCE
from collections import Counter, deque
import re


def copy_catalog_asset(source, target):
    """Bulk imports must not launch one subprocess for every asset and meta file."""
    import ctypes, shutil, sys
    source, target = Path(source), Path(target)
    if source.is_symlink() or target.is_symlink():
        raise RuntimeError('Catalog import refuses symlinks')
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists() and sys.platform == 'darwin':
        clone = ctypes.CDLL('/usr/lib/libSystem.B.dylib', use_errno=True).clonefile
        clone.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint32]
        clone.restype = ctypes.c_int
        if clone(str(source).encode(), str(target).encode(), 0) == 0:
            return
    shutil.copy2(source, target)


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


def scene_guid_owners(candidates, data, input_id):
    """Keep catalog GUID targets and give colliding exported scenes local IDs.

    A scene address and a serialized asset GUID are different identities. Only
    repair scenes when the original catalog explicitly disambiguates both paths.
    """
    index, repairs = {}, []
    locations = {row['id']: row for row in data['locations']}
    keys = {row['key']: row['locations'] for row in data['keys'] if row.get('keyType', 'System.String')=='System.String'}
    scene_paths = {row['internalId'] for row in data['locations'] if row.get('type', '').split(',')[0]=='UnityEngine.ResourceManagement.ResourceProviders.SceneInstance'}
    for guid, paths in candidates.items():
        if len(paths)==1:
            index[guid]=paths[0]
            continue
        targets={locations[identity]['internalId'] for identity in keys.get(guid, [])}
        if len(targets)!=1 or not targets<=set(paths) or not set(paths)<=scene_paths or any(not path.endswith('.unity') for path in paths):
            raise RuntimeError('Ambiguous exported GUID identity: '+guid)
        owner=next(iter(targets));index[guid]=owner
        for path in sorted(set(paths)-{owner}):
            generated=digest(dict(input_id=input_id,source_guid=guid,scene_path=path))[:32]
            if generated in candidates or generated in index:
                raise RuntimeError('Generated scene GUID collision')
            index[generated]=path
            repairs.append(dict(source=path,source_guid=guid,guid=generated,catalog_guid_owner=owner,
                                reason='Distinct original scene address; exported GUID belongs to another scene'))
    return index, repairs


def runtime_key_roots(data, candidates, legacy_aliases=None):
    """Exact IL address literals; provider labels retain their own typed loader.

    A stage name or label appearing in an unrelated string comparison is not an
    asset request. Accept catalog addresses, internal paths, GUID keys and exact
    aliases resolved by the shipped LegacyResourcesAPI initializer only.
    """
    keys = {row['key']: row['locations'] for row in data['keys'] if row.get('keyType', 'System.String') == 'System.String'}
    locations = {row['id']: row for row in data['locations']}
    roots, edges = set(), []
    for row in candidates:
        key=(legacy_aliases or {}).get(row['key'],row['key'])
        found = [identity for identity in keys.get(key, []) if locations[identity]['internalId'].startswith('Assets/')
                 and (re.fullmatch(r'[a-fA-F0-9]{32}',key) or key in (locations[identity].get('primaryKey'),locations[identity]['internalId']))]
        if found:
            roots.update(found)
            edges.append(dict(key=key, source_key=row['key'], locations=found, methods=row['methods']))
    return roots, edges


def analyze(source, export, index, helper, native_overrides=None, runtime_candidates=(), legacy_aliases=None):
    data = read_catalog(source)
    categories = list(dict.fromkeys(re.findall(r'FindLocationsThenAddLoadOperation(?:<[^>]+>)?\(AddressablesLabels\.(\w+)', helper)))
    if not categories:
        raise RuntimeError('Original provider category contract absent')
    packs, roots = catalog_roots(data, categories)
    locations = {row['id']: row for row in data['locations']}
    if len(locations) != len(data['locations']):
        raise RuntimeError('Duplicate catalog location identity')
    for row in locations.values():
        if not set(row['dependencies']) <= locations.keys():
            raise RuntimeError('Broken original catalog dependency')
    runtime_roots, runtime_edges = runtime_key_roots(data, runtime_candidates,legacy_aliases)
    seeds = roots | runtime_roots
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
                                   dependency_count=len(row['dependencies']), category=reason, catalog_root=row['id'] in roots, runtime_root=row['id'] in runtime_roots))
    key_locations = {row['key']: row['locations'] for row in data['keys'] if row.get('keyType', 'System.String') == 'System.String'}
    # Serialized references and runtime AssetReference keys are different edges.
    pending = deque(converted[identity]['source'] for identity in sorted(seeds) if identity in converted)
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
        # BakedEffectData.assetGUID feeds EffectDef's original async reference;
        # unlike Unity's AssetReference it has no m_ prefix in serialized data.
        # Native state preloads store runtime GUID keys as plain YAML strings,
        # outside both PPtr and AssetReference fields. Follow the entire family.
        preload_blocks = re.findall(r'^  preloadGUIDReferences:[ \t]*\n((?:  -[^\n]*\n?)*)', text, re.M)
        preloads = {value.strip() for block in preload_blocks for value in re.findall(r'^  -(.*)$', block, re.M)}
        invalid_preloads = sorted(key for key in preloads if not re.fullmatch(r'[a-f0-9]{32}', key))
        if invalid_preloads:
            issues.append(dict(source=relative, keys=invalid_preloads, category='invalid-preload-key'))
        valid_preloads = preloads - set(invalid_preloads)
        for guid in set(re.findall(r'\b(?:m_AssetGUID|assetGUID):\s*([a-f0-9]{32})', text)) | valid_preloads:
            targets = key_locations.get(guid, [])
            if guid in valid_preloads:
                runtime_roots.update(targets)
                runtime_edges.append(dict(key=guid, locations=targets, source=relative, field='preloadGUIDReferences'))
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
        runtime_key_edges=len(runtime_edges), runtime_roots=len(runtime_roots),
        resolved_runtime_roots=len(runtime_roots & converted.keys()),
        unresolved_runtime_roots=sorted(runtime_roots-converted.keys()),
        root_types=dict(Counter(locations[x]['type'].split(',')[0] if locations[x]['type'] else 'unresolved-type' for x in roots)),
        converted_locations=len(converted), unresolved_locations=len(unresolved),
        unresolved_root_locations=[row['id'] for row in unresolved if row['catalog_root']],
        closure_files=len(seen), closure_bytes=total_bytes, closure_suffixes=dict(suffixes),
        soft_reference_edges=len(soft_edges), issues=dict(Counter(row['category'] for row in issues)),
        quarantine=[],
        scope='Host metadata/serialized closure only. Unresolved conversion is not incompatibility. No loading, registration, gameplay, ownership or Android acceptance.',
    )
    return dict(summary=summary, packs=packs, roots=sorted(roots), runtime_roots=sorted(runtime_roots), runtime_key_edges=runtime_edges, converted=converted,
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
    collision_receipt = out/'typed-import-conversions.json'
    if collision_receipt.exists():
        corrected = read(collision_receipt)
        if corrected['metadata_sha256'] != sha(catalog_path(out)):
            raise RuntimeError('Typed import corrections belong to a different catalog')
        conversions.update(corrected['conversions'])
    assembly_hash = sha(game()/'Risk of Rain 2_Data/Managed/RoR2.dll')
    key = digest(dict(input=assembly_hash, ilspy='11.0.0.9375', args='project-referencepath-csharp9-v2'))
    helper = WORK/'decompiled/RoR2'/key[:16]/'RoR2.ContentManagement/AddressablesLoadHelper.cs'
    contract=read(out/'original-catalog-contract.json')
    if contract['input_sha256']!=assembly_hash:
        raise RuntimeError('Runtime key metadata belongs to different input')
    legacy_hash=next(row['sha256'] for row in read(WORK/'inventory/files.json')['files'] if row['path']=='Risk of Rain 2_Data/Managed/LegacyResourcesAPI.dll')
    if contract.get('legacyInputSha256')!=legacy_hash:
        raise RuntimeError('Refresh the native catalog contract for the accepted legacy assembly')
    result = analyze(catalog_path(out), export, index, helper.read_text(), conversions, contract.get('assetKeyCandidates', []),contract.get('legacyAliases',{}))
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
    candidates = {}
    for meta in (export/'Assets').rglob('*.meta'):
        match = re.search(r'^guid:\s*([a-f0-9]{32})', meta.read_text(errors='replace'), re.M)
        if not match:
            continue
        relative = str(Path(str(meta)[:-5]).relative_to(export))
        candidates.setdefault(match[1], []).append(relative)
    data=read_catalog(source)
    index, repairs=scene_guid_owners(candidates, data, read(WORK/'inventory/files.json')['input_id'])
    write(out/'source-guid-repairs.json', repairs)
    if list(dict.fromkeys(re.findall(r'FindLocationsThenAddLoadOperation(?:<[^>]+>)?\(AddressablesLabels\.(\w+)', helper.read_text())))!=read(out/'original-catalog-contract.json')['categories']:
        raise RuntimeError('Recovered provider categories disagree with original IL')
    contract=read(out/'original-catalog-contract.json')
    result = analyze(source, export, index, helper.read_text(), runtime_candidates=contract.get('assetKeyCandidates', []),legacy_aliases=contract.get('legacyAliases',{}))
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
    if 'PROVIDER_TYPES' in code:
        from boundaries import probe_tool
        original = game()/'Risk of Rain 2_Data/Managed/RoR2.dll'
        expected = next(row['sha256'] for row in read(WORK/'inventory/files.json')['files'] if row['path']=='Risk of Rain 2_Data/Managed/RoR2.dll')
        contract = json.loads(run(probe_tool()+['--catalog-contract', original], timeout=120).stdout)
        if contract['input_sha256']!=expected:
            raise RuntimeError('Provider contract belongs to unaccepted input')
        expected_legacy=next(row['sha256'] for row in read(WORK/'inventory/files.json')['files'] if row['path']=='Risk of Rain 2_Data/Managed/LegacyResourcesAPI.dll')
        if contract['legacyInputSha256']!=expected_legacy:
            raise RuntimeError('Legacy resource contract belongs to unaccepted input')
        write(out/'original-catalog-contract.json', contract)
        code = code.replace('PROVIDER_TYPES', 'new string[]{'+','.join(json.dumps(name) for name in contract['providers'])+'}')
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
    version=toolchain()['unity_version']
    code='if(Application.unityVersion!='+json.dumps(version)+'||EditorUtility.scriptCompilationFailed||EditorApplication.isCompiling||EditorApplication.isUpdating||EditorApplication.isPlayingOrWillChangePlaymode||BuildPipeline.isBuildingPlayer)throw new System.Exception("Catalog evidence requires the exact editor with current compiled source and idle state");'+code
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


def inspect_native_bundle(identity, locations, file_index):
    """Read one accepted original container, including typed subasset entries."""
    import UnityPy
    basename=locations[identity]['internalId'].replace('\\', '/').rsplit('/',1)[-1]
    matches=file_index.get(basename,[])
    if len(matches)!=1:
        raise RuntimeError('Ambiguous or absent legitimate bundle input')
    source=game()/matches[0]['path']
    if sha(source)!=matches[0]['sha256']:
        raise RuntimeError('Original bundle drift; explicitly review and accept')
    environment=UnityPy.load(str(source))
    containers=[]
    for obj in environment.objects:
        if obj.type.name!='AssetBundle':
            continue
        for address,info in obj.read().m_Container:
            asset=info.asset.deref()
            containers.append(dict(address=address,type=asset.type.name,name=asset.peek_name(),
                                   path_id=asset.path_id,serialized_file=asset.assets_file.name))
    if not containers:
        raise RuntimeError('No original asset container records')
    return dict(location=identity,source=matches[0]['path'],sha256=matches[0]['sha256'],containers=containers)


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


def repair_support_source(export, mapped, project, destination):
    """Resolve one observed decompiler ambiguity from the original field types."""
    relative='Assets/Scripts/Assembly-CSharp/AffixBeadProjectileSound.cs'
    if relative not in mapped:
        return
    from boundaries import probe_tool
    binary=game()/'Risk of Rain 2_Data/Managed/Assembly-CSharp.dll'
    expected=next(row['sha256'] for row in read(WORK/'inventory/files.json')['files'] if row['path']=='Risk of Rain 2_Data/Managed/Assembly-CSharp.dll')
    contract=json.loads(run(probe_tool()+[binary,'AffixBeadProjectileSound'],timeout=120).stdout)
    if contract['sha256']!=expected or len(contract['types'])!=1:
        raise RuntimeError('Recovered support source requires the accepted original field contract')
    fields={row['name']:row['type'] for row in contract['types'][0]['fields']}
    if fields!={'SpawnBeadChaseEvent':'AK.Wwise.Event','ExplodeEvent':'AK.Wwise.Event'}:
        raise RuntimeError('Observed support source ambiguity changed; inspect original types')
    source=export/relative;target=project/mapped[relative];text=source.read_text()
    corrected='using Event = AK.Wwise.Event;\n'+text
    if target.read_text() not in (text,corrected):
        raise RuntimeError('Unexpected edits to recovered support source')
    target.write_text(corrected)
    write(destination/'support-source-alias.json',dict(source=relative,target=mapped[relative],
          source_sha256=sha(source),output_sha256=sha(target),original_assembly_sha256=expected,fields=fields,
          scope='Qualify the two original audio-event field types; original methods unchanged; no audio availability claim'))


def source_mesh_subobjects(export, closure, metadata, native):
    """Resolve original GUID[subobject] mesh keys to exact native/exported objects.

    AssetRipper exports FBX mesh subobjects as separate .asset files. A typed
    main-FBX location cannot identify which mesh the shipped SkinDef requested.
    Require both the serialized name and the native container identity before
    adding a location; leave missing/ambiguous references explicit.
    """
    pattern = re.compile(r'm_AssetGUID: ([a-f0-9]{32})\s*\n\s*m_SubObjectName: ([^\n]+)\s*\n\s*m_SubObjectType: UnityEngine.Mesh,')
    locations = {row['id']: row for row in metadata['locations']}
    guid_locations = {row['key']: row['locations'] for row in metadata['keys']
                      if row.get('keyType', 'System.String') == 'System.String' and re.fullmatch(r'[a-f0-9]{32}', row['key'])}
    issues = {row['location']: row for row in native['issues']}
    seen, resolved, unresolved = set(), [], []
    for relative in closure['files']:
        path = export/relative
        if path.suffix not in {'.asset', '.prefab', '.unity'} or not path.is_file():
            continue
        with path.open('rb') as stream:
            if stream.read(5) != b'%YAML':
                continue
        for guid, raw_name in pattern.findall(path.read_text()):
            name = raw_name.strip()
            if name.startswith('"'):
                name = json.loads(name)
            elif name.startswith("'") and name.endswith("'"):
                name = name[1:-1].replace("''", "'")
            key = guid+'['+name+']'
            if key in seen:
                continue
            seen.add(key)
            mesh_ids = [identity for identity in guid_locations.get(guid, [])
                        if locations[identity]['type'].startswith('UnityEngine.Mesh,')]
            candidates = []
            for identity in mesh_ids:
                issue = issues.get(identity)
                if issue:
                    candidates.extend(issue.get('objects', []))
                else:
                    candidates.append(closure['converted'].get(str(identity), {}).get('native', {}))
            matches = {(row['source'], row['native_path_id']) for row in candidates
                       if row.get('type') == 'Mesh' and row.get('name') == name
                       and row.get('source') and (export/row['source']).is_file()}
            if len(mesh_ids) == 1 and len(matches) == 1:
                source, path_id = next(iter(matches))
                resolved.append(dict(key=key, source=source, native_path_id=path_id,
                                     type=locations[mesh_ids[0]]['type'], original_location=mesh_ids[0]))
            else:
                unresolved.append(dict(key=key, source=relative, mesh_locations=mesh_ids,
                                       matching_native_exports=len(matches)))
    return resolved, unresolved


def exported_mesh_signature(path):
    """Compare structural mesh data, never a same-named export filename alone."""
    import hashlib
    text = path.read_text()
    vertex = re.search(r'^    m_VertexCount: (\d+)$', text, re.M)
    submeshes = re.search(r'^  m_SubMeshes:\n(.*?)(?=^  m_Shapes:)', text, re.M | re.S)
    index = re.search(r'^  m_IndexBuffer: ([0-9a-f]+)$', text, re.M)
    data = re.search(r'^    _typelessdata: ([0-9a-f]+)$', text, re.M)
    if not vertex or not submeshes or not index or not data:
        return None
    fields = ('firstByte', 'indexCount', 'topology', 'baseVertex', 'firstVertex', 'vertexCount')
    rows = re.split(r'^  - serializedVersion: \d+\n', submeshes[1], flags=re.M)[1:]
    values = [tuple(int(re.search(r'^    '+field+r': (-?\d+)$', row, re.M)[1])
                    for field in fields) for row in rows]
    return (int(vertex[1]), tuple(values), hashlib.sha256(bytes.fromhex(index[1])).hexdigest(),
            hashlib.sha256(bytes.fromhex(data[1])).hexdigest()) if values else None


def native_mesh_signature(tree):
    import hashlib
    fields = ('firstByte', 'indexCount', 'topology', 'baseVertex', 'firstVertex', 'vertexCount')
    try:
        return (int(tree['m_VertexData']['m_VertexCount']),
                tuple(tuple(int(row[field]) for field in fields) for row in tree['m_SubMeshes']),
                hashlib.sha256(bytes(tree['m_IndexBuffer'])).hexdigest(),
                hashlib.sha256(bytes(tree['m_VertexData']['m_DataSize'])).hexdigest())
    except (KeyError, TypeError, ValueError, OverflowError):
        return None


def recover_ambiguous_mesh_subobjects(export, unresolved, metadata, native, receipts, accepted):
    """Resolve only unique native/export mesh signatures from accepted binaries."""
    import UnityPy
    locations = {row['id']: row for row in metadata['locations']}
    issues = {row['location']: row for row in native['issues']}
    files = {row['path']: row['sha256'] for row in accepted['files']}
    if accepted['input_id'] != read(WORK/'config/accepted-input.json')['input_id']:
        raise RuntimeError('Ambiguous mesh recovery requires accepted input')
    needed = {}
    for row in unresolved:
        if len(row['mesh_locations']) != 1:
            continue
        identity = row['mesh_locations'][0]
        name = row['key'].split('[', 1)[1][:-1]
        failures = [failure for failure in issues.get(identity, {}).get('failures', [])
                    if failure['category'] == 'ambiguous-exported-object'
                    and failure['native']['type'] == 'Mesh' and failure['native']['name'] == name]
        if len(failures) != 1:
            continue
        owner = locations[identity]['dependencies'][0]
        needed.setdefault(owner, []).append((row, identity, failures[0]))
    resolved = []
    for owner, requests in needed.items():
        receipt = receipts/('%s.json' % owner)
        if not receipt.exists():
            continue
        evidence = read(receipt)
        source = evidence['source']
        if evidence['location'] != owner or source not in files or evidence['sha256'] != files[source] or sha(game()/source) != files[source]:
            raise RuntimeError('Original mesh bundle receipt or accepted hash differs')
        environment = UnityPy.load(str(game()/source))
        objects = {(obj.assets_file.name, obj.path_id): obj for obj in environment.objects if obj.type.name == 'Mesh'}
        for row, identity, failure in requests:
            original = failure['native']
            obj = objects.get((original['serialized_file'], original['path_id']))
            if obj is None:
                continue
            signature = native_mesh_signature(obj.read_typetree())
            matches = [candidate for candidate in failure['candidates']
                       if (export/candidate).is_file() and exported_mesh_signature(export/candidate) == signature]
            if signature is None or len(matches) != 1:
                continue
            resolved.append(dict(key=row['key'], source=matches[0], native_path_id=original['path_id'],
                                 type=locations[identity]['type'], original_location=identity,
                                 resolution='native-mesh-signature'))
        del environment
    return resolved


def prepare_integration():
    """Import the complete discovered closure, reusing existing GUID owners once."""
    from build import preflight
    preflight()
    out = ROOT/read(WORK/'experiments/whole-catalog/latest.json')['path']
    export = ROOT/read(WORK/'config/reconstruction.json')['projects'][0]
    closure = read(out/'reconciled-closure.json')
    if closure['input_id'] != read(WORK/'config/accepted-input.json')['input_id']:
        raise RuntimeError('Whole catalog belongs to different input')
    metadata = read_catalog(catalog_path(out))
    native = read(out/'native-conversions.json')
    mesh_subobjects, unresolved_mesh_subobjects = source_mesh_subobjects(export, closure, metadata, native)
    receipts = ROOT/read(out/'native-latest.json')['path']
    recovered = recover_ambiguous_mesh_subobjects(export, unresolved_mesh_subobjects, metadata, native,
                                                   receipts, read(WORK/'inventory/files.json'))
    mesh_subobjects.extend(recovered)
    unresolved_mesh_subobjects = [row for row in unresolved_mesh_subobjects
                                  if row['key'] not in {entry['key'] for entry in recovered}]
    index = read(out/'source-guid-index.json')
    guids = {path: guid for guid, path in index.items()}
    repairs = {row['source']: row for row in read(out/'source-guid-repairs.json')} if (out/'source-guid-repairs.json').exists() else {}
    project = WORK/'lab-project'
    owners = {}
    for meta in (project/'Assets').rglob('*.meta'):
        match = re.search(r'^guid:\s*([a-f0-9]{32})', meta.read_text(errors='replace'), re.M)
        if match:
            if match[1] in owners:
                raise RuntimeError('Duplicate imported GUID; refuse ambiguous whole-content ownership')
            owners[match[1]] = str(Path(str(meta)[:-5]).relative_to(project))
    remaps = read(WORK/'config/hud-ui-remaps.json')
    if remaps['input_id'] != closure['input_id']:
        raise RuntimeError('UI remaps belong to different input')
    destination = out/('integration-'+now())
    destination.mkdir()
    mapped = {}
    copies = []
    # Copy each original identity once. Do not overwrite the accepted composition.
    for relative in sorted(set(closure['files']) | {row['source'] for row in mesh_subobjects}):
        source = export/relative
        guid = guids.get(relative)
        if not guid or not source.is_file():
            raise RuntimeError('Missing discovered source identity: '+relative)
        existing = owners.get(guid)
        if existing:
            mapped[relative] = existing
            continue
        if source.suffix == '.dll':
            # Exporter DLLs are not the receipted original runtime plugin inputs.
            # Their references are already measured through the binding remap table.
            continue
        target_relative = 'Assets/WholeGame/'+relative.removeprefix('Assets/')
        target = project/target_relative
        copy_catalog_asset(source, target)
        copy_catalog_asset(Path(str(source)+'.meta'), Path(str(target)+'.meta'))
        if relative in repairs:
            repair=repairs[relative];meta=Path(str(target)+'.meta')
            original='guid: '+repair['source_guid']
            if meta.read_text().count(original)!=1 or guid!=repair['guid']:
                raise RuntimeError('Measured scene GUID repair no longer matches export')
            meta.write_text(meta.read_text().replace(original,'guid: '+guid))
        with source.open('rb') as stream:
            yaml = stream.read(5) == b'%YAML'
        if yaml:
            text = source.read_text()
            for row in remaps['rows']:
                text = text.replace(row['from'], row['to'])
            if text != source.read_text():
                target.write_text(text)
        mapped[relative] = target_relative
        owners[guid] = target_relative
        copies.append(dict(source=relative, target=target_relative, sha256=sha(target),meta_sha256=sha(Path(str(target)+'.meta'))))
    repair_support_source(export,mapped,project,destination)
    for copied in copies:
        copied['sha256']=sha(project/copied['target'])
    roots = set(closure['roots']) | set(closure.get('runtime_roots', []))
    locations = []
    for row in metadata['locations']:
        conversion = closure['converted'].get(str(row['id']))
        if conversion and conversion['source'] in mapped:
            locations.append(dict(id=row['id'], path=mapped[conversion['source']], type=row['type'],
                                  primaryKey=row['primaryKey'], root=row['id'] in roots))
    next_location_id=max(row['id'] for row in metadata['locations'])+1
    subobject_keys=[]
    for row in mesh_subobjects:
        if row['source'] not in mapped:
            raise RuntimeError('Exact original mesh subobject was not staged: '+row['key'])
        locations.append(dict(id=next_location_id,path=mapped[row['source']],type=row['type'],
                              primaryKey=row['key'],root=False))
        subobject_keys.append(dict(key=row['key'],keyType='System.String',locations=[next_location_id]))
        next_location_id+=1
    if not roots <= {row['id'] for row in locations}:
        raise RuntimeError('Provider roots lost during staging')
    manifest = dict(input_id=closure['input_id'], attempt=destination.name,
                    locations=locations, keys=metadata['keys']+subobject_keys, providers=metadata['providers'],
                    source_catalog_sha256=closure['source_catalog_sha256'],
                    roots=sorted(roots), provider_roots=closure['roots'], runtime_roots=closure.get('runtime_roots', []), quarantine=[])
    write(destination/'manifest.json', manifest)
    write(destination/'mesh-subobjects.json',dict(resolved=mesh_subobjects,unresolved=unresolved_mesh_subobjects,
                                                   scope='Exact original serialized GUID/name/type and native container/export identity; unresolved refs stay explicit'))
    write(destination/'import-receipt.json', dict(copied=copies, reused=len(mapped)-len(copies),
                                               files=len(mapped), roots=len(roots)))
    write(out/'integration-latest.json', dict(path=str(destination.relative_to(ROOT))))
    copy_catalog_asset(ROOT/'tools/unity/WholeCatalogLoader.cs', project/'Assets/LabLoadingScene/WholeCatalogLoader.cs')
    copy_catalog_asset(ROOT/'tools/unity/WholeCatalogBootstrap.cs', project/'Assets/LabLoadingScene/WholeCatalogBootstrap.cs')
    copy_catalog_asset(ROOT/'tools/catalog/WholeCatalogHost.cs', project/'Assets/Editor/WholeCatalogHost.cs')
    print(json.dumps(dict(copied=len(copies), reused=len(mapped)-len(copies), roots=len(roots),
                          mapped_locations=len(locations), evidence=str(destination.relative_to(ROOT)))))


def host_integration():
    """Cheap engine import/type checks before a large Android content build."""
    out = ROOT/read(WORK/'experiments/whole-catalog/latest.json')['path']
    attempt = ROOT/read(out/'integration-latest.json')['path']
    export_catalog(attempt, 'ValidateWholeCatalog.cs.txt', 'host-integration.json')
    result = read(attempt/'host-integration.json')
    print(json.dumps(result['summary'], indent=2))
    if not result['success']:
        raise RuntimeError('Whole-content import has concrete failures; inspect host-integration.json')


def host_providers():
    import time
    out = ROOT/read(WORK/'experiments/whole-catalog/latest.json')['path']
    attempt = ROOT/read(out/'integration-latest.json')['path']
    result_path = attempt/'host-provider-result.json'
    if result_path.exists():
        result_path.rename(attempt/('host-provider-previous-'+now()+'.json'))
    export_catalog(attempt, 'StartWholeCatalog.cs.txt', 'host-provider-dispatch.json')
    deadline = time.monotonic()+300
    while time.monotonic()<deadline:
        if result_path.exists():
            result = read(result_path)
            if result.get('success') or result.get('error') or result.get('finished'):
                print(json.dumps(result, indent=2))
                if not result['success']:
                    raise RuntimeError('Original content-provider integration failed; retain attributed evidence')
                return
        time.sleep(2)
    raise RuntimeError('Host provider dispatch has no terminal result; inspect before repeating')


def repair_root_bindings():
    """Resolve exporter filename collisions by measured script/type identity."""
    out = ROOT/read(WORK/'experiments/whole-catalog/latest.json')['path']
    attempt = ROOT/read(out/'integration-latest.json')['path']
    failed = read(attempt/'host-integration.json')['failures']
    export = ROOT/read(WORK/'config/reconstruction.json')['projects'][0]
    closure = read(out/'reconciled-closure.json')
    metadata = read_catalog(catalog_path(out))
    locations = {row['id']: row for row in metadata['locations']}
    contracts = ROOT/read(out/'contracts-latest.json')['path']
    runtime = read(contracts/'runtime-contracts.json')
    scripts = {(row['guid'], str(row['fileId'])): row['type'] for row in runtime['scripts']}
    conversions = read(out/'native-conversions.json')['conversions']
    correction_path=out/'typed-import-conversions.json'
    if correction_path.exists():
        corrections=read(correction_path)
        if corrections['metadata_sha256']!=sha(catalog_path(out)):
            raise RuntimeError('Typed import corrections belong to a different catalog')
        conversions.update(corrections['conversions'])
    repairs = []
    file_index={}
    for file in read(WORK/'inventory/files.json')['files']:
        file_index.setdefault(Path(file['path']).name,[]).append(file)
    for failure in failed:
        row = locations[failure['id']]
        if row['id'] not in set(closure['roots'])|set(closure.get('runtime_roots',[])):
            raise RuntimeError('Unexpected non-root import failure')
        old = closure['converted'][str(row['id'])]['source']
        wanted = row['type'].split(',')[0]
        if wanted in ('UnityEngine.Material','UnityEngine.Texture2D'):
            owner=row['dependencies'][0]
            receipt=attempt/('typed-import-native-'+str(owner)+'.json')
            if not receipt.exists():
                write(receipt,inspect_native_bundle(owner,locations,file_index))
            original=read(receipt)
            accepted=next(file for file in read(WORK/'inventory/files.json')['files'] if file['path']==original['source'])
            if original['sha256']!=accepted['sha256'] or original['location']!=owner:
                raise RuntimeError('Typed subasset receipt belongs to different input')
            kind=wanted.rsplit('.',1)[-1]
            native=[entry for entry in original['containers'] if entry['address'].casefold()==row['internalId'].casefold() and entry['type']==kind]
            exported={}
            for candidate in (export/old).parent.iterdir():
                if candidate.suffix=='.meta' or not candidate.is_file():
                    continue
                with candidate.open('rb') as stream:
                    prefix=stream.read(16384)
                text=prefix.decode(errors='replace') if prefix.startswith(b'%YAML') else ''
                header=re.search(r'^--- !u!(\d+)',text,re.M)
                name=re.search(r'^  m_Name: (.*)$',text,re.M)
                asset_kind={21:'Material',28:'Texture2D'}.get(int(header[1])) if header else None
                object_name=name[1] if name else None
                if candidate.suffix.lower() in ('.png','.tga','.jpg','.exr'):
                    asset_kind,object_name='Texture2D',candidate.stem
                if asset_kind and object_name:
                    exported.setdefault((str(Path(old).parent),asset_kind,object_name),[]).append(str(candidate.relative_to(export)))
            objects,issues=native_candidates(native,exported)
            if issues or len(objects)!=1:
                raise RuntimeError('Original typed subasset conversion remains ambiguous: '+str(dict(location=row['id'],objects=objects,issues=issues)))
            conversion=dict(source=objects[0]['source'],resolution='original-typed-container',native=objects[0],original_internal_id=row['internalId'])
            conversions[str(row['id'])]=conversion
            repairs.append(dict(location=row['id'],previous=old,conversion=conversion))
            continue
        name = Path(row['internalId']).stem
        candidates = []
        for candidate in (export/old).parent.glob('*.asset'):
            with candidate.open('rb') as stream:
                text = stream.read(65536).decode(errors='replace')
            script = re.search(r'm_Script: \{fileID: (-?\d+), guid: ([a-f0-9]{32}), type: \d+\}', text)
            object_name = re.search(r'^  m_Name: (.*)$', text, re.M)
            if script and object_name and object_name[1] == name and scripts.get((script[2], script[1])) == wanted:
                candidates.append(str(candidate.relative_to(export)))
        if len(candidates) != 1:
            raise RuntimeError('Typed collision unresolved: '+str(dict(location=row['id'], candidates=candidates)))
        conversion = dict(source=candidates[0], resolution='typed-script-export-collision',
                          original_internal_id=row['internalId'], expected_type=wanted)
        conversions[str(row['id'])] = conversion
        repairs.append(dict(location=row['id'], previous=old, conversion=conversion))
    write(attempt/'typed-import-repairs.json', repairs)
    prior_corrections = read(out/'typed-import-conversions.json')['conversions'] if (out/'typed-import-conversions.json').exists() else {}
    prior_corrections.update({str(row['location']):row['conversion'] for row in repairs})
    write(out/'typed-import-conversions.json', dict(metadata_sha256=sha(catalog_path(out)), conversions=prior_corrections))
    assembly_hash = sha(game()/'Risk of Rain 2_Data/Managed/RoR2.dll')
    key = digest(dict(input=assembly_hash, ilspy='11.0.0.9375', args='project-referencepath-csharp9-v2'))
    helper = WORK/'decompiled/RoR2'/key[:16]/'RoR2.ContentManagement/AddressablesLoadHelper.cs'
    contract=read(out/'original-catalog-contract.json')
    if contract['input_sha256']!=assembly_hash:
        raise RuntimeError('Runtime key metadata belongs to different input')
    result = analyze(catalog_path(out), export, read(out/'source-guid-index.json'), helper.read_text(), conversions, contract.get('assetKeyCandidates',[]))
    result.update(input_id=closure['input_id'], source_catalog_sha256=closure['source_catalog_sha256'], metadata_sha256=sha(catalog_path(out)))
    write(out/'reconciled-closure.json', result)
    print(json.dumps(dict(repaired=len(repairs), closure_files=len(result['files']))))



def original_stage_contexts(export, stages, input_id, pool_keys):
    """Recover native population policy from each original serialized scene."""
    from source_scene_candidate import SCENES
    export=Path(export);contexts={}
    fields={'ignoreArtifactsThatRebuildCards':bool,'contentSourceMixLimitOverride':bool,
            'contentSourceMixLimitOverrideValue':int,'contentInteractableOnlySourceMixLimitOverride':bool,
            'contentInteractableOnlySourceMixLimitOverrideValue':int,
            'sceneDirectorInteractibleCredits':int,'sceneDirectorMonsterCredits':int}
    for stage in stages:
        if stage not in SCENES:
            raise RuntimeError('Unreviewed original stage population source: '+stage)
        scene_root=SCENES[stage]
        source=export/('Assets/RoR2/'+scene_root+'/Scenes/'+stage+'/'+stage+'.unity')
        blocks=re.split(r'(?=^--- !u!)',source.read_text(),flags=re.M)
        records=[block for block in blocks
                 if re.search(r'^  monsterDccsPool:',block,re.M)]
        if len(records)!=1:raise RuntimeError('Original stage population context is ambiguous: '+stage)
        record=records[0];result={'source_sha256':sha(source),'fields':{}}
        for name in ['monsterDccsPool','interactableDccsPool']:
            match=re.search(r'^  '+name+r': \{fileID: [-0-9]+, guid: ([a-f0-9]{32}), type: [0-9]+\}',record,re.M)
            if not match:raise RuntimeError('Original stage pool reference missing: '+stage+'/'+name)
            if match[1] not in pool_keys:raise RuntimeError('Stage pool has no unique typed runtime location: '+stage+'/'+name)
            result[name]=pool_keys[match[1]]
        for name,kind in fields.items():
            match=re.search(r'^  '+name+r': (-?\d+)$',record,re.M)
            if not match:raise RuntimeError('Original stage population policy missing: '+stage+'/'+name)
            value=int(match[1]);result['fields'][name]=bool(value) if kind is bool else value
        directors=[block for block in blocks if re.search(r'^  usePlacedSpawnPoints:',block,re.M)]
        if len(directors)!=1:raise RuntimeError('Original scene director is ambiguous: '+stage)
        result['director_fields']={}
        for name,kind in {'usePlacedSpawnPoints':bool,'expRewardCoefficient':float,'eliteBias':float,'spawnDistanceMultiplier':float}.items():
            match=re.search(r'^  '+name+r': ([-0-9.eE+]+)$',directors[0],re.M)
            if not match:raise RuntimeError('Original scene director policy missing: '+stage+'/'+name)
            result['director_fields'][name]=bool(int(match[1])) if kind is bool else float(match[1])
        if not re.search(r'^  monsterSpawnTargetOverride: \{fileID: 0\}$',directors[0],re.M):
            raise RuntimeError('Original scene monster target requires a measured binding: '+stage)
        objects={};transforms={};game_transforms={}
        for block in blocks:
            header=re.match(r'--- !u!(\d+) &(-?\d+)',block)
            if not header:continue
            kind,identity=map(int,header.groups())
            if kind==1:
                name=re.search(r'^  m_Name: (.*)$',block,re.M)
                if name:objects[identity]=name[1]
            elif kind in (4,224):
                owner=re.search(r'^  m_GameObject: \{fileID: (-?\d+)\}',block,re.M)
                parent=re.search(r'^  m_Father: \{fileID: (-?\d+)\}',block,re.M)
                if owner and parent:transforms[identity]=(int(owner[1]),int(parent[1]));game_transforms[int(owner[1])]=identity
        def object_path(identity):
            path=[];seen=set();current=game_transforms.get(identity)
            while current:
                if current in seen or current not in transforms:raise RuntimeError('Original bonus object hierarchy invalid: '+stage)
                seen.add(current);owner,current=transforms[current];path.append(objects[owner])
            if not path:raise RuntimeError('Original bonus object is absent: '+stage)
            return '/'.join(reversed(path))
        bonus=re.search(r'^  bonusInteractibleCreditObjects:(.*?)(?=^  [A-Za-z_]\w*:|\Z)',record,re.S|re.M)
        if not bonus:raise RuntimeError('Original bonus credit policy missing: '+stage)
        entries=list(re.finditer(r'^  - objectThatGrantsPointsIfEnabled: \{fileID: (-?\d+)\}\n    points: (-?\d+)$',bonus[1],re.M))
        if bonus[1].strip()!='[]' and (not entries or len(entries)!=bonus[1].count('objectThatGrantsPointsIfEnabled:')):
            raise RuntimeError('Original bonus credit entry is unresolved: '+stage)
        result['bonus_credits']=[{'path':object_path(int(match[1])),'points':int(match[2])} for match in entries]
        contexts[stage]=result
    return {'input_id':input_id,'stages':contexts,'scope':'Original pool, scene-director policy and bonus-credit object identities. Android retains continuous-body entry and teleporter lifecycle adapters.'}


# A player build only roots an assembly whose types it saw serialized. Asset bundles
# built earlier in the same editor process count; a code-only build in a fresh editor
# reuses the payload and sees none, so the linker then strips reflected Addressables
# operations (J30-J33, J505). Preserve the set the device-verified J503 build rooted
# instead of depending on editor process history (J506).
BUNDLE_ROOT_ASSEMBLIES = ('AK.Wwise.Unity.API', 'AK.Wwise.Unity.API.WwiseTypes', 'GenericIK',
                          'KinematicCharacterController', 'Rewired_Core', 'Unity.Postprocessing.Runtime',
                          'Unity.ResourceManager', 'com.unity.multiplayer-hlapi.Runtime')


def preservation_descriptor(roots):
    """Return the whole-catalog link.xml for measured type roots and bundle-rooted assemblies."""
    import xml.etree.ElementTree as ET
    linker=ET.Element('linker')
    for name in sorted(set(roots)|set(BUNDLE_ROOT_ASSEMBLIES)):
        assembly=ET.SubElement(linker,'assembly',fullname=name)
        if name in BUNDLE_ROOT_ASSEMBLIES:
            assembly.set('preserve','all')
        for type_name in sorted(roots.get(name,())):
            ET.SubElement(assembly,'type',fullname=type_name.replace('+','/'),preserve='all')
    return ET.tostring(linker,encoding='unicode')


def build_integration(code_only=False):
    from build import build, freeze_whole_payload, WHOLE_PLAYER_INPUTS
    from animation_bindings import repair as repair_animation_bindings
    from body_visual_map import generate as generate_body_visual_map
    from common_assets_map import generate as generate_common_asset_map
    out = ROOT/read(WORK/'experiments/whole-catalog/latest.json')['path']
    attempt = ROOT/read(out/'integration-latest.json')['path']
    if not read(attempt/'host-integration.json')['success']:
        raise RuntimeError('Whole roots must pass typed import before building')
    manifest = read(attempt/'manifest.json')
    project = WORK/'lab-project'
    assembly_hash=sha(game()/'Risk of Rain 2_Data/Managed/RoR2.dll')
    decompile_key=digest(dict(input=assembly_hash,ilspy='11.0.0.9375',args='project-referencepath-csharp9-v2'))
    source=WORK/'decompiled/RoR2'/decompile_key[:16]/'RoR2/CharacterBody.cs'
    contract=read(out/'original-catalog-contract.json')
    if contract['input_sha256']!=assembly_hash or manifest['input_id']!=read(WORK/'config/accepted-input.json')['input_id']:
        raise RuntimeError('Original body visual references belong to another accepted input')
    visual_map=generate_body_visual_map(source,project/'Assets/LabLoadingScene/OriginalBodyVisualMap.cs',manifest['input_id'],contract['legacyAliases'],manifest)
    health_source=source.with_name('HealthComponent.cs')
    health_visual_map=generate_body_visual_map(health_source,project/'Assets/LabLoadingScene/OriginalHealthVisualMap.cs',manifest['input_id'],contract['legacyAliases'],manifest)
    if health_visual_map['unlocated_fields']:
        raise RuntimeError('Original health visual references are absent from the accepted content closure')
    common_map=generate_common_asset_map(source.with_name('GlobalEventManager.cs'),project/'Assets/LabLoadingScene/OriginalGlobalCommonAssetMap.cs',manifest['input_id'],contract['legacyAliases'],manifest,{'groundOnHitPrefab','hollowPack'})
    write(WORK/'body-visual-map-latest.json',dict(body=visual_map,health=health_visual_map))
    write(WORK/'global-common-map-latest.json',common_map)
    animation_bindings = repair_animation_bindings(project)
    if code_only and animation_bindings['repaired']:
        raise RuntimeError('Original animation curves changed; a content build is required')
    if animation_bindings['repaired'] or animation_bindings['unresolved']:
        write(WORK/'animation-bindings-latest.json', animation_bindings)
    if (WORK/'scene-probe-build.json').exists() and not (project/'Assets/LabLoadingScene/Resources/MovementBatchProbe.json').is_file():
        raise RuntimeError('Composed session is not staged for this generation; migrate it before building against an old scene recipe')
    stage_config=project/'Assets/LabLoadingScene/Resources/MovementBatchProbe.json'
    if stage_config.exists():
        stages=[row['name'] for row in read(stage_config).get('stageCombatDecks',[])]
        export=ROOT/read(WORK/'config/reconstruction.json')['projects'][0]
        pool_keys={}
        for row in manifest['locations']:
            if not row['type'].startswith('RoR2.DccsPool,'):continue
            meta=(project/(row['path']+'.meta')).read_text()
            guid=re.search(r'^guid: ([a-f0-9]{32})$',meta,re.M)[1]
            if guid in pool_keys and pool_keys[guid]!=row['primaryKey']:
                raise RuntimeError('Ambiguous stage pool serialized owner')
            pool_keys[guid]=row['primaryKey']
        write(project/'Assets/LabLoadingScene/Resources/WholeStageContexts.json',original_stage_contexts(export,stages,manifest['input_id'],pool_keys))
    # A code-only build must compile every authored runtime source already in
    # the project. The former hand-maintained list omitted DOT and debug-input
    # fixes while still producing a successful but stale APK.
    runtime = project/'Assets/LabLoadingScene'
    copy_catalog_asset(ROOT/'tools/unity/GoldshoresBoundary.cs', runtime/'GoldshoresBoundary.cs')
    for source_file in sorted((ROOT/'tools/unity').glob('*.cs')):
        if (runtime/source_file.name).is_file() or 'Assets/LabLoadingScene/'+source_file.name in WHOLE_PLAYER_INPUTS:
            copy_catalog_asset(source_file, runtime/source_file.name)
    for filename in ['AndroidProgressionHost.cs','AndroidDiscoveryHost.cs']:
        copy_catalog_asset(ROOT/'tools/catalog'/filename, project/'Assets/Editor'/filename)
    body_boundary=project/'Assets/LabLoadingScene/BodyCatalogBoundary.cs'
    body_text=body_boundary.read_text()
    if 'WholeCatalogComposed.Prepare' not in body_text:
        body_text=body_text.replace(' IEnumerator RegisterBodyCatalog(){',' IEnumerator RegisterBodyCatalog(){\n  if(Resources.Load<TextAsset>("WholeCatalogBootstrap")){var shared=WholeCatalogComposed.Prepare();while(shared.MoveNext())yield return shared.Current;}')
        body_text=body_text.replace('ReleaseObjectiveBundlePreload();CleanupRecoveredText();','ReleaseObjectiveBundlePreload();CleanupRecoveredText();\n  if(Resources.Load<TextAsset>("WholeCatalogBootstrap"))WholeCatalogComposed.Release();')
        body_boundary.write_text(body_text)
    # Bundle-only serialized components and reflected location types are invisible
    # to the APK linker. Preserve their measured contracts, not a tested whitelist.
    roots={}
    for row in manifest['locations']:
        type_name, assembly = row['type'].split(',')[:2]
        roots.setdefault(assembly.strip(),set()).add(type_name)
    contract_dir=ROOT/read(out/'contracts-latest.json')['path']
    for row in read(contract_dir/'result.json')['contracts']:
        bound=row.get('target_imported') or row.get('imported')
        if bound and bound['type']:
            roots.setdefault(bound['assembly'],set()).add(bound['type'])
    # Native achievement registration discovers these original classes through
    # reflection; preserve their metadata, constructors and threshold properties.
    progression={'RoR2.UnlockableCatalog','RoR2.AchievementManager','RoR2.RegisterAchievementAttribute',
                 'RoR2.LocalUser','RoR2.UserAchievementManager','RoR2.Achievements.*'}
    roots.setdefault('RoR2',set()).update(progression)
    link_path=project/'Assets/LabLoadingScene/WholeCatalogPreservation/link.xml'
    link_path.parent.mkdir(exist_ok=True)
    link_path.write_text(preservation_descriptor(roots))
    copy_catalog_asset(ROOT/'tools/catalog/WholeCatalogBuild.cs', project/'Assets/Editor/WholeCatalogBuild.cs')
    # Extend the accepted integration; no regeneration of its large stage snapshots.
    runtime = project/'Assets/LabLoadingScene/MovementBatchProbe.cs'
    text = runtime.read_text()
    guard='  if(File.Exists(System.IO.Path.Combine(Application.persistentDataPath,"whole-catalog-selection.json")))yield break;'
    if guard not in text:
        needle=' IEnumerator Start(){'
        if text.count(needle)!=1:
            raise RuntimeError('Accepted integration entry point changed')
        text=text.replace(needle,needle+'\n'+guard)
        runtime.write_text(text)
    closure = read(out/'reconciled-closure.json')
    if closure['input_id'] != manifest['input_id']:
        raise RuntimeError('Source preload evidence belongs to another accepted input')
    missing_preloads = sorted({row['key'] for row in closure['runtime_key_edges']
                               if row.get('field') == 'preloadGUIDReferences' and not row.get('locations')})
    write(project/'Assets/LabLoadingScene/Resources/WholeCatalogBootstrap.json',
          dict(attempt=manifest['attempt'], input_id=manifest['input_id'],
               missingSourcePreloadKeys=missing_preloads))
    write(WORK/'whole-catalog-build.json', dict(manifest=str(attempt/'manifest.json')))
    if code_only:
        for rel in sorted(WHOLE_PLAYER_INPUTS):
            if not rel.endswith('.cs'):
                continue
            source=ROOT/'tools/unity'/Path(rel).name
            if source.is_file() and sha(source)!=sha(project/rel):
                raise RuntimeError('Code-only source was not staged: '+rel)
    previous = attempt/'build.json'
    if previous.exists():
        previous.rename(attempt/('build-previous-'+now()+'.json'))
    result = build('vulkan', force=True,reuse_payload=code_only)
    write(attempt/'build.json', result)
    if not code_only:
        freeze_whole_payload(project,result)


def run_integration():
    """One broad, attributed device scan; leave the ordinary game launch available."""
    import time
    from device import Device, PACKAGE
    from build import preflight
    preflight()
    out = ROOT/read(WORK/'experiments/whole-catalog/latest.json')['path']
    attempt = ROOT/read(out/'integration-latest.json')['path']
    evidence = attempt/('device-'+now())
    evidence.mkdir()
    d = Device()
    result = dict(success=False)
    selection_path = None
    try:
        result['install'] = d.install(read(WORK/'config/current-build.json')['apk'])
        result['bootstrap'] = d.launch()
        runtime = read(WORK/'device/runtime.json')['persistentDataPath']
        result['sync'] = d.sync()
        candidate_selection = runtime+'/whole-catalog-selection.json'
        if d.sh('sh', '-c', 'test ! -e '+candidate_selection+' || echo present', check=False).strip() == 'present':
            raise RuntimeError('Unexpected existing catalog launch selection')
        source = WORK/'generated-android-data/whole-catalog.json'
        write(evidence/'selection.json', dict(manifest_sha256=sha(source)))
        d.cmd('push', str(evidence/'selection.json'), candidate_selection)
        selection_path = candidate_selection
        d.sh('am', 'force-stop', PACKAGE)
        previous_report = runtime+'/whole-catalog-result.json'
        previous = d.sh('cat', previous_report, check=False)
        if previous:
            (evidence/'previous-runtime.txt').write_text(previous)
        d.sh('rm', '-f', previous_report)
        d.display(True)
        result['launch'] = d.sh('am', 'start', '-W', '-n', PACKAGE+'/com.unity3d.player.UnityPlayerActivity')
        started = time.monotonic()
        deadline = started+480
        while time.monotonic()<deadline:
            pid = d.sh('pidof', PACKAGE, check=False).strip()
            if not pid:
                raise RuntimeError('Integrated catalog process exited')
            result['pid'] = pid
            text = d.sh('cat', previous_report, check=False)
            try:
                record = json.loads(text)
            except ValueError:
                record = None
            if record:
                write(evidence/'runtime.json', record)
                if record.get('finished'):
                    result['runtime'] = record
                    result['success'] = record['success']
                    break
            time.sleep(1)
        if 'runtime' not in result:
            raise RuntimeError('Whole-catalog scan has no terminal result')
        result['seconds'] = time.monotonic()-started
    except Exception as error:
        result['error'] = str(error)
        raise
    finally:
        try:
            d.collect('all', evidence/'capture')
        finally:
            d.sh('am', 'force-stop', PACKAGE)
            if selection_path:
                d.sh('rm', '-f', selection_path)
            d.display(False)
            write(evidence/'result.json', result)
            write(attempt/'device-latest.json', dict(path=str(evidence.relative_to(ROOT))))
    print(json.dumps(dict(success=result['success'], runtime=result.get('runtime'), evidence=str(evidence.relative_to(ROOT))), indent=2))
    if not result['success']:
        raise RuntimeError('Whole-catalog Android integration failed; inspect first attributed failure')
