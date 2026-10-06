using Mono.Cecil;
using Mono.Cecil.Cil;
using System.Security.Cryptography;
using System.Text.Json;

// Exact-input optional presentation boundaries. Gameplay/state/charge/entitlements are untouched.
static class OptionalPresentationGuard {
 public static void Run(string[] args) {
  string Hash(string p)=>Convert.ToHexString(SHA256.HashData(File.ReadAllBytes(p))).ToLowerInvariant();
  var input=args[0];var output=args[1];var expected=args[2];
  if(Hash(input)!=expected||expected!="0497a902a7aaf3c97fa2f1251a5364723b0c1b422839f7002a4b5f9c02563e4f")throw new Exception("Optional guard requires the measured original input");
  if(Path.GetFullPath(input)==Path.GetFullPath(output)||File.Exists(output))throw new Exception("Require new distinct output");
  var resolver=new DefaultAssemblyResolver();resolver.AddSearchDirectory(Path.GetDirectoryName(Path.GetFullPath(input))!);resolver.AddSearchDirectory(args[3]);
  using var assembly=AssemblyDefinition.ReadAssembly(input,new ReaderParameters{AssemblyResolver=resolver});
  IEnumerable<TypeDefinition> Types(IEnumerable<TypeDefinition> ts){foreach(var t in ts){yield return t;foreach(var child in Types(t.NestedTypes))yield return child;}}
  string Fingerprint(MethodDefinition m){
   if(!m.HasBody)return "no-body";
   var body=m.Body.Instructions;
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
  var before=Types(assembly.MainModule.Types).SelectMany(t=>t.Methods).ToDictionary(m=>m.FullName,Fingerprint);
  var audio=assembly.MainModule.Types.Single(t=>t.FullName=="RoR2.WwiseIntegrationManager").Methods.Single(m=>m.Name=="get_noAudio");
  if(audio.Body.Instructions.Count!=2||audio.Body.Instructions[0].OpCode!=OpCodes.Ldc_I4_0||audio.Body.Instructions[1].OpCode!=OpCodes.Ret)throw new Exception("noAudio input contract changed");
  audio.Body.Instructions[0].OpCode=OpCodes.Ldc_I4_1;
  var sound=assembly.MainModule.Types.Single(t=>t.FullName=="RoR2.Util").Methods.Single(m=>m.Name=="PlaySound"&&m.Parameters.Count==2&&m.Parameters[0].ParameterType.FullName=="System.String"&&m.Parameters[1].ParameterType.FullName=="UnityEngine.GameObject");
  if(!sound.IsStatic||sound.ReturnType.FullName!="System.UInt32"||!sound.Body.Instructions.Any(i=>i.Operand is MethodReference mr&&mr.DeclaringType.Name=="AkSoundEngine"&&mr.Name=="PostEvent"))throw new Exception("Original PlaySound native contract changed");
  var il=sound.Body.GetILProcessor();var original=sound.Body.Instructions[0];
  il.InsertBefore(original,il.Create(OpCodes.Call,audio));il.InsertBefore(original,il.Create(OpCodes.Brfalse,original));il.InsertBefore(original,il.Create(OpCodes.Ldc_I4_0));il.InsertBefore(original,il.Create(OpCodes.Ret));
  var landing=assembly.MainModule.Types.Single(t=>t.FullName=="RoR2.GlobalEventManager").Methods.Single(m=>m.Name=="OnCharacterHitGroundSFX");
  if(landing.ReturnType.FullName!="System.Void"||landing.Parameters.Count!=3||!landing.Body.Instructions.Any(i=>i.Operand is MethodReference mr&&mr.DeclaringType.Name=="AkSoundEngine"&&mr.Name=="SetSwitch"))throw new Exception("Original optional landing SFX contract changed");
  il=landing.Body.GetILProcessor();original=landing.Body.Instructions[0];il.InsertBefore(original,il.Create(OpCodes.Call,audio));il.InsertBefore(original,il.Create(OpCodes.Brfalse,original));il.InsertBefore(original,il.Create(OpCodes.Ret));
  var teleporter=assembly.MainModule.Types.Single(t=>t.FullName=="RoR2.TeleporterInteraction");var fixedUpdate=teleporter.Methods.Single(m=>m.Name=="FixedUpdate");
  var instructions=fixedUpdate.Body.Instructions;
  var profiles=instructions.Where(i=>i.Operand is MethodReference mr&&mr.Name=="get_userProfile").ToArray();
  if(profiles.Length!=2)throw new Exception("Original two optional profile consumers changed");
  var profileLoad=profiles[0]; // Discovery indicator; particle-scaling consumer already null-checks.
  var userLoad=profileLoad.Previous;var userThis=userLoad.Previous;
  if(userLoad.OpCode!=OpCodes.Ldfld||userLoad.Operand is not FieldReference user||user.Name!="cachedLocalUser"||userThis.OpCode!=OpCodes.Ldarg_0)throw new Exception("Original discovery profile contract changed");
  var pings=instructions.Single(i=>i.Operand is FieldReference field&&field.Name=="currentPings");
  if(pings.Previous.OpCode!=OpCodes.Ldarg_0)throw new Exception("Original ping presentation branch changed");
  il=fixedUpdate.Body.GetILProcessor();il.InsertBefore(userThis,il.Create(OpCodes.Ldarg_0));il.InsertBefore(userThis,il.Create(OpCodes.Ldfld,user));il.InsertBefore(userThis,il.Create(OpCodes.Brfalse,pings.Previous));
  // Silent PlaySound returns ID0. Retain state exit/cleanup while omitting native
  // stop calls when the same explicit no-audio boundary is active.
  var lunarStops=new[]{("EntityStates.LunarWisp.ChargeLunarGuns",1),("EntityStates.LunarWisp.FireLunarGuns",2),("EntityStates.LunarWisp.SeekingBomb",1),("EntityStates.LunarGolem.ChargeTwinShot",1)};
  var lunarMethods=new List<MethodDefinition>();
  foreach(var (typeName,count) in lunarStops){
   var exit=assembly.MainModule.Types.Single(t=>t.FullName==typeName).Methods.Single(m=>m.Name=="OnExit");
   var calls=exit.Body.Instructions.Where(i=>i.OpCode==OpCodes.Call&&i.Operand is MethodReference mr&&mr.DeclaringType.Name=="AkSoundEngine"&&mr.Name=="StopPlayingID"&&mr.ReturnType.FullName=="System.Void"&&mr.Parameters.Count==1&&mr.Parameters[0].ParameterType.FullName=="System.UInt32").ToArray();
   if(calls.Length!=count||calls.Any(i=>i.Previous.OpCode!=OpCodes.Ldfld||i.Previous.Operand is not FieldReference f||f.FieldType.FullName!="System.UInt32"||f.DeclaringType.FullName!=typeName||i.Next==null))throw new Exception("Original lunar optional sound-stop contract changed: "+typeName);
   il=exit.Body.GetILProcessor();
   foreach(var stop in calls){var afterStop=stop.Next;il.InsertBefore(stop,il.Create(OpCodes.Call,audio));il.InsertBefore(stop,il.Create(OpCodes.Brfalse,stop));il.InsertBefore(stop,il.Create(OpCodes.Pop));il.InsertBefore(stop,il.Create(OpCodes.Br,afterStop));}
   lunarMethods.Add(exit);
  }
  var countdown=assembly.MainModule.Types.Single(t=>t.FullName=="RoR2.EscapeSequenceController").Methods.Single(m=>m.Name=="SetCountdownTime");
  var rtpcCalls=countdown.Body.Instructions.Where(i=>i.OpCode==OpCodes.Call&&i.Operand is MethodReference mr&&mr.DeclaringType.Name=="AkSoundEngine"&&mr.Name=="SetRTPCValue").ToArray();
  if(rtpcCalls.Length!=1||rtpcCalls[0].Operand is not MethodReference rtpc||rtpc.ReturnType.Name!="AKRESULT"||rtpc.Parameters.Count!=2||rtpc.Parameters[0].ParameterType.FullName!="System.String"||rtpc.Parameters[1].ParameterType.FullName!="System.Single"||rtpcCalls[0].Next.OpCode!=OpCodes.Pop)throw new Exception("Original escape countdown audio contract changed");
  // Preserve original HUD countdown and argument calculations. No fabricated
  // audio success code: discard the two arguments only on the no-audio path.
  il=countdown.Body.GetILProcessor();var rtpcCall=rtpcCalls[0];var afterRtpc=rtpcCall.Next.Next;
  il.InsertBefore(rtpcCall,il.Create(OpCodes.Call,audio));il.InsertBefore(rtpcCall,il.Create(OpCodes.Brfalse,rtpcCall));
  il.InsertBefore(rtpcCall,il.Create(OpCodes.Pop));il.InsertBefore(rtpcCall,il.Create(OpCodes.Pop));il.InsertBefore(rtpcCall,il.Create(OpCodes.Br,afterRtpc));
  // Insertion can move targets beyond the signed-byte range; keep branch semantics exactly.
  foreach(var m in new[]{sound,landing,fixedUpdate,countdown}.Concat(lunarMethods))foreach(var instruction in m.Body.Instructions) {
   if(instruction.OpCode==OpCodes.Br_S)instruction.OpCode=OpCodes.Br;
   else if(instruction.OpCode==OpCodes.Brfalse_S)instruction.OpCode=OpCodes.Brfalse;
   else if(instruction.OpCode==OpCodes.Brtrue_S)instruction.OpCode=OpCodes.Brtrue;
  }
  assembly.Write(output);
  var changed=new[]{audio.FullName,sound.FullName,landing.FullName,fixedUpdate.FullName,countdown.FullName}.Concat(lunarMethods.Select(m=>m.FullName)).ToArray();
  using var verified=AssemblyDefinition.ReadAssembly(output,new ReaderParameters{AssemblyResolver=resolver});
  var after=Types(verified.MainModule.Types).SelectMany(t=>t.Methods).ToDictionary(m=>m.FullName,Fingerprint);
  if(before.Count!=after.Count||before.Any(pair=>!after.ContainsKey(pair.Key)||(!changed.Contains(pair.Key)&&pair.Value!=after[pair.Key]))||changed.Any(name=>before[name]==after[name]))throw new Exception("Unexpected method addition/removal or change outside optional presentation");
  Console.WriteLine(JsonSerializer.Serialize(new{input_sha256=expected,output_sha256=Hash(output),methods=changed,unchanged_method_bodies=before.Count-changed.Length,scope="noAudio true; PlaySound returns invalid ID0 only when audio unavailable; optional discovery profile null guard; optional landing sound/effects unavailable (server fall damage unchanged); five lunar native sound-stop calls and one escape countdown RTPC call bypassed only when audio unavailable, retaining original state exit/cleanup/HUD countdown. Original gameplay, original sound bodies otherwise, ownership/authentication unchanged."}));
 }
}
