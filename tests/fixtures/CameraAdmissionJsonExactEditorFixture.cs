using System;
using System.Collections.Generic;
using System.IO;
using System.Reflection;
using UnityEngine;

// Compile this fixture as an Editor script in the existing authored project.
// Direct type references are deliberate; no authored lookalike is loaded dynamically.
[Serializable]
public sealed class AdmissionProductionFixtureResult
{
    public string schema;
    public bool fixtureInvoked, actualProductionAssembly, passed, positiveTopLevelSentinel;
    public bool zeroSampleUnobserved, oneSampleRoundTrips, firstLatestDistinct, rawJsonContainsSample;
    public bool firstCopyIndependentAndBounded, scalarOnlyEvidenceSchema, serializationWarningsAbsent;
    public string runtimeAssemblySimpleName, runtimeAssemblyMvid, runtimeAssemblyFileName;
    public bool runtimeAssemblyInScriptAssemblies;
    public string reportTypeIdentity, worldTypeIdentity, evidenceTypeIdentity;
    public string[] serializationMessages;
    public string zeroJson, oneJson, twoJson;
}

public static class AdmissionJsonProductionProjectFixture
{
    const int MaxIndividualJsonChars = 262144;
    const int MaxCombinedJsonChars = 524288;
    const int MaxWarnings = 16;
    const int MaxWarningChars = 512;

