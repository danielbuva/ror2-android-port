using System;

// Candidate diagnostic-only observer. It is a no-op unless explicitly armed.
// No Unity/Wwise references are required, so this helper cannot create or alter
// original engine objects and its report contains only bounded scalar fields.
public static class PointSoundDiagnosticObserver
{
    private static volatile bool enabled;
    private static bool requested;
    private static int requestCount;
    private static uint lastEventId;
    private static int lastStage;
    private static int hasEmitterAlive;
    private static int emitterAlive;
    private static int currentAcquisitionPath;
    private static int firstNullReferenceAcquisitionPath;
    private static int hasFirstNullReferenceEmitterAlive;
    private static int firstNullReferenceEmitterAlive;
    private static int firstNullReferenceStage;
    private static uint firstNullReferenceEventId;
    private static int matchingNullReferenceCount;

    public static bool Enabled => enabled;
    public static bool Requested => requested;

    public static string RouteRefusal(bool selected, bool integratedWorld)
    {
        if (!selected) return null;
        return integratedWorld ? null : "Point-sound diagnostic requires the integrated original gameplay route";
    }

    public static string OwnerRefusal(bool selected, bool originalAudioSelected, bool originalAudioReady)
    {
        if (!selected) return null;
        if (!originalAudioSelected) return "Point-sound diagnostic requires the selected original-audio owner";
        return originalAudioReady ? null : "Point-sound diagnostic requires the ready original-audio owner";
    }

    public static void Configure(bool requested)
    {
        if (requested) Reset();
        PointSoundDiagnosticObserver.requested = requested || PointSoundDiagnosticObserver.requested;
        enabled = requested;
    }

    public static void Disable() => enabled = false;

    public static void Reset()
    {
        requestCount = 0;
        lastEventId = 0;
        lastStage = 0;
        hasEmitterAlive = 0;
        emitterAlive = 0;
        currentAcquisitionPath = 0;
        firstNullReferenceStage = 0;
        firstNullReferenceEventId = 0;
        firstNullReferenceAcquisitionPath = 0;
        hasFirstNullReferenceEmitterAlive = 0;
        firstNullReferenceEmitterAlive = 0;
        matchingNullReferenceCount = 0;
    }

    public static void Begin(uint eventId)
    {
        if (!enabled) return;
        requestCount = SaturatingIncrement(requestCount);
        lastEventId = eventId;
        lastStage = 1;
        hasEmitterAlive = 0;
        emitterAlive = 0;
        currentAcquisitionPath = 0;
    }

    public static void Mark(int stage)
    {
        if (!enabled) return;
        lastStage = stage;
        // Existing emitted markers 20/21/22 already identify RequestEmitter's
        // pool, prefab, and fallback branches. Preserve that context while the
        // later EmitSoundLocal stages continue updating lastStage.
        if (stage >= 20 && stage <= 22) currentAcquisitionPath = stage;
    }

    public static void RecordEmitterAlive(bool value)
    {
        if (!enabled) return;
        emitterAlive = value ? 1 : 0;
        hasEmitterAlive = 1;
    }

    // Called only by the opted-in owner’s Unity log callback. It records a
    // stage/count, never the raw log or stack, and never handles the exception.
    public static void ObserveUnityLog(string condition, string stackTrace)
    {
        if (!enabled || condition == null || stackTrace == null) return;
        try
        {
            if (condition.IndexOf("NullReferenceException", StringComparison.Ordinal) < 0 ||
                (stackTrace.IndexOf("RoR2.Audio.PointSoundManager.EmitSoundLocal", StringComparison.Ordinal) < 0 &&
                 stackTrace.IndexOf("PointSoundManager:EmitSoundLocal", StringComparison.Ordinal) < 0))
                return;
            matchingNullReferenceCount = SaturatingIncrement(matchingNullReferenceCount);
            if (matchingNullReferenceCount == 1)
            {
                firstNullReferenceStage = lastStage;
                firstNullReferenceEventId = lastEventId;
                firstNullReferenceAcquisitionPath = currentAcquisitionPath;
                hasFirstNullReferenceEmitterAlive = hasEmitterAlive;
                firstNullReferenceEmitterAlive = emitterAlive;
            }
        }
        catch
        {
            // Diagnostics must not replace or mask Unity’s original log path.
        }
    }

    public static int RequestCount => requestCount;
    public static uint LastEventId => lastEventId;
    public static int LastStage => lastStage;
    public static int HasEmitterAlive => hasEmitterAlive;
    public static int EmitterAlive => emitterAlive;
    public static int FirstNullReferenceStage => firstNullReferenceStage;
    public static uint FirstNullReferenceEventId => firstNullReferenceEventId;
    public static int MatchingNullReferenceCount => matchingNullReferenceCount;

    [Serializable]
    public sealed class Snapshot
    {
        public bool requested;
        public bool enabled;
        public int requestCount;
        public uint lastEventId;
        public int lastStage;
        public bool hasEmitterAlive;
        public bool emitterAlive;
        public bool hasFirstNullReference;
        public uint firstNullReferenceEventId;
        public int firstNullReferenceStage;
        public int firstNullReferenceAcquisitionPath;
        public bool hasFirstNullReferenceEmitterAlive;
        public bool firstNullReferenceEmitterAlive;
        public int matchingNullReferenceCount;
    }

    public static Snapshot CaptureSnapshot()
    {
        if (!requested) return null;
        return new Snapshot {
            requested = requested,
            enabled = enabled,
            requestCount = requestCount,
            lastEventId = lastEventId,
            lastStage = lastStage,
            hasEmitterAlive = hasEmitterAlive != 0,
            emitterAlive = emitterAlive != 0,
            hasFirstNullReference = matchingNullReferenceCount != 0,
            firstNullReferenceEventId = firstNullReferenceEventId,
            firstNullReferenceStage = firstNullReferenceStage,
            firstNullReferenceAcquisitionPath = firstNullReferenceAcquisitionPath,
            hasFirstNullReferenceEmitterAlive = hasFirstNullReferenceEmitterAlive != 0,
            firstNullReferenceEmitterAlive = firstNullReferenceEmitterAlive != 0,
            matchingNullReferenceCount = matchingNullReferenceCount
        };
    }

    private static int SaturatingIncrement(int value) => value == int.MaxValue ? value : value + 1;
}
