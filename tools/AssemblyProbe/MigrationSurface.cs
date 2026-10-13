using Mono.Cecil;
using Mono.Cecil.Cil;
using System.Globalization;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;

// Read-only update comparison. Symbolic operands avoid mistaking metadata-token
// renumbering for a gameplay change. Matching fingerprints are not runtime proof.
static class MigrationSurface {
 public static void Compare(string[] args){
  using var resolver=new DefaultAssemblyResolver();resolver.AddSearchDirectory(args[2]);
  using var left=AssemblyDefinition.ReadAssembly(args[0],new ReaderParameters{AssemblyResolver=resolver});
  using var right=AssemblyDefinition.ReadAssembly(args[1],new ReaderParameters{AssemblyResolver=resolver});
  using var l=JsonDocument.Parse(Json(Surface(left)));using var r=JsonDocument.Parse(Json(Surface(right)));
  var lt=l.RootElement.GetProperty("types").EnumerateArray().ToDictionary(t=>t.GetProperty("name").GetString()!);
  var rt=r.RootElement.GetProperty("types").EnumerateArray().ToDictionary(t=>t.GetProperty("name").GetString()!);
  bool contracts=left.Name.FullName==right.Name.FullName&&left.MainModule.Mvid==right.MainModule.Mvid&&lt.Keys.SequenceEqual(rt.Keys)&&l.RootElement.GetProperty("references").ToString()==r.RootElement.GetProperty("references").ToString();
  var changed=new List<string>();int same=0;
  foreach(var pair in lt){
   if(!rt.TryGetValue(pair.Key,out var other)){contracts=false;continue;}
   foreach(var field in new[]{"contract","fieldOrder","fields"})contracts&=pair.Value.GetProperty(field).ToString()==other.GetProperty(field).ToString();
   var methods=pair.Value.GetProperty("methods").EnumerateArray().ToDictionary(m=>m.GetProperty("name").GetString()!);
   var newer=other.GetProperty("methods").EnumerateArray().ToDictionary(m=>m.GetProperty("name").GetString()!);contracts&=methods.Keys.SequenceEqual(newer.Keys);
   foreach(var method in methods){if(!newer.TryGetValue(method.Key,out var value)){contracts=false;continue;}contracts&=method.Value.GetProperty("contract").GetString()==value.GetProperty("contract").GetString();if(method.Value.GetProperty("body").GetString()==value.GetProperty("body").GetString())same++;else changed.Add(method.Key);}
  }
  Console.WriteLine(Json(new{contracts_preserved=contracts,unchanged_methods=same,changed_methods=changed}));if(!contracts)throw new Exception("Assembly contract divergence");
 }
 static string Hash(string value) => Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(value))).ToLowerInvariant();
 static string Json(object? value) => JsonSerializer.Serialize(value);
 static string Value(object? value) => value switch {
  null => "null", TypeReference t => Type(t),
  CustomAttributeArgument a => Type(a.Type)+":"+Value(a.Value),
  CustomAttributeArgument[] a => Json(a.Select(x=>Value(x))),
  IFormattable f => f.ToString(null,CultureInfo.InvariantCulture),
  _ => Json(value)
 };
 static string Type(TypeReference t) => t.FullName+"@"+(t.Scope?.Name??"");
 static string[] Attributes(ICustomAttributeProvider owner) => owner.CustomAttributes.Select(a =>
  Type(a.AttributeType)+"("+Json(a.ConstructorArguments.Select(x=>Value(x)))+")"+
  Json(a.Fields.Select(f=>"field:"+f.Name+"="+Value(f.Argument)).Concat(a.Properties.Select(p=>"property:"+p.Name+"="+Value(p.Argument))).OrderBy(x=>x))).OrderBy(x=>x).ToArray();
 static string[] Generics(IGenericParameterProvider owner) => owner.GenericParameters.Select(g =>
  g.Position+":"+g.Attributes+":"+Json(g.Constraints.Select(c=>Type(c.ConstraintType)).OrderBy(x=>x))+":"+Json(Attributes(g))).ToArray();
 static IEnumerable<TypeDefinition> Types(IEnumerable<TypeDefinition> types) {
  foreach(var t in types){yield return t;foreach(var n in Types(t.NestedTypes))yield return n;}
 }
 static string Operand(object? value, Mono.Cecil.Cil.MethodBody body) => value switch {
  Instruction target => "instruction:"+body.Instructions.IndexOf(target),
  Instruction[] targets => Json(targets.Select(t=>body.Instructions.IndexOf(t))),
  TypeReference t => Type(t),
  MemberReference member => member.FullName+"@"+Type(member.DeclaringType),
  VariableDefinition variable => "variable:"+variable.Index,
  ParameterDefinition parameter => "parameter:"+parameter.Index,
  CallSite site => site.FullName,
  _ => Value(value)
 };
 public static string Body(MethodDefinition m) {
  if(!m.HasBody)return Hash("no-body");
  var b=m.Body;
  int Index(Instruction? i)=>i==null?-1:b.Instructions.IndexOf(i);
  return Hash(Json(new {
   b.InitLocals, locals=b.Variables.Select(v=>Type(v.VariableType)),
   instructions=b.Instructions.Select(i=>i.OpCode.Name+" "+Operand(i.Operand,b)),
   exceptions=b.ExceptionHandlers.Select(h=>new {kind=h.HandlerType.ToString(),start=Index(h.TryStart),end=Index(h.TryEnd),handler=Index(h.HandlerStart),handlerEnd=Index(h.HandlerEnd),filter=Index(h.FilterStart),type=h.CatchType==null?null:Type(h.CatchType)})
  }));
 }
 public static object Surface(AssemblyDefinition a) => new {
  name=a.Name.FullName,
  references=a.MainModule.AssemblyReferences.Select(r=>r.FullName).OrderBy(x=>x),
  types=Types(a.MainModule.Types).OrderBy(t=>t.FullName).Select(t=>new {
   name=t.FullName,
   contract=Hash(Json(new {flags=t.Attributes.ToString(),baseType=t.BaseType==null?null:Type(t.BaseType),t.PackingSize,t.ClassSize,generic=Generics(t),interfaces=t.Interfaces.Select(i=>Type(i.InterfaceType)).OrderBy(x=>x),attributes=Attributes(t)})),
   // Field order is intentionally retained: layout/serialization may depend on it.
   fieldOrder=t.Fields.Select(f=>f.Name),
   fields=t.Fields.OrderBy(f=>f.Name).Select(f=>new {name=f.Name,type=Type(f.FieldType),contract=Hash(Json(new {flags=f.Attributes.ToString(),f.Offset,constant=f.HasConstant?Value(f.Constant):null,attributes=Attributes(f),marshal=f.HasMarshalInfo?f.MarshalInfo.NativeType.ToString():null}))}),
   methods=t.Methods.OrderBy(m=>m.FullName).Select(m=>new {
    name=m.FullName,
    contract=Hash(Json(new {flags=m.Attributes.ToString(),impl=m.ImplAttributes.ToString(),calling=m.CallingConvention.ToString(),result=Type(m.ReturnType),returnAttributes=Attributes(m.MethodReturnType),generic=Generics(m),attributes=Attributes(m),overrides=m.Overrides.Select(o=>o.FullName+"@"+Type(o.DeclaringType)).OrderBy(x=>x),parameters=m.Parameters.Select(p=>new {type=Type(p.ParameterType),flags=p.Attributes.ToString(),constant=p.HasConstant?Value(p.Constant):null,attributes=Attributes(p)}),pinvoke=m.HasPInvokeInfo?m.PInvokeInfo.Module.Name+"::"+m.PInvokeInfo.EntryPoint+":"+m.PInvokeInfo.Attributes:null})),
    body=Body(m)
   })
  })
 };
 public static void Run(string[] args) {
  var reports=new List<object>();
  using var resolver=new DefaultAssemblyResolver();resolver.AddSearchDirectory(args[0]);
  foreach(var file in Directory.GetFiles(args[0],"*.dll").OrderBy(x=>x)) {
   using var a=AssemblyDefinition.ReadAssembly(file,new ReaderParameters{ReadingMode=ReadingMode.Immediate,AssemblyResolver=resolver});
   reports.Add(new {file=Path.GetFileName(file),sha256=Convert.ToHexString(SHA256.HashData(File.ReadAllBytes(file))).ToLowerInvariant(),surface=JsonSerializer.SerializeToElement(Surface(a))});
  }
  Console.WriteLine(JsonSerializer.Serialize(reports));
 }
 public static void SelfTest(string directory) {
  if(Directory.Exists(directory))throw new Exception("Require new fixture directory");
  Directory.CreateDirectory(directory);
  var hashes=new List<string>();var bytes=new List<string>();
  for(int variant=0;variant<4;variant++) {
   using var a=AssemblyDefinition.CreateAssembly(new AssemblyNameDefinition("Fixture",new Version(1,0)),"Fixture.dll",ModuleKind.Dll);
   var t=new TypeDefinition("Fixture","Alpha",TypeAttributes.Public,a.MainModule.TypeSystem.Object);
   var u=new TypeDefinition("Fixture","Beta",TypeAttributes.Public,a.MainModule.TypeSystem.Object);
   foreach(var x in variant==1?new[]{u,t}:new[]{t,u})a.MainModule.Types.Add(x);
   var target=new MethodDefinition("Target",MethodAttributes.Public|MethodAttributes.Static,a.MainModule.TypeSystem.Int32);
   target.Body.Instructions.Add(Instruction.Create(OpCodes.Ldc_I4,variant==2?43:42));target.Body.Instructions.Add(Instruction.Create(OpCodes.Ret));u.Methods.Add(target);
   var m=new MethodDefinition("Compute",MethodAttributes.Public|MethodAttributes.Static,a.MainModule.TypeSystem.Int32);
   m.Body.InitLocals=true;m.Body.Variables.Add(new VariableDefinition(variant==3?a.MainModule.TypeSystem.Int64:a.MainModule.TypeSystem.Int32));
   m.Body.Instructions.Add(Instruction.Create(OpCodes.Call,target));m.Body.Instructions.Add(Instruction.Create(OpCodes.Ret));t.Methods.Add(m);
   var file=Path.Combine(directory,variant+".dll");a.Write(file);
   using var reread=AssemblyDefinition.ReadAssembly(file);
   var methods=Types(reread.MainModule.Types).SelectMany(x=>x.Methods).OrderBy(x=>x.FullName);
   hashes.Add(Hash(Json(methods.Select(x=>new{name=x.FullName,body=Body(x)}))));
   bytes.Add(Convert.ToHexString(SHA256.HashData(File.ReadAllBytes(file))));
  }
  if(bytes[0]==bytes[1]||hashes[0]!=hashes[1])throw new Exception("Metadata-row reorder must change binary without changing symbolic IL");
  if(hashes[0]==hashes[2]||hashes[0]==hashes[3])throw new Exception("Constant/local-type changes must change method fingerprint");
  Console.WriteLine(JsonSerializer.Serialize(new{success=true,checks=new[]{"different metadata order, same symbolic IL","changed constant detected","changed local width detected"}}));
 }
}
