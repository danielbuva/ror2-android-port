# Original jump-input boundary — J79 static review

The accepted direct CharacterMotor.Jump probe does not exercise GenericCharacterMain.ProcessJump. Current-input source inspection identifies the following next dependencies; no new jump-button capability is claimed.

Prior art: pinned Starstorm2 `BorgMain` (a9a4baddc5dd4405e893ab5dfc684eb9e27c26f8) invokes original GenericCharacterMain.ProcessJump before its custom hover behavior. This confirms the useful observation boundary; no hover behavior or mod hook is needed. Current original code takes precedence.

Original GatherInputs reads the unclaimed jump edge. ProcessJump checks the motor and body jump-count limit, optionally queries the inventory for JumpDamageStrike, and, after an accepted press, unconditionally queries the inventory for JumpBoost. It applies original jump velocity, increments jump count and dispatches the body's jump event. The first ordinary jump without bonus items avoids the extra-jump effects branch; absent animator and sound locator skip those optional paths, not inventory or event dispatch.

Inventory.Awake acquires original pooled ItemCollection storage. ItemCatalog controls buffer sizes. Inventory teardown queues pool release through its static fixed-update callback, which must be explicitly verified in an inactive fixture. ItemDef queries accept null and map it to ItemIndex.None, but using absent definitions would only prove a missing-content fallback. The meaningful next candidate should bind recovered definitions, initialize a bounded catalog and prove their zero counts with an empty original inventory before trying jump input.

The body jump event uses the actual network authority/server path and sends its original RPC on a server. A full body added after identity spawning has not proven RPC component registration. Test inventory allocation/query/disposal separately, then measure body/network event dispatch before claiming the complete press-to-jump path. Do not replace dispatch, synthesize ownership, skip the query or pass `ignoreRequirements` to force acceptance.

The recovered DynamicsManager records gravity (0, -30, 0), unlike the previous lab default (0, -9.81, 0). J79 supplies only the measured gravity during isolated probes and restores it afterward. The exported default material and collision matrix remain separate, unvalidated settings; this is not full stock physics parity.

Next bounded experiments: recovered jump-item identity and empty inventory lifecycle; real body jump-event networking; first legal jump press through the original state with normal count checks. Full master/body startup, populated catalogs, animation, skills, bonus jumps and physical controls remain separate gates.

## J81–J82 device outcome

The four bounded dependencies now pass on Android. Original catalog initialization requires a non-null previous content array; the diagnostic fixture supplies an empty array and restores its original value. Recovered definitions receive original indices, original empty inventory allocation/query/disposal passes, and original body authority dispatches one jump event through the server path with no connected client. A normal first press through GenericCharacterMain then produces one jump, rises and lands under source gravity -30; it does not call the motor Jump helper directly.

The earlier proposed RPC-registration risk did not block server-only sending: current NetworkBehaviour resolves its actual NetworkIdentity lazily, and the send path completes without an unspawned warning. This does not resolve observer/client delivery or full character registration. Actual item definitions are used for both jump queries; unrelated landing item/buff definitions remain absent, so their missing-definition fallbacks are outside catalog/fall-damage acceptance.

Four accepted probes span two receipted builds; null-array failures remain preserved. Full body/master initialization, complete catalogs/stats, repeated jump-limit behavior and physical controls remain the next boundaries. See J81/J82 and S29–S32 for evidence and limits.
