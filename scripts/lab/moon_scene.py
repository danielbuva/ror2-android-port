"""Restore measured original Moon components into ignored generated scenes."""
import re
from pathlib import Path

from common import WORK, sha


def restore_pillar_beams(source_scene, generated_scene):
    source_scene, generated_scene = Path(source_scene).resolve(), Path(generated_scene).resolve()
    if (source_scene == generated_scene or
            not all(p.is_relative_to(WORK.resolve()) for p in (source_scene, generated_scene))):
        raise RuntimeError('Pillar transformation requires distinct ignored generated/source scenes')

    def blocks(text):
        return {re.match(r'--- !u!(\d+) &(-?\d+)', b)[2]: b
                for b in re.split(r'(?=^--- !u!)', text, flags=re.M)[1:]}

    source_text, generated_text = source_scene.read_text(), generated_scene.read_text()
    source, generated = blocks(source_text), blocks(generated_text)
    additions, attachments, groups = {}, {}, {}
    for object_id, block in source.items():
        if not block.startswith('--- !u!1 ') or not re.search(r'^  m_Name: Beam(?:, Strong)?$', block, re.M):
            continue
        components = re.findall(r'component: \{fileID: (-?\d+)\}', block)
        transform = next(source[i] for i in components if source[i].startswith('--- !u!4 '))
        parent_id = re.search(r'm_Father: \{fileID: (-?\d+)\}', transform)[1]
        parent_object = re.search(r'm_GameObject: \{fileID: (-?\d+)\}', source[parent_id])[1]
        parent_name = re.search(r'^  m_Name: (.+)$', source[parent_object], re.M)[1]
        if parent_name not in ('InactiveFX', 'ChargingFX', 'ChargedFX'):
            continue
        if object_id not in generated:
            raise RuntimeError('Pillar beam owner missing from generated scene')
        native = [i for i in components if source[i].startswith(('--- !u!198 ', '--- !u!199 '))]
        if len(native) != 2:
            raise RuntimeError('Original pillar particle/renderer pair differs')
        groups[parent_name] = groups.get(parent_name, 0) + 1
        owned = generated[object_id]
        for component_id in native:
            if component_id in generated:
                if generated[component_id] != source[component_id]:
                    raise RuntimeError('Existing pillar native component differs from source')
            else:
                additions[component_id] = source[component_id]
            link = '  - component: {fileID: ' + component_id + '}\n'
            if link not in owned:
                owned = owned.replace('  m_Component:\n', '  m_Component:\n' + link, 1)
                if link not in owned:
                    raise RuntimeError('Generated pillar component list missing')
        attachments[object_id] = owned
    if groups != {'InactiveFX': 16, 'ChargingFX': 16, 'ChargedFX': 16}:
        raise RuntimeError('Original Moon pillar beam inventory differs; review input')
    for object_id, replacement in attachments.items():
        generated_text = generated_text.replace(generated[object_id], replacement, 1)
    generated_text += ''.join(additions.values())
    generated_scene.write_text(generated_text)
    return {'source_sha256': sha(source_scene), 'generated_sha256': sha(generated_scene),
            'beam_objects': len(attachments), 'native_components_restored': len(additions),
            'groups': groups, 'source_native_components_unchanged': True}


def restore_moon_gravity(source_scene, generated_scene, script_identities):
    source_scene, generated_scene, script_identities = map(Path, (source_scene, generated_scene, script_identities))
    if (source_scene.resolve() == generated_scene.resolve() or
            not all(p.resolve().is_relative_to(WORK.resolve()) for p in (source_scene, generated_scene, script_identities))):
        raise RuntimeError('Moon gravity restoration requires distinct ignored scenes/identities')
    identities = [line.split('|') for line in script_identities.read_text().splitlines()]
    identity, = [row for row in identities if row[2] == 'RoR2.SetGravity']
    source_text, generated_text = source_scene.read_text(), generated_scene.read_text()
    source = re.split(r'(?=^--- !u!)', source_text, flags=re.M)[1:]
    components = [b for b in source if b.startswith('--- !u!114 ') and
                  ('m_Script: {fileID: ' + identity[0] + ', guid: ' + identity[1] + ',') in b]
    component, = components
    component_id = re.match(r'--- !u!114 &(-?\d+)', component)[1]
    owner_id = re.search(r'm_GameObject: \{fileID: (-?\d+)\}', component)[1]
    match = re.search(r'^--- !u!1 &' + owner_id + r'\n.*?(?=^--- !u!|\Z)', generated_text, re.M | re.S)
    if not match:
        raise RuntimeError('Original gravity owner missing from generated Moon scene')
    existing = re.search(r'^--- !u!114 &' + component_id + r'\n.*?(?=^--- !u!|\Z)', generated_text, re.M | re.S)
    if existing and existing[0] != component:
        raise RuntimeError('Existing Moon gravity component differs from original')
    link = '  - component: {fileID: ' + component_id + '}\n'
    owner = match[0]
    if link not in owner:
        owner = owner.replace('  m_Component:\n', '  m_Component:\n' + link, 1)
        if link not in owner:
            raise RuntimeError('Gravity owner component list missing')
    generated_text = generated_text.replace(match[0], owner, 1)
    if not existing:
        generated_text += component
    generated_scene.write_text(generated_text)
    return {'source_sha256': sha(source_scene), 'generated_sha256': sha(generated_scene),
            'component_id': component_id, 'owner_id': owner_id,
            'new_gravity': float(re.search(r'^  newGravity: (.+)$', component, re.M)[1]),
            'source_component_unchanged': True, 'added': not bool(existing)}


