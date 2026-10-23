# Reconstruct the accepted Android build from owner inputs

Assessment: 2026-10-23. **A fixed-target converter is a credible, narrower design
than reproducing Unity's project/editor workflow on Android. It is not currently
an operational phone converter.** Existing results establish several ingredients,
but neither a complete game-code build nor the Android content producer exists
without desktop-generated inputs. The accepted APK is an oracle, not a permitted
input to a public installer. Do not start another general exporter or change the
working runtime on the strength of this assessment.

Keep Architecture C, Unity 2021.3.45f2, IL2CPP ARM64, the current renderer and
original gameplay implementations. ADR-002's Route A is its owner-build delivery
direction, not ADR-001's source-reconstruction Architecture A. The desktop
owner-build fallback remains available; it is not selected as the final player
experience. Experiment evidence is recorded once in [J1036](PORTING_JOURNAL.md#j1036--assess-fixed-target-reconstruction-of-the-accepted-android-build).

## What the accepted build actually contains

The immutable comparison target is J850: source `1780ea9545f1597c033a8d32e08074b03c7f38c8`,
APK SHA-256 `f1550ce0ff030ea0fa7a1ab66de19d54ee7894a7ae2f5b344f993157d6713949`,
accepted input `6af7ed94619fe1b4346974b4486afa03a8d1625a7820e92da0ff74d57208fe88`.
Its two standard assisted checks passed. It is a laboratory baseline, not a
complete released game or audio acceptance. Later audio APKs add a separately
supplied Android Wwise library and new owner-generated outputs.

All **574 APK entries** and **266 payload files** were read. The APK contains
222,167,613 uncompressed bytes; the payload contains 2,272,394,833 bytes:
133 UnityFS files, 132 text manifests and one catalog JSON. Five older payload
members were recovered from retained attempts and matched the frozen receipt;
the mutable current payload was not silently substituted. Whole-file hash
comparison against the 2,749-file legitimate PC inventory found no matches.
That result does not measure subfile reuse, patch size or conversion difficulty.

| Output | Size / extent | Reuse or reconstruction decision |
| --- | --- | --- |
| `libunity.so`, `libmain.so` | 60,927,416 and 13,312 bytes | Exactly match the supplied Unity Android IL2CPP **Development** ARM64 libraries. No game compilation is needed to reproduce these two entries. Acquire through permitted Unity distribution or owner-supplied SDK; runtime redistribution is conditional, not an open-source grant. |
| `unity default resources` | 4,222,168 bytes | Exactly matches the supplied Android module file. Same Unity rights/acquisition boundary. Other built-in/player data is not thereby cleared. |
| `libil2cpp.so` | 98,203,920 bytes | Contains game-derived native code together with authored/package/runtime code. Must be owner-generated or separately authorized. PC managed DLLs are inputs, not a ready Android library. |
| `global-metadata.dat` | 17,756,092 bytes | Must be generated with the matching stripped assembly closure and IL2CPP conversion. It is coupled to code/type registration; substituting a different metadata file is not an assembly loader. |
| `lib_burst_generated.so` | 268,688 bytes | Build output with provenance and compiler dependencies. Treat as owner-generated until the complete compiled cohort and grants establish otherwise. Do not remove Burst or reuse an opaque binary to simplify installation. |
| Other Unity player data | 40,487,585 bytes after the matched default resources | Includes serialized startup data, built-ins and imported resources. Separate generic engine resources from game-derived/imported data; the accepted APK does not establish that all of this cohort is distributable. |
| Android DEX/resources/manifest | Four DEX entries plus packaging/resources | Reuse permitted SDK/runtime Java inputs and compile authored Android code; generate package/version/resource tables. Existing phone packaging work is relevant. Preserve the actual manifest contract. |
| External UnityFS payload | 133 files; most payload bytes | Reconstruct locally from original assets plus authored transformations, dependency/remap rules and target-format encoders. They are not unchanged Windows bundles. |
| Catalog and bundle manifests | One JSON and 132 text manifests | Generate relationships, dependency names and hashes from reconstructed outputs. Existing recipes and catalog owners help; a digest manifest cannot synthesize missing bytes. |
| Signatures and installation identity | Owner-specific | Align and sign the completed APK with a durable private owner key. Existing project signing material is never shipped. Updates must retain that owner key. |

This is a complete output-cohort classification, not a claim that every serialized
object already has a direct reconstruction recipe.

## What can avoid the Unity Editor

There is no general requirement to reopen a Unity project merely to package or
execute an already constructed IL2CPP player. [Unity's documented IL2CPP stages](https://docs.unity3d.com/2021.3/Documentation/Manual/IL2CPP.html)
separate managed compilation, stripping, C++ generation, native compilation and
linking. Our J842/J921 authored-player results already connect phone-generated
code to fresh native compilation, replacement in a fixed player and actual
Android load/update checks. They retain desktop scene roots and base content;
they are not a game build.

For a **single pinned game/input/build profile**, a converter can replace editor
orchestration with explicit, audited inputs:

1. Verify the legitimate input and exact tool/profile versions. Select the
   declared source objects and dependency closure; do not import the entire game
   into an editor project just to discover a known graph.
2. Reuse existing assembly transformations and compile the authored adapter code
   against exact references. Generate or independently justify the required
   preservation/module/type-usage records from that graph and SDK metadata.
3. Run permitted exact stripping/IL2CPP tools, then compile/link the owner-derived
   Android game library and matching metadata. No gameplay interpreter is added.
4. Copy compatible source data ranges, transform serialized records/references,
   produce the required Android resources/shaders and write the fixed bundles
   and startup data directly. Stream bounded groups to disk; a global mutable
   AssetRipper object graph is not a necessary product requirement.
5. Generate catalogs/manifests, assemble with permitted generic runtime pieces,
   align, owner-sign and use Android's normal user-mediated installation flow.

The accepted build fixes the destination contract, graph, layouts and comparison
hashes. It cannot supply protected destination bytes to the public converter.
Public recipes may contain the audited minimum identifiers and transformation
logic needed to derive them. Captured editor files must be reviewed or regenerated,
not assumed publishable wholesale.

The code side therefore still needs compilation, **not necessarily an Editor or
a reconstructed Unity project**. The content side still needs target-data
production, **not necessarily Unity's import/export workflow**. Neither statement
establishes a complete replacement toolchain today.

## The content work that remains real

The source inventory records **1,425 compiled shaders, no shader source, all
platform 4 (D3D11)**. A read-only Commando comparison found PC textures in
DXT1/DXT5, while the accepted Android bundle uses ETC2_RGBA8/ETC_RGB4 and some
RGB24/RGBA32. Its 24 shaders are platform 18 (Vulkan). It contains 75,378 objects
and dependencies, compared with 1,619 in the single original Commando bundle;
this is not a one-to-one bundle mapping. No complete raw object record matched
within that scoped pair. Unchanged vertex, image, animation or other subranges
were not exhaustively measured and may still be reusable.

These observations rule out treating a platform flag edit or archive repack as
the accepted conversion. They do not prove that full Unity import is required.
[Unity documents platform-specific bundle assets](https://docs.unity3d.com/es/2021.1/ScriptReference/AssetBundle.html),
including different shaders and textures. A direct writer must preserve type
and script identity, object references, animation/avatar data, scene graphs,
external resource streams and bundle dependency ownership. Native baked mesh,
physics or other imported data must each have a source/producer decision.

Existing shader recovery already derives programs from owner-supplied DXBC;
it is not necessary to invent a different shader style. However, the current
replay still depends on **46 pinned local analysis inputs**, native tools and a
CrossOver fallback. The present compiler is UnityShaderCompiler. An open Vulkan
compiler alone does not reproduce Unity's variant selection, binding metadata
and serialized Shader representation. Porting the accepted derivation and
target writer, or obtaining permitted access to exact tools, remains work.
Distributing the accepted game shader programs would evade this dependency by
shipping game-derived content, which is outside the ownership model.

The authored no-editor UnityFS writer currently supports AssetBundle/TextAsset,
not this mesh/material/texture/animation/script/scene/shader cohort. The R1
owner-assembly prefix can reconstruct 49 DLL/importer pairs on the host without
a prior project. R2-R9 and the exporter are useful derivation knowledge, not a
finished binary-content converter. Existing inherited assets and private analysis
inputs also remain public-bootstrap debt in the desktop workflow.

## Binary patches and retained artifacts

| Candidate shortcut | Assessment |
| --- | --- |
| Use final manifests/hashes as the conversion | Validation only. They identify an output but contain no algorithm for creating it. |
| Copy original blobs/ranges; generate remaps and structural edits | Useful where a verified source-to-target relationship exists. This is the direct-reconstruction design; compatibility must be established per actual target data class. |
| Apply a PC-to-Android binary delta | Technically a delta can encode arbitrary output, including an entire new library. Its new literals/differences may contain game-derived machine code, shaders or content. Neither compression nor ownership checks establishes redistribution permission. No patch-size or literal-content audit has qualified such a package. |
| Ship generated C++, stripped game DLLs, metadata, an encrypted game library, or converted bundles | Still ships game-derived material. A later download or requirement to own the PC game does not establish authorization. |
| Reuse an owner's previously produced Android cache/APK | Technically useful for local install/updates and exact byte reuse. It requires that owner to have produced/supplied the cache already; it does not bootstrap PC files on a phone. |
| Publish a generic engine/bootstrap and authored recipe | Appropriate candidate, subject to exact component grants and a content/provenance audit. It cannot contain the current game's AOT code or baked assets disguised as a generic shell. |

## Genuine blockers and their scope

**Missing producers:** complete game/player managed compilation and roots;
matching code/metadata construction at game scale; the full target serialized
content and shader producer; Burst and current Android middleware integration.
These are absent implementations/qualifications, not proof that the Editor is
mathematically indispensable. A frozen destination removes general editor
authoring and asset discovery requirements, but does not remove their output
semantics.

**Phone execution and resources:** the shell fixture chain works, while the
ordinary target-33 app-host path still fails its writable-execution restriction.
An installer needs a permitted Android app/tool execution design. A Termux/ADB
proof is not that design. General AssetRipper imports have exceeded bounded
phone memory without returning a graph; a sequential raw scan succeeds at about
227 MB sampled RSS. That makes bounded direct reconstruction attractive, not
already implemented. The 4.12 GB PC input plus 2.27 GB target payload already
consume about 6.39 GB before SDKs, generated native sources/objects, APKs,
temporary data and retained rollback space. No complete phone peak-cost result
or completion estimate is available.

**Rights:** [Unity's terms](https://unity.com/legal/editor-terms-of-service/software)
provide conditional integrated-runtime distribution rights and distinguish
Editor/Toolkit use. They do not grant this project a blanket right to package
Editor/compiler components into an Android converter. The applicable agreement
for this exact Unity release/account and each supplied component needs to be
identified; current terms alone do not resolve historical applicability.
[The game's published Steam EULA](https://store.steampowered.com/eula/632360_eula_0)
provides a limited personal license and restricts redistribution/modification,
subject to applicable exceptions or separate permission. Legitimate possession
does not itself establish permission to distribute our derived Android code or
assets. The newer audio branch's Android Wwise SDK/runtime adds its own grant:
[Audiokinetic describes licenses per title/platform](https://www.audiokinetic.com/pricing/for-games/?asia=).
These are concrete unresolved grants, not a finding that every local conversion
is unlawful or that purchasing the PC game grants an Android SDK license.

No proposed converter may bypass DRM, authentication, ownership or DLC checks.
Local file verification must continue to be described as local input verification.

**Determinism and acceptance:** copying the target's signed APK is not the goal.
Owner signing necessarily changes the signature. J586 already observed build
ID/CRC, Burst path and Unity build metadata differences between desktop builds.
Define deterministic unsigned entries and code/content comparison rules
explicitly; do not normalize away shader instructions, serialized IDs or native
code differences. Pin transforms, roots, code-generation options, compiler,
optimization, libraries and shaders. An alternate Clang 21 build is not the
accepted Clang 9 build merely because both are IL2CPP. End-to-end device behavior
and matched performance remain required before adopting a new producer.

## Comparison and recommendation

| Route | What it saves | What still prevents a complete phone product |
| --- | --- | --- |
| General Unity-project reconstruction on phone | Reuses much existing desktop orchestration if all tools/importers become available | Global export/import memory, editor/native importer equivalents, shader tooling, build roots, tool rights and app execution. This is the broadest effort. |
| Fixed accepted-build reconstruction | Removes general project authoring, editor settling and unrelated input discovery; permits compatible data-range copies, streaming and a stable output manifest | Full game AOT inputs/build and target content/shader producers, app execution, component grants and complete acceptance. These cannot be replaced with target hashes. |
| Owner-supplied converted cache plus phone packaging | Avoids regeneration of that owner's existing code/content; strongest near-term reuse | Initial cache is external to the phone. Useful fallback/import mode, not PC-to-Android phone conversion. |
| Authorized prebuilt game code/shaders | Would remove major conversion stages | Requires rights not established here; cannot be the baseline assumption. Remaining owner content and acceptance still apply. |

**Recommend the fixed accepted-build reconstruction design as the next candidate
for phone conversion, while retaining the desktop fallback. Do not port the full
Unity Editor workflow or continue tuning general AssetRipper imports by default.**
This is a proposed build/distribution implementation within Architecture C; it
does not select a new execution backend or alter the accepted game build.

The implementation decision should be based on **one complete frozen-target
coverage map and end-to-end owner-input reconstruction**, reusing the existing
transforms and tool stages. Every required output must be either a permitted
generic component or have an owner-input producer, with no private target-byte
fallback. The present assessment identifies the two largest missing producers
(game-scale code and baked content/shaders); it does not establish a small patch
that closes them. Until they have a credible implementation and permitted tool
delivery, launching a second large converter would repeat the earlier mistake.

The simplest working experience available now is importing an owner's existing
converted cache and packaging/installing it, backed by the desktop owner build.
The simplest credible **phone-only first-build architecture** is the fixed-target
converter above. It is narrower than a Unity rebuild, but is not up and running
and is not yet demonstrated practical as a complete product.
