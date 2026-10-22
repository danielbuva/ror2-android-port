# Owner-build playtest checklist

Current scope: the prepared laboratory's desktop fallback. Phone-only owner
builds and the final player installation flow remain under investigation. Keep
owner-generated APKs and payloads private. The [player guide](PLAYER_GUIDE.md)
explains public availability; [current status](../PORTING_STATE.md) records limits.

Set `PLAYTEST_DEVICE` to your explicitly allowlisted test-device serial before
running device commands. Check that it is set in the same shell:

```sh
: "${PLAYTEST_DEVICE:?Set the authorized test-device serial}"
```

## Prepare a matching build

1. Set up the pinned toolchain and legitimate external game input using the
   [developer guide](DEVELOPING.md#local-setup). Keep the original installation
   untouched. Review input inventory and acceptance before building; stop on
   unknown-version, provenance or dependency refusals. Fresh public-input
   bootstrap remains an open gate in the [alpha checklist](public-alpha.md).
2. Use your isolated checkout and local work directory. Commit source before a
   whole-catalog build. Run `./dev doctor --device "$PLAYTEST_DEVICE"` and
   `./dev preflight --host-only`;
   resolve their first failure before requesting the build. Use the current
   `whole-catalog-build` action documented in the developer guide. Builds use
   the shared Unity mutex; wait for the owning process rather than deleting it.
3. Keep the resulting APK, matching payload directory and build receipt together.
   Record the APK SHA-256, source commit, input identity, toolchain and request
   from that receipt. Retain the previous known-good set. This is an owned lab
   build; release package identity/signing/update policy remains unqualified.

## Install on the explicitly selected test device

Set `PLAYTEST_APK` to your APK and
`PLAYTEST_PAYLOAD` to the payload from that same build. Run from the checkout
whose ignored `work/` holds your configuration and ownership receipts.

```sh
: "${PLAYTEST_DEVICE:?Set the authorized test-device serial}"
: "${PLAYTEST_APK:?Set your matching APK path}"
: "${PLAYTEST_PAYLOAD:?Set your matching payload directory}"
./dev storage --device "$PLAYTEST_DEVICE"
./dev preflight --device "$PLAYTEST_DEVICE"
./dev install --device "$PLAYTEST_DEVICE" --apk "$PLAYTEST_APK"
./dev sync-data --device "$PLAYTEST_DEVICE" --payload-dir "$PLAYTEST_PAYLOAD"
```

Read the new receipts: installed APK identity, package placement and runtime
backing are separate facts. Stop if ownership, capacity, signature or payload
checks refuse. Preserve existing games/data and storage configuration. Keep
commands and raw outputs private; they can contain identifiers.

`sync-data` requires the prepared lab's owned runtime-path receipt. If it is
missing or stale, stop and resolve the bootstrap/backing check with the lab
maintainer; do not copy another device's receipt or guess a storage path.

## Check and play

For your own current local build, run the two standard controls separately:

```sh
: "${PLAYTEST_DEVICE:?Set the authorized test-device serial}"
./dev check-baseline --device "$PLAYTEST_DEVICE"
./dev check-baseline --device "$PLAYTEST_DEVICE" --stage-exit
```

These are assisted diagnostic checks. Their success does not qualify ordinary
controls, an unassisted run or long-session stability. Inspect `is_current_build`
alongside the installed APK hash: a missing or different local build pointer
records `false`, even when the owned-APK check succeeds. Investigate a mismatch;
do not rewrite a pointer to claim a different build was checked. See
[baseline acceptance and teardown](BASELINE.md).

For an agreed manual playtest, record start/end time and assistance settings.
Check menu selection, movement/aim, skills, equipment and interaction; pause,
resume, end-run confirmation, menu return and a second session. Record visible
material errors, audio behavior, crashes and background/resume separately. A
successful check or a nonzero audio meter does not establish visual/audio parity.
Follow the approved run's owned cleanup and verify its idle/selector state.

## Keep evidence and send feedback deliberately

Keep the APK hash/receipt and failed-run directory. For a report, write short
reproduction steps, expected/actual behavior, build identity and assistance used.
Review every field before submitting through the
[repository's Issues page](https://github.com/danielbuva/ror2-android-port/issues/new).
Remove account/session details, private paths, device/storage identifiers and
signing data. Do not submit game files, generated packages or raw logs. Preview
and explicitly consent to any attachment. No automated upload or embedded token
is needed; settings integration and a redacted exporter remain open work.

Rollback requires a reviewed same-owner package/payload/profile-compatible set.
Keep that set rather than uninstalling or forcing a downgrade to bypass a
refusal; profile/settings retention across public updates remains unqualified.