    public static string Run()
    {
        var messages = new List<string>();
        Application.LogCallback callback = (condition, stackTrace, type) =>
        {
            if (type != LogType.Warning && type != LogType.Error &&
                type != LogType.Exception && type != LogType.Assert) return;
            if (messages.Count < MaxWarnings)
            {
                string message = type + ": " + (condition ?? "<null>");
                messages.Add(message.Length <= MaxWarningChars ? message : message.Substring(0, MaxWarningChars));
            }
        };

        string zero = "", one = "", two = "";
        bool zeroOkay = false, oneOkay = false, twoOkay = false, independent = false, rawSample = false;
        bool scalarSchema = HasScalarSchema();
        Application.logMessageReceived += callback;
        try
        {
            Assembly reportAssembly = typeof(PortSession.SessionReport).Assembly;
            Assembly worldAssembly = typeof(PortSession.WorldReport).Assembly;
            Assembly evidenceAssembly = typeof(AndroidNativeAudioCameraAdmissionEvidence).Assembly;
            Assembly scalarsAssembly = typeof(AndroidNativeAudioCameraAdmissionScalars).Assembly;
            Assembly sampleAssembly = typeof(AndroidNativeAudioCameraAdmissionSample).Assembly;
            string runtimeAssemblyLocation = reportAssembly.Location ?? "";
            bool assemblyInScriptAssemblies = !string.IsNullOrEmpty(runtimeAssemblyLocation) &&
                string.Equals(Path.GetFileName(runtimeAssemblyLocation), "Assembly-CSharp.dll", StringComparison.Ordinal) &&
                runtimeAssemblyLocation.Replace('\\', '/').Contains("/Library/ScriptAssemblies/");
            bool actualAssembly = reportAssembly == worldAssembly && reportAssembly == evidenceAssembly &&
                reportAssembly == scalarsAssembly && reportAssembly == sampleAssembly &&
                reportAssembly != typeof(AdmissionJsonProductionProjectFixture).Assembly &&
                string.Equals(reportAssembly.GetName().Name, "Assembly-CSharp", StringComparison.Ordinal) &&
                assemblyInScriptAssemblies && reportAssembly.ManifestModule.ModuleVersionId != Guid.Empty;

            var zeroReport = MakeReport(null);
            zero = JsonUtility.ToJson(zeroReport);
            PortSession.SessionReport zeroRead = JsonUtility.FromJson<PortSession.SessionReport>(zero);
            bool topSentinel = HasSentinels(zeroRead);
            zeroOkay = topSentinel && IsUnobserved(zeroRead.world.originalAudioCameraContextLastAdmissionEvidence);

            var oneValue = MakeEvidence(1, 11.25f, "one-sample");
            oneValue.firstAdmissionSample = oneValue.CopyAsFirstSample();
            one = JsonUtility.ToJson(MakeReport(oneValue.Copy()));
            PortSession.SessionReport oneRead = JsonUtility.FromJson<PortSession.SessionReport>(one);
            AndroidNativeAudioCameraAdmissionEvidence oneEvidence = ReadEvidence(oneRead);
            oneOkay = HasSentinels(oneRead) && HasValue(oneEvidence, 1, 11.25f, "one-sample") &&
                HasValue(oneEvidence == null ? null : oneEvidence.firstAdmissionSample, 1, 11.25f, "one-sample");
            rawSample = ContainsSampleValue(one, "one-sample", 11.25f) &&
                ContainsRawValue(one, "one-sample", 11.25f);

            var latest = MakeEvidence(1, 21.25f, "first-sample");
            latest.firstAdmissionSample = latest.CopyAsFirstSample();
            AndroidNativeAudioCameraAdmissionSample originalFirst = latest.firstAdmissionSample;
            latest.BeginAdmissionObservation(2, 22.5f, 20f, 40f);
            // BeginAdmissionObservation intentionally clears these per-observation flags.
            // Re-establish them as a real evaluated sample before the fixture accepts it.
            latest.admissionDecision = "latest-sample";
            latest.admissionEvaluationObserved = true;
            latest.admissionInputsKnown = true;
            latest.originalContextProbeAvailable = true;
            latest.originalContextResultKnown = true;
            latest.originalContextReady = false;
            latest.RecordDeltaTime(0.025f, true);
            if (!HasValue(latest, 2, 22.5f, "latest-sample") ||
                !HasValue(latest.firstAdmissionSample, 1, 21.25f, "first-sample"))
                throw new InvalidOperationException("latest/first fixture setup did not satisfy evidence contract before serialization");
            var productionCopy = latest.Copy();
            independent = !ReferenceEquals(productionCopy.firstAdmissionSample, latest.firstAdmissionSample) &&
                ReferenceEquals(originalFirst, latest.firstAdmissionSample) &&
                productionCopy.firstAdmissionSample != null;
            two = JsonUtility.ToJson(MakeReport(productionCopy));
            PortSession.SessionReport twoRead = JsonUtility.FromJson<PortSession.SessionReport>(two);
            AndroidNativeAudioCameraAdmissionEvidence twoEvidence = ReadEvidence(twoRead);
            AndroidNativeAudioCameraAdmissionSample first = twoEvidence == null ? null : twoEvidence.firstAdmissionSample;
            twoOkay = HasSentinels(twoRead) && HasValue(twoEvidence, 2, 22.5f, "latest-sample") &&
                HasValue(first, 1, 21.25f, "first-sample") &&
                twoEvidence.originalContextResultKnown && !twoEvidence.originalContextReady &&
                twoEvidence.deltaTimeValid && twoEvidence.deltaTime == 0.025f;
            rawSample = rawSample && ContainsSampleValue(two, "first-sample", 21.25f) &&
                ContainsRawValue(two, "latest-sample", 22.5f);

            if (zero.Length == 0 || one.Length == 0 || two.Length == 0 ||
                zero.Length > MaxIndividualJsonChars || one.Length > MaxIndividualJsonChars ||
                two.Length > MaxIndividualJsonChars || zero.Length + one.Length + two.Length > MaxCombinedJsonChars)
                throw new InvalidOperationException("production JSON missing or exceeds fixture bound");

            bool passed = actualAssembly && zeroOkay && oneOkay && twoOkay && independent && rawSample && scalarSchema && messages.Count == 0;
            return JsonUtility.ToJson(new AdmissionProductionFixtureResult
            {
                schema = "first-admission-production-json-r4",
                fixtureInvoked = true,
                actualProductionAssembly = actualAssembly,
                passed = passed,
                positiveTopLevelSentinel = topSentinel,
                zeroSampleUnobserved = zeroOkay,
                oneSampleRoundTrips = oneOkay,
                firstLatestDistinct = twoOkay,
                rawJsonContainsSample = rawSample,
                firstCopyIndependentAndBounded = independent,
                scalarOnlyEvidenceSchema = scalarSchema,
                serializationWarningsAbsent = messages.Count == 0,
                runtimeAssemblySimpleName = reportAssembly.GetName().Name,
                runtimeAssemblyMvid = reportAssembly.ManifestModule.ModuleVersionId.ToString("D"),
                runtimeAssemblyFileName = Path.GetFileName(runtimeAssemblyLocation),
                runtimeAssemblyInScriptAssemblies = assemblyInScriptAssemblies,
                reportTypeIdentity = typeof(PortSession.SessionReport).AssemblyQualifiedName,
                worldTypeIdentity = typeof(PortSession.WorldReport).AssemblyQualifiedName,
                evidenceTypeIdentity = typeof(AndroidNativeAudioCameraAdmissionEvidence).AssemblyQualifiedName,
                serializationMessages = messages.ToArray(),
                zeroJson = zero,
                oneJson = one,
                twoJson = two
            });
        }
        catch (Exception e)
        {
            if (messages.Count < MaxWarnings)
            {
                string message = "fixture exception: " + e.GetType().FullName + ": " + e.Message;
                messages.Add(message.Length <= MaxWarningChars ? message : message.Substring(0, MaxWarningChars));
            }
            return JsonUtility.ToJson(new AdmissionProductionFixtureResult
            {
                schema = "first-admission-production-json-r4",
                fixtureInvoked = true,
                passed = false,
                zeroSampleUnobserved = zeroOkay,
                oneSampleRoundTrips = oneOkay,
                firstLatestDistinct = twoOkay,
                rawJsonContainsSample = rawSample,
                firstCopyIndependentAndBounded = independent,
                scalarOnlyEvidenceSchema = scalarSchema,
                serializationWarningsAbsent = false,
                serializationMessages = messages.ToArray(),
                zeroJson = zero,
                oneJson = one,
                twoJson = two
            });
        }
        finally
        {
            Application.logMessageReceived -= callback;
        }
    }

