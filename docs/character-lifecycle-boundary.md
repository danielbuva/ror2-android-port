# Recovered character lifecycle boundary

J82 proves a first jump press in an inactive diagnostic body. Replacing that fixture requires measured lifecycle dependencies, not merely assigning the same component names to a new object.

Prior art: pinned Starstorm2 SS2VanillaSurvivor (a9a4baddc5dd4405e893ab5dfc684eb9e27c26f8) keeps named EntityStateMachines connected to NetworkStateMachine, death and hurt lists. Pinned DebugToolkit NetworkManager (d1e2f0aa4b8ac4747547db0fcd87344953432f06) uses actual server spawning. These distinguish prefab relationships from activation and network ownership; no mod implementation is copied.

Original CharacterBody.Awake caches components, obtains BuffCatalog-sized arrays, resolves model/hurtbox/core references and invokes its global awake event. BuffCatalog.SetBuffDefs can initialize an explicitly empty diagnostic catalog. This supports isolated Awake testing, not real buff availability. The experiment restores prior catalog array identities and keeps the recovered Commando root inactive.

CharacterBody.Start is a broader boundary: authority, Run time, drone lookup, RecalculateStats, master linking, health, sound and collision-layer updates. It is not part of the Awake proof. Original OnDestroy also invokes audio and master callbacks. The inactive fixture detaches only its measured model subscription instead of claiming full original teardown safety.

The canonical player prefab is PlayerMaster; CommandoMonsterMaster is an AI master and is not substituted for it. Original CharacterMaster.Awake caches its actual Inventory, identity and player controller and subscribes to inventory/stage events. Awake/registration can be tested without Start, spawning or a player session. Original master OnDestroy and inventory queued disposal provide the bounded cleanup path.

The body's masterObject setter records the actual network ID. Reading masterObject resolves a real server/client object, adopts the master's inventory and invokes OnInventoryChanged. That callback directly dereferences the four Lunar skill-replacement item definitions. Its equipment comparison also requires care: an absent QuestVolatileBattery definition can compare equal to empty equipment, incorrectly selecting an item behavior. Do not treat absent definitions as a complete empty inventory contract or suppress these callbacks to claim linkage.

UpdateMasterLink then invokes CharacterMaster.OnBodyStart, recalculates stats, requires a registered BodyCatalog index and reads the master's loadout. Therefore separately test real master/body network resolution and required inventory definitions before complete Start/OnBodyStart. Normal catalog/stat initialization, native audio, local-client/player relationship and physical controls remain open gates.

## J84 device outcome

All four selective probes pass on Android: empty buff storage, recovered Commando Awake, body registration and recovered PlayerMaster Awake/registration. Original caches agree with actual prefab components, and the body's awake event fires once. Source/read-only state-machine inspection uses the current private field; the older community accessibility did not match this input and caused the preserved J83 compiler failure.

This establishes original setup on recovered objects, beyond the prior assembled diagnostic body. The roots remain inactive and no Start/stat/master-link/network-spawn path runs. Continue with actual identity resolution and measured inventory callback definitions before reciprocal body-master linkage; preserve the distinction between registration, network ownership and fully initialized simulation.

## Next inventory-adoption content candidate

Current input contains the original LunarPrimaryReplacement, LunarSecondaryReplacement, LunarUtilityReplacement and LunarSpecialReplacement ItemDefs in their corresponding item directories, plus QuestVolatileBattery EquipmentDef. Some directories also contain identically named SkillDefs; select by exact path and original script type, not basename. A future empty-inventory linkage probe must bind the actual required definitions and distinguish optional zero-count queries from directly dereferenced definitions.

Static review of OnInventoryChanged also reaches hurtbox availability, optional item behaviors, equipment changes, item/buff availability and drone checks. Empty inventory plus a non-drone Commando narrows those branches, but does not establish a full content catalog or normal stat computation. Preserve individual first-failure reports when invoking the real getter; do not replace it with NetworkServer.FindLocalObject and call that complete linkage.

## J85 network prerequisite outcome

Original state-machine networking setup and actual server spawning of recovered body/master pass on Android. The original body setter stores a distinct real master ID, and actual server lookup resolves it; both roots remain inactive. Original effective-authority queries pass without assigned flags. Owned unspawn removes the registered objects.

