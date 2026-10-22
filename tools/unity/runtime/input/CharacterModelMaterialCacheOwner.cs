using System;
using System.Collections.Generic;
using System.Reflection;

// Process-lifetime prerequisite for original CharacterModel material updates.
// The source owns the cache; session teardown does not reset it.
public static class CharacterModelMaterialCacheOwner
{
    public enum Outcome
    {
        AlreadyInitialized,
        Initialized,
        Refused,
        Failed
    }

    // Unity JsonUtility consumes public fields on a serializable DTO. This is a
    // detached copy; exposing the internal memoized Snapshot would not serialize
    // its private-set properties reliably.
    [Serializable]
    public sealed class Report
    {
        public string outcome;
        public bool initializerAttempted;
        public int maximumMaterials;
        public int cacheLength;
        public string failureType;
    }

    public sealed class Snapshot
    {
        public Outcome outcome { get; private set; }
        public bool initializerAttempted { get; private set; }
        public int maximumMaterials { get; private set; }
        public int cacheLength { get; private set; }
        public string failureType { get; private set; }

        internal Snapshot(Outcome outcome, bool initializerAttempted, int maximumMaterials, int cacheLength,
                          string failureType)
        {
            this.outcome = outcome;
            this.initializerAttempted = initializerAttempted;
            this.maximumMaterials = maximumMaterials;
            this.cacheLength = cacheLength;
            this.failureType = failureType ?? string.Empty;
        }
    }

    private sealed class Entry
    {
        public bool inProgress;
        public Type materialArrayType;
        public Snapshot terminal;
    }

    private const int MinimumMaximumMaterials = 1;
    private const int MaximumMaterialsBound = 64;
    private static readonly object gate = new object();
    private static readonly Dictionary<Type, Entry> entries = new Dictionary<Type, Entry>();

    // At the integration point modelType is typeof(RoR2.CharacterModel), and
    // materialArrayType is typeof(UnityEngine.Material[][]). Exact types are
    // injected so the same contract can be tested against authored fixtures.
    public static Snapshot EnsureInitialized(Type modelType, Type materialArrayType)
    {
        if (modelType == null || materialArrayType == null || !IsExactJaggedArrayType(materialArrayType))
            return new Snapshot(Outcome.Refused, false, -1, -1, string.Empty);

        lock (gate)
        {
            Entry entry;
            if (entries.TryGetValue(modelType, out entry))
            {
                if (entry.materialArrayType != materialArrayType)
                    return new Snapshot(Outcome.Refused, false, -1, -1, string.Empty);
                if (entry.terminal != null)
                    return entry.terminal;
                if (entry.inProgress)
                    return new Snapshot(Outcome.Refused, false, -1, -1, string.Empty);
            }
            else
            {
                entry = new Entry { materialArrayType = materialArrayType };
                entries.Add(modelType, entry);
            }

            entry.inProgress = true;
            Snapshot result;
            bool initializerAttempted = false;
            try
            {
                result = EnsureCore(modelType, materialArrayType, ref initializerAttempted);
            }
            catch (Exception error)
            {
                // Once Invoke has been attempted, an exception can leave the
                // source-owned cache in an unknown state. Memoize the result and
                // never retry this type during the process lifetime.
                result = new Snapshot(Outcome.Failed, initializerAttempted, -1, -1,
                                      error.GetType().FullName);
            }
            entry.inProgress = false;
            entry.terminal = result;
            return result;
        }
    }

    public static Report CaptureReport(Snapshot snapshot)
    {
        if (snapshot == null)
            return new Report { outcome = Outcome.Refused.ToString(), maximumMaterials = -1, cacheLength = -1 };
        return new Report {
            outcome = snapshot.outcome.ToString(),
            initializerAttempted = snapshot.initializerAttempted,
            maximumMaterials = snapshot.maximumMaterials,
            cacheLength = snapshot.cacheLength,
            failureType = snapshot.failureType
        };
    }

    private static bool IsExactJaggedArrayType(Type value)
    {
        return value.IsArray && value.GetArrayRank() == 1 && value.GetElementType().IsArray &&
               value.GetElementType().GetArrayRank() == 1 && !value.GetElementType().GetElementType().IsArray;
    }

    private static Snapshot EnsureCore(Type modelType, Type materialArrayType, ref bool initializerAttempted)
    {
        const BindingFlags flags = BindingFlags.Static | BindingFlags.NonPublic | BindingFlags.DeclaredOnly;
        FieldInfo cacheField = modelType.GetField("sharedMaterialArrays", flags);
        FieldInfo maximumField = modelType.GetField("maxMaterials", flags);
        MethodInfo initializer = modelType.GetMethod("InitSharedMaterialsArrays", flags, null, Type.EmptyTypes, null);
        if (cacheField == null || !cacheField.IsPrivate || !cacheField.IsStatic ||
            cacheField.FieldType != materialArrayType ||
            maximumField == null || !maximumField.IsPrivate || !maximumField.IsStatic ||
            maximumField.FieldType != typeof(int) || initializer == null || !initializer.IsPrivate ||
            !initializer.IsStatic || initializer.IsGenericMethod || initializer.ContainsGenericParameters ||
            initializer.ReturnType != typeof(void) || initializer.DeclaringType != modelType)
            return new Snapshot(Outcome.Refused, false, -1, -1, string.Empty);

        int maximum = (int)maximumField.GetValue(null);
        if (maximum < MinimumMaximumMaterials || maximum > MaximumMaterialsBound)
            return new Snapshot(Outcome.Refused, false, maximum, -1, string.Empty);

        Array current = cacheField.GetValue(null) as Array;
        if (current != null)
            return Validate(current, maximum, materialArrayType.GetElementType(), Outcome.AlreadyInitialized, false);

        // Invoke only the exact retained original private static no-argument
        // initializer. Never allocate a replacement or replay the broad startup phase.
        try
        {
            initializerAttempted = true;
            initializer.Invoke(null, null);
        }
        catch (Exception error)
        {
            Exception cause = error is TargetInvocationException && error.InnerException != null
                                  ? error.InnerException : error;
            return new Snapshot(Outcome.Failed, true, maximum, -1, cause.GetType().FullName);
        }

        Array initialized = cacheField.GetValue(null) as Array;
        if (initialized == null)
            return new Snapshot(Outcome.Failed, true, maximum, -1, string.Empty);
        return Validate(initialized, maximum, materialArrayType.GetElementType(), Outcome.Initialized, true);
    }

    private static Snapshot Validate(Array cache, int maximum, Type bucketType, Outcome success, bool invoked)
    {
        if (cache.GetType() != bucketType.MakeArrayType() || cache.Length != maximum + 1)
            return new Snapshot(Outcome.Failed, invoked, maximum, cache.Length, string.Empty);
        for (int index = 0; index <= maximum; index++)
        {
            Array bucket = cache.GetValue(index) as Array;
            if (bucket == null || bucket.GetType() != bucketType || bucket.Length != index)
                return new Snapshot(Outcome.Failed, invoked, maximum, cache.Length, string.Empty);
        }
        return new Snapshot(success, invoked, maximum, cache.Length, string.Empty);
    }
}