    static PortSession.SessionReport MakeReport(AndroidNativeAudioCameraAdmissionEvidence evidence)
    {
        return new PortSession.SessionReport
        {
            combatPerformanceFocus = true,
            world = new PortSession.WorldReport
            {
                originalAudioCameraContextState = "first-admission-fixture-world-sentinel",
                originalAudioCameraContextLastAdmissionEvidence = evidence
            }
        };
    }

    static AndroidNativeAudioCameraAdmissionEvidence MakeEvidence(int sequence, float realtime, string decision)
    {
        var value = new AndroidNativeAudioCameraAdmissionEvidence();
        value.BeginAdmissionObservation(sequence, realtime, realtime - 2f, realtime + 10f);
        value.admissionDecision = decision;
        value.admissionEvaluationObserved = true;
        value.admissionInputsKnown = true;
        value.originalContextProbeAvailable = true;
        value.originalContextResultKnown = true;
        value.originalContextReady = sequence == 1;
        value.RecordDeltaTime(0.016f, true);
        return value;
    }

    static AndroidNativeAudioCameraAdmissionEvidence ReadEvidence(PortSession.SessionReport report)
    {
        return report == null || report.world == null ? null : report.world.originalAudioCameraContextLastAdmissionEvidence;
    }

    static bool HasSentinels(PortSession.SessionReport report)
    {
        return report != null && report.combatPerformanceFocus &&
            report.world != null && report.world.originalAudioCameraContextState == "first-admission-fixture-world-sentinel";
    }

    static bool IsUnobserved(AndroidNativeAudioCameraAdmissionEvidence evidence)
    {
        return evidence == null || (!evidence.admissionSampleKnown && evidence.admissionSampleSequence == 0 &&
            !evidence.admissionEvaluationObserved && string.IsNullOrEmpty(evidence.admissionDecision) &&
            (evidence.firstAdmissionSample == null || IsUnobserved(evidence.firstAdmissionSample)));
    }

    static bool IsUnobserved(AndroidNativeAudioCameraAdmissionSample sample)
    {
        return sample == null || (!sample.admissionSampleKnown && sample.admissionSampleSequence == 0 &&
            !sample.admissionEvaluationObserved && string.IsNullOrEmpty(sample.admissionDecision));
    }

