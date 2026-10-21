import test from 'node:test';
import assert from 'node:assert/strict';
import {createController, validate} from '../controller.js';
const snapshot = (status = 'idle', capabilities = {prepare:true}) => ({status, capabilities, progress:null, message:'Host status'});
function fixture(initial = snapshot()) {
  let emit, calls = [], cleaned = 0;
  return {version:1, getState:async () => initial,
    subscribe:fn => { emit = fn; fn(initial); return () => cleaned++; },
    invoke:async action => { calls.push(action); },
    emit:value => emit(value), calls, get cleaned() { return cleaned; }};
}
test('disconnected default and capabilities fail closed', async () => {
  const c = createController();
  assert.equal(c.snapshot().status, 'unavailable');
  assert.equal(await c.invoke('launch'), false);
  const f = fixture(); await c.connect(f);
  assert.equal(c.can('prepare'), true); assert.equal(c.can('launch'), false);
  assert.equal(await c.invoke('launch'), false); assert.deepEqual(f.calls, []);
  await c.invoke('prepare'); assert.equal(c.snapshot().status, 'idle');
});
test('host snapshots only; invalid state disconnects and tears down', async () => {
  const c = createController(), f = fixture(); await c.connect(f);
  f.emit(snapshot('ready', {launch:true})); assert.equal(c.can('launch'), true);
  f.emit({...snapshot(), progress:101}); assert.equal(c.snapshot().status, 'unavailable');
  assert.equal(f.cleaned, 1); f.emit(snapshot('ready', {launch:true})); assert.equal(c.can('launch'), false);
});
test('repeated click blocked; stale completion cannot unlock new connection', async () => {
  const c = createController(), f = fixture(); let finish;
  f.invoke = () => new Promise(resolve => { finish = resolve; });
  await c.connect(f); const request = c.invoke('prepare');
  assert.equal(await c.invoke('prepare'), false);
  c.disconnect(); await c.connect(fixture(snapshot('ready', {launch:true})));
  finish(); assert.equal(await request, false); assert.equal(c.can('launch'), true);
});
test('stale connect ignored; operation failures close boundary', async () => {
  const c = createController(), slow = fixture(); let finish;
  slow.getState = () => new Promise(resolve => { finish = resolve; });
  const pending = c.connect(slow); const current = fixture(); await c.connect(current);
  finish(snapshot('ready', {launch:true})); await pending; assert.equal(c.can('launch'), false);
  current.invoke = async () => { throw new Error('private backend detail'); };
  await c.invoke('prepare'); assert.equal(c.snapshot().status, 'unavailable');
  assert.ok(!c.snapshot().message.includes('private backend detail'));
});
test('malformed adapters and teardown contract fail closed', async () => {
  const c = createController(); await c.connect({}); assert.equal(c.can('prepare'), false);
  const f = fixture(); f.subscribe = fn => { fn({...snapshot(), status:'bogus'}); return () => {}; };
  await c.connect(f); assert.equal(c.snapshot().status, 'unavailable');
  assert.throws(() => validate({...snapshot(), progress:NaN}));
  assert.throws(() => validate({...snapshot(), message:'x'.repeat(501)}));
  assert.equal(validate(snapshot('idle', {prepare:'true'})).capabilities.prepare, false);
});
test('host-authorized pause and resume work while preparation remains pending', async () => {
  const c = createController(), f = fixture(); let finish;
  f.invoke = action => {
    f.calls.push(action);
    if (action === 'prepare') {
      f.emit(snapshot('preparing', {pause:true}));
      return new Promise(resolve => { finish = resolve; });
    }
    f.emit(snapshot(action === 'pause' ? 'paused' : 'preparing',
      action === 'pause' ? {resume:true} : {pause:true}));
    return Promise.resolve();
  };
  await c.connect(f); const preparation = c.invoke('prepare');
  assert.equal(c.can('pause'), true);
  assert.equal(await c.invoke('pause'), true);
  assert.equal(c.snapshot().busy, true);
  assert.equal(c.can('resume'), true);
  assert.equal(await c.invoke('resume'), true);
  assert.deepEqual(f.calls, ['prepare', 'pause', 'resume']);
  finish(); await preparation;
  assert.equal(c.snapshot().busy, false);
});
test('pending actions stay visible but reject duplicate requests across state updates', async () => {
  const c = createController(), f = fixture(); let finish;
  f.invoke = () => new Promise(resolve => { finish = resolve; });
  await c.connect(f); const pending = c.invoke('prepare');
  assert.equal(c.offers('prepare'), true);
  assert.equal(c.can('prepare'), false);
  f.emit(snapshot());
  assert.equal(await c.invoke('prepare'), false);
  finish(); await pending;
  assert.equal(c.can('prepare'), true);
});
