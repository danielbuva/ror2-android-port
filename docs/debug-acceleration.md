# Temporary debug acceleration

All controls default **off**. They exist only in the composed offline laboratory.
Open **Developer controls** on the right of the game screen, or use these keyboard
binds. Physical gameplay buttons retain their existing bindings.

| Bind | Effect | Acceptance invalidated when used |
| --- | --- | --- |
| F1 | Invincibility through the owned original health component | Normal combat and death |
| F2 | Original base and level damage ×1000 | Normal combat |
| F3 | Positive original holdout charge rate ×8 | Holdout timing/validation |
| F4 | Original base and level movement speed ×2 | Normal movement/navigation |
| F5 | Original base and level jump power ×6 | Normal movement/navigation |

Each control toggles independently. **Disable all** restores the saved values and
removes charge callbacks. Original attacks still deal damage; enemies are never
deleted by the controls. Fast charge leaves zero occupancy and negative discharge
unchanged, and the original controller owns completion. No mission, boss, stage,
entitlement, authentication or victory state is forced.

High jump keeps the original jump-count limit, input consumer, gravity, collision
and landing behavior. It grants no items or unlocks and writes no position or
velocity directly. The report records saved/applied jump fields, actual computed
jump power and maximum jump count. Disabling it restores the saved fields; it
does not cancel velocity from a jump already in progress.

For unattended integration, put explicit options in an ignored local JSON file:

```json
{
  "invincibility": true,
  "highDamage": true,
  "fastCharge": true,
  "movementBoost": false,
  "jumpBoost": false,
  "purpose": "Moon mission integration; exclude combat, death and holdout acceptance"
}
```

```sh
./dev prototype --action movement-batch-run --debug-options work/config/moon-debug-options.json
```

Use `movement-batch-retry` for another launch of the same verified APK. Omitting
`--debug-options` requests an unassisted launch. Options cannot be selected for
unrelated prototypes, and an APK that fails to report requested effects fails
evidence checks.

The HUD, result screen, run receipt and Android results ledger identify assisted
runs. The original result XML has a separate owned debug sidecar. Toggle events
record timing and source; the report records actual stats and charge rates.
**Ever assisted** stays true after disabling everything. Every assisted run is
ineligible for full normal-game acceptance and cannot advance its rollback gate.
Use assistance only where its effects do not invalidate the subsystem under test.
For Moon mission integration, high jump may bypass difficult traversal; this
does not validate normal traversal or an elevator/launch volume bypassed by it.
Moon integration leaves movement boost off. Final combat, death, holdout and the
complete genuine route still require unassisted verification.

Prior art: pinned [DebugToolkit player commands](https://github.com/harbingerofme/DebugToolkit/blob/d1e2f0aa4b8ac4747547db0fcd87344953432f06/Code/DT-Commands/PlayerCommands.cs)
identify the master/body god-mode relationship; pinned
[holdout commands](https://github.com/harbingerofme/DebugToolkit/blob/d1e2f0aa4b8ac4747547db0fcd87344953432f06/Code/DT-Commands/CurrentRun.cs)
show why direct charge/state mutation would obscure source behavior. The current
legitimate input supplies the actual Android API contract. No implementation was
copied and no original assembly is changed by this layer.

The same pinned player source's `dump_stats` distinguishes base jump power from
jump count. Current legitimate `CharacterBody.RecalculateStats` derives power
from base/level fields; `GenericCharacterMain.ProcessJump` consumes it and owns
jump limits, velocity and callbacks. This supports a small field-based high-jump
toggle without reconstructing items or replacing movement code.
