# Reconstruct the accepted Android build from owner inputs

The public converter targets functional native Android compatibility from
legitimate game files, permitted SDK inputs and public recipes. J850 remains
strict for code, asset identities, serialized relationships and runtime
compatibility. Incidental build identifiers and development connections may be
generated or omitted through named source producers; private historical values
are never required public inputs. Raw-exact results, generated metadata and
device acceptance are reported separately. Historical replay results below
retain their original byte-exact meaning.
J1254 supplies the two incidental startup files through a public producer;
current historical host readiness is 693/705 available (685 raw-exact, three
generated metadata/context files), with 12 reference entries still missing. Complete phone acceptance remains
open; the daily snapshot retains its earlier count until its next refresh.
The current source Menu producer now emits its complete 591-object graph and
standalone media through the player-data path. Its type identities/hashes match
J850, but current alignment and an original store-button Sprite differ from that
reference. Those genuine differences remain visible and do not advance the
historical readiness count; complete phone installation/update acceptance stays
open.


The public HUD phase emits its complete 2,021-object source graph and media
without historical HUD artifacts. All 6,648 pointers close and 5,236 nonnull typed
references match their target classes; script properties match the generated
registry. Its 119-object difference from J850 includes original hierarchy changes,
so historical exactness and native runtime acceptance remain open. J1264 records
the public-input proof; readiness stays 693/705.


