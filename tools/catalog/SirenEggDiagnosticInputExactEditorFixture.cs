// Actual C# owner/contract fixture. It uses inert fixture GameObjects and a fake
// context; it never loads a game profile, starts a server or invokes RoR2 combat.
#if UNITY_EDITOR
using System;
using System.Collections.Generic;
using System.Reflection;
using RoR2;
using UnityEditor;
using UnityEngine;
using UnityEngine.Networking;

public static class SirenEggDiagnosticInputExactEditorFixture
{
    sealed class Context : ISirenEggDiagnosticContext
    {
        public bool selected = true, assisted = true, manual, sceneActive = true, attached = true;
        public bool listener = true, nativeStarted, transporting, failed, yieldCombat, eligibleTarget = true;
        public int sceneHandle = 41, targetQueries, navigations;
        public float elapsed = 1;
        public CharacterBody target;
        public readonly List<CharacterBody> targets = new List<CharacterBody>();
        public readonly List<CharacterBody> visibleTargets = new List<CharacterBody>();
        public Vector3 lastDestination;
        public bool hasNativeRange;
        public float nativeRange = 60f;
        public bool Selected => selected;
        public bool Assisted => assisted;
        public bool ManualTakeover => manual;
        public bool SourceSceneActive => sceneActive;
        public bool SourceEncounterAttached => attached;
        public bool SourceListenerActive => listener;
        public bool NativeEncounterStarted => nativeStarted;
        public bool StageTransporting => transporting;
        public bool FirstFailure => failed;
        public int StageSceneHandle => sceneHandle;
        public float StageElapsed => elapsed;
        public bool RevalidatedSourceEggs(Vector3 position, List<CharacterBody> destination)
        {
            targetQueries++;
            destination.Clear();
            if (!SirenEggTargetSelectionPolicy.IsCandidateCountSupported(targets.Count))
                return false;
            if (!eligibleTarget)
                return true;
            if (targets.Count == 0)
            {
                if (target)
                    destination.Add(target);
                return true;
            }
            destination.AddRange(targets);
            return true;
        }
        public bool IsCurrentSourceEgg(CharacterBody candidate) => eligibleTarget && candidate &&
                                                                   (candidate == target || targets.Contains(candidate));
        public bool ShouldYieldToExistingWorldCombat(CharacterBody player) => yieldCombat;
        public void NavigateWorldInput(CharacterBody player, NovaInputBridge bridge, Vector3 destination, float stopDistance,
                                       string targetName, float time)
        {
            navigations++;
            lastDestination = destination;
            bridge.movement = Vector2.right;
        }
        public Vector3 WorldCombatAimPoint(CharacterBody body, Vector3 origin, out bool visible)
        {
            visible = visibleTargets.Count == 0 || visibleTargets.Contains(body);
            return body.transform.position + Vector3.up;
        }
        // Only the range case supplies synthetic geometry; no native tracker or
        // stage stall clock is created by this input-ownership fixture.
        public bool TryReadNavigationTrigger(CharacterBody player, CharacterBody egg, out float eggDistance,
                                             out float trackerMaximumDistance)
        {
            if (hasNativeRange && player && player.inputBank && egg)
            {
                eggDistance = Vector3.Distance(player.inputBank.aimOrigin, egg.transform.position + Vector3.up);
                trackerMaximumDistance = nativeRange;
                return true;
            }
            eggDistance = trackerMaximumDistance = float.NaN;
            return false;
        }
        public float NavigationObjectiveStalledSeconds => float.NaN;
        public ISirenNavigationObservationReader CreateNavigationObservationReader(CharacterBody player,
                                                                                    NovaInputBridge bridge) => null;
    }

    public static object Run()
    {
        Require(!EditorApplication.isPlaying && !EditorApplication.isCompiling && !UnityEngine.Networking.NetworkServer.active &&
                    !UnityEngine.Networking.NetworkClient.active,
                "Fixture requires idle editor with no game/network session");
        VerifyImportedSourceEggPrefab();
        VerifyNavigationObservationSeams();
        VerifyNativeListeningRegistrationFieldContract();
        VerifyNativeRegisteredMemberContract();
        VerifyCandidateContract();
        VerifyCombatThreatPolicy();
        VerifyTemporaryYieldRecoveryAndNativeStartLatch();
        VerifyVisibleRegisteredEggPreference();
        VerifyNativeRangeApproach();
        VerifyProducerFramePreparationAndDefaultOff();
        VerifyJumpLeaseOwnership();
        VerifySelectionDisableTransition();
        VerifyEveryTerminalLatch();
        return new { sourcePrefabAssetContractCases = 1,
                     sourceListenerRegistrationFieldContract = true,
                     sourceNativeMembershipCases = 3,
                     sourcePredicateCases = 17,
                     combatThreatPredicateCases = 6,
                     temporaryNoTargetAndCombatYieldRecover = true,
                     nativeStartStopsOnLiveGateAndLatches = true,
                     visibleRegisteredEggPreferredOverOccludedNearest = true,
                     nativeRangeSelectionApproachAndHold = true,
                     terminalStopReasonsTested = 8,
                     defaultOffInputNoninterference = true,
                     selectionDisabledOutstandingLeaseReleased = true,
                     freshSameValueTerminalProducerPreserved = true,
                     noProfileServerOrCombatCalls = true,
                     navigationObservationContextRemainsInert = true,
                     navigationObservationPolicyCases = 3 };
    }

