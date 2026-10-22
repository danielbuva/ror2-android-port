using System;

public sealed class Material { }

public sealed class NullCacheModel
{
    private static Material[][] sharedMaterialArrays;
    private static int maxMaterials = 3;
    public static int InitializerCalls;
    private static void InitSharedMaterialsArrays()
    {
        InitializerCalls++;
        sharedMaterialArrays = new Material[maxMaterials + 1][];
        for (int index = 0; index <= maxMaterials; index++)
            sharedMaterialArrays[index] = new Material[index];
    }
}

public sealed class ExistingCacheModel
{
    private static Material[][] sharedMaterialArrays = MakeValid();
    private static int maxMaterials = 2;
    public static int InitializerCalls;
    private static Material[][] MakeValid()
    {
        return new[] { new Material[0], new Material[1], new Material[2] };
    }
    private static void InitSharedMaterialsArrays() { InitializerCalls++; }
}

public sealed class MalformedCacheModel
{
    private static Material[][] sharedMaterialArrays = new[] { new Material[0] };
    private static int maxMaterials = 2;
    public static int InitializerCalls;
    private static void InitSharedMaterialsArrays() { InitializerCalls++; }
}

public sealed class ThrowingInitializerModel
{
    private static Material[][] sharedMaterialArrays;
    private static int maxMaterials = 2;
    public static int InitializerCalls;
    private static void InitSharedMaterialsArrays()
    {
        InitializerCalls++;
        sharedMaterialArrays = new[] { new Material[0] };
        throw new InvalidOperationException("synthetic partial initialization");
    }
}

public sealed class WrongSignatureModel
{
    private static Material[][] sharedMaterialArrays;
    private static int maxMaterials = 2;
    public static int InitializerCalls;
    private static void InitSharedMaterialsArrays(int ignored) { InitializerCalls++; }
}

public sealed class GenericInitializerModel
{
    private static Material[][] sharedMaterialArrays;
    private static int maxMaterials = 2;
    public static int InitializerCalls;
    private static void InitSharedMaterialsArrays<T>() { InitializerCalls++; }
}

public sealed class WrongCacheContractModel
{
    private static Material[][] sharedMaterialArrays;
    private static int maxMaterials = 2;
    public static int InitializerCalls;
    private static void InitSharedMaterialsArrays() { InitializerCalls++; }
}

public sealed class TooSmallMaximumModel
{
    private static Material[][] sharedMaterialArrays;
    private static int maxMaterials = 0;
    public static int InitializerCalls;
    private static void InitSharedMaterialsArrays() { InitializerCalls++; }
}

public sealed class TooLargeMaximumModel
{
    private static Material[][] sharedMaterialArrays;
    private static int maxMaterials = 65;
    public static int InitializerCalls;
    private static void InitSharedMaterialsArrays() { InitializerCalls++; }
}

public sealed class MissingCacheFieldModel
{
    private static int maxMaterials = 2;
    public static int InitializerCalls;
    private static void InitSharedMaterialsArrays() { InitializerCalls++; }
}

public static class CharacterModelMaterialCacheOwnerFixture
{
    private static void Need(bool condition, string name)
    {
        if (!condition) throw new Exception("failed: " + name);
    }

