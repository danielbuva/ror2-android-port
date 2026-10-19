using System;
using System.Collections.Generic;
using System.Reflection;
using System.Linq;

public struct NetworkInstanceId : IEquatable<NetworkInstanceId>
{
    public readonly uint Value;
    public NetworkInstanceId(uint value)
    {
        Value = value;
    }
    public bool Equals(NetworkInstanceId other)
    {
        return Value == other.Value;
    }
    public override bool Equals(object other)
    {
        return other is NetworkInstanceId && Equals((NetworkInstanceId)other);
    }
    public override int GetHashCode()
    {
        return (int)Value;
    }
    public static bool operator ==(NetworkInstanceId left, NetworkInstanceId right)
    {
        return left.Value == right.Value;
    }
    public static bool operator !=(NetworkInstanceId left, NetworkInstanceId right)
    {
        return left.Value != right.Value;
    }
}

public sealed class GameObject
{
    public readonly string name;
    public NetworkIdentity identity;
    public bool activeSelf;
    public int setActiveCalls;
    public bool setActiveBeforeCleanReset;

    public GameObject(string name, bool active)
    {
        this.name = name;
        activeSelf = active;
    }
    public void SetActive(bool value)
    {
        setActiveCalls++;
        if (identity == null || !identity.WasNativeResetCleanly)
            setActiveBeforeCleanReset = true;
        activeSelf = value;
    }
}

public sealed class NetworkIdentity
{
    private bool m_Reset;
    public NetworkInstanceId netId { get; private set; }
    public bool isServer { get; private set; }
    public bool isClient { get; private set; }
    public GameObject gameObject { get; private set; }
    public int resetCalls;
    public bool WasNativeResetCleanly;
    public bool leaveServerAfterReset;
    public bool leaveClientAfterReset;

    public NetworkIdentity(GameObject owner, uint networkId, bool server, bool client)
    {
        gameObject = owner;
        owner.identity = this;
        netId = new NetworkInstanceId(networkId);
        isServer = server;
        isClient = client;
    }
    public static implicit operator bool(NetworkIdentity value)
    {
        return value != null;
    }
    public void SimulateClientNetworkDestroy()
    {
        isServer = false;
    }
    public void TestSetNetId(uint value)
    {
        netId = new NetworkInstanceId(value);
    }
    public void TestSetServer(bool value)
    {
        isServer = value;
    }
    public void TestSetClient(bool value)
    {
        isClient = value;
    }
    public void MarkForReset()
    {
        m_Reset = true;
    }
    private void Reset()
    {
        resetCalls++;
        if (!m_Reset)
            return;
        m_Reset = false;
        isServer = leaveServerAfterReset;
        isClient = leaveClientAfterReset;
        netId = new NetworkInstanceId(0);
        WasNativeResetCleanly = !isServer && !isClient && netId.Value == 0;
    }
}

public static class NetworkServer
{
    public static bool active = true;
    public static int unspawnCalls;
    public static bool markForResetOnUnspawn = true;
    public static Action<GameObject> afterUnspawn;
    static readonly Dictionary<NetworkInstanceId, GameObject> objects = new Dictionary<NetworkInstanceId, GameObject>();

    public static void Register(NetworkIdentity identity)
    {
        objects[identity.netId] = identity.gameObject;
    }
    public static GameObject FindLocalObject(NetworkInstanceId id)
    {
        GameObject result;
        return objects.TryGetValue(id, out result) ? result : null;
    }
    public static void UnSpawn(GameObject obj)
    {
        unspawnCalls++;
        var identity = obj.identity;
        objects.Remove(identity.netId);
        // Accepted HLAPI host ordering: local-client OnNetworkDestroy clears only
        // server state, then UnSpawn marks the identity for its native Reset.
        identity.SimulateClientNetworkDestroy();
        if (markForResetOnUnspawn)
            identity.MarkForReset();
        if (afterUnspawn != null)
            afterUnspawn(obj);
    }
    public static void Put(NetworkInstanceId id, GameObject obj)
    {
        objects[id] = obj;
    }
    public static void Remove(NetworkInstanceId id)
    {
        objects.Remove(id);
    }
    public static void Clear()
    {
        objects.Clear();
        unspawnCalls = 0;
        markForResetOnUnspawn = true;
        afterUnspawn = null;
        active = true;
    }
}

public sealed class TestOwners
{
    public int beforeDirectorUnspawnCalls;
    public void BeforeDirectorIdentityUnspawn(NetworkIdentity identity)
    {
        beforeDirectorUnspawnCalls++;
    }
}

public sealed class IdentityState
{
    public NetworkIdentity identity;
    public bool activeSelf;
    public bool spawned;
    public NetworkInstanceId registeredId;
    public bool hasRegisteredId;
}

