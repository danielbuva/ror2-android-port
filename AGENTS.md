# Environment handoff

Read `environment/ENVIRONMENT_REPORT.md` and run `./scripts/doctor.sh` before toolchain-dependent work. This repository starts as an environment bootstrap, with an isolated test project in `smoke/`; it is not a game port yet.

- Never add proprietary game assets, assemblies, credentials, signing keys, or account data to Git.
- The exact verified editor is Unity 2021.3.33f1 (ee5a2aa03ab2), macOS ARM64. Use its bundled Android SDK, NDK and OpenJDK via `scripts/env.sh`.
- Canonical device ADB is `/opt/homebrew/bin/adb`. Require an explicit/unambiguous authorized device.
- Adopted Android storage is a primary constraint. Query live state: the physical internal volume has little free space. Do not format, repartition, erase, change storage configuration, or remove/move existing games to make space.
- Do not hardcode portable SD paths. Record real package placement after each test installation.
- `scripts/smoke-device.py` installs only the disposable bootstrap package and uninstalls it; it refuses a pre-existing package.
- Unity editor state/actions use the pinned Unity MCP; ordinary Git, GitHub, device, and inspection work use deterministic CLIs.
- Read-only doctor may report failure when Unity/MCP is closed. Follow the report's startup instructions; do not treat mere tool presence as a completed smoke test.
