using System;
using System.Collections.Generic;
using System.IO;

internal sealed class FakeFinalizerNativeApi : INativeWwiseDiagApi
{
    internal readonly long[] Values = new long[24];
    internal readonly List<string> Events;
    internal int RegisterCalls;
    internal int UnregisterCalls;
    internal int EngineTermCalls;
    internal int CallbackTermCalls;

    internal FakeFinalizerNativeApi(List<string> events)
    {
        Events = events;
        Values[14] = 1;
        Values[21] = 3;
    }
    public int Arm() { Values[13] = 1; return 1; }
    public int IsArmed() { return 1; }
    public int PostControl() { Values[22]++; return 1; }
    public int MarkEngineInitAttempted() { Values[23] = 1; return 1; }
    public int DisarmBeforeInit() { Values[13] = 2; return 1; }
    public void EngineTermReturned() { EngineTermCalls++; Events.Add("engine_term"); Values[12] = 1; }
    public void CallbackManagerTermReturned() { CallbackTermCalls++; Events.Add("callback_manager_term"); Values[20] = 1; }
    public bool FailDisarm;
    public int DisarmAfterTerm() { if (FailDisarm) return -7; Values[13] = 3; Values[19] = 1; return 1; }
    public int RegisterCapture(uint selectorMode, ulong outputSelector)
    {
        RegisterCalls++; Values[11] = 1; Values[15] = 1; Values[17] = 1; return 1;
    }
    public int UnregisterCapture(uint selectorMode, ulong outputSelector)
    {
        UnregisterCalls++; Events.Add("unregister"); Values[11] = 0; Values[16] = 1; return 1;
    }
    public long[] Snapshot() { return (long[])Values.Clone(); }
    internal void AddPcm()
    {
        Values[3] += 1; Values[4] += 1; Values[5] += 2; Values[6] += 2;
        Values[7] += 2; Values[18] = 77;
    }
}

internal sealed class FakeFinalizerReadbackApi : IPcmWaveformReadbackApiV1
{
    internal readonly List<string> Events;
    internal bool FailMetadata;
    internal uint ChannelMask = 3;
    internal int MetadataCalls;
    internal int CopyCalls;
    internal ulong Generation = 99;
    internal readonly float[] Samples = { 0.25f, -0.25f };
    internal FakeFinalizerReadbackApi(List<string> events) { Events = events; }
    public int ReadMetadata(int[] words)
    {
        MetadataCalls++; Events.Add("metadata_read");
        if (FailMetadata) return -99;
        Array.Clear(words, 0, words.Length);
        words[0] = 1;
        words[1] = unchecked((int)(1u | 2u | 8u | 256u));
        words[2] = unchecked((int)Generation); words[4] = 77; words[6] = 48000; words[7] = 2; words[8] = (int)ChannelMask; words[9] = 1;
        words[10] = 2; words[12] = 2; words[13] = 2; words[15] = 2; words[19] = 1;
        words[21] = BitConverter.ToInt32(BitConverter.GetBytes(0.25f), 0);
        words[22] = BitConverter.ToInt32(BitConverter.GetBytes(0.25f), 0);
        words[23] = BitConverter.ToInt32(BitConverter.GetBytes(0.25f), 0);
        return 1;
    }
    public int CopySamples(ulong generation, ulong expectedOutputId, float[] destination, out uint copiedSamples)
    {
        CopyCalls++; Events.Add("sample_copy");
        copiedSamples = 0;
        if (generation != Generation || expectedOutputId != 77 || destination.Length < Samples.Length) return -1;
        Array.Copy(Samples, destination, Samples.Length);
        copiedSamples = (uint)Samples.Length;
        return 1;
    }
}

