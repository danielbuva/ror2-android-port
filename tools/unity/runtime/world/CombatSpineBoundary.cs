// Subsystem: world/director (game path). Owner map: docs/ARCHITECTURE.md#ownership.
// Session phases: setup PrepareCombatConfigs, PrepareCombatScene (CombatSpineSession); teardown CleanupCombatScene, then CleanupCombatConfigs (Dispose).
using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using EntityStates;
using EntityStates.Commando;
using EntityStates.Commando.CommandoWeapon;
using RoR2;
using RoR2.Projectile;
using UnityEngine;
using UnityEngine.Networking;

// Integrated original skills and damage. Owned visuals/audio exclusions do not replace simulation.
public sealed partial class PortSession
{
    [Serializable]
    public class CombatReport
    {
        public int secondaryEntries, utilityEntries, specialEntries, projectiles, projectileSoundGuards, damageEvents;
        public float healthBefore, healthAfter, damageDealt, lastDamage;
        public string bodyState, weaponState, secondaryDefinition, utilityDefinition, specialDefinition;
        public bool targetServer, targetHurtBox, cleaned;
        public Vector3 targetCenter, aimOrigin;
        public int hurtBoxLayer, hurtBoxes;
        public string meleeCurve, meleeAnimatorController;
        public float meleeCurvePeak, meleeHitBoxAimDistance;
        public int meleeAttackTicksPeak, meleeHitBoxCount, meleeActiveHitBoxes, meleeAnimationStateHash;
    }
    CombatSpineSession combatSpineSession;
    CombatSpineSession GetCombatSpineSession()
    {
        if (combatSpineSession == null)
            combatSpineSession = new CombatSpineSession(this);
        return combatSpineSession;
    }
    EntityStateConfiguration[] PrepareCombatConfigs(SessionConfig cfg)
    {
        return GetCombatSpineSession().PrepareCombatConfigs(cfg);
    }
    void PrepareCombatScene(CharacterBody player, SessionConfig cfg)
    {
        GetCombatSpineSession().PrepareCombatScene(player, cfg);
    }
    Vector2 CombatAim(CharacterBody player)
    {
        return GetCombatSpineSession().CombatAim(player);
    }
    void ObserveCombatDamage(DamageReport report)
    {
        GetCombatSpineSession().ObserveCombatDamage(report);
    }
    void ObserveCombat(CharacterBody player, EntityStateMachine machine)
    {
        GetCombatSpineSession().ObserveCombat(player, machine);
    }
    void CleanupCombatScene()
    {
        GetCombatSpineSession().CleanupCombatScene();
    }
    void CleanupCombatConfigs()
    {
        GetCombatSpineSession().Dispose();
    }

