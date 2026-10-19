// Subsystem: runtime diagnostics. Owner: IntegratedWorldSession.
// Setup: current projectile catalog; teardown: integrated world cleanup.
// Observes native projectiles without changing their behavior.
using System;
using System.Collections.Generic;
using System.Globalization;
using RoR2;
using RoR2.Projectile;
using UnityEngine;
using UnityEngine.Networking;

public sealed class LightningStakeSamplingPolicy : IDisposable
{
    const int MaxTrackedStakes = 3;
    const int MaxSamplesPerStake = 12;
    const int MaxTotalSamples = MaxTrackedStakes * MaxSamplesPerStake;
    readonly HashSet<uint> activeIdentities = new HashSet<uint>();
    bool disposed;
    int totalIdentitiesObserved;

    public int IdentityCount => activeIdentities.Count;
    public int TotalIdentitiesObserved => totalIdentitiesObserved;
    public bool IsDisposed => disposed;

    public bool TryTrack(uint netId)
    {
        if (disposed || netId == 0 || activeIdentities.Contains(netId) || activeIdentities.Count >= MaxTrackedStakes)
            return false;
        activeIdentities.Add(netId);
        if (totalIdentitiesObserved < int.MaxValue)
            totalIdentitiesObserved++;
        return true;
    }

    public bool Untrack(uint netId)
    {
        return !disposed && netId != 0 && activeIdentities.Remove(netId);
    }

    // The observer may recycle a live slot after an identity disappears, but its
    // serialized sample history remains globally bounded. A transition can use
    // a full history only by replacing the oldest non-transition row.
    public bool TryReserveRecord(int priorSamples, bool firstNonFinite, int totalSamples, int oldestOrdinarySampleIndex,
                                 out int replaceSampleIndex)
    {
        replaceSampleIndex = -1;
        if (disposed || priorSamples < 0 || priorSamples >= MaxSamplesPerStake ||
            (priorSamples >= MaxSamplesPerStake - 1 && !firstNonFinite) || totalSamples < 0 || totalSamples > MaxTotalSamples)
            return false;

        if (totalSamples < MaxTotalSamples)
            return true;

        if (!firstNonFinite || oldestOrdinarySampleIndex < 0 || oldestOrdinarySampleIndex >= totalSamples)
            return false;
        replaceSampleIndex = oldestOrdinarySampleIndex;
        return true;
    }

    public static string InitialSampleReason(bool isFirstSample)
    {
        return isFirstSample ? "first-observed-not-spawn" : null;
    }

    public static bool IsFirstNonFiniteTransition(bool hasFiniteSample, bool previousFinite, bool currentFinite, bool alreadyRecorded)
    {
        return hasFiniteSample && previousFinite && !currentFinite && !alreadyRecorded;
    }

    public void Dispose()
    {
        disposed = true;
        activeIdentities.Clear();
    }
}

internal sealed class LightningStakeDiagnosticObserver : IDisposable
{
    const int MaxTrackedStakes = 3;
    const int MaxSamplesPerStake = 12;
    const int MaxTotalSamples = MaxTrackedStakes * MaxSamplesPerStake;
    const int PeriodicSampleFrames = 30;
    const int DiscoveryIntervalFrames = 6;

    // Kept independent of Unity/game objects so the exact production budget and
    // terminal behavior can be exercised by a host/editor fixture without
    // fabricating a spawned projectile.
    readonly LightningStakeSamplingPolicy samplingPolicy = new LightningStakeSamplingPolicy();

    sealed class TrackedStake
    {
        public NetworkIdentity identity;
        public uint netId;
        public int sampleCount;
        public int lastSampleFrame = -1;
        public int previousVictimInstance;
        public int previousStuckTransformInstance;
        public bool previousStuck;
        public bool previousFinite;
        public bool hasFiniteSample;
        public bool firstNonFiniteRecorded;
        public bool hasStateSample;
        public int lastFiniteFrame = -1;
        public Vector3 lastFinitePosition, lastFiniteNetworkPosition, lastFiniteRigidbodyPosition;
        public Vector3 lastFiniteVelocity, lastFiniteAngularVelocity;
    }

    readonly List<TrackedStake> tracked = new List<TrackedStake>(MaxTrackedStakes);
    readonly List<PortSession.LightningStakeObservation> observations = new List<PortSession.LightningStakeObservation>(MaxTotalSamples);
    int projectileIndex = -1;
    GameObject sourcePrefab;
    string setupStatus;
    bool historyCapped;
    public string SetupStatus => setupStatus;
    int lastDiscoveryFrame = -1;
    bool disposed;

