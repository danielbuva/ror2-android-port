using System;
using System.Globalization;
using System.IO;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using System.Text;
using System.Threading;

// Draft-only managed boundary. Integrate after the existing native lease has
// successfully unregistered its exact selector and verified CaptureRegistered=0.
internal interface IPcmWaveformReadbackApiV1
{
    int ReadMetadata(int[] words);
    int CopySamples(ulong generation, ulong expectedOutputId, float[] destination, out uint copiedSamples);
}

internal sealed class PcmWaveformMetadataV1
{
    internal const uint Schema = 1;
    internal const int WordCount = 24;
    internal const uint MaxSamples = 262144;
    internal const uint Float32 = 1;
    internal const uint FlagOutputKnown = 1u << 0;
    internal const uint FlagFormatKnown = 1u << 1;
    internal const uint FlagTruncated = 1u << 2;
    internal const uint FlagWaveformValid = 1u << 3;
    internal const uint FlagOutputMismatch = 1u << 4;
    internal const uint FlagConcurrentCallback = 1u << 5;
    internal const uint FlagFormatChanged = 1u << 6;
    internal const uint FlagCounterOverflow = 1u << 7;
    internal const uint FlagChannelMaskKnown = 1u << 8;

    internal uint Flags;
    internal ulong Generation;
    internal ulong OutputId;
    internal uint SampleRateHz;
    internal uint Channels;
    internal uint ChannelMask;
    internal uint Format;
    internal ulong TotalSamples;
    internal uint StoredSamples;
    internal ulong FiniteSamples;
    internal ulong NonzeroFiniteSamples;
    internal ulong NonfiniteSamples;
    internal ulong Callbacks;
    internal float WindowPeakAbs;
    internal float WindowRms;
    internal float StoredPrefixPeakAbs;

    internal bool Truncated { get { return (Flags & FlagTruncated) != 0; } }
    internal bool WaveformValid { get { return (Flags & FlagWaveformValid) != 0; } }

    internal static bool TryParse(int[] words, out PcmWaveformMetadataV1 result)
    {
        result = null;
        if (words == null || words.Length != WordCount || U(words[0]) != Schema) return false;
        var metadata = new PcmWaveformMetadataV1();
        metadata.Flags = U(words[1]);
        metadata.Generation = U64(words[2], words[3]);
        metadata.OutputId = U64(words[4], words[5]);
        metadata.SampleRateHz = U(words[6]);
        metadata.Channels = U(words[7]);
        metadata.ChannelMask = U(words[8]);
        metadata.Format = U(words[9]);
        metadata.TotalSamples = U64(words[10], words[11]);
        metadata.StoredSamples = U(words[12]);
        metadata.FiniteSamples = U64(words[13], words[14]);
        metadata.NonzeroFiniteSamples = U64(words[15], words[16]);
        metadata.NonfiniteSamples = U64(words[17], words[18]);
        metadata.Callbacks = U64(words[19], words[20]);
        metadata.WindowPeakAbs = Float(words[21]);
        metadata.WindowRms = Float(words[22]);
        metadata.StoredPrefixPeakAbs = Float(words[23]);
        if (!Finite(metadata.WindowPeakAbs) || !Finite(metadata.WindowRms) ||
            !Finite(metadata.StoredPrefixPeakAbs)) return false;
        result = metadata;
        return true;
    }

    private static uint U(int value) { return unchecked((uint)value); }
    private static ulong U64(int low, int high)
    { return U(low) | ((ulong)U(high) << 32); }
    private static float Float(int bits)
    { return BitConverter.ToSingle(BitConverter.GetBytes(bits), 0); }
    internal static bool Finite(float value)
    { return !Single.IsNaN(value) && !Single.IsInfinity(value); }
}

internal sealed class PcmWaveformReadbackV1
{
    private const int AkSuccess = 1;
    private const int NativeBusy = -8;
    private const int MaxMetadataQuiescencePolls = 8;
    private readonly IPcmWaveformReadbackApiV1 api;
    private bool attempted;

    internal PcmWaveformReadbackV1(IPcmWaveformReadbackApiV1 api)
    { this.api = api ?? throw new ArgumentNullException("api"); }

    internal string Failure { get; private set; }
    internal PcmWaveformMetadataV1 Metadata { get; private set; }
    internal float[] Samples { get; private set; }

