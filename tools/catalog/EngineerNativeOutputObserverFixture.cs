// Exact-editor source contracts and isolated Play Mode clone ownership.
// Run only reads assets; RunGuardCloneOwnership creates owned fixture clones.
// Neither method simulates native skill execution or server-spawned output.
#if UNITY_EDITOR
using System;
using System.Collections.Generic;
using RoR2;
using RoR2.Projectile;
using RoR2.Skills;
using UnityEditor;
using UnityEngine;
using UnityEngine.SceneManagement;

public static class EngineerNativeOutputObserverFixture
{
    const string Root = "Assets/WholeGame/RoR2/Base/Characters/Engi/";

    static void Require(bool condition, string message)
    {
        if (!condition)
            throw new System.InvalidOperationException(message);
    }

    static GameObject Source(string path)
    {
        var result = AssetDatabase.LoadAssetAtPath<GameObject>(Root + path);
        Require(result, "Accepted original Engineer asset missing: " + path);
        return result;
    }

    static void RequireSourceGuid(string path, string expectedGuid)
    {
        var actualGuid = AssetDatabase.AssetPathToGUID(Root + path);
        Require(string.Equals(actualGuid, expectedGuid, System.StringComparison.OrdinalIgnoreCase),
                "Accepted Engineer source GUID changed at " + path + ": " + actualGuid);
    }

    static int RejectorMembershipCount(HurtBox expected)
    {
        var count = 0;
        var rejectors = HurtBox.readOnlyAttackRejectorsList;
        for (var i = 0; i < rejectors.Count; i++)
            if (ReferenceEquals(rejectors[i], expected))
                count++;
        return count;
    }

    public static object Run()
    {
        Require(!EditorApplication.isPlaying && !EditorApplication.isCompiling && !UnityEngine.Networking.NetworkServer.active &&
                    !UnityEngine.Networking.NetworkClient.active,
                "Source-contract fixture requires an idle editor and no network session");
        var mine = Source("Projectiles/EngiMine/EngiMine.prefab");
        var bubble = Source("Projectiles/EngiBubbleShield/EngiBubbleShield.prefab");
        var turretMaster = Source("EngiTurret/EngiTurretMaster.prefab");
        var turretBody = Source("EngiTurret/EngiTurretBody.prefab");
        var secondaryFamily = AssetDatabase.LoadAssetAtPath<SkillFamily>(Root + "Engi/Skills/EngiBodySecondaryFamily.asset");
        Require(secondaryFamily && secondaryFamily.defaultVariantIndex >= 0 &&
                    secondaryFamily.defaultVariantIndex < secondaryFamily.variants.Length,
                "Original Engineer secondary skill family/default index missing");
        var expectedDefaultSecondary = AssetDatabase.LoadAssetAtPath<SkillDef>(Root + "Engi/Skills/EngiBodyPlaceMine.asset");
        var defaultSecondary = secondaryFamily.variants[secondaryFamily.defaultVariantIndex].skillDef;
        Require(expectedDefaultSecondary && ReferenceEquals(defaultSecondary, expectedDefaultSecondary),
                "Original Engineer default secondary no longer selects PlaceMine");
        RequireSourceGuid("Projectiles/EngiMine/EngiMine.prefab", "c373f0691916bae4dbee06bb49f25124");
        RequireSourceGuid("Projectiles/EngiBubbleShield/EngiBubbleShield.prefab", "4a8b0088e9b3cc545a8ebe59a3a68516");
        RequireSourceGuid("EngiTurret/EngiTurretMaster.prefab", "80481b70be8ba714b972743348575d0b");
        RequireSourceGuid("EngiTurret/EngiTurretBody.prefab", "fe55a9f937c1bec41bd41f3295298fdd");
        RequireSourceGuid("Engi/Skills/EngiBodySecondaryFamily.asset", "a73fc1ac5a0128549b246bbd538bad49");
        RequireSourceGuid("Engi/Skills/EngiBodyPlaceMine.asset", "5b5515ce7af522a49b269225d2d5003d");

        Require(mine.GetComponent<ProjectileController>() && mine.GetComponent<Deployable>(),
                "Original mine must retain projectile and deployable components");
        var mineAutoDeploy = mine.GetComponent<ProjectileDeployToOwner>();
        Require(mineAutoDeploy && mineAutoDeploy.deployableSlot == DeployableSlot.EngiMine,
                "Original mine must register under its native EngiMine slot");

        Require(bubble.GetComponent<ProjectileController>() && bubble.GetComponent<Deployable>() &&
                    bubble.GetComponent<EntityStateMachine>() && !bubble.GetComponent<ProjectileDeployToOwner>(),
                "Original shield must retain its projectile/state source and manual native state registration");