    public List<PortSession.LightningStakeObservation> Observations => observations;
    public int DiscoveredCount => samplingPolicy.TotalIdentitiesObserved;

    public LightningStakeDiagnosticObserver()
    {
        projectileIndex = ProjectileCatalog.FindProjectileIndex("LightningStake");
        sourcePrefab = projectileIndex >= 0 ? ProjectileCatalog.GetProjectilePrefab(projectileIndex) : null;
        if (!sourcePrefab || sourcePrefab.name != "LightningStake")
        {
            SetSetupStatus("source-projectile-unavailable");
            sourcePrefab = null;
            projectileIndex = -1;
            return;
        }
        var controller = sourcePrefab.GetComponent<ProjectileController>();
        if (!controller || controller.catalogIndex != projectileIndex ||
            ProjectileCatalog.GetProjectilePrefab(controller.catalogIndex) != sourcePrefab ||
            !sourcePrefab.GetComponent<ProjectileNetworkTransform>() || !sourcePrefab.GetComponent<ProjectileStickOnImpact>() ||
            !sourcePrefab.GetComponent<Rigidbody>() || !sourcePrefab.GetComponent<SphereCollider>())
        {
            SetSetupStatus("source-component-contract-incomplete");
            sourcePrefab = null;
            projectileIndex = -1;
            return;
        }
        SetSetupStatus("ready");
    }

    // Call from the integrated-world Update. Existing tracked identities are checked
    // each frame; the native server object registry is traversed at most every six frames.
    public bool Observe(float runSeconds)
    {
        if (disposed || samplingPolicy.IsDisposed || !NetworkServer.active || !sourcePrefab || projectileIndex < 0)
            return false;

        try
        {
            return ObserveActive(runSeconds);
        }
        catch (Exception error)
        {
            // This boundary is read-only. A broken diagnostic must become inert
            // and visible in the report, without changing gameplay or swallowing
            // an exception raised by a native callback elsewhere.
            SetSetupStatus("observe-error: " + error.GetBaseException().Message);
            Dispose();
            return false;
        }
    }

    bool ObserveActive(float runSeconds)
    {
        bool addedSample = false;
        for (int i = tracked.Count - 1; i >= 0; --i)
        {
            TrackedStake stake = tracked[i];
            if (!stake.identity)
            {
                RetireTrackedAt(i);
                continue;
            }

            GameObject obj = stake.identity.gameObject;
            if (!obj || stake.identity.netId.Value != stake.netId || NetworkServer.FindLocalObject(stake.identity.netId) != obj)
            {
                RetireTrackedAt(i);
                continue;
            }

            addedSample |= ObserveStake(stake, obj, runSeconds);
        }

        if (samplingPolicy.IdentityCount < MaxTrackedStakes &&
            (lastDiscoveryFrame < 0 || Time.frameCount - lastDiscoveryFrame >= DiscoveryIntervalFrames))
        {
            lastDiscoveryFrame = Time.frameCount;
            addedSample |= DiscoverStakes(runSeconds);
        }
        return addedSample;
    }

    void RetireTrackedAt(int index)
    {
        TrackedStake stake = tracked[index];
        samplingPolicy.Untrack(stake.netId);
        tracked.RemoveAt(index);
    }

    void MarkHistoryCapped()
    {
        if (historyCapped)
            return;
        historyCapped = true;
        setupStatus += ";sample-history-capped";
    }

    void SetSetupStatus(string value)
    {
        setupStatus = historyCapped ? value + ";sample-history-capped" : value;
    }

    bool DiscoverStakes(float runSeconds)
    {
        if (projectileIndex < 0 || !sourcePrefab)
            return false;

        bool addedSample = false;
        foreach (NetworkIdentity identity in NetworkServer.objects.Values)
        {
            if (samplingPolicy.IdentityCount >= MaxTrackedStakes)
                break;
            if (!identity || !identity.isServer)
                continue;
            uint netId = identity.netId.Value;
            if (netId == 0 || samplingPolicy.IdentityCount >= MaxTrackedStakes)
                continue;

            GameObject obj = identity.gameObject;
            if (!obj || NetworkServer.FindLocalObject(identity.netId) != obj)
                continue;
            ProjectileController controller = obj.GetComponent<ProjectileController>();
            if (!controller || controller.catalogIndex != projectileIndex ||
                ProjectileCatalog.GetProjectilePrefab(controller.catalogIndex) != sourcePrefab)
                continue;

            if (!samplingPolicy.TryTrack(netId))
                continue;

            // Catalog identity plus this exact server NetworkIdentity is the source
            // selector; the object name alone is deliberately not used as proof.
            var stake = new TrackedStake { identity = identity, netId = netId };
            tracked.Add(stake);
            addedSample |= ObserveStake(stake, obj, runSeconds);
        }
        return addedSample;
    }