    static void VerifyImportedSourceEggPrefab()
    {
        const string assetPath = "Assets/WholeGame/RoR2/Base/Scenes/shipgraveyard/VultureEgg/VultureEggBody.prefab";
        const string expectedGuid = "ee1b5efb4a4dbbb498e0cbb756a54118";
        Require(AssetDatabase.AssetPathToGUID(assetPath) == expectedGuid, "Imported VultureEggBody prefab GUID changed");
        GameObject prefab = AssetDatabase.LoadAssetAtPath<GameObject>(assetPath);
        Require(prefab && prefab.name == "VultureEggBody" && prefab.activeSelf,
                "Original VultureEggBody source prefab is absent or inactive");

        CharacterBody body = prefab.GetComponent<CharacterBody>();
        HealthComponent health = prefab.GetComponent<HealthComponent>();
        NetworkIdentity identity = prefab.GetComponent<NetworkIdentity>();
        Require(body && body.enabled && body.bodyIndex == BodyIndex.None,
                "Source egg body contract changed; runtime catalog must assign its body index");
        Require(health && health.enabled && identity && identity.enabled && !identity.assetId.Equals(default(NetworkHash128)) &&
                    identity.sceneId.Value == 0,
                "Source egg health or network asset identity is absent/invalid");
        Require(body.GetComponent<NetworkIdentity>() == identity && body.GetComponent<HealthComponent>() == health,
                "Source body, health, and NetworkIdentity no longer share the prefab root");

        HurtBoxGroup[] groups = prefab.GetComponentsInChildren<HurtBoxGroup>(true);
        HurtBox[] hurtBoxes = prefab.GetComponentsInChildren<HurtBox>(true);
        Require(groups.Length == 1 && groups[0] && groups[0].enabled && groups[0].mainHurtBox && groups[0].hurtBoxes != null &&
                    groups[0].hurtBoxes.Length == 1 && groups[0].hurtBoxes[0] == groups[0].mainHurtBox,
                "Source egg HurtBoxGroup/main HurtBox shape changed");
        HurtBox main = groups[0].mainHurtBox;
        Require(hurtBoxes.Length == 1 && hurtBoxes[0] == main && main.enabled && main.isBullseye && main.gameObject.activeSelf &&
                    AllSourceParentsActive(main.transform, prefab.transform) && main.healthComponent == health &&
                    main.hurtBoxGroup == groups[0],
                "Source egg main HurtBox is not the active bullseye linked to its root HealthComponent/group");
        Require(body.transform.IsChildOf(prefab.transform) && groups[0].transform.IsChildOf(prefab.transform),
                "Source egg body/group hierarchy changed");
        // LoadAssetAtPath returns the serialized prefab asset. This fixture
        // reads it only; it never instantiates or activates the source prefab.
    }

    static bool AllSourceParentsActive(Transform child, Transform root)
    {
        for (Transform current = child; current; current = current.parent)
        {
            if (!current.gameObject.activeSelf)
                return false;
            if (current == root)
                return true;
        }
        return false;
    }

    static void VerifyNavigationObservationSeams()
    {
        var context = new Context();
        float distance, trackerMaximumDistance;
        Require(!context.TryReadNavigationTrigger(null, null, out distance, out trackerMaximumDistance) &&
                    float.IsNaN(distance) && float.IsNaN(trackerMaximumDistance),
                "Synthetic fixture must not publish a live navigation trigger");
        Require(float.IsNaN(context.NavigationObjectiveStalledSeconds) &&
                    context.CreateNavigationObservationReader(null, null) == null,
                "Synthetic fixture must not claim live stage or world observation");
        Require(SirenNavigationObservationPolicy.ShouldStart(true, 398, 167f, 60f, .5f) &&
                    !SirenNavigationObservationPolicy.ShouldStart(false, 398, 167f, 60f, .5f) &&
                    !SirenNavigationObservationPolicy.ShouldStart(true, 0, 167f, 60f, .5f) &&
                    !SirenNavigationObservationPolicy.ShouldStart(true, 398, float.NaN, 60f, .5f) &&
                    !SirenNavigationObservationPolicy.ShouldStart(true, 398, 167f, 60f, float.NaN),
                "Compiled observation policy range/identity/time guards changed");
        var progressing = new SirenNavigationObservationRecorder();
        Require(!progressing.ObserveTrigger(true, true, 398, 167f, 60f, 0f, 1f) &&
                    progressing.ObserveTrigger(true, true, 398, 167f, 60f, 0f, 1.5f) &&
                    progressing.report.triggerObjectiveStallAvailable &&
                    progressing.report.triggerObjectiveStalledSeconds == 0f,
                "Progressing out-of-range route should arm and preserve zero stall");
        var unknownStall = new SirenNavigationObservationRecorder();
        Require(!unknownStall.ObserveTrigger(true, true, 399, 167f, 60f, float.NaN, 2f) &&
                    unknownStall.ObserveTrigger(true, true, 399, 167f, 60f, float.NaN, 2.5f) &&
                    !unknownStall.report.triggerObjectiveStallAvailable,
                "Unknown stall should not block range observation or be fabricated");
    }

