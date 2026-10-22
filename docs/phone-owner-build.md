# Phone-only owner-build assessment

2026-10-21. Scope: build/distribution engineering under
[ADR-002](ADR-002-public-alpha-distribution.md), keeping the IL2CPP ARM64 game
and Android renderer fixed. This combines source/tool inspection and isolated
authored probes, not a complete phone build or gameplay proof.
Evidence: [J831](PORTING_JOURNAL.md#j831--assess-phone-only-owner-builds-with-the-il2cpp-runtime-fixed).
First probe checkpoint: [J832](PORTING_JOURNAL.md#j832--run-the-exact-converter-on-android-and-load-content-built-without-a-template).
Phone generation/update checkpoint:
[J833](PORTING_JOURNAL.md#j833--generate-content-and-sign-increasing-fixture-updates-on-android).
Storage/oracle review qualification: [J834](PORTING_JOURNAL.md#j834--bind-phone-fixture-paths-and-the-exact-editor-oracle-after-review).
Authored phone-app build and unresolved sandbox control: [J836](PORTING_JOURNAL.md#j836--build-an-authored-apk-on-android-and-test-app-host-execution).
Target-33 follow-up: [J929](PORTING_JOURNAL.md#j929--test-the-authored-app-host-refusal-at-target-sdk-33).
Native fixture compile/link/loading: [J839](PORTING_JOURNAL.md#j839--compile-and-link-the-authored-il2cpp-native-library-on-android).
Full authored converter/native/device closure: [J842](PORTING_JOURNAL.md#j842--run-the-full-authored-converter-and-load-its-phone-compiled-native-output).
Authored input capture and Android stripping: [J846](PORTING_JOURNAL.md#j846--capture-authored-stripping-inputs-and-replay-unitylinker-on-android).
Connected stripping/converter boundary: [J849](PORTING_JOURNAL.md#j849--feed-actual-phone-stripping-output-into-the-exact-converter).
Independent-root contract inventory: [J851](PORTING_JOURNAL.md#j851--measure-sdk-metadata-coverage-and-identify-the-native-registry-gap).
Partial native-registry extraction on Android: [J853](PORTING_JOURNAL.md#j853--read-partial-owner-sdk-native-registration-metadata-on-android).
Explicit static-record module completion: [J855](PORTING_JOURNAL.md#j855--resolve-static-sdk-modules-from-explicit-registration-call-arguments).
Complete pinned native-registry metadata: [J857](PORTING_JOURNAL.md#j857--recover-the-complete-pinned-native-registry-from-owner-sdk-metadata-literals).
SDK-native metadata into stripping/conversion: [J859](PORTING_JOURNAL.md#j859--generate-sdk-native-root-metadata-on-android-and-preserve-strippingconversion).
Restricted fixture module policy into stripping/conversion: [J862](PORTING_JOURNAL.md#j862--derive-authored-fixture-module-policy-from-owner-sdk-and-package-data-on-android).
Persistent native class-ID prerequisite: [J864](PORTING_JOURNAL.md#j864--read-persistent-native-class-ids-from-the-pinned-sdk-on-android).
Scoped managed metadata/forwarding on Android: [J866](PORTING_JOURNAL.md#j866--qualify-scoped-sdk-assembly-metadata-and-forwarding-on-android).
SDK normal-path wrapper-search metadata: [J869](PORTING_JOURNAL.md#j869--decode-pinned-sdk-wrapper-search-order-on-android).
Independent desktop wrapper-query oracle:
[J873](PORTING_JOURNAL.md#j873--separate-direct-scene-names-from-sdk-wrapper-cache-queries).
Native SDK abstract/sealed/editor flags on Android:
[J876](PORTING_JOURNAL.md#j876--decode-native-sdk-type-flags-on-android).
SDK forward wrapper population on Android:
[J878](PORTING_JOURNAL.md#j878--reconstruct-sdk-wrapper-population-on-android-with-a-complete-forward-oracle).
Root-inclusive Android metadata/native SDK cache comparison:
[J883](PORTING_JOURNAL.md#j883--include-the-object-root-and-match-android-metadata-to-native-sdk-caches).
Independent desktop scene/manager observation and bounded name comparison:
[J893](PORTING_JOURNAL.md#j893--observe-authored-scene-and-manager-dependencies-without-conflating-native-identities).
Android SDK manager registration declarations and asset-dependency metadata:
[J895](PORTING_JOURNAL.md#j895--read-sdk-manager-registration-declarations-on-android-and-preserve-retention-boundaries).
Exact SDK C# compiler on Android, with unequal cross-host debug outputs:
[J899](PORTING_JOURNAL.md#j899--compile-an-authored-c-fixture-on-android-and-preserve-cross-host-output-differences).
SDK/package-derived Unity API fixture compilation on Android:
[J902](PORTING_JOURNAL.md#j902--compile-the-authored-unity-fixture-with-sdkpackage-derived-references-on-android).
Android-compiled fixture inputs through a separate stripping handoff:
[J905](PORTING_JOURNAL.md#j905--feed-the-android-compiled-unity-fixture-into-a-separate-stripping-handoff).

**Finding:** this repository has no demonstrated phone-only build path. Many
preparation and packaging stages have Android-capable open-source building
blocks. Unity's import/shader/bundle/player-data stages remain editor-bound in
the current implementation. The exact converter now passes the complete authored
player's stripped assembly closure on Android. The exact stripping tool also
passes the authored fixture using captured desktop scene/editor roots, and J849
connects its actual outputs to code generation, reaching the source/metadata
boundary qualified by J842's native build and device loading. Desktop
scene/editor roots, base engine and content inputs remain explicit.
A small content writer and fixture repackaging/signing/update have
phone-shell proofs. A separate app now builds wholly on the phone and runs an
installed native probe, but its writable-execution refusal control fails. Complete
player construction and app-host tool delivery remain open. Native fixture
compilation/linking passes with either supplied desktop-generated C++ or the
hash-bound phone converter output; that does not recreate missing content or
editor-generated stripping roots.
J851 measures why managed SDK metadata alone cannot replace those roots and
J857 qualifies the pinned SDK's complete native-registry metadata on Android.
J859 generates that native table at the actual stripping invocation and reaches
the same qualified C++/metadata boundary with captured project roots retained.
J862 additionally derives the restricted builtin/no-overrides fixture's module
policy from supplied SDK/package data, without staging captured policy arrays.
Project scene usage, general module policy and complete independent linker
roots remain unproduced.
J864 independently reads persistent native class IDs as another prerequisite;
J866 qualifies scoped managed metadata/forwarding on Android; J869 decodes the
SDK's normal-path wrapper-search metadata there. Linker-consumer semantics
and scene/manager/dependency usage remain open. J873 adds an independent desktop
verification oracle and separates direct scene names from inherited cache
queries; its reports are never phone-build inputs.
J876 qualifies a separate static native flag reader on Android.
J878 verifies forward wrapper mappings on Android against all supported exact-SDK
queries. J883 corrects root membership and matches Android-produced metadata to
independently observed native forward/reverse caches. Complete
linker-consumer semantics and root production remain unqualified; direct scene
names stay separate.
J893 adds a fresh authored SDK scene/manager dependency oracle and a bounded
comparison with the retained fixture's linker type names. Native usage
identities, scene associations and complete independent roots remain open;
the oracle is never a phone-build input.
J895 qualifies manager registration declarations on Android while retaining
live-context, target/serialization and complete native-usage gates. Dependency
exclusions remain separate from native class retention.
[J931](PORTING_JOURNAL.md#j931--read-manager-write-dispatch-bindings-on-android-without-evaluating-retention)
qualifies static write-method bindings and consumer dispatch offsets on Android;
actual target/state decisions and independent root production remain open.
[J934](PORTING_JOURNAL.md#j934--read-android-sdk-feature-declarations-and-compare-independent-api-observations)
qualifies a separate Android feature-declaration reader against SDK API
observations; module inclusion, live state and native usage remain separate
requirements before independent root production.
[J939](PORTING_JOURNAL.md#j939--read-sdk-target-key-input-bindings-on-android-and-preserve-lookup-mismatches)
qualifies static target-key input bindings on Android while preserving SDK API
lookup mismatches. These declarations do not establish constructed maps or
current target/module availability.
J899 runs the SDK's actual Roslyn compiler and unchanged runtime configuration
on Android for one authored arithmetic library. Android repeats its own outputs
exactly, but its DLL/PDB bytes differ from the desktop control. The observed
compiler-host version and derived debug identities explain this fixture's
differences; general managed compilation and pipeline equivalence remain open.
J902 independently selects the fixture's ordered SDK reference closure from
supplied SDK/package data, then compiles its public Unity API source on Android.
The generated reference report and reference assembly match the host; raw
implementation DLL/PDB bytes still differ. Full player defines, generators,
custom packages, stripping integration and game compilation remain open.
J905 connects the actual Android-produced fixture DLL/PDB to a separate
stripping handoff. The same output closure is emitted, with only those two
members differing from the earlier replay. J920/J921 then qualify conversion,
fresh native compilation and installed loading of that authored closure.
Desktop scene roots and base engine/content remain inputs.
These are build-pipeline problems; keep the game runtime
and desktop fallback while investigating them independently.

## Stage map

"Port candidate" means a public tool/source mechanism exists; it does not mean
our current command works on Android. "Editor-bound" describes this pipeline,
not proof that reimplementation is impossible. Owners: [ARCHITECTURE](ARCHITECTURE.md).

| Stage / owner | Desktop Unity required today? | Android assessment |
| --- | --- | --- |
| Acquisition, inventory, acceptance (`inventory.py`) | No | File/ZIP import, hashing and version checks are portable. Owned-account downloads need Guard, entitlement and accepted-version tests; no offline authentication substitute. |
| Decompile/export (`recovery.py`, ILSpy, AssetRipper) | No editor API; supplied tools are desktop builds | Public source permits investigating Android tool hosts and dependency ports. AssetRipper exports a project, not final Android content. |
| Assembly transforms/R1 (`assembly_transforms.py`, `AssemblyProbe`) | No | Cecil-based IL/metadata transforms are port candidates. Preserve exact DLL hashes/type identity. An Android build-tool host is unproven; it does not run gameplay. |
| R2–R6 composition, catalog, dependency and scene transforms | Mostly host code after export | Port candidates. Python, native texture/compression libraries, C# helpers and process/path assumptions all need qualification. A phone Python interpreter alone is insufficient. |
| Shader recovery/HLSL generation (`shader_recovery.py`, `shader_programs.py`) | Not inherently editor-bound | Pinned native tools and a CrossOver/Wine fallback remain; 46 local analysis inputs still need producers. Android-native replacements are unresolved. No Windows emulation route is selected. |
| HUD/inherited assets (`RecoveredHudBuilder`) | **Yes, existing producer** | AssetDatabase, prefab, font/material and asset-saving APIs are used. Fourteen inherited-store files remain bootstrap debt; generated game assets cannot be shipped to conceal this dependency. |
| Import, script/plugin binding and settling (R9 `LabBuild`) | **Yes** | Native importers, AssetDatabase and two-pass dependency reimport have no demonstrated Android equivalent here. Host validators do not replace importers. |
| Shader compilation/Android bundles (`LabBuild`, `WholeCatalogBuild`) | **Yes** | BuildAssetBundles, UnityShaderCompiler and ShaderUtil produce/validate target variants. SPIR-V compilation or a UnityFS writer alone does not recreate shader metadata, object graphs, mesh/animation import or dependencies. |
| C# compilation (`BuildPlayer`) | **Yes in current orchestration** | J899 runs exact SDK Roslyn components on Android with the original configuration. J902 derives the authored fixture's ordered SDK/package reference closure and compiles its unconditional Unity API source there; generated references and reference DLL match the host. Implementation DLL/PDB bytes differ. General defines, generators, custom packages, downstream integration and actual game/player compilation remain unqualified. No game runtime changes. |
| Stripping, IL2CPP C++/metadata (`BuildPlayer`) | **Yes in current orchestration** | J859/J862 connect SDK-native metadata and restricted fixture module-policy generation to authored stripping/conversion. J905 strips the actual Android-compiled fixture inputs; J920/J921 connect their conversion, fresh native linking and installed loading without weakening earlier replay gates. Captured project roots, general module policy, richer dependencies, game compilation and app/tool delivery remain gates. |
| C++/Burst/plugin compilation/linking | Not inherently, once all inputs exist | J839/J842 qualify the authored native graph with desktop or phone-generated C++; J921 uses the actual phone-compiled/stripped fixture closure. Original target libraries, captured native graph, base engine/content remain inputs. Compiler/linker and game-performance equivalence, Burst and middleware remain separate gates. |
| Java/resources/DEX, APK alignment/signing | No Unity import APIs | AOSP/Termux provide resource-tool, alignment and signing precedents; D8/R8 source is available. J836 builds native C/Java/DEX/resources and signs an authored app wholly in a phone shell. Full Unity player packaging, app-host tool dependencies and durable owner signing remain open. These tools cannot fill missing game code/data. |
| Install, placement, data retention and rollback | No | Android PackageInstaller provides user-mediated installation. Keep stable private owner keys, live capacity/backing checks and interruption handling. Host ADB scripts need on-device equivalents. |

Unity documents [desktop editor hosts][unity-hosts],
[editor AssetBundle builds][unity-bundles] and the
[stripping → IL2CPP → native compilation sequence][unity-il2cpp]. The existing
`LabBuild.cs` invokes BuildAssetBundles and BuildPlayer; RecoveredHudBuilder
uses editor asset APIs. ARM64 instruction-set agreement does not fix an OS/ABI
mismatch: [Android native binaries use ELF][android-abi], while the installed
Unity shader compiler and IL2CPP launcher are Mach-O.

## Tool and redistribution boundaries

Open-source candidates have conditions, not blanket product clearance:
[ILSpy][ilspy], [Cecil][cecil] and [UnityPy][unitypy] use MIT licenses;
[AssetRipper][ripper] uses GPL-3.0. Their licenses cover tools, not extracted
game bytes. Audit pinned versions, combined distributions and native dependencies
before bundling. [Python's Android guide][python-android] describes embedding
Python in an app with platform restrictions.

[Termux's LLVM recipe][termux-llvm] establishes a compiler-port precedent, not
equivalence to Unity's NDK. Installed NDK 21.3.6528147 reports Clang **9.0.8**;
the inspected Termux recipe uses a newer major version. [Google's host table][ndk-hosts]
lists desktop NDK variants. Do not silently replace the compiler or sysroot.

[AOSP aapt2][aapt2], [apksig][apksig] and [R8][r8] provide source-level packaging
paths under their respective licenses. [Termux build-tools][termux-build] covers
aapt2/zipalign, and its [signing recipe][termux-sign] shows a Java host approach.
These do not provide Unity's content or code generation. Termux-specific paths
and [Android executable restrictions][android-exec] also preclude treating its
binaries as automatically usable in any launcher APK. Do not lower security
requirements to claim a port.

Static inspection found managed Unity.IL2CPP/UnityLinker components with
.NET 6.0.18 runtime configuration alongside macOS apphost/CLR libraries. Three
inspected managed assemblies declare no direct P/Invoke rows. This is a tool-hosting
lead. J832/J842 test the converter through the complete authored player closure,
and J846 tests stripping with desktop roots, using a separate Android build-tool
host; wider dependencies, editor-root production,
subprocesses and app sandbox execution remain open.
The build-tool host is separate from the IL2CPP game runtime.

No permission to redistribute Unity editor/compiler components as an Android
tool bundle is established here. Review the applicable [Unity terms][unity-terms]
and exact component grants; owner download access and available runtime source
do not themselves establish redistribution permission. [SDK terms][sdk-terms]
likewise distinguish SDK restrictions from separately licensed open-source
components. Determine the applicable grants before packaging proprietary tools;
this assessment is not legal clearance.

Original/stripped DLLs, generated game C++, global-metadata.dat, game-derived
libil2cpp.so, shader programs and bundles stay owner-generated/private. A
prebuilt game library hidden in a patch/archive/download is not an owner build.
Authorized Android middleware is a separate dependency from PC game ownership;
the current game's audio remains unavailable.

## Blockers and existing debt

The largest technical gates are **editor-equivalent target-content production**
and **complete exact-tool IL2CPP player construction on Android**. No tested end-to-end open Android
replacement for these steps was found. Native compilation and signing precedents
cannot generate missing Unity inputs. Tool rights, Android execution and peak
storage/RAM are independent gates. Component timings are recorded, but complete
phone build-time, peak memory and thermal costs remain unmeasured.

The 47 pinned analysis inputs, 14 inherited-store files and provenance-based
membership are existing [reproducibility debt](execution-backlog.md#structural-cleanup).
They block a public desktop bootstrap too; they do not establish an inherent
platform limit. R9 device passes used workstation inputs. Importing bundles
generated on a desktop or remotely invoking an owner-controlled desktop builder
can improve the fallback experience, but neither is a phone-only build.

## Proof gates

J832/J833 supply precursors for content, converter and packaging work.
The small authored writer now runs on the phone; the fixture's base player still
uses the desktop editor. J842 connects the full authored converter to native
linking and installed loading. Phone-shell execution does not qualify an installer
app's sandbox. Larger content, editor-root production and durable owner key custody
and user-mediated installation remain gates.

1. **Content:** define an independently authored mesh/material/texture/animation/
   script-reference/Vulkan-shader fixture and an exact-editor oracle. Establish
   whether Android tools can produce target data from public source inputs,
   without using the oracle's generated assets as build inputs. Validate actual
   rendering, deserialization, callbacks and unload/reload. A loaded container
   is insufficient. Keep the working project unchanged.
2. **Converter:** preserve J842's authored converter/native/device contract and
   J846/J849's connected stripping contract; qualify editor-root
   production, richer dependencies and permitted acquisition/delivery.
   Report-order/source-comment differences remain explicit.
   No gameplay interpreter is introduced.
3. **Packaging:** package/sign/install an authored fixture with approved Android
   tools. Check native loading/alignment, cancellation, storage, signing and
   data-preserving updates, with a separate explicit fixture identity.
4. After those gates pass, reconstruct one legitimate content slice, then the
   complete accepted input without workstation-history dependencies. Preserve
   the desktop fallback and rollback receipts throughout.

There is no evidence-based completion date for the full phone-only route.
Present bounded results and constraints before choosing its final installation
experience. A failed build-tool gate does not authorize runtime migration.

## Performance gate

Pin Unity/revision/packages, input/transformed assemblies, linker roots/stripping,
IL2CPP options, C++ compiler/linker/sysroot, optimization/LTO/defines/ABI,
Burst/middleware, graphics API, shader bytes/keywords, content hashes and build
mode. The current builder uses Development mode, Low managed stripping and
engine stripping disabled; compare like modes before evaluating release changes.

Inspect real APK/ELF/metadata/payload differences, separating build IDs, paths
and signing from code/content changes. Host equality is not a performance result.
On the same authorized device, compare repeated cold starts and warmed matched
seed/survivor/stage workloads, settings and assist status. Measure frame-time
distributions/stalls, load time, available CPU/GPU evidence, PSS/managed memory,
repeated-session growth and sustained thermals under recorded battery conditions.
Alternate baseline/candidate order and agree regression limits before judging.
Retaining IL2CPP provides no numerical performance guarantee.

Ordinary controls, audio and the full-run gates remain independent. This report
does not advance them or certify a build pipeline ready.

[unity-hosts]: https://docs.unity3d.com/2021.3/Documentation/Manual/system-requirements.html
[unity-bundles]: https://docs.unity3d.com/2021.3/Documentation/Manual/AssetBundles-Building.html
[unity-il2cpp]: https://docs.unity3d.com/2021.3/Documentation/Manual/IL2CPP.html#HowItWorks
[android-abi]: https://developer.android.com/ndk/guides/abis
[ndk-hosts]: https://developer.android.com/ndk/guides/other_build_systems
[ripper]: https://github.com/AssetRipper/AssetRipper
[ilspy]: https://github.com/icsharpcode/ILSpy#license
[cecil]: https://github.com/jbevain/cecil
[unitypy]: https://github.com/K0lb3/UnityPy
[python-android]: https://docs.python.org/3.14/using/android.html
[termux-llvm]: https://github.com/termux/termux-packages/blob/d22cd9f98891a21199faf22dd9cc7ba0f67eedc5/packages/libllvm/build.sh
[termux-sign]: https://github.com/termux/termux-packages/blob/d22cd9f98891a21199faf22dd9cc7ba0f67eedc5/packages/apksigner/build.sh
[termux-build]: https://github.com/termux/android-build-tools#supported-tools
[aapt2]: https://android.googlesource.com/platform/frameworks/base/+/master/tools/aapt2/Main.cpp
[apksig]: https://android.googlesource.com/platform/tools/apksig/+/refs/heads/main/src/main/java/com/android/apksig/ApkSigner.java
[r8]: https://r8.googlesource.com/r8/+/refs/heads/main/LICENSE
[android-exec]: https://developer.android.com/about/versions/10/behavior-changes-10#execute-permission
[unity-terms]: https://unity.com/legal/editor-terms-of-service/software
[sdk-terms]: https://developer.android.com/studio/terms
