import './app.js';

// The native host exposes only state and fixed preparation actions. No paths,
// file contents, credentials, cross-window messages or shell operations cross it.
const native = window.OwnerPayload;
const subscribers = new Set();
let timer = null;
const state = () => JSON.parse(native.getState());
const publish = () => {
  const snapshot = state();
  for (const listener of subscribers) listener(snapshot);
};
if (native && typeof native.getState === 'function' && typeof native.invoke === 'function') {
  await window.launcher.connect({
    version: 1,
    getState: async () => state(),
    subscribe(listener) {
      subscribers.add(listener);
      listener(state());
      if (timer === null) timer = setInterval(publish, 300);
      return () => {
        subscribers.delete(listener);
        if (subscribers.size === 0 && timer !== null) {
          clearInterval(timer);
          timer = null;
        }
      };
    },
    invoke: async action => {
      if (!['pause', 'resume', 'retry', 'launch'].includes(action) || native.invoke(action) !== true) {
        throw new Error('Preparation action refused');
      }
      publish();
    }
  });
}
