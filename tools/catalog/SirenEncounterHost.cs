using System;
using System.Collections.Generic;
using System.Linq;
using RoR2;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Networking;
using UnityEngine.SceneManagement;

// Idle-editor fixture for pure runtime selection and rollback contracts. It
// does not activate imported content or start a game/network session.
public static class SirenEncounterHost
{
    const string OriginalSourceScenePath = "Assets/LabLoadingScene/SourceScenes/shipgraveyard/shipgraveyard.unity";

    sealed class FixtureCandidate
    {
        public string scene, name;
        public uint id;
        public bool active, validContract;
    }

    static void Require(bool condition, string message)
    {
        if (!condition)
            throw new InvalidOperationException(message);
    }

    static bool Refuses(IEnumerable<FixtureCandidate> candidates)
    {
        try
        {
            SirenEncounterContract.SelectOriginalInactiveEncounter(candidates, candidate => candidate.scene, candidate => candidate.name,
                candidate => candidate.id, candidate => candidate.active, candidate => candidate.validContract);
            return false;
        }
        catch (InvalidOperationException)
        {
            return true;
        }
    }

    /// <summary>
    /// Idle-editor fixture for pure exact source-identity selection and
    /// refusal. Native NetworkServer spawn/unspawn remains device-only.
    /// </summary>
    public static object Run()
    {
        Require(!EditorApplication.isPlaying && !EditorApplication.isCompiling && !NetworkServer.active &&
                    !NetworkClient.active,
            "Siren selection fixture requires the idle editor without a gameplay session");

        // Inspect the staged original scene additively through Unity 2021's
        // public editor API, retaining the current active scene. The
        // runtime selector is the same identity/contract gate used by Attach;
        // this fixture never activates the encounter or starts networking.
        Require(!SceneManager.GetSceneByPath(OriginalSourceScenePath).IsValid(),
            "Source-contract fixture must own its additive source scene, which is already open");
        var priorActiveScene = SceneManager.GetActiveScene();
        var sourceScene = EditorSceneManager.OpenScene(OriginalSourceScenePath, OpenSceneMode.Additive);
        int originalMapZoneCount = 0;
        try
        {
            Require(sourceScene.IsValid() && sourceScene.isLoaded,
                "Could not open staged Ship Graveyard source scene additively");
            var selectedSource = SirenEncounterSession.SelectSourceEncounter(sourceScene);
            Require(selectedSource, "Runtime selector returned no Ship Graveyard source encounter");
            var selectedIdentity = selectedSource.GetComponent<NetworkIdentity>();
            Require(selectedSource && selectedSource.scene == sourceScene &&
                        selectedSource.name == SirenEncounterContract.EncounterObjectName && !selectedSource.activeSelf &&
                        selectedIdentity && selectedIdentity.sceneId.Value == SirenEncounterContract.EncounterSceneId,
                "Runtime selector did not return the exact inactive source encounter with scene ID 10");

            var identities = sourceScene.GetRootGameObjects()
                .SelectMany(root => root.GetComponentsInChildren<NetworkIdentity>(true)).ToArray();
            var director = identities.Single(identity => identity.sceneId.Value == 2);
            Require(director && director.gameObject.name == "Director" && !director.gameObject.activeSelf &&
                        director.GetComponent<DirectorCore>() && director.GetComponent<SceneDirector>(),
                "Original Siren Director must remain inactive before the stage owner prepares source entry");
            var controllerIdentity = identities.Single(identity => identity.sceneId.Value == 11);
            var controller = controllerIdentity.GetComponent<SceneObjectToggleGroup>();
            Require(controller && !controllerIdentity.gameObject.activeSelf && controller.toggleGroups.Length == 5 &&
                        controller.toggleGroups.Select(group => group.objects.Length).SequenceEqual(new[] { 1, 2, 4, 3, 32 }),
                "Original Siren source toggle controller/group widths changed");
            var nests = controller.toggleGroups[4].objects;
            var spawners = nests.Select(nest => {
                Require(nest && nest.scene == sourceScene && !nest.activeSelf,
                    "Original source egg nest must remain inactive in the imported scene");
                var points = nest.GetComponentsInChildren<GenericSceneSpawnPoint>(true);
                Require(points.Length == 1 && points[0].enabled && points[0].gameObject.activeSelf &&
                            points[0].networkedObjectPrefab && points[0].networkedObjectPrefab.name == "VultureEggBody" &&
                            points[0].networkedObjectPrefab.GetComponent<HealthComponent>() &&
                            points[0].networkedObjectPrefab.GetComponent<NetworkIdentity>(),
                    "Each source nest must retain its one original enabled typed egg spawner");
                return points[0];
            }).ToArray();
            Require(spawners.Distinct().Count() == 32 &&
                        spawners.All(point => ReferenceEquals(point.networkedObjectPrefab, spawners[0].networkedObjectPrefab)),
                "Source nest/spawner references must be unique and share the original egg prefab");

            var originalMapZones = sourceScene.GetRootGameObjects()
                .SelectMany(root => root.GetComponentsInChildren<MapZone>(true))
                .ToArray();
            originalMapZoneCount = originalMapZones.Length;
            Require(originalMapZones.Length == 3 &&
                        originalMapZones.All(zone => zone && !zone.gameObject.activeSelf && !zone.gameObject.activeInHierarchy),
                "Source scene must retain all original MapZones disabled");
        }
        finally
        {
            if (priorActiveScene.IsValid() && priorActiveScene.isLoaded)
                SceneManager.SetActiveScene(priorActiveScene);
            if (sourceScene.IsValid() && sourceScene.isLoaded)
                Require(EditorSceneManager.CloseScene(sourceScene, true), "Fixture-owned additive source scene did not close");
        }

