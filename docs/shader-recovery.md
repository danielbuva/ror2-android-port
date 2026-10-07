# Shipped shader recovery — J364–J366

The original PC build is the visual authority. User-supplied gameplay images now provide qualitative targets; they do not identify the exact original draw call, camera, skin, constants or build for every view. Further hand-guessed shader math is suspended. Existing Android replacements remain explicitly approximate.

## Actual recovery results

The accepted original Windows shader bundle was read without modification. Its compressed segments yielded validated DXBC containers:64 for Cloud Intersection Remap,16 for UI Animate Alpha and3,024 across all three Deferred Standard segments. Counts are executable containers, not distinct authored shaders. J365 resolves the generic parser's segment-index failure with an authored strict reader. Standard has3,514 native records:3,024 executable programs and490 parameter records. Its first segment contains only the index table; records reside in the other two. Rebased private tool input preserves every record's exact bytes/hash/index; the source bundle is unchanged.

Unity_Shader_Decompiler emitted named ShaderLab/HLSL-like outputs for Cloud Intersection and UI Animate Alpha, with64 and16 collected executable functions respectively. Schema normalization only adds the tool's expected field aliases/dictionaries and converts integral JSON numbers to integers; native numerical values and the original tree are retained. Non-executable parameter records are distinct from DXBC programs. The tool's nominal Unity2022.3 parser is only measured against these2021.3 blobs, not accepted as universally compatible.

All four requested recovery tools then processed the **same** non-stereo, non-instanced Cloud Intersection vertex/fragment pair. Original matTeleporterRangeIndicator enables TRIPLANAR; the selected programs also use DIRECTIONAL and LIGHTPROBE_SH. An actual PC draw has not established whether it selects this exact variant.

| Original program | Identity | SHA-256 |
| --- | --- | --- |
| Vertex | Unity subprogram6, GPU type15 | `38a6f95f6e28ab0d80140920ee6595e5557c4b022508fede837f4127d0379104` |
| Fragment | Unity subprogram40, GPU type17 | `4e2899892aa69ebc9c7eafa0b0e781bf7c4632b714d6c1aedf2b7817201e0a2c` |

d3dasm emits structured HLSL and assembly; reassembling both programs produces byte-identical DXBC. HLSLDecompiler independently emits register-based HLSL; its actual D3DCompile validation succeeds for both outputs through an isolated local analysis bottle. dxbc-spirv emits disassembly, conversion IR, lowered IR and SPIR-V for both programs. These are real executions, not inferred upstream capabilities.

Byte-identical assembly roundtrip tests the bytecode representation. HLSL compilation tests compilability. Neither proves HLSL semantic equivalence. SPIR-V output still needs Unity/application resource and I/O integration and Android execution; it is not a drop-in Android shader. No shader-capability or visual-parity checkpoint advances.

## Concrete reconstruction errors

The named Unity output must **not** be imported directly into the accepted game:

- It binds the fragment's native depth sample to the remap texture, leaving the actual ramp sample anonymous. Original metadata distinguishes depth texture register3/sampler4 from remap register4/sampler3.
- It widens native three-component dot products using duplicated vector lanes. This changes normal transformation/normalization.
- It loses the all-bits-set comparison/integer-cast distinction used to determine sign. The resulting rim expression differs from native instructions. d3dasm and HLSLDecompiler agree on those relevant register-level operations; dxbc-spirv IR retains their types and widths. This agreement is evidence, not a formal equivalence proof.
- It emits default numeric blend/cull values instead of retaining their property-linked source state. Material-controlled values cannot be replaced by those defaults.
- It emits variant passes without proving the original keyword-selection behavior. J365 subsequently recovers selected native per-variant parameter records and builtin layouts; these are measured bindings, not a repair of the named tool's executable math.

Next work must recover faithful bindings, widths, comparison semantics and render-state/variant selection from the original records and independent outputs. Preserve disagreements as counterexamples. Standard's segmented table is now decoded, but its Deferred pass still needs faithful resource/pipeline integration before it can replace the current forward-rendered Commando or terrain. Compare source-program behavior with a legitimate PC RenderDoc/3DMigoto draw capture where available, then compile and run the recovered candidate within the integrated Android game. Do not substitute another guessed lighting model while this route remains available.

