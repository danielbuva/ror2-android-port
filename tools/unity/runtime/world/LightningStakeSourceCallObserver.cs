// Subsystem: original gameplay diagnostics. Owner: IntegratedWorldSession.
// Setup: explicit lightningStakeSourceCallDiagnosticRequested selection.
// Teardown: detach the exact bridge delegate before world-owner teardown.
using System;
using System.Collections.Generic;
using System.Globalization;
using RoR2;
using RoR2.Projectile;
using UnityEngine;
using UnityEngine.Networking;

internal sealed class LightningStakeSourceCallObserver : IDisposable
{
    const int MaxSourceCalls = 8;
    readonly PortSession.LightningStakeSourceCallReport report;
    readonly Action<object, object, object> callback;
    int calls;
    bool attached;
    bool disposed;

    public LightningStakeSourceCallObserver(PortSession.LightningStakeSourceCallReport report)
    {
        if (report == null) throw new ArgumentNullException(nameof(report));
        this.report = report;
        callback = Record;
        report.status = "requested";
        if (!OriginalOwnerProbeObserver.Observer.TryAttachLightningStakeSourceCall(callback))
        {
            report.status = "refused-owner-already-attached";
            throw new InvalidOperationException("LightningStake source-call observer owner is already attached.");
        }
        attached = true;
        report.status = "attached";
    }

    internal static string ValidateSelector(bool requested, bool integratedWorld, string routeId, string selectedSurvivor)
    {
        if (!requested) return null;
        if (!integratedWorld) return "LightningStake source-call observation requires the integrated world owner";
        if (routeId != "body-state-spawn-state-auto-nova-spine" && routeId != "body-state-spawn-state-auto-nova-spine-bringup")
            return "LightningStake source-call observation requires an accepted Nova source-selected route";
        if (String.IsNullOrEmpty(selectedSurvivor))
            return "LightningStake source-call observation requires a selected survivor";
        return null;
    }

    static bool Finite(float value) => !float.IsNaN(value) && !float.IsInfinity(value);
    static bool Finite(Vector3 value) => Finite(value.x) && Finite(value.y) && Finite(value.z);
    static string Position(Vector3 value) => Number(value.x) + "," + Number(value.y) + "," + Number(value.z);
    static string Number(float value) => value.ToString("R", CultureInfo.InvariantCulture);

