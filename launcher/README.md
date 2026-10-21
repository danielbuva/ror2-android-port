# Launcher frontend handoff

The approved launcher art and responsive UI, packaged as dependency-free HTML,
CSS and JavaScript. This is **not an Android launcher APK or a working preparation
backend**. It does not change the Unity player, architecture C, owner-built
Route A, or phone-only investigation. The public-alpha owner chooses the native
shell and implements the backend; this package does not select WebView as runtime
architecture.

## Run and test

From the repository root, `python3 -m http.server 8080 --bind 127.0.0.1`;
open `http://127.0.0.1:8080/launcher/`. Serve locally, not on a public interface.
Run `node --test launcher/tests/*.test.js` (Node 18 or newer).
Open `http://127.0.0.1:8080/launcher/tests/view.html` for browser regression checks
against the real frontend: pending Prepare/Pause, action and navigation focus,
and modal focus during background updates. All four results must read PASS.
No dependencies, build step, external fonts, analytics or remote requests.

- `index.html`: safe disconnected default, setup and diagnostics routes.
- `app.js`: view rendering, hash navigation, modal and accessibility wiring.
- `controller.js`: versioned state/action boundary; owns connection, subscription,
  per-action pending requests and stale-response rejection. `disconnect()` or page exit
  tears down the subscription; no preparation is canceled implicitly.
- `style.css`, `background.png`: approved shared visual treatment.
- `demo/`: explicitly separate, simulated click-through. No route or flag enables
  it in the real frontend. Its state and progress reset on reload.
- `PROVENANCE.md`: developer-facing source and asset-review record.

## Host adapter v1

After `app.js` loads, a trusted local host calls `window.launcher.connect(adapter)`.
The frontend never discovers a bridge automatically or listens to cross-window
messages. Connection returns a Promise. To disconnect, call
`window.launcher.disconnect()`; state becomes unavailable immediately.

The adapter has `version: 1` and these methods:

- `getState(): Promise<Snapshot>` returns the host's current state on connection.
- `subscribe(listener): () => void` immediately publishes the latest snapshot,
  then every change; returns a synchronous unsubscribe function. This immediate
  snapshot closes the get/subscribe race. Unsubscribe must not throw.
- `invoke(action): Promise<void>` requests a supported operation. Completion is
  not evidence of success; publish the observed state separately.

A snapshot is `{status, progress, message, capabilities}`. Status is one of
`unavailable`, `idle`, `preparing`, `paused`, `error`, `ready`. Progress is `null`
when not measurable, otherwise an observed number from 0 through 100. Message is
sanitized user-facing plain text, at most 500 characters, never raw exceptions,
identifiers, paths, credentials or logs. Capabilities is a map of booleans:
`selectFiles`, `prepare`, `pause`, `resume`, `retry`, `launch`.

The host owns native selection and permission prompts, fresh storage/capacity
checks, lawful user input validation, version/hash gates, preparation, recovery,
installation and launch. No path or ownership checkbox is accepted from this UI.
Publish `ready` and enable `launch` only after the required checks actually pass;
a percentage of 100 alone never makes the frontend ready. Each operation must
revalidate its own authorization and prerequisites: UI gating is not security.

Commands are also state-gated: idle → select/prepare; preparing → pause;
paused → resume; error → select/retry; ready → select/launch. Unavailable offers
none. Never advertise pause/retry before the backend can safely perform them.
Duplicate pending requests for the same action are suppressed. An `invoke` Promise
may remain pending while its operation runs; newly published state and capabilities
can authorize a different action, such as Pause during Prepare. The host must
serialize or reject incompatible operations. Pending actions remain visible but
disabled, and state updates preserve keyboard focus or move it to the next state
action. Adapter errors fail closed without
exposing their text; reconnect and re-query the host to recover. A host operation
may continue after disconnection, so its lifecycle/persistence must live outside
this UI. Reloading does not synthesize progress or remember readiness.

For an Android shell, restrict navigation/origins to bundled trusted content,
expose only narrow validated operations, and do not grant arbitrary JavaScript
filesystem/shell access. Native dialog cancellation should publish unchanged state.

## Next integration gates

1. Public-alpha owner chooses shell and maps existing owner-build contracts to
   adapter v1. Retain desktop preparation until a phone path is actually verified.
2. Connect real file permission, fresh capacity and input-version checks before
   enabling Prepare. Persist resumable job receipts in the backend, not the UI.
3. Verify cancellation, loss of storage/permission, process death, repeated taps,
   reload/reconnect and launch failures on the authorized device before accepting
   production behavior. Host tests do not establish Android/device readiness.