public partial class RollbackHarness
{
    readonly List<IdentityState> identities = new List<IdentityState>();
    readonly GameObject directorRoot;
    readonly TestOwners owners = new TestOwners();
    static readonly BindingFlags PrivateInstance = BindingFlags.Instance | BindingFlags.NonPublic;
    static readonly MethodInfo ResetIdentity = typeof(NetworkIdentity).GetMethod("Reset", PrivateInstance);

    static InvalidOperationException Refuse(string message)
    {
        return new InvalidOperationException(message);
    }
    public RollbackHarness(IdentityState state)
    {
        identities.Add(state);
        directorRoot = null;
    }
    public void Execute()
    {
        RollbackOwnedIdentities();
    }
}

public static class NativeIdentityResetHostTests
{
    static void Check(bool condition, string message)
    {
        if (!condition)
            throw new Exception(message);
    }
    static IdentityState Spawned(uint id, bool initiallyActive)
    {
        var obj = new GameObject("owned", true);
        var identity = new NetworkIdentity(obj, id, true, true);
        NetworkServer.Register(identity);
        return new IdentityState { identity = identity, activeSelf = initiallyActive, spawned = true, registeredId = identity.netId,
                                   hasRegisteredId = true };
    }
    static bool Throws(Action action)
    {
        try
        {
            action();
            return false;
        }
        catch (InvalidOperationException)
        {
            return true;
        }
    }
    static void Reset()
    {
        NetworkServer.Clear();
    }

    public static int Main()
    {
        Reset();
        var success = Spawned(11, false);
        var successHarness = new RollbackHarness(success);
        successHarness.Execute();
        Check(success.identity.resetCalls == 1 && success.identity.netId.Value == 0, "same-ID host UnSpawn invokes native Reset");
        Check(!success.identity.isServer && !success.identity.isClient, "native Reset clears client and server flags");
        Check(success.spawned == false && !success.identity.gameObject.activeSelf, "successful cleanup restores inactive scene object");
        Check(success.identity.gameObject.setActiveCalls == 1 && !success.identity.gameObject.setActiveBeforeCleanReset,
              "activeSelf restoration occurs only after native reset completes");
        successHarness.Execute();
        Check(NetworkServer.unspawnCalls == 1 && success.identity.resetCalls == 1 && success.identity.gameObject.setActiveCalls == 2,
              "repeated cleanup is idempotent and does not unspawn or reset twice");

        Reset();
        var foreign = Spawned(21, false);
        var foreignObject = new GameObject("foreign", true);
        NetworkServer.afterUnspawn = obj => NetworkServer.Put(foreign.registeredId, foreignObject);
        Check(Throws(() => new RollbackHarness(foreign).Execute()), "captured foreign remapping refuses");
        Check(foreign.identity.resetCalls == 0 && foreign.identity.gameObject.setActiveCalls == 0 &&
                  ReferenceEquals(NetworkServer.FindLocalObject(foreign.registeredId), foreignObject),
              "foreign registration is retained before native reset or active-state restoration");

        Reset();
        var changed = Spawned(31, false);
        NetworkServer.afterUnspawn = obj => changed.identity.TestSetNetId(32);
        Check(Throws(() => new RollbackHarness(changed).Execute()), "unexpected changed nonzero ID refuses");
        Check(changed.identity.resetCalls == 0 && changed.identity.netId.Value == 32 && changed.identity.gameObject.setActiveCalls == 0,
              "foreign identity state is not reset or reactivated");

        Reset();
        NetworkServer.markForResetOnUnspawn = false;
        var unmarked = Spawned(41, false);
        Check(Throws(() => new RollbackHarness(unmarked).Execute()), "unmarked ineffective native Reset refuses");
        Check(unmarked.identity.resetCalls == 1 && unmarked.identity.netId.Value == 41 && unmarked.identity.gameObject.setActiveCalls == 0,
              "failed native Reset leaves recovery state retained");

        Reset();
        var serverResidual = Spawned(51, false);
        serverResidual.identity.leaveServerAfterReset = true;
        Check(Throws(() => new RollbackHarness(serverResidual).Execute()), "server residual flag refuses");
        Check(serverResidual.identity.resetCalls == 1 && serverResidual.identity.isServer &&
                  serverResidual.identity.gameObject.setActiveCalls == 0,
              "server residual state is retained");

        Reset();
        var clientResidual = Spawned(61, false);
        clientResidual.identity.leaveClientAfterReset = true;
        Check(Throws(() => new RollbackHarness(clientResidual).Execute()), "client residual flag refuses");
        Check(clientResidual.identity.resetCalls == 1 && clientResidual.identity.isClient &&
                  clientResidual.identity.gameObject.setActiveCalls == 0,
              "client residual state is retained");

        Console.WriteLine(
            "{\"success_reset\":true,\"repeat_cleanup\":true,\"foreign_remap_refused\":true,\"changed_id_refused\":true,\"ineffective_reset_refused\":true,\"residual_flags_refused\":true,\"active_restore_ordered\":true,\"all_passed\":true}");
        return 0;
    }
}
