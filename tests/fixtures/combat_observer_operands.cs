using System;

namespace UnityEngine
{
public class Object
{
    public bool destroyed;
    public static implicit operator bool(Object value) => !ReferenceEquals(value, null) && !value.destroyed;
}
}

public sealed class EntityState
{
}
public class CharacterBody : UnityEngine.Object
{
    SkillLocator value;
    public int skillLocatorReads;
    public virtual SkillLocator skillLocator
    {
        get {
            skillLocatorReads++;
            return value;
        }
        set {
            this.value = value;
        }
    }
}
public class SkillLocator : UnityEngine.Object
{
    GenericSkill value;
    public int primaryReads;
    public virtual GenericSkill primary
    {
        get {
            primaryReads++;
            return value;
        }
        set {
            this.value = value;
        }
    }
}
public class GenericSkill : UnityEngine.Object
{
    EntityStateMachine value;
    public int stateMachineReads;
    public virtual EntityStateMachine stateMachine
    {
        get {
            stateMachineReads++;
            return value;
        }
        set {
            this.value = value;
        }
    }
}
public class EntityStateMachine : UnityEngine.Object
{
    EntityState value;
    public int stateReads;
    public virtual EntityState state
    {
        get {
            stateReads++;
            return value;
        }
        set {
            this.value = value;
        }
    }
}
public sealed class CombatReport
{
    public string primaryStateUnavailableReason, bodyStateUnavailableReason, weaponState, bodyState;
    public int primaryStateUnavailableObservations, bodyStateUnavailableObservations;
    public bool primaryStateAvailable, bodyStateAvailable;
}
public static class ProductionCombatObserver
{
    // Production helper members are inserted here by the host test.
    public static void Capture(CharacterBody player, EntityStateMachine machine, CombatReport report, out EntityState weapon,
                               out EntityState bodyState)
    {
        CaptureCombatStateOperands(player, machine, report, out weapon, out bodyState);
    }
    public static bool ReadPrimary(CharacterBody player, out EntityState state, out string unavailable)
    {
        return TryReadPrimaryWeaponState(player, out state, out unavailable);
    }
}
