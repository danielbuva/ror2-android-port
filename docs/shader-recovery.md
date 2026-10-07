# Shipped shader recovery — J364

The original PC build is the visual authority. User-supplied gameplay images now provide qualitative targets; they do not identify the exact original draw call, camera, skin, constants or build for every view. Further hand-guessed shader math is suspended. Existing Android replacements remain explicitly approximate.

## Actual recovery results

The accepted original Windows shader bundle was read without modification. Its compressed segments yielded validated DXBC containers:64 for Cloud Intersection Remap,16 for UI Animate Alpha and3,024 across all three Deferred Standard segments. Counts are executable containers, not distinct authored shaders. The generic UnityPy program parser fails on Standard's segmented layout; validated container extraction does not establish full variant/symbol recovery.

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
- It emits variant passes without proving the original keyword-selection behavior. Vertex builtin/per-variant constant-buffer layouts also remain incompletely named.

Next work must recover faithful bindings, widths, comparison semantics and render-state/variant selection from the original records and independent outputs. Preserve disagreements as counterexamples. Standard's segmented table needs its own measured parser correction before using its named output for Commando or terrain. Compare source-program behavior with a legitimate PC RenderDoc/3DMigoto draw capture where available, then compile and run the recovered candidate within the integrated Android game. Do not substitute another guessed lighting model while this route remains available.

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

The first orchestration attempt stopped at the general Unity-build10GiB host guard. At that point the host had about3.7GiB free. This fixed read-only analysis now uses its own100MiB guard and repeats accepted-input checks; Unity builds still require10GiB and remain blocked until headroom is available. The corrected command passed all16 tool invocations, preserving the first rejected attempt and unchanged original bundle.

All game-derived ShaderLab, HLSL, DXBC, IR, SPIR-V, raw trees and PC/Android captures stay ignored. The public repository contains authored orchestration and evidence summaries only. Native IL2CPP/native-engine reconstruction is unnecessary for this shader question; original Mono assemblies and existing passed middleware boundaries remain pinned. [Community prior art](community-prior-art.md) and [visual-restoration evidence](visual-restoration.md) retain the broader context.
