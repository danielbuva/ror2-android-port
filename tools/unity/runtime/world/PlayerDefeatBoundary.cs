// Subsystem: world/director (game path). Owner map: docs/ARCHITECTURE.md#ownership.
// Session phases: setup PreparePlayerDefeat, ObservePlayerDefeat (PlayerDefeatSession); teardown CleanupPlayerDeathEffect (coroutine); Dispose detaches the death listener only.
using System;
using System.Collections;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using RoR2;
using UnityEngine;
using UnityEngine.AddressableAssets;
using UnityEngine.AddressableAssets.ResourceLocators;
using UnityEngine.ResourceManagement.AsyncOperations;
using UnityEngine.ResourceManagement.ResourceLocations;
using UnityEngine.ResourceManagement.ResourceProviders;

// Observe original fatal damage/death/ragdoll/lifetime; the lab provides content and a stopped-input screen.
public sealed partial class PortSession
{
    [Serializable]
    public class PlayerDefeatReport
    {
        public bool prefabLoaded, ragdollStarted, deathEntered, effectTargetMatched, effectDestroyed, bodyDestroyed, masterRetained,
            corpseObserved;
        public int deathEvents, effects, ragdollBodies, stateIndex;
        public float health, seconds, holdSeconds;
        public string state;
    }
    const string PlayerDeathPath = "Prefabs/TemporaryVisualEffects/PlayerDeathEffect", PlayerDeathBundle = "player-death-effect-lab";
    PlayerDefeatSession playerDefeatSession;
    PlayerDefeatSession GetPlayerDefeatSession()
    {
        if (playerDefeatSession == null)
            playerDefeatSession = new PlayerDefeatSession(this);
        return playerDefeatSession;
    }
    IEnumerator PreparePlayerDefeat(CharacterBody body, SessionConfig cfg)
    {
        return GetPlayerDefeatSession().PreparePlayerDefeat(body, cfg);
    }
    void ObservePlayerDeathEvent(DamageReport report)
    {
        GetPlayerDefeatSession().ObservePlayerDeathEvent(report);
    }
    IEnumerator ObservePlayerDefeat(CharacterBody body, EntityStateMachine machine, NovaInputBridge bridge)
    {
        return GetPlayerDefeatSession().ObservePlayerDefeat(body, machine, bridge);
    }
    IEnumerator CleanupPlayerDeathEffect()
    {
        return GetPlayerDefeatSession().CleanupPlayerDeathEffect();
    }

