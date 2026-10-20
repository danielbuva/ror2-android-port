using System.Runtime.InteropServices;

[AttributeUsage(AttributeTargets.All, AllowMultiple = false)]
internal sealed class ContractAttribute : Attribute
{
    public ContractAttribute(FixtureMode mode, int[] values) { }
    public int Code;
    public string? Label { get; set; }
}

internal enum FixtureMode : short { First = 1, Second = 2 }

[Contract(FixtureMode.Second, new[] { 2, 5, 8 }, Code = 17, Label = "type-payload")]
internal static unsafe class ShapeFixture
{
    [Contract(FixtureMode.First, new[] { 2, 7 }, Code = 19, Label = "string-method-payload")]
    [return: Contract(FixtureMode.Second, new[] { 4 }, Code = 21, Label = "string-return-payload")]
    [DllImport("fixture", EntryPoint = "game-string", ExactSpelling = true, CharSet = CharSet.Unicode)]
    internal static extern int String([Contract(FixtureMode.First, new[] { 6, 10 }, Code = 25, Label = "string-parameter-payload"), MarshalAs(UnmanagedType.LPWStr)] string value);

    [Contract(FixtureMode.First, new[] { 1, 4 }, Code = 23, Label = "method-payload")]
    [return: Contract(FixtureMode.Second, new[] { 3, 6 }, Code = 29, Label = "return-payload")]
    [DllImport("fixture", EntryPoint = "pointer", ExactSpelling = true)]
    internal static extern int Pointer([Contract(FixtureMode.First, new[] { 5, 9 }, Code = 31, Label = "parameter-payload")] byte* value);

    [DllImport("fixture", EntryPoint = "byref", ExactSpelling = true)]
    internal static extern int ByRef(ref uint value);

    [DllImport("fixture", EntryPoint = "in", ExactSpelling = true)]
    internal static extern int In(in uint value);

    [DllImport("fixture", EntryPoint = "out", ExactSpelling = true)]
    internal static extern int Out(out uint value);

    [DllImport("fixture", EntryPoint = "sz-array", ExactSpelling = true)]
    internal static extern int SzArray([MarshalAs(UnmanagedType.LPArray)] int[] values);

    [DllImport("fixture", EntryPoint = "rank-two", ExactSpelling = true)]
    internal static extern int RankTwo([MarshalAs(UnmanagedType.LPArray)] int[,] values);

    [DllImport("fixture", EntryPoint = "sized-array", ExactSpelling = true)]
    internal static extern int SizedArray([MarshalAs(UnmanagedType.LPArray, ArraySubType = UnmanagedType.U4, SizeConst = 3)] uint[] values);

    [DllImport("fixture", EntryPoint = "sized-array-return", ExactSpelling = true)]
    [return: MarshalAs(UnmanagedType.LPArray, ArraySubType = UnmanagedType.U4, SizeConst = 3)]
    internal static extern uint[] SizedArrayReturn();

    [StructLayout(LayoutKind.Explicit, Pack = 2, Size = 16)]
    internal struct ExplicitLayout
    {
        [FieldOffset(0), Contract(FixtureMode.Second, new[] { 7 }, Code = 37, Label = "field-payload")] public uint A;
        [FieldOffset(0)] public float B;
        [FieldOffset(8)] public nint C;
    }

    internal static int BodyWithEhAndLocals(int value)
    {
        var local = value + 1;
        try { return local; }
        catch (Exception) { return -1; }
    }
}

internal static class AkSoundEngine
{
    internal static string StringFromIntPtrWString(nint value) => "wide";
    internal static string StringFromIntPtrString(nint value) => "bytes";
#if WRONG_REWRITE_SIGNATURE
    internal static string StringFromIntPtrOSString(string value) => value;
#else
#if WRONG_REWRITE_OPERAND
    internal static string StringFromIntPtrOSString(nint value) => StringFromIntPtrString(value);
#elif WRONG_REWRITE_BODY
    internal static string StringFromIntPtrOSString(nint value) => StringFromIntPtrWString(value) + "!";
#else
    internal static string StringFromIntPtrOSString(nint value) => StringFromIntPtrWString(value);
#endif
#endif
#if WRONG_REWRITE_OVERLOAD
    internal static string StringFromIntPtrOSString(string value) => value;
#endif
}
