using System;
using System.Collections.Generic;
using System.Linq;

// Host-only authored collaborators. No real gameplay event or server is raised.
public class GameObject
{
    public bool destroyed;
    public static implicit operator bool(GameObject value) { return value != null && !value.destroyed; }
}
public class CharacterBody : GameObject { public GameObject gameObject = new GameObject(); }
public class Force { public float magnitude; }
public class DamageInfo { public Force force = new Force(); }
public class DamageReport
{
    public CharacterBody victimBody, attackerBody;
    public float damageDealt;
    public DamageInfo damageInfo = new DamageInfo();
}
public static class Mathf { public static float Max(float a, float b) { return Math.Max(a, b); } }
public static class Time { public static float realtimeSinceStartup = 123f; }
public static class NetworkServer { public static void Destroy(GameObject value) { value.destroyed = true; } }
public class EnemyReport
{
    public int enemyDamageEvents, playerDamageEvents, deathGlobalEvents;
    public float damageToEnemy, damageToPlayer, maxIncomingForce;
}
public class Report
{
    public bool nativeFirstStageLifecycleDiagnosticAttempt, sourceStageLifecycleRecoveryRequired;
    public EnemyReport enemy = new EnemyReport();
}
public class ActorReport
{
    public int damageEvents, deathEvents;
    public float damageReceived, damageToPlayer, deathAt = -1;
    public bool dead;
    public Force lastDamageForce;
}
public class Actor { public CharacterBody body; public ActorReport report = new ActorReport(); }
public static class GlobalEventManager
{
    static Action<DamageReport> damage, death;
    public static int damageAdds, deathAdds, damageRemoves, deathRemoves;
    public static int throwOnAdd; // 1: before first add, 2: before second, 3: after second.
    public static Func<bool> ownedBeforeAdd;
    public static event Action<DamageReport> onServerDamageDealt
    {
        add {
            if (ownedBeforeAdd != null) SyntheticContract.Require(ownedBeforeAdd(), "Ownership missing before damage add");
            if (throwOnAdd == 1) throw new InvalidOperationException("injected first add failure");
            damageAdds++; damage += value;
        }
        remove { damageRemoves++; damage -= value; }
    }
    public static event Action<DamageReport> onCharacterDeathServer
    {
        add {
            if (ownedBeforeAdd != null) SyntheticContract.Require(ownedBeforeAdd(), "Ownership missing before death add");
            if (throwOnAdd == 2) throw new InvalidOperationException("injected second add failure");
            deathAdds++; death += value;
            if (throwOnAdd == 3) throw new InvalidOperationException("injected post-add failure");
        }
        remove { deathRemoves++; death -= value; }
    }
    public static Delegate[] DamageList { get { return damage == null ? new Delegate[0] : damage.GetInvocationList(); } }
    public static Delegate[] DeathList { get { return death == null ? new Delegate[0] : death.GetInvocationList(); } }
    public static void RaiseDamage(DamageReport value) { if (damage != null) damage(value); }
    public static void RaiseDeath(DamageReport value) { if (death != null) death(value); }
    public static void Reset()
    {
        damage = death = null;
        damageAdds = deathAdds = damageRemoves = deathRemoves = throwOnAdd = 0;
        ownedBeforeAdd = null;
    }
}
public partial class FixtureCoordinator
{
    public Report r = new Report();
    public CharacterBody enemyBody, enemyPlayer;
    public GameObject enemyMasterHost, sourceSceneInfoRoot, enemySceneHost, enemyTemplates;
    public List<Actor> directorActors = new List<Actor>();
    public FixtureOwner owner;
    public int cleanupCalls;
    public void CleanupDirectorActors()
    {
        SyntheticContract.Require(!owner.Owns && !GlobalEventManager.DamageList.Any(item => item.Target == owner) &&
                                  !GlobalEventManager.DeathList.Any(item => item.Target == owner),
                                  "Actor cleanup preceded observer detachment");
        cleanupCalls++;
    }
    public void CleanupRewardHosts() { }
    public void RestoreCatalogBodyTemplates() { }
    public void DeactivateSourceSceneInfo() { sourceSceneInfoRoot = null; }
}
public partial class FixtureOwner
{
    readonly FixtureCoordinator coordinator;
    bool observesEnemyActorEvents;
    GameObject enemyDetachedModel, enemyMaterial, enemySurface;
    public FixtureOwner(FixtureCoordinator value) { coordinator = value; value.owner = this; }
    public bool Owns { get { return observesEnemyActorEvents; } }
    public void Subscribe() { SubscribeEnemyActorEvents(); }
    public void Unsubscribe() { UnsubscribeEnemyActorEvents(); }
    static void Destroy(GameObject value) { value.destroyed = true; }
}
public static class SyntheticContract
{
    public static void Require(bool condition, string message) { if (!condition) throw new Exception(message); }
    static int unknownDamage, unknownDeath, laterDamage;
    static Action<DamageReport> unknownDamageHandler = value => unknownDamage++;
    static Action<DamageReport> unknownDeathHandler = value => unknownDeath++;
    static Action<DamageReport> laterDamageHandler = value => laterDamage++;
    static FixtureCoordinator Setup(bool native)
    {
        GlobalEventManager.Reset();
        unknownDamage = unknownDeath = laterDamage = 0;
        GlobalEventManager.onServerDamageDealt += unknownDamageHandler;
        GlobalEventManager.onCharacterDeathServer += unknownDeathHandler;
        var context = new FixtureCoordinator();
        context.r.nativeFirstStageLifecycleDiagnosticAttempt = native;
        context.enemyPlayer = new CharacterBody();
        context.enemyBody = native ? null : new CharacterBody();
        var actorBody = context.enemyBody ?? new CharacterBody();
        context.directorActors.Add(new Actor { body = actorBody });
        new FixtureOwner(context);
        return context;
    }
    static DamageReport Hit(Actor actor, CharacterBody player)
    {
        return new DamageReport { victimBody = actor.body, attackerBody = player, damageDealt = 17,
                                  damageInfo = new DamageInfo { force = new Force { magnitude = 4 } } };
    }
    static void AssertOnlyUnknownListeners(bool hasLaterObserver = false)
    {
        Require(GlobalEventManager.DamageList.Length == (hasLaterObserver ? 2 : 1) &&
                GlobalEventManager.DamageList[0].Equals(unknownDamageHandler) &&
                (!hasLaterObserver || GlobalEventManager.DamageList[1].Equals(laterDamageHandler)) &&
                GlobalEventManager.DeathList.Length == 1 && GlobalEventManager.DeathList[0].Equals(unknownDeathHandler),
                "An unrelated listener was removed or an owned listener leaked");
    }
    public static int Main()
    {
        int normalCases = 0, partialCases = 0;
        foreach (bool native in new[] { false, true })
        {
            var context = Setup(native);
            var owner = context.owner;
            GlobalEventManager.ownedBeforeAdd = () => owner.Owns;
            owner.NativeContextTail();
            Require(owner.Owns == native && GlobalEventManager.DamageList.Length == (native ? 2 : 1),
                    "Native context gate changed default registration timing");
            if (!native) owner.Subscribe(); // Existing fixture registration point.
            owner.Subscribe(); owner.Subscribe(); owner.NativeContextTail();
            Require(GlobalEventManager.damageAdds == 2 && GlobalEventManager.deathAdds == 2 && owner.Owns,
                    "Repeated preparation duplicated an owned subscription");
            // A later independent damage observer models the generic survivor
            // observer's separate ownership without invoking native gameplay.
            GlobalEventManager.onServerDamageDealt += laterDamageHandler;
            var actor = context.directorActors[0];
            var hit = Hit(actor, context.enemyPlayer);
            var force = hit.damageInfo.force;
            GlobalEventManager.RaiseDamage(hit);
            GlobalEventManager.RaiseDeath(hit);
            Require(actor.report.damageEvents == 1 && actor.report.damageReceived == 17 && actor.report.lastDamageForce == force &&
                    actor.report.deathEvents == 1 && actor.report.dead && actor.report.deathAt == Time.realtimeSinceStartup &&
                    unknownDamage == 1 && unknownDeath == 1 && laterDamage == 1,
                    "Forwarded production report callbacks did not run exactly once");
            Require(hit.victimBody == actor.body && hit.attackerBody == context.enemyPlayer && hit.damageDealt == 17 &&
                    hit.damageInfo.force == force, "A production callback mutated the damage input");
            var attackPlayer = new DamageReport { attackerBody = actor.body, victimBody = context.enemyPlayer, damageDealt = 3 };
            GlobalEventManager.RaiseDamage(attackPlayer);
            Require(actor.report.damageToPlayer == 3 && context.r.enemy.playerDamageEvents == 1 && context.r.enemy.damageToPlayer == 3,
                    "Existing player-damage observations changed");
            Require(context.r.enemy.enemyDamageEvents == (native ? 0 : 1) && context.r.enemy.deathGlobalEvents == (native ? 0 : 1),
                    "Native no-fixture branch invented legacy enemy counters");
            context.r.sourceStageLifecycleRecoveryRequired = true;
            owner.CleanupEnemy();
            Require(owner.Owns && GlobalEventManager.DamageList.Length == 3 && GlobalEventManager.DeathList.Length == 2 &&
                    context.cleanupCalls == 0, "Recovery discarded the retained listener owner");
            context.r.sourceStageLifecycleRecoveryRequired = false;
            owner.CleanupEnemy(); owner.CleanupEnemy(); owner.Unsubscribe();
            Require(!owner.Owns && GlobalEventManager.damageRemoves == 1 && GlobalEventManager.deathRemoves == 1,
                    "Normal/repeated cleanup detached owned delegates more than once");
            AssertOnlyUnknownListeners(true);
            GlobalEventManager.RaiseDamage(hit); GlobalEventManager.RaiseDeath(hit);
            Require(actor.report.damageEvents == 1 && actor.report.deathEvents == 1 && unknownDamage == 3 && unknownDeath == 2 &&
                    laterDamage == 3,
                    "Callbacks survived cleanup or unrelated listeners stopped");
            normalCases++;
        }
        foreach (int failure in new[] { 1, 2, 3 })
        {
            var context = Setup(true);
            var owner = context.owner;
            GlobalEventManager.ownedBeforeAdd = () => owner.Owns;
            GlobalEventManager.throwOnAdd = failure;
            bool threw = false;
            try { owner.NativeContextTail(); } catch (InvalidOperationException) { threw = true; }
            Require(threw && owner.Owns, "Partial registration lost its owner");
            GlobalEventManager.throwOnAdd = 0;
            owner.CleanupEnemy(); owner.CleanupEnemy();
            Require(!owner.Owns && GlobalEventManager.damageRemoves == 1 && GlobalEventManager.deathRemoves == 1,
                    "Partial registration was not retired exactly once");
            AssertOnlyUnknownListeners();
            owner.Subscribe(); owner.Subscribe();
            Require(GlobalEventManager.DamageList.Length == 2 && GlobalEventManager.DeathList.Length == 2,
                    "Cleaned partial registration could not be adopted exactly once");
            owner.CleanupEnemy();
            AssertOnlyUnknownListeners();
            partialCases++;
        }
        var unprepared = Setup(true);
        unprepared.owner.CleanupEnemy(); unprepared.owner.CleanupEnemy();
        AssertOnlyUnknownListeners();
        Require(GlobalEventManager.damageRemoves == 0 && GlobalEventManager.deathRemoves == 0,
                "Unprepared cleanup touched event registration");
        GlobalEventManager.Reset();
        Console.WriteLine("{\"normal_default_native_cases\":" + normalCases +
                          ",\"partial_subscription_failures\":" + partialCases +
                          ",\"unprepared_cleanup_case\":true,\"all_passed\":true,\"native_event_execution_claimed\":false}");
        return 0;
    }
}
