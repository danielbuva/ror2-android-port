using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using EntityStates.Loader;
using HarmonyLib;
using RoR2;
using RoR2.Projectile;
using UnityEngine;
using UnityEngine.Networking;
using Path = System.IO.Path;

namespace Ror2Lab.Reference
{
    internal sealed class GrappleObservation
    {
        private static GrappleObservation active;
        private readonly CharacterBody owner;
        private readonly EntityStateMachine hookMachine;
        private readonly float releaseAt;
        private readonly string secondary;
        private readonly List<Sample> samples = new List<Sample>();
        private bool sampling = true;

        private GrappleObservation(CharacterBody owner, float hold)
        {
            this.owner = owner;
            hookMachine = EntityStateMachine.FindByCustomName(owner.gameObject, "Hook");
            if (!hookMachine || !owner.characterMotor || owner.skillLocator.secondary.skillDef != owner.skillLocator.secondary.defaultSkillDef)
                throw new InvalidOperationException("The grapple recording requires Loader's default Secondary and native Hook machine.");
            secondary = owner.skillLocator.secondary.skillDef.skillNameToken;
            releaseAt = Time.fixedTime + hold;
        }

        public static void Install(Harmony harmony)
        {
            var poll = AccessTools.Method(typeof(PlayerCharacterMasterController), "PollButtonInput");
            harmony.Patch(poll, new HarmonyMethod(typeof(GrappleObservation), nameof(ReadButton)),
                new HarmonyMethod(typeof(GrappleObservation), nameof(SupplyButton)));
        }

        public static GrappleObservation Begin(CharacterBody owner, float hold)
        {
            active = new GrappleObservation(owner, hold);
            return active;
        }

        private static void ReadButton(InputBankTest ___bodyInputs, out InputBankTest.ButtonState __state)
        {
            __state = active != null && ___bodyInputs == active.owner.inputBank
                ? ___bodyInputs.skill2 : default;
        }

        private static void SupplyButton(InputBankTest ___bodyInputs, InputBankTest.ButtonState __state)
        {
            if (active == null || ___bodyInputs != active.owner.inputBank)
                return;
            ___bodyInputs.skill2 = __state;
            ___bodyInputs.skill2.PushState(Time.fixedTime < active.releaseAt);
            ___bodyInputs.moveVector = Vector3.zero;
        }

        public IEnumerator SampleTicks()
        {
            while (sampling && owner)
            {
                yield return new WaitForFixedUpdate();
                if (!sampling || !owner)
                    yield break;
                var fire = hookMachine.state as FireHook;
                GameObject hook = fire?.hookInstance;
                var stick = hook ? hook.GetComponent<ProjectileStickOnImpact>() : null;
                Transform victim = stick ? stick.stuckTransform : null;
                samples.Add(new Sample
                {
                    fixed_seconds = Time.fixedTime,
                    seconds = Time.realtimeSinceStartup,
                    secondary_skill = secondary,
                    secondary_held = owner.inputBank.skill2.down,
                    move_input = owner.inputBank.moveVector,
                    motor_position = owner.transform.position,
                    motor_velocity = owner.characterMotor.velocity,
                    hook_machine = hookMachine.state?.GetType().FullName,
                    hook_network_id = hook ? hook.GetComponent<NetworkIdentity>()?.netId.ToString() : null,
                    hook_position = hook ? hook.transform.position : Vector3.zero,
                    projectile_state = hook ? hook.GetComponent<EntityStateMachine>()?.state?.GetType().FullName : null,
                    stuck = stick && stick.stuck,
                    terrain = stick && stick.NetworkhitHurtboxIndex == -2 && victim && victim.gameObject.layer == LayerIndex.world.intVal,
                    victim = victim ? victim.name : null
                });
            }
        }

        public void Write(string folder)
        {
            Stop();
            using (var file = new StreamWriter(Path.Combine(folder, "grapple-ticks.jsonl")))
                foreach (Sample sample in samples)
                    file.WriteLine(JsonUtility.ToJson(sample));
        }

        public static void Stop()
        {
            if (active == null)
                return;
            active.sampling = false;
            active = null;
        }

        [Serializable]
        private sealed class Sample
        {
            public float fixed_seconds;
            public float seconds;
            public bool secondary_held, stuck, terrain;
            public Vector3 move_input, motor_position, motor_velocity, hook_position;
            public string secondary_skill, hook_machine, hook_network_id, projectile_state, victim;
        }
    }
}