def restore_moon_escape(source_scene, generated_scene, script_identities):
    """Restore source callbacks and the dropship's own state/holdout lifecycle."""
    paths = list(map(lambda p: Path(p).resolve(), (source_scene, generated_scene, script_identities)))
    source_scene, generated_scene, script_identities = paths
    if source_scene == generated_scene or not all(p.is_relative_to(WORK.resolve()) for p in paths):
        raise RuntimeError('Escape restoration requires distinct ignored scenes/identities')

    def blocks(text):
        return {re.match(r'--- !u!\d+ &(-?\d+)', b)[1]: b
                for b in re.split(r'(?=^--- !u!)', text, flags=re.M)[1:]}

    source = blocks(source_scene.read_text())
    generated_text = generated_scene.read_text()
    generated = blocks(generated_text)
    identities = {(r[0], r[1]): r[2] for r in
                  (line.split('|') for line in script_identities.read_text().splitlines())}
    owners = {re.search(r'm_GameObject: \{fileID: (-?\d+)\}', b)[1]: i
              for i, b in source.items() if b.startswith(('--- !u!4 ', '--- !u!224 '))}

    def owner_path(go):
        name = re.search(r'^  m_Name: (.*)$', source[go], re.M)[1]
        parent = re.search(r'm_Father: \{fileID: (-?\d+)\}', source[owners[go]])[1]
        return (owner_path(re.search(r'm_GameObject: \{fileID: (-?\d+)\}', source[parent])[1]) + '/'
                if parent != '0' else '') + name

    def kind(block):
        match = re.search(r'm_Script: \{fileID: (-?\d+), guid: ([a-f0-9]+)', block)
        return identities.get((match[1], match[2]), '') if match else ''

    dropship_types = {'RoR2.OnEnableEvent', 'RoR2.OnDisableEvent', 'RoR2.AwakeEvent',
                     'RoR2.EntityLogic.Timer', 'RoR2.MultiBodyTrigger', 'RoR2.HoldoutZoneController',
                     'RoR2.Networking.NetworkChildActivation', 'RoR2.Networking.NetworkContextActivationGuard',
                     'RoR2.GenericObjectiveProvider'}
    selected, roles = {}, {}
    for i, block in source.items():
        if not block.startswith('--- !u!114 '):
            continue
        go = re.search(r'm_GameObject: \{fileID: (-?\d+)\}', block)[1]
        path, type_name = owner_path(go), kind(block)
        role = None
        if path.startswith('Moon2DropshipZone') and type_name in dropship_types:
            role = 'dropship'
        elif path == 'EscapeSequenceController' and type_name == 'RoR2.EntityLogic.DelayedEvent':
            role = 'escape-delay'
        elif ('/BrotherEncounter, Phase 4/PhaseObjects/CompletionEvents' in path and
              type_name == 'RoR2.OnDisableEvent' and 'm_MethodName: CallDelayed' in block):
            role = 'encounter-completion'
        elif path == 'EscapeSequenceController/EscapeSequenceObjects/FreeDropship' and type_name == 'RoR2.OnEnableEvent':
            role = 'release-dropship'
        if role:
            selected[i] = block
            roles[role] = roles.get(role, 0) + 1
    if any(roles.get(role) != 1 for role in ('escape-delay', 'encounter-completion', 'release-dropship')):
        raise RuntimeError('Original escape callback contract differs')
    if sum(kind(b) == 'RoR2.HoldoutZoneController' for b in selected.values()) != 1:
        raise RuntimeError('Original dropship holdout contract differs')
    selected_owners = {re.search(r'm_GameObject: \{fileID: (-?\d+)\}', b)[1] for b in selected.values()}
    # Preserve source networking identities and trigger physics on those same owners.
    for i, block in source.items():
        if block.startswith('--- !u!54 ') or (block.startswith('--- !u!114 ') and
                'm_Script: {fileID: 372142912, guid: d382a022563c7517aadbc92ca1060016' in block):
            if re.search(r'm_GameObject: \{fileID: (-?\d+)\}', block)[1] in selected_owners:
                selected[i] = block
    missing = {fid for block in selected.values() for fid in re.findall(r'\{fileID: (-?\d+)\}', block)
               if fid in source and source[fid].startswith('--- !u!114 ') and fid not in generated and fid not in selected}
    if missing:
        raise RuntimeError('Escape callbacks reference omitted source components: ' + str(sorted(missing)))
    additions, attachments = {}, {}
    for i, block in selected.items():
        if i in generated and generated[i] != block:
            raise RuntimeError('Existing escape component differs from original: ' + i)
        if i not in generated:
            additions[i] = block
        go = re.search(r'm_GameObject: \{fileID: (-?\d+)\}', block)[1]
        if go not in generated:
            raise RuntimeError('Original escape component owner missing: ' + go)
        owner = attachments.get(go, generated[go])
        link = '  - component: {fileID: ' + i + '}\n'
        if link not in owner:
            owner = owner.replace('  m_Component:\n', '  m_Component:\n' + link, 1)
            if link not in owner:
                raise RuntimeError('Escape owner component list missing')
        attachments[go] = owner
    for go, owner in attachments.items():
        generated_text = generated_text.replace(generated[go], owner, 1)
    generated_text += ''.join(additions.values())
    generated_scene.write_text(generated_text)
    return {'source_sha256': sha(source_scene), 'generated_sha256': sha(generated_scene),
            'restored': len(additions), 'roles': roles, 'source_components_unchanged': True,
            'components': [{'id': i, 'type': kind(b)} for i, b in selected.items()],
            'external_guids': sorted(set(re.findall(r'guid: ([a-f0-9]{32})', ''.join(selected.values()))))}
