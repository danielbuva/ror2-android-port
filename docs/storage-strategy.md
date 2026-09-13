# Adopted-storage strategy

VERIFIED on the authorized Android 13 handheld: package code installs under the live adopted volume using the per-install `--force-uuid` option. This does not change global install settings. Manifest `auto` alone previously selected physical internal storage. Always query `sm list-volumes all`; never use a remembered UUID as an installation target.

The instrumented lab measured all three locations:

| Runtime concept | Measured location / backing |
| --- | --- |
| APK / Unity StreamingAssets | APK in `/mnt/expand/<live UUID>/app/...`; StreamingAssets is a `jar:file://...base.apk!/assets` URL. |
| Android private getFilesDir | `/mnt/expand/<live UUID>/user/0/dev.ror2lab.arm64/files` on adopted private storage. |
| Unity persistentDataPath | `/storage/emulated/0/Android/data/dev.ror2lab.arm64/files`; live df identifies adopted backing, although mount aliases can mention another bind-mount destination. |

A **27 MiB development APK + independently synced Android AssetBundle** passed real-device geometry rendering. The lab first launches to discover its runtime path, syncs payload files with SHA-256 verification and atomic same-directory rename, then relaunches. Runtime code/IL2CPP and initial player scene stay in the APK. Large explicit bundles and redirected Addressables providers can live outside it. Resources, embedded player data and arbitrary serialized bootstrap objects cannot simply be relocated by renaming folders.

`./dev install` queries live internal/adopted free bytes. It reserves 1 GiB physical-internal headroom plus a conservative estimate of three APK sizes and uncompressed native libraries. This is a warning/failure guard, not a proven Android scratch-space formula. A future near-capacity installation must be measured. Neither lab tooling nor future agents may format, repartition, erase, change storage configuration, or move/remove existing games to gain space.

`./dev sync-data` operates only under the runtime-reported package files directory, verifies remote file hashes, and skips unchanged files. It never deletes unrelated files. It queries actual payload backing and refuses unexpected paths. Large multi-gigabyte transfers and interrupted/resumed transfers remain unmeasured; current proof uses a ~63 KiB geometry bundle and a ~31 KiB negative Windows shader probe. No claim of whole-game payload scalability is made.

## Durability and permissions

App-specific files need no general storage permission for the app. ADB access measured here is a development capability, not an end-user permission model. VERIFIED by the storage-lifecycle experiment: a same-package/signature `-r` update preserved payload hashes and subsequent geometry rendering; a second sync transferred zero unchanged files. Record real placement each time. Uninstall/clear-data can remove app-specific content. The host's ignored generated payload is authoritative and can re-sync. Do not promise persistence across uninstall. Do not use `pm clear` on arbitrary packages; `./dev reset` uninstalls only a receipted lab package.

A durable end-user content library would require a separately selected storage location/provider (for example SAF) and an import/cache strategy, measured on adopted storage. This is a later experiment. No OBB implementation or permission bypass is claimed. For this device the adopted emulated volume already offers the desired capacity; portable-SD hardcoded paths are inappropriate.

Evidence: `work/runs/20260913T011048.134293Z-7630bdfebf6b/result.json`, `snapshot.json`, `private-path.txt`; initial storage controls in `environment/device-profile.json` and bootstrap smoke results. Query `./dev storage` for current numbers rather than reusing historical free space.

Update/sync evidence: `work/experiments/storage-lifecycle/result.json`. The disposable test package was removed afterward. Clear-data and durable external-library behavior remain untested.
