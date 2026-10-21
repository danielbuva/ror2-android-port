// Display contract only. The host must independently authorize every operation.
export const actions = Object.freeze(['selectFiles', 'prepare', 'pause', 'resume', 'retry', 'launch']);
const allowed = {
  idle: ['selectFiles', 'prepare'], preparing: ['pause'], paused: ['resume'],
  error: ['selectFiles', 'retry'], ready: ['selectFiles', 'launch'], unavailable: []
};
export function unavailable(message = 'Launcher backend is not connected.') {
  return {status: 'unavailable', progress: null, message, capabilities: {}};
}
export function validate(value) {
  if (!value || !Object.hasOwn(allowed, value.status)) throw new Error('Invalid status');
  if (value.progress !== null && (!Number.isFinite(value.progress) || value.progress < 0 || value.progress > 100)) throw new Error('Invalid progress');
  if (typeof value.message !== 'string' || value.message.length > 500) throw new Error('Invalid message');
  if (!value.capabilities || typeof value.capabilities !== 'object') throw new Error('Invalid capabilities');
  return Object.freeze({status: value.status, progress: value.progress, message: value.message,
    capabilities: Object.freeze(Object.fromEntries(actions.map(a => [a, value.capabilities[a] === true])))});
}
export function createController(onChange = () => {}) {
  let state = validate(unavailable()), adapter = null, unsubscribe = null, generation = 0;
  const pending = new Set();
  const snapshot = () => ({...state, busy: pending.size > 0});
  const notify = () => onChange(snapshot());
  function disconnect(message) {
    generation++;
    const cleanup = unsubscribe;
    unsubscribe = null; adapter = null; pending.clear();
    state = validate(unavailable(message));
    try { cleanup?.(); } finally { notify(); }
  }
  const offers = action => !!adapter && allowed[state.status].includes(action) && state.capabilities[action] === true;
  const can = action => offers(action) && !pending.has(action);
  async function connect(next) {
    disconnect();
    const token = generation;
    try {
      if (next?.version !== 1 || typeof next.getState !== 'function' || typeof next.subscribe !== 'function' || typeof next.invoke !== 'function') throw new Error('Invalid adapter');
      const initial = await next.getState();
      if (token !== generation) return;
      state = validate(initial); adapter = next;
      // subscribe must deliver the latest snapshot immediately, then every change.
      const cleanup = next.subscribe(value => {
        if (token !== generation) return;
        try { state = validate(value); notify(); }
        catch { disconnect('Backend state unavailable. Reconnect to continue.'); }
      });
      if (typeof cleanup !== 'function') throw new Error('Missing teardown');
      if (token !== generation) { cleanup(); return; }
      unsubscribe = cleanup;
      notify();
    } catch { if (token === generation) disconnect('Backend connection failed. Reconnect to continue.'); }
  }
  async function invoke(action) {
    if (!can(action)) return false;
    const token = generation;
    pending.add(action); notify();
    try {
      await adapter.invoke(action);
      // Completion alone never implies preparation/launch success. Only host state does.
      return token === generation;
    } catch {
      if (token === generation) disconnect('Operation failed. Reconnect to inspect backend state.');
      return false;
    } finally { if (token === generation) { pending.delete(action); notify(); } }
  }
  return {snapshot, offers, can, connect, invoke, disconnect};
}
