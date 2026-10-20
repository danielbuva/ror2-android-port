# Isolated phone build probes

These authored fixtures test build stages for ADR-002. They read no game files
and do not change the working Android project. Generated outputs, supplied
Unity tools, dependency archives, signing material and raw evidence stay ignored.
This is experimental tooling, not a supported phone installer.

`host/` is a separate current experimental app-sandbox fixture. Its Android
driver compiles authored C/Java, packages DEX/resources and aligns/signs an APK
on the phone using explicit supplied tool roots and owner SDK inputs. It
refuses an existing output directory and retains the first failing stage.
`HostProbeActivity` compares a PackageManager-installed immutable native
executable against the identical bytes copied to writable app storage, under
target API 30. It uses public APIs and expects writable execution to be refused.
This tests neither an interpreter host nor the game. See `host/README.md` for
inputs and invocation.

`ConverterFixture.cs` supplies a small arithmetic assembly for the exact local
IL2CPP converter. A build-tool .NET host is independent of the game's native
IL2CPP runtime. Compare all generated C++ and metadata against the desktop
baseline. A shell test does not qualify an app sandbox or a complete player.

```sh
./dev prototype --action phone-content-fixture
./dev prototype --action phone-content-check --target <generated-project>
./dev prototype --action phone-content-build --target <generated-project>
```

The generator constructs a UnityFS archive and Android serialized file from
authored values and versioned native wire schemas using Python's standard
library. It reads no class database, editor output or game-derived template.
The two types are AssetBundle and TextAsset. UnityPy supplies an independent
host parser, not a dependency of the standalone writer. Run the same writer
on Android with `python3 -I -S phone_bundle.py NEW_OUTPUT.bundle`.
Each generated project binds source and bundle hashes. Staging refuses an
existing attempt, checks reject source drift, and builds require committed
fixture sources. The runner locates the primary checkout through Git's common
directory and acquires its existing persistent build mutex. A contended lock
refuses promptly. No existing editor is stopped or reused.

The exact-editor check independently loads the bundle, reads the expected
TextAsset and verifies its destruction on unload. The separate player uses
`dev.ror2lab.phonecontentfixture`, ARM64 IL2CPP and Vulkan. It copies the bundle
from StreamingAssets, or reads `phone-candidate.bundle` from its own persistent
data directory when `phone-fixture-selection.json` supplies the exact `sha256`.
A mismatch refuses; no arbitrary input path is accepted. It checks two native
load/unload cycles and writes `phone-content-report.json` with the actual hash
and source selection. Before installation, require explicit alpha device
selection, fresh capacity/storage checks and package absence. Retain ownership,
actual APK hash, package placement and runtime data backing. Remove only the
owned disposable fixture and put the display to sleep.

Both editor entry points require the pinned version; each launch writes a fresh
oracle report whose actual Unity version and content checks are required by the
launcher even after exit code zero. The player publishes Android's actual
private/external files directories and Unity's persistent directory in its own
private bootstrap report. The device checker canonicalizes and binds these
observations before selecting report/candidate paths, checks private backing
against freshly selected storage and records the separate runtime backing.

This tiny contract establishes no mesh, texture, material, animation, script
binding, shader compilation, catalog, game or performance acceptance. The larger
fixture and owner-build gates remain in
[phone-owner-build.md](../../docs/phone-owner-build.md).

Packaging support is a separate probe:

```sh
./dev prototype --action phone-apk-fixture --target work/config/phone-fixture-request.json
python3 -I -S phone_apk.py BASE.apk CANDIDATE.bundle NEW_UNSIGNED.apk --version-code 3
```

The host request supplies `apk`, `apk_sha256`, `bundle`, `bundle_sha256` and
`version_code`. Inputs stay under ignored `work/`. The standalone command takes
the same explicit artifacts on Android. It accepts only the content fixture
package, requires an increasing version code and never overwrites an input or
earlier output. Other ZIP entry bytes remain unchanged; previous signatures are
removed. Follow with Android-host zipalign, private owner signing, independent
signature/alignment verification and owned-package installation/update checks.
Retain signing keys locally. This is repackaging of an explicit desktop-built
fixture player, not a complete phone build from public source.
