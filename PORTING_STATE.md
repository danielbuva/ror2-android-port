# Current Porting State (x64 / `x86_64` Edition)

## Snapshot

| Item | Current fact |
| --- | --- |
| Target repository | `https://github.com/san5ezez/ror2-android-port` |
| Accepted input | Steam 25475991; input `6af7ed94619fe1b4346974b4486afa03a8d1625a7820e92da0ff74d57208fe88` |
| Toolchain | Unity 2021.3.45f2 (`88f88f591b2e`), IL2CPP **x64 (`x86_64`)**, Vulkan; `environment/toolchain.json` |
| Native ABI | `x86_64` (`EM_X86_64 = 62`, `-march=x86-64`, `-target x86_64-linux-android22`) |
| GitHub Actions CI | `.github/workflows/build-apk.yml` (sole workflow — builds and signs `ror2-android-x64-debug.apk`) |
