"""Stage an original scene beside, never over, the accepted reduced scene."""
import hashlib
import json
import re
from pathlib import Path

from common import RECIPE, ROOT, WORK, game, read, run, sha, write


GLOBAL_OWNERS = frozenset({'RoR2Application', 'SceneInfo', 'Director', 'GameManager'})
OPTIONAL_GLOBAL_OWNER = 'Main Camera'
SCENES = {name: 'Base' for name in ('golemplains', 'foggyswamp', 'frozenwall',
          'dampcavesimple', 'skymeadow', 'wispgraveyard', 'shipgraveyard',
          'blackbeach', 'blackbeach2', 'golemplains2', 'goolake', 'rootjungle',
          'goldshores')}
SCENES['lakes'] = 'DLC2'
SCENES.update({name: 'DLC1' for name in ('ancientloft', 'snowyforest', 'sulfurpools')})
SCENES.update({name: 'DLC2' for name in ('habitat', 'habitatfall', 'helminthroost',
                                      'lakesnight', 'village', 'villagenight')})
# The original Wwise assembly has no authorized Android native engine. Keep
# scene-local game logic, but do not activate serialized native-audio clients.
# RTPCController is the game's own direct Wwise-only component on SceneInfo.
NO_AUDIO_GUID = '2b6c926553287666f24ffd5af5ba21cb'
NO_AUDIO_GAME_SCRIPT = ('-1095921540', '951ce57ad999ac1f040a4dceb5f8b763')
UNAVAILABLE_RENDER_SCRIPTS = {('-1252323107', '90eda32cd325c26600dacf144354b407'),
                              ('11500000', 'c716ef2e96be153a122ff34c6f228460')}


def stage_unavailable_audio():
    """Preserve dynamic source objects while reporting absent native audio."""
    from boundaries import probe_tool
    import shutil
    project = WORK / 'lab-project'
    marker = project / '.port-input.json'
    generation = read(marker)
    accepted = read(WORK / 'config/accepted-input.json')
    if generation['input_id'] != accepted['input_id']:
        raise RuntimeError('Audio boundary input differs from accepted generation')
    names = ('AK.Wwise.Unity.API.dll', 'AK.Wwise.Unity.MonoBehaviour.dll')
    original = game() / 'Risk of Rain 2_Data/Managed'
    stage = project / 'Assets/LabLoadingScene/Plugins'
    output = WORK / 'experiments/source-scenes/audio-boundary-v3'
    legacy = [WORK / 'experiments/source-scenes/audio-boundary-v2',
              WORK / 'experiments/source-scenes/audio-boundary']
    legacy_receipts = [(folder, read(folder / 'receipt.json')) for folder in legacy
                       if (folder / 'receipt.json').exists()]
    def source_and_stage_verified():
        for name in names:
            expected = generation['original_assemblies'][name]
            if sha(original / name) != expected:
                raise RuntimeError('Original Wwise assembly changed: ' + name)
            current = sha(stage / name)
            if current == expected and name not in generation['transformed_assemblies']:
                continue
            if (generation['transformed_assemblies'].get(name) == current and
                    any(receipt['input_id'] == generation['input_id']
                        and current == receipt['outputs'][name] and sha(folder / name) == current
                        for folder, receipt in legacy_receipts)):
                continue
            raise RuntimeError('Current Wwise staging differs from original and reviewed prior boundary: ' + name)
    if (output / 'receipt.json').exists():
        prior = read(output / 'receipt.json')
        if prior['input_id'] != generation['input_id'] or any(
            sha(output / name) != prior['outputs'][name] or
            sha(original / name) != generation['original_assemblies'][name]
            for name in names):
            raise RuntimeError('Existing local audio boundary differs from its receipt')
        if all(sha(stage / name) == prior['outputs'][name] and
               generation['transformed_assemblies'].get(name) == prior['outputs'][name]
               for name in names):
            return prior
        source_and_stage_verified()
        for name in names:
            shutil.copy2(output / name, stage / name)
            generation['transformed_assemblies'][name] = prior['outputs'][name]
        write(marker, generation)
        return prior
    output.mkdir(parents=True, exist_ok=True)
    source_and_stage_verified()
    api, mono = names
    report = json.loads(run(probe_tool() + ['--wwise-unavailable',
        original / api, output / api, generation['original_assemblies'][api],
        original / mono, output / mono, generation['original_assemblies'][mono], original], timeout=120).stdout)
    outputs = {api: report['api_output_sha256'], mono: report['mono_output_sha256']}
    if any(sha(output / name) != outputs[name] for name in names):
        raise RuntimeError('Audio boundary output hash mismatch')
    for name in names:
        shutil.copy2(output / name, stage / name)
        generation['transformed_assemblies'][name] = outputs[name]
    write(marker, generation)
    receipt = {'input_id': generation['input_id'], 'outputs': outputs, 'transformation': report}
    write(output / 'receipt.json', receipt)
    return receipt


