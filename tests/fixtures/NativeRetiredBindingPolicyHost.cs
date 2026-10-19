using System;

sealed class ManagedWrapper
{
    public object Value;
    public bool UnityAlive;
}

static class NativeRetiredBindingPolicyHost
{
    static void Require(bool condition, string message)
    {
        if (!condition) throw new Exception(message);
    }

    static void Refuses(Action action, string message)
    {
        try { action(); }
        catch (InvalidOperationException) { return; }
        throw new Exception("Expected lease refusal: " + message);
    }

    static NativeSourceBindingRestoreAction Decide(bool scene, bool componentAlive, bool componentReference,
                                                    bool ownerAlive, bool ownerReference, bool sameOwner,
                                                    bool ownerScene, bool directField)
    {
        return NativeSourceBindingRestorePolicy.Decide(scene, componentAlive, componentReference,
            ownerAlive, ownerReference, sameOwner, ownerScene, directField);
    }

    public static int Main()
    {
        Require(Decide(true, true, true, true, true, true, true, true) == NativeSourceBindingRestoreAction.RestoreLiveOwner,
                "live exact owner path changed");
        Require(Decide(true, true, true, false, true, false, false, true) == NativeSourceBindingRestoreAction.Refuse,
                "live component with missing owner did not refuse");
        Require(Decide(true, true, true, true, true, false, true, true) == NativeSourceBindingRestoreAction.Refuse,
                "live component detached from captured owner did not refuse");
        Require(Decide(true, true, true, true, true, true, false, true) == NativeSourceBindingRestoreAction.Refuse,
                "live component with owner in another scene did not refuse");
        Require(Decide(false, false, true, false, true, false, false, true) == NativeSourceBindingRestoreAction.Refuse,
                "retired path bypassed requested/bound/valid/loaded/active scene conjunction");
        Require(Decide(true, false, false, false, true, false, false, true) == NativeSourceBindingRestoreAction.Refuse,
                "actual null component reference did not refuse");
        Require(Decide(true, false, true, false, false, false, false, true) == NativeSourceBindingRestoreAction.Refuse,
                "actual null captured owner reference did not refuse");
        Require(Decide(true, false, true, true, true, false, true, true) == NativeSourceBindingRestoreAction.Refuse,
                "destroyed component with still-live GameObject/child consumer did not refuse");
        Require(Decide(true, false, true, false, true, false, false, false) == NativeSourceBindingRestoreAction.Refuse,
                "unknown direct-field contract did not refuse");
        Require(Decide(true, false, true, false, true, false, false, true) ==
                    NativeSourceBindingRestoreAction.RestoreCapturedManagedField,
                "fake-null component and captured GameObject did not select the captured lease");

        var original = new object();
        var owned = new object();
        var foreign = new object();
        var wrapper = new ManagedWrapper { Value = original, UnityAlive = true };
        var lease = new NativeBorrowedFieldLease<object>(() => wrapper.Value, value => wrapper.Value = value,
                                                         original, owned);
        lease.Bind();
        Require(ReferenceEquals(wrapper.Value, owned), "lease did not bind the owned value");
        wrapper.UnityAlive = false; // Synthetic Unity fake-null; closure retains this exact wrapper.
        Require(Decide(true, false, true, false, true, false, false, true) ==
                    NativeSourceBindingRestoreAction.RestoreCapturedManagedField,
                "dead wrapper did not route through the exact captured lease");
        lease.Restore();
        lease.Restore();
        Require(ReferenceEquals(wrapper.Value, original), "dead-wrapper lease did not restore idempotently");

        var foreignLease = new NativeBorrowedFieldLease<object>(() => wrapper.Value, value => wrapper.Value = value,
                                                                original, owned);
        foreignLease.Bind();
        wrapper.Value = foreign;
        Refuses(foreignLease.Restore, "foreign replacement");
        Require(ReferenceEquals(wrapper.Value, foreign), "foreign replacement was overwritten");

        Console.WriteLine("PASS retired-wrapper policy and captured-lease contracts");
        return 0;
    }
}
