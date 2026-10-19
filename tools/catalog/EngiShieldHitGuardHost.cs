using System;
using System.Collections.Generic;
using System.Reflection;
using RoR2;
using UnityEditor;
using UnityEngine;
using UnityEngine.Networking;
using UnityEngine.SceneManagement;

/// <summary>
/// Exact-editor Play Mode fixture for the one null-world-hit compatibility guard.
/// Uses the imported accepted prefab shape and native RoR2 callbacks only.
/// It creates no run, network session, skill execution, profile change, or device activity.
/// </summary>
public static class EngiShieldHitGuardHost
{
    const string PrefabPath = "Assets/WholeGame/RoR2/Base/Characters/Engi/Projectiles/EngiBubbleShield/EngiBubbleShield.prefab";
    const BindingFlags PrivateInstance = BindingFlags.Instance | BindingFlags.NonPublic;

    static void Require(bool condition, string message)
    {
        if (!condition)
            throw new InvalidOperationException(message);
    }

    static bool GuardOwns(EngiShieldHitGuard guard, HurtBox target)
    {
        var method = typeof(EngiShieldHitGuard).GetMethod("OwnsFilterOn", PrivateInstance);
        Require(method != null, "Guard ownership diagnostic method missing");
        return (bool)method.Invoke(guard, new object[] { target });
    }

    static void RestoreGuard(EngiShieldHitGuard guard)
    {
        var method = typeof(EngiShieldHitGuard).GetMethod("RestoreOwnedFilter", PrivateInstance);
        Require(method != null, "Guard restore method missing");
        method.Invoke(guard, null);
    }

    static void InvokeAndRequireOwnershipRefusal(Func<HurtBox.HurtBoxAttackHitProcessorArgs, HurtBox, bool> filter,
                                                 HurtBox.HurtBoxAttackHitProcessorArgs args, HurtBox processorHurtBox)
    {
        var refused = false;
        try
        {
            filter(args, processorHurtBox);
        }
        catch (InvalidOperationException)
        {
            refused = true;
        }
        Require(refused, "Guard callback did not refuse a disposed or foreign processor invocation");
    }

    static GameObject Instantiate(GameObject prefab, Scene scene)
    {
        var instance = UnityEngine.Object.Instantiate(prefab);
        Require(instance, "Unity did not instantiate the accepted Engi shield prefab");
        SceneManager.MoveGameObjectToScene(instance, scene);
        return instance;
    }

    static HurtBox ConfiguredHurtBox(GameObject root, BetterBlockingEnablerSphere blocker)
    {
        var field = typeof(BetterBlockingEnabler).GetField("hurtBox", PrivateInstance);
        Require(field != null, "Native BetterBlockingEnabler serialized field missing");
        var configured = field.GetValue(blocker) as HurtBox[];
        Require(configured != null && configured.Length == 1 && configured[0], "Native blocker lost its serialized HurtBox");
        Require(configured[0].gameObject == root.transform.Find("Collision").gameObject,
                "Native blocker reference did not resolve to the Collision child");
        return configured[0];
    }

    static void ActivateSourceCollisionChild(GameObject root, HurtBox hurtBox)
    {
        var locator = root.GetComponent<ChildLocator>();
        Require(locator, "Original EngiBubbleShield ChildLocator missing");
        var bubble = locator.FindChild("Bubble");
        Require(bubble && bubble == hurtBox.transform, "Original Deployed child key no longer resolves to Collision");
        Require(!bubble.gameObject.activeSelf && !hurtBox.collider, "Collision must begin inactive with no cached HurtBox collider");
        bubble.gameObject.SetActive(true); // Fixture action; native deployed-state timing remains a device gate.
        Physics.SyncTransforms();
        Require(bubble.gameObject.activeSelf && hurtBox.collider && hurtBox.collider.enabled,
                "Native Collision activation did not initialize its collider/HurtBox");
    }

