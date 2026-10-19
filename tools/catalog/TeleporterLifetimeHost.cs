using System;
using RoR2;
using UnityEditor;
using UnityEngine;
using UnityEngine.Networking;

// Play Mode fixture for the native CombatSquad server-listener contract.
// The temporary host is created and destroyed in one call; reflection reads
// the original static event lists but never invokes lifecycle callbacks.
public static class TeleporterLifetimeHost
{
    static void Require(bool condition, string message)
    {
        if (!condition)
            throw new InvalidOperationException(message);
    }

    public static object Run()
    {
        Require(EditorApplication.isPlaying && !EditorApplication.isCompiling && !NetworkServer.active &&
                    !NetworkClient.active,
                "Teleporter lifetime fixture requires Play Mode without an existing network session");

        GameObject host = null;
        NetworkIdentity identity = null;
        CombatSquad squad = null;
        bool serverInitializationAttempted = false;
        bool spawned = false;
        Exception primaryError = null;
        int deathBefore = -1, deathAfter = -1, summonBefore = -1, summonAfter = -1;
        try
        {
            serverInitializationAttempted = true;
            Require(NetworkServer.Listen("127.0.0.1", 0), "Pinned transport could not open the fixture's ephemeral local server");
            Require(NetworkServer.active, "Public NetworkServer.Listen did not activate server authority");

            host = new GameObject("Owned native CombatSquad listener fixture");
            host.SetActive(false);
            identity = host.AddComponent<NetworkIdentity>();
            squad = host.AddComponent<CombatSquad>();
            Require(NativeCombatSquadListenerEvidence.CountDeathListeners(new[] { squad }) == 0 &&
                        NativeCombatSquadListenerEvidence.CountSummonListeners(new[] { squad }) == 0,
                    "Inactive fixture host ran native Awake before activation");
            host.SetActive(true);
            NetworkServer.Spawn(host);
            spawned = true;
            Require(identity && identity.netId.Value != 0 && NetworkServer.FindLocalObject(identity.netId) == host,
                    "Public NetworkServer.Spawn did not register the exact fixture host");
            var exactSquad = new[] { squad };
            deathBefore = NativeCombatSquadListenerEvidence.CountDeathListeners(exactSquad);
            summonBefore = NativeCombatSquadListenerEvidence.CountSummonListeners(exactSquad);
            Require(deathBefore == 1 && summonBefore == 1,
                    "Native CombatSquad.Awake did not attach both server listeners");

            var networkId = identity.netId;
            NetworkServer.UnSpawn(host);
            Require(NetworkServer.active && NetworkServer.FindLocalObject(networkId) != host,
                    "Public NetworkServer.UnSpawn left the fixture identity registered");
            UnityEngine.Object.DestroyImmediate(host);
            host = null;
            deathAfter = NativeCombatSquadListenerEvidence.CountDeathListeners(exactSquad);
            summonAfter = NativeCombatSquadListenerEvidence.CountSummonListeners(exactSquad);
            Require(deathAfter == 0 && summonAfter == 0,
                    "Native CombatSquad.OnDestroy retained a server listener after exact host destruction");
            return new { serverStarted = true, networkSpawnObserved = spawned, deathBefore, deathAfter, summonBefore, summonAfter,
                         bothListenersRemoved = true };
        }
        catch (Exception error)
        {
            primaryError = error;
            throw;
        }
        finally
        {
            Exception cleanupError = null;
            try
            {
                if (host)
                {
                    Require(NetworkServer.active,
                            "Cannot clean the fixture CombatSquad after server shutdown; its native OnDestroy cleanup is server-gated");
                    if (identity && identity.netId.Value != 0 && NetworkServer.FindLocalObject(identity.netId) == host)
                        NetworkServer.UnSpawn(host);
                    UnityEngine.Object.DestroyImmediate(host);
                }
            }
            catch (Exception error)
            {
                cleanupError = error;
            }
            try
            {
                if (serverInitializationAttempted)
                    NetworkServer.Shutdown();
            }
            catch (Exception error)
            {
                cleanupError = cleanupError ?? error;
            }
            if (cleanupError != null)
            {
                if (primaryError != null)
                    Debug.LogError("Teleporter lifetime fixture cleanup after primary failure: " + cleanupError);
                else
                    throw new InvalidOperationException("Teleporter lifetime fixture cleanup failed", cleanupError);
            }
        }
    }
}
