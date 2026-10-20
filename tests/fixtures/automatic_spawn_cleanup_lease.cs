using System;
using System.Collections.Generic;
using System.Linq;
using UnityEngine;

namespace UnityEngine
{
public class Object
{
    public bool destroyed;
    public static implicit operator bool(Object value) => !ReferenceEquals(value, null) && !value.destroyed;
}

public sealed class GameObject : Object
{
    public readonly string name;
    public GameObject(string name)
    {
        this.name = name;
    }
}
}

public sealed class EntityStateMachine : UnityEngine.Object
{
    public string name;
    public UnityEngine.GameObject gameObject;
}

public sealed class GenericSkill : UnityEngine.Object
{
    public EntityStateMachine stateMachine;
}

public sealed class SkillLocator : UnityEngine.Object
{
    public GenericSkill primary, secondary, utility, special;
}

// The test inserts exact extracted members from the current public owner here.
public static class ProductionCleanup
{
}

public sealed class ThrowingPublisher
{
    public Action handlers;
    public bool throwAfterAdd;

    public event Action Changed
    {
        add
        {
            handlers += value;
            if (throwAfterAdd)
                throw new InvalidOperationException("injected add failure after delegate mutation");
        }
        remove
        {
            handlers -= value;
        }
    }
}
