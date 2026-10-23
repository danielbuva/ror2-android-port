using System;
using System.Collections;
using System.Security.Cryptography;
using System.Text;
using UnityEngine;

// The generated request pin is default-off. A true request is admitted only
// when all accepted-source and generated-stage identities match this candidate.
internal static class GameAudioOriginalAcceptedRequestProvider
{
    private const string AcceptedInputId = "6af7ed94619fe1b4346974b4486afa03a8d1625a7820e92da0ff74d57208fe88";
    private const string AcceptedGameAssemblySha256 = "a5f7d83c7e6872fdd6099fdc299adb7d4fa03cbf465e526d6f5efcc35c2c281d";
    private const string AcceptedComposedGameSha256 = "594282cfa617ac58eda6965e0a48e6958438f345cbb98bfb7cb49b9130efad1d";
    private const string AcceptedRawApiSha256 = "564b74ec232e81af8fa4b65c17537a4d05890d9181281eab0bc28bd441a3a781";
    private const string AcceptedAdaptedApiSha256 = "2bd973178c99bfcb4d20510e2d1eac7efa9dd6d698237f2edfa486171bc2f272";
    private const string AcceptedObservedApiSha256 = "a2914ace8e2a7338010f8e9a9515911d68489bf0ad467bc7f73f4de293a19fe9";
    private const string AcceptedInstrumentedApiSha256 = "1cedc89f59f44f91deea8b07fcdf289e5fec9448ba87d4d68519d6658bba942b";
    private const string AcceptedNativeLibrarySha256 = "9075b5a4d3718a209eb244760d2b251a59ef2f5c486a2d2fc0e83b90240cbba3";
    private const string AcceptedAdaptedInitSha256 = "618d1c5d534af10fc4cc30a1bacd193bf6871dab3e63992ebedd92a92576fb90";

    internal static GameAudioOriginalRequest Create()
    {
        if (!GameAudioOriginalGeneratedRequestPin.Requested) return null;
        string refusal = ValidateGeneratedPins();
        if (refusal != null)
            return new GameAudioOriginalRequest(true, RefusalNames(),
                new RefusedPreparation(refusal));

        var monitor = new NativeWwiseMonitorLease(new NativeWwiseDiagPInvokeApi());
        var native = new GameAudioOriginalAndroidNativeBootstrap(monitor);
        bool captureRequested = GameAudioOriginalGeneratedRequestPin.PassivePcmCaptureRequested;
        bool musicOutputRequested = GameAudioOriginalGeneratedRequestPin.PassivePcmCaptureMusicOutputRequested;
        bool afterAuthoritySkill = GameAudioOriginalGeneratedRequestPin.PassivePcmCaptureAfterAuthoritySkillRequested;
        if (afterAuthoritySkill && (!captureRequested || musicOutputRequested))
            return new GameAudioOriginalRequest(true, RefusalNames(),
                new RefusedPreparation("skill_deferred_capture_requires_main_output"));
        if (musicOutputRequested && !captureRequested)
            return new GameAudioOriginalRequest(true, RefusalNames(),
                new RefusedPreparation("music_output_capture_without_passive_capture_request"));
        IGameAudioOriginalPassivePcmCapture passiveCapture = native.CreatePassivePcmCaptureOwner(
            captureRequested, musicOutputRequested);
        return new GameAudioOriginalRequest(true, GameAudioOriginalGeneratedStagePin.BankNames,
            new GameAudioOriginalPreparation(Application.streamingAssetsPath,
                GameAudioOriginalGeneratedStagePin.BankNames,
                GameAudioOriginalGeneratedStagePin.ReceiptSha256, native),
            captureRequested, passiveCapture, musicOutputRequested, afterAuthoritySkill);
    }

    internal static IGameAudioOriginalStartupPreparation Refused(string reason) => new RefusedPreparation(reason);

    private static string[] RefusalNames()
    {
        var names = new string[153];
        for (int i = 0; i < names.Length; i++) names[i] = "refused_audio_request_" + i.ToString("000");
        return names;
    }

