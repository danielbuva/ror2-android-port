# Public Unity Crunch decompression headers

Unchanged `inc/crn_decomp.h`, `inc/crn_defs.h`, `inc/crnlib.h` and root
`license.txt` from [Unity-Technologies/crunch](https://github.com/Unity-Technologies/crunch/tree/8708900eca8ec609d279270e72936258f81ddfb7),
commit `8708900eca8ec609d279270e72936258f81ddfb7`, branch `unity`.
This is the public original submodule selected by
[AssetRipper.Conversions.UnityCrunch 1.0.3](https://github.com/AssetRipper/AssetRipper.Conversions.UnityCrunch/tree/1.0.3).
The complete upstream Zlib notice is retained in LICENSE and the headers.

Only decompression headers are distributed here; no SDK implementation,
compressed image, original game bytes or generated texture is included.
The authored bounded adapter and platform compatibility header are separate.
The builder verifies the exact unchanged header/license hashes before output
creation and records them before/after compilation.
