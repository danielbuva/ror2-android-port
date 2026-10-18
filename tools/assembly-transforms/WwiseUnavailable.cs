using Mono.Cecil;
using Mono.Cecil.Cil;
using System.Security.Cryptography;
using System.Text.Json;

// Local, input-gated Android no-audio boundary. The native engine is absent;
// this does not report a successful audio event or initialized sound engine.
static class WwiseUnavailable {
 static string Hash(string path) => Convert.ToHexString(SHA256.HashData(File.ReadAllBytes(path))).ToLowerInvariant();
 static IEnumerable<TypeDefinition> Types(IEnumerable<TypeDefinition> types) {
  foreach(var type in types) {yield return type;foreach(var nested in Types(type.NestedTypes))yield return nested;}
 }
 static string Fingerprint(MethodDefinition method) {
  if(!method.HasBody)return "no-body";
  var body=method.Body.Instructions;
  string Operand(object? value)=>value switch {
   Instruction target=>"instruction:"+body.IndexOf(target),
   Instruction[] targets=>string.Join(",",targets.Select(x=>body.IndexOf(x))),
   MemberReference member=>member.FullName,
   VariableDefinition variable=>"variable:"+variable.Index,
   ParameterDefinition parameter=>"parameter:"+parameter.Index,
   null=>"",_=>value.ToString()??""
  };
  return string.Join("\n",body.Select(i=>i.OpCode.Name+" "+Operand(i.Operand)));
 }
 static string[] Contracts(AssemblyDefinition assembly)=>Types(assembly.MainModule.Types)
  .SelectMany(t=>new[]{"type:"+t.FullName+"|"+t.BaseType?.FullName}
   .Concat(t.Fields.Select(f=>"field:"+f.FullName))
   .Concat(t.Methods.Select(m=>"method:"+m.FullName))).OrderBy(x=>x).ToArray();
 public static void Run(string[] args) {
  if(args.Length!=7)throw new Exception("Expected API input/output/hash, MonoBehaviour input/output/hash, resolver directory");
  var apiInput=args[0];var apiOutput=args[1];var monoInput=args[3];var monoOutput=args[4];
  if(Hash(apiInput)!=args[2]||Hash(monoInput)!=args[5]||
     args[2]!="564b74ec232e81af8fa4b65c17537a4d05890d9181281eab0bc28bd441a3a781"||
     args[5]!="f0449ab6ca73eb34d44fe2cf72f7e2f4bca5e35fd56ef7fa380787b738c66da7")
   throw new Exception("Reviewed Wwise input identity changed");
  if(File.Exists(apiOutput)||File.Exists(monoOutput)||Path.GetFullPath(apiInput)==Path.GetFullPath(apiOutput)||Path.GetFullPath(monoInput)==Path.GetFullPath(monoOutput))
   throw new Exception("Require new, distinct local outputs");
  var resolver=new DefaultAssemblyResolver();
  resolver.AddSearchDirectory(Path.GetDirectoryName(Path.GetFullPath(apiInput))!);
  resolver.AddSearchDirectory(Path.GetDirectoryName(Path.GetFullPath(monoInput))!);
  resolver.AddSearchDirectory(args[6]);
  using var api=AssemblyDefinition.ReadAssembly(apiInput,new ReaderParameters{AssemblyResolver=resolver});
  using var mono=AssemblyDefinition.ReadAssembly(monoInput,new ReaderParameters{AssemblyResolver=resolver});
  var apiIdentity=api.Name.FullName;var monoIdentity=mono.Name.FullName;
  var apiMvid=api.MainModule.Mvid;var monoMvid=mono.MainModule.Mvid;
  var apiContracts=Contracts(api);var monoContracts=Contracts(mono);
  var apiBefore=Types(api.MainModule.Types).SelectMany(t=>t.Methods).ToDictionary(m=>m.FullName,Fingerprint);
  var monoBefore=Types(mono.MainModule.Types).SelectMany(t=>t.Methods).ToDictionary(m=>m.FullName,Fingerprint);
  var initialized=api.MainModule.Types.Single(t=>t.FullName=="AkSoundEngine").Methods.Single(m=>m.Name=="IsInitialized"&&m.Parameters.Count==0);
  if(initialized.ReturnType.FullName!="System.Boolean"||initialized.Body.Instructions.Count!=2||
     initialized.Body.Instructions[0].OpCode!=OpCodes.Call||initialized.Body.Instructions[0].Operand is not MethodReference native||
     native.DeclaringType.FullName!="AkSoundEnginePINVOKE"||native.Name!="CSharp_IsInitialized"||
     initialized.Body.Instructions[1].OpCode!=OpCodes.Ret)throw new Exception("Original native initialization query changed");
  initialized.Body.Instructions[0].OpCode=OpCodes.Ldc_I4_0;
  initialized.Body.Instructions[0].Operand=null;
  // Loader's original charge state (and other source states) updates an RTPC
  // by playing ID each fixed tick. Preserve the original call when an engine
  // exists; report the shipped not-initialized result on this no-audio build.
  var akResult=api.MainModule.Types.Single(t=>t.FullName=="AKRESULT");
  var notInitialized=akResult.Fields.Single(f=>f.Name=="AK_NotInitialized");
  if(!notInitialized.HasConstant||Convert.ToInt32(notInitialized.Constant)!=102)throw new Exception("Original Wwise unavailable result changed");
  var rtpc=api.MainModule.Types.Single(t=>t.FullName=="AkSoundEngine").Methods.Single(m=>m.Name=="SetRTPCValueByPlayingID"&&m.Parameters.Select(p=>p.ParameterType.FullName).SequenceEqual(new[]{"System.String","System.Single","System.UInt32"}));
  if(rtpc.ReturnType.FullName!="AKRESULT"||rtpc.Body.Instructions.Count!=5||rtpc.Body.Instructions[0].OpCode!=OpCodes.Ldarg_0||rtpc.Body.Instructions[1].OpCode!=OpCodes.Ldarg_1||rtpc.Body.Instructions[2].OpCode!=OpCodes.Ldarg_2||rtpc.Body.Instructions[3].OpCode!=OpCodes.Call||rtpc.Body.Instructions[3].Operand is not MethodReference rtpcNative||rtpcNative.DeclaringType.FullName!="AkSoundEnginePINVOKE"||rtpcNative.Name!="CSharp_SetRTPCValueByPlayingID__SWIG_7"||rtpc.Body.Instructions[4].OpCode!=OpCodes.Ret)throw new Exception("Original Wwise RTPC-by-playing-ID contract changed");
  var rtpcIl=rtpc.Body.GetILProcessor();var rtpcOriginal=rtpc.Body.Instructions[0];
  rtpcIl.InsertBefore(rtpcOriginal,rtpcIl.Create(OpCodes.Call,initialized));
  rtpcIl.InsertBefore(rtpcOriginal,rtpcIl.Create(OpCodes.Brtrue,rtpcOriginal));
  rtpcIl.InsertBefore(rtpcOriginal,rtpcIl.Create(OpCodes.Ldc_I4,102));
  rtpcIl.InsertBefore(rtpcOriginal,rtpcIl.Create(OpCodes.Ret));
  var stopPlaying=api.MainModule.Types.Single(t=>t.FullName=="AkSoundEngine").Methods.Single(m=>m.Name=="StopPlayingID"&&m.Parameters.Count==1&&m.Parameters[0].ParameterType.FullName=="System.UInt32");
  if(stopPlaying.ReturnType.FullName!="System.Void"||stopPlaying.Body.Instructions.Count!=3||stopPlaying.Body.Instructions[0].OpCode!=OpCodes.Ldarg_0||stopPlaying.Body.Instructions[1].OpCode!=OpCodes.Call||stopPlaying.Body.Instructions[1].Operand is not MethodReference stopNative||stopNative.DeclaringType.FullName!="AkSoundEnginePINVOKE"||stopNative.Name!="CSharp_StopPlayingID__SWIG_2"||stopPlaying.Body.Instructions[2].OpCode!=OpCodes.Ret)throw new Exception("Original Wwise stop-by-playing-ID contract changed");
  var stopIl=stopPlaying.Body.GetILProcessor();var stopOriginal=stopPlaying.Body.Instructions[0];
  stopIl.InsertBefore(stopOriginal,stopIl.Create(OpCodes.Call,initialized));
  stopIl.InsertBefore(stopOriginal,stopIl.Create(OpCodes.Brtrue,stopOriginal));
  stopIl.InsertBefore(stopOriginal,stopIl.Create(OpCodes.Ret));
  var imported=mono.MainModule.ImportReference(initialized);
  var gameObj=mono.MainModule.Types.Single(t=>t.FullName=="AkGameObj");
  var setPosition=gameObj.Methods.Single(m=>m.Name=="SetPosition"&&m.Parameters.Count==0);
  if(setPosition.ReturnType.FullName!="System.Void"||setPosition.Body.Instructions.Count(i=>i.Operand is MethodReference mr&&mr.DeclaringType.FullName=="AkSoundEngine"&&mr.Name=="SetObjectPosition")!=2)
   throw new Exception("Original AkGameObj position contract changed");
  var eventType=mono.MainModule.Types.Single(t=>t.FullName=="AkEvent");
  var handle=eventType.Methods.Single(m=>m.Name=="HandleEvent"&&m.Parameters.Count==1&&m.Parameters[0].ParameterType.FullName=="UnityEngine.GameObject");
  var stop=eventType.Methods.Single(m=>m.Name=="Stop"&&m.Parameters.Count==2);
  if(handle.ReturnType.FullName!="System.Void"||!handle.Body.Instructions.Any(i=>i.Operand is MethodReference mr&&mr.Name=="Post")||
     stop.ReturnType.FullName!="System.Void"||!stop.Body.Instructions.Any(i=>i.Operand is MethodReference mr&&mr.Name=="Stop"))
   throw new Exception("Original AkEvent callback contract changed");
  foreach(var method in new[]{setPosition,handle,stop}) {
   var il=method.Body.GetILProcessor();var original=method.Body.Instructions[0];
   il.InsertBefore(original,il.Create(OpCodes.Call,imported));
   il.InsertBefore(original,il.Create(OpCodes.Brtrue,original));
   il.InsertBefore(original,il.Create(OpCodes.Ret));
  }
  api.Write(apiOutput);mono.Write(monoOutput);
  using var apiCheck=AssemblyDefinition.ReadAssembly(apiOutput,new ReaderParameters{AssemblyResolver=resolver});
  using var monoCheck=AssemblyDefinition.ReadAssembly(monoOutput,new ReaderParameters{AssemblyResolver=resolver});
  var changedApi=new[]{initialized.FullName,rtpc.FullName,stopPlaying.FullName};var changedMono=new[]{setPosition.FullName,handle.FullName,stop.FullName};
  void Verify(AssemblyDefinition output,string identity,Guid mvid,string[] contracts,Dictionary<string,string> before,string[] changed) {
   if(output.Name.FullName!=identity||output.MainModule.Mvid!=mvid||!contracts.SequenceEqual(Contracts(output)))throw new Exception("Wwise assembly identity/contract changed");
   var after=Types(output.MainModule.Types).SelectMany(t=>t.Methods).ToDictionary(m=>m.FullName,Fingerprint);
   if(before.Count!=after.Count||before.Any(pair=>!after.ContainsKey(pair.Key)||(!changed.Contains(pair.Key)&&pair.Value!=after[pair.Key]))||changed.Any(name=>before[name]==after[name]))
    throw new Exception("Unexpected Wwise method change");
  }
  Verify(apiCheck,apiIdentity,apiMvid,apiContracts,apiBefore,changedApi);
  Verify(monoCheck,monoIdentity,monoMvid,monoContracts,monoBefore,changedMono);
  Console.WriteLine(JsonSerializer.Serialize(new{api_input_sha256=args[2],api_output_sha256=Hash(apiOutput),mono_input_sha256=args[5],mono_output_sha256=Hash(monoOutput),methods=changedApi.Concat(changedMono),assembly_identities_preserved=true,scope="Native audio unavailable: IsInitialized false; dynamically created AkGameObj positional audio and AkEvent playback/stop skip native calls. RTPC-by-playing-ID reports AK_NotInitialized and stop-by-playing-ID skips only when the sound engine is absent. No sound or ownership success synthesized."}));
 }
}