    // Create on first use and retain for partial setup, repeated cleanup and later
    // observations. Scene cleanup stays separate; Dispose releases configs only.
    sealed class CombatSpineSession : IDisposable
    {
        readonly PortSession coordinator;
        readonly List<EntityStateConfiguration> combatConfigs = new List<EntityStateConfiguration>();
        readonly HashSet<int> observedProjectiles = new HashSet<int>();
        GameObject projectileTemplateHost, projectileHost, targetHost, targetVisual;
        GameObject ownedFMJ;
        CharacterBody targetBody;
        Material combatMaterial;
        Texture2D combatTexture;
        EntityState lastCombatBody, lastCombatWeapon;
        static readonly FieldInfo meleeAttackTicksField =
            typeof(BasicMeleeAttack).GetField("meleeAttackTicks", BindingFlags.Instance | BindingFlags.NonPublic);
        public CombatSpineSession(PortSession coordinator)
        {
            this.coordinator = coordinator;
        }
        public EntityStateConfiguration[] PrepareCombatConfigs(SessionConfig cfg)
        {
            coordinator.r.combat = new CombatReport();
            SilentProjectileBoundary.prepared = 0;
            foreach (var asset in new[] { cfg.secondaryConfigAsset, cfg.utilityConfigAsset, cfg.specialConfigAsset })
            {
                var original = coordinator.artifactBundle.LoadAsset<EntityStateConfiguration>(asset);
                coordinator.Check(original, "Original default skill configuration missing: " + asset);
                var copy = Instantiate(original);
                copy.serializedFieldsCollection.serializedFields = original.serializedFieldsCollection.serializedFields.ToArray();
                for (int i = 0; i < copy.serializedFieldsCollection.serializedFields.Length; i++)
                {
                    var name = copy.serializedFieldsCollection.serializedFields[i].fieldName;
                    if (name == "attackSoundString")
                        copy.serializedFieldsCollection.serializedFields[i].fieldValue.stringValue = "";
                    if (name == "effectPrefab" && ((Type)copy.targetType) == typeof(FireFMJ))
                        copy.serializedFieldsCollection.serializedFields[i].fieldValue.objectValue = null;
                    if (name == "projectilePrefab")
                    {
                        var originalProjectile = copy.serializedFieldsCollection.serializedFields[i].fieldValue.objectValue as GameObject;
                        coordinator.Check(originalProjectile, "Original FMJ projectile missing");
                        projectileTemplateHost = new GameObject("Owned silent projectile template");
                        projectileTemplateHost.SetActive(false);
                        ownedFMJ = Instantiate(originalProjectile, projectileTemplateHost.transform);
                        ownedFMJ.SetActive(true);
                        ownedFMJ.AddComponent<SilentProjectileBoundary>();
                        foreach (var component in ownedFMJ.GetComponentsInChildren<MonoBehaviour>(true))
                        {
                            if (component.GetType().Name.StartsWith("Ak", StringComparison.Ordinal))
                            {
                                DestroyImmediate(component);
                                continue;
                            }
                            foreach (var field in component.GetType().GetFields(BindingFlags.Public | BindingFlags.Instance))
                            {
                                // Original AkEventIdArg bypasses native ID lookup only for null, not empty strings.
                                if (field.FieldType == typeof(string) &&
                                    field.Name.IndexOf("sound", StringComparison.OrdinalIgnoreCase) >= 0)
                                    field.SetValue(component, null);
                                if (typeof(NetworkSoundEventDef).IsAssignableFrom(field.FieldType) || field.Name == "flightSoundLoop")
                                    field.SetValue(component, null);
                                if (field.FieldType == typeof(GameObject) &&
                                    new[] { "ghostPrefab", "impactEffect", "impactEffectPrefab", "hitEffectPrefab" }.Contains(field.Name))
                                    field.SetValue(component, null);
                            }
                        }
                        // Readability marker follows the actual original projectile, without changing its motion/collision.
                        var marker = GameObject.CreatePrimitive(PrimitiveType.Cube);
                        DestroyImmediate(marker.GetComponent<Collider>());
                        marker.name = "Owned FMJ marker";
                        marker.layer = 30;
                        marker.transform.SetParent(ownedFMJ.transform, false);
                        marker.transform.localScale = new Vector3(.15f, .15f, 1.5f);
                        combatMaterial = new Material(Resources.Load<Shader>("CommandoPreview"));
                        combatTexture = new Texture2D(1, 1);
                        combatTexture.SetPixel(0, 0, Color.cyan);
                        combatTexture.Apply();
                        combatMaterial.mainTexture = combatTexture;
                        marker.GetComponent<Renderer>().sharedMaterial = combatMaterial;
                        copy.serializedFieldsCollection.serializedFields[i].fieldValue.objectValue = ownedFMJ;
                    }
                }
                combatConfigs.Add(copy);
            }
            return combatConfigs.ToArray();
        }
        public void PrepareCombatScene(CharacterBody player, SessionConfig cfg)
        {
            coordinator.r.phase = "integrated-combat-setup";
            coordinator.Save();
            coordinator.Check(!ProjectileManager.instance, "Existing projectile manager");
            projectileHost = new GameObject("Owned original projectile manager");
            projectileHost.AddComponent<ProjectileManager>();
            if (cfg.integratedWorld)
            {
                GlobalEventManager.onServerDamageDealt += ObserveCombatDamage;
                return;
            }
            targetHost = Instantiate(coordinator.artifactBundle.LoadAsset<GameObject>(cfg.bodyAsset));
            targetHost.name = "Owned original damage target";
            foreach (var component in targetHost.GetComponentsInChildren<MonoBehaviour>(true))
            {
                component.enabled = false;
                if (component.GetType().Name.StartsWith("Ak", StringComparison.Ordinal))
                    DestroyImmediate(component);
            }
            foreach (var renderer in targetHost.GetComponentsInChildren<Renderer>(true))
                renderer.enabled = false;
            foreach (var collider in targetHost.GetComponentsInChildren<Collider>(true))
                collider.enabled = false;
            targetBody = targetHost.GetComponent<CharacterBody>();
            Call(targetBody, "Awake");
            Call(targetBody.healthComponent, "Awake");
            Call(targetBody.teamComponent, "Awake");
            // Same recovered direct animator binding as the accepted player display, before original Awake.
            var animator = targetBody.modelLocator.modelTransform.GetComponent<Animator>();
            animator.avatar = coordinator.artifactBundle.LoadAsset<Avatar>(cfg.displayAssets[1]);
            animator.runtimeAnimatorController = coordinator.artifactBundle.LoadAsset<RuntimeAnimatorController>(cfg.displayAssets[0]);
            animator.enabled = false;
            targetBody.teamComponent.teamIndex = TeamIndex.Monster;
            targetBody.baseMaxHealth = 5000;
            targetBody.RecalculateStats();
            targetBody.healthComponent.health = targetBody.maxHealth;
            targetHost.transform.position = player.transform.position + Vector3.forward * 5;
            var hurt = targetBody.mainHurtBox;
            foreach (var box in targetBody.hurtBoxGroup.hurtBoxes)
            {
                box.enabled = true;
                box.teamIndex = TeamIndex.Monster;
                box.GetComponent<Collider>().enabled = true;
                for (var t = box.transform; t && t != targetHost.transform; t = t.parent)
                    t.gameObject.SetActive(true);
            }
            NetworkServer.Spawn(targetHost);
            targetHost.SetActive(true);
            Physics.SyncTransforms();
            targetVisual = GameObject.CreatePrimitive(PrimitiveType.Capsule);
            DestroyImmediate(targetVisual.GetComponent<Collider>());
            targetVisual.name = "Owned target health display";
            targetVisual.layer = 30;
            targetVisual.transform.position = hurt.transform.position;
            targetVisual.GetComponent<Renderer>().sharedMaterial = combatMaterial;
            coordinator.r.combat.targetServer = targetBody.isServer;
            coordinator.r.combat.targetHurtBox = hurt.healthComponent == targetBody.healthComponent;
            coordinator.r.combat.healthBefore = targetBody.healthComponent.health;
            coordinator.r.combat.targetCenter = targetBody.corePosition;
            coordinator.r.combat.aimOrigin = player.inputBank.aimOrigin;
            coordinator.r.combat.hurtBoxLayer = hurt.gameObject.layer;
            coordinator.r.combat.hurtBoxes = targetBody.hurtBoxGroup.hurtBoxes.Length;
            coordinator.r.combat.secondaryDefinition = ((ScriptableObject)player.skillLocator.secondary.skillDef).name;
            coordinator.r.combat.utilityDefinition = ((ScriptableObject)player.skillLocator.utility.skillDef).name;
            coordinator.r.combat.specialDefinition = ((ScriptableObject)player.skillLocator.special.skillDef).name;
            coordinator.Check(coordinator.r.combat.targetServer && coordinator.r.combat.targetHurtBox &&
                                  coordinator.r.combat.healthBefore == 5000,
                              "Original target server/hurtbox/health contract");
            GlobalEventManager.onServerDamageDealt += ObserveCombatDamage;
            coordinator.Save();
        }
        public Vector2 CombatAim(CharacterBody player)
        {
            var delta = targetBody.corePosition - player.inputBank.aimOrigin;
            return new Vector2(delta.x, delta.z).normalized;
        }
        public void ObserveCombatDamage(DamageReport report)
        {
            if (coordinator.r.integratedWorld && coordinator.r.world != null && coordinator.r.world.blueEliteHits.Count < 4 &&
                report.attackerBody && report.attackerBody.HasBuff(RoR2Content.Buffs.AffixBlue) && report.damageInfo != null)
            {
                var hit = report.damageInfo.position;
                coordinator.r.world.blueEliteHits.Add(
                    new BlueEliteHitObservation { frame = Time.frameCount, seconds = coordinator.r.world.seconds,
                                                  attacker = Position(report.attackerBody.corePosition), hit = Position(hit),
                                                  victim = report.victimBody ? Position(report.victimBody.corePosition) : "missing",
                                                  finiteHit = Finite(hit) });
                coordinator.Save();
            }
            if (coordinator.r.integratedWorld)
            {
                if (report.attackerBody != coordinator.worldPlayer)
                    return;
            }
            else if (report.victimBody != targetBody)
                return;
            coordinator.r.combat.damageEvents++;
            coordinator.r.combat.lastDamage = report.damageDealt;
            coordinator.r.combat.damageDealt += report.damageDealt;
        }
        public void ObserveCombat(CharacterBody player, EntityStateMachine machine)
        {
            var weapon = player.skillLocator.primary.stateMachine.state;
            coordinator.r.combat.weaponState = weapon.GetType().FullName;
            coordinator.r.combat.bodyState = machine.state.GetType().FullName;
            var melee = weapon as BasicMeleeAttack;
            if (melee != null)
            {
                var animator = player.modelLocator && player.modelLocator.modelTransform
                                   ? player.modelLocator.modelTransform.GetComponent<Animator>()
                                   : null;
                var curve = melee.mecanimHitboxActiveParameter;
                coordinator.r.combat.meleeCurve = curve;
                if (animator)
                {
                    coordinator.r.combat.meleeAnimatorController =
                        animator.runtimeAnimatorController ? animator.runtimeAnimatorController.name : "";
                    if (!string.IsNullOrEmpty(curve) && animator.parameters.Any(parameter => parameter.name == curve))
                        coordinator.r.combat.meleeCurvePeak = Mathf.Max(coordinator.r.combat.meleeCurvePeak, animator.GetFloat(curve));
                    var layer = animator.GetLayerIndex("Gesture, Override");
                    if (layer >= 0)
                        coordinator.r.combat.meleeAnimationStateHash = animator.GetCurrentAnimatorStateInfo(layer).shortNameHash;
                }
                if (meleeAttackTicksField != null)
                    coordinator.r.combat.meleeAttackTicksPeak =
                        Mathf.Max(coordinator.r.combat.meleeAttackTicksPeak, (int)meleeAttackTicksField.GetValue(melee));
                var group = melee.OverlapAttack != null ? melee.OverlapAttack.hitBoxGroup : null;
                if (group && group.hitBoxes != null)
                {
                    coordinator.r.combat.meleeHitBoxCount = group.hitBoxes.Length;
                    coordinator.r.combat.meleeActiveHitBoxes =
                        group.hitBoxes.Count(box => box && box.enabled && box.gameObject.activeInHierarchy);
                    if (coordinator.r.world != null)
                        foreach (var box in group.hitBoxes)
                            if (box && box.enabled && box.gameObject.activeInHierarchy)
                            {
                                var distance = Vector3.Distance(box.transform.position, coordinator.r.world.combatAimTarget);
                                if (coordinator.r.combat.meleeHitBoxAimDistance <= 0 ||
                                    distance < coordinator.r.combat.meleeHitBoxAimDistance)
                                    coordinator.r.combat.meleeHitBoxAimDistance = distance;
                            }
                }
            }
            if (weapon != lastCombatWeapon)
            {
                if (weapon is FireFMJ)
                    coordinator.r.combat.secondaryEntries++;
                if (weapon is FireBarrage)
                    coordinator.r.combat.specialEntries++;
                lastCombatWeapon = weapon;
            }
            if (machine.state != lastCombatBody)
            {
                if (machine.state is DodgeState)
                    coordinator.r.combat.utilityEntries++;
                lastCombatBody = machine.state;
            }
            // The local server owns every spawned original projectile. Its live identity
            // registry avoids traversing the complete Unity object graph each frame.
            foreach (var identity in NetworkServer.objects.Values)
            {
                if (!identity)
                    continue;
                var projectile = identity.GetComponent<ProjectileController>();
                if (projectile)
                    observedProjectiles.Add(projectile.GetInstanceID());
            }
            coordinator.r.combat.projectiles = observedProjectiles.Count;
            coordinator.r.combat.projectileSoundGuards = SilentProjectileBoundary.prepared;
            coordinator.r.combat.healthAfter = targetBody ? targetBody.healthComponent.health : 0;
        }
        public void CleanupCombatScene()
        {
            GlobalEventManager.onServerDamageDealt -= ObserveCombatDamage;
            foreach (var projectile in FindObjectsOfType<ProjectileController>())
                NetworkServer.Destroy(projectile.gameObject);
            if (targetHost)
            {
                targetHost.SetActive(false);
                NetworkServer.UnSpawn(targetHost);
                Destroy(targetHost);
            }
            if (targetVisual)
                Destroy(targetVisual);
            if (projectileHost)
                Destroy(projectileHost);
            if (coordinator.r.combat != null)
                coordinator.r.combat.cleaned = true;
        }
        public void Dispose()
        {
            foreach (var cfg in combatConfigs)
                if (cfg)
                    Destroy(cfg);
            combatConfigs.Clear();
            if (projectileTemplateHost)
                Destroy(projectileTemplateHost);
            if (combatMaterial)
                Destroy(combatMaterial);
            if (combatTexture)
                Destroy(combatTexture);
        }
    }
}
