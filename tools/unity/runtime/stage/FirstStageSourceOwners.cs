// Concrete source ownership for the default-off first-stage lifecycle diagnostic.
using System;
using System.Linq;
using System.Reflection;
using LabPort.SourceStageLifecycle;
using RoR2;
using UnityEngine;
using UnityEngine.Events;
using UnityEngine.Networking;
using UnityEngine.SceneManagement;

public sealed partial class PortSession
{
    sealed partial class IntegratedStageSession
    {
        sealed class FirstStageSourceOwners : ISourceStageIdentityOwners
        {
            readonly PortSession coordinator;
            readonly Scene scene;
            GameObject root;
            SceneDirector sceneDirector;
            CombatDirector fast, slow;
            DirectorCore core;
            bool rootWasActive, sceneDirectorWasEnabled, fastWasEnabled, slowWasEnabled;
            DirectorCardCategorySelection priorFastDeck, priorSlowDeck, ownedDeck;
            bool rootPrepared, fastListenerAdded, slowListenerAdded, rolledBack;
            GameObject priorAutomaticDirectorHost;
            CombatDirector priorRewardDirector, priorSourceSlowDirector;
            UnityAction<GameObject> fastSpawnListener, slowSpawnListener;
            static readonly BindingFlags PrivateInstance = BindingFlags.Instance | BindingFlags.NonPublic;
            static readonly FieldInfo DirectorRng = typeof(CombatDirector).GetField("rng", PrivateInstance);
            static readonly FieldInfo DirectorMoneyWaves = typeof(CombatDirector).GetField("moneyWaves", PrivateInstance);
            static readonly FieldInfo DirectorCardSelection = typeof(CombatDirector).GetField("monsterCardsSelection", PrivateInstance);

            public FirstStageSourceOwners(PortSession coordinator, Scene scene)
            {
                this.coordinator = coordinator ?? throw new ArgumentNullException("coordinator");
                this.scene = scene;
            }

            public bool StageRngReady => Run.instance && Run.instance.stageRng != null && SceneManager.GetActiveScene() == scene &&
                                         scene.IsValid() && scene.isLoaded;

            public SceneInfo RequireActiveSceneInfo(Scene requested)
            {
                coordinator.Check(requested == scene && coordinator.stageSourceObjects && coordinator.sourceSceneInfoRoot &&
                                      coordinator.sourceSceneInfoRoot.scene == scene,
                                  "First-stage lifecycle requires the StageGeometry-owned source context");
                var info = coordinator.sourceSceneInfoRoot.GetComponent<SceneInfo>();
                coordinator.Check(info && SceneInfo.instance == info &&
                                      coordinator.sourceSceneInfoRoot.GetComponent<ClassicStageInfo>() == ClassicStageInfo.instance &&
                                      ClassicStageInfo.instance.gameObject.scene == scene,
                                  "Borrowed source SceneInfo/ClassicStageInfo identity changed");
                return info;
            }

            public void PreflightDirectorRoot(Scene requested)
            {
                coordinator.Check(requested == scene && coordinator.r != null && coordinator.r.liveCatalogs != null &&
                                      coordinator.currentStageCombatDeck != null && coordinator.currentStageCombatDeck.nativePool &&
                                      coordinator.currentStageCombatDeck.stage == scene.name &&
                                      coordinator.currentStageCombatDeck.cards != null &&
                                      coordinator.currentStageCombatDeck.cards.Length > 0,
                                  "First-stage diagnostic requires the already-selected full native stage deck");
                var roots = scene.GetRootGameObjects().Where(candidate => candidate.name == "Director").ToArray();
                coordinator.Check(roots.Length == 1 && !roots[0].activeSelf && roots[0].scene == scene,
                                  "Exact inactive source Director root is missing or ambiguous");
                var directorRoot = roots[0];
                var directors = directorRoot.GetComponents<CombatDirector>();
                coordinator.Check(directorRoot.GetComponent<SceneDirector>() && directorRoot.GetComponent<DirectorCore>() &&
                                      directors.Length == 2 && directors.All(candidate => candidate && candidate.enabled) &&
                                      directors[0].onSpawnedServer != null && directors[1].onSpawnedServer != null && DirectorRng != null &&
                                      DirectorMoneyWaves != null && DirectorCardSelection != null &&
                                      directors.All(candidate => DirectorRng.GetValue(candidate) == null &&
                                                                 DirectorMoneyWaves.GetValue(candidate) == null &&
                                                                 DirectorCardSelection.GetValue(candidate) == null),
                                  "Source Director native component cohort was already awakened or its initialization witness changed");
                coordinator.Check(!coordinator.rewardDirectorHost && !DirectorCore.instance,
                                  "Temporary reward DirectorCore must be absent before source-stage preflight");
                coordinator.Check((!coordinator.automaticDirectorHost ||
                                   ReferenceEquals(coordinator.automaticDirectorHost,
                                                   scene.GetRootGameObjects().Single(candidate => candidate.name == "Director"))) &&
                                      coordinator.automaticDeck && coordinator.currentStageCombatDeck.nativePool,
                                  "A foreign active director or missing full native deck conflicts with first-stage source ownership");
            }