        var master = turretMaster.GetComponent<CharacterMaster>();
        Require(master && master.bodyPrefab == turretBody && turretMaster.GetComponent<MinionOwnership>(),
                "Original turret master must retain its body and native minion-ownership contract");
        Require(!EngineerNativeOutputObserver.IsExactOwnedDeployable(default(DeployableInfo), null, DeployableSlot.EngiMine),
                "Null/foreign owner must never pass deployable attribution");

        return new { sourceAssetsLoaded = true,
                     defaultSecondary = "EngiBodyPlaceMine",
                     mineSlot = mineAutoDeploy.deployableSlot.ToString(),
                     bubbleUsesNativeStateRegistration = true,
                     turretBody = turretBody.name,
                     noGameObjectsInstantiatedOrActivated = true,
                     nativeOutputNotClaimed = true };
    }

    // Run only from a later exact Play Mode fixture after the lab has rebound
    // catalog templates. This reads the adapted catalogs and stable native
    // indices; it creates no bodies, masters, network objects, or outputs.
    public static object RunAdaptedCatalogIdentity()
    {
        Require(EditorApplication.isPlaying && Application.isPlaying,
                "Adapted catalog fixture requires Play Mode with the lab catalogs loaded");
        var sourceMaster = Source("EngiTurret/EngiTurretMaster.prefab").GetComponent<CharacterMaster>();
        Require(sourceMaster && sourceMaster.bodyPrefab, "Original turret master/body source missing");

        BodyIndex expectedBody = BodyCatalog.FindBodyIndex("EngiTurretBody");
        MasterCatalog.MasterIndex expectedMaster = MasterCatalog.FindMasterIndex("EngiTurretMaster");
        Require(expectedBody != BodyIndex.None && expectedMaster != MasterCatalog.MasterIndex.none,
                "Adapted original turret catalog indices are unavailable");

        GameObject adaptedBody = BodyCatalog.GetBodyPrefab(expectedBody);
        GameObject adaptedMaster = MasterCatalog.GetMasterPrefab(expectedMaster);
        var adaptedBodyComponent = adaptedBody ? adaptedBody.GetComponent<CharacterBody>() : null;
        var adaptedMasterComponent = adaptedMaster ? adaptedMaster.GetComponent<CharacterMaster>() : null;
        var adaptedMasterBody = adaptedMasterComponent ? adaptedMasterComponent.bodyPrefab : null;
        var adaptedMasterBodyComponent = adaptedMasterBody ? adaptedMasterBody.GetComponent<CharacterBody>() : null;
        Require(adaptedBodyComponent && adaptedBodyComponent.bodyIndex == expectedBody && adaptedMaster &&
                    MasterCatalog.FindMasterIndex(adaptedMaster) == expectedMaster && adaptedMasterBodyComponent &&
                    adaptedMasterBodyComponent.bodyIndex == expectedBody,
                "Adapted catalog templates do not preserve original stable body/master indices");

        return new { originalMasterIndex = (int)expectedMaster,
                     originalBodyIndex = (int)expectedBody,
                     catalogMasterIsSourceMaster = ReferenceEquals(adaptedMaster, sourceMaster.gameObject),
                     catalogBodyIsSourceBody = ReferenceEquals(adaptedBody, sourceMaster.bodyPrefab),
                     reciprocalCatalogBodyIndexPreserved = true,
                     noBodyOrMasterInstantiated = true,
                     noNetworkOrGameplayOutputClaimed = true };
    }

