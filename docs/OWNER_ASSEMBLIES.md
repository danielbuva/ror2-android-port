# Owner assembly prefix

Current host preparation action: `owner-assembly-prefix` generates the reviewed
DLL/importer subset from legitimate input, the public assembly recipes and the
documented desktop toolchain. It requires no previous Unity project or private
provenance map. The SDK producer remains the default. An explicit public .NET 8
build-tool profile is available; it does not select a different game runtime.
The final installation flow remains research, with the desktop fallback and
IL2CPP ARM64 runtime retained.

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

## Optional public build-tool profile

`public_transform_tools.py` owns the public profile's pinned archive validation,
member extraction, source compilation and two transform modes. It consumes the
three exact archives described in `recipe/owner-public-tools.json` from an
explicit read-only local cache. The repository contains metadata, an authored
provider witness and a Roslyn license notice; it contains no downloaded tool
binaries or Cecil implementation. Compiler/reference packages were signature
verified during profile qualification; each use checks pinned archive/member
hashes. Cecil source also checks Git blob IDs. No upstream build script, package
restore or network request runs in this command.

Download the three public URLs in that recipe into an ignored cache, retaining
the exact filenames. Do not substitute versions or accept hash drift. Native
Python/.NET hosts and their dependencies remain owner-provided. Select exactly
one qualified build-tool host: `host10` (.NET 10.0.12, explicit major roll-forward)
or `android8` (.NET 8.0.32, no roll-forward). The runtime used by the tool and the
generated unsigned Cecil provider are observed at each transform invocation.

```sh
: "${OWNER_INPUT_WORK:?Set the reviewed input work tree}"
: "${OWNER_TOOL_ARCHIVES:?Set the three-archive cache}"
: "${OWNER_DOTNET:?Set the qualified dotnet executable}"
./dev prototype --action owner-assembly-prefix \
  --work-dir "$OWNER_INPUT_WORK" \
  --dest work/rebuild/owner-assembly-public-1 \
  --assembly-profile public-dotnet8 \
  --tool-archives "$OWNER_TOOL_ARCHIVES" \
  --tool-launcher "$OWNER_DOTNET" --tool-host host10
```

This retains the complete accepted-input and DLL/importer output gates. The
attempt includes `public-tools-receipt.json`, extracted notices, compiler logs,
runtime/provider witnesses and failure state. Existing attempts are never
reused. The ordinary SDK producer and R1 still call the existing generator.

For a supplied legitimate Managed directory, the same stdlib-only module also
exposes a portable component CLI, suitable for an isolated Android Python host:

```sh
python3 scripts/lab/public_transform_tools.py \
  --managed "$OWNER_MANAGED" --dest "$OWNER_NEW_COMPONENT_DEST" \
  --archives "$OWNER_TOOL_ARCHIVES" --launcher "$OWNER_DOTNET" --host android8
```

The component destination must be new and under this checkout's `work/rebuild/`.
It produces only the three transformed DLLs. It does not verify a complete
accepted game inventory or emit a Unity project. Source checkout/import, native
host bootstrap, Android app permissions/network policy and the rest of the
player pipeline remain separate gates. All generated outputs stay private.

## Existing knowledge and validation

Pinned ThunderKit's [PackageHelper metadata API](https://github.com/PassivePicasso/ThunderKit/blob/95a6236df08b0e4bbd5350dd4afdb0927cb7fb6a/Editor/Core/Utilities/PackageHelper.cs#L103)
separates metadata emission from assembly processing. The lab retains its audited
GUID and execution-order recipes and existing transform implementation. No
community implementation is copied or installed.

Host contracts live in `tests/test_owner_assemblies.py`; R1 compatibility remains
covered by `tests/test_rebuild.py`. Passing this stage does not establish a full
public-input build, Android behavior or equivalent game performance. See the
[public alpha gates](public-alpha.md) and [phone build assessment](phone-owner-build.md).
