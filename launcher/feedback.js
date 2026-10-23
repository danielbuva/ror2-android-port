// Consumer of scripts/lab/baseline_feedback.py schema 1; never reads raw receipts.
export const MAX_PREVIEW_LENGTH = 8192;
export const MAX_NOTE_LENGTH = 2000;

function boolean(value) {
  if (typeof value !== 'boolean') throw new Error('Invalid check fact');
  return value;
}
function quantity(value, integer = false) {
  if (value === null) return null;
  if (typeof value !== 'number' || !Number.isFinite(value) || value < 0 || value > 604800 || (integer && !Number.isInteger(value))) throw new Error('Invalid check fact');
  return value;
}
export function parsePreview(raw) {
  if (typeof raw !== 'string' || raw.length > MAX_PREVIEW_LENGTH) throw new Error('Invalid check preview');
  const source = JSON.parse(raw);
  if (!source || source.schema !== 1 || !['baseline', 'stage-exit'].includes(source.check)
    || typeof source.apk_sha256 !== 'string' || !/^[0-9a-f]{64}$/.test(source.apk_sha256)
    || source.assisted !== true || source.ordinary_controls_qualified !== false
    || source.full_run_qualified !== false || source.visual_audio_parity_qualified !== false) throw new Error('Invalid check preview');
  const success = boolean(source.reported_success);
  const failures = source.failed_criteria_count;
  if (!Number.isInteger(failures) || failures < 0 || failures > 10000 || success !== (failures === 0)) throw new Error('Invalid check result');
  const cleanup = source.cleanup;
  if (!cleanup || cleanup.selector_absent !== true || cleanup.process_absent !== true) throw new Error('Incomplete teardown');
  const sleeping = boolean(cleanup.sleep_requested);
  const asleep = cleanup.display_asleep === null ? null : boolean(cleanup.display_asleep);
  if (sleeping && asleep !== true) throw new Error('Incomplete teardown');
  // Select fields explicitly, including nested ones. Ignore URLs, messages and unknown keys.
  const facts = {
    schema: 1, check: source.check, apk_sha256: source.apk_sha256,
    reported_success: success, matches_local_current_build: boolean(source.matches_local_current_build),
    failed_criteria_count: failures, assisted: true,
    world_seconds: quantity(source.world_seconds), applied_profile_runs: quantity(source.applied_profile_runs, true),
    cleanup: {selector_absent: true, process_absent: true, sleep_requested: sleeping, display_asleep: asleep},
    ordinary_controls_qualified: false, full_run_qualified: false, visual_audio_parity_qualified: false,
  };
  if (source.check === 'stage-exit') {
    facts.transitions = quantity(source.transitions, true);
    facts.stage_world_seconds = quantity(source.stage_world_seconds);
  }
  return facts;
}
export function buildDraft(notes, raw = '') {
  const fields = ['steps', 'expected', 'actual'].map(key => {
    const value = notes[key];
    if (typeof value !== 'string' || value.length > MAX_NOTE_LENGTH) throw new Error('Invalid notes');
    return value.trim();
  });
  if (!fields[2]) throw new Error('Describe the actual behavior');
  const facts = raw.trim() ? parsePreview(raw) : null;
  return [
    'Risk of Rain 2 Android laboratory feedback',
    'User-entered notes (not automatically redacted or verified).',
    'Reproduction steps:\n' + (fields[0] || '(not provided)'),
    'Expected behavior:\n' + (fields[1] || '(not provided)'),
    'Actual behavior:\n' + fields[2],
    facts ? 'Selected assisted-check claims (not independently verified):\n' + JSON.stringify(facts, null, 2)
      : 'No check metadata included; installed build and device behavior are unknown.',
    'Ordinary controls, a full run and visual/audio parity remain unqualified by this draft.',
    'No logs or attachments collected. Review and consent to each attachment separately before sharing.',
  ].join('\n\n') + '\n';
}

