public static class LightningStakeRollingObserverHostContracts
{
    static void Require(bool condition, string label)
    {
        if (!condition) throw new Exception("failed: " + label);
    }

    sealed class SyntheticRetirementOwner
    {
        public sealed class TrackedStake { public uint netId; }
        readonly System.Collections.Generic.List<TrackedStake> tracked = new System.Collections.Generic.List<TrackedStake>();
        readonly LightningStakeSamplingPolicy samplingPolicy = new LightningStakeSamplingPolicy();

        public void Add(uint netId)
        {
            if (samplingPolicy.TryTrack(netId)) tracked.Add(new TrackedStake { netId = netId });
        }
        public int ActiveCount => samplingPolicy.IdentityCount;
        public int TrackedCount => tracked.Count;
        public void RunRetirement(int index) { RetireTrackedAt(index); }

        // Production RetireTrackedAt is inserted here by the extraction runner.
        __EXTRACTED_RETIREMENT_METHOD__
    }

    sealed class PauseCoordinator
    {
        public bool offlineSettingsPaused;
        public int observations;
        public SyntheticProjectileOwner projectile;
        public void ObserveLightningStakes()
        {
            observations++;
            if (projectile != null) projectile.Observe(1f);
        }
    }
    sealed class PauseBridge
    {
        public int neutralCalls;
        public void Neutral() { neutralCalls++; }
    }
    sealed class PauseConfig { public bool integratedWorld; }

    static void CheckPause(bool paused, bool integrated, int expectedObservations, int expectedSimulation)
    {
        var coordinator = new PauseCoordinator { offlineSettingsPaused = paused };
        var bridge = new PauseBridge();
        var cfg = new PauseConfig { integratedWorld = integrated };
        int simulation = 0;
        for (int frame = 0; frame < 3; frame++)
        {
            __EXTRACTED_PAUSED_BRANCH__
            simulation++;
        }
        Require(coordinator.observations == expectedObservations, "paused observation follows integrated owner selection");
        Require(bridge.neutralCalls == (paused ? 3 : 0), "pause keeps input neutral each frame");
        Require(simulation == expectedSimulation, "paused diagnostic never resumes simulation");
    }

    // Authored scalar collaborators: no game implementation or physics simulation.
    class LiveObject { public bool alive = true; public static implicit operator bool(LiveObject value) => value != null && value.alive; }
    struct Vector3
    {
        public float x, y, z;
        public Vector3(float x, float y, float z) { this.x = x; this.y = y; this.z = z; }
        public static Vector3 zero => new Vector3();
    }
    struct Quaternion { public float x, y, z, w; public static Quaternion identity => new Quaternion { w = 1 }; }
    sealed class Transform : LiveObject
    {
        public Vector3 position, lossyScale = new Vector3(1, 1, 1);
        public Quaternion rotation = Quaternion.identity;
        public int GetInstanceID() => 7;
    }
    sealed class GameObject : LiveObject
    {
        public readonly Transform transform = new Transform();
        public readonly Dictionary<Type, object> components = new Dictionary<Type, object>();
        public T GetComponent<T>() where T : class => components[typeof(T)] as T;
        public int GetInstanceID() => 8;
    }
    struct NetworkId { public uint Value; }
    sealed class NetworkIdentity : LiveObject { public NetworkId netId; public GameObject gameObject; }
    static class NetworkServer
    {
        public static bool active = true;
        public static GameObject current;
        public static GameObject FindLocalObject(NetworkId id) => current;
    }
    static class Time { public static int frameCount; }
    sealed class ProjectileNetworkTransform : LiveObject
    {
        public Vector3 NetworkserverPosition;
        public Quaternion NetworkserverRotation = Quaternion.identity;
    }
    sealed class ProjectileStickOnImpact : LiveObject
    {
        public Vector3 NetworklocalPosition;
        public Quaternion NetworklocalRotation = Quaternion.identity;
        public bool stuck;
        public Transform stuckTransform;
        public GameObject victim;
    }
    sealed class Rigidbody : LiveObject { public Vector3 position, velocity, angularVelocity; }
    sealed class SphereCollider : LiveObject { public float radius = .5f; public Vector3 center; }
    sealed class Snapshot { public bool finite, firstNonFiniteTransition; }

