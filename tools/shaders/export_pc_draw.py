"""Export one existing D3D11 RenderDoc draw; never launch or modify the game.

API contract: RenderDoc v1.35 replay headers. Real replay remains unverified
until a legitimate PC capture and its matching RenderDoc runtime are available.
Every program, resource, constant and owner record remains under ignored work/.
"""
import argparse
import hashlib
import json
from pathlib import Path


def digest(data):
    return hashlib.sha256(data).hexdigest()


def record(value, depth=0):
    """Keep typed replay fields, including bindings; reject silent truncation."""
    if depth > 16:
        raise ValueError('Replay record exceeded measured depth')
    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    if isinstance(value, (bytes, bytearray)):
        return {'bytes': len(value), 'sha256': digest(value)}
    if type(value).__name__ == 'ResourceId':
        return str(value)
    if hasattr(value, '__iter__'):
        return [record(x, depth + 1) for x in value]
    fields = {}
    for name in dir(value):
        if name.startswith('_') or name in ['this', 'thisown', 'reflection', 'bytecode']:
            continue
        child = getattr(value, name)
        if not callable(child):
            fields[name] = record(child, depth + 1)
    return {'type': type(value).__name__, 'fields': fields} if fields else str(value)


def find_draw(actions, event, draw_flag):
    for action in actions:
        if action.eventId == event:
            if not action.flags & draw_flag:
                raise ValueError('Selected event is not a draw')
            return action
        found = find_draw(action.children, event, draw_flag)
        if found is not None:
            return found
    return None


def export(controller, rd, event, output, unity=None, native_records=()):
    if controller.GetAPIProperties().pipelineType != rd.GraphicsAPI.D3D11:
        raise ValueError('Only the original D3D11 capture contract is supported')
    action = find_draw(controller.GetRootActions(), event, rd.ActionFlags.Drawcall)
    if action is None:
        raise ValueError('Draw event absent from this capture')
    controller.SetFrameEvent(event, True)
    pipeline = controller.GetPipelineState()
    state = controller.GetD3D11PipelineState()
    result = {'schema_version': 1, 'event_id': event, 'action': {k: record(getattr(action, k)) for k in ['flags', 'numIndices', 'numInstances', 'indexOffset', 'vertexOffset', 'instanceOffset']},
              'api': record(controller.GetAPIProperties()), 'stages': [],
              'input_assembly': record(state.inputAssembly),
              'rasterizer': record(state.rasterizer), 'output_merger': record(state.outputMerger),
              'textures': record(controller.GetTextures()), 'buffers': record(controller.GetBuffers()),
              'resources': record(controller.GetResources()),
              'unity': unity, 'owner_association': 'unavailable',
              'limits': ['Texture media remains in the hashed capture; no pixel ownership inference.',
                         'Unity renderer/material/frame association requires synchronized evidence.']}
    if unity:
        if unity.get('event_id') != event or not unity.get('association_evidence'):
            raise ValueError('Unity sidecar has no evidence linking it to this draw')
        result['owner_association'] = 'supplied-evidence-requires-review'
    for name in ['Vertex', 'Hull', 'Domain', 'Geometry', 'Pixel']:
        stage = getattr(rd.ShaderStage, name)
        reflection = pipeline.GetShaderReflection(stage)
        if reflection is None:
            continue
        code = bytes(reflection.rawBytes)
        if not code.startswith(b'DXBC'):
            raise ValueError('Captured stage does not expose original DXBC: ' + name)
        path = output / (name + '.dxbc')
        path.write_bytes(code)
        constants = []
        for index, used in enumerate(pipeline.GetConstantBlocks(stage, True)):
            binding = used.descriptor
            data = bytes(controller.GetBufferData(binding.resource, binding.byteOffset, binding.byteSize))
            if len(data) != binding.byteSize:
                raise ValueError('Captured constant buffer extent differs')
            file = output / (name + '-cb-' + str(index) + '.bin')
            file.write_bytes(data)
            constants.append({'binding': record(used), 'file': file.name, 'sha256': digest(data), 'bytes': len(data)})
        result['stages'].append({'stage': name, 'shader_id': str(pipeline.GetShader(stage)),
                                'entry_point': pipeline.GetShaderEntryPoint(stage),
                                'file': path.name, 'dxbc_sha256': digest(code),
                                'native_program_matches': [r for r in native_records if r.get('dxbc_sha256') == digest(code)],
                                'input_signature': record(reflection.inputSignature),
                                'output_signature': record(reflection.outputSignature),
                                'constant_layout': record(reflection.constantBlocks),
                                'constants': constants,
                                'read_only_resources': record(pipeline.GetReadOnlyResources(stage, True)),
                                'samplers': record(pipeline.GetSamplers(stage))})
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('capture', type=Path)
    parser.add_argument('event', type=int)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--unity-record', type=Path)
    parser.add_argument('--native-records', type=Path, help='Private original native-records.json; match exact DXBC hashes')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    output = args.output.resolve()
    if not output.is_relative_to(root / 'work') or output.exists():
        raise ValueError('Use a fresh ignored work/ directory')
    import renderdoc as rd
    output.mkdir(parents=True)
    capture = rd.OpenCaptureFile()
    controller = None
    status = {'success': False, 'capture_sha256': digest(args.capture.read_bytes()),
              'RenderDoc_version': rd.GetVersionString(), 'runtime_API_validation': False,
              'native_records_sha256': digest(args.native_records.read_bytes()) if args.native_records else None,
              'unity_record_sha256': digest(args.unity_record.read_bytes()) if args.unity_record else None}
    try:
        opened = capture.OpenFile(str(args.capture), '', None)
        if opened != rd.ResultCode.Succeeded:
            raise RuntimeError(str(opened))
        opened, controller = capture.OpenCapture(rd.ReplayOptions(), None)
        if opened != rd.ResultCode.Succeeded:
            raise RuntimeError(str(opened))
        unity = json.loads(args.unity_record.read_text()) if args.unity_record else None
        native = json.loads(args.native_records.read_text()) if args.native_records else []
        result = export(controller, rd, args.event, output, unity, native)
        (output / 'draw.json').write_text(json.dumps(result, indent=2))
        status.update(success=True, runtime_API_validation=True, event_id=args.event)
    except Exception as error:
        status['first_failure'] = str(error)
        raise
    finally:
        if controller is not None:
            controller.Shutdown()
        capture.Shutdown()
        (output / 'receipt.json').write_text(json.dumps(status, indent=2))


if __name__ == '__main__':
    main()
