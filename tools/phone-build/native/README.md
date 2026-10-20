# Authored IL2CPP native build replay

Current experimental support for the existing content fixture only. This
compiles the supplied, unmodified IL2CPP runtime and generated fixture C++;
it implements no runtime and changes no game build.

```sh
./dev prototype --action phone-native-fixture --target REQUEST.json
python3 -I -S phone_native.py STAGE OWNED_TOOL_ROOT NEW_OUTPUT [REUSE.json]
```

The ignored host request selects `project`, `apk` and `sha256` for the committed
authored fixture. Its native Bee graph, managed stripping, generated C++/metadata,
base player/data and supplied Unity inputs still originate on the desktop.
These dependencies stay explicit. The stage generator reads no game source and
refuses other input roots, shell command composition, output traversal and
unknown lump directives. It copies underlying inputs unchanged and generates
fresh relative-include wrappers in the original include order. It never edits
authored/runtime sources by text replacement.

The Android driver verifies the entire staged input manifest and replays each
compile followed by the link. It preserves target/optimization/ABI defines and
the original NDK target sysroot/C++ libraries and supplied Baselib archive.
The Android-host Clang 21 and LLD differ from the recorded desktop Clang 9/BFD;
their arguments and changes are recorded. Those differences require validation
and eventual performance measurement, even though IL2CPP remains the runtime.
The retained source graph is private tool metadata, not a new public recipe.

Outputs and command logs are separate per attempt, with failure evidence
preserved. A linked ELF alone does not qualify Unity loading, rendering,
metadata identity, content lifecycle, a full phone build or game performance.
Any subsequent fixture packaging/install must bind its exact metadata/base APK
and native library, use private signing, fresh selected-device capacity/storage
and ownership-checked cleanup. No Unity/tool redistribution grant is inferred.

The explicit optional reuse request binds prior stage/output paths, the exact
prior result hash and every object hash. Reuse requires the same compile plan,
source/target manifest and actual recorded compiler arguments. Only driver/plan
metadata and the added original NDK GCC link archive may differ. A link-only
repair copies proven objects into a new attempt; it preserves the failed link
and avoids recompiling unchanged code. The linker uses explicit original static
C++/ABI/GCC archives rather than the host compiler's implicit library choices.

References: Android's [external build-system guide](https://developer.android.com/ndk/guides/other_build_systems)
and [C++ runtime selection](https://developer.android.com/ndk/guides/cpp-support).

Native replacement is separate packaging support:

```sh
./dev prototype --action phone-native-apk-fixture --target REQUEST.json
python3 -I -S phone_native_apk.py BASE.apk LIBRARY.so NEW_UNSIGNED.apk \
  --version-code 3 --apk-sha256 HASH --library-sha256 HASH --metadata-sha256 HASH
```

Keep `phone_native_apk.py` beside `phone_apk.py` for the standalone Android
command. The ignored host request supplies `apk`, `apk_sha256`, `library`,
`library_sha256`, `metadata_sha256` and `version_code`. The writer accepts only
the authored fixture identity and an ARM64 shared-library header, refuses hash
or metadata drift and overwrites, preserves other bytes/notices and removes old
signatures. Header checks do not establish complete ELF/ABI validity. Independently
inspect dependencies, SONAME and exported APIs, then align/sign and test the
actual installed/mapped library with `phone-package-check`. Raw unstripped ELF
outputs remain private and are not a production size/performance qualification.
