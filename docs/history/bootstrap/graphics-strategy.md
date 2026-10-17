# Graphics laboratory strategy

Preserve the built-in pipeline initially. Retarget a small representative geometry/material family at a time; replacing the whole renderer before measuring startup is not justified. Use the exact Unity editor to compile Android shaders and bundles. Dummy AssetRipper output is geometry/serialization scaffolding only.

| Family | Initial classification | Proof needed |
| --- | --- | --- |
| Unity built-in shaders supplied by exact editor | REBUILDABLE | Compile device variants and compare material properties. |
| Hopoo deferred Standard / terrain / snow / cloth | REPLACEMENT REQUIRED initially | Recover or translate programs, reconstruct property semantics, compare captures. D3D bytecode translation is EXPERIMENTAL. |
| Custom water / vegetation / decals | TRANSLATABLE hypothesis | Depth, normals, stencil and deformation behavior under Android API. |
| Particle cloud remap / distortion / trails | REPLACEMENT REQUIRED initially | Readability first, then blending/depth/soft-particle parity. |
| Postprocessing / SSR / compute | OPTIONAL FOR MVP | A representative compute dispatch and resource-format compatibility before enabling. |
| UI / damage numbers / outline | REBUILDABLE or replacement | Legibility and state cues before visual parity. |
| Reconstructed dummy shaders | REPLACEMENT REQUIRED | 1,333/1,333 stub markers; never label them original source. |

Machine manifest: `work/inventory/shader-manifest.json` retains observed source availability and platforms. Its TRANSLATABLE entries mark experiments, not successful conversion. No original shader source was found in the scanned records.

| Gate | Required real-device evidence |
| --- | --- |
| G0 | Process survives; package and ABI verified. |
| G1 | Unity renders a visible diagnostic/reference scene. |
| G2 | RoR2-derived mesh visibly renders from an independently synced Android bundle. |
| G3 | Representative characters/material families recognizable. |
| G4 | Actual gameplay readable; magenta/nonessential effects may remain. |
| G5 | Particles, terrain, decals, instancing and postprocessing broadly correct. |
| G6 | Visual parity, frame pacing, thermals and memory measured under a reproducible run. |

The lab explicitly selects GLES3 or Vulkan through `./dev build --target gles|vulkan`. There is no silent API fallback in these comparison builds. Runtime snapshot reports actual API/GPU. A small original Windows shader bundle is a negative portability probe; loading its container does not establish shader support. No custom Turnip loader is included.
