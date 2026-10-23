# Authored build-tool host fixture

Current experimental support for comparing .NET build-tool hosts. This fixture
reads no game, SDK, editor or saved export data. It does not select the game's
execution backend. The game remains Unity IL2CPP ARM64.

`Program` allocates an authored binary tree and checks every stored node ID,
name, payload byte, parent reference and ordered child reference. It computes
a scalar witness from those stored fields, then requests a collection while
retaining the graph until process exit. `--self-test` uses 4,096 nodes;
`--graph` uses 262,144. Invalid arguments exit 3; a failed internal contract
exits 2. Success emits one JSON record and exits 0 after a two-second sampling
window. The process owns all fixture state; nothing persists after exit.

With an explicitly selected .NET 10 SDK, run the managed profile on a desktop:

```sh
dotnet run --project tools/phone-build/tool-host-fixture/fixture.csproj -c Release -- --self-test
dotnet run --project tools/phone-build/tool-host-fixture/fixture.csproj -c Release -- --graph
```

The independent arithmetic witnesses are:

| Nodes | Stored ID sum | Complete graph witness |
| ---: | ---: | ---: |
| 4,096 | 8,386,560 | 43,753,216 |
| 262,144 | 34,359,607,296 | 87,382,695,748 |

The SHA-256 field checks an authored UTF-8 constant independently of the graph.
`live_managed_bytes`, `server_gc` and externally sampled RSS are observations,
not interchangeable measurements. Different tool versions, collectors and
heap policies require separate qualification. This small graph cannot predict
AssetRipper's retained graph, complete export capacity or game performance.

Android NativeAOT uses the experimental `linux-bionic-arm64` tool target.
The [.NET 10 source guide](https://github.com/dotnet/runtime/blob/v10.0.12/src/coreclr/nativeaot/docs/android-bionic.md)
describes its publishing flags and separate NDK/OpenSSL requirements. The
[upstream older-NDK issue](https://github.com/dotnet/runtime/issues/116327)
explains a relevant ARM64 atomic-helper link failure. Use an isolated tool
profile: this fixture never changes the pinned Unity game toolchain. A phone
shell result does not qualify execution from an installed launcher app.

Generated outputs, dependency archives, raw device reports and any local linker
adapter stay in ignored storage. No complete tool distribution or installer is
provided here.