    static void VerifyCandidateContract()
    {
        var valid = new SirenEggCandidateEvidence { ownerLive = true,
                                                    candidateSceneLoaded = true,
                                                    candidateSceneHandle = 7,
                                                    ownerSceneHandle = 7,
                                                    activeSceneHandle = 7,
                                                    bodyName = "VultureEggBody(Clone)",
                                                    bodyIndex = 12,
                                                    expectedBodyIndex = 12,
                                                    nativeRegisteredEggCount = 6,
                                                    nativeRegistrationObserved = true,
                                                    nativeListeningInstanceMatches = true,
                                                    nativeRegisteredListContainsCandidate = true,
                                                    identityIsServer = true,
                                                    hasNonzeroNetworkId = true,
                                                    sourceAssetIdMatches = true,
                                                    networkMapOwnsExactObject = true,
                                                    healthExists = true,
                                                    healthAlive = true,
                                                    hurtBoxGroupExists = true,
                                                    mainHurtBoxExists = true,
                                                    groupOwnsMainHurtBox = true,
                                                    mainHurtBoxBullseye = true,
                                                    mainHurtBoxEnabled = true,
                                                    mainHurtBoxActive = true,
                                                    hurtBoxUsesSameHealthComponent = true };
        Require(SirenEggSourceContract.IsEligible(valid), "Exact source candidate contract rejected a complete source instance");
        Require(!SirenEggSourceContract.IsEligible(Change(valid,
                                                          x =>
                                                          {
                                                              x.nativeRegistrationObserved = false;
                                                              return x;
                                                          })),
                "Pre-registration egg candidate was eligible for diagnostic input");
        Require(!SirenEggSourceContract.IsEligible(Change(valid,
                                                          x =>
                                                          {
                                                              x.nativeRegisteredEggCount = 0;
                                                              return x;
                                                          })),
                "Zero registered egg slots synthesized candidate eligibility");
        Require(!SirenEggSourceContract.IsEligible(Change(valid,
                                                          x =>
                                                          {
                                                              x.nativeRegisteredListContainsCandidate = false;
                                                              return x;
                                                          })),
                "A later-spawned or otherwise unregistered egg was eligible for diagnostic input");
        Require(!SirenEggSourceContract.IsEligible(Change(valid,
                                                          x =>
                                                          {
                                                              x.nativeListeningInstanceMatches = false;
                                                              return x;
                                                          })),
                "A replacement native Listening instance inherited a prior registration snapshot");
        Require(!SirenEggSourceContract.IsEligible(Change(valid,
                                                          x =>
                                                          {
                                                              x.ownerLive = false;
                                                              return x;
                                                          })),
                "Stale scene owner was accepted");
        Require(!SirenEggSourceContract.IsEligible(Change(valid,
                                                          x =>
                                                          {
                                                              x.candidateSceneHandle = 8;
                                                              return x;
                                                          })),
                "Foreign scene target was accepted");
        Require(!SirenEggSourceContract.IsEligible(Change(valid,
                                                          x =>
                                                          {
                                                              x.activeSceneHandle = 8;
                                                              return x;
                                                          })),
                "Non-active stage target was accepted");
        Require(!SirenEggSourceContract.IsEligible(Change(valid,
                                                          x =>
                                                          {
                                                              x.bodyIndex = 13;
                                                              return x;
                                                          })),
                "Wrong body index was accepted");
        Require(!SirenEggSourceContract.IsEligible(Change(valid,
                                                          x =>
                                                          {
                                                              x.healthAlive = false;
                                                              return x;
                                                          })),
                "Dead target was accepted");
        Require(!SirenEggSourceContract.IsEligible(Change(valid,
                                                          x =>
                                                          {
                                                              x.networkMapOwnsExactObject = false;
                                                              return x;
                                                          })),
                "Foreign/stale net object was accepted");
        Require(!SirenEggSourceContract.IsEligible(Change(valid,
                                                          x =>
                                                          {
                                                              x.identityIsServer = false;
                                                              return x;
                                                          })),
                "Unspawned client target was accepted");
        Require(!SirenEggSourceContract.IsEligible(Change(valid,
                                                          x =>
                                                          {
                                                              x.groupOwnsMainHurtBox = false;
                                                              return x;
                                                          })),
                "Mismatched native main HurtBox was accepted");
        Require(!SirenEggSourceContract.IsEligible(Change(valid,
                                                          x =>
                                                          {
                                                              x.hurtBoxUsesSameHealthComponent = false;
                                                              return x;
                                                          })),
                "Foreign HealthComponent linkage was accepted");
        Require(!SirenEggSourceContract.IsEligible(Change(valid,
                                                          x =>
                                                          {
                                                              x.hasNonzeroNetworkId = false;
                                                              return x;
                                                          })),
                "A stale zero-netId target was accepted");
        Require(!SirenEggSourceContract.IsEligible(Change(valid,
                                                          x =>
                                                          {
                                                              x.sourceAssetIdMatches = false;
                                                              return x;
                                                          })),
                "A different source prefab/asset identity was accepted");
        Require(!SirenEggSourceContract.IsEligible(Change(valid,
                                                          x =>
                                                          {
                                                              x.candidateSceneLoaded = false;
                                                              return x;
                                                          })),
                "An unloaded-scene target was accepted");
    }

