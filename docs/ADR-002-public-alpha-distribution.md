# ADR-002 — Preserve IL2CPP and investigate phone-only owner builds

Status: **accepted direction**, 2026-10-20. Phone-only feasibility is unproven.
This amends [ADR-001](ADR-001-port-architecture.md); its architecture C remains
the runtime implementation. The user's **Route A** means preserving that
native IL2CPP runtime, not ADR-001's source-reconstruction option A.

## Decision

Keep Unity **2021.3.45f2 (88f88f591b2e)**, IL2CPP ARM64 and the existing Android
rendering pipeline authoritative. Do not migrate gameplay to HybridCLR, Mono,
box64, another interpreter or another execution backend to simplify delivery.

Investigate an owner build performed entirely on the phone. Separate acquisition,
content reconstruction, native compilation and packaging from runtime engineering.
Present findings before implementing a replacement pipeline or altering the
working Android build. Keep the existing desktop owner-build workflow as a
fallback; it is not the chosen final installation experience.

The [phone owner-build assessment](phone-owner-build.md) maps editor requirements,
Android-capable tools and genuine blockers. [public-alpha.md](public-alpha.md)
holds open release work. Earlier [runtime-option research](history/public-alpha-distribution-options-2026-10-20.md)
is historical background only.

## Distribution and ownership

Publish audited original tooling, recipes and independently authored bootstrap
material. Owners supply legitimate input and generate all game-derived APK
code, metadata, shaders and content locally. Moving original AOT code into a
library, patch, archive or later download does not remove that constraint.
No project-hosted game build service is approved.

Open-source licenses must cover complete distributed tool dependencies. Unity
editor/compiler components, middleware and original game content remain separate
rights/input boundaries. Acquisition must retain ownership/Guard checks and
secret-safe handling; it does not establish original in-game Steam startup or
DLC entitlement. Local files must not be labelled an authenticated session.
Android and PC/cloud profiles retain their separate compatibility gates.

The alpha device is exclusively assigned to alpha by J818. Its serial stays in
ignored configuration and is explicit on every device action. The main session retains
the primary gameplay device, original gameplay/audio/animations and their runtime owners.
Shared Unity builds retain the mandatory mutex and editor coordination.

## Acceptance

IL2CPP alone does not establish equivalent performance. Pin and compare Unity
and package versions, assembly transforms, compiler options, stripping, shaders
and actual build outputs. Any alternative pipeline must pass device contracts
and matched-workload performance/memory benchmarks before adoption. Host success
or a loaded bundle container cannot advance those gates.

Runtime replacement and external publication remain unapproved. Complete the
findings review before changing the working build or committing to the final
distribution experience.
