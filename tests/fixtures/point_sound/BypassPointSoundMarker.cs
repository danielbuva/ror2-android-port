using System;
using System.Linq;
using Mono.Cecil;
using Mono.Cecil.Cil;

internal static class BypassPointSoundMarker
{
    private static int Main(string[] args)
    {
        if (args.Length != 3) return 2;
        var resolver = new DefaultAssemblyResolver();
        resolver.AddSearchDirectory(System.IO.Path.GetDirectoryName(System.IO.Path.GetFullPath(args[0])));
        resolver.AddSearchDirectory(System.IO.Path.GetFullPath(args[2]));
        resolver.AddSearchDirectory("/Applications/Unity/Hub/Editor/2021.3.45f2/Unity.app/Contents/Managed/UnityEngine");
        using (var game = AssemblyDefinition.ReadAssembly(args[0], new ReaderParameters { AssemblyResolver = resolver }))
        {
            var type = game.MainModule.Types.Single(t => t.FullName == "RoR2.Audio.PointSoundManager");
            var emit = type.Methods.Single(m => m.Name == "EmitSoundLocal" && m.Parameters.Select(p => p.ParameterType.FullName)
                .SequenceEqual(new[] { "RoR2.Audio.AkEventIdArg", "UnityEngine.Vector3" }));
            var request = emit.Body.Instructions.Single(i => i.Operand is MethodReference mr &&
                mr.DeclaringType.FullName == "RoR2.Audio.PointSoundManager" && mr.Name == "RequestEmitter");
            var markerCall = request.Previous;
            var markerEntry = markerCall?.Previous;
            var marker = markerCall?.Operand as MethodReference;
            if (marker == null || marker.Name != "Mark" || markerEntry == null ||
                markerEntry.OpCode != OpCodes.Ldc_I4 || !Equals(markerEntry.Operand, 2))
                throw new InvalidOperationException("expected stage-2 marker before RequestEmitter");
            var branches = emit.Body.Instructions.Where(i => ReferenceEquals(i.Operand, markerEntry)).ToArray();
            if (branches.Length == 0) throw new InvalidOperationException("no incoming control edge to mutate");
            foreach (var branch in branches) branch.Operand = request;
            game.Write(args[1]);
        }
        Console.WriteLine("retargeted an existing incoming branch around the stage-2 marker");
        return 0;
    }
}
