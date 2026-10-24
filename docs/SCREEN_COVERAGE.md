# Player screen inventory

Current composed Android route, compared with the original UI families found in
the accepted input. This is a screen inventory, not a complete interaction or
appearance qualification. Results belong in the journal; open acceptance work
belongs in [public-alpha.md](public-alpha.md). See
[subsystem coverage](subsystem-coverage.md) for gameplay contracts.

| Original UI family | Android owner/current surface | Remaining player gate |
| --- | --- | --- |
| Startup, title, first launch and profile choice | Isolated lab bootstrap and Android-local profile; stock platform startup unavailable | Fresh player installation, first launch and unsupported-input/storage recovery |
| Main menu and single player | `OfflineApplicationBoundary`: recovered menu where ready, explicit fallback otherwise; Start and Quit | Ordinary touch/controller navigation; natural Quit and complete source presentation |
| Survivor selection and loadout | `OfflineApplicationBoundary` and original profile-filtered definitions | Physical navigation/rebinding; all supported earned choices; ordinary input on each supported device |
| Difficulty choice | Android menu retains original difficulty indices and saves Android preferences | Touch/controller persistence after update and cold restart |
| Multiplayer, lobby and online service screens | Unavailable offline capability, no fabricated identity/session | Explicitly deferred by [alpha policy](ALPHA_POLICY.md); no online support claim |
| Settings and controls | `AndroidOfflineSettings` / `OfflineSettingsBoundary`: deadzone, camera sensitivity, invert Y, Save/Resume | Full touch movement/camera/actions and mappings/rebinding; original graphics/audio/accessibility options not integrated |
| Pause and end run | Settings owns pause; End run opens a separate confirmation with cancel | [J1066](PORTING_JOURNAL.md#j1066--qualify-native-settings-feedback-and-two-step-end-run-controls) qualifies touch cancel/confirm, pause and strict diagnostic restart; ordinary physical input and held-input release remain open |
| In-run HUD, inventory and pickup notices | Recovered HUD and original notification queue under `IntegratedWorldBoundary` | Ordinary touch/controller inspection and full source font/layout/visual parity |
| Results and restart | Original result/statistics plus Android ledger; Restart/Close surface | Ordinary input, menu return, repeated-session bound and profile retention |
| Logbook, challenges/unlock inspection, artifacts and alternate modes | Not integrated as player screens | Preserve absence; define and qualify intended alpha coverage before claiming full original UI |
| Credits and software notices | Original input contains credits/notices; no composed player route | Add appropriate notices for distributed tooling and qualify the final player route |
| Feedback | `AndroidFeedbackScreen` / `AndroidFeedbackDraft`, local preview, consent, clipboard and browser draft | [J1066](PORTING_JOURNAL.md#j1066--qualify-native-settings-feedback-and-two-step-end-run-controls) qualifies Android keyboard, preview/consent, clipboard readback and browser return; raw logs and attachments are not collected |
| Phone preparation/install/update/recovery | Launcher frontend boundary only; no connected Android backend | Owned by the phone installation workstream; fixture proofs do not qualify the player flow |

Current touch support is limited to menus/settings, equipment and diagnostic
buttons. It does not provide movement, camera, four skills or full interaction.
The measured physical controller bridge is restricted to the Nova; Thor accepts
explicit automatic diagnostics only. Neither route is a generic Android control
mapping. Do not describe the existing settings title as proof of touch gameplay.
