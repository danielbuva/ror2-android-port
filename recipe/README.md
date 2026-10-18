# Build recipes

Tracked, audited inputs that describe how the lab turns a legitimate game installation into
the Android build: authored transformations, configuration and reproducible build steps. The
goal is a build that needs only this repository, the documented toolchain and the user's own
installation, never the private history under `work/`.

What belongs here, and what does not:

- **Tracked:** independently authored transformations, selections and configuration;
  identifiers and hashes needed to apply them; measured mappings between public
  identities (for example Unity package GUIDs).
- **Tracked when needed (user decision, 2026-10-17):** the minimum game-derived identifiers and
  relationships needed to locate, transform and reconstruct content from the user's own
  installation, such as ordinary asset paths, GUIDs, catalog names and keys. A recipe must
  enable local reconstruction, never substitute for owning the game: it must not reproduce
  protected content or circumvent access controls.
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
| `runtime-sources.json` | Explicit and existing-file membership in `build.py` and the `whole_catalog.build_integration` copy loop | Authored file list: 92 sorted C# paths relative to `tools/unity`; coordinator entry renamed to `PortSession.cs` (source name only). Initial selection reproduces the old rules using generated-project filenames and existence only. | No game content, generated source, private paths or identifiers; repository-authored source names only. Audited 2026-10-17. | `build.py` derives player-only source and `.meta` inputs; `whole_catalog.py` stages the same selection. No game input dependency. |
| `project-layout.json` | Inherited authored script identities and package dependency selection | 92 GUID lines for authored sources in `runtime-sources.json`; 36 public direct dependency pins. | Identifiers and public package coordinates only; no importer bodies, game-derived content or private URLs. Per-package audit below, 2026-10-17. | `build.py` validates staged identities and manifest dependencies without writing them. No game input dependency. |

`runtime-sources.json` lists paths relative to `tools/unity`, staged at
`Assets/LabLoadingScene` by basename. Basename collisions (including generated sources)
are rejected. Staging copies the C# sources only and retains existing
Unity-owned `.meta` files; both paths remain player-only inputs for payload reuse.
Generated visual maps and non-source player inputs remain declared in `build.py`.
Missing authored sources and unlisted staged C# files fail validation. Historical
source lists in `nova_bridge.py` and `scene_runtime.py` remain independent; their
coordinator source entry is now `PortSession`, with resource/file names unchanged.

## Project layout audit (2026-10-17)

`project-layout.json` records 92 authored source GUIDs keyed by the same relative
paths as `runtime-sources.json`, and the 36 direct package dependency pins below.
Only filenames, the `guid:` lines of those sources' staged metadata, and manifest
dependency names/versions/public URLs were inspected in the generated project.
The GUIDs identify repository-authored scripts referenced by bundles; they contain
no game assets or importer bodies and must remain stable. These identifiers and
public dependency coordinates are independent of the accepted game input.
`build.py` validates them after staged-source validation for whole-catalog builds.
Validation never writes metadata or packages; generation belongs to a later step.

Each dependency is retained to preserve the current project contract; this is not
an assertion that every enabled module is individually used. Unity registry
packages come from Unity, while `com.unity.modules.*` are built-in modules supplied
by the pinned editor, not third-party registry downloads ([Unity manual][modules]).
Only names, versions and a public pinned Git URL are published, not package source,
licensed binaries, license texts or local package caches. No dependency was private
or game-derived, so all 36 are retained. ProjectSettings, lockfiles, generated
visual-map GUIDs and all other metadata fields are outside this extraction.

License evidence is Unity's published documentation for the pinned package release
lines and CoplayDev's license at the exact tag; no package-cache content was read.
Built-in modules remain under the operator's applicable Unity Software license
([software terms][software]), not an open-source redistribution grant.

