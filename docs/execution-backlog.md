# Open findings for Agent #3

Prioritize experiments that discriminate architectures; do not expand this into a whole-port implementation dump.

1. **Burst/Collections compatibility:** recovered loadingbasic opens, but entering Play Mode crashes the ARM64 editor in BurstCompilerService / Unity.Collections direct-call initialization. Determine exact shipped Burst/Collections package versions and whether compatible editor packages can replace player-compiled artifacts while preserving serialized types. Keep a crash-free checkpoint and avoid repeating unmodified Play Mode.
2. **RoR2 IL2CPP closure:** the SimpleJSON proof is insufficient. The minimal exported-project Android build now fails IL2CPP VTable construction; offending types resolve to Rewired_Core and Rewired_Windows. Isolate those platform assemblies, then repeat the closure test before deciding preserved DLLs versus controlled C#9 reconstruction. Both compilers currently report 11 first-pass source errors.
3. **Platform startup/entitlement boundary:** trace Steam, EOS, cloud/save and entitlement initialization. Design a legitimate offline development entry point; never falsify ownership/authentication. Preserve local HLAPI authority without requiring online transport.
4. **Wwise:** native version 2023.1.4.8496, Windows banks version 150. Resolve lawful matching Android runtime access; establish codec/bank compatibility and whether authoring sources exist. Separately prove a bounded no-audio lifecycle adapter.
5. **Rewired:** core 1.1.47.0.U2021. Establish lawful Android integration or action-preserving adapter; retain serialized action/player/controller maps and verify the handheld controls.
6. **Content/reference conversion:** use serialized-references.json plus scene probe. Resolve local PPtr/fileID and Addressables dependency/catalog remapping; do not interpret external-GUID scanning as full reference repair.
7. **Shaders:** all scanned platform arrays are D3D11; all exported shader files are dummies. Test one Hopoo Standard family with replacement/recovery, then terrain/particles/UI. Compute/postprocessing export/import errors need independent experiments.
8. **Storage scale/lifecycle:** small payload split passes on adopted storage. Measure multi-GiB payload sync, transfer interruption, update retention and uninstall/clear-data behavior with synthetic disposable data before large content migration. End-user durable import/scoped-storage strategy remains open.
9. **Observability:** add actual RoR2 run/player/audio/network/service checkpoints, not heuristic names. Validate GPU timing against external profiling and add configurable frame-cap/scenario sampling.
10. **Update process:** run an old/new input comparison when a second legitimate build becomes available; validate signature/semantic patch matching and selective cache invalidation on a real update.

Further unknowns: native PlayFab/Xbox/Discord reachability; successful Android build from the reconstructed project (the first minimal attempt failed); complete scene loading on device; rigged mesh/animation fidelity; shader translation quality; exact bank licensing; multiplayer. Do not silently promote these to facts.
