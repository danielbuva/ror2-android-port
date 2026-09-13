# Evidence-based milestone skeleton

This is a dependency skeleton for Agent #3, not a final execution plan. Read ADR-001 and current state first. Mark a milestone passed only with stored evidence.

| Milestone | Proof required | Likely blocker | Depends on |
| --- | --- | --- | --- |
| L0 reproducible input inventory | Full hashes, build/version, assembly/native/content manifests | Input update or missing install | Legitimate local install |
| L1 architecture boundary proof | Original assembly API executes through IL2CPP; converted mesh renders from independent payload | AOT/type identity, bundle target | L0, exact editor |
| L2 G0–G2 device harness | APK/ABI/placement verified, checkpoint, screenshot, logs; GLES/Vulkan compared | Install scratch space, diagnostics | L1 |
| L3 original managed closure | Link/AOT report with first failure; no blind service startup | Burst/Collections mismatch, native imports, reflection/generics | L0–L2 |
| L4 first original scene | Scene hierarchy, serialization reference audit and device capture | Missing GUIDs, engine/package version mismatch, shader stubs | L3, converted assets |
| L5 lawful offline platform boundary + menu | No false auth/ownership claims; initialization timeline and menu navigation | Steam/EOS/entitlements/save coupling, Wwise/Rewired startup | L3–L4 |
| L6 stage load + player/controller | Stage content loaded, player spawned, movement/camera/UI actions recorded | Addressables paths, local authority, controller maps | L5 |
| L7 director/enemies/combat | Reproducible local simulation and readable combat (G4) | HLAPI semantics, spawn catalogs, effects | L6 |
| L8 transition + complete offline run | Stage transitions, result screen, deterministic logs across a full run | Lifetime/unload/save dependencies | L7 |
| L9 save/profile persistence | Save and reload across update; explicit uninstall behavior | Storage adapter and platform saves | L5; acceptance alongside L8 |
| L10 audio | Licensed compatible ARM64 engine, bank/codec proof, representative events | Wwise licensing and authoring/bank compatibility | L5; can proceed parallel to gameplay once authorized resources exist |
| L11 broad graphics | G5 material/effect families, compute/terrain/decal tests | Dummy/D3D shader reconstruction | L4–L8 |
| L12 sustained performance | Scenario traces, memory/thermals, frame percentiles, load/transfer times | Whole-game workload not yet available | L8, G4+, real device |
| L13 reproducible user transformation | Fresh legitimate install → verified local build/data with no proprietary repository payload | Update matching, rights for middleware redistribution | L0–L12 |
| Later multiplayer/platform integration | Explicit service permissions and end-to-end network tests | Identity/SDK/transport compatibility | Stable offline run |

Passed laboratory evidence is limited to L0–L2. L1 proves only a utility assembly and static mesh. Reconstructed loadingbasic opens in the editor, but Play Mode crashed in Burst/Collections initialization; this does not pass L4.
