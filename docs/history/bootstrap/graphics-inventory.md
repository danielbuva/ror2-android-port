# Graphics evidence

VERIFIED: built-in pipeline. Serialized GraphicsSettings.m_CustomRenderPipeline is null; all three tier rendering paths are 3 (deferred shading), linear color space is selected, and deferred/reflection/screen-space-shadow shaders are customized. Individual camera overrides still require scene/runtime inspection.

VERIFIED: scanned shaders contain platform **4 (D3D11)** programs; original ShaderLab/HLSL source is absent in the inspected shader records. BuildSettings graphics API value 2 denotes Direct3D11. The 1,472 Addressables bundles contain Windows-target serialized files. UnityFS signatures alone would not prove platform; serialized metadata and shader program arrays supply that evidence.

The complete scan records 1,425 shader objects, 6,950 materials, 11,240 meshes, 600 compute-shader objects, 18,619 particle systems, 10 terrain objects and 15 projectors. Counts include duplicated assets across bundles, not unique authored content. AssetRipper exported 1,333 `.shader` files; **all 1,333 contain dummy/stub exporter markers**. Syntactically valid HLSL in those files is not recovered game shader logic.

Hopoo families include deferred Standard, Snow Topped, Triplanar Terrain Blend, Wavy Cloth; water/grass/flags; cloud remap/distortion/particles; postprocessing, UI, outlines and optimized Switch variants. A shader name containing Switch is not proof of a Switch or Android program: its stored platform is still D3D11.

Evidence: `graphics.json` (settings, shader/material links, bundle containers/dependencies, mesh names), `shader-manifest.json`, `reconstruction.json`. Cross-file material references are retained as file/path IDs and not claimed resolved globally. Missing serialized references need a separate GUID/PPtr audit after import; merely listing material shader IDs is insufficient.

The reconstructed loadingbasic scene probe reports 64 objects, zero missing-script components and zero null material slots. Stub shaders report supported in this editor scene; that does not imply shader fidelity. Import emitted compute-shader failures. Global YAML external-GUID audit reports 173 unresolved GUIDs; refer to serialized-references.json for scope and examples.
