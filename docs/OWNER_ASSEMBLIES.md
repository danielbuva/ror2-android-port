# Owner assembly prefix

Current host preparation action: `owner-assembly-prefix` generates the reviewed
DLL/importer subset from legitimate input, the public assembly recipes and the
documented desktop toolchain. It requires no previous Unity project or private
provenance map. Phone execution and the final installation flow remain research;
the desktop fallback and IL2CPP ARM64 runtime remain authoritative.

This is an initial subset of a project. Content, shaders, packages, native usage,
linker roots and the rest of project composition still need their own producers
and acceptance. The ordinary build and R1 comparison gates retain their existing
contracts. No current-build pointer, lab generation marker or installation is
created by this action.

## Run from an isolated checkout

Prepare the [documented toolchain and reviewed installation](DEVELOPING.md#local-setup).
The selected input work tree must contain `config/local.json`,
`config/accepted-input.json` and `inventory/files.json`; the installation must
still match its inventory. Input and recipe identities must agree. The existing
transform producer uses the owner's pinned Unity Mono.Cecil and .NET toolchain;
this action bundles no SDK or game binaries.

Set `OWNER_INPUT_WORK` to that reviewed local work tree. Choose a new destination
beneath this checkout's ignored `work/rebuild/`:

```sh
: "${OWNER_INPUT_WORK:?Set the reviewed input work tree}"
./dev prototype --action owner-assembly-prefix \
  --work-dir "$OWNER_INPUT_WORK" \
  --dest work/rebuild/owner-assembly-prefix-1
```

The action checks inventory identity/current source stats, recipe membership,
original DLL hashes, transform source/output pins and the existing 10 GiB host
reserve. Every output must match the public DLL hash or authored importer
contract before project files are written. Inputs and generator sources are
rechecked after generation; output hashes are read back.

## Outputs and failure handling

`owner_assemblies.py` owns setup, exclusive destination creation and the receipt's
`preparing` → `complete` or `failed` lifecycle. It reuses `rebuild.assembly_payload`,
`assembly_transforms.generate` and the existing importer template. Under the new
destination:

- `project/` contains only the selected DLLs and their `.meta` files.
- `attempt/` preserves the isolated transform inputs, tool build and intermediates.
- `manifest.json` binds the completed output paths, sizes and SHA-256 hashes.
- `receipt.json` records input/recipe/source hashes, commit, uncommitted-source
  status, progress and first failure. Complete-project, phone-build and runtime
  qualifications remain explicitly false.

An existing destination, redirected/protected path, unknown input, source drift
or output mismatch refuses. Failed attempts remain for inspection; choose a new
destination after resolving the first failure. Keep all outputs and raw receipts
private. No process state persists after exit, and no editor or device is used.

## Existing knowledge and validation

Pinned ThunderKit's [PackageHelper metadata API](https://github.com/PassivePicasso/ThunderKit/blob/95a6236df08b0e4bbd5350dd4afdb0927cb7fb6a/Editor/Core/Utilities/PackageHelper.cs#L103)
separates metadata emission from assembly processing. The lab retains its audited
GUID and execution-order recipes and existing transform implementation. No
community implementation is copied or installed.

Host contracts live in `tests/test_owner_assemblies.py`; R1 compatibility remains
covered by `tests/test_rebuild.py`. Passing this stage does not establish a full
public-input build, Android behavior or equivalent game performance. See the
[public alpha gates](public-alpha.md) and [phone build assessment](phone-owner-build.md).