    static void VerifyNativeListeningRegistrationFieldContract()
    {
        Type listeningType = typeof(EntityStates.Missions.SuperRoboBallEncounter.Listening);
        FieldInfo registered = listeningType.GetField("hasRegisteredEggs", BindingFlags.Instance | BindingFlags.NonPublic);
        FieldInfo eggs = listeningType.GetField("eggList", BindingFlags.Instance | BindingFlags.NonPublic);
        MethodInfo register = listeningType.GetMethod("RegisterEggs", BindingFlags.Instance | BindingFlags.NonPublic);
        Require(registered != null && registered.IsPrivate && registered.FieldType == typeof(bool),
                "Accepted native Listening registration flag contract changed");
        Require(eggs != null && eggs.IsPrivate && eggs.FieldType == typeof(List<GameObject>),
                "Accepted native Listening egg-list contract changed");
        Require(register != null && register.IsPrivate && register.GetParameters().Length == 0,
                "Accepted native Listening registration method contract changed");
        // Metadata inspection only: the fixture neither creates a Listening
        // instance nor writes/invokes its native registration state.
    }

    static void VerifyNativeRegisteredMemberContract()
    {
        const string assetPath = "Assets/WholeGame/RoR2/Base/Scenes/shipgraveyard/VultureEgg/VultureEggBody.prefab";
        GameObject sourceEggAsset = AssetDatabase.LoadAssetAtPath<GameObject>(assetPath);
        Require(sourceEggAsset, "Native membership fixture lost the accepted source prefab asset");
        var nativeList = new List<GameObject> { sourceEggAsset };
        Require(SirenEggSourceContract.IsExactNativeRegisteredMember(nativeList, sourceEggAsset),
                "Exact current native registered object was rejected");
        Require(!SirenEggSourceContract.IsExactNativeRegisteredMember(new List<GameObject>(), sourceEggAsset),
                "An egg absent from native registration was accepted");
        GameObject laterEgg = new GameObject("VultureEggBody(Clone)");
        try
        {
            Require(!SirenEggSourceContract.IsExactNativeRegisteredMember(nativeList, laterEgg),
                    "A later same-name egg absent from the native list was accepted");
        }
        finally
        {
            UnityEngine.Object.DestroyImmediate(laterEgg);
        }
        // The source prefab asset is referenced only; it is never instantiated
        // or activated, and no native registration method/state is invoked.
    }

