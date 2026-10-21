using System;
using System.Collections;
using System.Collections.Generic;

// Host-injectable preparation boundary. The platform adapter must be the
// accepted Android library/resolver/monitor path; this class never calls Wwise.
public interface IGameAudioOriginalNativeBootstrap
{
    bool EnsureNativeLibraryLoaded { get; }
    bool InstallAndroidResolver { get; }
    void AbandonBeforeOriginalInit();
    void ArmNativeMonitorBeforeExistingInit();
    void MarkNativeEngineInitAttempted();
    void PostExactControlMarker();
    bool ExactControlMarkerObserved { get; }
    bool NativeControlObservationFailed { get; }
    string PersistentBankRoot { get; }
    void ObserveEngineTermReturned();
    void ObserveCallbackManagerTermReturned();
}

public interface IGameAudioOriginalPayloadCopyOperation
{
    string Refusal { get; }
    IEnumerator CopyToOriginalSearchRoot();
}

public sealed class GameAudioOriginalPreparation : IGameAudioOriginalStartupPreparation
{
    private readonly string streamingRoot;
    private readonly IEnumerable<string> sourceBankNames;
    private readonly string receiptSha256;
    private readonly IGameAudioOriginalNativeBootstrap native;
    private IGameAudioOriginalPayloadCopyOperation payloadCopy;
    private readonly Func<string, IGameAudioOriginalPayloadCopyOperation> payloadFactory;
    private bool prepared;
    private bool originalInitAttempted;
    private string refusal;

    public GameAudioOriginalPreparation(string streamingRoot, IEnumerable<string> sourceBankNames,
        string receiptSha256, IGameAudioOriginalNativeBootstrap native)
        : this(streamingRoot, sourceBankNames, receiptSha256, native,
            root => new GameAudioOriginalPayloadCopy(streamingRoot, root, sourceBankNames, receiptSha256))
    {
    }

    internal GameAudioOriginalPreparation(string streamingRoot, IEnumerable<string> sourceBankNames,
        string receiptSha256, IGameAudioOriginalNativeBootstrap native,
        Func<string, IGameAudioOriginalPayloadCopyOperation> payloadFactory)
    {
        this.streamingRoot = streamingRoot ?? throw new ArgumentNullException(nameof(streamingRoot));
        this.sourceBankNames = sourceBankNames ?? throw new ArgumentNullException(nameof(sourceBankNames));
        this.receiptSha256 = receiptSha256 ?? throw new ArgumentNullException(nameof(receiptSha256));
        this.native = native ?? throw new ArgumentNullException(nameof(native));
        this.payloadFactory = payloadFactory ?? throw new ArgumentNullException(nameof(payloadFactory));
    }

    public bool Prepared { get { return prepared; } }
    public string Refusal { get { return refusal; } }

    public IEnumerator PrepareBeforeExistingManagerInit()
    {
        bool resolverMayBeInstalled = false;
        try
        {
            string error;
            bool loaded;
            try { loaded = native.EnsureNativeLibraryLoaded; error = null; }
            catch (Exception exception) { loaded = false; error = "android_native_library_load_threw:" + exception.GetType().Name; }
            if (!loaded)
            { Refuse(error ?? "android_native_library_load_not_proven"); yield break; }
            resolverMayBeInstalled = true;
            bool installed;
            try { installed = native.InstallAndroidResolver; error = null; }
            catch (Exception exception) { installed = false; error = "android_import_resolver_threw:" + exception.GetType().Name; }
            if (!installed)
            { Refuse(error ?? "android_import_resolver_not_installed"); yield break; }
            string root;
            if (!TryGetPersistentRoot(out root, out error))
            { Refuse(error); yield break; }
            if (String.IsNullOrWhiteSpace(root))
            { Refuse("original_android_persistent_bank_root_unavailable"); yield break; }
            if (!TryCreatePayloadCopy(root, out error))
            { Refuse(error); yield break; }
            IEnumerator copyRoutine = payloadCopy.CopyToOriginalSearchRoot();
            while (true)
            {
                bool moved;
                object current;
                if (!TryAdvance(copyRoutine, out moved, out current, out error))
                { Refuse(error); yield break; }
                if (!moved) break;
                yield return current;
            }
            if (!String.IsNullOrEmpty(payloadCopy.Refusal))
            { Refuse(payloadCopy.Refusal); yield break; }
            try { native.ArmNativeMonitorBeforeExistingInit(); }
            catch (Exception exception)
            { Refuse("native_monitor_preinit_arm_failed:" + exception.GetType().Name); yield break; }
            prepared = true;
        }
        finally
        {
            if (resolverMayBeInstalled && !prepared && !originalInitAttempted)
                RestoreResolver();
        }
    }

    private static bool TryAdvance(IEnumerator routine, out bool moved, out object current, out string error)
    {
        try
        {
            moved = routine.MoveNext();
            current = moved ? routine.Current : null;
            error = null;
            return true;
        }
        catch (Exception exception)
        {
            moved = false;
            current = null;
            error = "payload_copy_threw:" + exception.GetType().Name;
            return false;
        }
    }

    private bool TryGetPersistentRoot(out string root, out string error)
    {
        try { root = native.PersistentBankRoot; error = null; return true; }
        catch (Exception exception)
        { root = null; error = "original_android_persistent_bank_root_failed:" + exception.GetType().Name; return false; }
    }

    private bool TryCreatePayloadCopy(string root, out string error)
    {
        try
        {
            payloadCopy = payloadFactory(root);
            if (payloadCopy == null) throw new InvalidOperationException("Payload factory returned null.");
            error = null;
            return true;
        }
        catch (Exception exception)
        { error = "payload_copy_configuration_failed:" + exception.GetType().Name; return false; }
    }

    public void ArmNativeMonitorBeforeInit()
    {
        if (!prepared) throw new InvalidOperationException("Preparation has not completed.");
        try
        {
            native.MarkNativeEngineInitAttempted();
            originalInitAttempted = true;
        }
        catch
        {
            RestoreResolver();
            throw;
        }
    }

    public void AbandonBeforeOriginalInit()
    {
        if (!originalInitAttempted) RestoreResolver();
    }

    public void PostExactControlMarker()
    {
        if (!prepared) throw new InvalidOperationException("Preparation has not completed.");
        native.PostExactControlMarker();
    }

    public bool NativeExactControlObserved() { return native.ExactControlMarkerObserved; }
    public bool NativeControlObservationFailed { get { return native.NativeControlObservationFailed; } }
    public void ObserveEngineTermReturned() { native.ObserveEngineTermReturned(); }
    public void ObserveCallbackManagerTermReturned() { native.ObserveCallbackManagerTermReturned(); }

    private void Refuse(string reason)
    {
        refusal = reason;
    }

    private void RestoreResolver()
    {
        try { native.AbandonBeforeOriginalInit(); }
        catch (Exception error)
        {
            refusal = (refusal ?? "original_audio_preparation_refused") +
                ":resolver_restore_failed:" + error.GetType().Name;
        }
    }
}