            public void PrepareSourceInteractableTables(Scene requested, NetworkIdentity[] sourceIdentities,
                                                       GameObject[] toggleTargets)
            {
                coordinator.Check(requested == scene && coordinator.r.nativeFirstStageLifecycleDiagnosticAttempt,
                                  "Native source interactable preparation lost its exact scene owner");
                coordinator.PrepareNativeSourceInteractableTables(scene, sourceIdentities, toggleTargets);
            }

            public void RestoreSourceInteractableTables(Scene requested)
            {
                coordinator.Check(requested == scene, "Native source interactable restore changed scenes");
                coordinator.RestoreNativeSourceInteractableTables(scene);
            }

            public GameObject PrepareDirectorRoot(Scene requested)
            {
                PreflightDirectorRoot(requested);
                root = scene.GetRootGameObjects().Single(candidate => candidate.name == "Director");
                rootWasActive = root.activeSelf;
                sceneDirector = root.GetComponent<SceneDirector>();
                sceneDirectorWasEnabled = coordinator.NativeSourceSceneDirectorWasEnabled;
                var directors = root.GetComponents<CombatDirector>();
                fast = directors[0];
                slow = directors[1];
                fastWasEnabled = fast.enabled;
                slowWasEnabled = slow.enabled;
                priorAutomaticDirectorHost = coordinator.automaticDirectorHost;
                priorRewardDirector = coordinator.rewardDirector;
                priorSourceSlowDirector = coordinator.sourceSlowDirector;
                core = root.GetComponent<DirectorCore>();
                priorFastDeck = coordinator.NativeOriginalSourceFastDeck;
                priorSlowDeck = coordinator.NativeOriginalSourceSlowDeck;
                coordinator.Check(ReferenceEquals(fast.monsterCards, priorFastDeck) ||
                                      ReferenceEquals(fast.monsterCards, coordinator.automaticDeck),
                                  "Source fast deck changed outside the stage selector before ownership transfer");
                coordinator.Check(ReferenceEquals(slow.monsterCards, priorSlowDeck) ||
                                      ReferenceEquals(slow.monsterCards, coordinator.automaticDeck),
                                  "Source slow deck changed outside the stage selector before ownership transfer");
                ownedDeck = coordinator.automaticDeck;
                rootPrepared = true; // Transaction is owned from the first mutation onward.
                try
                {
                    // Reuse the existing owner for exact root validation and SceneDirector disable.
                    var borrowed = coordinator.SourceStageDirectorRoot(false);
                    coordinator.Check(ReferenceEquals(borrowed, root) && !sceneDirector.enabled &&
                                          ReferenceEquals(coordinator.sourceSlowDirector, slow),
                                      "AutomaticDirectorSession lent a different source root");
                    fast.monsterCards = coordinator.automaticDeck;
                    slow.monsterCards = coordinator.automaticDeck;
                    coordinator.Check(coordinator.automaticDeck &&
                                          coordinator.automaticDeck.categories.SelectMany(category => category.cards).Any(),
                                      "Source directors lack the selected full native deck");
                    coordinator.automaticDirectorHost = root;
                    coordinator.rewardDirector = fast;
                    fastSpawnListener = obj =>
                    { coordinator.RecordStageCombatSpawn(obj, coordinator.worldPlayer, fast); };
                    slowSpawnListener = obj =>
                    {
                        if (coordinator.currentStageCombatDeck != null)
                            coordinator.RecordStageCombatSpawn(obj, coordinator.worldPlayer, slow);
                        else
                            coordinator.RecordDirectorActor(obj, coordinator.worldPlayer);
                    };
                    fast.onSpawnedServer.AddListener(fastSpawnListener);
                    fastListenerAdded = true;
                    slow.onSpawnedServer.AddListener(slowSpawnListener);
                    slowListenerAdded = true;
                    return root;
                }
                catch (Exception primary)
                {
                    try
                    {
                        RollbackDirectorRoot();
                    }
                    catch (Exception rollback)
                    {
                        primary.Data["FirstStageDirectorRollbackFailure"] = rollback;
                    }
                    throw;
                }
            }

