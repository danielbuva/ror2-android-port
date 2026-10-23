using System;
using System.Collections.Generic;
using System.Reflection;

internal static class CameraAdmissionEvidenceProgram
{
    private static int checks;

    private static void Need(bool condition, string name)
    {
        checks++;
        if (!condition)
            throw new Exception(name);
    }

    private static void SetAllFloatFields(AndroidNativeAudioCameraAdmissionEvidence evidence)
    {
        var floatFields = typeof(AndroidNativeAudioCameraAdmissionEvidence).GetFields(BindingFlags.Instance | BindingFlags.Public);
        int ordinal = 0;
        foreach (FieldInfo field in floatFields)
        {
            if (field.FieldType != typeof(float))
                continue;
            string validName = field.Name + "Valid";
            FieldInfo valid = typeof(AndroidNativeAudioCameraAdmissionEvidence).GetField(validName);
            Need(valid != null, "each float has an explicit validity field: " + field.Name);
            field.SetValue(evidence, ordinal++ % 3 == 0 ? float.NaN : ordinal % 3 == 1 ? float.PositiveInfinity : float.NegativeInfinity);
            valid.SetValue(evidence, true);
        }
    }

    private static void CheckFiniteZeroProjection(AndroidNativeAudioCameraAdmissionEvidence evidence, string sampleName)
    {
        foreach (FieldInfo field in typeof(AndroidNativeAudioCameraAdmissionEvidence).GetFields(BindingFlags.Instance | BindingFlags.Public))
        {
            if (field.FieldType != typeof(float))
                continue;
            float value = (float)field.GetValue(evidence);
            FieldInfo valid = typeof(AndroidNativeAudioCameraAdmissionEvidence).GetField(field.Name + "Valid");
            Need(!float.IsNaN(value) && !float.IsInfinity(value), sampleName + " finite float " + field.Name);
            Need(value == 0f && valid != null && !(bool)valid.GetValue(evidence),
                sampleName + " invalid float projects to zero with validity false: " + field.Name);
        }
    }

    public static int Main()
    {
        var evidence = new AndroidNativeAudioCameraAdmissionEvidence();
        evidence.RecordOriginalContextResult(false, false);
        Need(!evidence.originalContextProbeAvailable && !evidence.originalContextResultKnown && !evidence.originalContextReady,
            "unavailable original-context probe remains unknown");
        evidence.RecordOriginalContextResult(true, false);
        Need(evidence.originalContextProbeAvailable && evidence.originalContextResultKnown && !evidence.originalContextReady,
            "available probe returning false is observed false");

        evidence.RecordStartWindowSample(10f, true, true, true, false, true, false,
            AndroidNativeAudioCameraStartStep.WaitForOriginalStart, 9f, 20f);
        evidence.RecordStartWindowSample(10.5f, true, true, false, true, true, false,
            AndroidNativeAudioCameraStartStep.Continue, 9f, 20f);
        Need(evidence.startWindowSampleCount == 2 && evidence.startWindowFirstModeIsNull &&
            evidence.startWindowFirstWaitRealtimeValid && evidence.startWindowFirstWaitRealtime == 10f &&
            evidence.startWindowFirstPlayerBasicRealtimeValid && evidence.startWindowFirstPlayerBasicRealtime == 10.5f,
            "first wait and PlayerBasic transition retain exact observed times");

        evidence.BeginAdmissionObservation(1, 12f, 9f, 20f);
        evidence.RecordDeltaTime(0.016f, true);
        evidence.RecordMusicSnapshot(true, true, true, true, true, false, false, true,
            true, true, true, true, 11.5f, 0.5f, true);
        evidence.musicFreshKnown = evidence.musicFresh = evidence.musicTargetObserved = true;
        evidence.firstAdmissionSample = evidence.Copy();

        // A new actual admission evaluation begins, then an early refusal can
        // return before delta, music, and inner-gate fields are recorded.
        evidence.BeginAdmissionObservation(2, 12.25f, 9f, 20f);
        var early = evidence.Copy();
        Need(early.admissionSampleKnown && early.admissionSampleSequence == 2 &&
            !early.deltaTimeKnown && !early.deltaTimeValid && early.deltaTime == 0f,
            "early return cannot carry prior delta validity");
        Need(!early.musicSnapshotKnown && !early.musicSnapshotRefreshObserved && !early.musicRequested &&
            !early.musicSourceAudioReady && !early.musicEngineInitialized &&
            !early.musicObservationRealtimeValid && early.musicObservationRealtime == 0f &&
            !early.musicObservationAgeSecondsValid && early.musicObservationAgeSeconds == 0f &&
            !early.musicFreshKnown && !early.musicFresh && !early.musicTargetObserved,
            "early return leaves omitted music operands unknown rather than stale");
        Need(early.firstAdmissionSample != null && early.firstAdmissionSample.musicSnapshotKnown &&
            early.firstAdmissionSample.musicSnapshotRefreshObserved &&
            early.firstAdmissionSample.musicObservationRealtimeValid &&
            early.firstAdmissionSample.musicObservationRealtime == 11.5f,
            "the immutable first admission snapshot survives the next early return");

        // A later evaluation can reuse the existing 0.5-second source snapshot
        // without another source capture; the refresh flag makes that explicit.
        evidence.RecordMusicSnapshot(true, false, true, true, true, false, false, true,
            true, true, true, true, 11.5f, 0.75f, true);
        Need(evidence.musicSnapshotKnown && !evidence.musicSnapshotRefreshObserved && evidence.musicRequested &&
            evidence.musicObservationRealtimeValid && evidence.musicObservationRealtime == 11.5f &&
            evidence.musicObservationAgeSecondsValid && evidence.musicObservationAgeSeconds == 0.75f,
            "non-refresh sample retains cached source timestamp and reports its current age");

        var nonfinite = new AndroidNativeAudioCameraAdmissionEvidence();
        SetAllFloatFields(nonfinite);
        nonfinite.firstAdmissionSample = new AndroidNativeAudioCameraAdmissionEvidence();
        SetAllFloatFields(nonfinite.firstAdmissionSample);
        var safeCopy = nonfinite.Copy();
        CheckFiniteZeroProjection(safeCopy, "outer sample");
        CheckFiniteZeroProjection(safeCopy.firstAdmissionSample, "nested first sample");

        Need(AndroidNativeAudioCameraContextContract.EvaluateObservation(
            true, false, false, false, false) == AndroidNativeAudioContextStep.Wait,
            "evidence recording does not bypass the incomplete-context wait");
        Need(AndroidNativeAudioCameraContextContract.EvaluateObservation(
            true, false, false, false, true) == AndroidNativeAudioContextStep.Retire,
            "evidence recording does not bypass the expired-context refusal");
        Console.WriteLine("R31 camera admission DTO contract checks passed: " + checks);
        return 0;
    }
}