        var original = new FixtureCandidate
        {
            scene = SirenEncounterContract.SceneName,
            name = SirenEncounterContract.EncounterObjectName,
            id = SirenEncounterContract.EncounterSceneId,
            active = false,
            validContract = true
        };
        var selected = SirenEncounterContract.SelectOriginalInactiveEncounter(new[] { original }, candidate => candidate.scene,
            candidate => candidate.name, candidate => candidate.id, candidate => candidate.active,
            candidate => candidate.validContract);
        Require(ReferenceEquals(selected, original), "Exact original inactive source identity was not selected");

        var duplicate = new FixtureCandidate
        {
            scene = SirenEncounterContract.SceneName,
            name = SirenEncounterContract.EncounterObjectName,
            id = SirenEncounterContract.EncounterSceneId,
            active = false,
            validContract = true
        };
        var wrongScene = new FixtureCandidate
        {
            scene = "wrong-scene",
            name = SirenEncounterContract.EncounterObjectName,
            id = SirenEncounterContract.EncounterSceneId,
            active = false,
            validContract = true
        };
        var wrongName = new FixtureCandidate
        {
            scene = SirenEncounterContract.SceneName,
            name = "different-object",
            id = SirenEncounterContract.EncounterSceneId,
            active = false,
            validContract = true
        };
        var active = new FixtureCandidate
        {
            scene = SirenEncounterContract.SceneName,
            name = SirenEncounterContract.EncounterObjectName,
            id = SirenEncounterContract.EncounterSceneId,
            active = true,
            validContract = true
        };
        var wrongContract = new FixtureCandidate
        {
            scene = SirenEncounterContract.SceneName,
            name = SirenEncounterContract.EncounterObjectName,
            id = SirenEncounterContract.EncounterSceneId,
            active = false,
            validContract = false
        };
        Require(Refuses(Array.Empty<FixtureCandidate>()) && Refuses(new[] { original, duplicate }) &&
                    Refuses(new[] { wrongScene }) && Refuses(new[] { wrongName }) && Refuses(new[] { active }) &&
                    Refuses(new[] { wrongContract }),
            "Siren source identity selector did not refuse missing, ambiguous, wrong-scene/name, active, or changed contracts");
        Require(!original.active && !duplicate.active && !wrongScene.active && !wrongName.active && active.active &&
                    !wrongContract.active,
            "Selection/refusal fixture mutated candidate active state");

        bool transactionActive = false;
        bool rollbackObserved = false;
        bool spawnAttempted = false;
        bool originalFailurePreserved = false;
        try
        {
            SirenEncounterContract.RunAttachTransaction(() => transactionActive = true,
                () =>
                {
                    spawnAttempted = true;
                    throw new InvalidOperationException("fixture-injected spawn failure");
                },
                () =>
                {
                    transactionActive = false;
                    rollbackObserved = true;
                });
        }
        catch (InvalidOperationException exception)
        {
            originalFailurePreserved = exception.Message == "fixture-injected spawn failure";
        }
        Require(spawnAttempted && rollbackObserved && !transactionActive && originalFailurePreserved,
            "Failed attach did not preserve its error and restore pre-attach state");

        bool activationRollback = false;
        bool activationSpawnAttempted = false;
        bool activationFailurePreserved = false;
        try
        {
            SirenEncounterContract.RunAttachTransaction(
                () => { throw new InvalidOperationException("fixture-injected activation failure"); },
                () => activationSpawnAttempted = true,
                () =>
                {
                    activationRollback = true;
                    throw new InvalidOperationException("fixture-injected rollback failure");
                });
        }
        catch (InvalidOperationException exception)
        {
            activationFailurePreserved = exception.Message == "fixture-injected activation failure";
        }
        Require(activationRollback && !activationSpawnAttempted && activationFailurePreserved,
            "Failed activation must skip spawn, attempt rollback and preserve the activation error");