    // The caller passes the exact old-lease facts. False/unknown ownership is a
    // hard refusal, and a failed read is never retried through this client.
    internal bool TryReadOnce(bool unregisterSucceeded, bool callbackKnownAbsent,
        ulong expectedOutputId)
    {
        if (attempted) return Refuse("readback_already_attempted");
        attempted = true;
        if (!unregisterSucceeded || !callbackKnownAbsent)
            return Refuse("capture_callback_not_proven_removed");
        if (expectedOutputId == 0UL || expectedOutputId == UInt64.MaxValue)
            return Refuse("expected_output_identity_invalid");
        if (BitConverter.IsLittleEndian == false)
            return Refuse("little_endian_float32_host_required");

        int[] words = new int[PcmWaveformMetadataV1.WordCount];
        int result = 0;
        try
        {
            for (int poll = 0; poll < MaxMetadataQuiescencePolls; poll++)
            {
                result = api.ReadMetadata(words);
                if (result != NativeBusy) break;
                Thread.Yield(); // bounded readback wait only; no callback/registration retry
            }
        }
        catch (Exception error) { return Refuse("metadata_read_throw:" + error.GetType().Name); }
        if (result != AkSuccess) return Refuse("metadata_read_result_not_success");

        PcmWaveformMetadataV1 metadata;
        if (!PcmWaveformMetadataV1.TryParse(words, out metadata))
            return Refuse("metadata_schema_or_scalar_invalid");
        const uint incompatibleFlags = PcmWaveformMetadataV1.FlagOutputMismatch |
            PcmWaveformMetadataV1.FlagConcurrentCallback | PcmWaveformMetadataV1.FlagFormatChanged |
            PcmWaveformMetadataV1.FlagCounterOverflow;
        if ((metadata.Flags & ~((1u << 9) - 1u)) != 0 ||
            (metadata.Flags & incompatibleFlags) != 0 || !metadata.WaveformValid ||
            (metadata.Flags & PcmWaveformMetadataV1.FlagOutputKnown) == 0 ||
            (metadata.Flags & PcmWaveformMetadataV1.FlagFormatKnown) == 0 ||
            (metadata.Flags & PcmWaveformMetadataV1.FlagChannelMaskKnown) == 0)
            return Refuse("native_waveform_validity_not_proven");
        if (metadata.OutputId != expectedOutputId) return Refuse("callback_output_identity_mismatch");
        if (metadata.Generation == 0UL || metadata.SampleRateHz == 0 ||
            metadata.Channels < 1 || metadata.Channels > 2 ||
            !((metadata.Channels == 1 && metadata.ChannelMask == 4) ||
              (metadata.Channels == 2 && metadata.ChannelMask == 3)) ||
            metadata.Format != PcmWaveformMetadataV1.Float32)
            return Refuse("unsupported_pcm_layout");
        if (metadata.StoredSamples == 0 || metadata.StoredSamples > PcmWaveformMetadataV1.MaxSamples ||
            metadata.StoredSamples % metadata.Channels != 0 ||
            metadata.TotalSamples < metadata.StoredSamples ||
            metadata.Truncated != (metadata.StoredSamples < metadata.TotalSamples) ||
            metadata.FiniteSamples != metadata.TotalSamples || metadata.NonfiniteSamples != 0 ||
            metadata.NonzeroFiniteSamples > metadata.FiniteSamples)
            return Refuse("sample_count_or_finiteness_invalid");

        var samples = new float[checked((int)metadata.StoredSamples)];
        uint copied;
        try { result = api.CopySamples(metadata.Generation, expectedOutputId, samples, out copied); }
        catch (Exception error) { return Refuse("sample_copy_throw:" + error.GetType().Name); }
        if (result != AkSuccess || copied != metadata.StoredSamples)
            return Refuse("sample_copy_result_or_count_invalid");
        for (int i = 0; i < samples.Length; i++)
            if (!PcmWaveformMetadataV1.Finite(samples[i]))
                return Refuse("copied_pcm_contains_nonfinite_value");
        float measuredPrefixPeak = 0f;
        ulong measuredPrefixNonzero = 0;
        for (int i = 0; i < samples.Length; i++)
        {
            measuredPrefixPeak = Math.Max(measuredPrefixPeak, Math.Abs(samples[i]));
            if (samples[i] != 0f) measuredPrefixNonzero++;
        }
        if ((metadata.Truncated && measuredPrefixNonzero > metadata.NonzeroFiniteSamples) ||
            (!metadata.Truncated && measuredPrefixNonzero != metadata.NonzeroFiniteSamples))
            return Refuse("copied_pcm_nonzero_count_mismatch");
        if (Math.Abs(measuredPrefixPeak - metadata.StoredPrefixPeakAbs) > 0.00001f)
            return Refuse("copied_pcm_peak_mismatch");
        if (!metadata.Truncated && Math.Abs(measuredPrefixPeak - metadata.WindowPeakAbs) > 0.00001f)
            return Refuse("complete_window_peak_mismatch");
        if (!metadata.Truncated && Math.Abs((float)PrefixRms(samples) - metadata.WindowRms) > 0.00001f)
            return Refuse("complete_window_rms_mismatch");

        Metadata = metadata;
        Samples = samples;
        return true;
    }

