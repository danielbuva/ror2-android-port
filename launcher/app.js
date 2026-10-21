import {createController} from './controller.js';
const main = document.querySelector('main');
const dialog = document.querySelector('dialog');
const escape = text => String(text).replace(/[&<>"']/g, char => ({'&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;'}[char]));
const back = '<button class="back" data-view="home" data-focus="home">← Back to home</button>';
const labels = {selectFiles:'Select game files', prepare:'Prepare', pause:'Pause', resume:'Resume', retry:'Retry', launch:'Play'};
const statusLabels = {unavailable:'Backend unavailable', idle:'Setup required', preparing:'Preparing', paused:'Paused', error:'Needs attention', ready:'Ready'};
const controller = createController(() => render());
let focusKey = null;
function button(action) {
  return `<button class="${action === 'launch' || action === 'prepare' ? 'primary' : 'secondary'}" data-action="${action}" data-focus="${action}" ${controller.can(action) ? '' : 'disabled'}>${labels[action]}</button>`;
}
function render() {
  const state = controller.snapshot();
  const active = document.activeElement;
  if (main.contains(active) && active !== main) focusKey = active.dataset.focus ?? null;
  else if (active !== main) focusKey = null;
  const view = location.hash.slice(1);
  const status = escape(statusLabels[state.status]);
  const message = `<p>${escape(state.message)}</p>`;
  if (view === 'setup') {
    main.innerHTML = `${back}<section class="panel"><h2>${status}</h2>${message}${state.progress === null ? '' : `<div class="progress-head"><span>Preparation</span><strong>${state.progress}%</strong></div><progress max="100" value="${state.progress}" aria-label="Preparation progress"></progress>`}<div class="actions">${Object.keys(labels).filter(a => controller.offers(a) || (state.status === 'unavailable' && ['selectFiles','prepare'].includes(a))).map(button).join('')}</div></section>`;
  } else if (view === 'diagnostics') {
    main.innerHTML = `${back}<section class="panel"><h2>Diagnostics</h2><div class="summary"><span>State</span><strong>${status}</strong></div>${message}<p>No device logs or personal data are collected by this frontend.</p></section>`;
  } else {
    main.innerHTML = `<h1>Risk of<span>Rain <span class="number">2</span></span></h1><nav class="menu" aria-label="Launcher">${state.status === 'ready' ? button('launch') : '<button class="primary" data-view="setup" data-focus="setup">Set up <span class="arrow">→</span></button>'}<button data-view="setup" data-focus="files">Game files</button><button data-view="diagnostics" data-focus="diagnostics">Diagnostics</button><button data-about data-focus="about">About</button></nav><div class="home-status"><span class="dot"></span><strong>${status}</strong></div>`;
  }
  if (focusKey) {
    let target = main.querySelector(`[data-focus="${focusKey}"]`);
    // Follow a completed state action to its successor (Prepare → Pause → Resume).
    if (!target && Object.hasOwn(labels, focusKey)) target = main.querySelector('[data-action]:not(:disabled)');
    if (target && !target.disabled) { focusKey = target.dataset.focus; target.focus(); }
    else main.focus(); // Retain the key until a temporarily disabled action settles.
  }
  document.querySelector('#announcement').textContent = state.busy ? 'Request in progress.' : state.message;
}
function showAbout() { if (!dialog.open) dialog.showModal(); }
document.addEventListener('click', event => {
  const button = event.target.closest('button');
  if (!button || button.disabled) return;
  if (button.hasAttribute('data-about')) showAbout();
  if (button.dataset.view) location.hash = button.dataset.view;
  if (button.dataset.action) void controller.invoke(button.dataset.action);
});
window.addEventListener('hashchange', () => { render(); focusKey = null; main.focus(); });
document.querySelector('#about').onclick = showAbout;
document.querySelector('#close-about').onclick = () => dialog.close();
// Explicit local host integration; there is no postMessage, network or automatic bridge.
window.launcher = Object.freeze({connect: controller.connect, disconnect: controller.disconnect});
window.addEventListener('pagehide', () => controller.disconnect());
render();
