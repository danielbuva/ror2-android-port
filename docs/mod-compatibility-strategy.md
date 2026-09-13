# Mod compatibility after the vanilla Android port

Mod compatibility is **POST-VANILLA-PORT** work, not a new milestone or prerequisite. DEVELOPMENT_PLAN.md remains authoritative: achieve the original offline run before building a compatibility host. Architecture C does not depend on BepInEx, R2API, ThunderKit or an experimental Android loader.

## Preserve useful contracts now

Preserve original RoR2 namespaces, assembly/type identities, public and consumed method/field/property signatures, serialized script identities, prefab GUID/fileIDs, Addressable runtime keys and typed subobjects. Preserve content-pack registration phases, EntityState configuration/identity, CharacterMaster↔CharacterBody linkage, SkinDef/SkinDefParams semantics, catalog IDs, and NetworkIdentity/local authority relationships where the pinned input permits it. These are valuable for vanilla correctness as well as later ecosystem compatibility.

Divergences must be explicit: Android bundle payloads/provider internal IDs, app-owned profile/content roots, native middleware replacements, diagnostic or rebuilt shaders, and truthful unavailable platform capabilities. Do not rename original API/content identities just to simplify a harness. Do not preserve a Windows path or invalid payload merely for nominal compatibility.

## Compatibility categories

| Category | Possible route | Limits and evidence status |
| --- | --- | --- |
| A — assets/content | Rebuild or retarget authorized source/exported content into Android bundles | EXPERIMENTAL; shader programs, texture formats, serialization and external dependencies need validation. A Windows bundle is not portable by renaming. |
| B — source-available Unity/content mods | Adapt dependencies, rebuild content and compile compatible code into an AOT player | INFERRED promising compared with opaque binaries, but substantial. Starstorm2 demonstrates structured authoring/content; it still contains hooks, native dependencies and licenses that require separate review. Not plug-and-play. |
| C — source-available R2API/BepInEx plugins | Recompile selected logic against a future explicit host or integrate at build time | EXPERIMENTAL. R2API records useful registration seams, but its hooks/patchers and host assumptions must be analyzed module by module. Publicized reference assemblies are not a reason to change the currently unchanged originals. |
| D — ordinary runtime hooks | Possibly native/interoperability hooks or build-time adaptation of specific callbacks | NOT APPLICABLE as an assumed drop-in path. On.RoR2, Harmony Prefix/Postfix and RuntimeDetour depend on runtime, signature and bridge support; desktop Mono success proves none of these on our ARM64 IL2CPP player. |
| E — CIL mutation | Manual source port or targeted ahead-of-time transformation before IL2CPP | Runtime IL.RoR2/MonoMod.Cil patterns cannot be assumed to rewrite the native code executed after AOT. Interop stubs are not the original executed method IL. Revalidate semantics at the corresponding device gate. |
| F — Windows native plugins | Obtain authorized Android ARM64 equivalents or a bounded lawful alternative | Windows DLLs cannot supply Android ABI/native services. Middleware licensing and unavailable bank/authoring sources remain independent constraints. |

## Prior art, with explicit limits

Exact revisions, source paths, activity and licenses are in [community-sources.json](../reference/community-sources.json); applicable subsystem behavior is in [community-prior-art.md](community-prior-art.md).

**VERIFIED source:** R2API is split into content, Addressables, prefab/networking, director, damage/items, language and sound seams. Preserving those underlying game contracts may allow selected logic to be rebuilt later. It does not make the R2API binaries compatible now. R2API's patched game declarations are not authoritative replacements for the legitimate input.

**VERIFIED source:** Starstorm2 uses the exact 2021.3.33f1 revision and organizes asset collections, asynchronous content loading, survivor/display skins, named state machines and scene content. Its modern MSU dependency uses UberSkinDef while older VanillaSkinDef is obsolete. Its project license is GPL-3.0; embedded game/middleware assets are not automatically covered. MSU has custom attribution/README terms. Future source ports need a per-component license inventory. This research copied no implementation.

**VERIFIED source:** upstream BepInEx's inspected README describes stable Mono releases and desktop IL2CPP support; its compatibility chart does not establish ARM Android support. Its IL2CPP runtime uses an interop/toolchain ecosystem, not a promise that ordinary Mono mods work unchanged. The exact source is LGPL-2.1.

**EXPERIMENTAL prior art:** NextBep/BepInEx.Android adapts the preloader to Android environment discovery, CoreCLR entry and native interop. NextBep/BepInEx.Android.Launcher contains ARM64 native loading, il2cpp_init interception, Dobby integration and logcat diagnostics. These are source observations, not tested RoR2 compatibility, safety, performance or maintenance guarantees. The fork has LGPL-2.1; no root license was located in the launcher, so direct code reuse is not approved by this research. Component-level terms still need inspection. Neither repository was built, installed, run, or added as a dependency.

The vanilla Android player must remain independently buildable and runnable. No plan change, dynamic code host, mod marketplace, compatibility promise, source transplant or distribution work is authorized by this strategy. Revisit only after the vanilla gates, with one source-available mod and concrete content/API assertions.
