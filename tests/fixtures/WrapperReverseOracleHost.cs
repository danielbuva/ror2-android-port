using System;
using System.Collections.Generic;
using System.Linq;
namespace UnityEngine
{
    public class Object { }
    public static class Application {public static string unityVersion = "fixture";}
    public static class JsonUtility
    {
        public static string ToJson(object value, bool pretty) {throw new Exception("Not an SDK batch");}
        public static T FromJson<T>(string value) {throw new Exception("Not an SDK batch");}
    }
    public static class Debug {public static void Log(object value) {}}
}
public static class ReverseHost
{
    static Dictionary<ulong, byte> memory;
    static void Write(ulong address, byte[] bytes) {for (int i = 0; i < bytes.Length; i++) memory[address + (ulong)i] = bytes[i];}
    static byte[] Read(ulong address, int count) {return Enumerable.Range(0, count).Select(i => memory[address + (ulong)i]).ToArray();}
    static WrapperReverseOracle.Layout Reset()
    {
        memory = new Dictionary<ulong, byte>();
        Write(0x1200, BitConverter.GetBytes(0x4000UL));
        Write(0x4080, BitConverter.GetBytes(0x5000UL).Concat(BitConverter.GetBytes(0x5020UL)).ToArray());
        Write(0x5000, new[] {0x7000UL, 0x1100UL, 0x7100UL, 0x1140UL}.SelectMany(BitConverter.GetBytes).ToArray());
        Write(0x1128, BitConverter.GetBytes(801));
        Write(0x1168, BitConverter.GetBytes(802));
        return new WrapperReverseOracle.Layout {schema = 1, manager_slot = 0x1200, begin_offset = 0x80, end_offset = 0x88,
            stride = 16, native_id_offset = 40, ranges = new[] {new WrapperReverseOracle.Range {start = 0x1000, size = 0x1000, file_size = 0x180}}};
    }
    static WrapperReverseOracle.Name Identify(ulong pointer)
    {
        return new WrapperReverseOracle.Name {name = "Authored." + pointer, assembly_identity = "Authored, Version=1.0.0.0"};
    }
    static WrapperReverseOracle.Layout ForwardReset()
    {
        var value = Reset(); value.forward_offset = 0x100; value.forward_count_offset = 0x118;
        Write(0x4100, BitConverter.GetBytes(0x6000UL));
        Write(0x4118, BitConverter.GetBytes(3UL));
        Write(0x6000, new[] {0x7000UL, 0UL, 0x7100UL}.SelectMany(BitConverter.GetBytes).ToArray());
        return value;
    }
    static void Refuse(Action action)
    {
        try {action();} catch (InvalidOperationException) {return;}
        throw new Exception("Invalid reverse cache was accepted");
    }
    public static int Main()
    {
        var layout = Reset();
        var rows = WrapperReverseOracle.ReadTable(layout, 0, Read, Identify);
        if (!rows.Select(r => r.persistentTypeID).SequenceEqual(new[] {801, 802})) throw new Exception("Observed IDs differ");
        const ulong slide = 0x20000;
        Write(0x1200, BitConverter.GetBytes(0x4000UL + slide));
        Write(0x4080, BitConverter.GetBytes(0x5000UL + slide).Concat(BitConverter.GetBytes(0x5020UL + slide)).ToArray());
        Write(0x5000, new[] {0x7000UL, 0x1100UL, 0x7100UL, 0x1140UL}.SelectMany(p => BitConverter.GetBytes(p + slide)).ToArray());
        rows = WrapperReverseOracle.ReadTable(layout, (long)slide, (p, n) => Read(p - slide, n), Identify);
        if (!rows.Select(r => r.persistentTypeID).SequenceEqual(new[] {801, 802})) throw new Exception("ASLR observation differs");
        // The manager slot deliberately lies beyond file bytes, but inside VM.
        if (layout.manager_slot <= layout.ranges[0].start + layout.ranges[0].file_size) throw new Exception("Fixture lacks zero-fill tail");
        layout = Reset(); Write(0x4088, BitConverter.GetBytes(0x5001UL));
        Refuse(() => WrapperReverseOracle.ReadTable(layout, 0, Read, p => {throw new Exception("Metadata queried before bounds validation");}));
        layout = Reset(); Write(0x4088, BitConverter.GetBytes(0x5000UL + 4097 * 16));
        Refuse(() => WrapperReverseOracle.ReadTable(layout, 0, Read, Identify));
        layout = Reset(); Write(0x5010, BitConverter.GetBytes(0x7000UL));
        Refuse(() => WrapperReverseOracle.ReadTable(layout, 0, Read, Identify));
        layout = Reset(); Write(0x5008, BitConverter.GetBytes(0x3000UL));
        Refuse(() => WrapperReverseOracle.ReadTable(layout, 0, Read, p => {throw new Exception("Foreign native pointer queried metadata");}));
        layout = Reset();
        Refuse(() => WrapperReverseOracle.ReadTable(layout, 0, Read, p => new WrapperReverseOracle.Name {name = "Same", assembly_identity = "Same"}));
        layout = Reset();
        Refuse(() => WrapperReverseOracle.ReadTable(layout, 0, Read, p => {Write(0x5008, BitConverter.GetBytes(0x1140UL)); return Identify(p);}));
        layout = Reset();
        Refuse(() => WrapperReverseOracle.ReadTable(layout, 0, Read, p => {Write(0x4088, BitConverter.GetBytes(0x5010UL)); return Identify(p);}));
        layout = Reset(); layout.manager_slot = 0x3000;
        Refuse(() => WrapperReverseOracle.ReadTable(layout, 0, Read, Identify));
        layout = ForwardReset();
        rows = WrapperReverseOracle.ReadForward(layout, 0, new[] {801, 802, 803}, Read, Identify);
        if (!rows.Select(r => r.persistentTypeID).SequenceEqual(new[] {801, 803})) throw new Exception("Forward zero-slot coverage differs");
        layout = ForwardReset(); Write(0x4118, BitConverter.GetBytes(4UL));
        Refuse(() => WrapperReverseOracle.ReadForward(layout, 0, new[] {801, 802, 803}, Read, Identify));
        layout = ForwardReset();
        Refuse(() => WrapperReverseOracle.ReadForward(layout, 0, new[] {801, 802, 803}, Read, p => {Write(0x6000, BitConverter.GetBytes(0UL)); return Identify(p);}));
        layout = ForwardReset();
        Refuse(() => WrapperReverseOracle.ReadForward(layout, 0, new[] {801, 801, 803}, Read, Identify));
        Console.WriteLine("PASS: reverse snapshot, zero-fill VM, bounds, keys, identities, foreign pointers and drift");
        return 0;
    }
}
