using System;
using System.Collections.Generic;
using RoR2;
using UnityEditor;
using UnityEngine;
using UnityEngine.Networking;

// Play Mode fixture for exact ownership over the native temporary-overlay registry.
// It uses only registry reads plus TemporaryOverlayManager's public mutation APIs.
public static class TeleportOverlayLifetimeHost
{
    static void Require(bool condition, string message)
    {
        if (!condition)
            throw new InvalidOperationException(message);
    }

    static GameObject CreateHost(string name, List<GameObject> hosts)
    {
        var host = new GameObject(name);
        hosts.Add(host);
        return host;
    }

    public static object Run()
    {
        Require(EditorApplication.isPlaying && !EditorApplication.isCompiling && !NetworkServer.active && !NetworkClient.active,
                "Temporary overlay fixture requires idle Play Mode without a game network session");
        Require(TeleportOverlayRegistryOwnership.ActiveCount == 0,
                "Temporary overlay fixture requires the native manager's initialized empty registry");

        var hosts = new List<GameObject>();
        var overlays = new List<TemporaryOverlayInstance>();
        Exception primaryError = null;
        try
        {
            var foreignHost = CreateHost("Owned fixture foreign-live overlay", hosts);
            var foreignOverlay = TemporaryOverlayManager.AddOverlay(foreignHost);
            overlays.Add(foreignOverlay);

            var expiredHost = CreateHost("Owned fixture expiring overlay", hosts);
            var expiredOverlay = TemporaryOverlayManager.AddOverlay(expiredHost);
            overlays.Add(expiredOverlay);
            int expiredIndex = expiredOverlay.managerIndex;
            Require(expiredIndex == 1 && TeleportOverlayRegistryOwnership.ActiveCount == 2,
                    "Fixture overlays did not enter the expected native manager slots");

            // Native removal of the last slot while another entry remains sets
            // arraySize to one, then reassigns the removed wrapper's old index.
            TemporaryOverlayManager.RemoveOverlay(expiredIndex);
            Require(TeleportOverlayRegistryOwnership.ActiveCount == 1 && expiredOverlay.managerIndex == expiredIndex &&
                        !TeleportOverlayRegistryOwnership.Contains(expiredOverlay),
                    "Pinned native last-slot removal no longer exhibits the tested stale-index condition");

            var replacementHost = CreateHost("Owned fixture replacement live overlay", hosts);
            var replacementOverlay = TemporaryOverlayManager.AddOverlay(replacementHost);
            overlays.Add(replacementOverlay);
            Require(replacementOverlay.managerIndex == expiredIndex && TeleportOverlayRegistryOwnership.Contains(replacementOverlay),
                    "Fixture did not reuse the stale manager index with a distinct live instance");

            bool removedStale = TeleportOverlayRegistryOwnership.RemoveIfActive(expiredOverlay);
            Require(!removedStale && expiredOverlay.managerIndex == -1 && TeleportOverlayRegistryOwnership.Contains(foreignOverlay) &&
                        TeleportOverlayRegistryOwnership.Contains(replacementOverlay) && TeleportOverlayRegistryOwnership.ActiveCount == 2,
                    "Stale owned index removed or disturbed another live overlay");

            var destroyedHost = CreateHost("Owned fixture destroyed unobserved host", hosts);
            var destroyedOverlay = TemporaryOverlayManager.AddOverlay(destroyedHost);
            overlays.Add(destroyedOverlay);
            UnityEngine.Object.DestroyImmediate(destroyedHost);
            TemporaryOverlayManager.OverlayUpdate();
            Require(!TeleportOverlayRegistryOwnership.Contains(destroyedOverlay) &&
                        TeleportOverlayRegistryOwnership.Contains(foreignOverlay) &&
                        TeleportOverlayRegistryOwnership.Contains(replacementOverlay) && TeleportOverlayRegistryOwnership.ActiveCount == 2,
                    "Native public update failed to prune a destroyed host or changed live foreign overlays");

            Require(TeleportOverlayRegistryOwnership.RemoveIfActive(foreignOverlay),
                    "Exact removal did not remove the selected foreign fixture instance");
            Require(TeleportOverlayRegistryOwnership.RemoveIfActive(replacementOverlay),
                    "Exact removal did not remove the selected replacement fixture instance");
            Require(TeleportOverlayRegistryOwnership.ActiveCount == 0, "Fixture retained an entry after exact native removal");
            return new { success = true,
                         nativeLastSlotIndexWasStale = true,
                         staleReferenceDidNotRemoveReplacement = true,
                         publicUpdatePrunedDestroyedHost = true,
                         liveForeignOverlaysPreservedDuringPrune = true,
                         exactRemovalReturnedRegistryToEmpty = true };
        }
        catch (Exception error)
        {
            primaryError = error;
            throw;
        }
        finally
        {
            Exception cleanupError = null;
            foreach (var overlay in overlays)
            {
                try
                {
                    TeleportOverlayRegistryOwnership.RemoveIfActive(overlay);
                }
                catch (Exception error)
                {
                    cleanupError = cleanupError ?? error;
                }
            }
            foreach (var host in hosts)
            {
                try
                {
                    if (host)
                        UnityEngine.Object.DestroyImmediate(host);
                }
                catch (Exception error)
                {
                    cleanupError = cleanupError ?? error;
                }
            }
            if (cleanupError != null)
            {
                if (primaryError != null)
                    Debug.LogError("Temporary overlay fixture cleanup after primary failure: " + cleanupError);
                else
                    throw new InvalidOperationException("Temporary overlay fixture cleanup failed", cleanupError);
            }
        }
    }
}