The getter is still uncalled: inventory adoption, its callbacks and the master's reciprocal body reference are explicitly asserted absent. These tests remove network-ID uncertainty before the required content/empty-inventory adoption experiment. No connected-client, replication, full Start or player-session result is implied.

## J87 inventory-adoption outcome and next boundary

Five original definitions and original empty-inventory adoption pass in separate Android processes. The getter resolves the real master, adopts its inventory, detects the player controller and completes one callback; subsequent reads do not repeat it. The reciprocal master body remains absent. Optional absent definitions still use original zero-count fallbacks; full catalogs, item grants and later inventory notifications remain untested.

Next isolate meaningful RecalculateStats prerequisites: an absent Run causes an immediate silent return, while the active path immediately reads TeamManager experience/level through body.teamComponent. Actual original team setup and a bounded Run context must be measured before accepting stats. SpawnBody also needs populated body caches, loadout and Run spawn callbacks. Preserve original methods and separate these from full prefab activation; directly writing reciprocal caches cannot establish the original spawn path.

## J88–J90 stat prerequisites and first-failure sequence

Original team experience initialization/thresholds, recovered team/hurtbox membership, minimal Run singleton enable/disable, four recovered GenericSkill default assignments and recovered motor capsule bounds now pass independently on Android. Run.Awake/Start remains uncalled. Skill identity/state-machine/cooldown and capsule initialization use original methods; none establishes full character activation.

RecalculateStats remains unaccepted. The first attempt lacked GenericSkill.Awake; the second reached effect bounds without CharacterMotor.Awake; the third reaches UpdateKnockBackHitVisualsAndGracePeriod, which directly dereferences two absent DLC2 BuffDefs. These are distinct measured dependencies, not repeated unchanged failures. Neither partial values nor absence of a crash passes the completion assertion.

Next recover bdKnockUpHitEnemies and bdKnockUpHitEnemiesJuggleCount from the original KnockBackHitEnemies directory, verify typed identities and catalog indices separately, and allocate body buff storage after this diagnostic catalog is populated. Restore both name mappings and arrays afterward. Trace the grounded/authority branch before retrying the original handler/stat calculation. Do not suppress its callback, inject completed stats or activate full startup. Keep level-one expected values and completion-event assertions unchanged.

## J92 base-stat acceptance

The two recovered knockback BuffDefs now receive original indices before body Awake allocates storage. The original zero-buff handler and original RecalculateStats pass independently; level-one results are health 110, speed 7, damage 12 and jump 15, with one completion event. The handler uses the original non-authoritative grounding branch; neither solver motion nor full motor authority is established here.

J91 initially failed earlier because its bundle omitted ModelLocator serialized fields despite unchanged original files. Regenerated staging/import restores those fields; buff-disabled/enabled controls both pass. The exact import-cache trigger is still unisolated, and the rejected payload remains archived. Do not patch the original prefab or clear broad caches based on that observation.

Next test original team-level-derived stat changes, then recovered motor/state setup using computed stats. Keep subset catalogs and selective inactive lifecycle explicit; reciprocal spawning, loadout/body catalog, client/player semantics and formal L5.5 remain separate.

## J93 computed-stat motor and level-up boundary

Recovered solver binding and motor authority now consume original computed acceleration 80/speed 7 in PreMove; cap/braking pass without replacing stats. Original state-driven solver displacement on this recovered body remains next. Full Start and reciprocal/client relationships remain separate.

Team level-up reaches the original LevelUpEffectManager subscriber, which accesses the absent application singleton. TeamCatalog static initialization also tries legacy effect loads and logs missing Addressables RuntimeData. Preserve the failed launch. Before retrying, inspect actual team effect closure and legitimate audio/application context; do not suppress subscriber/sound or infer level-two success from partial team mutation.

## J94 recovered state-motion acceptance

The existing recovered Body machine and InputBankTest now run original GenericCharacterMain entry/exit, input gathering and state-driven motor/solver motion with original computed stats. Three fresh Android launches pass. Direction input produces x5.844 after one simulated second and neutral input stops at x7. Roots stay inactive; simulation is stepped explicitly, without gravity or collision.

Next inspect original recovered motor Start and landing callback dependencies, then add gravity and floor collision separately. Preserve the existing state/input relationships and computed stats. Visual character motion, automatic full lifecycle, reciprocal spawning and client/controller acceptance remain unproven.

## J95/J96 recovered gravity and landing

