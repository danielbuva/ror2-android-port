// Subsystem: world/director (game path). Owner map: docs/ARCHITECTURE.md#ownership.
// Session phases: setup PrepareSpineConfigs, ApplySpineExclusions, ObserveSpinePrimary, PrimaryFireBoundary (PrimaryFireSession); teardown CleanupSpineConfig (Dispose); IsPlayableSpine stays on the coordinator.
using System;
using System.Linq;
using System.Reflection;
using EntityStates;
using EntityStates.Commando.CommandoWeapon;
using RoR2;
using RoR2.Skills;
using UnityEngine;

// Diagnostic scheduling isolates the original skill factory/activation from its first native consumer.
public sealed partial class PortSession
{
    [Serializable]
    public class PrimaryFireOperandSnapshot
    {
        public int sequence, bodyInstanceId, skillLocatorInstanceId, primaryInstanceId, stateMachineInstanceId;
        public int stock;
        public float seconds;
        public string phase, bodyStatus, skillLocatorStatus, primaryStatus, stateMachineStatus, stateMachineCustomName, stateStatus,
            stockStatus;
        public string firstUnavailable, exceptionStage, exceptionType, exceptionMessage;
        public PrimaryFireOperandSnapshot Clone()
        {
            return new PrimaryFireOperandSnapshot { sequence = sequence,
                                                    bodyInstanceId = bodyInstanceId,
                                                    skillLocatorInstanceId = skillLocatorInstanceId,
                                                    primaryInstanceId = primaryInstanceId,
                                                    stateMachineInstanceId = stateMachineInstanceId,
                                                    stock = stock,
                                                    seconds = seconds,
                                                    phase = phase,
                                                    bodyStatus = bodyStatus,
                                                    skillLocatorStatus = skillLocatorStatus,
                                                    primaryStatus = primaryStatus,
                                                    stateMachineStatus = stateMachineStatus,
                                                    stateMachineCustomName = stateMachineCustomName,
                                                    stateStatus = stateStatus,
                                                    stockStatus = stockStatus,
                                                    firstUnavailable = firstUnavailable,
                                                    exceptionStage = exceptionStage,
                                                    exceptionType = exceptionType,
                                                    exceptionMessage = exceptionMessage };
        }
    }
    [Serializable]
    public class PrimaryFireReport
    {
        public int observerTicks;
        public PrimaryFireOperandSnapshot lastOperands, firstFailureOperands;
        public string observerExceptionStage, observerExceptionType, observerExceptionMessage;
        public string skill, state, firstFailure, audioException, weaponInitialState, definitionType;
        public bool weaponEnabled, slotWeaponMatched, rootActive;
        public int stockBefore, stockAfter, stepBefore, stepAfter, authorityEvents, serverEvents;
        public float damageCoefficient, force, baseDuration;
        public bool scheduled, entered, firingAvailable, audioAvailable, silentFixture;
        public int shots, reloads;
        public float spreadAfter;
    }
    bool IsPlayableSpine()
    {
        return r.id.StartsWith("body-state-spawn-state-auto-nova-spine");
    }
    PrimaryFireSession primaryFireSession;
    PrimaryFireSession GetPrimaryFireSession()
    {
        if (primaryFireSession == null)
            primaryFireSession = new PrimaryFireSession(this);
        return primaryFireSession;
    }
    EntityStateConfiguration[] PrepareSpineConfigs(SessionConfig cfg, EntityStateConfiguration spawn)
    {
        return GetPrimaryFireSession().PrepareSpineConfigs(cfg, spawn);
    }
    void ApplySpineExclusions()
    {
        GetPrimaryFireSession().ApplySpineExclusions();
    }
    void ObserveSpinePrimary(CharacterBody body)
    {
        GetPrimaryFireSession().ObserveSpinePrimary(body);
    }
    void CleanupSpineConfig()
    {
        GetPrimaryFireSession().Dispose();
    }
    bool IsPrimaryFire()
    {
        return GetPrimaryFireSession().IsPrimaryFire();
    }
    void PrimaryFireBoundary(CharacterBody body, SessionConfig cfg)
    {
        GetPrimaryFireSession().PrimaryFireBoundary(body, cfg);
    }

