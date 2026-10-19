using Mono.Cecil;
using Mono.Cecil.Cil;
using System.Text.Json;

// Read the Addressables label constants and content-pack provider identifiers from
// shipped IL, so the host catalog reader needs no editor reflection. Nothing is invoked.
static class CatalogNames {
 static IEnumerable<Instruction> Code(MethodDefinition method) => method.Body.Instructions.Where(i=>i.OpCode!=OpCodes.Nop);
 public static void Run(string file, string[] providerTypes) {
  using var resolver=new DefaultAssemblyResolver();resolver.AddSearchDirectory(Path.GetDirectoryName(Path.GetFullPath(file))!);
  using var assembly=AssemblyDefinition.ReadAssembly(file,new ReaderParameters{AssemblyResolver=resolver});
  var module=assembly.MainModule;
  var labelsType=module.GetType("RoR2.ContentManagement.AddressablesLabels")??throw new Exception("AddressablesLabels absent");
  var constructor=labelsType.Methods.SingleOrDefault(m=>m.IsConstructor&&m.IsStatic);
  var assigned=new Dictionary<string,string>();
  if(constructor!=null){
   var code=Code(constructor).ToArray();
   for(int i=1;i<code.Length;i++)
    if(code[i].OpCode==OpCodes.Stsfld&&code[i].Operand is FieldReference field&&field.DeclaringType.FullName==labelsType.FullName&&field.FieldType.FullName=="System.String"){
     if(code[i-1].OpCode!=OpCodes.Ldstr)throw new Exception("Label "+field.Name+" is not a string literal");
     if(!assigned.TryAdd(field.Name,(string)code[i-1].Operand))throw new Exception("Label "+field.Name+" assigned twice");
    }
  }
  var labels=labelsType.Fields.Where(f=>f.IsStatic&&f.IsPublic&&f.FieldType.FullName=="System.String").Select(f=>new{
   name=f.Name,
   key=f.HasConstant?(string)f.Constant:assigned.TryGetValue(f.Name,out var value)?value:throw new Exception("Label "+f.Name+" has no literal value")
  }).ToArray();
  var providers=providerTypes.Select(name=>{
   var type=module.GetType(name)??throw new Exception("Provider absent: "+name);
   var getter=type.Methods.SingleOrDefault(m=>m.Name=="get_identifier"&&!m.IsStatic&&m.Parameters.Count==0)??throw new Exception("Provider identifier getter absent: "+name);
   var code=Code(getter).ToArray();
   if(code.Length!=2||code[0].OpCode!=OpCodes.Ldstr||code[1].OpCode!=OpCodes.Ret)throw new Exception("Provider identifier is not a string literal: "+name);
   return new{identifier=(string)code[0].Operand,type=type.FullName+", "+assembly.Name.FullName};
  }).ToArray();
  Console.WriteLine(JsonSerializer.Serialize(new{labels,providers,scope="Read-only original IL: label literals and provider identifier literals; nothing invoked"}));
 }
}