    static void VerifyCombatThreatPolicy()
    {
        var near =
            new SirenCombatThreatEvidence { bodyLive = true,    masterLive = true,         healthAlive = true,   playerTeamKnown = true,
                                            hostileTeam = true, insideSourceBounds = true, distanceSqr = 399.99f };
        Require(SirenCombatThreatContract.IsNearbyHostileDirectorThreat(near),
                "Nearby live hostile source actor did not yield the Siren input frame");
        Require(!SirenCombatThreatContract.IsNearbyHostileDirectorThreat(new SirenCombatThreatEvidence()),
                "No threat should not yield the Siren input frame");
        Require(!SirenCombatThreatContract.IsNearbyHostileDirectorThreat(ChangeThreat(near,
                                                                                      e =>
                                                                                      {
                                                                                          e.distanceSqr = 400f;
                                                                                          return e;
                                                                                      })),
                "A threat at or beyond the 20 m boundary should not yield the Siren input frame");
        Require(!SirenCombatThreatContract.IsNearbyHostileDirectorThreat(ChangeThreat(near,
                                                                                      e =>
                                                                                      {
                                                                                          e.healthAlive = false;
                                                                                          return e;
                                                                                      })),
                "A dead director body should not yield the Siren input frame");
        Require(!SirenCombatThreatContract.IsNearbyHostileDirectorThreat(ChangeThreat(near,
                                                                                      e =>
                                                                                      {
                                                                                          e.hostileTeam = false;
                                                                                          return e;
                                                                                      })),
                "A friendly director actor should not yield the Siren input frame");
        Require(!SirenCombatThreatContract.IsNearbyHostileDirectorThreat(ChangeThreat(near,
                                                                                      e =>
                                                                                      {
                                                                                          e.insideSourceBounds = false;
                                                                                          return e;
                                                                                      })),
                "An out-of-bounds director actor should not yield the Siren input frame");
    }

    static SirenCombatThreatEvidence ChangeThreat(SirenCombatThreatEvidence value,
                                                  Func<SirenCombatThreatEvidence, SirenCombatThreatEvidence> mutation)
    {
        return mutation(value);
    }

    static SirenEggCandidateEvidence Change(SirenEggCandidateEvidence value,
                                            Func<SirenEggCandidateEvidence, SirenEggCandidateEvidence> mutation)
    {
        return mutation(value);
    }

    static void VerifyTemporaryYieldRecoveryAndNativeStartLatch()
    {
        var objects = new FixtureObjects();
        var context = new Context();
        var report = new SirenEggInputReport();
        var owner = new SirenEggDiagnosticInput(context, report);
        try
        {
            objects.Setup();
            context.target = objects.target;
            context.eligibleTarget = false;
            Require(!owner.Apply(objects.player, objects.bridge, true) && !report.terminal &&
                        report.stopReason == "no-current-source-egg-target",
                    "Missing candidate should yield temporarily");

            context.eligibleTarget = true;
            objects.BeginFreshProducerFrame();
            Require(owner.Apply(objects.player, objects.bridge, true) && report.active && context.navigations == 1,
                    "Valid current candidate did not recover after a temporary no-target yield");

            context.yieldCombat = true;
            objects.BeginFreshProducerFrame();
            Require(!owner.Apply(objects.player, objects.bridge, true) && !report.terminal && context.navigations == 1,
                    "Existing combat should temporarily own its frame");
            context.yieldCombat = false;
            objects.BeginFreshProducerFrame();
            Require(owner.Apply(objects.player, objects.bridge, true) && context.navigations == 2,
                    "Siren objective did not resume after existing combat released its frame");

            context.manual = true;
            objects.bridge.diagnosticInput = false;
            objects.BeginFreshProducerFrame();
            Require(!owner.Apply(objects.player, objects.bridge, true) && !report.terminal && context.navigations == 2,
                    "Manual takeover did not temporarily release the owner");
            context.manual = false;
            objects.bridge.diagnosticInput = true;
            objects.BeginFreshProducerFrame();
            Require(owner.Apply(objects.player, objects.bridge, true) && context.navigations == 3,
                    "Siren objective did not resume after manual takeover ended");

            // This live context flips after the previous ordinary input frame and
            // before a hypothetical 0.5 s observer sample. Apply must stop now.
            context.nativeStarted = true;
            objects.BeginFreshProducerFrame();
            // The current frame's legitimate producer happens to emit the same
            // movement value as the previous Siren overlay. Fresh capture must
            // preserve it when the live native-start boundary stops this owner.
            objects.bridge.movement = Vector2.right;
            Require(!owner.Apply(objects.player, objects.bridge, true) && report.terminal &&
                        report.stopReason == "native-encounter-started" && objects.bridge.movement == Vector2.right,
                    "Live hasSpawnedServer boundary failed or overwrote a same-value fresh producer");
            int countAtStop = context.navigations;
            context.nativeStarted = false;
            context.listener = true;
            objects.BeginFreshProducerFrame();
            Require(!owner.Apply(objects.player, objects.bridge, true) && context.navigations == countAtStop &&
                        report.stopReason == "native-encounter-started",
                    "Restored context resumed after terminal native start");
        }
        finally
        {
            owner.Dispose();
            objects.Dispose();
        }
    }