    internal string WriteAppPrivateRaw(string persistentDataPath, string captureId,
        bool engineTermReturned, bool callbackManagerTermReturned, bool postTermDisarmVerified)
    {
        if (!engineTermReturned || !callbackManagerTermReturned || !postTermDisarmVerified)
            throw new InvalidOperationException("Verified original Term and disarm witnesses are required for persistence.");
        if (Metadata == null || Samples == null) throw new InvalidOperationException("No validated waveform is available.");
        Guid parsedCaptureId;
        if (!Guid.TryParseExact(captureId, "N", out parsedCaptureId) ||
            !String.Equals(parsedCaptureId.ToString("N"), captureId, StringComparison.Ordinal))
            throw new ArgumentException("A canonical lowercase capture nonce is required.", "captureId");
        if (String.IsNullOrWhiteSpace(persistentDataPath) || !Path.IsPathRooted(persistentDataPath))
            throw new ArgumentException("A rooted app-private persistent path is required.", "persistentDataPath");
        if (Samples.Length == 0 || Samples.Length > PcmWaveformMetadataV1.MaxSamples ||
            Samples.Length % Metadata.Channels != 0 || !BitConverter.IsLittleEndian)
            throw new InvalidOperationException("Waveform is outside the bounded raw export contract.");
        string root = Path.GetFullPath(persistentDataPath);
        if (!Directory.Exists(root)) throw new IOException("App-private persistent root is unavailable.");
        string directory = Path.Combine(root, "lab-original-audio-pcm");
        if (Directory.Exists(directory) && (File.GetAttributes(directory) & FileAttributes.ReparsePoint) != 0)
            throw new IOException("Refusing an app-private export directory that is a link.");
        Directory.CreateDirectory(directory);
        string fullDirectory = Path.GetFullPath(directory);
        if (!fullDirectory.StartsWith(root.TrimEnd(Path.DirectorySeparatorChar) + Path.DirectorySeparatorChar, StringComparison.Ordinal))
            throw new IOException("PCM export escaped the app-private root.");
        string stem = "capture-v1-" + captureId + "-" + Metadata.Generation.ToString("x16", CultureInfo.InvariantCulture);
        string rawPath = Path.Combine(directory, stem + ".f32le");
        string metadataPath = Path.Combine(directory, stem + ".json");
        byte[] raw = new byte[checked(Samples.Length * sizeof(float))];
        Buffer.BlockCopy(Samples, 0, raw, 0, raw.Length);
        string rawHash;
        using (SHA256 sha = SHA256.Create())
            rawHash = Hex(sha.ComputeHash(raw));
        bool rawCreated = false;
        bool metadataCreated = false;
        try
        {
            using (var stream = new FileStream(rawPath, FileMode.CreateNew, FileAccess.Write, FileShare.None))
            {
                rawCreated = true;
                stream.Write(raw, 0, raw.Length);
                stream.Flush();
            }
            string metadataJson = CreateMetadataJson(Metadata, rawHash, Samples, captureId,
                engineTermReturned, callbackManagerTermReturned, postTermDisarmVerified);
            byte[] json = new UTF8Encoding(false).GetBytes(metadataJson);
            using (var stream = new FileStream(metadataPath, FileMode.CreateNew, FileAccess.Write, FileShare.None))
            {
                metadataCreated = true;
                stream.Write(json, 0, json.Length);
                stream.Flush();
            }
            return rawPath;
        }
        catch
        {
            // Remove only the exact files this method created. A pre-existing
            // path causes CreateNew to fail before rawCreated/metadataCreated.
            if (metadataCreated) TryDelete(metadataPath);
            if (rawCreated) TryDelete(rawPath);
            throw;
        }
    }

