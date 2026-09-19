# L10-a unavailable-audio lifecycle audit (J63)

## Scope and method

This is a static, exact-input audit only. It reuses J50--J55 rather than
executing the original coroutine, instantiating audio prefabs, loading a bank,
or changing an assembly. The accepted input is
`3e2dc63f6350b7523f3222c06962b40948da5ebf26b1d1b04f1f67d85b4e9dfd`.
J52 proves the two legacy audio prefab *assets* load without instantiation;
J53 proves a direct original native query raises `DllNotFoundException` on
Android; J55 proves only the early `noAudio` getter guard reaches the
Addressables yield. None is evidence that later lifecycle paths are safe.

The pinned prior art is R2API `SoundAPI.cs` at
`f539511eabf87f02afddb5a83cafd2f4704c85ad`. It shows a relevant lifetime
contract: bank work begins after engine initialization, native load results
are retained, and unload success governs retained-memory release. It is not an
Android implementation, a substitute for Wwise, or evidence for this input.
No community code was copied.

## Source-hashed call-site and lifetime matrix

| Ordered obligation | Exact local caller and condition | Native boundary / counter and callbacks | Teardown owner and platform/profile coupling | Evidence status |
| --- | --- | --- | --- | --- |
| Early prefab request, covered by J55 | `RoR2.WwiseIntegrationManager.Init`; the two legacy prefab requests occur only when `noAudio` is false. | Prefab callbacks would instantiate `WwiseGlobal` and `AudioManager`; no native call is made by the suppressed branch itself. | No completion or cleanup callback is supplied by this branch. | **Observed:** J52 asset-only load; **observed:** J55 early guard. Instantiation and callback completion remain unobserved. |
| Prefab activation and engine owner | `AkInitializer.OnEnable` on the `WwiseGlobal` prefab, then `AkSoundEngineController.Init`. `AudioManager` also installs update/focus and pause-related callbacks when its prefab is active. | Controller initialization queries/initializes the native sound engine. The static `AudioManager` controls also query/post through it. | `AkInitializer.OnApplicationQuit` delegates to the controller; `OnDisable`, focus, and pause callbacks have distinct lifecycle edges. | **Inferred from source:** J51 identifies these components; J52 deliberately did not instantiate them. Exact enabled-object ordering and Android behavior are unresolved. |
| First uncovered native query and error dialog | `RoR2Application.InitializeGameRoutine` calls `AkSoundEngine.IsInitialized` after the early guard and after the coupled filesystem/platform portion of the coroutine. It is not conditioned on `WwiseIntegrationManager.noAudio`. | The query reaches the `AkSoundEngine` P/Invoke binding. Its `DllNotFoundException` handler calls `IssueStartupError` rather than establishing a no-audio mode. | `IssueStartupError` clears local users, changes to the title scene through the network manager, creates a dialog, and routes a teardown action through console quit. This cannot be treated as an audio-only handler. | **Observed:** J53 establishes the native-unavailable outcome for the direct query in a separate bounded probe. **Inferred:** this later call remains outside J55. **Blocked:** reaching it in the original coroutine crosses J61's platform/Steam boundary first. |
| Bank-load producer and pending wait | Each active `SoundbankLoader.Start` from the `WwiseGlobal` prefab calls `AkBankManager.LoadBankAsync` and increments `pendingLoads`; later `RoR2Application.InitializeGameRoutine` waits for `SoundbankLoader.doneLoading` after `SceneCatalog.Init`. | `AkBankManager` invokes native asynchronous bank loading. Its completion is packaged by `AkCallbackManager`; controller `LateUpdate` posts callbacks and drives scheduled unload work. A fresh J55 path has no instantiated producer, so the zero-initialized counter would not demonstrate a successful bank lifecycle. | Bank handle/callback removal and native unload occur in the Wwise manager/controller path, not at the coroutine wait. | **Inferred from source:** J51 counted eight `SoundbankLoader` components. **Unobserved:** bank files, native result, callback dispatch, counter balance after producer activation, wait reachability, and unload. A superficially satisfied zero counter under J55 would be a missing-producer result, not a pass. |
| Application shutdown | `RoR2Application.OnApplicationQuit` invokes `onShutDown` and the Steam unload delegate; `OnDestroy` also unloads Steam under its original condition. `PlatformSystems.Init` registers its shutdown work with `onShutDown`. | Wwise component quit/focus paths can call controller/native lifecycle code. The audited base `AkSoundEngineInitialization.ShouldKeepSoundEngineEnabled` returns true; no override was found in the audited source receipts, so normal `AkInitializer.OnApplicationQuit` is not static proof of native termination. Other disable/forced-reset paths remain relevant. | Whole-application shutdown necessarily includes platform save/lobby and Steam unload registrations, so it is not an isolated audio-cleanup test. | **Inferred from source:** shutdown reaches platform callbacks; **unresolved:** actual Unity destruction order, registered subscriber set, and native cleanup behavior on Android. No teardown was executed. |