export function mountFeedback(container, notes) {
  container.innerHTML = `<section class="panel feedback"><h2>Feedback draft</h2>
    <p>Write and review a plain-text draft here, then copy it to share yourself. Nothing is sent or saved to disk.</p>
    <p class="notice">Your notes are not automatically redacted. Leave out account details, device identifiers, private paths, logs and game files.</p>
    <form data-feedback-form>
      <div class="field"><label for="feedback-steps">Reproduction steps</label><textarea id="feedback-steps" data-note="steps" maxlength="2000" rows="3"></textarea></div>
      <div class="field"><label for="feedback-expected">Expected behavior</label><textarea id="feedback-expected" data-note="expected" maxlength="2000" rows="2"></textarea></div>
      <div class="field"><label for="feedback-actual">Actual behavior (required)</label><textarea id="feedback-actual" data-note="actual" maxlength="2000" rows="3" required></textarea></div>
      <details class="field"><summary>Add sanitized check facts (optional)</summary>
        <p class="hint" id="feedback-facts-help">Paste a sanitized preview from the local baseline feedback tool. Raw run reports are refused. Only selected check facts enter the draft; check claims are not authenticated.</p>
        <label for="feedback-metadata">Sanitized preview JSON</label><textarea id="feedback-metadata" data-note="metadata" maxlength="8192" rows="4" spellcheck="false" aria-describedby="feedback-facts-help"></textarea>
      </details><button class="primary" type="submit">Preview draft</button>
    </form>
    <p data-feedback-error role="alert"></p>
    <section data-feedback-preview hidden><h3>Review before copying</h3>
      <label for="feedback-preview">Exact text to copy</label><textarea id="feedback-preview" readonly rows="12" spellcheck="false"></textarea>
      <label class="check"><input type="checkbox" data-feedback-consent>I reviewed this draft for private or game-derived information.</label>
      <button class="secondary" type="button" data-feedback-copy disabled>Copy reviewed draft</button>
    </section><p data-feedback-status role="status" aria-live="polite"></p>
    <p class="hint">Draft notes stay in this page until reload or close. Attachments require a separate review wherever you choose to share.</p>
  </section>`;
  const form = container.querySelector('[data-feedback-form]');
  const preview = container.querySelector('[data-feedback-preview]');
  const output = container.querySelector('#feedback-preview');
  const consent = container.querySelector('[data-feedback-consent]');
  const copy = container.querySelector('[data-feedback-copy]');
  const error = container.querySelector('[data-feedback-error]');
  const status = container.querySelector('[data-feedback-status]');
  let revision = 0, disposed = false;
  for (const field of form.querySelectorAll('[data-note]')) field.value = notes[field.dataset.note] || '';
  function edited(event) {
    if (!event.target.dataset.note) return;
    notes[event.target.dataset.note] = event.target.value;
    revision++; consent.checked = false; copy.disabled = true;
    preview.hidden = true; output.value = ''; error.textContent = ''; status.textContent = '';
  }
  function submit(event) {
    event.preventDefault(); revision++; consent.checked = false; copy.disabled = true; status.textContent = '';
    try {
      output.value = buildDraft(notes, notes.metadata || '');
      error.textContent = ''; preview.hidden = false; output.focus();
    } catch {
      preview.hidden = true; output.value = '';
      error.textContent = 'Draft unavailable. Describe the actual behavior and check the optional sanitized preview. Notes are limited to 2,000 characters each.';
    }
  }
  function reviewed() { copy.disabled = !consent.checked || preview.hidden; }
  async function copied() {
    if (!consent.checked || preview.hidden || copy.disabled) return;
    const pendingRevision = revision; copy.disabled = true;
    try {
      await navigator.clipboard.writeText(output.value);
      if (!disposed && revision === pendingRevision) status.textContent = 'Draft copied. Nothing has been submitted.';
    } catch {
      if (!disposed && revision === pendingRevision) {
        output.focus(); output.select();
        status.textContent = 'Clipboard unavailable. Copy the selected preview text manually.';
      }
    } finally {
      if (!disposed && revision === pendingRevision) reviewed();
    }
  }
  form.addEventListener('input', edited); form.addEventListener('submit', submit);
  consent.addEventListener('change', reviewed); copy.addEventListener('click', copied);
  return () => {
    disposed = true;
    form.removeEventListener('input', edited); form.removeEventListener('submit', submit);
    consent.removeEventListener('change', reviewed); copy.removeEventListener('click', copied);
  };
}