internal static class PcmWaveformCaptureFinalizerHarness
{
    private static void Check(bool value, string message)
    {
        if (!value) throw new Exception(message);
    }
    private static NativeWwiseMonitorLease ReadyLease(FakeFinalizerNativeApi api)
    {
        var lease = new NativeWwiseMonitorLease(api);
        lease.ArmBeforeInit(); lease.MarkEngineInitAttempted();
        lease.BeginPostInitControlObservation(); lease.PollPostInitControl();
        Check(lease.PostInitControlObserved, "exact post-init control precedes capture");
        return lease;
    }
    private static PassivePcmCaptureWindow StartWindow(FakeFinalizerNativeApi native,
        PcmWaveformCaptureFinalizerV1 finalizer,
        GameAudioOriginalPassivePcmCaptureSelection? selection = null, NativeWwiseMonitorLease existingLease = null)
    {
        var lease = existingLease ?? ReadyLease(native);
        Action guard = null;
        var window = new PassivePcmCaptureWindow(lease, true,
            value => guard = value, () => guard, null, finalizer);
        Check(selection.HasValue ? window.RequestGameplayArm(selection.Value) : window.RequestGameplayArm(),
            "explicit capture request arms at playable boundary");
        Check(window.Start(1f, true, true, true, 1), "one admitted capture starts after service frame");
        native.AddPcm();
        window.FinishGameplayWindow();
        Check(native.UnregisterCalls == 1 && lease.CaptureSafeBeforeEngineTerm,
            "window uses existing exact unregister before readback");
        Check(window.Report.State == "captured", "readback errors do not rewrite successful callback cleanup");
        return window;
    }
    private static void ReadbackThenTermsThenPrivatePersist()
    {
        var events = new List<string>();
        var native = new FakeFinalizerNativeApi(events);
        var api = new FakeFinalizerReadbackApi(events);
        string root = Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "private-root-success");
        Directory.CreateDirectory(root);
        try
        {
            var finalizer = new PcmWaveformCaptureFinalizerV1(api, () => root);
            var window = StartWindow(native, finalizer);
            Check(finalizer.State == "validated_waiting_for_original_terms" && api.MetadataCalls == 1 && api.CopyCalls == 1,
                "metadata and sample bytes are copied exactly once before original Term");
            Check(events.IndexOf("unregister") < events.IndexOf("metadata_read") &&
                events.IndexOf("metadata_read") < events.IndexOf("sample_copy"),
                "readback follows the successful unregister/absent snapshot path");
            string export = Path.Combine(root, "lab-original-audio-pcm");
            Check(!Directory.Exists(export), "raw file persistence is deferred until after original Terms");
            Check(!finalizer.PersistAfterOriginalTerms(null), "missing Term/disarm lease is insufficient to persist");
            Check(native.EngineTermCalls == 0, "managed readback does not invoke Term");
            var lease = GetLease(window);
            lease.RecordEngineTermReturned();
            Check(!PcmWaveformTermFinalizerV1.RunAfterVerifiedTerms(lease,
                () => finalizer.PersistAfterOriginalTerms(lease), null),
                "engine Term alone cannot trigger final persistence");
            lease.RecordCallbackManagerTermReturned();
            lease.DisarmAfterReturnedTerms();
            bool observerReturned = false;
            Check(PcmWaveformTermFinalizerV1.RunAfterVerifiedTerms(lease, () =>
            {
                Check(finalizer.PersistAfterOriginalTerms(lease), "both verified Term markers permit persistence");
                Check(Directory.GetFiles(export).Length == 2, "raw PCM and metadata sidecar are written before the observer returns");
                observerReturned = true;
            }, null), "the verified callback-manager return observer invokes finalization synchronously");
            Check(observerReturned, "no Unity Update is needed to finish raw evidence persistence");
            Check(Directory.GetFiles(export).Length == 2, "raw PCM and metadata sidecar are written together");
            Check(finalizer.RawPersisted && finalizer.State == "written" && finalizer.Generation == 99 &&
                finalizer.StoredSamples == 2, "safe scalar receipt state survives clearing managed sample buffer");
            string metadata = File.ReadAllText(Directory.GetFiles(export, "*.json")[0]);
            Check(metadata.Contains("\"raw_pcm_persisted\": true") &&
                metadata.Contains("\"source_event_attributed\": false") &&
                metadata.Contains("\"physical_audibility_claim\": false"),
                "private sidecar labels raw persistence and keeps event/audibility claims false");
            int copyAt = events.IndexOf("sample_copy");
            int engineTermAt = events.IndexOf("engine_term");
            int callbackTermAt = events.IndexOf("callback_manager_term");
            Check(copyAt < engineTermAt && engineTermAt < callbackTermAt && api.MetadataCalls == 1,
                "sample copy precedes both Terms and metadata is never reread afterwards");
            window.PersistWaveformAfterOriginalTerms();
            Check(api.MetadataCalls == 1 && api.CopyCalls == 1 && Directory.GetFiles(export).Length == 2,
                "repeated owner update does not retry readback or persistence");
        }
        finally { if (Directory.Exists(root)) Directory.Delete(root, true); }
    }
    private static void SameNativeGenerationGetsDistinctPrivateCaptureFiles()
    {
        string root = Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "private-root-repeat-generation");
        Directory.CreateDirectory(root);
        try
        {
            var ids = new HashSet<string>(StringComparer.Ordinal);
            for (int capture = 0; capture < 2; capture++)
            {
                var events = new List<string>();
                var native = new FakeFinalizerNativeApi(events);
                var api = new FakeFinalizerReadbackApi(events) { Generation = 1 };
                var finalizer = new PcmWaveformCaptureFinalizerV1(api, () => root);
                var window = StartWindow(native, finalizer);
                var lease = GetLease(window);
                lease.RecordEngineTermReturned();
                lease.RecordCallbackManagerTermReturned();
                lease.DisarmAfterReturnedTerms();
                Check(PcmWaveformTermFinalizerV1.RunAfterVerifiedTerms(lease,
                    () => window.PersistWaveformAfterOriginalTerms(), null), "verified Term observer persists repeat capture");
            }
            string export = Path.Combine(root, "lab-original-audio-pcm");
            string[] sidecars = Directory.GetFiles(export, "*.json");
            string[] raw = Directory.GetFiles(export, "*.f32le");
            Check(sidecars.Length == 2 && raw.Length == 2,
                "two cold-process captures with native generation one preserve both raw/sidecar pairs");
            foreach (string sidecar in sidecars)
            {
                string json = File.ReadAllText(sidecar);
                var match = System.Text.RegularExpressions.Regex.Match(json, "\"capture_id\": \"([0-9a-f]{32})\"");
                Check(match.Success && ids.Add(match.Groups[1].Value), "each persisted pair has its own opaque canonical nonce");
            }
        }
        finally { if (Directory.Exists(root)) Directory.Delete(root, true); }
    }

    private static NativeWwiseMonitorLease GetLease(PassivePcmCaptureWindow window)
    {
        return (NativeWwiseMonitorLease)typeof(PassivePcmCaptureWindow)
            .GetField("lease", System.Reflection.BindingFlags.Instance | System.Reflection.BindingFlags.NonPublic)
            .GetValue(window);
    }
    private static void ReadbackFailureDoesNotBlockNativeTerms()
    {
        var events = new List<string>();
        var native = new FakeFinalizerNativeApi(events);
        var api = new FakeFinalizerReadbackApi(events) { FailMetadata = true };
        string root = Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "private-root-read-failure");
        Directory.CreateDirectory(root);
        try
        {
            var finalizer = new PcmWaveformCaptureFinalizerV1(api, () => root);
            var window = StartWindow(native, finalizer);
            Check(finalizer.State == "failed" && finalizer.Failure == "metadata_read_result_not_success",
                "native metadata failure is recorded as readback-only failure");
            Check(window.Report.State == "captured" && GetLease(window).CaptureSafeBeforeEngineTerm,
                "failed readback leaves successful callback removal and capture report intact");
            Check(window.Report.Failure == null && window.Report.WaveformReadbackFailure == finalizer.Failure,
                "readback evidence failure remains separate from the capture/lifecycle failure channel");
            var lease = GetLease(window);
            lease.RecordEngineTermReturned(); lease.RecordCallbackManagerTermReturned(); lease.DisarmAfterReturnedTerms();
            Check(lease.EngineTermReturnedState && lease.CallbackManagerTermReturnedState &&
                native.EngineTermCalls == 1 && native.CallbackTermCalls == 1,
                "original Term-return markers still complete after readback failure");
            Check(!finalizer.PersistAfterOriginalTerms(lease) && !Directory.Exists(Path.Combine(root, "lab-original-audio-pcm")),
                "failed readback creates no private audio files");
        }
        finally { if (Directory.Exists(root)) Directory.Delete(root, true); }
    }
    private static void MissingPrivateRootSkipsNativeReadbackButNotUnregister()
    {
        var events = new List<string>();
        var native = new FakeFinalizerNativeApi(events);
        var api = new FakeFinalizerReadbackApi(events);
        var finalizer = new PcmWaveformCaptureFinalizerV1(api, () => throw new IOException("root not available"));
        var window = StartWindow(native, finalizer);
        Check(finalizer.State == "failed" && api.MetadataCalls == 0 && api.CopyCalls == 0,
            "missing verified root fails closed before consuming one-shot native readback");
        Check(native.UnregisterCalls == 1 && GetLease(window).CaptureSafeBeforeEngineTerm,
            "root refusal cannot suppress or retry the existing callback unregister");
        var lease = GetLease(window);
        lease.RecordEngineTermReturned(); lease.RecordCallbackManagerTermReturned();
        Check(lease.EngineTermReturnedState && lease.CallbackManagerTermReturnedState,
            "Term proceeds when private persistence root cannot be proved");
    }
    private static void SelectedOutputMismatchRefusesReadback()
    {
        var events = new List<string>();
        var native = new FakeFinalizerNativeApi(events);
        var api = new FakeFinalizerReadbackApi(events);
        string root = Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "private-root-output-mismatch");
        Directory.CreateDirectory(root);
        try
        {
            GameAudioOriginalPassivePcmCaptureSelection selection;
            Check(GameAudioOriginalPassivePcmCaptureSelection.TrySpecificOutput(
                true, true, true, 78, out selection), "a known accepted specific output is represented exactly");
            var finalizer = new PcmWaveformCaptureFinalizerV1(api, () => root);
            var window = StartWindow(native, finalizer, selection);
            Check(finalizer.State == "failed" && finalizer.Failure == "callback_removal_or_output_identity_unproven" &&
                api.MetadataCalls == 0 && api.CopyCalls == 0,
                "reported callback output cannot substitute for a different selected output");
            var lease = GetLease(window);
            Check(lease.CaptureSafeBeforeEngineTerm && native.UnregisterCalls == 1,
                "specific-output mismatch refuses evidence without changing callback ownership cleanup");
            lease.RecordEngineTermReturned(); lease.RecordCallbackManagerTermReturned();
            Check(lease.EngineTermReturnedState && lease.CallbackManagerTermReturnedState,
                "specific-output mismatch does not interrupt either original Term path");
        }
        finally { if (Directory.Exists(root)) Directory.Delete(root, true); }
    }
    private static void InvalidLayoutAndWriteCollisionFailWithoutTermImpact()
    {
        var events = new List<string>();
        var native = new FakeFinalizerNativeApi(events);
        var api = new FakeFinalizerReadbackApi(events) { ChannelMask = 0 };
        string root = Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "private-root-layout-failure");
        Directory.CreateDirectory(root);
        try
        {
            var finalizer = new PcmWaveformCaptureFinalizerV1(api, () => root);
            var window = StartWindow(native, finalizer);
            Check(finalizer.State == "failed" && finalizer.Failure == "unsupported_pcm_layout" && api.CopyCalls == 0,
                "noncanonical channel mask is rejected before raw sample copy");
            var lease = GetLease(window);
            lease.RecordEngineTermReturned(); lease.RecordCallbackManagerTermReturned();
            Check(lease.EngineTermReturnedState && lease.CallbackManagerTermReturnedState,
                "unsupported PCM layout does not affect either original Term path");
        }
        finally { if (Directory.Exists(root)) Directory.Delete(root, true); }

        events = new List<string>();
        native = new FakeFinalizerNativeApi(events);
        api = new FakeFinalizerReadbackApi(events);
        root = Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "private-root-write-collision");
        string export = Path.Combine(root, "lab-original-audio-pcm");
        Directory.CreateDirectory(export);
        const string fixedCaptureId = "00000000000000000000000000000000";
        string existing = Path.Combine(export, "capture-v1-" + fixedCaptureId + "-0000000000000063.f32le");
        File.WriteAllText(existing, "preexisting");
        try
        {
            var finalizer = new PcmWaveformCaptureFinalizerV1(api, () => root, fixedCaptureId);
            var window = StartWindow(native, finalizer);
            var lease = GetLease(window);
            lease.RecordEngineTermReturned(); lease.RecordCallbackManagerTermReturned();
            lease.DisarmAfterReturnedTerms();
            Check(!finalizer.PersistAfterOriginalTerms(lease) && finalizer.State == "failed",
                "pre-existing app-private output path refuses overwrite");
            Check(window.Report.Failure == null && window.Report.WaveformReadbackFailure == finalizer.Failure,
                "post-Term persistence failure cannot become an original audio lifecycle failure");
            Check(File.ReadAllText(existing) == "preexisting" && Directory.GetFiles(export).Length == 1,
                "failed create-new persistence preserves foreign/pre-existing files");
            Check(lease.EngineTermReturnedState && lease.CallbackManagerTermReturnedState,
                "persistence collision cannot roll back or interrupt completed Terms");
        }
        finally { if (Directory.Exists(root)) Directory.Delete(root, true); }
    }
    private static void ActualBootstrapTermObserverPersistsOnlyAfterVerifiedDisarm()
    {
        var events = new List<string>();
        var native = new FakeFinalizerNativeApi(events);
        var lease = ReadyLease(native);
        string root = Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "private-root-bootstrap-chain");
        Directory.CreateDirectory(root);
        try
        {
            var readback = new FakeFinalizerReadbackApi(events);
            var finalizer = new PcmWaveformCaptureFinalizerV1(readback, () => root);
            var window = StartWindow(native, finalizer, null, lease);
            int finalized = 0;
            int evidenceFailure = 0;
            var bootstrap = new GameAudioOriginalAndroidNativeBootstrap(lease,
                () => { finalized++; window.PersistWaveformAfterOriginalTerms(); },
                () => { evidenceFailure++; window.RecordUnverifiedPostTermDisarm(); });

            bootstrap.ObserveCallbackManagerTermReturned();
            Check(finalized == 0 && native.CallbackTermCalls == 0,
                "actual bootstrap callback observer ignores callback-manager Term before engine Term");
            bootstrap.ObserveEngineTermReturned();
            bootstrap.ObserveCallbackManagerTermReturned();
            Check(finalized == 1 && evidenceFailure == 0 && lease.DisarmAttempted && lease.ArmedState == 3 &&
                !lease.OutcomeUnknown,
                "actual bootstrap observer records both Terms, verifies disarm, then runs finalizer");
            string export = Path.Combine(root, "lab-original-audio-pcm");
            Check(Directory.GetFiles(export).Length == 2 && finalizer.RawPersisted,
                "actual observer call persists both raw and sidecar before returning without Update");
            string json = File.ReadAllText(Directory.GetFiles(export, "*.json")[0]);
            Check(json.Contains("\"original_engine_term_returned\": true") &&
                json.Contains("\"original_callback_manager_term_returned\": true") &&
                json.Contains("\"post_term_disarm_verified\": true"),
                "private sidecar records all three verified lifecycle witnesses");
            bootstrap.ObserveCallbackManagerTermReturned();
            Check(finalized == 1 && native.CallbackTermCalls == 1,
                "duplicate actual callback-Term observer cannot repeat persistence or native calls");
        }
        finally { if (Directory.Exists(root)) Directory.Delete(root, true); }

        events = new List<string>();
        native = new FakeFinalizerNativeApi(events) { FailDisarm = true };
        lease = ReadyLease(native);
        root = Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "private-root-bootstrap-disarm-failure");
        Directory.CreateDirectory(root);
        try
        {
            var finalizer = new PcmWaveformCaptureFinalizerV1(new FakeFinalizerReadbackApi(events), () => root);
            var window = StartWindow(native, finalizer, null, lease);
            int evidenceFailure = 0;
            var bootstrap = new GameAudioOriginalAndroidNativeBootstrap(lease, () => window.PersistWaveformAfterOriginalTerms(),
                () => { evidenceFailure++; window.RecordUnverifiedPostTermDisarm(); });
            bootstrap.ObserveEngineTermReturned();
            Exception observed = null;
            try { bootstrap.ObserveCallbackManagerTermReturned(); }
            catch (Exception error) { observed = error; }
            Check(observed is NativeWwiseDiagRefusalException,
                "the actual bootstrap preserves the original native disarm exception outcome");
            Check(evidenceFailure == 1 && !finalizer.RawPersisted && finalizer.State == "failed" &&
                finalizer.Failure == "post_term_disarm_unverified" &&
                !Directory.Exists(Path.Combine(root, "lab-original-audio-pcm")),
                "failed disarm records dedicated evidence refusal and never persists raw PCM");
        }
        finally { if (Directory.Exists(root)) Directory.Delete(root, true); }

        events = new List<string>();
        native = new FakeFinalizerNativeApi(events);
        lease = ReadyLease(native);
        root = Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "private-root-bootstrap-writer-failure");
        Directory.CreateDirectory(root);
        try
        {
            var finalizer = new PcmWaveformCaptureFinalizerV1(new FakeFinalizerReadbackApi(events), () => root);
            var window = StartWindow(native, finalizer, null, lease);
            var bootstrap = new GameAudioOriginalAndroidNativeBootstrap(lease,
                () => window.PersistWaveformAfterOriginalTerms(),
                () => window.RecordUnverifiedPostTermDisarm());
            Directory.Delete(root, true);
            bootstrap.ObserveEngineTermReturned();
            bootstrap.ObserveCallbackManagerTermReturned();
            Check(lease.ArmedState == 3 && !lease.OutcomeUnknown && finalizer.State == "failed" &&
                finalizer.Failure.StartsWith("persistence_failed:", StringComparison.Ordinal) &&
                !finalizer.RawPersisted,
                "writer failure is contained after verified disarm and cannot change the original Term result");
        }
        finally { if (Directory.Exists(root)) Directory.Delete(root, true); }
    }

    private static int Main()
    {
        ReadbackThenTermsThenPrivatePersist();
        SameNativeGenerationGetsDistinctPrivateCaptureFiles();
        ReadbackFailureDoesNotBlockNativeTerms();
        MissingPrivateRootSkipsNativeReadbackButNotUnregister();
        SelectedOutputMismatchRefusesReadback();
        InvalidLayoutAndWriteCollisionFailWithoutTermImpact();
        ActualBootstrapTermObserverPersistsOnlyAfterVerifiedDisarm();
        Console.WriteLine("PASS actual bootstrap Term observer, pre-Term readback, post-Term private persistence, and failure-safe cleanup");
        return 0;
    }
}
