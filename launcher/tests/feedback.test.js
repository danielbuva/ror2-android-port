import test from 'node:test';
import assert from 'node:assert/strict';
import {buildDraft, parsePreview, MAX_PREVIEW_LENGTH, MAX_NOTE_LENGTH} from '../feedback.js';

const fixture = (check = 'baseline') => ({
  schema:1, check, apk_sha256:'a'.repeat(64), reported_success:true,
  matches_local_current_build:false, failed_criteria_count:0, assisted:true,
  world_seconds:35, applied_profile_runs:13,
  cleanup:{selector_absent:true, process_absent:true, sleep_requested:true, display_asleep:true},
  ordinary_controls_qualified:false, full_run_qualified:false, visual_audio_parity_qualified:false,
  ...(check === 'stage-exit' ? {transitions:1, stage_world_seconds:10} : {}),
});
const notes = {steps:'Open setup', expected:'Continue', actual:'Setup pauses'};
test('baseline and stage-exit consume producer schema without changing reported claims', () => {
  for (const mode of ['baseline', 'stage-exit']) assert.deepEqual(parsePreview(JSON.stringify(fixture(mode))), fixture(mode));
  const failed = {...fixture(), reported_success:false, failed_criteria_count:2, world_seconds:null, applied_profile_runs:null};
  assert.deepEqual(parsePreview(JSON.stringify(failed)), failed);
});
test('unknown fields, nested data and issue URLs never enter the selected facts or draft', () => {
  const input = {...fixture(), message:'PRIVATE_SENTINEL', issue_draft_url:'https://invalid.example/PRIVATE_SENTINEL'};
  input.cleanup.unknown = {text:'PRIVATE_SENTINEL'};
  assert.deepEqual(parsePreview(JSON.stringify(input)), fixture());
  const draft = buildDraft(notes, JSON.stringify(input));
  assert.ok(!draft.includes('PRIVATE_SENTINEL'));
  assert.ok(draft.includes('not independently verified'));
  assert.ok(draft.includes('ordinary_controls_qualified'));
});
test('notes-only draft states its evidence limits and preserves literal user text', () => {
  const draft = buildDraft({...notes, actual:'<img src=x onerror=alert(1)>'});
  assert.ok(draft.includes('<img src=x onerror=alert(1)>'));
  assert.ok(draft.includes('not automatically redacted'));
  assert.ok(draft.includes('installed build and device behavior are unknown'));
  assert.ok(draft.includes('No logs or attachments collected'));
});
test('malformed, raw, oversized, contradictory and unqualified check data refuse', () => {
  const variants = [
    null, [], {}, {...fixture(), schema:2}, {...fixture(), check:'unknown'},
    {...fixture(), apk_sha256:'A'.repeat(64)}, {...fixture(), assisted:false},
    {...fixture(), ordinary_controls_qualified:true}, {...fixture(), full_run_qualified:true},
    {...fixture(), visual_audio_parity_qualified:true}, {...fixture(), reported_success:'true'},
    {...fixture(), failed_criteria_count:1}, {...fixture(), reported_success:false},
    {...fixture(), failed_criteria_count:10001}, {...fixture(), failed_criteria_count:0.1},
    {...fixture(), matches_local_current_build:null}, {...fixture(), world_seconds:-1},
    {...fixture(), world_seconds:604801}, {...fixture(), world_seconds:'35'},
    {...fixture(), applied_profile_runs:1.5}, {...fixture(), world_seconds:undefined},
    {...fixture(), cleanup:{...fixture().cleanup, selector_absent:false}},
    {...fixture(), cleanup:{...fixture().cleanup, process_absent:false}},
    {...fixture(), cleanup:{...fixture().cleanup, display_asleep:null}},
    {...fixture(), cleanup:{...fixture().cleanup, sleep_requested:'true'}},
    {...fixture('stage-exit'), transitions:null, stage_world_seconds:-1},
  ];
  for (const input of variants) assert.throws(() => parsePreview(JSON.stringify(input)));
  assert.throws(() => parsePreview('{'));
  assert.throws(() => parsePreview(' '.repeat(MAX_PREVIEW_LENGTH + 1)));
  assert.throws(() => parsePreview(JSON.stringify(fixture()).replace('"world_seconds":35', '"world_seconds":1e999')));
  assert.throws(() => buildDraft(notes, '{'));
});
test('manual notes are required and bounded, without silent truncation', () => {
  assert.throws(() => buildDraft({...notes, actual:'  '}));
  for (const field of ['steps', 'expected', 'actual']) {
    assert.throws(() => buildDraft({...notes, [field]:'x'.repeat(MAX_NOTE_LENGTH + 1)}));
    assert.throws(() => buildDraft({...notes, [field]:null}));
  }
});