    static bool HasScalarSchema()
    {
        FieldInfo[] fields = typeof(AndroidNativeAudioCameraAdmissionEvidence).GetFields(
            BindingFlags.Instance | BindingFlags.Public);
        if (fields.Length != 142 || fields.Length > 192) return false;
        int nestedFields = 0;
        foreach (FieldInfo field in fields)
        {
            if (field.Name == "firstAdmissionSample" &&
                field.FieldType == typeof(AndroidNativeAudioCameraAdmissionSample))
            {
                nestedFields++;
                continue;
            }
            if (!(field.FieldType.IsPrimitive || field.FieldType == typeof(string))) return false;
        }
        FieldInfo[] sampleFields = typeof(AndroidNativeAudioCameraAdmissionSample).GetFields(
            BindingFlags.Instance | BindingFlags.Public);
        FieldInfo[] scalarFields = typeof(AndroidNativeAudioCameraAdmissionScalars).GetFields(
            BindingFlags.Instance | BindingFlags.Public);
        if (sampleFields.Length != 141 || scalarFields.Length != 141 ||
            typeof(AndroidNativeAudioCameraAdmissionSample).GetField("firstAdmissionSample") != null)
            return false;
        foreach (FieldInfo field in scalarFields)
        {
            if (!(field.FieldType.IsPrimitive || field.FieldType == typeof(string))) return false;
            FieldInfo sampleField = typeof(AndroidNativeAudioCameraAdmissionSample).GetField(field.Name,
                BindingFlags.Instance | BindingFlags.Public);
            FieldInfo evidenceField = typeof(AndroidNativeAudioCameraAdmissionEvidence).GetField(field.Name,
                BindingFlags.Instance | BindingFlags.Public);
            if (sampleField == null || evidenceField == null || sampleField.FieldType != field.FieldType ||
                evidenceField.FieldType != field.FieldType) return false;
        }
        return nestedFields == 1;
    }

    static bool HasValue(AndroidNativeAudioCameraAdmissionScalars evidence, int sequence, float realtime, string decision)
    {
        return evidence != null && evidence.admissionSampleKnown && evidence.admissionSampleSequence == sequence &&
            evidence.admissionSampleRealtimeValid && evidence.admissionSampleRealtime == realtime &&
            evidence.admissionEvaluationObserved && evidence.admissionInputsKnown &&
            evidence.originalContextResultKnown && evidence.originalContextReady == (sequence == 1) &&
            evidence.admissionDecision == decision;
    }

    static bool ContainsSampleValue(string json, string decision, float realtime)
    {
        if (string.IsNullOrEmpty(json)) return false;
        const string member = "\"firstAdmissionSample\":";
        int memberIndex = json.IndexOf(member, StringComparison.Ordinal);
        if (memberIndex < 0) return false;
        int opening = json.IndexOf('{', memberIndex + member.Length);
        if (opening < 0) return false;
        int depth = 0, closing = -1;
        for (int i = opening; i < json.Length; i++)
        {
            if (json[i] == '{') depth++;
            else if (json[i] == '}' && --depth == 0)
            {
                closing = i;
                break;
            }
        }
        if (closing < 0) return false;
        string sampleJson = json.Substring(opening, closing - opening + 1);
        return sampleJson.IndexOf("\"admissionDecision\":\"" + decision + "\"", StringComparison.Ordinal) >= 0 &&
            sampleJson.IndexOf("\"admissionSampleRealtime\":" + realtime.ToString("0.0#", System.Globalization.CultureInfo.InvariantCulture),
                StringComparison.Ordinal) >= 0;
    }

    static bool ContainsRawValue(string json, string decision, float realtime)
    {
        return !string.IsNullOrEmpty(json) &&
            json.IndexOf("\"admissionDecision\":\"" + decision + "\"", StringComparison.Ordinal) >= 0 &&
            json.IndexOf("\"admissionSampleRealtime\":" + realtime.ToString("0.0#", System.Globalization.CultureInfo.InvariantCulture),
                StringComparison.Ordinal) >= 0;
    }
}