    sealed class SyntheticProjectileOwner
    {
        const int MaxTrackedStakes = 3, PeriodicSampleFrames = 30, DiscoveryIntervalFrames = 6, MaxTotalSamples = 36;
        readonly LightningStakeSamplingPolicy samplingPolicy = new LightningStakeSamplingPolicy();
        readonly List<TrackedStake> tracked = new List<TrackedStake>();
        public readonly List<Snapshot> observations = new List<Snapshot>();
        GameObject sourcePrefab = new GameObject();
        int projectileIndex = 0, lastDiscoveryFrame = -1;
        bool disposed, historyCapped;
        string setupStatus = "synthetic";
        public int ActiveCount => tracked.Count;
        public int lastFiniteFrame => tracked[0].lastFiniteFrame;
        public SyntheticProjectileOwner(GameObject obj)
        {
            samplingPolicy.TryTrack(1);
            tracked.Add(new TrackedStake { netId = 1, identity = new NetworkIdentity {
                netId = new NetworkId { Value = 1 }, gameObject = obj } });
        }
        bool DiscoverStakes(float seconds) => false; // identity supplied explicitly, not a native spawn
        bool Record(TrackedStake stake, GameObject obj, float seconds, string reason,
                    bool firstNonFinite, bool compositeFinite, int replaceSampleIndex)
        {
            if (replaceSampleIndex >= 0) observations.RemoveAt(replaceSampleIndex);
            observations.Add(new Snapshot { finite = compositeFinite, firstNonFiniteTransition = firstNonFinite });
            stake.sampleCount++;
            stake.lastSampleFrame = Time.frameCount;
            return true;
        }
        __EXTRACTED_PROJECTILE_METHODS__
    }

    static void CheckImpactPauseAndTeardown(bool injectInvalidPosition)
    {
        var obj = new GameObject();
        var network = new ProjectileNetworkTransform();
        var stick = new ProjectileStickOnImpact();
        var body = new Rigidbody();
        var sphere = new SphereCollider();
        obj.components[typeof(ProjectileNetworkTransform)] = network;
        obj.components[typeof(ProjectileStickOnImpact)] = stick;
        obj.components[typeof(Rigidbody)] = body;
        obj.components[typeof(SphereCollider)] = sphere;
        NetworkServer.current = obj;
        var owner = new SyntheticProjectileOwner(obj);
        Time.frameCount = 0;
        Require(owner.Observe(1f), "finite free projectile sampled");
        Require(owner.observations[0].finite, "initial collider inputs finite");

        // Synthetic impact precedes pause. The network position deliberately lags
        // physical state, matching the ordering localized by retained evidence.
        stick.stuck = true;
        stick.victim = new GameObject();
        stick.stuckTransform = stick.victim.transform;
        obj.transform.position = body.position = stick.NetworklocalPosition = new Vector3(2, 3, 4);
        Time.frameCount++;
        owner.Observe(1f);
        Require(owner.observations[1].finite, "terrain impact collider inputs finite");
        if (injectInvalidPosition) obj.transform.position = body.position = new Vector3(float.NaN, 3, 4);
        var coordinator = new PauseCoordinator { offlineSettingsPaused = true, projectile = owner };
        var bridge = new PauseBridge();
        var cfg = new PauseConfig { integratedWorld = true };
        for (int frame = 0; frame < 3; frame++)
        {
            Time.frameCount++;
            __EXTRACTED_PAUSED_BRANCH__
            throw new Exception("paused branch reached simulation");
        }
        Require(coordinator.observations == 3 && bridge.neutralCalls == 3, "paused updates observe without simulation");
        Require(!float.IsNaN(network.NetworkserverPosition.x), "network position remains finite during lag");
        Require(!float.IsNaN(sphere.radius) && !float.IsNaN(sphere.center.x), "collider geometry remains finite");
        if (injectInvalidPosition)
        {
            var transition = owner.observations[owner.observations.Count - 1];
            Require(!transition.finite && transition.firstNonFiniteTransition, "physical NaN detected despite finite network and geometry");
            Require(owner.lastFiniteFrame == 1, "invalid paused frames preserve finite predecessor");
            Require(float.IsNaN(obj.transform.position.x), "read-only observer does not repair invalid state");
        }
        else
        {
            foreach (var row in owner.observations) Require(row.finite, "impact/pause history has finite collider inputs");
            network.NetworkserverPosition = body.position;
            Time.frameCount += 30;
            owner.Observe(2f);
            Require(owner.observations[owner.observations.Count - 1].finite, "resumed collider inputs finite");
        }
        // Actual teardown detaches observation before destroying native objects.
        int retained = owner.observations.Count;
        owner.Dispose();
        obj.alive = false;
        obj.components.Clear(); // any stale read now throws
        owner.Dispose();
        Require(!owner.Observe(3f) && owner.ActiveCount == 0, "disposed observer never reads destroyed components");
        Require(owner.observations.Count == retained, "teardown retains scalar evidence");
        NetworkServer.current = null;
    }

