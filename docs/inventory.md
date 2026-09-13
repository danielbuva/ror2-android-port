# Current legitimate input

VERIFIED: Steam app 632360, installed build **21587608**, player bundle version **1.4.1**, Unity **2021.3.33f1**, Windows Mono. The installation is a user-supplied CrossOver Steam directory configured in ignored `work/config/local.json`; its exact path is not a repository requirement. This identifies the installed build, not a claim that it is the newest available Steam release.

Full SHA-256 input identity: `3e2dc63f6350b7523f3222c06962b40948da5ebf26b1d1b04f1f67d85b4e9dfd`.

| Measure | Verified observation |
| --- | --- |
| Files / total bytes | 2,395 / 3,208,983,811 |
| Managed assemblies / defined types | 143 / 28,648, including engine and framework assemblies |
| RoR2.dll | 5,847 metadata types; gameplay and platform orchestration; SHA-256 `0497a902a7aaf3c97fa2f1251a5364723b0c1b422839f7002a4b5f9c02563e4f` |
| Native PE binaries | 18; 17 x86_64 and one x86 EOS binary |
| Unity bundles | 1,472; Addressables StandaloneWindows64 directory |
| Sound banks | 218, Windows platform |
| Base player scene | `loadingbasic`; additional scenes in bundles |
| Content inventory coverage | 1,478 serialized inputs parsed without errors after correcting the scanner API |

Reproduce: `./dev inspect --full`, `./dev graphics`, `./dev prototype --action middleware`. Fast `inspect` reuses hashes only when size and nanosecond mtime match. Use full hashing for a release/checkpoint; metadata caching is not tamper detection.

Evidence: `work/inventory/files.json`, `summary.json`, `managed.json`, `native.json`, `graphics.json`, `middleware.json`. Raw inventories, names, recovered source, bundle contents, APKs, screenshots and logs remain ignored. Tracked documentation contains findings and small identifying facts, not a redistributed project.
