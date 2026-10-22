using System;
using System.Collections.Generic;

namespace UnityEngine
{
    public class Object
    {
        static int nextObjectId;
        readonly int objectId = ++nextObjectId;
        bool destroyed;
        public bool Destroyed { get => destroyed; set => destroyed = value; }
        public int GetInstanceID() => objectId;
        public static implicit operator bool(Object value) => !ReferenceEquals(value, null) && !value.destroyed;
    }
    public sealed class GameObject : Object
    {
        static int nextId;
        readonly int id = ++nextId;
        readonly Dictionary<Type, object> components = new Dictionary<Type, object>();
        public readonly string name;
        public Transform transform = new Transform();
        public GameObject(string name) { this.name = name; }
        public new int GetInstanceID() => id;
        public T GetComponent<T>() where T : class
        { components.TryGetValue(typeof(T), out var value); return (T)value; }
        public void AddComponent<T>(T value) where T : class { components[typeof(T)] = value; }
    }
    public sealed class Transform : Object { public Vector3 position; }
    public struct Vector3
    {
        public float x, y, z;
        public static Vector3 zero => new Vector3();
        public Vector3(float x, float y, float z) { this.x = x; this.y = y; this.z = z; }
    }
    public static class Time { public static int frameCount = 42; }
}

namespace UnityEngine.Networking
{
    public struct NetworkInstanceId { public uint Value; }
    public sealed class NetworkIdentity : UnityEngine.Object { public NetworkInstanceId netId; }
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
    public sealed class CharacterMotor : Object { public Vector3 velocity; }
    public sealed class CharacterBody : Object
    {
        public CharacterMotor characterMotor;
        readonly Dictionary<Type, object> components = new Dictionary<Type, object>();
        public T GetComponent<T>() where T : class { components.TryGetValue(typeof(T), out var value); return (T)value; }
        public void AddComponent<T>(T value) where T : class { components[typeof(T)] = value; }
    }
    public static class ProjectileCatalog { public static int FindProjectileIndex(string name) => name == "LightningStake" ? 117 : -1; }
}

namespace RoR2.Projectile
{
    using UnityEngine;
    public struct FireProjectileInfo
    {
        public GameObject projectilePrefab, owner;
        public Vector3 position;
        public float damage, force;
        public bool crit;
    }
}

public sealed partial class PortSession
{
    [Serializable]
    public sealed class LightningStakeSourceCallObservation
    {
        public int frame, damageAttackerInstance, projectileOwnerInstance, ownerBodyInstance, hitObjectInstance;
        public int projectilePrefabInstance, projectileCatalogIndex;
        public uint damageAttackerNetworkId, projectileOwnerNetworkId, ownerBodyNetworkId;
        public string projectilePrefabName, damagePosition, projectilePosition, ownerPosition, ownerVelocity, hitPosition;
        public float damageInfoDamage, damageInfoForce, damageInfoProcCoefficient, projectileDamage, projectileForce;
        public bool damageInfoCrit, projectileCrit, damageInfoRejected, attackerMatchesProjectileOwner;
        public bool hasOwnerBody, hasAttackerNetworkIdentity, hasProjectileOwnerNetworkIdentity, hasOwnerBodyNetworkIdentity,
            hasProjectilePrefab, isLightningStakeName;
        public bool finiteDamagePosition, finiteProjectilePosition, finiteOwnerPosition, finiteOwnerVelocity, finiteHitPosition,
            finiteDamageInfoDamage, finiteDamageInfoForce, finiteProjectileDamage, finiteProjectileForce;
    }
    [Serializable]
    public sealed class LightningStakeSourceCallReport
    {
        public string status;
        public int sourceCallCount, captureFailures;
        public string firstCaptureFailureType;
        public bool historyCapped, detached;
        public List<LightningStakeSourceCallObservation> sourceCalls = new List<LightningStakeSourceCallObservation>();
    }
    public static int IncrementBoundedCount(int value) => value >= 1000000 ? 1000000 : value + 1;
}
