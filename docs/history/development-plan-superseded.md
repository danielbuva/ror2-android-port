# Superseded development-plan sections

Moved verbatim from docs/DEVELOPMENT_PLAN.md on 2026-10-16. The T01→T07 bootstrap sequence,
the J64 Terra/Astra handoff and the L5.5 issue list were completed or superseded by the
whole-game integration direction (2026-10-04) and are kept for reference only.

## Immediate execution

T01 → T02 → T05 → T06 → T07. T03/T04/T08/T10 are conditional support, not wholesale prerequisites. T01 is non-negotiable: `./dev doctor`, `./dev preflight`, `./dev test`, `./dev smoke --target vulkan`. Stop at the first failed prerequisite. Unknown input requires inventory/diff review and explicit local acceptance. Do not repeat unchanged failed Rewired builds or reconstructed Play Mode.

T01 passed anew at work/runs/20260913T020341.114229Z-46130c90d7a1; screenshot visually verified and disposable package removed. Historical G2 remains utility execution/static geometry, not gameplay.

## Independent constructive experiments (J64)

Gate order controls formal acceptance, not every experiment. While J61 defers platform startup, bounded original simulation precursors may execute before L5 if their actual dependencies can be provided without faking or bypassing platform/ownership checks. Such a result must identify its diagnostic fixtures and cannot pass L5.5, replace its L5 prerequisite or unlock downstream gates. Do not fabricate Run, catalogs, master/body linkage or authority to claim a precursor pass. Retain original simulation/serialization semantics.

Prefer new Android execution, rendering, simulation or persistence over another static audit. Static inspection is limited to bounding the chosen executable experiment. After one read-only review, another consecutive read-only task requires concrete reasons no constructive candidate can run. Do not prove all theoretical downstream lifecycles first; reuse existing harnesses and preserve first-failure discipline.

J64 selects L11-a original skin material assignment and Vulkan rendering, defined in l11-commando-material-device-contract.md. Terra implements and runs it, then returns evidence to Astra. J61–J63 are accepted; no further expansion of those audits is requested.

## L5.5 — original character simulation

Prerequisite: L5. Use the smallest functioning recovered environment and original Commando prefab dependency closure. A diagnostic camera, simple collision surface, neutral lighting and replacement materials are allowed. Do not require a whole stage/director/full camera rig.

Issue 1: spawn an original CharacterMaster/CharacterBody without input; assert linkage, components, local authority and stable original state-machine ticking.
Issue 2: feed a recorded short sequence at the game's input boundary; assert original movement/stop, jump/landing where supported and corresponding state transitions. Never move the Transform directly to claim simulation success.
Issue 3: inspect built-in handheld controls and bind them to the same proven boundary; verify manual movement and a state-changing action. Scripted input is not controller acceptance.

Record master/body identity, authority, state, velocity/position, grounding and exceptions. Use existing build/install/run/capture; add a thin ./dev prototype --action character-simulation only when needed. Pass: three cold launches with ≥60 seconds stable simulation each, deterministic assertions, manual built-in input, structured and visual evidence, no unexplained required-component/authority failure.

Failure order: prefab/reference → creation → authority → state initialization/tick → physics/movement → input. Roll back to L5 APK and payload. Sync only this closure after live storage checks. Complete stage, enemies, combat, full camera/audio/material parity are non-goals. Establish LAST_KNOWN_GOOD_SIMULATION and replan before L6.