    static void VerifyVisibleRegisteredEggPreference()
    {
        var objects = new FixtureObjects();
        var context = new Context();
        var report = new SirenEggInputReport();
        var owner = new SirenEggDiagnosticInput(context, report);
        GameObject visibleObject = null;
        try
        {
            objects.Setup();
            context.target = objects.target;
            objects.target.transform.position = new Vector3(1, 0, 0);
            visibleObject = FixtureObjects.NewBodyObject("VultureEggBody visible candidate");
            var visibleBody = visibleObject.GetComponent<CharacterBody>();
            visibleObject.transform.position = new Vector3(8, 0, 0);
            context.targets.Add(objects.target);
            context.targets.Add(visibleBody);
            context.visibleTargets.Add(visibleBody);
            Require(owner.Apply(objects.player, objects.bridge, true) && report.active,
                    "Visible registered-source candidate did not receive ordinary input");
            Require(context.lastDestination == visibleObject.transform.position && objects.bridge.diagnosticPrimary,
                    "Closer occluded egg displaced the farther visible native source target");
        }
        finally
        {
            owner.Dispose();
            objects.Dispose();
            if (visibleObject)
                UnityEngine.Object.DestroyImmediate(visibleObject);
        }
    }

    static void VerifyNativeRangeApproach()
    {
        var objects = new FixtureObjects();
        var context = new Context { hasNativeRange = true };
        var report = new SirenEggInputReport();
        var owner = new SirenEggDiagnosticInput(context, report);
        GameObject distantObject = null;
        try
        {
            objects.Setup();
            context.target = objects.target;
            objects.target.transform.position = new Vector3(3, 0, 0);
            distantObject = FixtureObjects.NewBodyObject("VultureEggBody distant candidate");
            var distant = distantObject.GetComponent<CharacterBody>();
            distantObject.transform.position = new Vector3(167, 0, 0);
            context.targets.Add(objects.target);
            context.targets.Add(distant);
            context.visibleTargets.Add(distant);
            Require(owner.Apply(objects.player, objects.bridge, true) && report.active && context.navigations == 1,
                    "No attackable egg did not preserve ordinary approach");
            Require(context.lastDestination == objects.target.transform.position && !objects.bridge.diagnosticPrimary &&
                        !report.lastTargetVisible && report.lastTargetNativeRangeKnown,
                    "Distant visible out-of-range egg displaced the nearer approach");

            // An attackable egg may be farther than an occluded approach target.
            distantObject.transform.position = new Vector3(20, 0, 0);
            objects.BeginFreshProducerFrame();
            Require(owner.Apply(objects.player, objects.bridge, true) && objects.bridge.diagnosticPrimary &&
                        objects.bridge.movement == Vector2.zero && !objects.bridge.diagnosticSprint && context.navigations == 1,
                    "In-range visible egg did not hold a native firing position");
            Require(report.lastTargetVisible && report.lastTargetPrimaryRequested && report.lastTargetNativeDistance <= context.nativeRange,
                    "Range-qualified primary report disagrees with its input");

            // Range comes from the live source limit, without a cached 60 m assumption.
            context.nativeRange = 1;
            context.targets.Remove(objects.target);
            objects.BeginFreshProducerFrame();
            Require(owner.Apply(objects.player, objects.bridge, true) && !objects.bridge.diagnosticPrimary &&
                        context.navigations == 2 && report.lastTargetVisible &&
                        report.lastPrimaryRequestReason == "outside-native-primary-range",
                    "A visible out-of-range egg was fired at or failed to approach");
            owner.Dispose();
            Require(objects.bridge.movement == Vector2.zero && !objects.bridge.diagnosticPrimary && report.cleaned,
                    "Range approach retained its owned input after disposal");
        }
        finally
        {
            owner.Dispose();
            objects.Dispose();
            if (distantObject)
                UnityEngine.Object.DestroyImmediate(distantObject);
        }
    }

    static void VerifyProducerFramePreparationAndDefaultOff()
    {
        var objects = new FixtureObjects();
        var context = new Context();
        var report = new SirenEggInputReport();
        var owner = new SirenEggDiagnosticInput(context, report);
        try
        {
            objects.Setup();
            context.target = objects.target;
            objects.bridge.movement = Vector2.left;
            SirenEggDiagnosticInput.PrepareProducerFrameForSelection(false, owner, objects.bridge);
            Require(objects.bridge.movement == Vector2.left && !report.active,
                    "Default-off preparation changed bridge input without an owned lease");
            objects.bridge.movement = Vector2.zero;
            Require(owner.Apply(objects.player, objects.bridge, true) && report.active,
                    "Producer preparation fixture could not establish an owner lease");
            SirenEggDiagnosticInput.PrepareProducerFrameForSelection(true, owner, objects.bridge);
            Require(!report.active && objects.bridge.movement == Vector2.zero,
                    "Selected preparation did not release only the previous Siren overlay");
            objects.BeginFreshProducerFrame();
            Require(owner.Apply(objects.player, objects.bridge, true) && report.active,
                    "Siren owner did not resume after a fresh ordinary producer frame");
        }
        finally
        {
            owner.Dispose();
            objects.Dispose();
        }
    }

