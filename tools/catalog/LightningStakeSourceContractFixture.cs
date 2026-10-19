// Exact-editor source and bounded policy fixture. It reads the imported prefab asset
// only; it does not instantiate it, load ProjectileCatalog, or start networking.
#if UNITY_EDITOR
using System;
using RoR2.Projectile;
using UnityEditor;
using UnityEngine;
using UnityEngine.Networking;

public static class LightningStakeSourceContractFixture
{
    const string SourcePath = "Assets/WholeGame/RoR2/Base/Elites/EliteLightning/LightningStake.prefab";
    const string SourceGuid = "531a6e5adb1a61d47b7e4d6c2dc102e9";

    static void Require(bool condition, string message)
    {
        if (!condition)
            throw new InvalidOperationException(message);
    }

    static bool Finite(float value) => !float.IsNaN(value) && !float.IsInfinity(value);

    static void VerifySamplingPolicy()
    {
        var policy = new LightningStakeSamplingPolicy();
        Require(policy.TryTrack(1) && policy.TryTrack(2) && policy.TryTrack(3),
                "Sampling policy must accept at most three distinct identities");
        Require(!policy.TryTrack(4) && !policy.TryTrack(1) && policy.IdentityCount == 3,
                "Sampling policy exceeded or duplicated the identity cap");
        Require(LightningStakeSamplingPolicy.InitialSampleReason(true) == "first-observed-not-spawn" &&
                    LightningStakeSamplingPolicy.InitialSampleReason(false) == null,
                "First observation must not be mislabeled as a true spawn sample");
        Require(!LightningStakeSamplingPolicy.IsFirstNonFiniteTransition(false, false, false, false) &&
                    LightningStakeSamplingPolicy.IsFirstNonFiniteTransition(true, true, false, false) &&
                    !LightningStakeSamplingPolicy.IsFirstNonFiniteTransition(true, true, false, true),
                "Only the first observed finite-to-nonfinite transition may claim that boundary");
        for (int priorSamples = 0; priorSamples < 11; priorSamples++)
            Require(policy.CanRecord(priorSamples, false), "Sampling policy stopped before its reserved slot");
        Require(!policy.CanRecord(11, false) && policy.CanRecord(11, true),
                "Final snapshot slot must be reserved for the first finite-to-nonfinite boundary");
        Require(!policy.CanRecord(12, true), "Sampling policy exceeded the 12-sample identity cap");
        policy.Dispose();
        Require(policy.IsDisposed && policy.IdentityCount == 0 && !policy.TryTrack(5) && !policy.CanRecord(0, true),
                "Disposed policy accepted tracking or sampling work");
    }

    public static object Run()
    {
        Require(!EditorApplication.isPlaying && !EditorApplication.isCompiling && !NetworkServer.active && !NetworkClient.active,
                "Source-asset fixture requires an idle editor and no network session");
        Require(string.Equals(AssetDatabase.AssetPathToGUID(SourcePath), SourceGuid, StringComparison.OrdinalIgnoreCase),
                "LightningStake source asset identity changed");

        GameObject source = AssetDatabase.LoadAssetAtPath<GameObject>(SourcePath);
        Require(source && source.name == "LightningStake", "Original LightningStake prefab is unavailable");
        var controller = source.GetComponent<ProjectileController>();
        var networkTransform = source.GetComponent<ProjectileNetworkTransform>();
        var stick = source.GetComponent<ProjectileStickOnImpact>();
        var identity = source.GetComponent<NetworkIdentity>();
        var body = source.GetComponent<Rigidbody>();
        var sphere = source.GetComponent<SphereCollider>();
        Require(controller && networkTransform && stick && identity && body && sphere,
                "Original projectile/network/stick/rigidbody/collider component closure changed");
        Require(source.activeSelf && controller.enabled && networkTransform.enabled && stick.enabled && sphere.enabled,
                "Source projectile components must remain enabled in the asset");
        Require(Finite(source.transform.localScale.x) && Finite(source.transform.localScale.y) && Finite(source.transform.localScale.z) &&
                    source.transform.localScale == Vector3.one,
                "Source root scale is non-finite or differs from the compared source");
        Require(Finite(sphere.radius) && sphere.radius == 0.5f && Finite(sphere.center.x) && Finite(sphere.center.y) &&
                    Finite(sphere.center.z) && sphere.center == Vector3.zero && !sphere.isTrigger,
                "Source sphere geometry differs from the compared source");
        Require(Finite(body.mass) && body.mass == 1f && !body.useGravity && body.interpolation == RigidbodyInterpolation.Interpolate,
                "Source rigidbody properties differ from the compared source");
        VerifySamplingPolicy();

        return new { sourceGuidVerified = true,
                     sourceAssetOnly = true,
                     noInstantiationOrActivation = true,
                     projectileNetworkAndImpactComponents = true,
                     colliderGeometryFinite = true,
                     rigidbodyPropertiesMatchComparedSource = true,
                     identityCapThreeSampleCapTwelveAndReservedTransitionVerified = true,
                     firstObservationIsNotClaimedAsSpawn = true,
                     alreadyInvalidFirstObservationIsNotClaimedAsTransition = true,
                     disposedPolicyIsInert = true,
                     runtimeCatalogIndexNotAsserted = true,
                     spawnPositionAndRuntimeCauseUnproven = true };
    }
}
#endif
