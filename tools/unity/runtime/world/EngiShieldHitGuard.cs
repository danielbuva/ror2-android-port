// Subsystem: survivor compatibility. Owner map: docs/ARCHITECTURE.md#ownership.
using System;
using System.Reflection;
using RoR2;
using UnityEngine;

/// <summary>
/// Engi-only adapter for BulletAttack's valid world-hit/null-HurtBox argument.
/// All valid HurtBox targets delegate to the exact native sphere filter.
/// </summary>
[DefaultExecutionOrder(10000)]
public sealed class EngiShieldHitGuard : MonoBehaviour
{
    const BindingFlags InstancePrivate = BindingFlags.Instance | BindingFlags.NonPublic;
    int guardedWorldHits;
    HurtBox targetHurtBox;
    Func<HurtBox.HurtBoxAttackHitProcessorArgs, HurtBox, bool> originalFilter;
    Func<HurtBox.HurtBoxAttackHitProcessorArgs, HurtBox, bool> ownedFilter;

    void Awake()
    {
        // AssetBundle.LoadAsset returns a template outside a scene. Its cloned
        // scene instances run this only after the native blocker has initialized.
        if (gameObject.scene.IsValid())
            InstallNow();
    }

    internal void InstallNow()
    {
        if (ownedFilter != null)
            return;

        var blockers = GetComponents<BetterBlockingEnablerSphere>();
        if (blockers.Length != 1)
            throw new InvalidOperationException("Engi guard requires exactly one native BetterBlockingEnablerSphere on the shield root");
        var blocker = blockers[0];

        // Match the native serialized reference, rather than wrapping an arbitrary child HurtBox.
        var hurtBoxField = typeof(BetterBlockingEnabler).GetField("hurtBox", InstancePrivate);
        var configured = hurtBoxField == null ? null : hurtBoxField.GetValue(blocker) as HurtBox[];
        if (configured == null || configured.Length != 1 || !configured[0])
            throw new InvalidOperationException("Engi shield native rejection filter must reference exactly one serialized HurtBox");
        // The source ChildLocator's Bubble key maps directly to Collision.
        var collision = transform.Find("Collision");
        if (!collision || configured[0].gameObject != collision.gameObject || !collision.GetComponent<Collider>())
            throw new InvalidOperationException("Engi shield serialized rejector is not the source Bubble/Collision HurtBox collider");

        var current = configured[0].attackHitRejectionFilter;
        var method = current == null ? null : current.Method;
        if (current == null || !ReferenceEquals(current.Target, blocker) || method.Name != "RejectionFilter" ||
            method.DeclaringType != typeof(BetterBlockingEnablerSphere))
            throw new InvalidOperationException("Engi shield rejection callback is not the exact native sphere blocker delegate");

        targetHurtBox = configured[0];
        originalFilter = current;
        ownedFilter = RejectOnlyNullWorldHit;
        targetHurtBox.attackHitRejectionFilter = ownedFilter;
        if (!ReferenceEquals(targetHurtBox.attackHitRejectionFilter, ownedFilter))
        {
            ClearReferences();
            throw new InvalidOperationException("Engi guard did not acquire the native HurtBox filter slot");
        }
    }

    bool RejectOnlyNullWorldHit(HurtBox.HurtBoxAttackHitProcessorArgs args, HurtBox processorHurtBox)
    {
        var native = originalFilter;
        if (native == null)
            throw new InvalidOperationException("Engi guard lost its native rejection delegate");
        if (!ReferenceEquals(processorHurtBox, targetHurtBox))
            throw new InvalidOperationException("Engi guard callback was invoked for a foreign processor HurtBox");
        if (!ReferenceEquals(targetHurtBox.attackHitRejectionFilter, ownedFilter))
            throw new InvalidOperationException("Engi guard callback was invoked after a foreign filter replacement");

        if (!targetHurtBox || !(native.Target as BetterBlockingEnablerSphere))
            throw new InvalidOperationException("Engi guard lost its live native processor owner");
        if (ReferenceEquals(args.hitHurtBox, null))
        {
            if (!targetHurtBox.collider)
                throw new InvalidOperationException("Engi guard world-hit processor collider is unavailable");
            if (++guardedWorldHits == 1)
                Debug.Log("LAB_ENGI_SHIELD_NULL_TARGET_GUARDED");
            return false;
        }

        // Deliberately let destroyed/fake-null HurtBoxes and missing target colliders reach native code.
        // Those indicate a different lifecycle/source failure and must remain visible.
        return native(args, processorHurtBox);
    }

    internal bool OwnsFilterOn(HurtBox expected)
    {
        return expected && ReferenceEquals(targetHurtBox, expected) && ownedFilter != null &&
               ReferenceEquals(expected.attackHitRejectionFilter, ownedFilter);
    }