    static void VerifyJumpLeaseOwnership()
    {
        var go = new GameObject("Siren jump lease fixture");
        go.SetActive(false);
        try
        {
            var bridge = go.AddComponent<NovaInputBridge>();
            bridge.diagnosticInput = true;
            var lease = new SirenEggInputLease();
            lease.CaptureProducerValues(bridge, true);
            bridge.DiagnosticJump(true);
            lease.CaptureOwnedOverlay(bridge);
            lease.Release(bridge);
            Require(!bridge.diagnosticJumpRequest && !bridge.CaptureDiagnosticJump().Pending,
                    "Owned unconsumed jump remained queued after release");

            bridge.Neutral();
            bridge.DiagnosticJump(true);
            bridge.DiagnosticJump(false); // Producer has an unconsumed pulse but no hold.
            lease.CaptureProducerValues(bridge, true);
            bridge.DiagnosticJump(true); // Siren adds a coalesced edge.
            lease.CaptureOwnedOverlay(bridge);
            lease.Release(bridge);
            Require(!bridge.diagnosticJumpRequest && bridge.CaptureDiagnosticJump().Pending,
                    "Releasing Siren's edge erased the producer's still-pending pulse");

            bridge.Neutral();
            bridge.DiagnosticJump(true);
            bridge.DiagnosticJump(false);
            lease.CaptureProducerValues(bridge, true);
            bridge.DiagnosticJump(true);
            lease.CaptureOwnedOverlay(bridge);
            // Model only the bridge's fixed-consumption boundary; no gameplay or
            // actual Unity scheduling is claimed by this idle fixture.
            typeof(NovaInputBridge).GetField("jumpLatched", BindingFlags.Instance | BindingFlags.NonPublic).SetValue(bridge, false);
            bridge.fixedTicks++;
            lease.Release(bridge);
            Require(!bridge.diagnosticJumpRequest && !bridge.CaptureDiagnosticJump().Pending,
                    "Release duplicated a producer pulse already consumed by a fixed tick");

            bridge.Neutral();
            lease.CaptureProducerValues(bridge, true);
            bridge.DiagnosticJump(true);
            lease.CaptureOwnedOverlay(bridge);
            bridge.DiagnosticJump(true); // Later same-value write must survive.
            lease.Release(bridge);
            Require(bridge.diagnosticJumpRequest && bridge.CaptureDiagnosticJump().Pending,
                    "Release overwrote a later producer's same-value held write");

            bridge.Neutral();
            bridge.DiagnosticJump(true);
            bridge.DiagnosticJump(false);
            lease.CaptureProducerValues(bridge, true);
            lease.CaptureOwnedOverlay(bridge); // No jump write belongs to Siren.
            lease.Release(bridge);
            Require(bridge.CaptureDiagnosticJump().Pending, "Unchanged overlay cleared a producer latch");

            bridge.Neutral();
            lease.CaptureProducerValues(bridge, true);
            bridge.DiagnosticJump(true);
            lease.CaptureOwnedOverlay(bridge);
            bridge.Neutral();
            lease.Release(bridge);
            Require(!bridge.diagnosticJumpRequest && !bridge.CaptureDiagnosticJump().Pending,
                    "Release resurrected input after a later Neutral call");
        }
        finally
        {
            UnityEngine.Object.DestroyImmediate(go);
        }
    }

    static void VerifySelectionDisableTransition()
    {
        var objects = new FixtureObjects();
        var context = new Context();
        var report = new SirenEggInputReport();
        var owner = new SirenEggDiagnosticInput(context, report);
        try
        {
            objects.Setup();
            context.target = objects.target;
            Require(owner.Apply(objects.player, objects.bridge, true) && report.active,
                    "Selection-disable fixture could not establish an owner lease");
            Vector2 priorOverlayMovement = objects.bridge.movement;
            Vector3 priorOverlayAim = objects.bridge.diagnosticAim;
            Require(priorOverlayMovement != Vector2.zero && priorOverlayAim != Vector3.zero,
                    "Selection-disable fixture expected nonzero owned channels");

            context.selected = false;
            SirenEggDiagnosticInput.PrepareProducerFrameForSelection(false, owner, objects.bridge);
            Require(!report.active && objects.bridge.movement == Vector2.zero && objects.bridge.diagnosticAim == Vector3.zero,
                    "Disable transition did not release its prior owned overlay before producers");

            // The ordinary producer leaves movement untouched but writes a
            // fresh aim equal to the prior Siren overlay. Value equality alone
            // must not make terminal cleanup erase that current producer.
            objects.bridge.diagnosticAim = priorOverlayAim;
            Require(!owner.Apply(objects.player, objects.bridge, true) && report.terminal && report.stopReason == "selection-disabled",
                    "Disabled selection did not terminate after the producer frame");
            Require(objects.bridge.movement == Vector2.zero && objects.bridge.diagnosticAim == priorOverlayAim,
                    "Selection-disable cleanup clobbered a fresh same-value producer or left an unwritten old channel");
        }
        finally
        {
            owner.Dispose();
            objects.Dispose();
        }
    }

