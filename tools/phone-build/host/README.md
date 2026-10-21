# Authored app-sandbox host probe

Current experimental support, independent of Unity and the game build.

Stage these four authored sources with owner-supplied `android.jar` (API 30),
`d8.jar` (build tools 34.0.0) and the separately acquired Termux apksigner JAR.
These inputs remain ignored and hash-bound; no SDK/compiler redistribution grant
is inferred. An explicit owned tool root supplies `usr/bin/clang-21`, its
`usr/bin/lld`, headers/libraries, `python/usr` and `packaging/usr` from the
qualified Termux package set. The phone's own public system libc is a link
input; this is not compiler/sysroot equivalence with Unity's desktop NDK.

```sh
python3 -I -S build_on_android.py OWNED_TOOL_ROOT NEW_OUTPUT_DIRECTORY [30|33]
```

The driver produces a new APK from authored C/Java/XML without an editor-built
base player. It compiles a tiny PIE executable and packages the same bytes as
`lib/arm64-v8a/libtoolprobe.so` and `assets/control.bin`. The app uses
`ApplicationInfo.nativeLibraryDir` to launch the installed immutable binary,
then tries a writable private copy as the negative control. Child output must
carry its actual app UID, matching untrusted-app process context and authored
arithmetic marker. The default retains the literal target API 30 manifest;
explicit `33` selects `AndroidManifestTarget33.xml` without modifying either
source. The Java compile classpath remains API 30. Both variants require the
same writable-copy permission denial. No permissions, network, game input or
Unity code are used.

The disposable signing password exists only in the build process and child
environment; the encrypted key is an output, not a durable owner identity.
Every failure keeps its output directory. Installation requires explicit alpha
device selection, package absence, current capacity/storage checks and an
ownership receipt binding the exact APK hash. Capture private app reports,
actual placement/backing and logs, remove only the owned fixture, and sleep the
display. Native executables succeeding here would establish only the installed
location contract, not Python/.NET/Clang dependency hosting in an app.

Android documents the
[writable execution restriction](https://developer.android.com/about/versions/10/behavior-changes-10#execute-permission)
and the public
[native library directory](https://developer.android.com/reference/android/content/pm/ApplicationInfo#nativeLibraryDir).

J836 records the phone build and installed execution observation. The writable
copy also executes on the selected device, so the sandbox-policy control fails.
The report retains self/child contexts and an optional unprivileged enforcement
read without changing security state. A denied read leaves enforcement unknown.
An ignored `phone-host-check` request contains `apk`, `sha256` and optional
`target_sdk` (30 by default; only 30 or 33 accepted). The checker independently
checks the child identity/output and actual permission-denied control, records
file metadata/backing even when that control fails, and removes only its exact
owned APK. A higher target or different domain alone does not pass this gate;
this fixture does not establish a general app-host environment.