The host-qualified [release update contract](../tools/phone-build/owner-apk/README.md#public-release-updates)
covers signed public-tool acquisition, per-entry incremental reuse, existing-key
signing and session installation. Publisher trust and a reviewed complete release
plan require maintainer provisioning; complete phone production and installed-game
update/save retention still require device qualification. No APK or game data
is published by the release workflow.
The [phone import/stage flow](../tools/phone-build/owner-apk/README.md#phone-only-import-and-installation)
adds SAF folder/ZIP admission, private resumable copies, foreground checkpoints,
unchanged thermal supervision and the existing session-install handoff. Public
recipes bind required originals; assembly hashes are computed on the phone from
verified source-produced outputs. No PC, Unity, private replay packet or supplied
game APK is part of this flow. A complete published producer plan and real-phone
qualification remain release gates, not conclusions from synthetic host tests.

Assessment and implementation evidence: 2026-10-23. **Complete private
accepted-output reconstruction now works on Android without Unity Editor or game
compilation.** A pinned delta/frame package plus verified owner PC and SDK inputs
reproduces every file of the frozen target. This is a practical narrow replay
architecture; independent PC-input-only conversion and a phone installation
product remain open. [J1065](history/journal-J1-J1177/PORTING_JOURNAL.md#j1065--qualify-private-owner-apk-preparation-upgrade-and-unity-lifecycle)
qualifies the private host-built/signed bootstrap candidate's device
preparation, upgrade, Unity lifecycle and assisted standard controls.
The package carries substantial game-derived
output information and stays private. No new execution backend is needed.

The complete host/Android result is recorded once in
[J1042](history/journal-J1-J1177/PORTING_JOURNAL.md#j1042--reconstruct-the-complete-accepted-output-on-android).
The open [receiver and its setup](../tools/phone-build/accepted-output/README.md)
preserve the proven stream implementation. The earlier census and producer
assessment below remain useful, but their missing-producer findings apply to
**independent derivation**, not to replaying a supplied private target package.

Keep Architecture C, Unity 2021.3.45f2, IL2CPP ARM64, the current renderer and
original gameplay implementations. ADR-002's Route A is its owner-build delivery
direction, not ADR-001's source-reconstruction Architecture A. The desktop
owner-build fallback remains available; it is not selected as the final player
experience. Experiment evidence is recorded once in [J1036](history/journal-J1-J1177/PORTING_JOURNAL.md#j1036--assess-fixed-target-reconstruction-of-the-accepted-android-build).

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

[J1063](history/journal-J1-J1177/PORTING_JOURNAL.md#j1063--complete-the-source-input-host-native-owner-build) completes one public source-input host command through fresh managed
production, stripping, IL2CPP conversion and native linking, without an Editor
project or captured native graph. Explicit authorized SDK products remain inputs.
The static loader contract passes; byte, performance and device equivalence
remain unqualified. Phone hosting and complete content production stay open.

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
hashes. Supplying destination bytes through a patch is a different distribution choice
from deriving them independently; evaluate that actual artifact and its rights.
Public recipes may contain the audited minimum identifiers and transformation
logic needed to derive them. Captured editor files must be reviewed or regenerated,
not assumed publishable wholesale.

For independent owner-input derivation, the code side still needs compilation,
**not necessarily an Editor or a reconstructed Unity project**. The content side still needs target-data
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

[J1050's complete decompressed-range census](history/journal-J1-J1177/PORTING_JOURNAL.md#j1050--measure-exact-data-reuse-across-every-pc-and-accepted-android-bundle)
now establishes substantial reuse across all PC/accepted payload bundles. It
supersedes the scoped raw-record comparison as the coverage assessment, while
leaving that experiment's observations intact. Exact ranges are useful inputs,
not serialized-object producers; the remaining code/content/shader construction
and public-input conversion gates stay open. Do not read chunk coverage as a
completed-conversion percentage or a public-patch size/rights result.

[J1070](history/journal-J1-J1177/PORTING_JOURNAL.md#j1070--produce-the-accepted-mesh-cohort-from-original-pc-bundles-on-android)
adds an independent source-only producer for 13,231 accepted mesh records,
with two tangent/importer cases excluded. Its tracked recipe contains selectors,
hashes and authored operations; no target geometry, byte deltas or target float
literals are supplied. The output is a private object/resource pack rather
than assembled bundles, so it does not replace the replay packet or establish
a whole-content conversion percentage. See the
[producer setup](../tools/phone-build/accepted-output/README.md#produce-meshes-directly-from-original-pc-bundles).

[J1075](history/journal-J1-J1177/PORTING_JOURNAL.md#j1075--produce-every-accepted-avatar-from-original-pc-bundles-on-android)
adds complete source-only Avatar production. Every byte is copied from original
body ranges, with complete original table entries reordered where required.
Its [producer setup](../tools/phone-build/accepted-output/README.md#produce-avatars-directly-from-original-pc-bundles)
uses tracked layout/identity metadata rather than target bodies. This completes
one object class; it does not complete bundles or the private-packet replacement.

[J1079](history/journal-J1-J1177/PORTING_JOURNAL.md#j1079--complete-uncompressed-texture-production-from-pc-bundles-on-android)
completes source-only production of all 399 uncompressed texture records,
including the public-source JPEG tool built on Android. Its
[setup](../tools/phone-build/accepted-output/README.md#produce-uncompressed-textures-directly-from-original-pc-bundles)
needs original PC pixels and tracked metadata, not target image literals.
[J1082](history/journal-J1-J1177/PORTING_JOURNAL.md#j1082--produce-the-complete-alpha8-texture-cohort-from-pc-bundles-on-android)
adds the complete 4,326-record source Alpha8/single-mip cohort and public codec
build on Android. Its [setup](../tools/phone-build/accepted-output/README.md#produce-alpha8-textures-directly-from-original-pc-bundles)
uses canonical original sources plus metadata relationships.
[J1088](history/journal-J1-J1177/PORTING_JOURNAL.md#j1088--produce-every-single-mip-etc1-texture-from-pc-bundles-on-android)
adds all 281 ETC1/single-mip records through the same source-only owner and
shared public codec, with a complete 5,006-record phone regression.
Other compressed formats/mips, complete bundle assembly and full replay-packet
replacement remain open.

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

The [complete managed-input case (J1052)](history/journal-J1-J1177/PORTING_JOURNAL.md#j1052--trace-the-full-player-managed-closure-and-reproduce-its-raw-audio-api-input)
traces the real full-player closure and executes the existing raw-input producer
without the Editor or modified project assemblies. It identifies concrete source,
post-processing and linker-root dependencies rather than treating an Editor
rebuild as inevitable. Its host result is not full-player or phone qualification;
reuse these existing producers instead of starting a second raw audio pipeline.

The [complete retained-package producer (J1053)](history/journal-J1-J1177/PORTING_JOURNAL.md#j1053--produce-all-four-retained-package-assemblies-without-the-editor)
now compiles all four retained package assemblies and their required managed
post-processor from explicit owner SDK/package inputs without the Editor.
This closes their host production dependency; DLL bytes still differ from the
capture, the declared managed projection is bounded, and Android execution,
full-player/native integration and performance remain unqualified.

The [complete source-audio input case (J1054)](history/journal-J1-J1177/PORTING_JOURNAL.md#j1054--reproduce-the-complete-source-bank-index-without-a-lab-project)
reproduces the exact full bank index from legitimate PC files without a project,
and reproduces Init bytes with the existing public transformation. The historical
receipt is reproduced by actually executing its retained producer; its separate
public-source audit remains open. No stage/request guard changes. These concrete
input results do not complete the requested-audio assemblies or the game build.

The [complete source prefab producer (J1055)](history/journal-J1-J1177/PORTING_JOURNAL.md#j1055--reconstruct-the-complete-source-audio-prefab-directly-from-pc-bundles)
derives all bytes of the required WwiseGlobal prefab from four original bundles,
existing script identity and one explicitly audited export-GUID binding. It
executes neither Editor nor exporter and consumes no target asset. This resolves
another whole source input without general import; Android execution and the
remaining game/player/native/content producers are still open.

The [complete requested-audio support case (J1056)](history/journal-J1-J1177/PORTING_JOURNAL.md#j1056--stage-and-compile-the-complete-requested-audio-support-closure-without-the-editor)
now stages all 274 payload files to the exact existing receipt and compiles the
observer/core/bootstrap through existing lower-level owners without a project
or Editor. Strict request/stage generators accept the independent input chain;
the instrumented native library remains supplied licensed local state.
Whole-player/native/device equivalence remains open, and existing project/runtime
admissions are unchanged.

The [complete gameplay source case (J1057)](history/journal-J1-J1177/PORTING_JOURNAL.md#j1057--compile-the-complete-gameplay-source-cohort-directly-from-owner-inputs)
produces all three exact visual maps from PC DLLs/catalog and compiles the full
145-source current gameplay cohort with 243 independent references. The matching
SDK compiler and fresh retained Burst processor run without a project or Editor;
all sixteen selected support types match the declared R27 target projection.
Full assembly/native/gameplay equivalence and independent player roots remain
open. Captured game DLLs are comparison oracles only.

The [whole-player fixed-root case (J1058)](history/journal-J1-J1177/PORTING_JOURNAL.md#j1058--strip-and-convert-the-complete-player-with-fixed-target-root-configuration)
now runs the complete host chain: 332 independent DLL providers → 93 stripped
DLLs → 691 generated C++/metadata files. It reuses supplied, explicitly labeled
current target root/preservation configuration and generates the SDK-native table
from owner SDK bytes. General Editor root discovery is unnecessary for that
candidate, but the configuration is not independently inferred scene semantics
or an audited public bootstrap. Stripped DLLs match only 45/93 frozen R27 hashes;
no whole-output/native equivalence is claimed. Full native/Burst, content/shader
production, Android execution and installation remain open.

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

**Missing producers/qualification:** independent licensed native SDK product
production/acquisition, the full target serialized content and shader producer,
Burst and Android integration. [J1063](history/journal-J1-J1177/PORTING_JOURNAL.md#j1063--complete-the-source-input-host-native-owner-build) completes public source-input
host game-code orchestration through the native library. Remaining missing
implementations/qualifications do not prove the Editor is mathematically
indispensable. A frozen destination removes general authoring and discovery
requirements, but does not remove their output semantics.

**Phone execution and resources:** the shell fixture chain works, while the
ordinary target-33 app-host path still fails its writable-execution restriction.
An installer needs a permitted Android app/tool execution design. A Termux/ADB
proof is not that design. General AssetRipper imports have exceeded bounded
phone memory without returning a graph; a sequential raw scan succeeds at about
227 MB sampled RSS. That makes bounded direct reconstruction attractive, not
a reason to require full project import. J1042 instead completes bounded replay
using a private package. The 4.12 GB PC input plus 2.27 GB target payload already
consume about 6.39 GB before SDKs, generated native sources/objects, APKs,
temporary data and retained rollback space. J1042 measures complete replay cost; the cost of independent code/content
production remains unmeasured.

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

**Deeper rights research and working policy.** Rights uncertainty is not a
blanket stop on local owner-only feasibility work, nor a reason to discard
independently authored conversion recipes. [Hopoo's published modding statement](https://store.steampowered.com/news/posts/?appids=632360&enddate=1567203681&feed=steam_community_announcements)
encourages the modding community and describes its intended EULA purpose. This
is favorable evidence for mod tools, but a historical community statement is
not a specific grant to redistribute a later Android game build.

There are legal paths that do not require a new permission letter for every
tool. [17 U.S.C. §117(a)](https://www.copyright.gov/title17/92chap1.html#117)
provides a conditional owner-copy/adaptation exception; eligibility and the
proposed use matter, while §117(b) separately restricts transfers of adaptations.
[Sony v. Connectix](https://law.justia.com/cases/federal/appellate-courts/F3/203/596/474793/)
protects the particular intermediate reverse-engineering use considered there.
Neither is a universal approval or prohibition of this local port.
[Galoob](https://law.justia.com/cases/federal/appellate-courts/F2/964/965/341457/)
also rejects a blanket infringement theory for the Game Genie, while
[Micro Star](https://law.justia.com/cases/federal/appellate-courts/F3/154/1107/625110/)
finds infringement for the different fixed map-file product before it. These
different outcomes require examining the actual tool/patch and protected
expression; neither the word "patch" nor absence of embedded source text settles
the question.

Accordingly, proceed with private owner-generated reconstruction and patch
feasibility under the existing no-DRM-bypass scope. Do not classify every derived
byte as automatically forbidden. Evaluate any proposed public patch's actual
data and applicable grants/exceptions; absence of a port-specific prohibition
alone is not affirmative public-distribution clearance. The explicit game-EULA
restrictions, statutory transfer restriction and conditional SDK grants are
evidence to resolve for that particular distributed artifact, not an excuse to
leave the technical reconstruction uninvestigated. No conclusive determination
that the proposed independently authored owner-only converter is unlawful was
established by this research.

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

[J1084](history/journal-J1-J1177/PORTING_JOURNAL.md#j1084--run-whole-player-stripping-conversion-and-arm64-compilation-in-the-android-tool-host) qualifies the supplied-provider Android backend
control. Its linker/converter match the host, but its separately corrected native
link differs under Android Clang 21. [J1098](history/journal-J1-J1177/PORTING_JOURNAL.md#j1098--preserve-recorded-object-order-for-the-fixed-target-native-link) preserves the recorded native object order for the fixed
target: host metadata and all 23 native executable/data sections match J850
exactly, with build-ID/debug-link differences retained. The source-only phone
native job, corrected phone linking and complete APK/device/performance
acceptance remain open; the accepted target supplies no
hidden output bytes.

[J1094](history/journal-J1-J1177/PORTING_JOURNAL.md#j1094--qualify-exact-sdk-vulkan-shader-compilation-on-android) qualifies standalone exact-SDK
Vulkan tool execution with identical authored host/phone payloads, reflection and
diagnostics. It does not qualify original shader recovery, complete variants,
serialized shader records, ordinary app delivery or accepted-target appearance.
[J1102](history/journal-J1-J1177/PORTING_JOURNAL.md#j1102--qualify-linked-vulkan-fragment-output-and-explicit-owner-apk-code-inputs)
confirms the linked payload contains both executable graphics stages; an authored
fragment-only operation change preserves its vertex module and changes the
fragment instructions, raw-exact across host/phone. The existing APK builder now
accepts an explicit complete IL2CPP/metadata/Burst cohort alongside the content
producer's existing target-file tree, with no replay code fallback. Full-player
assembly and phone/install/performance gates remain open.

The same explicit `code` mapping now also accepts the complete 13-entry Android
SDK output cohort with those three mandatory code files. The SDK producer owns
the exact entry membership; partial cohorts and unknown paths refuse. Produced
manifest bytes feed the existing bootstrap/version patch, while the other SDK
outputs stream unchanged with actual source hashes and independent ZIP readback.
Host fixtures verify complete 16-entry selection without replay source files,
including manifest consumption and drift refusal. Complete phone composition,
installation, controls and matched performance remain open.

[J1103](history/journal-J1-J1177/PORTING_JOURNAL.md#j1103--produce-fixed-target-burst-and-sign-owner-apks-in-the-android-tool-host)
closes the fixed-target ordinary-app Burst producer and authored-APK app-signing
gates. All 20 Burst runtime sections and fresh linker roots match J850; raw
build-ID/debug differences remain. The app retains a private owner key across
separate signing processes. Android DEX/manifest/resources and SDK library
staging, complete source-derived target assembly, corrected phone native linking,
full-player signing, compatible signer provisioning, ordinary installation and
matched game performance remain open. Accepted APK entries remain validation
references, never fallback suppliers for those missing producers.

## Comparison and recommendation

| Route | What it saves | What still prevents a complete phone product |
| --- | --- | --- |
| General Unity-project reconstruction on phone | Reuses much existing desktop orchestration if all tools/importers become available | Global export/import memory, editor/native importer equivalents, shader tooling, build roots, tool rights and app execution. This is the broadest effort. |
| Fixed-target independent derivation | Removes general project authoring, editor settling and unrelated input discovery; permits compatible data-range copies, streaming and a stable output manifest | Full game AOT inputs/build and target content/shader producers, app execution, component grants and complete acceptance. Target hashes alone cannot supply the bytes. |
| Private accepted-output delta/frame replay (J1042) | Complete phone reconstruction avoids Editor, import, shader compilation and game compilation; native/code/content bytes match the accepted target | Requires a 1.89 GB game-bearing private package plus supplied SDK bytes. Public packet/profile acquisition, phone-side signing, ordinary app/launcher execution, update/install and any public package distribution remain open; host packet reproduction and aligned/signed assembly pass. It does not independently derive the target from PC files alone. |
| Owner-supplied converted cache plus phone packaging | Avoids regeneration of that owner's existing code/content; strongest near-term reuse | Initial cache is external to the phone. Useful fallback/import mode, not PC-to-Android phone conversion. |
| Authorized prebuilt game code/shaders | Would remove major conversion stages | Requires rights not established here; cannot be the baseline assumption. Remaining owner content and acceptance still apply. |

**Recommend the fixed accepted-build reconstruction design as the next candidate
for phone conversion, while retaining the desktop fallback. Do not port the full
Unity Editor workflow or continue tuning general AssetRipper imports by default.**
This is a proposed build/distribution implementation within Architecture C; it
does not select a new execution backend or alter the accepted game build.

The complete J1042 experiment answers the immediate feasibility question: an
Editor rebuild is **not technically required when the required target information
is supplied in a delta/frame package**. This path reconstructs all native code,
metadata, resources and bundles, without altering their runtime architecture.
The private package is about 75.73% of the total uncompressed target size. Most
frames do not use a PC dictionary; this is neither an optimal all-source delta
search nor proof that a small independently distributable patch exists.

**Continue the narrow replay implementation before another large exporter:**
use the reproducible packet producer and corrected resource-storage assembler;
integrate [J1095 durable signing](history/journal-J1-J1177/PORTING_JOURNAL.md#j1095--retain-one-on-device-owner-key-across-separate-apk-signing-builds)
into the full-player path, connect an ordinary Android host to the
approved launcher adapter, and qualify normal installation/update and performance
on device. The initial phone-produced archive needs the corrected assembly step.
The resulting host-aligned/signed candidate is ready for device qualification; no
installation is inferred. Keep private owner-generated packages as a usable local route while evaluating the actual contents and applicable rights
of any proposed public package; uncertainty did not stop the local implementation.

If the public delivery path cannot supply those frames under applicable rights,
independent producers are still needed for the game-scale AOT and baked
content/shader cohorts. J1042 does not solve that separate information-source
problem by compression. The desktop owner-build/cache fallback remains available
while the phone product is completed. No final distribution architecture is
adopted solely from byte-reconstruction success.

J1109 qualifies all 13 generic Android package entries from pinned SDK/public
tools on the host, raw byte-identical to J850. Ordinary Android app-host production
also succeeds: 11 entries are raw-exact; the other two DEX files differ only in
compiler-generated class checksums and derived DEX headers, with all remaining
bytes exact. The guarded startup-affinity rerun completes with a 79.2 C peak and
340 ms maximum sampling gap, meeting the short-job thermal protocol; the earlier
95.5 C failure remains recorded. Complete content composition, sustained thermal
qualification and final installation remain open.

[J1112](history/journal-J1-J1177/PORTING_JOURNAL.md#j1112--inventory-final-owner-apk-inputs-before-launcher-compilation) records the current owner APK `--check-request` action inventories the existing final
`targets[].path` tree plus the complete 16-entry code/SDK selection before any
launcher compilation. Missing files remain explicit; it never substitutes a
replay file for an absent produced code output. Raw code differences remain
separate from file availability, source provenance and runtime qualification.
Use the same request for assembly once the content owner supplies final bundle/
player-data files; its intermediate record packs cannot fill those paths.
Follow unsigned assembly with the existing durable owner-signing action. The
separately labelled full host replay-content validation passes composition,
durable signing, signature verification and alignment. Source-derived content,
corrected phone-native production and device installation remain open.

[J1114](history/journal-J1-J1177/PORTING_JOURNAL.md#j1114--produce-both-generic-android-build-metadata-files)
extends the existing SDK producer to both generic Android `META-INF` metadata
files without accepted-byte inputs. Fresh host production makes all 15 SDK
entries raw-exact. The current explicit selection contains 18 code/SDK files;
the readiness report leaves 687 missing final content files and no code-file
availability gaps. J1187 verifies all 15 persisted outputs raw-exact in the ordinary
Android app host,
including the added metadata and all four DEX files; the prior 13 are unchanged.
Producer time is 44.279 s (48.614 s supervised), peak UID RSS 358,784 KiB,
output 60,271 KiB and observed CPU/GPU peak 54.5 C. Evidence and per-file hashes:
`work/coordination/phone-code/android-sdk-phone-v6-proof.json`. Cleanup passes
with both displays asleep and the lease released. This run lacks current battery/charge
admission evidence; thermal qualification remains open despite the cool CPU/GPU trace.
The shared producer cutoff is corrected to battery >= 43 C. Complete native/content
composition, installation, controls and matched performance remain separate gates.

[J1153](history/journal-J1-J1177/PORTING_JOURNAL.md#j1153--admit-reviewed-current-input-drift-without-historical-runtime-suppliers)
adds explicit `drift-explained` readiness for current-install content. Three
pinned private documents bind historical exact production, repeated current
production by the same public producer, and a complete named input/output
difference map. The checker hashes every current extent and reports exact and
drift-explained counts separately. Assembly and the Android payload index use
the admitted current hashes; historical originals and outputs are qualification
evidence only. The [evidence contract](../tools/phone-build/owner-apk/README.md#current-input-drift-evidence)
still requires human review of source lineage and independent invocations.
It does not qualify runtime behavior or permit replay filling missing inputs.

[J1154](history/journal-J1-J1177/PORTING_JOURNAL.md#j1154--collect-the-paused-native-jobs-terminal-timeout-without-restarting-it)
collects the original phone native job's failed terminal report. Job 498 times
out at the existing 3,600 s wall deadline; retained objects and receipts remain
available for checked continuation. A complete phone-native library and matched
game controls/performance remain open.

[J1162](history/journal-J1-J1177/PORTING_JOURNAL.md#j1162--retain-the-native-measurement-transport-failure-and-refresh-source-readiness)
updates current host readiness to 583 of 705 files: 578 raw-exact, two produced
code outputs requiring separate comparisons and three drift-explained files.
Seven APK files and 115 payload files remain missing; current-only assembly,
phone production and runtime qualification remain open. The native measurement
attempt stops on a host ADB stream SIGKILL during tool-host compilation, before
any native timings. Its sender is unknown; cleanup verifies stopped tools,
sleeping panels and lease release.

J1183 adds eight source-derived scene bundles after the five in J1179: current
host readiness is 606 of 705 files (601 raw-exact, two code comparison entries
and three drift-explained); 99 remain missing (7 APK, 92 payload).
The eight scenes expose 135,541 records, including 80 Shader records, through
existing object/Shader owners and the target-tree writer. Spine Shader variants
follow original scene renderer roots; whole scenes retain recursive content closure.
Complete phone assembly and runtime qualification remain open.

[J1167](history/journal-J1-J1177/PORTING_JOURNAL.md#j1167--measure-representative-native-compilation-on-the-phone) completes the three representative ordinary-app native compiler timings.
They size the active-time budget for checked continuation from 498 retained
objects; complete native production, final assembly and game qualification
remain open.

J1168 records the first continuation failure before compilation: Android
Python lacks `os.link`. A receipt-checked copy fallback passes host contracts;
full phone native production and gameplay qualification remain open.

[J1161](history/journal-J1-J1177/PORTING_JOURNAL.md#j1161--assemble-the-complete-player-script-registry-and-default-scene-shared-file)
adds complete source-derived script-registry and default-scene files through the
existing player owner. Its 177-file host cohort has 175 raw-exact files and two
current-input differences; complete host availability is 583 of 705 files.
[J1169](history/journal-J1-J1177/PORTING_JOURNAL.md#j1169--bound-the-complete-source-only-player-registry-metadata-lifetime) closes the host metadata memory gate;
a fresh bounded phone replay remains open.
[J1159](history/journal-J1-J1177/PORTING_JOURNAL.md#j1159--phone-player-assembly-refuses-an-omitted-original-shader-input)
records the separate phone replay's incomplete staging;
[J1166](history/journal-J1-J1177/PORTING_JOURNAL.md#j1166--guarded-phone-player-assembly-stops-on-thermal-limit)
records its repaired retry's thermal stop and verified cleanup. No complete
phone comparison or installation is qualified.

[J1171](history/journal-J1-J1177/PORTING_JOURNAL.md#j1171--identical-input-scene-exports-change-historical-yaml-identity-hashes)
confirms exporter GUID entropy in identical-input scene YAML repeats. The
WholeStageContexts remains non-exact to that historical YAML provenance. The
current public original-record producer described below uses independently
verifiable source provenance under the updated input contract; the historical
raw-exact counter remains unchanged.

J1185 completes source-derived Conduit Canyon through the existing owners:
607/705 files available (602 raw-exact, two code comparisons, three drift-explained),
98 missing (7 APK, 91 payload). Fungal Shader packs qualify separately; complete
Fungal assembly and phone/runtime qualification remain open.

J1192 closes ten further source-derived spine payloads: Golemplains2,
Dampcavesimple, Blackbeach2, Foggyswamp, Ancientloft, Village, Shipgraveyard,
Goolake, Golemplains and Blackbeach. Guarded public CLI production followed by
independent comparison verifies all 140,029 persisted objects, 20 serialized
members and ten compressed bundles raw-exact against J850. Current host readiness
is 626/705 available (621 raw-exact, two code comparisons, three drift-explained),
with 79 missing (7 APK, 72 payload). Existing object/Shader owners and the
target-tree writer consume audited public selectors and separately produced
record packs. Phone production, installation and original behavior remain open.

The complete single-mip RGBA source pack now has Android shell evidence
([J1199](PORTING_JOURNAL.md#j1199--complete-phone-rgba-production-and-app-texture-dispatch)): 1,333 records and all three persisted output hashes match the
host target after verified checkpoint continuation. This supplies existing
receipt-pinned texture consumers; it does not close missing complete bundles.
App-host texture dispatch reuses this producer, with device execution still open.

J1220 closes Frozenwall, Villagenight and Foggyswamp source bundles and Skymeadow
spine: 69,360 persisted objects, eight serialized members and four compressed
bundles are host raw-exact to J850. Original Bezier curve operands plus 42
captured build-angle triplets produce geometry locally; public recipes contain
no captured geometry arrays. Receipt-pinned Shader index reuse preserves actual
supplier provenance. The retained landed union includes Frozenwall spine and
advances from 648 to 652/705 available (647 raw-exact, two code comparisons,
three drift-explained), with 53 missing (7 APK, 46 payload). Evidence:
`work/coordination/p1-scenes-ss/safe-five-v1/readiness-union/`.
Goolake, Lakes, Lakesnight and Village source recipes remain open. Complete phone
production, installation and original runtime behavior remain separate gates.

J1256 adds the public original-record WholeStageContexts producer and narrow APK
admission. All runtime fields in 23 population contexts and three identity/toggle
graphs match J850; 26 incidental exporter hashes use explicit member/graph
provenance. The complete named file is regenerated during admission, without
masking fields or trusting a target-derived graph. Host availability becomes
693/705: 685 raw-exact, two generated startup files, one generated source context,
two code comparisons and three explained input differences; 12 files remain.
Complete phone generation, installation, launch and data-preserving updates remain
open. Evidence: `work/coordination/orchestrator/stage-context-public-v2/`.

J1261 adds complete opt-in original-lighting alternatives for Promo and Snowy
Forest. Public source production runs with historical outputs, exported projects
and preparation captures denied as inputs. Of 30,149 objects, 30,141 are
historically raw-exact; the other eight preserve original reflection chains and
RenderSettings. Every native/script identity, script table and external-file
identity matches J850. Source material/probe/sky relationships remain checked.
Snowy's rebound empty component derives its correct cached script identity from
the original MonoScript and SDK; no historical identifier is a literal input.
These two source artifacts are separate from the unchanged historical 693/705
count. Native BC6H support, complete phone generation, full game-runtime behavior
and final source-output assembly/install/update qualification remain gates.
Evidence: `work/coordination/orchestrator/scenes/promo-source-complete-v1/` and
`work/coordination/orchestrator/scenes/snowy-source-complete-v2/`.