| Dependency | Pin | Provenance / license evidence | Publication decision |
| --- | --- | --- | --- |
| `com.coplaydev.unity-mcp` | `v10.2.0`, `MCPForUnity` (public Git URL in recipe) | CoplayDev public Git repository; [MIT at v10.2.0][mcp-license] | Public coordinate only; retain. |
| `com.unity.burst` | `1.8.11` | Unity registry; [Unity Companion License (source); Unity Package Distribution License (otherwise)][burst-license] | Public coordinate only; retain. |
| `com.unity.collections` | `1.2.4` | Unity registry; [Unity Companion License for Unity-dependent projects][collections-license] | Public coordinate only; retain. |
| `com.unity.mathematics` | `1.2.1` | Unity registry; [Unity Companion License for Unity-dependent projects][mathematics-license] | Public coordinate only; retain. |
| `com.unity.modules.ai` | `1.0.0` | Unity editor built-in module; [Unity Software terms][software] | Public coordinate only; retain. |
| `com.unity.modules.androidjni` | `1.0.0` | Unity editor built-in module; [Unity Software terms][software] | Public coordinate only; retain. |
| `com.unity.modules.animation` | `1.0.0` | Unity editor built-in module; [Unity Software terms][software] | Public coordinate only; retain. |
| `com.unity.modules.assetbundle` | `1.0.0` | Unity editor built-in module; [Unity Software terms][software] | Public coordinate only; retain. |
| `com.unity.modules.audio` | `1.0.0` | Unity editor built-in module; [Unity Software terms][software] | Public coordinate only; retain. |
| `com.unity.modules.cloth` | `1.0.0` | Unity editor built-in module; [Unity Software terms][software] | Public coordinate only; retain. |
| `com.unity.modules.director` | `1.0.0` | Unity editor built-in module; [Unity Software terms][software] | Public coordinate only; retain. |
| `com.unity.modules.imageconversion` | `1.0.0` | Unity editor built-in module; [Unity Software terms][software] | Public coordinate only; retain. |
| `com.unity.modules.imgui` | `1.0.0` | Unity editor built-in module; [Unity Software terms][software] | Public coordinate only; retain. |
| `com.unity.modules.jsonserialize` | `1.0.0` | Unity editor built-in module; [Unity Software terms][software] | Public coordinate only; retain. |
| `com.unity.modules.particlesystem` | `1.0.0` | Unity editor built-in module; [Unity Software terms][software] | Public coordinate only; retain. |
| `com.unity.modules.physics` | `1.0.0` | Unity editor built-in module; [Unity Software terms][software] | Public coordinate only; retain. |
| `com.unity.modules.physics2d` | `1.0.0` | Unity editor built-in module; [Unity Software terms][software] | Public coordinate only; retain. |
| `com.unity.modules.screencapture` | `1.0.0` | Unity editor built-in module; [Unity Software terms][software] | Public coordinate only; retain. |
| `com.unity.modules.terrain` | `1.0.0` | Unity editor built-in module; [Unity Software terms][software] | Public coordinate only; retain. |
| `com.unity.modules.terrainphysics` | `1.0.0` | Unity editor built-in module; [Unity Software terms][software] | Public coordinate only; retain. |
| `com.unity.modules.tilemap` | `1.0.0` | Unity editor built-in module; [Unity Software terms][software] | Public coordinate only; retain. |
| `com.unity.modules.ui` | `1.0.0` | Unity editor built-in module; [Unity Software terms][software] | Public coordinate only; retain. |
| `com.unity.modules.uielements` | `1.0.0` | Unity editor built-in module; [Unity Software terms][software] | Public coordinate only; retain. |
| `com.unity.modules.umbra` | `1.0.0` | Unity editor built-in module; [Unity Software terms][software] | Public coordinate only; retain. |
| `com.unity.modules.unityanalytics` | `1.0.0` | Unity editor built-in module; [Unity Software terms][software] | Public coordinate only; retain. |
| `com.unity.modules.unitywebrequest` | `1.0.0` | Unity editor built-in module; [Unity Software terms][software] | Public coordinate only; retain. |
| `com.unity.modules.unitywebrequestassetbundle` | `1.0.0` | Unity editor built-in module; [Unity Software terms][software] | Public coordinate only; retain. |
| `com.unity.modules.unitywebrequestaudio` | `1.0.0` | Unity editor built-in module; [Unity Software terms][software] | Public coordinate only; retain. |
| `com.unity.modules.unitywebrequesttexture` | `1.0.0` | Unity editor built-in module; [Unity Software terms][software] | Public coordinate only; retain. |
| `com.unity.modules.unitywebrequestwww` | `1.0.0` | Unity editor built-in module; [Unity Software terms][software] | Public coordinate only; retain. |
| `com.unity.modules.vehicles` | `1.0.0` | Unity editor built-in module; [Unity Software terms][software] | Public coordinate only; retain. |
| `com.unity.modules.video` | `1.0.0` | Unity editor built-in module; [Unity Software terms][software] | Public coordinate only; retain. |
| `com.unity.modules.vr` | `1.0.0` | Unity editor built-in module; [Unity Software terms][software] | Public coordinate only; retain. |
| `com.unity.modules.wind` | `1.0.0` | Unity editor built-in module; [Unity Software terms][software] | Public coordinate only; retain. |
| `com.unity.modules.xr` | `1.0.0` | Unity editor built-in module; [Unity Software terms][software] | Public coordinate only; retain. |
| `com.unity.ugui` | `1.0.0` | Unity registry; [Unity Companion License for Unity-dependent projects][ugui-license] | Public coordinate only; retain. |

[modules]: https://docs.unity3d.com/2021.3/Documentation/Manual/upm-ui-disable.html
[software]: https://unity.com/legal/editor-terms-of-service/software
[mcp-license]: https://github.com/CoplayDev/unity-mcp/blob/v10.2.0/LICENSE
[burst-license]: https://docs.unity3d.com/Packages/com.unity.burst@1.8/license/LICENSE.html
[collections-license]: https://docs.unity3d.com/Packages/com.unity.collections@1.2/license/LICENSE.html
[mathematics-license]: https://docs.unity3d.com/Packages/com.unity.mathematics@1.2/license/LICENSE.html
[ugui-license]: https://docs.unity3d.com/Packages/com.unity.ugui@1.0/license/LICENSE.html

In `project-layout.json`, a runtime source whose GUID is `null` is new and not yet imported by
Unity: the build skips its `.meta` check until its first build, after which the GUID is
recorded.
