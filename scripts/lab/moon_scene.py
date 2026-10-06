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
