using System;
using System.Linq;
using Mono.Cecil;

internal static class RemoveMarkerExceptionHandlers
{
    static int Main(string[] args)
    {
        if (args.Length != 3) return 2;
        using (var resolver = new DefaultAssemblyResolver())
        {
            resolver.AddSearchDirectory(System.IO.Path.GetDirectoryName(System.IO.Path.GetFullPath(args[0])));
            resolver.AddSearchDirectory(args[2]);
            using (var module = ModuleDefinition.ReadModule(args[0], new ReaderParameters { AssemblyResolver = resolver }))
            {
                var marker = module.GetType("RoR2.AndroidNativeSourceViewOnlyRigMarker");
                var pump = marker.Methods.Single(method => method.Name == "TryPumpOriginalEarlyUpdate");
                if (pump.Body.ExceptionHandlers.Count == 0)
                    throw new InvalidOperationException("source output had no marker exception handler to mutate");
                pump.Body.ExceptionHandlers.Clear();
                module.Write(args[1]);
            }
        }
        return 0;
    }
}