    static HurtBox.HurtBoxAttackHitProcessorArgs Args(HurtBox target, Vector3 origin, Vector3 hit)
    {
        return new HurtBox.HurtBoxAttackHitProcessorArgs { hitHurtBox = target, attackOrigin = origin, hitPosition = hit, attacker = null };
    }

    static void NativeWorldHitThrows(HurtBox rejector)
    {
        var errorObserved = false;
        try
        {
            // A null hitHurtBox is the native BulletHit representation of a world collider.
            rejector.AttackHitRejectsHurtbox(Args(null, new Vector3(0, 0, -15), new Vector3(0, 0, 12)));
        }
        catch (NullReferenceException)
        {
            errorObserved = true;
        }
        Require(errorObserved, "Fixture failed to reproduce the native null-HurtBox filter exception");
    }

    public static object Run()
    {
        Require(EditorApplication.isPlaying && !EditorApplication.isCompiling && !NetworkServer.active && !NetworkClient.active,
                "Require exact-editor Play Mode without a gameplay/network session");
        var source = AssetDatabase.LoadAssetAtPath<GameObject>(PrefabPath);
        Require(source, "Accepted imported EngiBubbleShield prefab missing: " + PrefabPath);
        EngiShieldHitGuardTemplateLease.ValidateSourceTemplate(source);