    public static int Main()
    {
        CheckImpactPauseAndTeardown(false);
        CheckImpactPauseAndTeardown(true);
        CheckPause(true, true, 3, 0);
        CheckPause(true, false, 0, 0);
        CheckPause(false, true, 0, 3);
        var policy = new LightningStakeSamplingPolicy();
        Require(policy.TryTrack(1) && policy.TryTrack(2) && policy.TryTrack(3), "three active identities fit");
        Require(!policy.TryTrack(4) && policy.IdentityCount == 3, "active identity budget refuses fourth");
        Require(policy.Untrack(2) && policy.IdentityCount == 2, "vacated identity releases active slot");
        Require(!policy.Untrack(2) && policy.TryTrack(4), "retirement is idempotent and slot recycles");
        Require(policy.TotalIdentitiesObserved == 4, "identity count is cumulative across turnover");
        Require(!policy.Untrack(0) && !policy.TryTrack(0), "zero network id is refused");

        var owner = new SyntheticRetirementOwner();
        owner.Add(25);
        Require(owner.ActiveCount == 1 && owner.TrackedCount == 1, "synthetic observer setup owns active identity");
        owner.RunRetirement(0);
        Require(owner.ActiveCount == 0 && owner.TrackedCount == 0, "extracted production retirement releases exact slot and row");
        owner.Add(26);
        Require(owner.ActiveCount == 1 && owner.TrackedCount == 1, "retired production slot is reusable");

        int replace;
        Require(policy.TryReserveRecord(10, false, 35, -1, out replace) && replace == -1,
                "ordinary sample allowed below total cap");
        Require(!policy.TryReserveRecord(11, false, 35, -1, out replace),
                "per-identity final slot stays reserved for transition");
        Require(policy.TryReserveRecord(11, true, 35, -1, out replace),
                "finite-to-invalid transition consumes reserved identity slot");
        Require(!policy.TryReserveRecord(12, true, 35, -1, out replace), "per-identity history remains capped");

        Require(!policy.TryReserveRecord(2, false, 36, 0, out replace), "full history refuses ordinary growth");
        Require(policy.TryReserveRecord(2, true, 36, 4, out replace) && replace == 4,
                "full history preserves transition by replacing oldest ordinary row");
        Require(!policy.TryReserveRecord(2, true, 36, -1, out replace),
                "all-transition history refuses further growth without evicting transition evidence");
        Require(!policy.TryReserveRecord(2, true, 37, 4, out replace), "invalid over-cap count refuses record");

        Require(LightningStakeSamplingPolicy.IsFirstNonFiniteTransition(true, true, false, false),
                "first finite-to-invalid edge is detected");
        Require(!LightningStakeSamplingPolicy.IsFirstNonFiniteTransition(true, false, false, false) &&
                !LightningStakeSamplingPolicy.IsFirstNonFiniteTransition(true, true, false, true),
                "already-invalid and already-recorded cases are not duplicate transitions");

        policy.Dispose();
        Require(policy.IsDisposed && policy.IdentityCount == 0 && policy.TotalIdentitiesObserved == 4,
                "cleanup releases active IDs but retains scalar report count");
        Require(!policy.TryTrack(5) && !policy.Untrack(4) &&
                !policy.TryReserveRecord(0, true, 0, -1, out replace), "disposed policy is inert");
        Console.WriteLine("PASS: rolling observer policy contracts");
        return 0;
    }
}
