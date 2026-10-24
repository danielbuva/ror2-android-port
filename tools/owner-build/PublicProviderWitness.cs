using System;
using System.IO;
using System.Runtime.CompilerServices;
using System.Security.Cryptography;
using System.Text.Json;

internal static class BuildToolProviderWitness
{
    [ModuleInitializer]
    internal static void Check()
    {
        var provider = typeof(Mono.Cecil.ModuleDefinition).Assembly;
        var path = provider.Location;
        var actual = Convert.ToHexString(SHA256.HashData(File.ReadAllBytes(path))).ToLowerInvariant();
        var expected = Environment.GetEnvironmentVariable("ROR2LAB_CECIL_SHA256");
        if (expected == null || actual != expected)
            throw new InvalidOperationException("Build-tool Cecil provider hash differs");
        Console.Error.WriteLine("CECIL_PROVIDER_WITNESS " + JsonSerializer.Serialize(new {
            path, sha256 = actual, identity = provider.FullName,
            runtime_version = Environment.Version.ToString()
        }));
    }
}