    internal void DiscardValidatedSamples()
    {
        Samples = null;
        Metadata = null;
    }

    private bool Refuse(string reason) { Failure = reason; return false; }
    private static void TryDelete(string path) { try { File.Delete(path); } catch { } }
    private static string Hex(byte[] bytes)
    {
        var builder = new StringBuilder(bytes.Length * 2);
        for (int i = 0; i < bytes.Length; i++) builder.Append(bytes[i].ToString("x2", CultureInfo.InvariantCulture));
        return builder.ToString();
    }
    private static string F(float value) { return value.ToString("R", CultureInfo.InvariantCulture); }
    private static double PrefixRms(float[] samples)
    {
        double sum = 0.0;
        for (int i = 0; i < samples.Length; i++) sum += (double)samples[i] * samples[i];
        return Math.Sqrt(sum / samples.Length);
    }
    private static string CreateMetadataJson(PcmWaveformMetadataV1 value, string rawHash, float[] samples,
        string captureId, bool engineTermReturned, bool callbackManagerTermReturned, bool postTermDisarmVerified)
    {
        return "{\n" +
            "  \"schema\": 1,\n" +
            "  \"abi\": \"WwiseDiag_CaptureReadbackV1\",\n" +
            "  \"capture_id\": \"" + captureId + "\",\n" +
            "  \"generation\": \"" + value.Generation.ToString(CultureInfo.InvariantCulture) + "\",\n" +
            "  \"output_id\": \"" + value.OutputId.ToString(CultureInfo.InvariantCulture) + "\",\n" +
            "  \"sample_format\": \"ieee-float32-le\",\n" +
            "  \"sample_rate_hz\": " + value.SampleRateHz.ToString(CultureInfo.InvariantCulture) + ",\n" +
            "  \"channels\": " + value.Channels.ToString(CultureInfo.InvariantCulture) + ",\n" +
            "  \"channel_mask\": " + value.ChannelMask.ToString(CultureInfo.InvariantCulture) + ",\n" +
            "  \"total_samples\": \"" + value.TotalSamples.ToString(CultureInfo.InvariantCulture) + "\",\n" +
            "  \"stored_samples\": " + value.StoredSamples.ToString(CultureInfo.InvariantCulture) + ",\n" +
            "  \"finite_samples\": \"" + value.FiniteSamples.ToString(CultureInfo.InvariantCulture) + "\",\n" +
            "  \"nonzero_finite_samples\": \"" + value.NonzeroFiniteSamples.ToString(CultureInfo.InvariantCulture) + "\",\n" +
            "  \"nonfinite_samples\": \"" + value.NonfiniteSamples.ToString(CultureInfo.InvariantCulture) + "\",\n" +
            "  \"callbacks\": \"" + value.Callbacks.ToString(CultureInfo.InvariantCulture) + "\",\n" +
            "  \"window_peak_abs\": " + F(value.WindowPeakAbs) + ",\n" +
            "  \"window_rms\": " + F(value.WindowRms) + ",\n" +
            "  \"stored_prefix_peak_abs\": " + F(value.StoredPrefixPeakAbs) + ",\n" +
            "  \"stored_prefix_rms\": " + PrefixRms(samples).ToString("R", CultureInfo.InvariantCulture) + ",\n" +
            "  \"truncated\": " + (value.Truncated ? "true" : "false") + ",\n" +
            "  \"original_engine_term_returned\": " + (engineTermReturned ? "true" : "false") + ",\n" +
            "  \"original_callback_manager_term_returned\": " + (callbackManagerTermReturned ? "true" : "false") + ",\n" +
            "  \"post_term_disarm_verified\": " + (postTermDisarmVerified ? "true" : "false") + ",\n" +
            "  \"raw_pcm_persisted\": true,\n" +
            "  \"raw_sha256\": \"" + rawHash + "\",\n" +
            "  \"source_event_attributed\": false,\n" +
            "  \"physical_audibility_claim\": false\n" +
            "}\n";
    }
}

