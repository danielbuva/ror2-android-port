# Build recipes

Tracked, audited inputs that describe how the lab turns a legitimate game installation into
the Android build: authored transformations, configuration and reproducible build steps. The
goal is a build that needs only this repository, the documented toolchain and the user's own
installation, never the private history under `work/`.

What belongs here, and what does not:

- **Tracked:** independently authored transformations, selections and configuration;
  identifiers and hashes needed to apply them; measured mappings between public
  identities (for example Unity package GUIDs).
- **Never tracked:** generated game-derived content (assets, decompiled source, bundles,
  catalogs), private configuration (`work/config/local.json`, device or storage
  identifiers, home paths) and protected third-party material.
- Readers of game-input-derived recipes stay input-gated: they check the recipe's
  `input_id` (and source hashes where recorded) against the accepted input before using it.
  Repository-authored source selections are independent of the game input.

Before adding a file, audit it for provenance, privacy, licensing and sensitive contents,
record the result below, and run `python3 scripts/audit-public.py`. Where a generator can
produce the file from the input, prefer tracking the generator.

## Audit record

| File | Replaces | Provenance | Privacy and licensing | Readers |
| --- | --- | --- | --- | --- |
| `hud-ui-remaps.json` | `work/config/hud-ui-remaps.json` (LOCAL_STATE blocker B2) | 43 rows mapping Unity's own uGUI script identities: the precompiled `UnityEngine.UI.dll` reference in exported scenes (`from`) to the public `com.unity.ugui` package script GUID (`to`), with the type name and package path. Measured for input `6af7ed94…`; re-verified for the 2021.3.45f2 toolchain. | No game content, names or assets; identifiers and hashes only. One repo-relative evidence path. Audited 2026-10-17. | `composition_migration.py`, `whole_catalog.py`, `source_scene_candidate.py`, `integrated_objective.py`; each checks `input_id`, two also the `UnityEngine.UI.dll` hash |
| `runtime-sources.json` | Explicit and existing-file membership in `build.py` and the `whole_catalog.build_integration` copy loop | Authored file list: 91 sorted `tools/unity` C# filenames. Initial selection reproduces the old rules using generated-project filenames and existence only. | No game content, generated source, private paths or identifiers; repository-authored source names only. Audited 2026-10-17. | `build.py` derives player-only source and `.meta` inputs; `whole_catalog.py` stages the same selection. No game input dependency. |

`runtime-sources.json` lists filenames relative to `tools/unity`, staged at
`Assets/LabLoadingScene`. Staging copies the C# sources only and retains existing
Unity-owned `.meta` files; both paths remain player-only inputs for payload reuse.
Generated visual maps and non-source player inputs remain declared in `build.py`.
Missing authored sources and unlisted staged C# files fail validation. Historical
source lists in `nova_bridge.py` and `scene_runtime.py` remain independent and unchanged.
