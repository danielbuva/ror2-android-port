using System;
using System.Collections;
using System.Collections.Generic;
using RoR2;
using RoR2.Projectile;
using UnityEngine;
using UnityEngine.Networking;
using Path = System.IO.Path;

namespace Ror2Lab.Reference
{
    internal sealed class ProjectileObservation
    {
        private static ProjectileObservation active;
        private readonly CharacterBody player;
        private readonly CharacterBody target;
        private readonly Trace trace;

        private ProjectileObservation(CharacterBody player, CharacterBody target, GenericSkill skill)
        {
            if (!skill || skill.skillDef != skill.defaultSkillDef)
                throw new InvalidOperationException("Projectile capture requires the stock skill.");
            this.player = player;
            this.target = target;
            trace = new Trace
            {
                cast_seconds = Time.realtimeSinceStartupAsDouble,
                cast_frame = Time.frameCount,
                activation_state = skill.skillDef.activationState.stateType.FullName,
                player_position = player.transform.position,
                move_input = player.inputBank.moveVector,
                aim_origin = player.inputBank.aimOrigin,
                aim_direction = player.inputBank.aimDirection,
                target_position = target.transform.position,
                target_core = target.corePosition,
                target_network_id = target.netId.Value
            };
        }

        public static ProjectileObservation Begin(CharacterBody player, CharacterBody target, GenericSkill skill)
        {
            active = new ProjectileObservation(player, target, skill);
            GlobalEventManager.onServerDamageDealt += active.OnDamage;
            return active;
        }

        public IEnumerator SampleTicks()
        {
            while (active == this)
            {
                yield return new WaitForFixedUpdate();
                if (active != this || !player)
                    yield break;
                foreach (NetworkIdentity identity in NetworkServer.objects.Values)
                {
                    if (!identity || !identity.TryGetComponent(out ProjectileController projectile) ||
                        projectile.owner != player.gameObject)
                        continue;
                    trace.projectiles.Add(new Sample
                    {
                        frame = Time.frameCount,
                        seconds = Time.realtimeSinceStartupAsDouble,
                        fixed_seconds = Time.fixedTime,
                        network_id = projectile.netId.Value,
                        prefab = Prefab(projectile),
                        position = projectile.transform.position,
                        direction = projectile.transform.forward,
                        player_position = player.transform.position
                    });
                }
            }
        }

        private void OnDamage(DamageReport damage)
        {
            DamageInfo info = damage.damageInfo;
            if (damage.attackerBody != player || !info.inflictor ||
                !info.inflictor.TryGetComponent(out ProjectileController projectile) || projectile.owner != player.gameObject)
                return;
            trace.damage.Add(new Hit
            {
                frame = Time.frameCount,
                seconds = Time.realtimeSinceStartupAsDouble,
                projectile_network_id = projectile.netId.Value,
                projectile_prefab = Prefab(projectile),
                planned_target = damage.victimBody == target,
                victim = damage.victimBody ? BodyCatalog.GetBodyName(damage.victimBody.bodyIndex) : null,
                victim_network_id = damage.victimBody ? damage.victimBody.netId.Value : 0,
                position = info.position,
                damage = damage.damageDealt,
                crit = info.crit,
                damage_type = info.damageType.damageType.ToString(),
                dot_type = damage.dotType.ToString()
            });
        }

        private static string Prefab(ProjectileController projectile)
        {
            GameObject prefab = ProjectileCatalog.GetProjectilePrefab(projectile.catalogIndex);
            return prefab ? prefab.name : projectile.name;
        }

        public void Write(string folder)
        {
            Stop();
            CaptureEvidence.WriteJson(Path.Combine(folder, "projectile-trace.json"), trace);
        }

        public static void Stop()
        {
            if (active == null)
                return;
            GlobalEventManager.onServerDamageDealt -= active.OnDamage;
            active = null;
        }

        [Serializable]
        private sealed class Trace
        {
            public double cast_seconds;
            public int cast_frame;
            public string activation_state;
            public Vector3 player_position, move_input, aim_origin, aim_direction, target_position, target_core;
            public uint target_network_id;
            public List<Sample> projectiles = new List<Sample>();
            public List<Hit> damage = new List<Hit>();
        }

        [Serializable]
        private sealed class Sample
        {
            public int frame;
            public double seconds;
            public float fixed_seconds;
            public uint network_id;
            public string prefab;
            public Vector3 position, direction, player_position;
        }

        [Serializable]
        private sealed class Hit
        {
            public int frame;
            public double seconds;
            public uint projectile_network_id, victim_network_id;
            public string projectile_prefab, victim, damage_type, dot_type;
            public bool planned_target, crit;
            public float damage;
            public Vector3 position;
        }
    }
}