// Owns the one-read / one-persist sequence around the existing callback lease.
// PCM is copied only after successful unregister and the final absent snapshot.
// File I/O is deferred until after both original Term calls have returned.
internal sealed class PcmWaveformCaptureFinalizerV1
{
    private readonly PcmWaveformReadbackV1 reader;
    private Func<string> appPrivateRootProvider;
    private string appPrivateRoot;
    private bool readAttempted;
    private bool persistAttempted;
    private ulong captureGeneration;
    private uint storedSamples;
    private readonly string captureId;

    internal PcmWaveformCaptureFinalizerV1(IPcmWaveformReadbackApiV1 api,
        Func<string> appPrivateRootProvider, string captureId = null)
    {
        reader = new PcmWaveformReadbackV1(api);
        this.appPrivateRootProvider = appPrivateRootProvider;
        this.captureId = captureId ?? Guid.NewGuid().ToString("N");
        Guid parsedCaptureId;
        if (!Guid.TryParseExact(this.captureId, "N", out parsedCaptureId) ||
            !String.Equals(parsedCaptureId.ToString("N"), this.captureId, StringComparison.Ordinal))
            throw new ArgumentException("A canonical lowercase capture nonce is required.", "captureId");
        State = "not_attempted";
    }

    internal string State { get; private set; }
    internal string Failure { get; private set; }
    internal bool RawPersisted { get; private set; }
    internal ulong Generation { get { return captureGeneration; } }
    internal uint StoredSamples { get { return storedSamples; } }
    internal string CaptureId { get { return captureId; } }

    internal bool ReadBeforeOriginalTerm(bool requested, bool unregisterSucceeded,
        bool callbackKnownAbsent, ulong observedOutputId)
    {
        if (readAttempted) return false;
        readAttempted = true;
        if (!requested) { State = "not_requested"; return false; }
        if (!unregisterSucceeded || !callbackKnownAbsent || observedOutputId == 0UL)
            return Refuse("callback_removal_or_output_identity_unproven");
        try
        {
            if (appPrivateRootProvider == null)
                return Refuse("app_private_root_provider_unavailable");
            appPrivateRoot = appPrivateRootProvider();
            if (String.IsNullOrWhiteSpace(appPrivateRoot) || !Path.IsPathRooted(appPrivateRoot) ||
                !Directory.Exists(appPrivateRoot))
                return Refuse("app_private_root_unavailable");
            appPrivateRoot = Path.GetFullPath(appPrivateRoot);
            if (!reader.TryReadOnce(unregisterSucceeded, callbackKnownAbsent, observedOutputId))
                return Refuse(reader.Failure ?? "native_readback_refused");
            captureGeneration = reader.Metadata.Generation;
            storedSamples = reader.Metadata.StoredSamples;
            State = "validated_waiting_for_original_terms";
            return true;
        }
        catch (Exception error)
        {
            return Refuse("readback_prepare_failed:" + error.GetType().Name);
        }
    }

    internal bool PersistAfterOriginalTerms(NativeWwiseMonitorLease lease)
    {
        if (lease == null || !PcmWaveformTermFinalizerV1.HasVerifiedPostTermDisarm(lease))
        {
            if (lease != null && lease.EngineTermReturnedState && lease.CallbackManagerTermReturnedState && !persistAttempted)
            {
                persistAttempted = true;
                Refuse("post_term_disarm_unverified");
            }
            return false;
        }
        if (persistAttempted || State != "validated_waiting_for_original_terms") return false;
        persistAttempted = true;
        try
        {
            reader.WriteAppPrivateRaw(appPrivateRoot, captureId, true, true, true);
            RawPersisted = true;
            State = "written";
            return true;
        }
        catch (Exception error)
        {
            return Refuse("persistence_failed:" + error.GetType().Name);
        }
        finally
        {
            reader.DiscardValidatedSamples();
            appPrivateRoot = null;
            appPrivateRootProvider = null;
        }
    }

