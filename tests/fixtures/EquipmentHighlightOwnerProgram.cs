using System;
using System.Collections;
using System.Reflection;
using RoR2;
using UnityEngine;
using UnityEngine.AddressableAssets;
using UnityEngine.AddressableAssets.ResourceLocators;
using UnityEngine.ResourceManagement.AsyncOperations;
using UnityEngine.ResourceManagement.ResourceLocations;

internal static class EquipmentHighlightOwnerProgram
{
    static void Require(bool condition, string message)
    {
        if (!condition) throw new Exception(message);
    }
    static FieldInfo Field(string name) => typeof(EquipmentCatalog).GetField(name, BindingFlags.Static | BindingFlags.NonPublic);
    static void ClearFields()
    {
        Field("equipmentHighlightPrefab").SetValue(null, null);
        Field("lunarEquipmentHighlightPrefab").SetValue(null, null);
        Field("bossEquipmentHighlightPrefab").SetValue(null, null);
    }
    static IEnumerator Prepare(PortSession owner) => (IEnumerator)typeof(PortSession)
        .GetMethod("PrepareOriginalEquipmentHighlightAssets", BindingFlags.Instance | BindingFlags.NonPublic).Invoke(owner, null);
    static void Cleanup(PortSession owner, Exception originalFailure = null) => typeof(PortSession)
        .GetMethod("CleanupOriginalEquipmentHighlightAssets", BindingFlags.Instance | BindingFlags.NonPublic)
        .Invoke(owner, new object[] { originalFailure });
    static void RequireCleanupRefusal(PortSession owner)
    {
        bool refused = false;
        try { Cleanup(owner); }
        catch (TargetInvocationException exception) when (exception.InnerException is AggregateException) { refused = true; }
        Require(refused && !owner.r.originalEquipmentHighlightAssets.cleaned,
                "unowned source static must block catalog retirement");
    }
    static void CompleteAll(AsyncOperationStatus status = AsyncOperationStatus.Succeeded)
    {
        foreach (var operation in Addressables.operations)
        {
            operation.done = true;
            operation.status = status;
            operation.result = status == AsyncOperationStatus.Succeeded ? new GameObject() : null;
        }
    }
    static void Drain(IEnumerator iterator)
    {
        int count = 0;
        while (iterator.MoveNext())
        {
            if (++count > 100) throw new Exception("unexpectedly unbounded coroutine");
        }
    }
    static PortSession NewOwner()
    {
        Addressables.Reset();
        Addressables.create = _ => new TestOperation<GameObject>();
        WholeCatalogComposed.IsConfigured = true;
        WholeCatalogLoader.locator = NewLocator();
        ClearFields();
        return new PortSession();
    }
    static ResourceLocationMap NewLocator()
    {
        var locator = new ResourceLocationMap();
        AddLocation(locator, "164a5db278443b1469a210be383c4b0e", "RoR2/Base/UI/HighlightEquipment.prefab",
            "Assets/WholeGame/RoR2/Base/UI/AR/HighlightEquipment.prefab");
        AddLocation(locator, "0cb44955b08ec6a4a9c3e04c5f73b815", "RoR2/Base/UI/HighlightLunarItem.prefab",
            "Assets/WholeGame/RoR2/Base/UI/AR/HighlightLunarItem.prefab");
        AddLocation(locator, "5c3d7eca2b1255148958484c738869d8", "RoR2/Base/UI/HighlightBossItem.prefab",
            "Assets/WholeGame/RoR2/Base/UI/AR/HighlightBossItem.prefab");
        return locator;
    }
    static TestResourceLocation AddLocation(ResourceLocationMap locator, string key, string primaryKey, string internalId)
    {
        var location = new TestResourceLocation
        {
            ResourceType = typeof(GameObject),
            PrimaryKey = primaryKey,
            InternalId = internalId
        };
        locator.Add(key, location);
        return location;
    }
    static void ReadyAllSourceSlots()
    {
        foreach (var name in new[] { "equipmentHighlightPrefab", "lunarEquipmentHighlightPrefab", "bossEquipmentHighlightPrefab" })
            Field(name).SetValue(null, new GameObject());
    }
    public static int Main()
    {
        // Empty source slots produce exactly three typed, retained requests;
        // readiness is not published until all three complete successfully.
        var owner = NewOwner();
        var pending = Prepare(owner);
        Require(pending.MoveNext(), "owner must wait while source operations are pending");
        Require(Addressables.operations.Count == 3, "one request per source slot");
        Require(Addressables.requestedLocations.Count == 3 &&
                Addressables.requestedLocations.TrueForAll(location => location.ResourceType == typeof(GameObject)) &&
                Addressables.requestedLocations[0].PrimaryKey == "RoR2/Base/UI/HighlightEquipment.prefab" &&
                Addressables.requestedLocations[0].InternalId == "Assets/WholeGame/RoR2/Base/UI/AR/HighlightEquipment.prefab",
                "requests use the exact validated typed locator result");
        CompleteAll();
        Drain(pending);
        Require(Field("equipmentHighlightPrefab").GetValue(null) != null && owner.saves >= 3 &&
                owner.r.originalEquipmentHighlightAssets.state == "ready",
                "successful typed results are assigned before camera admission");
        owner.worldPlayer = new GameObject();
        bool cleanupRefused = false;
        try { Cleanup(owner); } catch (TargetInvocationException exception) when (exception.InnerException is InvalidOperationException) { cleanupRefused = true; }
        Require(cleanupRefused && Addressables.operations.TrueForAll(x => x.releases == 0),
                "cleanup refuses while the original world player may still consume shared slots");
        owner.worldPlayer = null;
        Cleanup(owner);
        Cleanup(owner);
        Require(Addressables.operations.TrueForAll(x => x.releases == 1), "cleanup releases each retained handle once");
        Require(Field("equipmentHighlightPrefab").GetValue(null) == null, "cleanup restores only this owner's prior empty slot");
        Require(!owner.r.originalEquipmentHighlightAssets.ready, "cleanup clears readiness after restoring owned slots");

        // This route does not adopt a preexisting initializer's static slots.
        owner = NewOwner();
        ReadyAllSourceSlots();
        var readyBefore = Field("equipmentHighlightPrefab").GetValue(null);
        bool prepopulatedRefused = false;
        try { Drain(Prepare(owner)); } catch (InvalidOperationException) { prepopulatedRefused = true; }
        Require(prepopulatedRefused && Addressables.operations.Count == 0, "unowned static refuses before requests");
        bool retirementRefused = false;
        try { Cleanup(owner); } catch (TargetInvocationException exception) when (exception.InnerException is AggregateException) { retirementRefused = true; }
        Require(ReferenceEquals(readyBefore, Field("equipmentHighlightPrefab").GetValue(null)) &&
                retirementRefused && !owner.r.originalEquipmentHighlightAssets.cleaned,
                "foreign statics survive and block bundle retirement");

        // A preexisting partial failure does not overwrite any slot or publish a partial set.
        owner = NewOwner();
        pending = Prepare(owner);
        Require(pending.MoveNext(), "partial failure fixture pending");
        Addressables.operations[0].done = true;
        Addressables.operations[0].status = AsyncOperationStatus.Succeeded;
        Addressables.operations[0].result = new GameObject();
        Addressables.operations[1].done = true;
        Addressables.operations[1].status = AsyncOperationStatus.Failed;
        Addressables.operations[1].result = null;
        Addressables.operations[2].done = true;
        Addressables.operations[2].status = AsyncOperationStatus.Succeeded;
        Addressables.operations[2].result = new GameObject();
        bool failed = false;
        try { pending.MoveNext(); } catch (InvalidOperationException) { failed = true; }
        Require(failed && Field("equipmentHighlightPrefab").GetValue(null) == null,
                "failed sibling refuses the set before any static assignment");
        Cleanup(owner);
        Require(Addressables.operations.TrueForAll(x => x.releases == 1), "failed preparation still releases all owned handles");

        // Succeeded with a null result is distinct from a valid GameObject.
        owner = NewOwner();
        pending = Prepare(owner);
        Require(pending.MoveNext(), "null-result fixture pending");
        CompleteAll();
        Addressables.operations[1].result = null;
        failed = false;
        try { Drain(pending); } catch (InvalidOperationException) { failed = true; }
        Require(failed && Field("equipmentHighlightPrefab").GetValue(null) == null,
                "null successful result refuses before any slot assignment");
        Cleanup(owner);

        // Requests are forbidden unless the accepted composed locator is owned.
        owner = NewOwner();
        WholeCatalogComposed.IsConfigured = false;
        failed = false;
        try { Drain(Prepare(owner)); } catch (InvalidOperationException) { failed = true; }
        WholeCatalogComposed.IsConfigured = true;
        Require(failed && Addressables.operations.Count == 0, "unowned locator refuses before Addressables request");
        Cleanup(owner);

        // Resolution is fail-closed: missing, ambiguous, wrong-type, wrong-key,
        // and wrong-path records all refuse before the first request.
        owner = NewOwner();
        WholeCatalogLoader.locator.Remove("164a5db278443b1469a210be383c4b0e");
        failed = false;
        try { Drain(Prepare(owner)); } catch (InvalidOperationException) { failed = true; }
        Require(failed && Addressables.operations.Count == 0, "missing exact address refuses before request");
        Cleanup(owner);

        owner = NewOwner();
        AddLocation(WholeCatalogLoader.locator, "164a5db278443b1469a210be383c4b0e",
            "RoR2/Base/UI/HighlightEquipment.prefab", "Assets/WholeGame/RoR2/Base/UI/AR/HighlightEquipment.prefab");
        failed = false;
        try { Drain(Prepare(owner)); } catch (InvalidOperationException) { failed = true; }
        Require(failed && Addressables.operations.Count == 0, "ambiguous exact address refuses before request");
        Cleanup(owner);

        owner = NewOwner();
        WholeCatalogLoader.locator = new ResourceLocationMap();
        WholeCatalogLoader.locator.Add("164a5db278443b1469a210be383c4b0e", new TestResourceLocation
        {
            ResourceType = typeof(string), PrimaryKey = "RoR2/Base/UI/HighlightEquipment.prefab",
            InternalId = "Assets/WholeGame/RoR2/Base/UI/AR/HighlightEquipment.prefab"
        });
        failed = false;
        try { Drain(Prepare(owner)); } catch (InvalidOperationException) { failed = true; }
        Require(failed && Addressables.operations.Count == 0, "wrong typed location refuses before request");
        Cleanup(owner);

        owner = NewOwner();
        var reflectedRows = (Array)typeof(PortSession).GetNestedType("OriginalEquipmentHighlightAssetsSession", BindingFlags.NonPublic)
            .GetField("Rows", BindingFlags.Static | BindingFlags.NonPublic).GetValue(null);
        var firstSpec = reflectedRows.GetValue(0);
        string firstKey = (string)firstSpec.GetType().GetField("addressKey").GetValue(firstSpec);
        string firstPrimary = (string)firstSpec.GetType().GetField("primaryKey").GetValue(firstSpec);
        string firstPath = (string)firstSpec.GetType().GetField("internalId").GetValue(firstSpec);
        WholeCatalogLoader.locator = new ResourceLocationMap();
        AddLocation(WholeCatalogLoader.locator, firstKey, "foreign/primary.prefab", firstPath);
        failed = false;
        try { Drain(Prepare(owner)); } catch (InvalidOperationException) { failed = true; }
        Require(failed && Addressables.operations.Count == 0, "foreign primary key refuses before request");
        Cleanup(owner);

        owner = NewOwner();
        reflectedRows = (Array)typeof(PortSession).GetNestedType("OriginalEquipmentHighlightAssetsSession", BindingFlags.NonPublic)
            .GetField("Rows", BindingFlags.Static | BindingFlags.NonPublic).GetValue(null);
        firstSpec = reflectedRows.GetValue(0);
        firstKey = (string)firstSpec.GetType().GetField("addressKey").GetValue(firstSpec);
        firstPrimary = (string)firstSpec.GetType().GetField("primaryKey").GetValue(firstSpec);
        WholeCatalogLoader.locator = new ResourceLocationMap();
        AddLocation(WholeCatalogLoader.locator, firstKey, firstPrimary, "Assets/foreign/HighlightEquipment.prefab");
        failed = false;
        try { Drain(Prepare(owner)); } catch (InvalidOperationException) { failed = true; }
        Require(failed && Addressables.operations.Count == 0, "foreign internal path refuses before request");
        Cleanup(owner);

        owner = NewOwner();
        pending = Prepare(owner);
        Require(pending.MoveNext(), "locator replacement fixture pending");
        WholeCatalogLoader.locator = NewLocator();
        CompleteAll();
        failed = false;
        try { Drain(pending); } catch (InvalidOperationException) { failed = true; }
        Require(failed && Field("equipmentHighlightPrefab").GetValue(null) == null,
                "replaced active locator refuses before publishing loaded locations");
        Cleanup(owner);

        // The durable session-level report is created before source validation,
        // so an early locator refusal is still visible to the caller.
        owner = NewOwner();
        WholeCatalogLoader.locator.Remove("164a5db278443b1469a210be383c4b0e");
        failed = false;
        try { Drain(Prepare(owner)); } catch (InvalidOperationException) { failed = true; }
        Require(failed && owner.r.originalEquipmentHighlightAssets != null &&
                owner.r.originalEquipmentHighlightAssets.state == "preparing",
                "early locator refusal remains in session report");
        Cleanup(owner);

        // A competing static owner arriving during the wait is never overwritten.
        owner = NewOwner();
        pending = Prepare(owner);
        Require(pending.MoveNext(), "conflict fixture pending");
        var foreign = new GameObject();
        Field("equipmentHighlightPrefab").SetValue(null, foreign);
        CompleteAll();
        failed = false;
        try { Drain(pending); } catch (InvalidOperationException) { failed = true; }
        Require(failed && ReferenceEquals(foreign, Field("equipmentHighlightPrefab").GetValue(null)),
                "slot conflict is refused before write");
        RequireCleanupRefusal(owner);
        Require(ReferenceEquals(foreign, Field("equipmentHighlightPrefab").GetValue(null)), "foreign value survives cleanup");

        // A destroyed Unity object is not mistaken for an empty managed reference.
        owner = NewOwner();
        var dead = new GameObject { destroyed = true };
        Field("equipmentHighlightPrefab").SetValue(null, dead);
        failed = false;
        try { Drain(Prepare(owner)); } catch (InvalidOperationException) { failed = true; }
        Require(failed && Addressables.operations.Count == 0, "fake-null static slot refuses without replacement request");
        RequireCleanupRefusal(owner);

        // A changed source field type refuses before issuing any request.
        owner = NewOwner();
        var sessionType = typeof(PortSession).GetNestedType("OriginalEquipmentHighlightAssetsSession", BindingFlags.NonPublic);
        var rows = (Array)sessionType.GetField("Rows", BindingFlags.Static | BindingFlags.NonPublic).GetValue(null);
        var firstRow = rows.GetValue(0);
        var fieldName = firstRow.GetType().GetField("field", BindingFlags.Instance | BindingFlags.Public);
        string originalName = (string)fieldName.GetValue(firstRow);
        fieldName.SetValue(firstRow, "wrongTypeField");
        failed = false;
        try { Drain(Prepare(owner)); } catch (InvalidOperationException) { failed = true; }
        fieldName.SetValue(firstRow, originalName);
        Require(failed && Addressables.operations.Count == 0, "changed static type refuses before loading");
        Cleanup(owner);

        // An operation that never finishes is a bounded startup refusal.
        owner = NewOwner();
        pending = Prepare(owner);
        Require(pending.MoveNext(), "timeout fixture pending");
        UnityEngine.Time.realtimeSinceStartup = 60f;
        failed = false;
        try { pending.MoveNext(); } catch (TimeoutException) { failed = true; }
        Require(failed, "pending operations time out instead of admitting the camera");
        Cleanup(owner);
        Require(Addressables.operations.TrueForAll(x => x.releases == 1), "timeout cleanup releases all handles");

        // A pending preparation reserves the owner before issuing its first
        // request; a duplicate cannot reset the live report or issue more loads.
        owner = NewOwner();
        pending = Prepare(owner);
        Require(pending.MoveNext(), "duplicate reservation fixture pending");
        var reportBeforeDuplicate = owner.r.originalEquipmentHighlightAssets;
        reportBeforeDuplicate.state = "sentinel-preserved";
        failed = false;
        try { Drain(Prepare(owner)); } catch (InvalidOperationException) { failed = true; }
        Require(failed && Addressables.operations.Count == 3 && reportBeforeDuplicate.state == "sentinel-preserved",
                "duplicate pending preparation refuses before report mutation or new requests");
        Cleanup(owner);
        Require(!pending.MoveNext(), "resuming an iterator after disposal cannot publish");
        Require(Field("equipmentHighlightPrefab").GetValue(null) == null, "disposed pending request publishes no static slots");

        // Dispose while waiting cancels publication even if Addressables complete
        // before the suspended iterator is resumed.
        owner = NewOwner();
        pending = Prepare(owner);
        Require(pending.MoveNext(), "cancellation fixture pending");
        Cleanup(owner);
        CompleteAll();
        Require(!pending.MoveNext(), "cancelled coroutine exits without reading or publishing released handles");
        Require(Field("equipmentHighlightPrefab").GetValue(null) == null &&
                owner.r.originalEquipmentHighlightAssets.state == "cancelled-cleaned",
                "cancellation remains truthful and does not assign slots");

        // An original callback publishing the identical loaded object still has
        // an independent lifetime; this route cannot silently adopt it.
        owner = NewOwner();
        pending = Prepare(owner);
        Require(pending.MoveNext(), "same-result callback fixture pending");
        CompleteAll();
        var replacement = Addressables.operations[0].result;
        Field("equipmentHighlightPrefab").SetValue(null, replacement);
        failed = false;
        try { Drain(pending); } catch (InvalidOperationException) { failed = true; }
        Require(failed && ReferenceEquals(replacement, Field("equipmentHighlightPrefab").GetValue(null)),
                "same-result callback still refuses an unowned static write");
        RequireCleanupRefusal(owner);
        Require(ReferenceEquals(replacement, Field("equipmentHighlightPrefab").GetValue(null)),
                "same-result foreign static survives failed retirement");

        // If a later Addressables request throws, all earlier handles remain
        // owned and are released; no partially loaded result reaches a static.
        owner = NewOwner();
        Addressables.throwOnKey = "RoR2/Base/UI/HighlightLunarItem.prefab";
        failed = false;
        try { Drain(Prepare(owner)); } catch (InvalidOperationException) { failed = true; }
        Require(failed && Addressables.operations.Count == 1 &&
                Field("equipmentHighlightPrefab").GetValue(null) == null,
                "partial request throw retains acquired handles without publishing");
        Cleanup(owner);
        Require(Addressables.operations[0].releases == 1, "partial request throw releases prior acquired handle");

        owner = NewOwner();
        Addressables.throwOnKey = "RoR2/Base/UI/HighlightLunarItem.prefab";
        Addressables.create = _ => new TestOperation<GameObject>();
        failed = false;
        Exception preparationFailure = null;
        try { Drain(Prepare(owner)); } catch (InvalidOperationException exception) { failed = true; preparationFailure = exception; }
        Addressables.operations[0].throwOnRelease = true;
        AggregateException combinedFailure = null;
        try { Cleanup(owner, preparationFailure); }
        catch (TargetInvocationException exception) { combinedFailure = exception.InnerException as AggregateException; }
        Require(failed && combinedFailure != null && combinedFailure.InnerExceptions.Contains(preparationFailure) &&
                owner.r.originalEquipmentHighlightAssets.state == "cleanup-failed",
                "cleanup failure is aggregated with, not substituted for, the preparation failure");

        // Cleanup attempts every owned release even when one release fails, and
        // a repeated call cannot convert the failed outcome into success.
        owner = NewOwner();
        pending = Prepare(owner);
        Require(pending.MoveNext(), "release-failure fixture pending");
        Addressables.operations[0].throwOnRelease = true;
        failed = false;
        try { Cleanup(owner); } catch (TargetInvocationException exception) when (exception.InnerException is AggregateException) { failed = true; }
        Require(failed && Addressables.operations[1].releases == 1 && Addressables.operations[2].releases == 1,
                "release failure is aggregated after remaining handles are attempted");
        Require(owner.r.originalEquipmentHighlightAssets.state == "cleanup-failed",
                "release failure is visible in report");
        failed = false;
        try { Cleanup(owner); } catch (TargetInvocationException exception) when (exception.InnerException is AggregateException) { failed = true; }
        Require(failed && owner.r.originalEquipmentHighlightAssets.state == "cleanup-failed",
                "repeat cleanup remains failed instead of reporting success");

        // A slot ownership conflict is sticky across repeated cleanup calls.
        owner = NewOwner();
        pending = Prepare(owner);
        Require(pending.MoveNext(), "sticky-conflict fixture pending");
        CompleteAll();
        Drain(pending);
        foreign = new GameObject();
        Field("equipmentHighlightPrefab").SetValue(null, foreign);
        failed = false;
        try { Cleanup(owner); } catch (TargetInvocationException exception) when (exception.InnerException is AggregateException) { failed = true; }
        Require(failed && owner.r.originalEquipmentHighlightAssets.state == "cleanup-failed",
                "initial cleanup conflict is reported");
        failed = false;
        try { Cleanup(owner); } catch (TargetInvocationException exception) when (exception.InnerException is AggregateException) { failed = true; }
        Require(failed && owner.r.originalEquipmentHighlightAssets.state == "cleanup-failed" &&
                ReferenceEquals(foreign, Field("equipmentHighlightPrefab").GetValue(null)),
                "repeat cleanup preserves failed conflict and foreign slot");

        Console.WriteLine("original-equipment-highlight-owner-contract: PASS");
        return 0;
    }
}