## Source provenance

| Logical source | SHA-256 |
| --- | --- |
| `RoR2.WwiseIntegrationManager` | `adfb33fadfe1df2b99cc3527917c6a8e2d1eb2ac1598b5851d1b4b23f977f008` |
| `RoR2.RoR2Application` | `bbdf759ca70f13692ab3626cd4ac7be3410a71a55ae469af2347feeac27f78a8` |
| `RoR2.WwiseUtils.SoundbankLoader` | `e6d304d1e2c28af9052561794ab1c0f411cf1aabc2f1ce217372a583bb50ce4c` |
| `RoR2.AudioManager` | `a31604aac06df3abb66b5ea469e9ddcd30f690860cc6cc86db291d1eb4bb2377` |
| `AkInitializer` | `e376257437e70d20d5554d46135fdc7f1742ed6f9a54b00eb49cb84cc80c02e5` |
| `AkSoundEngineController` | `16ec9e9f0a3ff33bbca1ab42f19d4bd81fc2eec043ed392f10bc50b24abcbf68` |
| `AkSoundEngineInitialization` | `945850a8c600d5fa4bf26c978b2261cbd1b8515c7baf601127018c71a4f94a8e` |
| `AkBankManager` | `c0e7d412166166edf795d6671f3e73f82b8c2eb073656de280bc2fc37ba8b2fb` |
| `AkCallbackManager` | `50944dadbae91f229e8dd22d16afa52824b4461685c3f4ba79d1bd5082f3dfb8` |
| `AkSoundEngine` | `52e12f3a682a648de45e7cd2167bba847a4cd021cdf7492078ad61460215041f` |
| `AkSoundEnginePINVOKE` | `725adb816e8c0965d7b88f267f646e21e24716a6edcb3d59000f86d803e2156f` |
| `RoR2.PlatformSystems` | `d0e49e869bc636f68e679eae3d998b5c2dc3de92fb67849353e947ecf09b4fb5` |

## Assessment and transfer boundary

The first ordered uncovered obligation is the later original
`AkSoundEngine.IsInitialized` query and its Windows-runtime dialog path. It is
not eligible for an isolated runtime probe now: its original reachability is
downstream of J61's blocked filesystem/platform/Steam initialization, and its
failure handler requires local-user, network/title-scene, dialog, and console
state. The later bank wait adds a second independent obligation: J55 suppresses
the only identified producers, while a normal producer relies on native bank
completion and controller callback dispatch. Whole-app teardown is likewise
platform-coupled.

Therefore L10-a completes as attribution, not a no-audio, menu, L5, or audio
capability result. No single runtime probe is specified. Astra must choose any
future bounded experiment only after restoring runtime prerequisites and
preserving the J61 ownership/authentication/platform boundary. In particular,
reconstruction, a fake service, or a forced zero pending counter would not
satisfy the missing native, bank, ownership, entitlement, authentication,
license, or cleanup contracts.

## Health and preservation

`./dev doctor` on 2026-09-19 accepted the legitimate input and local tools but
reported no registered Unity MCP editor instance. Its detailed bootstrap check
also found zero authorized ADB devices. No editor, device, build, install,
assembly, original input, or checkpoint was mutated. The current device
absence is a prerequisite drift, not a revision of historical J52/J55/J57
evidence. The accepted J52, J55, and J57 receipts remain under
ignored `work/checkpoints/` and were not changed.