    internal void AbandonAfterOriginalTerms(NativeWwiseMonitorLease lease)
    {
        if (lease == null || !lease.EngineTermReturnedState || !lease.CallbackManagerTermReturnedState || persistAttempted) return;
        persistAttempted = true;
        reader.DiscardValidatedSamples();
        appPrivateRoot = null;
        appPrivateRootProvider = null;
        if (State == "validated_waiting_for_original_terms")
            Refuse(PcmWaveformTermFinalizerV1.HasVerifiedPostTermDisarm(lease)
                ? "persistence_abandoned_after_original_terms"
                : "post_term_disarm_unverified");
    }

    internal void RecordUnexpectedReadbackFailure(Exception error)
    {
        if (State == "written" || State == "failed") return;
        Refuse("readback_integration_failed:" + (error == null ? "Unknown" : error.GetType().Name));
    }

    private bool Refuse(string reason)
    {
        Failure = reason;
        State = "failed";
        reader.DiscardValidatedSamples();
        appPrivateRoot = null;
        appPrivateRootProvider = null;
        return false;
    }
}

// Invoked synchronously from the callback-manager Term return observer. The
// observer itself is after the original callback-manager Term returned; a
// failed/missing lease marker or disarm proof reports evidence failure and
// never writes samples. Valid persistence stays before shutdown returns without
// moving file work before either original Term or owning a Unity Update.
internal static class PcmWaveformTermFinalizerV1
{
    internal static bool HasVerifiedPostTermDisarm(NativeWwiseMonitorLease lease)
    {
        return lease != null && lease.EngineTermReturnedState && lease.CallbackManagerTermReturnedState &&
            lease.DisarmAttempted && lease.ArmedState == 3 && !lease.OutcomeUnknown;
    }

    internal static bool RunAfterVerifiedTerms(NativeWwiseMonitorLease lease, Action finalizer,
        Action evidenceFailure)
    {
        if (lease == null || !lease.EngineTermReturnedState) return false;
        if (!lease.CallbackManagerTermReturnedState)
        {
            try { evidenceFailure?.Invoke(); }
            catch { /* waveform evidence cannot escape into the original Term observer */ }
            return false;
        }
        if (!HasVerifiedPostTermDisarm(lease))
        {
            try { evidenceFailure?.Invoke(); }
            catch { /* waveform evidence cannot escape into the original Term observer */ }
            return false;
        }
        if (finalizer != null)
        {
            try { finalizer(); }
            catch { /* waveform evidence cannot escape into the original Term observer */ }
        }
        return true;
    }
}

// The concrete P/Invoke adapter adds two imports. Keep these separate from the
// current 11 imports and preserve all existing selectors/snapshots.
internal sealed class NativePcmWaveformReadbackApiV1 : IPcmWaveformReadbackApiV1
{
    private const string Library = "AkSoundEngine";
    [DllImport(Library, EntryPoint = "WwiseDiag_CaptureReadbackV1")]
    private static extern int ReadMetadataNative(IntPtr words, uint capacityWords);
    [DllImport(Library, EntryPoint = "WwiseDiag_CaptureCopyV1")]
    private static extern int CopySamplesNative(ulong generation, ulong expectedOutputId,
        IntPtr destination, uint capacitySamples, out uint copiedSamples);

    public int ReadMetadata(int[] words)
    {
        if (words == null || words.Length != PcmWaveformMetadataV1.WordCount) return -1;
        IntPtr memory = Marshal.AllocHGlobal(words.Length * sizeof(int));
        try
        {
            for (int i = 0; i < words.Length; i++) Marshal.WriteInt32(memory, i * sizeof(int), 0);
            int result = ReadMetadataNative(memory, (uint)words.Length);
            for (int i = 0; i < words.Length; i++) words[i] = Marshal.ReadInt32(memory, i * sizeof(int));
            return result;
        }
        finally { Marshal.FreeHGlobal(memory); }
    }

    public int CopySamples(ulong generation, ulong expectedOutputId, float[] destination, out uint copiedSamples)
    {
        copiedSamples = 0;
        if (destination == null || destination.Length > PcmWaveformMetadataV1.MaxSamples) return -1;
        GCHandle pinned = GCHandle.Alloc(destination, GCHandleType.Pinned);
        try
        {
            return CopySamplesNative(generation, expectedOutputId, pinned.AddrOfPinnedObject(),
                (uint)destination.Length, out copiedSamples);
        }
        finally { pinned.Free(); }
    }
}