    // Exact Play Mode helper for the draft's read-only guard ownership query.
    // It exercises Unity's real clone field/delegate remapping and native
    // blocker Awake; it does not create an owner, network-spawn, or claim that
    // the game deployed this object through a skill.
    public static object RunGuardCloneOwnership()
    {
        Require(EditorApplication.isPlaying && !EditorApplication.isCompiling && !UnityEngine.Networking.NetworkServer.active &&
                    !UnityEngine.Networking.NetworkClient.active,
                "Guard clone fixture requires Play Mode without a network session");
        var source = Source("Projectiles/EngiBubbleShield/EngiBubbleShield.prefab");
        EngiShieldHitGuardTemplateLease.ValidateSourceTemplate(source);
        var scene = SceneManager.GetActiveScene();
        Require(scene.IsValid() && scene.isLoaded, "Guard clone fixture requires a loaded scene");
        GameObject template = null, clone = null;
        EngiShieldHitGuardTemplateLease lease = null;
        HurtBox templateHurtBox = null;
        System.Func<HurtBox.HurtBoxAttackHitProcessorArgs, HurtBox, bool> templateNativeFilter = null;
        var cleanupErrors = new List<Exception>();
        Exception primaryError = null;
        var templateRejectorRemoved = false;
        object result = null;
        try
        {
            template = UnityEngine.Object.Instantiate(source);
            template.name = source.name;
            SceneManager.MoveGameObjectToScene(template, scene);
            var templateCollision = template.transform.Find("Collision");
            Require(templateCollision, "Source Collision child missing from fixture template");
            templateHurtBox = templateCollision.GetComponent<HurtBox>();
            Require(templateHurtBox, "Source Collision HurtBox missing from fixture template");
            templateNativeFilter = templateHurtBox.attackHitRejectionFilter;
            Require(templateNativeFilter != null, "Native template HurtBox filter was not initialized");
            Require(!EngineerNativeOutputObserver.OwnsSourceBubbleFilter(template.GetComponent<Deployable>()),
                    "Unguarded native bubble unexpectedly passed guard ownership query");
            lease = EngiShieldHitGuardTemplateLease.Acquire(template);
            Require(EngineerNativeOutputObserver.OwnsSourceBubbleFilter(template.GetComponent<Deployable>()),
                    "Guard lease did not own the exact source Collision HurtBox filter");

            clone = UnityEngine.Object.Instantiate(template);
            SceneManager.MoveGameObjectToScene(clone, scene);
            var cloneGuard = clone.GetComponent<EngiShieldHitGuard>();
            var cloneCollision = clone.transform.Find("Collision");
            var cloneHurtBox = cloneCollision ? cloneCollision.GetComponent<HurtBox>() : null;
            Require(cloneGuard && cloneCollision && cloneHurtBox &&
                        !ReferenceEquals(cloneHurtBox, templateCollision.GetComponent<HurtBox>()) &&
                        EngineerNativeOutputObserver.OwnsSourceBubbleFilter(clone.GetComponent<Deployable>()),
                    "Unity clone did not remap the exact source Collision HurtBox guard ownership");
            cloneCollision.gameObject.SetActive(true); // Fixture action only.
            Physics.SyncTransforms();
            Require(EngineerNativeOutputObserver.OwnsSourceBubbleFilter(clone.GetComponent<Deployable>()),
                    "Native Collision activation replaced or lost the owned filter");

            result = new { nativeCloneCreated = true,    exactCollisionHurtBoxRemapped = true,
                           clonedGuardOwnsFilter = true, nativeDeployableOrSkillRun = false,
                           networkSpawnObserved = false, androidMarkerOrGuardedHitNotClaimed = true };
        }
        catch (Exception error)
        {
            primaryError = error;
            throw;
        }
        finally
        {
            if (clone)
            {
                try
                {
                    UnityEngine.Object.DestroyImmediate(clone);
                }
                catch (Exception error)
                {
                    cleanupErrors.Add(error);
                }
            }
            if (lease != null)
            {
                if (clone)
                    cleanupErrors.Add(
                        new InvalidOperationException("Cannot release the guard template lease while its fixture clone remains alive"));
                else
                {
                    try
                    {
                        lease.ReleaseAfterWorldCleanup();
                    }
                    catch (Exception error)
                    {
                        cleanupErrors.Add(error);
                    }
                }
            }
            if (template)
            {
                try
                {
                    UnityEngine.Object.DestroyImmediate(template);
                }
                catch (Exception error)
                {
                    cleanupErrors.Add(error);
                }
            }

            // J617 showed that a destroyed scene stand-in with an inactive
            // Collision child can retain its exact native delegate in the
            // global rejector list. Retire only this fixture's captured native
            // filter, and only if that exact delegate still owns the slot.
            if (!ReferenceEquals(templateHurtBox, null) && templateNativeFilter != null)
            {
                try
                {
                    var current = templateHurtBox.attackHitRejectionFilter;
                    if (ReferenceEquals(current, templateNativeFilter))
                        templateHurtBox.attackHitRejectionFilter = null;
                    else if (!ReferenceEquals(current, null))
                        throw new InvalidOperationException("Fixture template filter changed to a foreign callback; preserving it");

                    templateRejectorRemoved = RejectorMembershipCount(templateHurtBox) == 0;
                    if (!templateRejectorRemoved)
                        throw new InvalidOperationException(
                            "Fixture template HurtBox remains in the native rejector list after owned cleanup");
                }
                catch (Exception error)
                {
                    cleanupErrors.Add(error);
                }
            }
            else if (templateNativeFilter != null)
                cleanupErrors.Add(
                    new InvalidOperationException("Fixture template HurtBox reference was unavailable for exact native filter cleanup"));

            if (cleanupErrors.Count > 0)
            {
                var aggregate = new AggregateException("Guard clone fixture cleanup failed", cleanupErrors);
                if (primaryError != null)
                    Debug.LogError("Guard clone fixture cleanup after primary failure: " + aggregate);
                else
                    throw new InvalidOperationException("Guard clone fixture cleanup failed", aggregate);
            }
        }
        return new { observation = result, fixtureOwnedTemplateRejectorRemoved = templateRejectorRemoved };
    }
}
#endif