    internal void RestoreOwnedFilter()
    {
        var target = targetHurtBox;
        var native = originalFilter;
        var owned = ownedFilter;
        if (target && owned != null && ReferenceEquals(target.attackHitRejectionFilter, owned))
            target.attackHitRejectionFilter = native;
        ClearReferences();
    }

    void OnDestroy()
    {
        // Scene guards share their shield host's lifetime. A never-activated
        // Collision child does not receive native OnDisable, even on destruction.
        // The native managed setter retires this exact rejector-list entry.
        // Keep CLR identity here: Unity may already consider the child destroyed.
        var target = targetHurtBox;
        var owned = ownedFilter;
        if (!ReferenceEquals(target, null) && owned != null && ReferenceEquals(target.attackHitRejectionFilter, owned))
            target.attackHitRejectionFilter = null;
        ClearReferences();
        // Live component-only removal must call RestoreOwnedFilter first, as
        // template release does. That explicit detach clears these references.
    }

    void ClearReferences()
    {
        targetHurtBox = null;
        originalFilter = null;
        ownedFilter = null;
    }
}

/// <summary>
/// Temporary owner for the one in-memory accepted shield template mutation.
/// Call ReleaseAfterWorldCleanup after shield clones are gone and before releasing WholeCatalogComposed.
/// </summary>
public sealed class EngiShieldHitGuardTemplateLease
{
    const BindingFlags InstancePrivate = BindingFlags.Instance | BindingFlags.NonPublic;
    EngiShieldHitGuard guard;

    public static EngiShieldHitGuardTemplateLease Acquire(GameObject acceptedTemplate)
    {
        ValidateSourceTemplate(acceptedTemplate);
        var guard = acceptedTemplate.GetComponent<EngiShieldHitGuard>();
        if (guard)
            throw new InvalidOperationException("Engi shield template already has a guard owner");
        guard = acceptedTemplate.AddComponent<EngiShieldHitGuard>();
        try
        {
            // Scene instances have already received Awake; a bundle template
            // may not have run any Unity lifecycle methods yet.
            if (acceptedTemplate.scene.IsValid())
                guard.InstallNow();
            return new EngiShieldHitGuardTemplateLease { guard = guard };
        }
        catch
        {
            if (guard)
            {
                guard.RestoreOwnedFilter();
                UnityEngine.Object.DestroyImmediate(guard);
            }
            throw;
        }
    }

    public static void ValidateSourceTemplate(GameObject source)
    {
        if (!source || source.name != "EngiBubbleShield")
            throw new InvalidOperationException("Expected accepted EngiBubbleShield source template");
        if (!source.activeSelf)
            throw new InvalidOperationException("Accepted EngiBubbleShield root must retain its active source state");
        var blockers = source.GetComponents<BetterBlockingEnablerSphere>();
        var hurtBoxes = source.GetComponentsInChildren<HurtBox>(true);
        var collision = source.transform.Find("Collision");
        if (blockers.Length != 1 || !collision || hurtBoxes.Length != 1 || hurtBoxes[0].gameObject != collision.gameObject ||
            collision.gameObject.activeSelf || !collision.GetComponent<MeshCollider>() || !collision.GetComponent<HurtBox>())
            throw new InvalidOperationException("Accepted Engi shield Collision child/HurtBox/collider shape changed");

        var hurtBoxField = typeof(BetterBlockingEnabler).GetField("hurtBox", InstancePrivate);
        var configured = hurtBoxField == null ? null : hurtBoxField.GetValue(blockers[0]) as HurtBox[];
        if (configured == null || configured.Length != 1 || !ReferenceEquals(configured[0], hurtBoxes[0]))
            throw new InvalidOperationException("Accepted BetterBlockingEnablerSphere serialized HurtBox reference changed");
    }

    public void ReleaseAfterWorldCleanup()
    {
        var owned = guard;
        if (owned)
        {
            // One bounded, type-specific read verifies world cleanup ordering.
            // Never destroy or reset any scene guard from this template lease.
            var liveGuards = Resources.FindObjectsOfTypeAll<EngiShieldHitGuard>();
            for (var i = 0; i < liveGuards.Length; i++)
            {
                var candidate = liveGuards[i];
                if (candidate && candidate != owned && candidate.gameObject.scene.IsValid())
                    throw new InvalidOperationException("Engi shield guard clones remain in a live scene during template release");
            }

            owned.RestoreOwnedFilter();
            // This component belongs only to the in-memory bundle template.
            // Its caller must retain the bundle until scene clones are gone.
            UnityEngine.Object.DestroyImmediate(owned);
            if (owned)
                throw new InvalidOperationException("Owned Engi guard component survived its template lease release");
        }
        guard = null;
    }
}