            public void BeforeDirectorRootRollback(bool nativeQueuesEmpty)
            {
                coordinator.AbortNativeWholeStagePopulationBeforeStart(nativeQueuesEmpty);
            }

            public void RollbackDirectorRoot()
            {
                if (rolledBack || !rootPrepared)
                    return;
                // Restore in reverse acquisition order; only detach our exact delegates.
                if (slowListenerAdded && slow && slow.onSpawnedServer != null)
                    slow.onSpawnedServer.RemoveListener(slowSpawnListener);
                slowListenerAdded = false;
                if (fastListenerAdded && fast && fast.onSpawnedServer != null)
                    fast.onSpawnedServer.RemoveListener(fastSpawnListener);
                fastListenerAdded = false;
                if (root)
                {
                    if (root.activeSelf)
                        root.SetActive(false);
                    if (fast)
                    {
                        coordinator.Check(ReferenceEquals(fast.monsterCards, ownedDeck) ||
                                              ReferenceEquals(fast.monsterCards, priorFastDeck),
                                          "Foreign fast director deck replaced the owned first-stage value");
                        if (ReferenceEquals(fast.monsterCards, ownedDeck))
                            fast.monsterCards = priorFastDeck;
                        fast.enabled = fastWasEnabled;
                    }
                    if (slow)
                    {
                        coordinator.Check(ReferenceEquals(slow.monsterCards, ownedDeck) ||
                                              ReferenceEquals(slow.monsterCards, priorSlowDeck),
                                          "Foreign slow director deck replaced the owned first-stage value");
                        if (ReferenceEquals(slow.monsterCards, ownedDeck))
                            slow.monsterCards = priorSlowDeck;
                        slow.enabled = slowWasEnabled;
                    }
                    if (sceneDirector)
                        sceneDirector.enabled = sceneDirectorWasEnabled;
                    root.SetActive(rootWasActive);
                }
                if (coordinator.automaticDirectorHost == root)
                    coordinator.automaticDirectorHost = priorAutomaticDirectorHost;
                if (coordinator.rewardDirector == fast)
                    coordinator.rewardDirector = priorRewardDirector;
                if (coordinator.sourceSlowDirector == slow)
                    coordinator.sourceSlowDirector = priorSourceSlowDirector;
                rolledBack = true;
                rootPrepared = false;
                if (rootWasActive && root && core)
                    coordinator.Check(DirectorCore.instance == core, "Borrowed DirectorCore did not restore");
            }

            public void SuspendDirectorBehaviorsForSynchronousActivation(GameObject requestedRoot)
            {
                RequirePreparedRoot(requestedRoot);
                coordinator.Check(fast.enabled && slow.enabled && fastWasEnabled && slowWasEnabled,
                                  "Source CombatDirector states changed before native identity activation");
                fast.enabled = false;
                slow.enabled = false;
                coordinator.Check(!CombatDirector.instancesList.Contains(fast) && !CombatDirector.instancesList.Contains(slow),
                                  "Source CombatDirector behavior remained registered during identity activation");
            }

            public void ActivateDirectorForSceneIdentityLifecycle(GameObject requestedRoot)
            {
                RequirePreparedRoot(requestedRoot);
                coordinator.Check(!DirectorCore.instance, "Temporary DirectorCore still owns the singleton slot");
                requestedRoot.SetActive(true);
                coordinator.Check(requestedRoot.activeInHierarchy && SceneManager.GetActiveScene() == scene &&
                                      SceneInfo.instance == coordinator.sourceSceneInfoRoot.GetComponent<SceneInfo>() &&
                                      DirectorCore.instance == core,
                                  "Borrowed source Director failed exact root/Core activation");
            }