        var scene = SceneManager.GetActiveScene();
        Require(scene.IsValid() && scene.isLoaded, "Require a loaded exact-editor scene for owned fixture objects");
        GameObject plain = null, template = null, guardedClone = null, foreignClone = null, targetOutside = null, targetInside = null;
        EngiShieldHitGuardTemplateLease lease = null;
        Exception primaryError = null;
        try
        {
            // Play Mode instantiation runs the imported prefab's normal Unity lifecycle.
            // First prove that this exact imported prefab reaches the original native failure.
            plain = Instantiate(source, scene);
            var plainBlocker = plain.GetComponent<BetterBlockingEnablerSphere>();
            Require(plainBlocker, "Native sphere blocker absent from original source prefab");
            var plainHurtBox = ConfiguredHurtBox(plain, plainBlocker);
            var plainNative = plainHurtBox.attackHitRejectionFilter;
            Require(plainNative != null && ReferenceEquals(plainNative.Target, plainBlocker) &&
                        plainNative.Method.Name == "RejectionFilter" &&
                        plainNative.Method.DeclaringType.Assembly == typeof(BetterBlockingEnablerSphere).Assembly,
                    "Unmodified source prefab did not bind the native sphere rejection method");
            ActivateSourceCollisionChild(plain, plainHurtBox);
            NativeWorldHitThrows(plainHurtBox);
            UnityEngine.Object.DestroyImmediate(plain);
            plain = null;

            // Runtime uses a non-scene bundle template. This Play Mode clone is only a fixture stand-in;
            // Awake runs normally on it and the lease exercises ownership against actual native callbacks.
            template = Instantiate(source, scene);
            template.name = source.name;
            var originalBlocker = template.GetComponent<BetterBlockingEnablerSphere>();
            var originalHurtBox = ConfiguredHurtBox(template, originalBlocker);
            var originalNative = originalHurtBox.attackHitRejectionFilter;
            lease = EngiShieldHitGuardTemplateLease.Acquire(template);
            var templateGuard = template.GetComponent<EngiShieldHitGuard>();
            Require(templateGuard && GuardOwns(templateGuard, originalHurtBox) &&
                        ReferenceEquals(originalHurtBox.attackHitRejectionFilter.Target, templateGuard),
                    "Template lease did not wrap only the original template's native callback");

            guardedClone = Instantiate(template, scene);
            var cloneBlocker = guardedClone.GetComponent<BetterBlockingEnablerSphere>();
            var cloneHurtBox = ConfiguredHurtBox(guardedClone, cloneBlocker);
            var cloneGuard = guardedClone.GetComponent<EngiShieldHitGuard>();
            var capturedField = typeof(EngiShieldHitGuard).GetField("originalFilter", PrivateInstance);
            var cloneNative = capturedField == null
                                  ? null
                                  : capturedField.GetValue(cloneGuard) as Func<HurtBox.HurtBoxAttackHitProcessorArgs, HurtBox, bool>;
            Require(cloneGuard && GuardOwns(cloneGuard, cloneHurtBox) && cloneHurtBox != originalHurtBox &&
                        !ReferenceEquals(cloneHurtBox, ConfiguredHurtBox(source, source.GetComponent<BetterBlockingEnablerSphere>())) &&
                        cloneNative != null && ReferenceEquals(cloneNative.Target, cloneBlocker) &&
                        ReferenceEquals(cloneHurtBox.attackHitRejectionFilter.Target, cloneGuard),
                    "Unity clone did not remap the native serialized HurtBox/filter to the cloned shield");
            ActivateSourceCollisionChild(guardedClone, cloneHurtBox);
            Require(!cloneHurtBox.AttackHitRejectsHurtbox(Args(null, new Vector3(0, 0, -15), new Vector3(0, 0, 12))),
                    "Guard failed to treat a real-null world hit as no blockable HurtBox target");
            var ownedCallback = cloneHurtBox.attackHitRejectionFilter;
            var worldArgs = Args(null, new Vector3(0, 0, -15), new Vector3(0, 0, 12));

            targetOutside = new GameObject("Owned Engi body target");
            SceneManager.MoveGameObjectToScene(targetOutside, scene);
            var outsideCollider = targetOutside.AddComponent<SphereCollider>();
            outsideCollider.radius = 1;
            var outsideHurtBox = targetOutside.AddComponent<HurtBox>();
            Require(outsideHurtBox.collider == outsideCollider, "Target collider cache missing");
            var bounds = cloneHurtBox.collider.bounds;
            Require(bounds.size.sqrMagnitude > 0, "Activated source shield collider has no measured bounds");
            var reach = bounds.extents.magnitude + 20;
            var outsideNative = false;
            var outsideArgs = default(HurtBox.HurtBoxAttackHitProcessorArgs);
            foreach (var direction in new[] { Vector3.forward, Vector3.right, Vector3.back, Vector3.left, Vector3.up, Vector3.down })
            {
                var origin = bounds.center - direction * reach;
                var hit = bounds.center + direction * reach;
                targetOutside.transform.position = hit;
                Physics.SyncTransforms();
                outsideArgs = Args(outsideHurtBox, origin, hit);
                outsideNative = cloneNative(outsideArgs, cloneHurtBox);
                if (outsideNative)
                    break;
            }
            Require(outsideNative, "No native blocked HurtBox ray measured through source collider bounds");
            var outsideGuarded = cloneHurtBox.AttackHitRejectsHurtbox(outsideArgs);
            Require(outsideGuarded == outsideNative, "Guard changed the measured native blocked HurtBox ray");
            InvokeAndRequireOwnershipRefusal(ownedCallback, Args(null, Vector3.zero, Vector3.zero), outsideHurtBox);

            targetInside = new GameObject("Owned Engi clear-ray target");
            SceneManager.MoveGameObjectToScene(targetInside, scene);
            var clearOrigin = bounds.max + Vector3.one * reach;
            targetInside.transform.position = clearOrigin + Vector3.one * 5;
            var insideCollider = targetInside.AddComponent<SphereCollider>();
            insideCollider.radius = 1;
            var insideHurtBox = targetInside.AddComponent<HurtBox>();
            Require(insideHurtBox.collider == insideCollider, "Clear-ray target collider cache missing");
            Physics.SyncTransforms();
            var insideArgs = Args(insideHurtBox, clearOrigin, targetInside.transform.position);
            var insideNative = cloneNative(insideArgs, cloneHurtBox);
            Require(!insideNative, "Native shield unexpectedly blocked the measured clear HurtBox ray");
            var insideGuarded = cloneHurtBox.AttackHitRejectsHurtbox(insideArgs);
            Require(insideGuarded == insideNative, "Guard changed the measured native clear HurtBox ray");

            // Owned restoration: still-owned wrapper returns to the captured exact native delegate.
            RestoreGuard(cloneGuard);
            Require(ReferenceEquals(cloneHurtBox.attackHitRejectionFilter, cloneNative) && !GuardOwns(cloneGuard, cloneHurtBox),
                    "Guard did not restore its captured native delegate");
            InvokeAndRequireOwnershipRefusal(ownedCallback, worldArgs, cloneHurtBox);
            UnityEngine.Object.DestroyImmediate(guardedClone);
            guardedClone = null;

            // Foreign replacement: restoration must leave a later producer's callback untouched.
            foreignClone = Instantiate(template, scene);
            var foreignBlocker = foreignClone.GetComponent<BetterBlockingEnablerSphere>();
            var foreignHurtBox = ConfiguredHurtBox(foreignClone, foreignBlocker);
            var foreignGuard = foreignClone.GetComponent<EngiShieldHitGuard>();
            Require(foreignGuard && GuardOwns(foreignGuard, foreignHurtBox), "Foreign replacement fixture guard did not install");
            var foreignSavedWrapper = foreignHurtBox.attackHitRejectionFilter;
            Func<HurtBox.HurtBoxAttackHitProcessorArgs, HurtBox, bool> foreign = (args, box) => true;
            foreignHurtBox.attackHitRejectionFilter = foreign;
            InvokeAndRequireOwnershipRefusal(foreignSavedWrapper, Args(null, Vector3.zero, Vector3.zero), foreignHurtBox);
            RestoreGuard(foreignGuard);
            Require(ReferenceEquals(foreignHurtBox.attackHitRejectionFilter, foreign),
                    "Guard restoration overwrote a foreign replacement filter");
            UnityEngine.Object.DestroyImmediate(foreignClone);
            foreignClone = null;

            // Template release runs after all shield clones. It restores then removes only the added guard.
            var blockerAfter = template.GetComponent<BetterBlockingEnablerSphere>();
            lease.ReleaseAfterWorldCleanup();
            lease = null;
            Require(!template.GetComponent<EngiShieldHitGuard>() && template.GetComponent<BetterBlockingEnablerSphere>() == blockerAfter &&
                        ReferenceEquals(originalHurtBox.attackHitRejectionFilter, originalNative),
                    "Template lease changed the native component or failed to remove only its guard");
            UnityEngine.Object.DestroyImmediate(template);
            template = null;

            return new { success = true,
                         nativeNullWorldHitThrows = true,
                         guardedNullWorldHitReturnsFalse = true,
                         validBlockedRayMatchesNative = outsideGuarded == outsideNative,
                         validClearRayMatchesNative = insideGuarded == insideNative,
                         clonedSerializedHurtBoxRemapped = true,
                         ownedDelegateRestored = true,
                         foreignReplacementPreserved = true,
                         staleCallbackRefused = true,
                         sourceCollisionActivationInitializesNativeHurtBox = true,
                         originalNativeSphereFilterPreserved = true };
        }
        catch (Exception error)
        {
            primaryError = error;
            throw;
        }
        finally
        {
            var cleanupErrors = new List<Exception>();
            foreach (var instance in new[] { guardedClone, foreignClone, plain })
                if (instance)
                    try
                    {
                        UnityEngine.Object.DestroyImmediate(instance);
                    }
                    catch (Exception error)
                    {
                        cleanupErrors.Add(error);
                    }
            if (lease != null)
                try
                {
                    lease.ReleaseAfterWorldCleanup();
                }
                catch (Exception error)
                {
                    cleanupErrors.Add(error);
                }
            foreach (var instance in new[] { template, targetOutside, targetInside })
                if (instance)
                    try
                    {
                        UnityEngine.Object.DestroyImmediate(instance);
                    }
                    catch (Exception error)
                    {
                        cleanupErrors.Add(error);
                    }
            if (cleanupErrors.Count > 0)
            {
                if (primaryError != null)
                    cleanupErrors.Insert(0, primaryError);
                throw new AggregateException("Engi guard fixture cleanup failed", cleanupErrors);
            }
        }
    }
}
