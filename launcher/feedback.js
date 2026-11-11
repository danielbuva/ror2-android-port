export const MAX_PREVIEW_LENGTH = 8192;
export const MAX_NOTE_LENGTH = 2000;

export function mountFeedback(container, notes) {
  container.innerHTML = `<section class="panel feedback"><h2>Feedback draft</h2><p>Write and review a plain-text draft here.</p></section>`;
  return () => {};
}
