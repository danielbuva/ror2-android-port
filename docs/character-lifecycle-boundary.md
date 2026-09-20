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
