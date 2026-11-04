# ADR-003 — Measured lighting tolerance

Status: accepted policy (user decision 2026-10-31); validator shipped 2026-11-04.
No real lighting record has yet completed numerical **and** visual admission.
Architecture C, the J850 compatibility reference and ownership boundaries remain.

The exception covers GPU floating-point or sampling differences in reflection
and ambient probes, lightmaps and their lighting containers. It does not cover
other textures, materials, shaders, geometry, code, serialized relationships or
input drift. Existing build-identity and generated-metadata policies are separate.
Raw-exact, drift-explained and tolerance-accepted are distinct results.

## Deriving a bound

Use one reusable source-derived producer with legitimate original/SDK/public
inputs. J850 is a private qualification reference, never a production input.
Compare matching records by member, path ID, native type/schema, dimensions,
format, face, mip, texel and channel (or probe/coefficient). Reject missing data,
layout differences and nonfinite values before calculating errors.

For each record and channel, measure the maximum absolute difference over **all**
matching samples against J850. Retain the sample count, maxima, distribution,
producer/input hashes and numerical evidence locally. Repeat only as required to
establish the observed GPU/sampling variation. Freeze the smallest practical
per-channel envelope covering those measured differences in a reviewed recipe;
use representable units for integer texels. Explain any outward rounding with
its measured precision. Do not choose a blanket epsilon, infer bounds from a
similar scene, or widen a bound merely to admit a new candidate. A changed
producer/input/schema needs a new measured review; changed original content
belongs to drift analysis.

The validator computes `abs(candidate - reference)` for every sample and accepts
only `maximum <= max_abs[channel]`. There is no hidden relative epsilon, average
error allowance or percentile exemption. Coefficient channel order follows the
native serialized order (27 bounds, one per coefficient); texture channel order follows
the native format. Every sample must be finite even when its bytes match.

## Numerical and visual admission

`tools/phone-build/accepted-output/scene_compare.py` extends the existing
`unity_write.py` serialized-v22 qualification owner. Its `compare_member` entry
point can be called by full-scene qualification; `qualify` checks all members of
a UnityFS scene or one standalone serialized file. The recipe pins the complete
reference file and selects records and native field paths, never arbitrary byte
ranges. Embedded native schemas determine the sample extents. It requires:

- Identical native/script types, identities, object tables/layout, external
  references, metadata and every byte outside selected lighting sample fields.
- RenderSettings (104) `m_AmbientProbe`, or LightProbes (258)
  `m_BakedCoefficients`, as complete 27-float probes.
- Cubemap (89) inline `image data` with an actual local RenderSettings (104) or
  ReflectionProbe (215) reflection pointer to that record. A Texture2D (28) must
  instead have an actual local LightmapSettings (157) `m_Lightmaps` pointer.
  Unbound textures and cubemaps do not qualify by class alone.
- Complete inline RGB24, RGBA32, RGBAHalf or RGBAFloat texels with exact format,
  dimensions, mip layout, array lengths and all storage/reference fields.
- Exact unselected bundle members and decompressed padding. Container directory,
  native framing, block boundaries/flags, versions and checksum field stay exact;
  compressed payloads and their derived lengths may change with sample bytes.

Container class membership never exempts a whole body. LightmapSettings,
ReflectionProbe and other containers with no supported sample field stay exact.
Missing schemas, compressed/streamed texel changes, external lightmap/probe links
and unsupported encodings remain blocked; extending decoding requires its own
measured contract. This deliberately admits less than the policy's full scope.

Review matched captures against J850 with the same camera, scene, lighting,
exposure, output transfer function and render settings. Cover each affected
probe/lightmap region, reflection faces/mips and relevant viewing angles; inspect
both the rendered result and amplified difference images for seams, banding,
clipping and changed illumination. Retain captures/settings and a concise review
locally. Numerical success alone cannot supply visual parity. A reviewed visual
document must pin both complete file hashes, set `parity: true`, and explain the
matched comparison in `review`; it attests human review, not automated vision.

APK readiness's optional `lighting_tolerance` selection pins the recipe, visual
review and private reference. It reruns numerical comparison on the actual
supplier and retains measured maxima. Assembly rechecks all evidence hashes and
preserves the admitted candidate's actual bytes/hashes. `tolerance_accepted_count`
counts final files, not records, separately from `exact_count` and
`drift_explained_count`; `target_equal` remains false. Provenance and device
qualification remain separate gates. See the [request contract](../tools/phone-build/owner-apk/README.md#lighting-tolerance).

## Evidence and consequences

J1261/J1269 identify lighting-only source alternatives. J1266 measures ambient
error up to 0.000162162 against a desktop **source** reference, not J850; it does
not establish an admitted bound. Pinned AssetRipper `813fed1597`'s
`LightmapSettingsExtensions.cs` shows that editor-format conversion can reset
lighting settings; preserve native fields rather than normalize them. Pinned
UnityPy 1.25.3 `ObjectReader` identifies class/type IDs and byte extents; the
existing bounded readers reuse that format knowledge. Neither supplies tolerance
numbers. The private full-scene comparison technique checks every record and
preserves probe pointers; no community/game implementation is copied here.

Host fixtures cover exact/bounded/over-bound results, class and field scope,
lightmap/reflection relationships, non-lighting bytes, numerical finiteness,
visual pins and independent readiness counts. They establish the validator's
contract, not visual/game readiness. Current readiness remains 693/705 available,
685 raw-exact, **0 tolerance-accepted**. Prefer the same reusable producer on all
phones; per-device GPU recomputation needs measured benefit before adoption.