        string successfulOrder = "";
        SirenEncounterContract.RunAttachTransaction(() => successfulOrder += "activate;",
            () => successfulOrder += "spawn;", () => successfulOrder += "rollback;");
        Require(successfulOrder == "activate;spawn;", "Successful attach must activate then spawn without rollback");

        var sourceSpawners = new[] { "nest-1", "nest-2", "nest-3" };
        var selectedSpawners = new[] { "nest-1", "nest-3" };
        var eggRoots = new[] { "egg-a", "egg-b" };
        var eggIds = new uint[] { 101, 102 };
        var observed = new[] { true, true };
        Require(SirenSourceEntryContract.IsExactBijection(sourceSpawners, selectedSpawners, eggRoots, eggIds, observed, 2),
            "Exact selected source-spawner/egg bijection rejected a complete unique mapping");
        Require(!SirenSourceEntryContract.IsExactBijection(sourceSpawners, selectedSpawners, eggRoots,
                new uint[] { 101, 101 }, observed, 2),
            "Duplicate network IDs must fail the source-spawner/egg bijection");
        Require(!SirenSourceEntryContract.IsExactBijection(sourceSpawners, selectedSpawners, eggRoots,
                new uint[] { 0, 102 }, observed, 2),
            "Empty network IDs must fail the source-spawner/egg bijection");
        Require(!SirenSourceEntryContract.IsExactBijection(sourceSpawners, selectedSpawners, eggRoots,
                eggIds, new[] { true, false }, 2),
            "A source spawner without its natural disable witness must fail the bijection");
        Require(!SirenSourceEntryContract.IsExactBijection(sourceSpawners, selectedSpawners, eggRoots,
                eggIds, observed, 3),
            "Unexpected selected source-spawner count must fail the bijection");
        Require(SirenSourceEntryContract.MayRestoreToggleTarget(false, false, true, false, false) &&
                    SirenSourceEntryContract.MayRestoreToggleTarget(false, true, true, true, true) &&
                    !SirenSourceEntryContract.MayRestoreToggleTarget(false, true, true, false, true) &&
                    !SirenSourceEntryContract.MayRestoreToggleTarget(false, true, false, true, true) &&
                    !SirenSourceEntryContract.MayRestoreToggleTarget(false, true, true, true, false),
            "Source toggle cleanup must restore only the original state or the exact attempted native choice");
        Require(SirenSourceEntryContract.MayAdmitEncounter(true, true, true, true, true),
            "Exact egg mapping, drained queues, inactive ID 10 and egg input OFF should admit the original encounter");
        Require(!SirenSourceEntryContract.MayAdmitEncounter(false, true, true, true, true) &&
                    !SirenSourceEntryContract.MayAdmitEncounter(true, false, true, true, true) &&
                    !SirenSourceEntryContract.MayAdmitEncounter(true, true, false, true, true) &&
                    !SirenSourceEntryContract.MayAdmitEncounter(true, true, true, false, true) &&
                    !SirenSourceEntryContract.MayAdmitEncounter(true, true, true, true, false),
            "Encounter admission must refuse any missing egg bijection, pending queue, active ID 10, or selected egg input");

        Require(SirenSourceEntryContract.IsNaturallyRetiredEgg(true, true, false, false, true) &&
                    !SirenSourceEntryContract.IsNaturallyRetiredEgg(false, true, false, false, true) &&
                    !SirenSourceEntryContract.IsNaturallyRetiredEgg(true, false, false, false, true) &&
                    !SirenSourceEntryContract.IsNaturallyRetiredEgg(true, true, true, false, true) &&
                    !SirenSourceEntryContract.IsNaturallyRetiredEgg(true, true, false, true, true) &&
                    !SirenSourceEntryContract.IsNaturallyRetiredEgg(true, true, false, false, false),
            "Natural egg retirement needs exact captured death, destroyed objects and absent server mapping");

        return new
        {
            success = true,
            stagedSourceScene = OriginalSourceScenePath,
            importedInactiveSceneId10SelectedByRuntimeAttachPredicate = true,
            originalMapZoneCount = originalMapZoneCount,
            originalInactiveDirectorAndToggleController = true,
            originalEggSpawnerCount = 32,
            naturalRetirementRefusalPolicy = true,
            allOriginalMapZonesRemainDisabled = true,
            nativeEncounterLifecycleVerified = false,
            exactIdentitySelected = true,
            missingAmbiguousWrongSceneWrongNameActiveAndChangedContractsRefused = true,
            candidatesRemainUnchanged = true,
            failedAttachRollbackAndErrorPreservation = true,
            activationFailureSkipsSpawnAndPreservesErrorEvenIfRollbackFails = true,
            successfulActivationThenSpawnWithoutRollback = true,
            sourceEntryBijectionAndAdmissionRefusalsPassed = true,
            nativeSpawnAndUnspawn = "device-only; requires live local server"
        };
    }

}