    bool ObserveStake(TrackedStake stake, GameObject obj, float runSeconds)
    {
        Transform transform = obj.transform;
        ProjectileNetworkTransform network = obj.GetComponent<ProjectileNetworkTransform>();
        ProjectileStickOnImpact stick = obj.GetComponent<ProjectileStickOnImpact>();
        Rigidbody rigidbody = obj.GetComponent<Rigidbody>();
        Vector3 position = transform.position;
        Vector3 networkPosition = network ? network.NetworkserverPosition : Vector3.zero;
        Vector3 rigidbodyPosition = rigidbody ? rigidbody.position : Vector3.zero;
        Vector3 velocity = rigidbody ? rigidbody.velocity : Vector3.zero;
        Vector3 angularVelocity = rigidbody ? rigidbody.angularVelocity : Vector3.zero;
        Vector3 localPosition = stick ? stick.NetworklocalPosition : Vector3.zero;
        Quaternion localRotation = stick ? stick.NetworklocalRotation : Quaternion.identity;
        Quaternion rotation = transform.rotation;
        Vector3 scale = transform.lossyScale;
        Quaternion networkRotation = network ? network.NetworkserverRotation : Quaternion.identity;
        SphereCollider sphere = obj.GetComponent<SphereCollider>();
        Transform stuckTransform = stick ? stick.stuckTransform : null;
        Vector3 stuckTransformPosition = stuckTransform ? stuckTransform.position : Vector3.zero;
        GameObject victim = stick ? stick.victim : null;
        Vector3 victimPosition = victim ? victim.transform.position : Vector3.zero;
        bool finite =
            Finite(position) && Finite(rotation) && Finite(scale) && (!sphere || (Finite(sphere.radius) && Finite(sphere.center))) &&
            (!network || (Finite(networkPosition) && Finite(networkRotation))) && (!rigidbody || Finite(rigidbodyPosition)) &&
            (!rigidbody || Finite(velocity)) && (!rigidbody || Finite(angularVelocity)) &&
            (!stick || !stick.stuck ||
             (Finite(localPosition) && Finite(localRotation) && Finite(stuckTransformPosition) && (!victim || Finite(victimPosition))));
        int victimInstance = victim ? victim.GetInstanceID() : 0;
        int stuckTransformInstance = stuckTransform ? stuckTransform.GetInstanceID() : 0;
        bool isStuck = stick && stick.stuck;

        bool firstNonFinite = LightningStakeSamplingPolicy.IsFirstNonFiniteTransition(stake.hasFiniteSample, stake.previousFinite, finite,
                                                                                      stake.firstNonFiniteRecorded);
        bool stuckChanged = stake.hasStateSample && (stake.previousStuck != isStuck || stake.previousVictimInstance != victimInstance ||
                                                     stake.previousStuckTransformInstance != stuckTransformInstance);
        bool firstSample = stake.sampleCount == 0;
        bool periodic = stake.lastSampleFrame < 0 || Time.frameCount - stake.lastSampleFrame >= PeriodicSampleFrames;
        bool takeSample = firstSample || firstNonFinite || stuckChanged || periodic;

        stake.previousFinite = finite;
        if (finite)
        {
            stake.hasFiniteSample = true;
            stake.lastFiniteFrame = Time.frameCount;
            stake.lastFinitePosition = position;
            stake.lastFiniteNetworkPosition = networkPosition;
            stake.lastFiniteRigidbodyPosition = rigidbodyPosition;
            stake.lastFiniteVelocity = velocity;
            stake.lastFiniteAngularVelocity = angularVelocity;
        }
        stake.previousStuck = isStuck;
        stake.previousVictimInstance = victimInstance;
        stake.previousStuckTransformInstance = stuckTransformInstance;
        stake.hasStateSample = true;

        if (!takeSample)
            return false;

        int replaceSampleIndex = FindOldestOrdinarySampleIndex();
        if (!samplingPolicy.TryReserveRecord(stake.sampleCount, firstNonFinite, observations.Count, replaceSampleIndex,
                                             out replaceSampleIndex))
        {
            if (observations.Count >= MaxTotalSamples)
                MarkHistoryCapped();
            return false;
        }
        string reason = LightningStakeSamplingPolicy.InitialSampleReason(firstSample) ?? (firstNonFinite ? "first-finite-to-nonfinite"
                                                                                          : stuckChanged ? "stick-or-victim-transition"
                                                                                                         : "bounded-periodic");
        bool recorded = Record(stake, obj, runSeconds, reason, firstNonFinite, finite, replaceSampleIndex);
        if (recorded && replaceSampleIndex >= 0)
            MarkHistoryCapped();
        if (recorded && firstNonFinite)
            stake.firstNonFiniteRecorded = true;
        return recorded;
    }