    public static int Main()
    {
        var nullType = typeof(NullCacheModel);
        var initialized = CharacterModelMaterialCacheOwner.EnsureInitialized(nullType, typeof(Material[][]));
        Need(initialized.outcome == CharacterModelMaterialCacheOwner.Outcome.Initialized, "null cache initialized");
        Need(initialized.initializerAttempted && initialized.maximumMaterials == 3 && initialized.cacheLength == 4,
             "initializer outcome snapshot");
        Need(NullCacheModel.InitializerCalls == 1, "initializer invoked once");
        Need(object.ReferenceEquals(initialized,
             CharacterModelMaterialCacheOwner.EnsureInitialized(nullType, typeof(Material[][]))),
             "terminal result memoized");
        Need(NullCacheModel.InitializerCalls == 1, "memoized path does not retry");
        Need(CharacterModelMaterialCacheOwner.EnsureInitialized(nullType, typeof(object[][])).outcome ==
             CharacterModelMaterialCacheOwner.Outcome.Refused, "terminal type binding cannot be changed");

        var already = CharacterModelMaterialCacheOwner.EnsureInitialized(typeof(ExistingCacheModel), typeof(Material[][]));
        Need(already.outcome == CharacterModelMaterialCacheOwner.Outcome.AlreadyInitialized && !already.initializerAttempted,
             "valid source cache preserved");
        Need(ExistingCacheModel.InitializerCalls == 0, "existing cache not reinitialized");

        var malformed = CharacterModelMaterialCacheOwner.EnsureInitialized(typeof(MalformedCacheModel), typeof(Material[][]));
        Need(malformed.outcome == CharacterModelMaterialCacheOwner.Outcome.Failed && !malformed.initializerAttempted,
             "malformed existing cache fails closed");
        Need(MalformedCacheModel.InitializerCalls == 0, "malformed cache not overwritten");

        var threwType = typeof(ThrowingInitializerModel);
        var threw = CharacterModelMaterialCacheOwner.EnsureInitialized(threwType, typeof(Material[][]));
        Need(threw.outcome == CharacterModelMaterialCacheOwner.Outcome.Failed && threw.initializerAttempted,
             "throwing invocation is terminal failure");
        Need(ThrowingInitializerModel.InitializerCalls == 1, "throwing initializer called once");
        Need(object.ReferenceEquals(threw, CharacterModelMaterialCacheOwner.EnsureInitialized(threwType, typeof(Material[][]))),
             "unknown partial state never retried");
        Need(ThrowingInitializerModel.InitializerCalls == 1, "failed initializer retry refused");

        var wrongSignature = CharacterModelMaterialCacheOwner.EnsureInitialized(typeof(WrongSignatureModel), typeof(Material[][]));
        Need(wrongSignature.outcome == CharacterModelMaterialCacheOwner.Outcome.Refused && !wrongSignature.initializerAttempted,
             "wrong initializer signature refused");
        Need(WrongSignatureModel.InitializerCalls == 0, "wrong-signature method not invoked");

        var generic = CharacterModelMaterialCacheOwner.EnsureInitialized(typeof(GenericInitializerModel), typeof(Material[][]));
        Need(generic.outcome == CharacterModelMaterialCacheOwner.Outcome.Refused && !generic.initializerAttempted,
             "generic initializer refused");
        Need(GenericInitializerModel.InitializerCalls == 0, "generic initializer not invoked");

        var missingField = CharacterModelMaterialCacheOwner.EnsureInitialized(typeof(MissingCacheFieldModel), typeof(Material[][]));
        Need(missingField.outcome == CharacterModelMaterialCacheOwner.Outcome.Refused && !missingField.initializerAttempted,
             "missing source field refused");
        Need(MissingCacheFieldModel.InitializerCalls == 0, "missing-field initializer not invoked");

        Need(CharacterModelMaterialCacheOwner.EnsureInitialized(null, typeof(Material[][])).outcome ==
             CharacterModelMaterialCacheOwner.Outcome.Refused, "null type refused");
        Need(CharacterModelMaterialCacheOwner.EnsureInitialized(typeof(WrongCacheContractModel), typeof(object[][])).outcome ==
             CharacterModelMaterialCacheOwner.Outcome.Refused, "wrong cache contract refused");
        Need(CharacterModelMaterialCacheOwner.EnsureInitialized(typeof(NullCacheModel), typeof(Material[,][])).outcome ==
             CharacterModelMaterialCacheOwner.Outcome.Refused, "multidimensional jagged type refused");
        Need(CharacterModelMaterialCacheOwner.EnsureInitialized(typeof(NullCacheModel), typeof(Material[][][])).outcome ==
             CharacterModelMaterialCacheOwner.Outcome.Refused, "over-nested array type refused");
        Need(CharacterModelMaterialCacheOwner.EnsureInitialized(typeof(TooSmallMaximumModel), typeof(Material[][])).outcome ==
             CharacterModelMaterialCacheOwner.Outcome.Refused, "zero maximum refused");
        Need(TooSmallMaximumModel.InitializerCalls == 0, "zero maximum initializer not invoked");
        Need(CharacterModelMaterialCacheOwner.EnsureInitialized(typeof(TooLargeMaximumModel), typeof(Material[][])).outcome ==
             CharacterModelMaterialCacheOwner.Outcome.Refused, "bounded maximum enforced");
        Need(TooLargeMaximumModel.InitializerCalls == 0, "oversized maximum initializer not invoked");

        var serialized = CharacterModelMaterialCacheOwner.CaptureReport(initialized);
        var reportType = typeof(CharacterModelMaterialCacheOwner.Report);
        Need(Attribute.IsDefined(reportType, typeof(SerializableAttribute)), "report DTO serializable");
        var fields = reportType.GetFields(System.Reflection.BindingFlags.Public | System.Reflection.BindingFlags.Instance);
        Need(fields.Length == 5, "report DTO has five public fields");
        Need(serialized.outcome == "Initialized" && serialized.initializerAttempted &&
             serialized.maximumMaterials == 3 && serialized.cacheLength == 4 && serialized.failureType == string.Empty,
             "report DTO copies terminal owner snapshot");

        Console.WriteLine("material cache owner synthetic contract passed");
        return 0;
    }
}
