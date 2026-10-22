using System;
using OriginalOwnerProbeObserver;

namespace UnityEngine
{
    public sealed class GameObject
    {
        static int nextId;
        readonly int id = ++nextId;
        public readonly string name;
        public GameObject(string name) { this.name = name; }
        public int GetInstanceID() => id;
    }
    public struct Vector3
    {
        public float x, y, z;
        public Vector3(float x, float y, float z) { this.x = x; this.y = y; this.z = z; }
    }
    public struct Quaternion { public static Quaternion identity => new Quaternion(); }
}

namespace RoR2
{
    using UnityEngine;
    public struct DamageInfo
    {
        public GameObject attacker;
        public Vector3 position;
        public float damage, force, procCoefficient;
        public bool crit, rejected;
    }
    public static class LegacyResourcesAPI
    {
        public static T Load<T>(string path) where T : class => new GameObject(path) as T;
    }
    namespace Projectile
    {
        using RoR2;
        public struct FireProjectileInfo
        {
            public GameObject projectilePrefab, owner;
            public Vector3 position;
            public Quaternion rotation;
            public float damage, force;
            public bool crit;
        }
        public sealed class ProjectileManager
        {
            public static ProjectileManager instance;
            public int Calls;
            public FireProjectileInfo Last;
            public void FireProjectile(FireProjectileInfo info) { Calls++; Last = info; }
        }
    }
    public sealed class GlobalEventManager
    {
        public void OnHitAllProcess(DamageInfo damageInfo, GameObject hitObject)
        {
            var projectileInfo = new Projectile.FireProjectileInfo();
            projectileInfo.projectilePrefab = LegacyResourcesAPI.Load<GameObject>("Prefabs/Projectiles/LightningStake");
            projectileInfo.position = damageInfo.position;
            projectileInfo.rotation = Quaternion.identity;
            projectileInfo.owner = damageInfo.attacker;
            projectileInfo.damage = damageInfo.damage * 2f;
            projectileInfo.force = 0f;
            projectileInfo.crit = damageInfo.crit;
            Projectile.ProjectileManager.instance.FireProjectile(projectileInfo);
        }
    }
}

internal static class LightningSourceCallFixture
{
    static void Require(bool value, string message) { if (!value) throw new InvalidOperationException(message); }

    static RoR2.DamageInfo Input(UnityEngine.GameObject owner)
    {
        return new RoR2.DamageInfo {
            attacker = owner,
            position = new UnityEngine.Vector3(4.5f, -2f, 8f),
            damage = 17.25f,
            force = 6f,
            procCoefficient = 0.8f,
            crit = true,
            rejected = false
        };
    }

    static void Reset(RoR2.Projectile.ProjectileManager manager)
    {
        manager.Calls = 0;
        manager.Last = default(RoR2.Projectile.FireProjectileInfo);
        Observer.LightningStakeSourceCall = null;
    }

    public static int Main()
    {
        var manager = new RoR2.Projectile.ProjectileManager();
        RoR2.Projectile.ProjectileManager.instance = manager;
        var owner = new UnityEngine.GameObject("attacker");
        var hit = new UnityEngine.GameObject("hit");

        // Absent observer is the ordinary path: one unchanged original call.
        Reset(manager);
        new RoR2.GlobalEventManager().OnHitAllProcess(Input(owner), hit);
        Require(manager.Calls == 1 && manager.Last.owner == owner && manager.Last.damage == 34.5f &&
                manager.Last.force == 0f && manager.Last.crit && manager.Last.position.x == 4.5f &&
                manager.Last.position.y == -2f && manager.Last.position.z == 8f &&
                manager.Last.projectilePrefab.name == "Prefabs/Projectiles/LightningStake",
                "default-off path changed original FireProjectile arguments or count");

        // Exact callback runs before the original call and sees both copied structs.
        Reset(manager);
        int seen = 0;
        Observer.LightningStakeSourceCall = (damage, hitObject, projectile) => {
            Require(manager.Calls == 0, "observer ran after original projectile call");
            Require(damage is RoR2.DamageInfo && hitObject == hit && projectile is RoR2.Projectile.FireProjectileInfo,
                "observer operands lost their source types or hit-object identity");
            var capturedDamage = (RoR2.DamageInfo)damage;
            var capturedProjectile = (RoR2.Projectile.FireProjectileInfo)projectile;
            Require(capturedDamage.position.x == 4.5f && capturedDamage.damage == 17.25f && capturedDamage.force == 6f &&
                    capturedDamage.crit && capturedProjectile.position.y == -2f && capturedProjectile.damage == 34.5f &&
                    capturedProjectile.force == 0f && capturedProjectile.crit &&
                    capturedProjectile.projectilePrefab.name == "Prefabs/Projectiles/LightningStake" &&
                    capturedProjectile.owner == capturedDamage.attacker,
                "observer did not receive exact original hit and computed projectile values");
            seen++;
        };
        new RoR2.GlobalEventManager().OnHitAllProcess(Input(owner), hit);
        Require(seen == 1 && manager.Calls == 1 && manager.Last.damage == 34.5f && manager.Last.owner == owner,
            "instrumented path did not preserve exactly one original call after observation");

        // Bridge contains observer exceptions; the source call still executes once.
        Reset(manager);
        Observer.LightningStakeSourceCall = (damage, hitObject, projectile) => { throw new ApplicationException("fixture observer failure"); };
        new RoR2.GlobalEventManager().OnHitAllProcess(Input(owner), hit);
        Require(manager.Calls == 1 && manager.Last.damage == 34.5f && manager.Last.owner == owner,
            "throwing observer replaced or skipped the original call");
        Observer.LightningStakeSourceCall = null;
        Console.WriteLine("PASS default-off, exact pre-call operand capture, original call preservation, and contained observer throw");
        return 0;
    }
}