    // Retain the owner for partial setup, repeated cleanup and later calls. Dispose
    // only detaches the listener; effect/asset release must await the coroutine's
    // original frame yields and release order, including when setup was skipped.
    sealed class PlayerDefeatSession : IDisposable
    {
        readonly PortSession coordinator;
        ResourceLocationMap playerDeathLocator;
        AsyncOperationHandle<GameObject> playerDeathHandle;
        GameObject playerDeathPrefab;
        readonly List<LocalCameraEffect> playerDeathEffects = new List<LocalCameraEffect>();
        CharacterBody observedDefeatBody;
        public PlayerDefeatSession(PortSession coordinator)
        {
            this.coordinator = coordinator;
        }
        public IEnumerator PreparePlayerDefeat(CharacterBody body, SessionConfig cfg)
        {
            coordinator.r.playerDefeat = new PlayerDefeatReport();
            coordinator.Check(!Resources.FindObjectsOfTypeAll<LocalCameraEffect>().Any(x => x.gameObject.scene.IsValid()),
                              "Existing local death camera effects");
            var index = EntityStateCatalog.GetStateIndex(typeof(EntityStates.Commando.DeathState));
            coordinator.Check(index != EntityStateIndex.Invalid &&
                                  EntityStateCatalog.GetStateType(index) == typeof(EntityStates.Commando.DeathState),
                              "Original player death state catalog identity missing");
            coordinator.r.playerDefeat.stateIndex = (int)index;
            body.GetComponent<SfxLocator>().deathSound =
                ""; // Original death explicitly skips an empty sound string; Android audio remains unavailable.
            string key;
            coordinator.Check(LegacyResourcesAPI.GetGuid(PlayerDeathPath, out key) && key == cfg.playerDeathEffectKey,
                              "Measured original player death key mismatch");
            var bundle = new ResourceLocationBase(PlayerDeathBundle,
                                                  System.IO.Path.Combine(Application.persistentDataPath, "payload", PlayerDeathBundle),
                                                  typeof(AssetBundleProvider).FullName, typeof(IAssetBundleResource));
            bundle.Data = new AssetBundleRequestOptions { BundleName = PlayerDeathBundle };
            playerDeathLocator = new ResourceLocationMap("player-death-effect-probe");
            playerDeathLocator.Add(key, new ResourceLocationBase(key, cfg.playerDeathEffectAsset, typeof(BundledAssetProvider).FullName,
                                                                 typeof(GameObject), bundle));
            Addressables.AddResourceLocator(playerDeathLocator);
            playerDeathHandle = LegacyResourcesAPI.LoadAsync<GameObject>(PlayerDeathPath);
            float deadline = Time.realtimeSinceStartup + 5;
            while (!playerDeathHandle.IsDone && Time.realtimeSinceStartup < deadline)
                yield return null;
            yield return null;
            coordinator.Check(playerDeathHandle.IsDone && playerDeathHandle.Status == AsyncOperationStatus.Succeeded &&
                                  LegacyResourcesAPI.ActiveCount == 0,
                              "Original player death effect provider failed");
            playerDeathPrefab = playerDeathHandle.Result;
            coordinator.Check(playerDeathPrefab && playerDeathPrefab.name == "PlayerDeathEffect" &&
                                  playerDeathPrefab.GetComponent<LocalCameraEffect>().effectRoot &&
                                  playerDeathPrefab.GetComponentsInChildren<Component>(true).All(x => x),
                              "Original player death effect serialized contract");
            coordinator.r.playerDefeat.prefabLoaded = true;
            var model = body.modelLocator.modelTransform;
            var ragdoll = model.GetComponent<RagdollController>();
            coordinator.Check(ragdoll && ragdoll.bones.Length > 0 &&
                                  ragdoll.bones.All(x => x && x.GetComponent<Collider>() && x.GetComponent<Rigidbody>()),
                              "Original Commando ragdoll references missing");
            ragdoll.enabled = true;
            yield return null;
            coordinator.Check(
                typeof(RagdollController).GetField("animator", BindingFlags.NonPublic | BindingFlags.Instance).GetValue(ragdoll) ==
                        model.GetComponent<Animator>() &&
                    ragdoll.bones.All(x => x.GetComponent<Rigidbody>().isKinematic && !x.GetComponent<Collider>().enabled),
                "Original ragdoll Start/cache/isolation failed");
            coordinator.r.playerDefeat.ragdollStarted = true;
            observedDefeatBody = body;
            GlobalEventManager.onCharacterDeathGlobal += ObservePlayerDeathEvent;
            coordinator.Save();
        }
        public void ObservePlayerDeathEvent(DamageReport report)
        {
            if (report.victimBody == observedDefeatBody)
                coordinator.r.playerDefeat.deathEvents++;
        }
        public IEnumerator ObservePlayerDefeat(CharacterBody body, EntityStateMachine machine, NovaInputBridge bridge)
        {
            coordinator.Check(body && !body.healthComponent.alive && coordinator.r.playerDefeat != null,
                              "Original fatal player damage missing");
            coordinator.r.playerDefeat.health = body.healthComponent.health;
            if (coordinator.r.integratedWorld && coordinator.r.world != null)
            {
                coordinator.r.world.health = coordinator.r.playerDefeat.health;
                coordinator.r.world.target = "";
                coordinator.r.world.objective = RecoveredHudPresentation.DefeatObjective(coordinator.r.selectedSurvivor);
            }
            // The normal world observer stops before its next HUD pass on fatal damage.
            // Bind the original health value once while the body still exists so the
            // results screen cannot retain the last living HP sample.
            if (coordinator.recoveredHud)
                coordinator.ObserveRecoveredHud();
            var playerRoot = body.gameObject;
            var master = body.master;
            bridge.enabled = false;
            coordinator.r.phase = "commando-death";
            coordinator.Save();
            float began = Time.realtimeSinceStartup;
            while (Time.realtimeSinceStartup - began < 8)
            {
                foreach (var effect in Resources.FindObjectsOfTypeAll<LocalCameraEffect>().Where(x => x.gameObject.scene.IsValid() &&
                                                                                                      x.targetCharacter == playerRoot))
                    if (!playerDeathEffects.Contains(effect))
                    {
                        playerDeathEffects.Add(effect);
                        coordinator.r.playerDefeat.effects++;
                        coordinator.r.playerDefeat.effectTargetMatched = true;
                    }
                if (body && machine && machine.state is EntityStates.Commando.DeathState)
                {
                    coordinator.r.playerDefeat.deathEntered = true;
                    coordinator.r.playerDefeat.state = machine.state.GetType().FullName;
                    coordinator.Check(!body.characterMotor.enabled, "Original death did not disable character motor");
                }
                if (coordinator.ownedDetachedModel)
                    coordinator.r.playerDefeat.ragdollBodies =
                        Math.Max(coordinator.r.playerDefeat.ragdollBodies,
                                 coordinator.ownedDetachedModel.GetComponentsInChildren<Rigidbody>(true).Count(x => !x.isKinematic));
                coordinator.r.playerDefeat.bodyDestroyed = !body;
                coordinator.r.playerDefeat.effectDestroyed = playerDeathEffects.Count == 1 && playerDeathEffects.All(x => !x);
                coordinator.r.playerDefeat.masterRetained = master && !master.GetBody();
                coordinator.r.playerDefeat.corpseObserved |=
                    !body && coordinator.ownedDetachedModel && coordinator.ownedDetachedModel.GetComponent<Corpse>();
                coordinator.r.playerDefeat.seconds = Time.realtimeSinceStartup - began;
                coordinator.ObserveEnemy();
                coordinator.Save();
                if (coordinator.r.playerDefeat.bodyDestroyed && coordinator.r.playerDefeat.effectDestroyed)
                    break;
                yield return null;
            }
            coordinator.Check(coordinator.r.playerDefeat.deathEvents == 1 && coordinator.r.playerDefeat.deathEntered &&
                                  coordinator.r.playerDefeat.effects == 1 && coordinator.r.playerDefeat.effectTargetMatched &&
                                  coordinator.r.playerDefeat.effectDestroyed && coordinator.r.playerDefeat.bodyDestroyed &&
                                  coordinator.r.playerDefeat.masterRetained && coordinator.r.playerDefeat.ragdollBodies > 0,
                              "Original player death/ragdoll/effect/natural body lifetime incomplete");
            if (coordinator.r.results != null && coordinator.r.results.ready)
            {
                var ending = Enumerable.Range(0, GameEndingCatalog.endingCount)
                                 .Select(x => GameEndingCatalog.GetGameEndingDef((GameEndingIndex)x))
                                 .Single(x => x.cachedName == "StandardLoss");
                coordinator.Check(!ending.isWin, "Original defeat ending is a victory");
                Run.instance.BeginGameOver(ending);
                float deadline = Time.realtimeSinceStartup + 5;
                while (!coordinator.r.results.persisted && Time.realtimeSinceStartup < deadline)
                {
                    Call(coordinator.activeBodyClient, "Update");
                    coordinator.ObserveIntegratedResults();
                    yield return null;
                }
                coordinator.Check(coordinator.r.results.persisted && coordinator.r.results.clientEnding,
                                  "Original defeat report/client/persistence incomplete");
            }
            GlobalEventManager.onCharacterDeathGlobal -= ObservePlayerDeathEvent;
            coordinator.r.phase = "commando-defeated";
            coordinator.Save();
            // Restart waits for original death/body lifetime, then uses the full session teardown.
            while (coordinator.r.freePlay && !coordinator.restartRequested)
            {
                coordinator.r.playerDefeat.holdSeconds += Time.unscaledDeltaTime;
                if (Time.frameCount % 30 == 0)
                    coordinator.Save();
                yield return null;
            }
        }
        public void Dispose()
        {
            GlobalEventManager.onCharacterDeathGlobal -= ObservePlayerDeathEvent;
        }
        public IEnumerator CleanupPlayerDeathEffect()
        {
            GlobalEventManager.onCharacterDeathGlobal -= ObservePlayerDeathEvent;
            if (playerDeathLocator == null)
                yield break;
            foreach (var effect in playerDeathEffects)
                if (effect)
                    Destroy(effect.gameObject);
            yield return null;
            coordinator.Check(playerDeathEffects.All(x => !x), "Player death effects survived owned cleanup");
            for (int i = 0; i < playerDeathEffects.Count; i++)
                Addressables.Release(playerDeathPrefab);
            if (playerDeathHandle.IsValid())
                Addressables.Release(playerDeathHandle);
            yield return null;
            coordinator.Check(!AssetBundle.GetAllLoadedAssetBundles().Any(x => x.name == PlayerDeathBundle),
                              "Player death provider bundle retained");
            Addressables.RemoveResourceLocator(playerDeathLocator);
            playerDeathLocator = null;
        }
    }
}