def prepare(names=('lakes',)):
    project = WORK / 'lab-project'
    export = ROOT / read(WORK / 'config/reconstruction.json')['projects'][0]
    generation = read(project / '.port-input.json')
    accepted = read(WORK / 'config/accepted-input.json')
    if generation['input_id'] != accepted['input_id']:
        raise RuntimeError('Source scene input differs from the accepted generation')
    recipe_path = WORK / 'scene-probe-build.json'
    recipe = read(recipe_path)
    config_path = project / 'Assets/LabLoadingScene/Resources/MovementBatchProbe.json'
    config = read(config_path)
    remaps = {row['from']: row['to'] for row in read(RECIPE/'hud-ui-remaps.json')['rows']}
    staged = []
    for name in names:
        configured = {row['name'] for row in config['integratedStages']} | {'golemplains'}
        if name not in SCENES or name not in configured:
            raise RuntimeError('Unreviewed source scene: ' + name)
        source = export / 'Assets/RoR2' / SCENES[name] / 'Scenes' / name / (name + '.unity')
        text = source.read_text()
        header, body = text.split('--- !u!', 1)
        blocks = re.split(r'(?=^--- !u!)', '--- !u!' + body, flags=re.M)[1:]
        by_id = {re.match(r'--- !u!\d+ &(-?\d+)', block)[1]: block for block in blocks}
        roots = []
        for block in blocks:
            if not block.startswith(('--- !u!4 ', '--- !u!224 ')) or not re.search(r'^  m_Father: \{fileID: 0\}$', block, re.M):
                continue
            owner = re.search(r'm_GameObject: \{fileID: (-?\d+)\}', block)[1]
            game_object = by_id[owner]
            label = re.search(r'^  m_Name: (.*)$', game_object, re.M)[1]
            value = json.loads(label) if label.startswith('"') else label[1:-1].replace("''", "'") if label.startswith("'") else label
            roots.append((owner, value))
        owners = {owner for owner, label in roots if label in GLOBAL_OWNERS or label == OPTIONAL_GLOBAL_OWNER}
        if {label for _, label in roots if label in GLOBAL_OWNERS} != GLOBAL_OWNERS or len(owners) not in (4, 5):
            raise RuntimeError('Duplicate global-owner roots changed in original ' + name)
        counts = {'source_behaviours': sum(block.startswith('--- !u!114 ') for block in blocks),
                  'source_roots': len(roots), 'suppressed_global_roots': sorted(label for _, label in roots if label in GLOBAL_OWNERS or label == OPTIONAL_GLOBAL_OWNER)}
        for owner in owners:
            block = by_id[owner]
            if not re.search(r'^  m_IsActive: [01]$', block, re.M):
                raise RuntimeError('Original global-owner active state changed')
            by_id[owner] = re.sub(r'^  m_IsActive: 1$', '  m_IsActive: 0', block, count=1, flags=re.M)
        removed_audio = set()
        source_null = set()
        disabled_render = set()
        for fid, block in by_id.items():
            if not block.startswith('--- !u!114 '):
                continue
            if re.search(r'^  m_Script: \{fileID: 0\}$', block, re.M):
                source_null.add(fid)
                continue
            script = re.search(r'm_Script: \{fileID: (-?\d+), guid: ([a-f0-9]{32}), type: 3\}', block)
            if not script:
                continue
            if script[2] == NO_AUDIO_GUID or script.groups() == NO_AUDIO_GAME_SCRIPT:
                removed_audio.add(fid)
            elif script.groups() in UNAVAILABLE_RENDER_SCRIPTS:
                if not re.search(r'^  m_Enabled: 1$', block, re.M):
                    raise RuntimeError('Observed renderer callback state changed')
                disabled_render.add(fid)
                by_id[fid] = re.sub(r'^  m_Enabled: 1$', '  m_Enabled: 0', block, count=1, flags=re.M)
        if not removed_audio or not disabled_render:
            raise RuntimeError('Expected source audio/render callback populations absent')
        removed = removed_audio | source_null
        for fid, block in tuple(by_id.items()):
            if block.startswith('--- !u!1 '):
                by_id[fid] = re.sub(r'^  - component: \{fileID: (-?\d+)\}\n',
                                    lambda match: '' if match[1] in removed else match[0], block, flags=re.M)
        candidate = header + ''.join(by_id[fid] for block in blocks
                                     if (fid := re.match(r'--- !u!\d+ &(-?\d+)', block)[1]) not in removed)
        for before, after in remaps.items():
            candidate = candidate.replace(before, after)
        if 'guid: d3e719b59ab71ba3f6b398058c866280' in candidate:
            raise RuntimeError('Unmapped original Unity UI script identity in ' + name)
        if sum(block.startswith('--- !u!114 ') for block in re.split(r'(?=^--- !u!)', candidate, flags=re.M)) != counts['source_behaviours'] - len(removed):
            raise RuntimeError('Source behavior population changed unexpectedly')
        if any(re.search(r'component: \{fileID: '+fid+r'\}', candidate) for fid in removed):
            raise RuntimeError('Removed null/audio component retains a GameObject reference')
        target = project / 'Assets/LabLoadingScene/SourceScenes' / name / (name + '.unity')
        target.parent.mkdir(parents=True, exist_ok=True)
        scene_guid = hashlib.sha256(('ror2-android-source-scene:' + name + ':' + generation['input_id']).encode()).hexdigest()[:32]
        meta = Path(str(target) + '.meta')
        source_meta = Path(str(source) + '.meta').read_text()
        if not re.search(r'^guid: [a-f0-9]{32}$', source_meta, re.M):
            raise RuntimeError('Original scene metadata GUID unavailable')
        expected_meta = re.sub(r'^guid: [a-f0-9]{32}$', 'guid: ' + scene_guid, source_meta, count=1, flags=re.M)
        if target.exists() and target.read_text() != candidate:
            receipt = WORK / 'experiments/source-scenes/candidate.json'
            prior = read(receipt) if receipt.exists() else {}
            accepted_prior = next((row['candidate_sha256'] for row in prior.get('staged', []) if row['name'] == name), None)
            if not accepted_prior or sha(target) != accepted_prior or prior.get('input_id') != generation['input_id']:
                raise RuntimeError('Existing source-scene candidate differs from its owned receipt')
        if meta.exists() and meta.read_text() != expected_meta:
            raise RuntimeError('Existing source-scene metadata differs; inspect before replacing')
        target.write_text(candidate)
        meta.write_text(expected_meta)
        relative = str(target.relative_to(project))
        staged.append({'name': name, 'scene': relative, 'source_sha256': sha(source),
                       'candidate_sha256': sha(target), 'omitted_unavailable_audio_components': len(removed_audio),
                       'omitted_source_null_scripts': len(source_null),
                       'disabled_unavailable_render_components': len(disabled_render), **counts})
    recipe['sourceStageScenes'] = sorted(set(recipe.get('sourceStageScenes', []) + [row['scene'] for row in staged]))
    config['originalStageSceneNames'] = sorted(set(config.get('originalStageSceneNames', []) + [row['name'] for row in staged]))
    write(recipe_path, recipe)
    write(config_path, config)
    result = {'success': True, 'input_id': generation['input_id'], 'staged': staged,
              'scope': 'Original stage-local scene with duplicate global roots inactive; source-null scripts and measured unavailable native-audio components omitted, unsupported decal/shadow callbacks disabled. Current reduced scenes retained.'}
    out = WORK / 'experiments/source-scenes'
    out.mkdir(parents=True, exist_ok=True)
    write(out / 'candidate.json', result)
    return result