## Pinned tools and local prerequisites

| Tool | Pinned upstream revision | Measured limitation |
| --- | --- | --- |
| [Unity_Shader_Decompiler](https://github.com/Abby1591/Unity_Shader_Decompiler/tree/1ce3a1c47609f8574e091b30e8425d528f2b457c) | `1ce3a1c47609f8574e091b30e8425d528f2b457c` | No license found at the inspected revision; local analysis only, no upstream implementation vendored or redistributed. Named output has the errors above. |
| [d3dasm](https://github.com/coconutbird/d3dasm/tree/a292206a15daf0723d945a475c6254413eda8551) | `a292206a15daf0723d945a475c6254413eda8551` | MIT; needs matching cfglib API, not its latest checkout. |
| [cfglib](https://github.com/napbat/cfglib/tree/6e57c166403e80e81a0f51e01aebf5ed47267784) | `6e57c166403e80e81a0f51e01aebf5ed47267784` | MIT; latest removed the StructuredWalk/Edge/Sink/Issue API required by this d3dasm revision. |
| [HLSLDecompiler](https://github.com/javelinlinV2/HLSLDecompiler/tree/bc9b39dba5a3ae27e54ea6b3980bd1fac6f4061a) | `bc9b39dba5a3ae27e54ea6b3980bd1fac6f4061a` | MIT; Windows utility executes locally through existing CrossOver. `-V` verifies recompilation, not semantics. |
| [dxbc-spirv](https://github.com/doitsujin/dxbc-spirv/tree/c7f069701227dcb800a01bd93e42f8001b7543e7) | `c7f069701227dcb800a01bd93e42f8001b7543e7` | MIT; application-specific lowering still required. SPIRV-Headers submodule `c8ad050fcb29e42a2f57d9f59e97488f465c436d`. |

The private reference checkouts are `work/reference-repos/Abby1591__Unity_Shader_Decompiler`, `coconutbird__d3dasm`, `javelinlinV2__HLSLDecompiler` and `doitsujin__dxbc-spirv`; cfglib is under `work/napbat/cfglib`. The Unity tool is built with the existing .NET10.0.401 SDK; d3dasm uses the ignored Rust1.99.0 toolchain. dxbc-spirv's tools are built with Meson and its pinned submodule. The separate `shader-recovery` CrossOver bottle lives only in `work/toolchains/crossover-bottles`. No original Steam bottle or device app is changed by this analysis.

`./dev prototype --action shader-recovery` requires these already built tools. It does not download/install tools, modify upstream source, patch the accepted Unity project or install anything on Nova. It verifies accepted input metadata and the source bundle hash, exact tool revisions/unchanged tracked source, DXBC boundaries, Stage0 blob equality, named output presence, lossless assembly, HLSL validation and SPIR-V headers. Every attempt retains private command outputs, generated programs, tool/output hashes and a terminal receipt under ignored `work/experiments/shader-recovery/`; the current local pointer is `work/shader-recovery-current.json`.

The first J364 orchestration attempt stopped at the general Unity-build10GiB host guard. At that point the host had about3.7GiB free. This fixed read-only analysis now uses its own100MiB guard and repeats accepted-input checks; Unity builds still require10GiB. J365 regained about12GiB through68 hash-verified APFS clone replacements of redundant private archive files; evidence paths/bytes, modes and timestamps are retained, with independent inodes. Only fixed owned archive/payload paths were eligible. Fresh general preflight then passed; headroom remains a live measurement. The corrected command passed all16 tool invocations, preserving the first rejected attempt and unchanged original bundle.

All game-derived ShaderLab, HLSL, DXBC, IR, SPIR-V, raw trees and PC/Android captures stay ignored. The public repository contains authored orchestration and evidence summaries only. Native IL2CPP/native-engine reconstruction is unnecessary for this shader question; original Mono assemblies and existing passed middleware boundaries remain pinned. [Community prior art](community-prior-art.md) and [visual-restoration evidence](visual-restoration.md) retain the broader context.

## J365 — Standard segmentation, parameter records and independent failure

`./dev prototype --action shader-recovery --target standard` selects the original non-stereo/non-instanced DEFERRED vertex249/fragment1473 with measured Commando material keywords DITHER/LIGHTPROBE_SH/LIMBREMOVAL. No live PC draw identifies the actual selected variant. Every original executable program is retained in the named output:3,024 collected functions. The initial named-tool temporary-fusion pass throws NullReferenceException; its supported `--no-fuse-temps` option completes recovery without changing the shipped programs.

Both selected Standard programs round-trip to byte-identical DXBC through d3dasm. Both complete dxbc-spirv conversion/lowering/SPIR-V. Independent HLSLDecompiler validates the vertex, but its fragment output fails D3DCompile: a two-lane dithering conversion is emitted as a uint3 cast. The unvalidated emitted output is preserved alongside the compiler error, native assembly, other HLSL and typed IR. The revised orchestration finishes independent analysis after this validation failure, then reports failure truthfully. It never drops DITHER or reports semantic equivalence. The independent utility's output is evidence, not trusted source.

Native parameter records recover exact buffer sizes/slots, constant names/offsets/shapes and texture/sampler bindings, including Unity builtin matrices. The Standard fragment's per-variant elite-ramp binding is absent from common metadata. Its opaque native descriptor is retained; dimension remains unresolved until corroborated by the DXBC declaration. Unknown structures, trailing bytes, dynamic constant accesses and consumed unbound lanes fail closed.

## J366 — Generated intersection candidate in the composed game

`./dev prototype --action shader-source` requires an explicitly selected successful private Cloud analysis in `work/config/shader-source-analysis.json`. The public generator contains resource-binding machinery only. Generated properties, expressions, ShaderLab and native programs remain ignored. It reads measured native buffers, uses original matrix columns, retains native texture/sampler pairing and emits the original float32 expressions from pinned d3dasm. Four material feature combinations preserve triplanar and vertex-color-fade behavior without relying on keywords cleared by the existing Android material adapter. Scope is mono/non-instanced ForwardBase; instancing/stereo and exact live-PC variant selection remain open.

Property defaults come directly from the original tree, including grey texture defaults that the named tool incorrectly prints as empty. Source material-controlled blend and cull properties are retained. Unity source compilation initially rejects partially written float4 output parameters. Zero initialization now precedes original writes, retaining native written lanes; undefined lanes are not evidence of source behavior.

`./dev prototype --action recovered-presentation-payload` stages this one generated shader into the existing nine-shader presentation bundle. It archives the prior selected build, shader sources and presentation payload, checks actual serialized editor completion/ShaderUtil errors and retains the APK and all other payload hashes. No derived math enters tracked files. Android compilation succeeds after the output-initialization correction. Runtime and visual acceptance are recorded below after the combined run; compilation alone does not advance them.

The recovered project records linear color space while the current lab uses gamma. This is a concrete host-observed configuration difference, not a new PC-frame capture or proof that changing it alone restores appearance. Current Standard lighting/materials, opaque cloud effects, Commando pose/palette and other families remain approximations or unresolved. Do not tune them into a new aesthetic.


J366 actual run:412.611seconds/68kills/four original exits into Sky Meadow/182 HUD checks,52 intersection bindings selecting the hash-verified payload, nine current-PID capture unions with zero errors/named Timeline warnings and full scoped cleanup. Only android-presentation-lab transfers; APK and exact four Android results retained, no installation/OLED asleep. Invincibility/high damage/fast charge ON, movement/jump OFF. Reviewed captures still fail broader PC appearance; exact GPU draw/semantic/visual parity is not established.62 authored safety/binding tests pass. Prior approximate source/payload remains in the accepted build's private previous directory.


J367 restores the original settings binary's linear color setting and explicitly binds original intersection keyword choices. Broader325-material audit exposes125 numeric-toggle disagreements;38 staged source materials already agree and their real Unity clone assertions pass. Combined updated-APK route completes four original exits in408.324seconds/65kills/179HUD checks with52 matching bindings/zero PID errors/full cleanup/results retained/OLED asleep.62 tests and208.116-second zero-error full build pass; six authored scenes/45 accepted assembly identities retained. Assisted run, no normal/visual/semantic/PC-draw or Moon acceptance. Darker chest captures are different views; snow/sky/cards/pose/palette/Standard deferred still unresolved. Previous APK/payload/source rollbacks preserved. Direct runtime activeColorSpace value remains unobserved; exact configuration and source hash are established.
