# Original PC appearance on Android

The legitimate PC build is the visual authority. Matching PC captures, source scene settings and source material parameters govern restoration. Android replacements remain explicitly approximate. None of J324–J326 establishes shader or whole-scene parity.

## Current restoration

The integrated world uses owned copies of recovered materials. Five authored Android shaders cover surfaces, RGB triplanar terrain, cloud particles, water and a camera pass. The source texture, normal, emission, tint, cutout, snow, blend and relevant fade/rim parameters are retained where supported. Terrain weighting, normal/specular response, water and clouds are approximations, not recovered shader source. Native simulation, asset identities and existing Moon beam shaders are unchanged.

J324's enhanced/legacy/enhanced same-view toggle captures show material detail changes, but were not PC comparisons. They exposed unmeasured grading and overly broad additive effects. J325 removes invented contrast/saturation/vignette, masks additive RGB with alpha and uses the source Fresnel toggle/power. Its identity camera pass does no grading. A reviewed teleporter capture shows the broad red overlay reduced to a readable rim; it does not prove the original effect.

J326 restores the five base scenes' original RenderSettings and native lights that geometry reduction discarded. Source fog enable/mode/color/range, ambient values, sun/sky references, light transforms/intensities and active flags are preserved. Counts are 12/10/61/110/32 source lights across golemplains/foggyswamp/frozenwall/dampcavesimple/skymeadow. Gameplay callbacks and Moon scene content are unchanged. The same-APK device window passes508.13seconds/four genuine transports/zero errors and cleanup; reviewed captures remain approximate, with sky camera still pending. See the journal for attribution and performance limits.

Four recovered stage sky materials use Unity's built-in cubemap shader. The prepared camera change retains their cubemap, tint, exposure and rotation and suppresses the diagnostic directional light when source directional lighting exists. The dampcavesimple sky reference resolves to a terrain material; this is an unresolved source/export discrepancy, not a reason to invent a sky. J327 compiles/builds this camera change in a host-only Vulkan APK with zero errors; it is not present in the sole installed J324 APK until an authorized update.

## Comparison and remaining gaps

No matching local PC screenshots were found. A usable original PC capture environment is currently unavailable; no licensing or authentication workaround was attempted. Matching PC captures remain necessary for acceptance. Source-data restoration and Android screenshots alone cannot demonstrate parity.

The installed APK still clears the sky to a diagnostic solid color. Exact cloud/soft-particle/distortion behavior, water reflection/refraction, baked lighting/probes, shadows, stylized outlines and stock postprocessing remain unresolved. Some material families share a fallback despite different original rendering contracts. Do not call these restored or substitute an invented look.

For each visual change retain source identities/parameters, shader and APK/payload hashes, stage/object/view context and private Android/PC captures where available. Identify the comparison as source-data, legacy/approximation, or matching PC. Compare silhouettes, surface response, fog/color, effect shape/opacity and hazard/objective readability separately. Only matching PC evidence may support an appearance-parity claim.

## Prior art and provenance

Consulted the pinned R2Wiki HG Triplanar Terrain Blend guide for RGB/top/side/vertex-color/signed-bias and normal/specular contracts, EditorKit HopooCloudRemapGUI for original blend-property metadata, and Starstorm2 SlateMines/R2API.Director for scene identity/lifecycle distinctions. See [community source map](community-prior-art.md) and its pinned source index. These describe contracts; they do not supply the original shader programs. No community, game or shader implementation was copied into the public source. Recovered assets and raw comparisons remain ignored locally.
