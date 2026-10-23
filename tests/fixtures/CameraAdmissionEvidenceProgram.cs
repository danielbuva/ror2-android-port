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

    private static void SetAllFloatFields(AndroidNativeAudioCameraAdmissionScalars evidence)
    {
        var floatFields = typeof(AndroidNativeAudioCameraAdmissionScalars).GetFields(BindingFlags.Instance | BindingFlags.Public);
        int ordinal = 0;
        foreach (FieldInfo field in floatFields)
        {
            if (field.FieldType != typeof(float))
                continue;
            string validName = field.Name + "Valid";
            FieldInfo valid = typeof(AndroidNativeAudioCameraAdmissionScalars).GetField(validName);
            Need(valid != null, "each float has an explicit validity field: " + field.Name);
            float invalidValue;
            switch (ordinal++ % 3)
            {
                case 0: invalidValue = float.NaN; break;
                case 1: invalidValue = float.PositiveInfinity; break;
                default: invalidValue = float.NegativeInfinity; break;
            }
            field.SetValue(evidence, invalidValue);
            valid.SetValue(evidence, true);
        }
    }

    private static void PopulateDistinctScalars(AndroidNativeAudioCameraAdmissionEvidence evidence)
    {
        int ordinal = 0;
        foreach (FieldInfo field in typeof(AndroidNativeAudioCameraAdmissionScalars).GetFields(BindingFlags.Instance | BindingFlags.Public))
        {
            int value = ordinal++;
            if (field.FieldType == typeof(bool))
                field.SetValue(evidence, field.Name.EndsWith("Valid", StringComparison.Ordinal) || value % 2 == 0);
            else if (field.FieldType == typeof(int))
                field.SetValue(evidence, 1000 + value);
            else if (field.FieldType == typeof(float))
            {
                field.SetValue(evidence, value + 0.25f);
                FieldInfo valid = typeof(AndroidNativeAudioCameraAdmissionScalars).GetField(field.Name + "Valid");
                if (valid != null)
                    valid.SetValue(evidence, true);
            }
            else if (field.FieldType == typeof(string))
                field.SetValue(evidence, "value-" + field.Name + "-" + value);
            else
                throw new Exception("unexpected non-scalar schema field: " + field.Name);
        }
    }

    private static void CheckScalarEquality(AndroidNativeAudioCameraAdmissionScalars expected,
        AndroidNativeAudioCameraAdmissionScalars actual, string name)
    {
        foreach (FieldInfo field in typeof(AndroidNativeAudioCameraAdmissionScalars).GetFields(BindingFlags.Instance | BindingFlags.Public))
            Need(object.Equals(field.GetValue(expected), field.GetValue(actual)), name + " copied field " + field.Name);
    }

    private static void CheckFiniteZeroProjection(AndroidNativeAudioCameraAdmissionScalars evidence, string sampleName)
    {
        foreach (FieldInfo field in typeof(AndroidNativeAudioCameraAdmissionScalars).GetFields(BindingFlags.Instance | BindingFlags.Public))
        {
            if (field.FieldType != typeof(float))
                continue;
            float value = (float)field.GetValue(evidence);
            FieldInfo valid = typeof(AndroidNativeAudioCameraAdmissionScalars).GetField(field.Name + "Valid");
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
        evidence.firstAdmissionSample = evidence.CopyAsFirstSample();

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
        nonfinite.firstAdmissionSample = nonfinite.CopyAsFirstSample();
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
        // The top-level evidence keeps its historical full name and inherits the same
        // 141 scalar public fields; only its first-sample edge has a different DTO.
        var scalarFields = typeof(AndroidNativeAudioCameraAdmissionScalars).GetFields(BindingFlags.Instance | BindingFlags.Public);
        Need(typeof(AndroidNativeAudioCameraAdmissionScalars).IsSerializable &&
            typeof(AndroidNativeAudioCameraAdmissionEvidence).IsSerializable &&
            typeof(AndroidNativeAudioCameraAdmissionSample).IsSerializable,
            "all DTO layers retain the serializable attribute");
        Need(scalarFields.Length == 141, "all original 141 scalar fields live in the shared serializable base");
        Need(typeof(AndroidNativeAudioCameraAdmissionEvidence).FullName == "AndroidNativeAudioCameraAdmissionEvidence",
            "top-level evidence full type name remains stable");
        Need(typeof(AndroidNativeAudioCameraAdmissionEvidence).GetField("firstAdmissionSample").FieldType ==
            typeof(AndroidNativeAudioCameraAdmissionSample), "first sample has the nonrecursive concrete DTO type");
        Need(typeof(AndroidNativeAudioCameraAdmissionSample).GetField("firstAdmissionSample") == null,
            "sample schema cannot contain a second nested sample");
        Need(typeof(AndroidNativeAudioCameraAdmissionSample).GetFields(BindingFlags.Instance | BindingFlags.Public).Length == 141,
            "first sample inherits every original public scalar field");

        var firstIndependent = new AndroidNativeAudioCameraAdmissionEvidence();
        firstIndependent.admissionSampleKnown = false; // unknown must remain unknown, not projected to observed false
        firstIndependent.admissionDecision = "first-observation";
        firstIndependent.admissionSampleSequence = 1;
        firstIndependent.firstAdmissionSample = firstIndependent.CopyAsFirstSample();
        var secondIndependent = new AndroidNativeAudioCameraAdmissionEvidence();
        secondIndependent.admissionDecision = "second-observation";
        secondIndependent.admissionSampleSequence = 2;
        secondIndependent.firstAdmissionSample = secondIndependent.CopyAsFirstSample();
        Need(firstIndependent.firstAdmissionSample.admissionDecision == "first-observation" &&
            secondIndependent.firstAdmissionSample.admissionDecision == "second-observation",
            "two independent one-sample reports retain distinct first/latest values");
        Need(!firstIndependent.firstAdmissionSample.admissionSampleKnown,
            "unknown scalar evidence remains unknown through first-sample copy");
        firstIndependent.admissionDecision = "mutated-latest";
        Need(firstIndependent.firstAdmissionSample.admissionDecision == "first-observation",
            "first sample is independent of later outer scalar mutation");

        var fullyPopulated = new AndroidNativeAudioCameraAdmissionEvidence();
        PopulateDistinctScalars(fullyPopulated);
        var firstScalarCopy = fullyPopulated.CopyAsFirstSample();
        CheckScalarEquality(fullyPopulated, firstScalarCopy, "first-sample copy");
        var evidenceCopy = fullyPopulated.Copy();
        CheckScalarEquality(fullyPopulated, evidenceCopy, "outer evidence copy");
        Need(evidenceCopy.firstAdmissionSample == null, "outer copy preserves absent nested sample as absent");

        var zero = new AndroidNativeAudioCameraAdmissionEvidence();
        var one = new AndroidNativeAudioCameraAdmissionEvidence { admissionDecision = "latest-one" };
        one.firstAdmissionSample = one.CopyAsFirstSample();
        var two = new AndroidNativeAudioCameraAdmissionEvidence { admissionDecision = "first-two" };
        two.firstAdmissionSample = two.CopyAsFirstSample();
        two.admissionDecision = "latest-two";
        Need(zero.firstAdmissionSample == null && one.firstAdmissionSample != null &&
            one.firstAdmissionSample.admissionDecision == "latest-one" &&
            two.firstAdmissionSample.admissionDecision == "first-two" && two.admissionDecision == "latest-two",
            "zero, one, and two distinct outer reports model a bounded one-level sample schema");
        var twoCopy = two.Copy();
        Need(twoCopy.firstAdmissionSample != null &&
            twoCopy.firstAdmissionSample.admissionDecision == "first-two" &&
            twoCopy.admissionDecision == "latest-two" &&
            !ReferenceEquals(twoCopy.firstAdmissionSample, two.firstAdmissionSample),
            "outer copy preserves and independently copies the bounded first sample");

        Console.WriteLine("Nonrecursive camera admission DTO contract checks passed: " + checks);
        return 0;
    }
}