    // Retain the owner for partial setup, repeated cleanup and later observations.
    // Dispose keeps combat cleanup before primary static restoration and clone release.
    sealed class PrimaryFireSession : IDisposable
    {
        readonly PortSession coordinator;
        FieldInfo[] spineFields;
        object[] spinePrior;
        EntityStateConfiguration spineReload;
        EntityState lastSpineWeaponState;
        public PrimaryFireSession(PortSession coordinator)
        {
            this.coordinator = coordinator;
        }
        public EntityStateConfiguration[] PrepareSpineConfigs(SessionConfig cfg, EntityStateConfiguration spawn)
        {
            spineFields = (cfg.combatSpine ? new[] { typeof(FirePistol2), typeof(FireBarrage), typeof(EntityStates.Commando.DodgeState) }
                                           : new[] { typeof(FirePistol2) })
                              .SelectMany(t => t.GetFields(BindingFlags.Public | BindingFlags.Static | BindingFlags.DeclaredOnly))
                              .ToArray();
            spinePrior = spineFields.Select(x => x.GetValue(null)).ToArray();
            var fire = coordinator.artifactBundle.LoadAsset<EntityStateConfiguration>(cfg.primaryFireConfigAsset);
            var reload = coordinator.artifactBundle.LoadAsset<EntityStateConfiguration>(cfg.primaryReloadConfigAsset);
            coordinator.Check(fire && reload, "Spine primary configurations missing");
            spineReload = Instantiate(reload);
            spineReload.serializedFieldsCollection.serializedFields = reload.serializedFieldsCollection.serializedFields.ToArray();
            int index = Array.FindIndex(spineReload.serializedFieldsCollection.serializedFields, x => x.fieldName == "enterSoundString");
            coordinator.Check(index >= 0, "Spine reload sound field missing");
            spineReload.serializedFieldsCollection.serializedFields[index].fieldValue.stringValue = "";
            coordinator.r.primary = new PrimaryFireReport { silentFixture = true, lastOperands = new PrimaryFireOperandSnapshot() };
            var configs = new[] { spawn, fire, spineReload };
            return cfg.combatSpine ? configs.Concat(coordinator.PrepareCombatConfigs(cfg)).ToArray() : configs;
        }
        public void ApplySpineExclusions()
        {
            FirePistol2.firePistolSoundString = "";
            FirePistol2.muzzleEffectPrefab = null;
            FirePistol2.hitEffectPrefab = null;
            FirePistol2.tracerEffectPrefab = null;
            coordinator.r.primary.damageCoefficient = FirePistol2.damageCoefficient;
            coordinator.r.primary.force = FirePistol2.force;
            coordinator.r.primary.baseDuration = FirePistol2.baseDuration;
            if (coordinator.r.combat != null)
            {
                FireBarrage.fireBarrageSoundString = "";
                FireBarrage.effectPrefab = null;
                FireBarrage.hitEffectPrefab = null;
                FireBarrage.tracerEffectPrefab = null;
                EntityStates.Commando.DodgeState.dodgeSoundString = "";
                EntityStates.Commando.DodgeState.jetEffect = null;
            }
        }
        static string UnityOperandStatus(UnityEngine.Object value)
        {
            if (ReferenceEquals(value, null))
                return "clr-null";
            return value ? "live" : "unity-fake-null";
        }
        static int FailureInstanceId(UnityEngine.Object value)
        {
            if (ReferenceEquals(value, null) || !value)
                return 0;
            try
            {
                return value.GetInstanceID();
            }
            catch (Exception)
            {
                return 0;
            }
        }
        static void ResetPrimaryOperandSnapshot(PrimaryFireOperandSnapshot snapshot, int sequence, float seconds, string phase)
        {
            snapshot.sequence = sequence;
            snapshot.seconds = seconds;
            snapshot.phase = phase;
            snapshot.bodyInstanceId = snapshot.skillLocatorInstanceId = snapshot.primaryInstanceId = snapshot.stateMachineInstanceId = 0;
            snapshot.stock = 0;
            snapshot.bodyStatus = null;
            snapshot.skillLocatorStatus = snapshot.primaryStatus = snapshot.stateMachineStatus = snapshot.stateMachineCustomName =
                snapshot.stateStatus = snapshot.stockStatus = "not-read-prerequisite-unavailable";
            snapshot.firstUnavailable = snapshot.exceptionStage = snapshot.exceptionType = snapshot.exceptionMessage = null;
        }
        void FreezePrimaryOperandFailure(PrimaryFireReport report, PrimaryFireOperandSnapshot snapshot, CharacterBody body,
                                         SkillLocator locator, GenericSkill primary, EntityStateMachine machine)
        {
            if (report.firstFailureOperands != null)
                return;
            snapshot.bodyInstanceId = FailureInstanceId(body);
            snapshot.skillLocatorInstanceId = FailureInstanceId(locator);
            snapshot.primaryInstanceId = FailureInstanceId(primary);
            snapshot.stateMachineInstanceId = FailureInstanceId(machine);
            report.firstFailureOperands = snapshot.Clone();
        }
        void RecordPrimaryOperandException(PrimaryFireReport report, PrimaryFireOperandSnapshot snapshot, string stage, Exception error,
                                           CharacterBody body, SkillLocator locator, GenericSkill primary, EntityStateMachine machine)
        {
            snapshot.exceptionStage = stage;
            snapshot.exceptionType = error.GetType().FullName;
            snapshot.exceptionMessage = error.Message.Length > 256 ? error.Message.Substring(0, 256) : error.Message;
            if (string.IsNullOrEmpty(report.observerExceptionStage))
            {
                report.observerExceptionStage = snapshot.exceptionStage;
                report.observerExceptionType = snapshot.exceptionType;
                report.observerExceptionMessage = snapshot.exceptionMessage;
            }
            FreezePrimaryOperandFailure(report, snapshot, body, locator, primary, machine);
        }
        void RefuseUnavailablePrimaryOperands(PrimaryFireReport report, PrimaryFireOperandSnapshot snapshot, CharacterBody body,
                                              SkillLocator locator, GenericSkill primary, EntityStateMachine machine)
        {
            FreezePrimaryOperandFailure(report, snapshot, body, locator, primary, machine);
            coordinator.Check(false, "Primary observer required operand unavailable: " + snapshot.firstUnavailable +
                                         " (body=" + snapshot.bodyStatus + ", locator=" + snapshot.skillLocatorStatus +
                                         ", primary=" + snapshot.primaryStatus + ", machine=" + snapshot.stateMachineStatus +
                                         ", state=" + snapshot.stateStatus + ")");
        }
        public void ObserveSpinePrimary(CharacterBody body)
        {
            var report = coordinator.r.primary;
            if (report == null)
                coordinator.Check(false, "Primary observer report is unavailable");
            if (report.lastOperands == null)
                report.lastOperands = new PrimaryFireOperandSnapshot();
            var snapshot = report.lastOperands;
            ResetPrimaryOperandSnapshot(snapshot, ++report.observerTicks, Time.realtimeSinceStartup, coordinator.r.phase);
            CharacterBody bodyRef = body;
            SkillLocator locator = null;
            GenericSkill primary = null;
            EntityStateMachine weapon = null;
            string operandStage = "body";
            try
            {
                snapshot.bodyStatus = UnityOperandStatus(bodyRef);
                if (snapshot.bodyStatus != "live")
                {
                    snapshot.firstUnavailable = "body:" + snapshot.bodyStatus;
                    RefuseUnavailablePrimaryOperands(report, snapshot, bodyRef, locator, primary, weapon);
                }
                operandStage = "body.skillLocator";
                locator = bodyRef.skillLocator;
                snapshot.skillLocatorStatus = UnityOperandStatus(locator);
                if (snapshot.skillLocatorStatus != "live")
                {
                    snapshot.firstUnavailable = "body.skillLocator:" + snapshot.skillLocatorStatus;
                    RefuseUnavailablePrimaryOperands(report, snapshot, bodyRef, locator, primary, weapon);
                }
                operandStage = "skillLocator.primary";
                primary = locator.primary;
                snapshot.primaryStatus = UnityOperandStatus(primary);
                if (snapshot.primaryStatus != "live")
                {
                    snapshot.firstUnavailable = "skillLocator.primary:" + snapshot.primaryStatus;
                    RefuseUnavailablePrimaryOperands(report, snapshot, bodyRef, locator, primary, weapon);
                }
                operandStage = "primary.stateMachine";
                weapon = primary.stateMachine;
                snapshot.stateMachineStatus = UnityOperandStatus(weapon);
                if (snapshot.stateMachineStatus != "live")
                {
                    snapshot.firstUnavailable = "primary.stateMachine:" + snapshot.stateMachineStatus;
                    RefuseUnavailablePrimaryOperands(report, snapshot, bodyRef, locator, primary, weapon);
                }
                operandStage = "stateMachine.state";
                EntityState state = weapon.state;
                snapshot.stateStatus = ReferenceEquals(state, null) ? "clr-null" : "live";
                if (snapshot.stateStatus != "live")
                {
                    snapshot.firstUnavailable = "stateMachine.state:clr-null";
                    RefuseUnavailablePrimaryOperands(report, snapshot, bodyRef, locator, primary, weapon);
                }
                if (state != lastSpineWeaponState)
                {
                    if (state is FirePistol2)
                    {
                        report.shots++;
                        report.entered = true;
                        report.firingAvailable = true;
                        operandStage = "body.spreadBloomAngle";
                        report.spreadAfter = bodyRef.spreadBloomAngle;
                    }
                    if (state is ReloadPistols)
                        report.reloads++;
                    lastSpineWeaponState = state;
                }
                operandStage = "primary.stock";
                snapshot.stock = primary.stock;
                snapshot.stockStatus = "read";
                report.stockAfter = snapshot.stock;
                report.state = state.GetType().FullName;
            }
            catch (Exception error)
            {
                if (report.firstFailureOperands == null)
                {
                    string stage = operandStage;
                    RecordPrimaryOperandException(report, snapshot, stage, error, bodyRef, locator, primary, weapon);
                }
                throw;
            }
        }
        public void Dispose()
        {
            coordinator.CleanupCombatConfigs();
            if (spineFields != null)
            {
                for (int i = 0; i < spineFields.Length; i++)
                    spineFields[i].SetValue(null, spinePrior[i]);
                spineFields = null;
            }
            if (spineReload)
                Destroy(spineReload);
        }
        public bool IsPrimaryFire()
        {
            return coordinator.r.id.StartsWith("body-state-spawn-state-primary-");
        }
        public void PrimaryFireBoundary(CharacterBody body, SessionConfig cfg)
        {
            coordinator.r.primary = new PrimaryFireReport();
            var report = coordinator.r.primary;
            var weapon = EntityStateMachine.FindByCustomName(body.gameObject, "Weapon");
            var skill = body.skillLocator.primary;
            var def = skill.skillDef as SteppedSkillDef;
            report.weaponEnabled = weapon && weapon.enabled;
            report.rootActive = body.gameObject.activeInHierarchy;
            report.weaponInitialState = weapon && weapon.state != null ? weapon.state.GetType().FullName : "null";
            report.definitionType = skill.skillDef ? skill.skillDef.GetType().FullName : "null";
            report.slotWeaponMatched = skill.stateMachine == weapon;
            coordinator.Save();
            coordinator.Check(weapon && !report.rootActive && weapon.state is Uninitialized && def && skill.stateMachine == weapon,
                              "Original primary/Weapon pre-Start contract");
            coordinator.Check(def == skill.skillFamily.defaultSkillDef && ((ScriptableObject)def).name == "CommandoBodyFirePistol" &&
                                  def.activationState.stateType == typeof(FirePistol2) && def.stepCount == 2 &&
                                  def.stepGraceDuration == .1f,
                              "Original primary definition/state/step identity");
            var fire = coordinator.artifactBundle.LoadAsset<EntityStateConfiguration>(cfg.primaryFireConfigAsset);
            var reload = coordinator.artifactBundle.LoadAsset<EntityStateConfiguration>(cfg.primaryReloadConfigAsset);
            coordinator.Check(fire && reload && (Type)fire.targetType == typeof(FirePistol2) &&
                                  (Type)reload.targetType == typeof(ReloadPistols),
                              "Original primary state configuration identities");
            coordinator.Check(!coordinator.ownsStateCatalog, "Existing state catalog; refuse primary replacement");
            var fields = typeof(FirePistol2).GetFields(BindingFlags.Public | BindingFlags.Static | BindingFlags.DeclaredOnly);
            var prior = fields.Select(x => x.GetValue(null)).ToArray();
            Action<GenericSkill> authority =
                                     s =>
            {
                if (s == skill)
                    report.authorityEvents++;
            },
                                 server = s =>
            {
                if (s == skill)
                    report.serverEvents++;
            };
            body.onSkillActivatedAuthority += authority;
            body.onSkillActivatedServer += server;
            try
            {
                coordinator.ownsStateCatalog = true;
                BuildStateCatalog(new[] { typeof(Uninitialized), typeof(Idle), typeof(FirePistol2), typeof(ReloadPistols) },
                                  new[] { fire, reload });
                report.skill = ((ScriptableObject)def).name;
                report.damageCoefficient = FirePistol2.damageCoefficient;
                report.force = FirePistol2.force;
                report.baseDuration = FirePistol2.baseDuration;
                coordinator.Check(report.damageCoefficient == 1 && report.force == 200 && report.baseDuration == .15f &&
                                      FirePistol2.firePistolSoundString == "Play_commando_R" && FirePistol2.muzzleEffectPrefab &&
                                      FirePistol2.hitEffectPrefab && FirePistol2.tracerEffectPrefab,
                                  "Original pistol configuration fields/references");
                var state = typeof(SteppedSkillDef)
                                .GetMethod("InstantiateNextState", BindingFlags.Instance | BindingFlags.NonPublic)
                                .Invoke(def, new object[] { skill }) as FirePistol2;
                var pistol = typeof(FirePistol2).GetField("pistol", BindingFlags.Instance | BindingFlags.NonPublic);
                coordinator.Check(state != null && state.activatorSkillSlot == skill && (int)pistol.GetValue(state) == 0,
                                  "Original factory/ISkillState/step setter result");
                var reloadState =
                    EntityStateCatalog.InstantiateState(EntityStateCatalog.GetStateIndex(typeof(ReloadPistols))) as ReloadPistols;
                coordinator.Check(reloadState != null && reloadState.enterSoundString == "Play_loader_m2_launch",
                                  "Original reload instance initializer");
                coordinator.r.phase = "original-primary-weapon-start";
                coordinator.Save();
                Call(weapon, "Start");
                coordinator.Check(weapon.state is Idle && !weapon.HasPendingState() && skill.stock == 1 && skill.maxStock == 1 &&
                                      skill.CanExecute(),
                                  "Original Weapon Idle/primary readiness");
                coordinator.Check(DLC2Content.Items.IncreasePrimaryDamage &&
                                      body.inventory.GetItemCountEffective(DLC2Content.Items.IncreasePrimaryDamage) == 0,
                                  "Original empty primary activation item contract");
                report.stockBefore = skill.stock;
                report.stepBefore = (int)pistol.GetValue(state);
                coordinator.r.phase = "original-primary-execute-if-ready";
                coordinator.Save();
                coordinator.Check(skill.ExecuteIfReady(), "Original primary execution rejected");
                report.stockAfter = skill.stock;
                report.scheduled = weapon.HasPendingState();
                var next = typeof(SteppedSkillDef)
                               .GetMethod("InstantiateNextState", BindingFlags.Instance | BindingFlags.NonPublic)
                               .Invoke(def, new object[] { skill }) as FirePistol2;
                report.stepAfter = (int)pistol.GetValue(next);
                coordinator.Check(report.scheduled && weapon.state is Idle && report.stockAfter == 0 && report.stepAfter == 1 &&
                                      report.authorityEvents == 1 && report.serverEvents == 1,
                                  "Original activation/stock/step/authority events");
                coordinator.Check(!skill.CanExecute() && !skill.ExecuteIfReady() && report.authorityEvents == 1 && report.serverEvents == 1,
                                  "Original pending-state/empty-stock rejection");
                if (coordinator.r.id.EndsWith("-native"))
                {
                    coordinator.r.phase = "original-primary-on-enter";
                    coordinator.Save();
                    try
                    {
                        weapon.ManagedFixedUpdate(.02f);
                        report.entered = true;
                        report.firingAvailable = true;
                    }
                    catch (DllNotFoundException e)
                    {
                        report.audioException = e.ToString();
                        report.firstFailure = "Wwise native event posting";
                        report.entered = weapon.state is FirePistol2;
                        coordinator.Check(report.audioException.Contains("AkSoundEngine") && report.audioException.Contains("FirePistol2"),
                                          "Native failure did not belong to original pistol audio path");
                    }
                    coordinator.Check(report.entered && !report.firingAvailable && !report.audioAvailable &&
                                          !string.IsNullOrEmpty(report.audioException),
                                      "Expected bounded unavailable native-audio observation changed; review result");
                }
                report.state = weapon.state.GetType().FullName;
                coordinator.Save();
            }
            finally
            {
                body.onSkillActivatedAuthority -= authority;
                body.onSkillActivatedServer -= server;
                Call(weapon, "OnDestroy");
                coordinator.Check(weapon.state == null, "Original primary Weapon cleanup");
                for (int i = 0; i < fields.Length; i++)
                    fields[i].SetValue(null, prior[i]);
            }
        }
    }
}