            public void ValidateDirectorAwakeWhileSuspended(GameObject requestedRoot)
            {
                RequirePreparedRoot(requestedRoot);
                var fastWaves = DirectorMoneyWaves?.GetValue(fast) as Array;
                var slowWaves = DirectorMoneyWaves?.GetValue(slow) as Array;
                var fastSelection = DirectorCardSelection?.GetValue(fast);
                var slowSelection = DirectorCardSelection?.GetValue(slow);
                var fastRng = DirectorRng?.GetValue(fast);
                var slowRng = DirectorRng?.GetValue(slow);
                coordinator.Check(
                    requestedRoot.activeInHierarchy && core && DirectorCore.instance == core && !fast.enabled && !slow.enabled &&
                        !CombatDirector.instancesList.Contains(fast) && !CombatDirector.instancesList.Contains(slow) &&
                        ReferenceEquals(fast.monsterCards, coordinator.automaticDeck) &&
                        ReferenceEquals(slow.monsterCards, coordinator.automaticDeck) && fastWaves != null && fastWaves.Length > 0 &&
                        slowWaves != null && slowWaves.Length > 0 && fastSelection != null && slowSelection != null && fastRng != null &&
                        slowRng != null,
                    "Native CombatDirector Awake state/RNG/deck initialization was not observed while behavior was suspended");
            }

            public void DirectorIdentitySpawned(NetworkIdentity identity)
            {
                coordinator.Check(rootPrepared && identity && identity.gameObject == root && identity.isServer &&
                                      identity.netId.Value != 0 && DirectorCore.instance == core,
                                  "Only the exact source Director identity may own first-stage native population");
            }

            public void BeginNativeStageBoundary()
            {
                coordinator.BeginNativeFirstStageBoundary();
            }

            public bool CaptureNativeStage(Stage stage)
            {
                return coordinator.CaptureNativeFirstStage(stage);
            }

            public void RestoreDirectorBehaviorsAfterServerStageBegin(GameObject requestedRoot)
            {
                RequirePreparedRoot(requestedRoot);
                coordinator.Check(Stage.instance && Stage.instance.isServer && Stage.instance.netId.Value != 0 &&
                                      Stage.instance.gameObject.scene == scene && fastListenerAdded && slowListenerAdded,
                                  "Native CombatDirector restore preceded the genuine server Stage-begin event");
                fast.enabled = fastWasEnabled;
                slow.enabled = slowWasEnabled;
                coordinator.Check(CombatDirector.instancesList.Contains(fast) && CombatDirector.instancesList.Contains(slow) &&
                                      ReferenceEquals(fast.monsterCards, coordinator.automaticDeck) &&
                                      ReferenceEquals(slow.monsterCards, coordinator.automaticDeck),
                                  "Full source CombatDirector behavior did not restore after server Stage begin");
            }

            public void BeforeDirectorIdentityUnspawn(NetworkIdentity identity)
            {
                coordinator.Check(rootPrepared && identity && identity.gameObject == root && identity.isServer &&
                                      DirectorCore.instance == core,
                                  "Refusing to unspawn a foreign Director identity");
                fast.enabled = false;
                slow.enabled = false;
                coordinator.Check(!CombatDirector.instancesList.Contains(fast) && !CombatDirector.instancesList.Contains(slow),
                                  "Owned CombatDirector behavior survived before identity unspawn");
            }

            public void RestoreDirectorRoot(GameObject requestedRoot)
            {
                RequirePreparedRoot(requestedRoot);
                requestedRoot.SetActive(false);
                coordinator.Check(!DirectorCore.instance, "Source DirectorCore survived deactivation");
                RollbackDirectorRoot();
            }

            void RequirePreparedRoot(GameObject requestedRoot)
            {
                coordinator.Check(rootPrepared && ReferenceEquals(requestedRoot, root) && root && root.scene == scene && fast && slow &&
                                      core && sceneDirector && coordinator.automaticDeck,
                                  "First-stage Director owner lost its exact borrowed objects");
            }
        }
    }
}
