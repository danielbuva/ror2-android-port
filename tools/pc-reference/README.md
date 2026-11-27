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
./dev pc-reference tools/pc-reference/plans/loader-roost.json
./dev pc-reference tools/pc-reference/plans/artificer-fire-bolt.json
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
and `move`. `grapple` holds Loader's default Secondary in the local input
bank for `holdSeconds` with movement input zero, then releases it. The Roost
plan records the native Hook state and network ID, world attachment, anchor
and motor position at fixed ticks. The step requires `ffmpeg` to assemble
an MP4 from timestamped PNGs at about 10 samples per second.
A step can reuse the preceding camera or supply a new position
and yaw/pitch. `aimAt` takes a spawned actor's alias or `player`.
`settleSeconds` delays a shot or specifies an assisted move's duration.
`recordSeconds` adds timestamped PNGs after the first frame.

The Artificer plan uses the native first-stage route to Distant Roost variant
with seed 3, a fixed camera and aim direction, and an assisted Beetle spawn.
The recorder activates the stock primary once. The projectile step starts
recording before the cast, retains one PNG per rendered frame during its short
window, and encodes `projectile.mp4` at the observed timestamps. The 60 FPS
setting is a target. `projectile-trace.json` records cast pose and aim, owned
projectile identity and positions, and native damage against the planned
Beetle or another victim. Compare observed contact and crit with the Android
trace when qualifying a match.

The command prints its private run directory. The manifest records the Steam
build, managed assembly digest and scenario results. Steps carry lossless
PNGs with HUD, camera and actor state, a sample of nearby frustum renderers,
and material slots, shader properties and property block values. Wwise posts
carry event identity, emitter, returned playing ID and Unity time. Wwise's
optional mix capture reports its middleware result. The WAV and frame
timestamps require runtime validation before use in a listening comparison.
These plans use native PC render resolution.

The [plan schema](plan.schema.json) describes the recorder inputs. The
[manifest schema](manifest.schema.json) describes the output consumed by
the comparison tool. The tool pairs an explicit PC step and Android PNG,
reports scene and camera metadata when an Android gameplay state is supplied,
and can compose an image for visual inspection.

```sh
python3 tools/pc-reference/compare.py "$pc_manifest" loader-roost loader-terrain-grapple "$phone_png" \
  --android-state "$phone_gameplay_json" --side-by-side "$private_output_png"
```

CrossOver translates the Windows D3D11 renderer, which can shift color and
lighting relative to native Windows. Its captures can be used for presence,
blend and effect comparisons. For a native Windows color comparison, use a
capture with the same scene, pose, game build and graphics settings.

The seeded lobby and authoritative spawns follow the patterns in the pinned
[DebugToolkit sources](../../docs/community-prior-art.md). The storage
boundary follows the separate-storage approach documented for ProperSave.