Original motor Start now enables gravity/authority and emits its event. Source gravity -30 produces expected free fall. The recovered capsule is centered on its root (height 1.82/offset 0), unlike the earlier diagnostic capsule: initial floor clearance must account for its lower half. Starting at 12 above floor top 9.5 yields one original landing event and a stable center at 10.42. The failed overlapping start remains preserved.

Combine this context with recovered state-driven horizontal motion next; isolate stop/reversal/wall acceptance. No original landing callback is removed, but the plain diagnostic floor does not establish material effects or audio. Full lifecycle, reciprocal body/client and physical controls remain open.

## J97 grounded motion acceptance

Recovered original state/motor/solver now combine ground contact with forward movement, reversal and wall stopping. Measured forward displacement is 6.76 in one simulated second; reversal reaches -6.152 after two more seconds; wall contact stops at 0.99. Neutral input stops in all cases and grounding remains.

Next review recovered jump item/event/SfxLocator dependencies against J81/J82 before running jump input. The earlier assembled fixture lacked recovered sound fields, so it cannot establish the Android native-audio path. Visual agreement using the accepted skin/material display is also outstanding; current screenshots show only the lab fixture. Preserve inactive/subset-catalog and full-lifecycle/client/control limits.

## J98 visible pose agreement and jump audit

The recovered character is now visible in two fixed-camera captures at its actual measured start/stop poses. Original simulation moves seven units; diagnostic renderer-only copies shift 512 pixels as projected. Display is bind pose with direct mesh/material binding, not skin-loader/animation or live controller integration.

The current recovered jumpSound field is empty; original GenericCharacterMain guards that call. Landing and fall-damage sound fields are populated. Next test the normal recovered jump with actual runtime field/count checks and original input/event/landing behavior. Do not clear sound fields, suppress callbacks or treat the earlier assembled-body jump as recovered-character acceptance. Bonus-jump effects and surface/audio remain separate.

## J99 ownership boundary in recovered jump

Runtime jumpSound is actually empty and landingSound remains populated; two recovered jump items have zero counts and original computed jump power/count are correct. Both direct original event dispatch and input-jump acceptance observe no local onJump event. Input impulse was not independently recorded; do not infer it from the combined failed assertion.

Original TriggerJumpEventGlobally gates local delivery on hasAuthority. The recovered prefab requests local-player authority, whereas the server-only effective-authority fallback can still drive movement without a client owner. This source-backed distinction needs direct runtime observations and a real local client/ownership experiment. Do not force flags, change the prefab setting or invoke events manually. Network/client serialization and player/master/body relationships remain separate dependencies.

## J100/J101 local authority prerequisite

Direct Android observation confirms the recovered server-only body has raw authority false, effective authority true, player-authority configuration true and no client owner. On a separate minimal identity, original local connection/readiness and client-authority message delivery/removal now pass with clean cleanup. Stop the owned server before ClientScene resets the shared transport; reverse order caused the preserved teardown error.

Next observe recovered-object OnStartClient/ownership paths. Minimal connection success does not establish recovered serialization, player/master/body relationships or jump-event delivery. Keep actual original connection/authority APIs and never replace missing ownership with private flag writes.

### J107–J109: fresh-clone initialization precedes reciprocal spawn
Original master SpawnBody creates the inactive recovered body and assigns its master network ID, then encounters an uninitialized team cache. The clone also lacks the skill cache and has no actual server registration. Original CharacterBody.Awake fills those caches. Existing explicitly initialized diagnostic-body proofs cannot establish initialization of a fresh clone. Next audit automatic Awake/OnEnable callbacks and isolate the original lifecycle; do not replace spawning or inject private reciprocal references. Default master loadout serialization passes separately.

### J110–J112: execution order restored; reciprocal spawning accepted
Original input MonoScript metadata sets CharacterMotor execution order to 200, while exported plugin metadata loses it to 0. The solver at order 0 binds the controller in Awake; restoration allows CharacterMotor OnEnable to use that binding. Automatic root activation/deactivation/destruction then passes without manual cache setup. Original CharacterMaster.SpawnBody also passes reciprocal linkage and server registration with root automatic initialization. Children remain inactive and the body is stopped before Start. Keep the measured importer restoration for future automatic-root tests; original BodyCatalog and Start/UpdateMasterLink callbacks are next, not broad gameplay activation.