    private static string ValidateGeneratedPins()
    {
        if (!ValidRequestId(GameAudioOriginalGeneratedRequestPin.RequestId)) return "audio_request_id_invalid";
        if (!IsHash(GameAudioOriginalGeneratedRequestPin.RequestReceiptSha256)) return "audio_request_receipt_pin_invalid";
        if (!IsHash(GameAudioOriginalGeneratedRequestPin.BuildInputContractSha256)) return "audio_build_input_contract_pin_invalid";
        if (!Equal(GameAudioOriginalGeneratedRequestPin.StageReceiptSha256, GameAudioOriginalGeneratedStagePin.ReceiptSha256))
            return "audio_stage_receipt_request_pin_mismatch";
        if (!Equal(GameAudioOriginalGeneratedRequestPin.AdaptedInitSha256, AcceptedAdaptedInitSha256))
            return "audio_adapted_init_pin_mismatch";
        if (!String.Equals(GameAudioOriginalGeneratedStagePin.AcceptedInputId, AcceptedInputId, StringComparison.Ordinal))
            return "audio_stage_pin_input_mismatch";
        if (!IsHash(GameAudioOriginalGeneratedStagePin.ReceiptSha256) || GameAudioOriginalGeneratedStagePin.BankNames == null ||
            GameAudioOriginalGeneratedStagePin.BankNames.Length != 153)
            return "audio_stage_pin_missing_or_invalid";
        var names = new System.Collections.Generic.HashSet<string>(StringComparer.Ordinal);
        foreach (string name in GameAudioOriginalGeneratedStagePin.BankNames)
            if (String.IsNullOrEmpty(name) || name.IndexOfAny(new[] { '/', '\\', ':' }) >= 0 || !names.Add(name))
                return "audio_stage_bank_names_invalid";
        if (!Equal(GameAudioOriginalGeneratedRequestPin.GameAssemblySha256, AcceptedGameAssemblySha256)) return "audio_game_source_pin_mismatch";
        if (!Equal(GameAudioOriginalGeneratedRequestPin.ComposedGameSha256, AcceptedComposedGameSha256)) return "audio_composed_game_pin_mismatch";
        if (!Equal(GameAudioOriginalGeneratedRequestPin.RawApiSha256, AcceptedRawApiSha256)) return "audio_raw_api_pin_mismatch";
        if (!Equal(GameAudioOriginalGeneratedRequestPin.AdaptedApiSha256, AcceptedAdaptedApiSha256)) return "audio_adapted_api_pin_mismatch";
        if (!Equal(GameAudioOriginalGeneratedRequestPin.ObservedApiSha256, AcceptedObservedApiSha256)) return "audio_observer_api_pin_mismatch";
        if (!Equal(GameAudioOriginalGeneratedRequestPin.InstrumentedApiSha256, AcceptedInstrumentedApiSha256)) return "audio_instrumented_api_pin_mismatch";
        if (!Equal(GameAudioOriginalGeneratedRequestPin.NativeLibrarySha256, AcceptedNativeLibrarySha256)) return "audio_native_library_pin_mismatch";
        return null;
    }

    private static bool ValidRequestId(string value)
    {
        Guid parsed;
        return Guid.TryParseExact(value, "N", out parsed);
    }

    private static bool IsHash(string value)
    {
        if (String.IsNullOrEmpty(value) || value.Length != 64) return false;
        foreach (char c in value) if (!Uri.IsHexDigit(c)) return false;
        return true;
    }

    private static bool Equal(string left, string right) => String.Equals(left, right, StringComparison.OrdinalIgnoreCase);

    private sealed class RefusedPreparation : IGameAudioOriginalStartupPreparation
    {
        private readonly string refusal;
        internal RefusedPreparation(string reason) { refusal = reason; }
        public bool Prepared => false;
        public string Refusal => refusal;
        public IEnumerator PrepareBeforeExistingManagerInit() { yield break; }
        public void ArmNativeMonitorBeforeInit() { throw new InvalidOperationException(refusal); }
        public void AbandonBeforeOriginalInit() { }
        public void PostExactControlMarker() { throw new InvalidOperationException(refusal); }
        public bool NativeExactControlObserved() => false;
        public bool NativeControlObservationFailed => true;
        public void ObserveEngineTermReturned() { }
        public void ObserveCallbackManagerTermReturned() { }
    }
}
