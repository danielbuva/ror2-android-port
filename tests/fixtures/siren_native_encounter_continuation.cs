
using System;
using System.Collections.Generic;
using System.Linq;
using UnityEngine;
using UnityEngine.Networking;
using UnityEngine.SceneManagement;
using RoR2;
namespace UnityEngine
{
public class Object
{
    public bool Destroyed;
    public static implicit operator bool(Object value) => !ReferenceEquals(value, null) && !value.Destroyed;
    public static bool operator !(Object value) => !((bool)value);
    public static bool operator ==(Object left, Object right)
    {
        bool leftNull = !((bool)left), rightNull = !((bool)right);
        return leftNull || rightNull ? leftNull == rightNull : ReferenceEquals(left, right);
    }
    public static bool operator !=(Object left, Object right) => !(left == right);
    public override bool Equals(object value) => ReferenceEquals(this, value);
    public override int GetHashCode() => base.GetHashCode();
}
public class GameObject : Object
{
    public Scene scene;
}
}
namespace UnityEngine.SceneManagement
{
public struct Scene : IEquatable<Scene>
{
    public bool valid, isLoaded;
    public int handle;
    public string name;
    public bool IsValid() => valid;
    public bool Equals(Scene other) => handle == other.handle;
    public override bool Equals(object other) => other is Scene && Equals((Scene)other);
    public override int GetHashCode() => handle;
    public static bool operator ==(Scene left, Scene right) => left.Equals(right);
    public static bool operator !=(Scene left, Scene right) => !left.Equals(right);
}
}
namespace UnityEngine.Networking
{
public struct NetworkInstanceId
{
    public uint Value;
    public static readonly NetworkInstanceId Invalid = new NetworkInstanceId { Value = 0 };
    public static bool operator ==(NetworkInstanceId left, NetworkInstanceId right) => left.Value == right.Value;
    public static bool operator !=(NetworkInstanceId left, NetworkInstanceId right) => left.Value != right.Value;
    public override bool Equals(object other) => other is NetworkInstanceId && ((NetworkInstanceId)other).Value == Value;
    public override int GetHashCode() => (int)Value;
}
public class NetworkIdentity : UnityEngine.Object
{
    public bool isServer;
    public NetworkInstanceId netId;
    public SceneId sceneId;
}
public struct SceneId
{
    public uint Value;
}
public static class NetworkServer
{
    public static bool active;
    public static readonly Dictionary<uint, UnityEngine.GameObject> LocalObjects = new Dictionary<uint, UnityEngine.GameObject>();
    public static UnityEngine.GameObject FindLocalObject(NetworkInstanceId id) => id.Value != 0 && LocalObjects.TryGetValue(id.Value,
                                                                                                                            out var value)
                                                                                      ? value
                                                                                      : null;
}
}
namespace RoR2
{
using UnityEngine.Networking;
public enum TeamIndex
{
    Monster,
    Player
}
public class ScriptedCombatEncounter : UnityEngine.Object
{
    public bool hasSpawnedServer;
}
public class CombatSquad : UnityEngine.Object
{
    public List<CharacterMaster> readOnlyMembersList = new List<CharacterMaster>();
}
public class BossGroup : UnityEngine.Object
{
    public CombatSquad combatSquad;
}
public class MinionOwnership : UnityEngine.Object
{
    public NetworkInstanceId NetworkownerMasterId;
}
public class CharacterMaster : UnityEngine.Object
{
    public NetworkInstanceId netId;
    public TeamIndex teamIndex;
    public bool playerCharacterMasterController;
    public UnityEngine.GameObject bodyPrefab, gameObject;
    public MinionOwnership minionOwnership;
}
public static class BodyCatalog
{
    public static UnityEngine.GameObject CatalogBoss;
    public static UnityEngine.GameObject FindBodyPrefab(string name) => CatalogBoss;
}
}
__PRODUCTION_CONTRACT__
public static class SirenEncounterContract
{
    public const string SceneName = "synthetic-source-scene";
    public const uint EncounterSceneId = 10;
}
public sealed class SirenEncounterSessionHarness
{
    sealed class OwnedMaster
    {
        public CharacterMaster master;
        public NetworkInstanceId networkId;
    }
    const string OriginalBossBodyName = "SyntheticBossBody";
    public bool disposed, cleanupStarted;
    public ScriptedCombatEncounter encounter;
    public BossGroup bossGroup;
    public Scene scene;
    public GameObject encounterObject;
    public NetworkIdentity identity;
    readonly List<OwnedMaster> ownedBossMasters = new List<OwnedMaster>();
    public void Capture(CharacterMaster master) => ownedBossMasters.Add(new OwnedMaster { master = master, networkId = master.netId });
    public void ClearCaptured() => ownedBossMasters.Clear();
    __PRODUCTION_METHOD__
    public static SirenEncounterSessionHarness Create()
    {
        NetworkServer.LocalObjects.Clear();
        NetworkServer.active = true;
        var value = new SirenEncounterSessionHarness();
        value.scene = new Scene { valid = true, isLoaded = true, handle = 7, name = "synthetic-source-scene" };
        value.encounterObject = new GameObject { scene = value.scene };
        value.identity =
            new NetworkIdentity { isServer = true, sceneId = new SceneId { Value = 10 }, netId = new NetworkInstanceId { Value = 10 } };
        NetworkServer.LocalObjects[10] = value.encounterObject;
        value.encounter = new ScriptedCombatEncounter { hasSpawnedServer = true };
        var squad = new CombatSquad();
        value.bossGroup = new BossGroup { combatSquad = squad };
        BodyCatalog.CatalogBoss = new GameObject();
        var master = new CharacterMaster { netId = new NetworkInstanceId { Value = 21 }, teamIndex = TeamIndex.Monster,
                                           bodyPrefab = BodyCatalog.CatalogBoss, gameObject = new GameObject() };
        squad.readOnlyMembersList.Add(master);
        value.Capture(master);
        NetworkServer.LocalObjects[21] = master.gameObject;
        return value;
    }
    public CharacterMaster Member => bossGroup.combatSquad.readOnlyMembersList[0];
}
public static class WitnessFixture
{
    static void Assert(bool value, string name)
    {
        if (!value)
            throw new Exception(name);
    }
    public static void Main()
    {
        float stageElapsed;
        Assert(SirenNativeEncounterContinuationContract.TryGetStageElapsedSeconds(500, 200, 295, out stageElapsed) && stageElapsed == 5,
               "late app uptime must not exhaust stage budget");
        Assert(!SirenNativeEncounterContinuationContract.TryGetStageElapsedSeconds(499, 500, 0, out stageElapsed),
               "realtime before origin refused");
        Assert(!SirenNativeEncounterContinuationContract.TryGetStageElapsedSeconds(500, 200, 301, out stageElapsed),
               "future stage offset refused");
        Assert(!SirenNativeEncounterContinuationContract.TryGetStageElapsedSeconds(float.NaN, 200, 0, out stageElapsed),
               "NaN clock refused");
        Assert(!SirenNativeEncounterContinuationContract.TryGetStageElapsedSeconds(500, float.PositiveInfinity, 0, out stageElapsed),
               "infinite origin refused");
        Assert(!SirenNativeEncounterContinuationContract.TryGetStageElapsedSeconds(500, 200, float.NegativeInfinity, out stageElapsed),
               "infinite offset refused");
        Assert(SirenNativeEncounterContinuationContract.TryGetWorldStageElapsedSeconds(300, 295, out stageElapsed) && stageElapsed == 5,
               "world clock uses stage offset");
        Assert(!SirenNativeEncounterContinuationContract.TryGetWorldStageElapsedSeconds(float.NaN, 0, out stageElapsed),
               "invalid world clock refused");
        uint[] ids;
        var good = SirenEncounterSessionHarness.Create();
        Assert(good.TryGetExactNativeBossNetworkIds(out ids) && ids.Length == 1 && ids[0] == 21, "exact captured native boss accepted");
        var foreign = SirenEncounterSessionHarness.Create();
        var foreignSameId = new CharacterMaster { netId = foreign.Member.netId, teamIndex = TeamIndex.Monster,
                                                  bodyPrefab = BodyCatalog.CatalogBoss, gameObject = new GameObject() };
        foreign.bossGroup.combatSquad.readOnlyMembersList[0] = foreignSameId;
        Assert(!foreign.TryGetExactNativeBossNetworkIds(out ids), "same network id foreign master refused");
        var mapChanged = SirenEncounterSessionHarness.Create();
        NetworkServer.LocalObjects[21] = new GameObject();
        Assert(!mapChanged.TryGetExactNativeBossNetworkIds(out ids), "network map replacement refused");
        NetworkServer.LocalObjects[21] = mapChanged.Member.gameObject;
        var wrongBody = SirenEncounterSessionHarness.Create();
        wrongBody.Member.bodyPrefab = new GameObject();
        Assert(!wrongBody.TryGetExactNativeBossNetworkIds(out ids), "body catalog mismatch refused");
        var missingCatalog = SirenEncounterSessionHarness.Create();
        BodyCatalog.CatalogBoss = null;
        Assert(!missingCatalog.TryGetExactNativeBossNetworkIds(out ids), "missing native catalog prefab refused");
        var player = SirenEncounterSessionHarness.Create();
        player.Member.playerCharacterMasterController = true;
        Assert(!player.TryGetExactNativeBossNetworkIds(out ids), "player master refused");
        var minion = SirenEncounterSessionHarness.Create();
        minion.Member.minionOwnership = new MinionOwnership { NetworkownerMasterId = new NetworkInstanceId { Value = 99 } };
        Assert(!minion.TryGetExactNativeBossNetworkIds(out ids), "foreign minion owner refused");
        var duplicate = SirenEncounterSessionHarness.Create();
        duplicate.bossGroup.combatSquad.readOnlyMembersList.Add(duplicate.Member);
        Assert(!duplicate.TryGetExactNativeBossNetworkIds(out ids), "duplicate network identity refused");
        var noCallback = SirenEncounterSessionHarness.Create();
        noCallback.ClearCaptured();
        Assert(!noCallback.TryGetExactNativeBossNetworkIds(out ids), "uncaptured squad member refused");
        var deadMember = SirenEncounterSessionHarness.Create();
        deadMember.Member.Destroyed = true;
        Assert(!deadMember.TryGetExactNativeBossNetworkIds(out ids), "Unity fake-null member refused");
        var wrongSource = SirenEncounterSessionHarness.Create();
        wrongSource.identity.sceneId = new SceneId { Value = 11 };
        Assert(!wrongSource.TryGetExactNativeBossNetworkIds(out ids), "non-ID-10 source identity refused");
        var serverInactive = SirenEncounterSessionHarness.Create();
        NetworkServer.active = false;
        Assert(!serverInactive.TryGetExactNativeBossNetworkIds(out ids), "inactive NetworkServer refused");
        NetworkServer.active = true;
        var encounterNotStarted = SirenEncounterSessionHarness.Create();
        encounterNotStarted.encounter.hasSpawnedServer = false;
        Assert(!encounterNotStarted.TryGetExactNativeBossNetworkIds(out ids), "native encounter not started refused");
        var wrongEncounterMap = SirenEncounterSessionHarness.Create();
        NetworkServer.LocalObjects[10] = new GameObject();
        Assert(!wrongEncounterMap.TryGetExactNativeBossNetworkIds(out ids), "ID-10 local identity map mismatch refused");
        var identityNotServer = SirenEncounterSessionHarness.Create();
        identityNotServer.identity.isServer = false;
        Assert(!identityNotServer.TryGetExactNativeBossNetworkIds(out ids), "nonserver encounter identity refused");
        var disposed = SirenEncounterSessionHarness.Create();
        disposed.disposed = true;
        Assert(!disposed.TryGetExactNativeBossNetworkIds(out ids), "disposed owner refused");
        var unloaded = SirenEncounterSessionHarness.Create();
        unloaded.scene.isLoaded = false;
        Assert(!unloaded.TryGetExactNativeBossNetworkIds(out ids), "unloaded source scene refused");
        System.Console.WriteLine("siren-native-boss-production-witness-all-passed");
    }
}
