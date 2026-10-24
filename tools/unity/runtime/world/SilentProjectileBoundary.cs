// Subsystem: world/director (game path). Owner map: docs/ARCHITECTURE.md#ownership.
// Session phases: setup Awake; teardown —.
using RoR2.Projectile;
using UnityEngine;

// Preserve source events with a ready original owner; normalize absent events
// to the original null/no-event branch after Unity cloning.
[DefaultExecutionOrder(-20000)]
public sealed class SilentProjectileBoundary : MonoBehaviour
{
    public static int prepared;
    void Awake()
    {
        var source = GetComponent<ProjectileController>();
        if (!GameAudioOriginalOwner.Ready || string.IsNullOrEmpty(source.startSound))
            source.startSound = null;
        prepared++;
    }
}
