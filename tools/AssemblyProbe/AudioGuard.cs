using Mono.Cecil;
using Mono.Cecil.Cil;
using System.Security.Cryptography;
using System.Text.Json;

// Input-gated local experiment. No native or platform success is synthesized.
static class AudioGuard {
 public static void Run(string[] args) {
  var input=args[0];var output=args[1];var expected=args[2];
  string Hash(string p)=>Convert.ToHexString(SHA256.HashData(File.ReadAllBytes(p))).ToLowerInvariant();
  if(Hash(input)!=expected)throw new Exception("Audio guard input hash mismatch");
  if(Path.GetFullPath(input)==Path.GetFullPath(output)||File.Exists(output))throw new Exception("Output must be a new distinct local file");
  var resolver=new DefaultAssemblyResolver();
  resolver.AddSearchDirectory(Path.GetDirectoryName(Path.GetFullPath(input))!);
  resolver.AddSearchDirectory(args[3]);
  using var a=AssemblyDefinition.ReadAssembly(input,new ReaderParameters {AssemblyResolver=resolver});
  var method=a.MainModule.Types.Single(t=>t.FullName=="RoR2.WwiseIntegrationManager").Methods.Single(m=>m.Name=="get_noAudio");
  if(!method.IsStatic||method.ReturnType.FullName!="System.Boolean"||method.Parameters.Count!=0||method.Body.Instructions.Count!=2||method.Body.Instructions[0].OpCode!=OpCodes.Ldc_I4_0||method.Body.Instructions[1].OpCode!=OpCodes.Ret)throw new Exception("Unexpected noAudio getter contract");
  method.Body.Instructions[0].OpCode=OpCodes.Ldc_I4_1;
  a.Write(output);
  Console.WriteLine(JsonSerializer.Serialize(new {input_sha256=expected,output_sha256=Hash(output),method=method.FullName,change="ldc.i4.0 to ldc.i4.1; audio explicitly unavailable",scope="Early optional audio only; no native/service success"}));
 }
}