    void Record(object damageInfoValue, object hitObjectValue, object projectileInfoValue)
    {
        if (disposed) return;
        if (report.sourceCalls == null)
            report.sourceCalls = new List<PortSession.LightningStakeSourceCallObservation>(MaxSourceCalls);
        if (calls < int.MaxValue) calls++;
        report.sourceCallCount = calls;
        if (report.sourceCalls.Count >= MaxSourceCalls)
        {
            report.historyCapped = true;
            return;
        }
        try
        {
            if (!(damageInfoValue is DamageInfo damageInfo) || !(projectileInfoValue is FireProjectileInfo projectileInfo))
                throw new InvalidOperationException("Injected source-call operands have unexpected runtime types.");

            var attacker = damageInfo.attacker;
            var projectileOwner = projectileInfo.owner;
            var hitObject = hitObjectValue as GameObject;
            var ownerBody = projectileOwner ? projectileOwner.GetComponent<CharacterBody>() : null;
            var attackerIdentity = attacker ? attacker.GetComponent<NetworkIdentity>() : null;
            var projectileOwnerIdentity = projectileOwner ? projectileOwner.GetComponent<NetworkIdentity>() : null;
            var ownerBodyIdentity = ownerBody ? ownerBody.GetComponent<NetworkIdentity>() : null;
            var prefab = projectileInfo.projectilePrefab;
            var hitTransform = hitObject ? hitObject.transform : null;
            var ownerMotor = ownerBody ? ownerBody.characterMotor : null;
            var spawnPosition = projectileInfo.position;
            var damagePosition = damageInfo.position;
            var ownerPosition = projectileOwner ? projectileOwner.transform.position : Vector3.zero;
            var ownerVelocity = ownerMotor ? ownerMotor.velocity : Vector3.zero;
            var hitPosition = hitTransform ? hitTransform.position : Vector3.zero;
            int projectileIndex = prefab ? ProjectileCatalog.FindProjectileIndex(prefab.name) : -1;
            report.sourceCalls.Add(new PortSession.LightningStakeSourceCallObservation {
                frame = Time.frameCount,
                damageAttackerInstance = attacker ? attacker.GetInstanceID() : 0,
                projectileOwnerInstance = projectileOwner ? projectileOwner.GetInstanceID() : 0,
                ownerBodyInstance = ownerBody ? ownerBody.GetInstanceID() : 0,
                hitObjectInstance = hitObject ? hitObject.GetInstanceID() : 0,
                projectilePrefabInstance = prefab ? prefab.GetInstanceID() : 0,
                projectileCatalogIndex = projectileIndex,
                damageAttackerNetworkId = attackerIdentity ? attackerIdentity.netId.Value : 0,
                projectileOwnerNetworkId = projectileOwnerIdentity ? projectileOwnerIdentity.netId.Value : 0,
                ownerBodyNetworkId = ownerBodyIdentity ? ownerBodyIdentity.netId.Value : 0,
                projectilePrefabName = prefab ? prefab.name : "",
                damagePosition = Position(damagePosition),
                projectilePosition = Position(spawnPosition),
                ownerPosition = Position(ownerPosition),
                ownerVelocity = Position(ownerVelocity),
                hitPosition = Position(hitPosition),
                damageInfoDamage = damageInfo.damage,
                damageInfoForce = damageInfo.force,
                damageInfoProcCoefficient = damageInfo.procCoefficient,
                projectileDamage = projectileInfo.damage,
                projectileForce = projectileInfo.force,
                damageInfoCrit = damageInfo.crit,
                projectileCrit = projectileInfo.crit,
                damageInfoRejected = damageInfo.rejected,
                attackerMatchesProjectileOwner = attacker && projectileOwner && attacker == projectileOwner,
                hasOwnerBody = ownerBody,
                hasAttackerNetworkIdentity = attackerIdentity,
                hasProjectileOwnerNetworkIdentity = projectileOwnerIdentity,
                hasOwnerBodyNetworkIdentity = ownerBodyIdentity,
                hasProjectilePrefab = prefab,
                isLightningStakeName = prefab && prefab.name == "LightningStake",
                finiteDamagePosition = Finite(damagePosition),
                finiteProjectilePosition = Finite(spawnPosition),
                finiteOwnerPosition = Finite(ownerPosition),
                finiteOwnerVelocity = Finite(ownerVelocity),
                finiteHitPosition = Finite(hitPosition),
                finiteDamageInfoDamage = Finite(damageInfo.damage),
                finiteDamageInfoForce = Finite(damageInfo.force),
                finiteProjectileDamage = Finite(projectileInfo.damage),
                finiteProjectileForce = Finite(projectileInfo.force)
            });
        }
        catch (Exception error)
        {
            report.captureFailures = report.captureFailures >= 1000000 ? 1000000 : report.captureFailures + 1;
            if (String.IsNullOrEmpty(report.firstCaptureFailureType))
            {
                string type = error.GetType().FullName;
                report.firstCaptureFailureType = String.IsNullOrEmpty(type) ? "unknown" :
                    (type.Length <= 256 ? type : type.Substring(0, 256));
            }
            report.status = "capture-failed";
        }
    }

    public void Dispose()
    {
        if (disposed) return;
        if (attached)
        {
            if (!OriginalOwnerProbeObserver.Observer.TryDetachLightningStakeSourceCall(callback))
            {
                report.status = "detach-refused-owner-changed";
                throw new InvalidOperationException("LightningStake source-call observer no longer owns the bridge callback.");
            }
            attached = false;
        }
        disposed = true;
        if (report.status == "attached") report.status = "detached";
        report.detached = !attached;
    }
}
