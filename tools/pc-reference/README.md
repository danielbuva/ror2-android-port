# Steam PC reference recorder

The Mac needs CrossOver, the lab's pinned Unity distribution for its C#
compiler, and the configured Steam installation. The game runs through
CrossOver. The recorder does not launch Unity Editor. Steam must already be
open and signed in to an account that owns the game. Close any running copy of
the game before starting a capture.

```sh
./dev pc-reference --prepare-only
./dev pc-reference --validate-plan tools/pc-reference/plans/gameplay.json
./dev pc-reference tools/pc-reference/plans/gameplay.json --scenario roost
./dev pc-reference tools/pc-reference/plans/gameplay.json
```

Preparation uses an APFS clone inside the same bottle. Stock Steam performs
initialization and ownership checks. After they succeed, the plug-in switches
profile storage to memory and suppresses achievement writes. Its loader and
managed assembly references stay on this Mac. The runner checks host memory
pressure before launching each scenario.

## Plans and evidence

A scenario names the expected scene, unsigned 64-bit decimal seed and body
prefab. Set `naturalFirstStage` to use the game's first-stage chooser. Other
scenarios use the game's first-scene override and report assisted direct entry.
Player placement, camera overrides, frozen enemy AI and forced skill states
are capture assistance. The initial plan's Siren and Gold views show the
scenery before mission progression. Siren's sixth-egg sequence and Gold's
native portal and beacon sequence need their own gameplay captures.

Step actions include `capture`, `spawn` (master prefab), `state` (entity
state and machine), `skill` (native skill slot), `ping`, `fire-trail`
and `move`. A step can reuse the preceding camera or supply a new position
and yaw/pitch. `aimAt` takes a spawned actor's alias or `player`.
`settleSeconds` delays a shot or specifies an assisted move's duration.
`recordSeconds` adds timestamped PNGs after the first frame.

The command prints its private run directory. The manifest records the Steam
build, managed assembly digest and scenario results. Steps carry lossless
PNGs with HUD, camera and actor state, a sample of nearby frustum renderers,
and material slots, shader properties and property block values. Wwise posts
carry event identity, emitter, returned playing ID and Unity time. Wwise's
optional mix capture reports its middleware result. The WAV and frame
timestamps require runtime validation before use in a listening comparison.
These plans use native PC render resolution.

CrossOver translates the Windows D3D11 renderer, which can shift color and
lighting relative to native Windows. Its captures can be used for presence,
blend and effect comparisons. For a native Windows color comparison, use a
capture with the same scene, pose, game build and graphics settings.

The seeded lobby and authoritative spawns follow the patterns in the pinned
[DebugToolkit sources](../../docs/community-prior-art.md). The storage
boundary follows the separate-storage approach documented for ProperSave.