    int FindOldestOrdinarySampleIndex()
    {
        for (int i = 0; i < observations.Count; i++)
        {
            if (!observations[i].firstNonFiniteTransition)
                return i;
        }
        return -1;
    }

    bool Record(TrackedStake stake, GameObject obj, float runSeconds, string reason, bool firstNonFinite, bool compositeFinite,
                int replaceSampleIndex)
    {
        Transform transform = obj.transform;
        ProjectileNetworkTransform network = obj.GetComponent<ProjectileNetworkTransform>();
        ProjectileStickOnImpact stick = obj.GetComponent<ProjectileStickOnImpact>();
        Rigidbody rigidbody = obj.GetComponent<Rigidbody>();
        SphereCollider sphere = obj.GetComponent<SphereCollider>();
        ProjectileController controller = obj.GetComponent<ProjectileController>();
        NetworkIdentity ownerIdentity = controller && controller.owner ? controller.owner.GetComponent<NetworkIdentity>() : null;
        CharacterBody ownerBody = controller && controller.owner ? controller.owner.GetComponent<CharacterBody>() : null;
        TeamComponent ownerTeam = controller && controller.owner ? controller.owner.GetComponent<TeamComponent>() : null;
        GameObject victim = stick ? stick.victim : null;
        Transform stuckTransform = stick ? stick.stuckTransform : null;
        CharacterBody stuckBody = stick ? stick.stuckBody : null;
        HurtBox stuckHurtBox = stick ? stick.stuckHurtBox : null;

        var observation = new PortSession.LightningStakeObservation {
            frame = Time.frameCount,
            instance = obj.GetInstanceID(),
            fixedTime = Time.fixedTime,
            seconds = runSeconds,
            sample = reason,
            spawnTimeKnown = false,
            networkId = stake.netId,
            networkObjectMatches =
                stake.identity && stake.identity.netId.Value == stake.netId && NetworkServer.FindLocalObject(stake.identity.netId) == obj,
            networkAssetId = stake.identity ? stake.identity.assetId.ToString() : "missing",
            projectileCatalogIndex = controller ? controller.catalogIndex : -1,
            isServer = stake.identity && stake.identity.isServer,
            ownerNetworkId = ownerIdentity ? ownerIdentity.netId.Value : 0,
            ownerObjectMatches =
                ownerIdentity && ownerIdentity.netId.Value != 0 && NetworkServer.FindLocalObject(ownerIdentity.netId) == controller.owner,
            ownerName = controller && controller.owner ? controller.owner.name : "missing",
            ownerBody = ownerBody ? ownerBody.name : "missing",
            ownerTeam = ownerTeam ? (int)ownerTeam.teamIndex : -1,
            ownerBlueElite = ownerBody && ownerBody.HasBuff(RoR2Content.Buffs.AffixBlue),
            ownerPosition = ownerBody ? Position(ownerBody.corePosition) : "missing",
            finitePosition = Finite(transform.position),
            finiteNetworkPosition = network && Finite(network.NetworkserverPosition),
            finiteRigidbodyPosition = rigidbody && Finite(rigidbody.position),
            finiteVelocity = rigidbody && Finite(rigidbody.velocity),
            finiteAngularVelocity = rigidbody && Finite(rigidbody.angularVelocity),
            firstNonFiniteTransition = firstNonFinite,
            finiteLocalPosition = stick && Finite(stick.NetworklocalPosition),
            finiteLocalRotation = stick && Finite(stick.NetworklocalRotation),
            finiteStuckTransformPosition = stuckTransform && Finite(stuckTransform.position),
            finiteVictimPosition = victim && Finite(victim.transform.position),
            lastFiniteFrame = stake.lastFiniteFrame,
            lastFinitePosition = stake.hasFiniteSample ? Position(stake.lastFinitePosition) : "unknown",
            lastFiniteNetworkPosition = stake.hasFiniteSample ? Position(stake.lastFiniteNetworkPosition) : "unknown",
            lastFiniteRigidbodyPosition = stake.hasFiniteSample ? Position(stake.lastFiniteRigidbodyPosition) : "unknown",
            lastFiniteVelocity = stake.hasFiniteSample ? Position(stake.lastFiniteVelocity) : "unknown",
            lastFiniteAngularVelocity = stake.hasFiniteSample ? Position(stake.lastFiniteAngularVelocity) : "unknown",
            position = Position(transform.position),
            rotation = Rotation(transform.rotation),
            scale = Position(transform.lossyScale),
            networkPosition = network ? Position(network.NetworkserverPosition) : "missing",
            networkRotation = network ? Rotation(network.NetworkserverRotation) : "missing",
            rigidbodyPosition = rigidbody ? Position(rigidbody.position) : "missing",
            velocity = rigidbody ? Position(rigidbody.velocity) : "missing",
            angularVelocity = rigidbody ? Position(rigidbody.angularVelocity) : "missing",
            rigidbodyKinematic = rigidbody && rigidbody.isKinematic,
            rigidbodyGravity = rigidbody && rigidbody.useGravity,
            rigidbodyDetectCollisions = rigidbody && rigidbody.detectCollisions,
            colliderEnabled = sphere && sphere.enabled,
            colliderTrigger = sphere && sphere.isTrigger,
            colliderRadius = sphere ? Number(sphere.radius) : "missing",
            colliderCenter = sphere ? Position(sphere.center) : "missing",
            stuck = stick && stick.stuck,
            stuckHurtBoxIndex = stick ? stick.NetworkhitHurtboxIndex : (sbyte)-1,
            victimNetworkId = victim && victim.GetComponent<NetworkIdentity>() ? victim.GetComponent<NetworkIdentity>().netId.Value : 0,
            victimName = victim ? victim.name : "missing",
            victimPosition = victim ? Position(victim.transform.position) : "missing",
            stuckTransformPath = Hierarchy(stuckTransform),
            stuckTransformPosition = stuckTransform ? Position(stuckTransform.position) : "missing",
            stuckBody = stuckBody ? stuckBody.name : "missing",
            stuckBodyPosition = stuckBody ? Position(stuckBody.corePosition) : "missing",
            stuckHurtBox = stuckHurtBox ? stuckHurtBox.name : "missing",
            localPosition = stick ? Position(stick.NetworklocalPosition) : "missing",
            localRotation = stick ? Rotation(stick.NetworklocalRotation) : "missing",
            finiteSnapshot = compositeFinite,
            finiteRotation = Finite(transform.rotation),
            finiteScale = Finite(transform.lossyScale),
            finiteNetworkRotation = network && Finite(network.NetworkserverRotation),
        };
        if (replaceSampleIndex >= 0)
            observations.RemoveAt(replaceSampleIndex);
        observations.Add(observation);
        stake.sampleCount++;
        stake.lastSampleFrame = Time.frameCount;
        return reason != "bounded-periodic";
    }

    static bool Finite(float value) => !float.IsNaN(value) && !float.IsInfinity(value);
    static bool Finite(Vector3 value) => Finite(value.x) && Finite(value.y) && Finite(value.z);
    static bool Finite(Quaternion value) => Finite(value.x) && Finite(value.y) && Finite(value.z) && Finite(value.w);
    static string Number(float value) => value.ToString("R", CultureInfo.InvariantCulture);
    static string Position(Vector3 value) => Number(value.x) + "," + Number(value.y) + "," + Number(value.z);
    static string Rotation(Quaternion value) => Number(value.x) + "," + Number(value.y) + "," + Number(value.z) + "," + Number(value.w);

    static string Hierarchy(Transform transform)
    {
        if (!transform)
            return "missing";
        var names = new Stack<string>();
        for (Transform current = transform; current; current = current.parent)
            names.Push(current.name);
        return string.Join("/", names.ToArray());
    }

    public void Dispose()
    {
        if (disposed)
            return;
        disposed = true;
        tracked.Clear();
        samplingPolicy.Dispose();
        // Samples contain only scalar/string observations and remain owned by the
        // WorldReport list that was given this same list during setup.
        sourcePrefab = null;
    }
}
