using System;
using OriginalOwnerProbeObserver;
using RoR2;
using RoR2.Projectile;
using UnityEngine;
using UnityEngine.Networking;

internal static class LightningStakeOwnerHostContracts
{
    static void Require(bool value, string message) { if (!value) throw new InvalidOperationException(message); }
    static NetworkIdentity Identity(uint id)
    { return new NetworkIdentity { netId = new NetworkInstanceId { Value = id } }; }
    static void Send(DamageInfo damage, GameObject hit, FireProjectileInfo info)
    { Observer.RecordLightningStakeSourceCall(damage, hit, info); }

    public static int Main()
    {
        Require(LightningStakeSourceCallObserver.ValidateSelector(false, false, null, null) == null,
            "default-off request must not require an integrated route");
        Require(LightningStakeSourceCallObserver.ValidateSelector(true, false,
                    "body-state-spawn-state-auto-nova-spine", "Commando") != null,
            "requested selector accepted a non-integrated world");
        Require(LightningStakeSourceCallObserver.ValidateSelector(true, true, "other-route", "Commando") != null,
            "requested selector accepted an unknown route");
        Require(LightningStakeSourceCallObserver.ValidateSelector(true, true,
                    "body-state-spawn-state-auto-nova-spine", null) != null,
            "requested selector accepted an unselected survivor");
        Require(LightningStakeSourceCallObserver.ValidateSelector(true, true,
                    "body-state-spawn-state-auto-nova-spine", "Commando") == null &&
                LightningStakeSourceCallObserver.ValidateSelector(true, true,
                    "body-state-spawn-state-auto-nova-spine-bringup", "Commando") == null,
            "accepted Nova source-selected routes were refused");
        Observer.Reset();
        var attacker = new GameObject("attacker");
        attacker.AddComponent(Identity(17));
        var body = new CharacterBody { characterMotor = new CharacterMotor { velocity = new Vector3(3, 4, 0) } };
        body.AddComponent(Identity(18));
        attacker.AddComponent(body);
        var prefab = new GameObject("LightningStake");
        var hit = new GameObject("hit") { transform = new Transform { position = new Vector3(6, 7, 8) } };
        var damage = new DamageInfo {
            attacker = attacker, position = new Vector3(1, 2, 3), damage = 12.5f, force = 9f,
            procCoefficient = 0.75f, crit = true, rejected = false
        };
        var info = new FireProjectileInfo {
            projectilePrefab = prefab, owner = attacker, position = damage.position,
            damage = 25f, force = 0f, crit = true
        };
        var report = new PortSession.LightningStakeSourceCallReport();
        var owner = new LightningStakeSourceCallObserver(report);
        Require(report.status == "attached" && Observer.HasLightningStakeSourceCallObserver(), "explicit observer did not attach");
        Send(damage, hit, info);
        Require(report.sourceCallCount == 1 && report.sourceCalls.Count == 1, "one source callback did not yield one row");
        var row = report.sourceCalls[0];
        Require(row.frame == 42 && row.projectilePrefabName == "LightningStake" && row.projectileCatalogIndex == 117 &&
                row.damageAttackerInstance == attacker.GetInstanceID() && row.projectileOwnerInstance == attacker.GetInstanceID() &&
                row.damageAttackerNetworkId == 17 && row.projectileOwnerNetworkId == 17 && row.ownerBodyNetworkId == 18 &&
                row.attackerMatchesProjectileOwner && row.ownerPosition == "0,0,0" && row.ownerVelocity == "3,4,0" &&
                row.hitPosition == "6,7,8" && row.damageInfoDamage == 12.5f && row.damageInfoForce == 9f &&
                row.projectileDamage == 25f && row.projectileForce == 0f && row.finiteDamagePosition && row.finiteProjectilePosition,
                "captured scalar source context did not preserve owner, source, finite flags, and computed projectile arguments");
        for (int i = 1; i < 9; i++) Send(damage, hit, info);
        Require(report.sourceCallCount == 9 && report.sourceCalls.Count == 8 && report.historyCapped,
            "history bound or saturation metadata changed");
        owner.Dispose();
        Require(report.detached && report.status == "detached" && !Observer.HasLightningStakeSourceCallObserver(),
            "owner did not detach its exact bridge callback");

        var nonfiniteReport = new PortSession.LightningStakeSourceCallReport();
        using (var nonfiniteOwner = new LightningStakeSourceCallObserver(nonfiniteReport))
        {
            var badPosition = damage;
            badPosition.position = new Vector3(float.NaN, 0, 0);
            Send(badPosition, hit, info);
            Require(nonfiniteReport.sourceCalls.Count == 1 && !nonfiniteReport.sourceCalls[0].finiteDamagePosition,
                "nonfinite source input was lost or marked finite");
        }
        Require(nonfiniteReport.detached, "nonfinite capture owner failed teardown");

        var occupiedReport = new PortSession.LightningStakeSourceCallReport();
        Action<object, object, object> preexisting = (a, b, c) => { };
        Observer.LightningStakeSourceCall = preexisting;
        bool attachRefused = false;
        try { new LightningStakeSourceCallObserver(occupiedReport); }
        catch (InvalidOperationException) { attachRefused = true; }
        Require(attachRefused && object.ReferenceEquals(Observer.LightningStakeSourceCall, preexisting) &&
                occupiedReport.status == "refused-owner-already-attached",
            "setup replaced an existing owner callback");
        Observer.LightningStakeSourceCall = null;

        var malformedReport = new PortSession.LightningStakeSourceCallReport();
        using (var malformedOwner = new LightningStakeSourceCallObserver(malformedReport))
        {
            Observer.RecordLightningStakeSourceCall("unexpected-damage", hit, "unexpected-projectile");
            Require(malformedReport.sourceCallCount == 1 && malformedReport.captureFailures == 1 &&
                    malformedReport.sourceCalls.Count == 0 && malformedReport.status == "capture-failed",
                "unexpected source operand types were not counted as a contained capture failure");
        }
        Require(malformedReport.detached, "malformed capture owner failed teardown");

        var conflicting = new PortSession.LightningStakeSourceCallReport();
        var conflictOwner = new LightningStakeSourceCallObserver(conflicting);
        Action<object, object, object> replacement = (a, b, c) => { };
        Observer.LightningStakeSourceCall = replacement;
        bool detachRefused = false;
        try { conflictOwner.Dispose(); } catch (InvalidOperationException) { detachRefused = true; }
        Require(detachRefused && object.ReferenceEquals(Observer.LightningStakeSourceCall, replacement) &&
                conflicting.status == "detach-refused-owner-changed",
            "teardown cleared a callback it no longer owned");
        Observer.LightningStakeSourceCall = null;
        Console.WriteLine("PASS actual observer source captures scalar context, bounds history, contains nonfinite values, and owns teardown");
        return 0;
    }
}