    static void VerifyEveryTerminalLatch()
    {
        for (int kind = 0; kind < 8; kind++)
        {
            var objects = new FixtureObjects();
            var context = new Context();
            var report = new SirenEggInputReport();
            var owner = new SirenEggDiagnosticInput(context, report);
            try
            {
                objects.Setup();
                context.target = null; // Start the owner at the source without issuing input.
                owner.Apply(objects.player, objects.bridge, true);
                switch (kind)
                {
                case 0:
                    context.failed = true;
                    break;
                case 1:
                    context.transporting = true;
                    break;
                case 2:
                    context.sceneActive = false;
                    break;
                case 3:
                    context.attached = false;
                    break;
                case 4:
                    context.sceneHandle++;
                    break;
                case 5:
                    context.nativeStarted = true;
                    break;
                case 6:
                    context.listener = false;
                    break;
                case 7:
                    context.elapsed = 1 + SirenEggDiagnosticInput.MaximumStageSeconds;
                    break;
                }
                objects.BeginFreshProducerFrame();
                Require(!owner.Apply(objects.player, objects.bridge, true) && report.terminal,
                        "Terminal context did not latch for case " + kind);
                string firstStop = report.stopReason;
                int navigationsAtStop = context.navigations;
                context.failed = context.transporting = false;
                context.sceneActive = context.attached = context.listener = true;
                context.nativeStarted = false;
                context.sceneHandle = 41;
                context.elapsed = 2;
                context.target = objects.target;
                objects.BeginFreshProducerFrame();
                Require(!owner.Apply(objects.player, objects.bridge, true) && context.navigations == navigationsAtStop &&
                            report.stopReason == firstStop,
                        "Restored context resumed or rewrote the first stop for case " + kind);
            }
            finally
            {
                owner.Dispose();
                objects.Dispose();
            }
        }
    }

    sealed class FixtureObjects : IDisposable
    {
        GameObject playerObject, targetObject;
        public CharacterBody player, target;
        public InputBankTest bank;
        public NovaInputBridge bridge;

        public void Setup()
        {
            playerObject = NewBodyObject("Diagnostic input owner fixture");
            targetObject = NewBodyObject("VultureEggBody fixture candidate");
            player = playerObject.GetComponent<CharacterBody>();
            target = targetObject.GetComponent<CharacterBody>();
            bank = playerObject.GetComponent<InputBankTest>();
            bridge = playerObject.AddComponent<NovaInputBridge>();
            bridge.bank = bank;
            bridge.diagnosticInput = true;
        }

        public static GameObject NewBodyObject(string name)
        {
            var go = new GameObject(name);
            go.SetActive(false);
            try
            {
                var bank = go.AddComponent<InputBankTest>();
                // InputBankTest requires and automatically adds CharacterBody.
                var body = go.GetComponent<CharacterBody>();
                Require(bank && body, "Fixture input bank/body dependencies missing");
                var bankField =
                    typeof(CharacterBody).GetField("<inputBank>k__BackingField", BindingFlags.Instance | BindingFlags.NonPublic);
                Require(bankField != null, "Accepted CharacterBody input-bank cache changed");
                bankField.SetValue(body, bank);
                var coreField = typeof(CharacterBody).GetField("<coreTransform>k__BackingField", BindingFlags.Instance | BindingFlags.NonPublic);
                Require(coreField != null, "Accepted CharacterBody core cache changed");
                coreField.SetValue(body, go.transform);
                var bankBody = typeof(InputBankTest).GetField("characterBody", BindingFlags.Instance | BindingFlags.NonPublic);
                Require(bankBody != null, "Accepted InputBankTest body cache changed");
                bankBody.SetValue(bank, body);
                return go;
            }
            catch
            {
                UnityEngine.Object.DestroyImmediate(go);
                throw;
            }
        }

        public void BeginFreshProducerFrame()
        {
            bridge.movement = Vector2.zero;
            bridge.aim = Vector2.zero;
            bridge.diagnosticAim = Vector3.zero;
            bridge.diagnosticSprint = false;
            bridge.diagnosticPrimary = false;
            bridge.DiagnosticJump(false);
            bridge.fixedTicks++;
        }

        public void Dispose()
        {
            if (playerObject)
                UnityEngine.Object.DestroyImmediate(playerObject);
            if (targetObject)
                UnityEngine.Object.DestroyImmediate(targetObject);
        }
    }

    static void Require(bool condition, string message)
    {
        if (!condition)
            throw new InvalidOperationException(message);
    }
}
#endif
