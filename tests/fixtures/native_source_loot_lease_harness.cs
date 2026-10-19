using System;
using System.Collections.Generic;

sealed class Slot { public object Value; }
static class LeaseHostTests
{
    static void Check(bool condition, string message)
    {
        if (!condition) throw new Exception(message);
    }
    static void Throws(Action action, string message)
    {
        try { action(); }
        catch (InvalidOperationException) { return; }
        throw new Exception("Expected refusal: " + message);
    }
    public static int Main()
    {
        var original = new object();
        var owned = new object();
        var slot = new Slot { Value = original };
        var resources = new List<object> { owned };
        var lease = new NativeBorrowedFieldLease<object>(() => slot.Value, value => slot.Value = value, original, owned);
        lease.Bind();
        Check(ReferenceEquals(slot.Value, owned), "bind uses owned clone");
        lease.Restore();
        lease.Restore();
        Check(ReferenceEquals(slot.Value, original), "restore is exact and idempotent");
        Check(resources.Contains(owned), "resource owner retains clone after field restoration");

        var foreign = new object();
        slot.Value = original;
        var blocked = new NativeBorrowedFieldLease<object>(() => slot.Value, value => slot.Value = value, original, owned);
        blocked.Bind();
        slot.Value = foreign;
        Throws(blocked.Restore, "foreign replacement");
        Check(ReferenceEquals(slot.Value, foreign), "foreign replacement remains untouched");
        Check(resources.Contains(owned), "foreign replacement retains cleanup resource");

        var a = new Slot { Value = new object() };
        var b = new Slot { Value = new object() };
        var originals = new[] { a.Value, b.Value };
        var clones = new[] { new object(), new object() };
        var partial = new List<NativeBorrowedFieldLease<object>>();
        var partialResources = new List<object>();
        for (int i = 0; i < 2; i++)
        {
            partialResources.Add(clones[i]);
            var current = i == 0 ? a : b;
            var item = new NativeBorrowedFieldLease<object>(() => current.Value, value => current.Value = value,
                                                            originals[i], clones[i]);
            partial.Add(item); // Mirrors the production handle-before-bind transaction.
            item.Bind();
        }
        for (int i = partial.Count - 1; i >= 0; i--) partial[i].Restore();
        Check(ReferenceEquals(a.Value, originals[0]) && ReferenceEquals(b.Value, originals[1]),
              "partial setup restores each borrowed field in reverse order");
        Check(partialResources.Count == 2, "partial setup leaves resources with their owner");
        Console.WriteLine("production lease bind, restore, idempotence, refusal, and partial rollback passed");
        return 0;
    }
}
