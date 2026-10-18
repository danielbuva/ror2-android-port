using Mono.Cecil;
using Mono.Cecil.Cil;
using System.Security.Cryptography;
using System.Text.Json;

// Read the shipped registration and startup metadata without invoking game code.
static class CatalogContract {
 static IEnumerable<TypeDefinition> Types(IEnumerable<TypeDefinition> types) {
  foreach(var t in types){yield return t;foreach(var n in Types(t.NestedTypes))yield return n;}
 }
 static object? Argument(CustomAttributeArgument arg) => arg.Value switch {
  TypeReference type => type.FullName,
  CustomAttributeArgument[] values => values.Select(Argument).ToArray(),
  _ => arg.Value
 };
 public static void Run(string file) {
  using var resolver=new DefaultAssemblyResolver();resolver.AddSearchDirectory(Path.GetDirectoryName(Path.GetFullPath(file))!);
  using var assembly=AssemblyDefinition.ReadAssembly(file,new ReaderParameters{AssemblyResolver=resolver});
  var types=Types(assembly.MainModule.Types).ToArray();
  bool Provider(TypeReference type) => type.Resolve().Interfaces.Any(i=>i.InterfaceType.FullName=="RoR2.ContentManagement.IContentPackProvider");
  var registrations=types.Where(t=>t.FullName=="RoR2.RoR2Application"||t.FullName.StartsWith("RoR2.RoR2Application/"))
   .SelectMany(t=>t.Methods).Where(m=>m.HasBody&&m.Body.Instructions.Any(i=>i.Operand is MethodReference call&&call.DeclaringType.FullName=="RoR2.ContentManagement.ContentManager/AddContentPackProviderDelegate"&&call.Name=="Invoke"))
   .Select(m=>new{method=m,constructors=m.Body.Instructions.Where(i=>i.OpCode==OpCodes.Newobj&&i.Operand is MethodReference ctor&&Provider(ctor.DeclaringType)).Select(i=>(MethodReference)i.Operand).ToArray()})
   .Where(row=>row.constructors.Length!=0).ToArray();
  if(registrations.Length!=1)throw new Exception("Expected one measured original provider registration body");
  var registration=registrations[0];
  if(registration.constructors.Any(c=>c.Parameters.Count!=0))throw new Exception("Provider constructor requires reviewed arguments");
  var providers=registration.constructors.Select(c=>c.DeclaringType.FullName).ToArray();
  if(providers.Distinct().Count()!=providers.Length)throw new Exception("Duplicate original provider construction");
  var helperMethods=types.Where(t=>t.FullName=="RoR2.ContentManagement.AddressablesLoadHelper"||t.FullName.StartsWith("RoR2.ContentManagement.AddressablesLoadHelper/"))
   .SelectMany(t=>t.Methods).Where(m=>m.HasBody&&m.Body.Instructions.Any(i=>i.Operand is MethodReference call&&call.Name=="FindLocationsThenAddLoadOperation")).ToArray();
  var categories=helperMethods.SelectMany(m=>m.Body.Instructions).Where(i=>i.OpCode==OpCodes.Ldsfld&&i.Operand is FieldReference field&&field.DeclaringType.FullName=="RoR2.ContentManagement.AddressablesLabels")
   .Select(i=>((FieldReference)i.Operand).Name).Distinct().ToArray();
  if(categories.Length==0)throw new Exception("No measured original content categories");
  var initializers=types.SelectMany(t=>t.Methods).SelectMany(m=>m.CustomAttributes.Where(a=>a.AttributeType.FullName is "RoR2.SystemInitializerAttribute" or "RoR2.InitDuringStartupPhaseAttribute")
   .Select(a=>new{method=m.FullName,isStatic=m.IsStatic,attribute=a.AttributeType.FullName,arguments=a.ConstructorArguments.Select(Argument).ToArray(),body=MigrationSurface.Body(m)})).ToArray();
  var phase=types.SingleOrDefault(t=>t.FullName=="RoR2.GameInitPhase");
  // Conservative runtime edges: exact shipped literals are matched against the
  // original catalog by the converter. A match is not proof of execution.
  var assetKeyCandidates=types.SelectMany(t=>t.Methods).Where(m=>m.HasBody)
   .SelectMany(m=>m.Body.Instructions.Where(i=>i.OpCode==OpCodes.Ldstr).Select(i=>new{key=(string)i.Operand,method=m.FullName}))
   .GroupBy(row=>row.key,StringComparer.Ordinal).OrderBy(group=>group.Key,StringComparer.Ordinal)
   .Select(group=>new{key=group.Key,methods=group.Select(row=>row.method).Distinct().OrderBy(name=>name,StringComparer.Ordinal).ToArray()}).ToArray();
  var legacyFile=Path.Combine(Path.GetDirectoryName(Path.GetFullPath(file))!,"LegacyResourcesAPI.dll");
  using var legacy=AssemblyDefinition.ReadAssembly(legacyFile);
  var legacyAliases=new Dictionary<string,string>(StringComparer.Ordinal);
  int legacyAssignments=0,legacyReassignments=0;
  var initializer=Types(legacy.MainModule.Types).Single(type=>type.FullName=="RoR2.LegacyResourcesAPI").Methods.Single(method=>method.IsConstructor&&method.IsStatic);
  var instructions=initializer.Body.Instructions;
  for(int i=2;i<instructions.Count;i++){
   if(instructions[i].Operand is not MethodReference setter||setter.Name!="set_Item"||!setter.DeclaringType.FullName.StartsWith("System.Collections.Generic.Dictionary`2<System.String,System.String>",StringComparison.Ordinal))continue;
   if(instructions[i-2].OpCode!=OpCodes.Ldstr||instructions[i-1].OpCode!=OpCodes.Ldstr)throw new Exception("Original legacy alias assignment requires reviewed IL");
   var alias=(string)instructions[i-2].Operand;var key=(string)instructions[i-1].Operand;
   if(string.IsNullOrEmpty(alias)||string.IsNullOrEmpty(key))throw new Exception("Original legacy alias identity is empty");
   // The shipped initializer also uses canonical addresses and intentional
   // reassignment. Preserve dictionary setter order, including the final value.
   legacyAssignments++;if(legacyAliases.ContainsKey(alias))legacyReassignments++;legacyAliases[alias]=key;
  }
  if(legacyAliases.Count==0)throw new Exception("Original legacy resource aliases absent");
  Console.WriteLine(JsonSerializer.Serialize(new{
   input_sha256=Convert.ToHexString(SHA256.HashData(File.ReadAllBytes(file))).ToLowerInvariant(),
   registrationMethod=registration.method.FullName,registrationBody=MigrationSurface.Body(registration.method),providers,categories,initializers,
   phaseValues=phase?.Fields.Where(f=>f.HasConstant).ToDictionary(f=>f.Name,f=>f.Constant),assetKeyCandidates,legacyAliases,
   legacyInputSha256=Convert.ToHexString(SHA256.HashData(File.ReadAllBytes(legacyFile))).ToLowerInvariant(),legacyAssignments,legacyReassignments,
   scope="Read-only original IL/metadata; no provider, initializer, ownership or platform service invoked"
  }));
 }
}
