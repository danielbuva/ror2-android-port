using System;
using System.Collections.Generic;

public enum EquipmentIndex { None = -1, Base = 0, ExpansionA = 1, ExpansionB = 2 }
public sealed class ExpansionDef
{
    public bool enabled;
    public static implicit operator bool(ExpansionDef value) => value != null;
}
public sealed class EquipmentDef
{
    public EquipmentIndex equipmentIndex;
    public ExpansionDef requiredExpansion;
    public static implicit operator bool(EquipmentDef value) => value != null;
}
public sealed class Run
{
    public EquipmentMask expansionLockedEquipment;
    public bool destroyed;
    public int expansionChecks;
    public static implicit operator bool(Run value) => value != null && !value.destroyed;
    public bool IsExpansionEnabled(ExpansionDef expansion)
    {
        expansionChecks++;
        return expansion.enabled;
    }
}
public sealed class EquipmentMask
{
    readonly HashSet<EquipmentIndex> locked = new HashSet<EquipmentIndex>();
    public static int rents, returns;
    public static EquipmentIndex? throwOnAdd;
    public static EquipmentMask Rent() { rents++; return new EquipmentMask(); }
    public static void Return(EquipmentMask mask)
    {
        if (mask == null) throw new Exception("Return(null)");
        returns++;
    }
    public void Clear() => locked.Clear();
    public void Add(EquipmentIndex index)
    {
        if (throwOnAdd == index) throw new InvalidOperationException("injected population failure");
        locked.Add(index);
    }
    public bool Contains(EquipmentIndex index) => locked.Contains(index);
}
public static class EquipmentCatalog
{
    public static EquipmentIndex[] allEquipment;
    static readonly Dictionary<EquipmentIndex, EquipmentDef> defs = new Dictionary<EquipmentIndex, EquipmentDef>();
    public static int equipmentCount => allEquipment == null ? 0 : allEquipment.Length;
    public static EquipmentDef GetEquipmentDef(EquipmentIndex index) => defs.TryGetValue(index, out var def) ? def : null;
    public static void Set(EquipmentIndex index, ExpansionDef expansion) => defs[index] = new EquipmentDef { equipmentIndex = index, requiredExpansion = expansion };
    public static void Remove(EquipmentIndex index) => defs.Remove(index);
}
