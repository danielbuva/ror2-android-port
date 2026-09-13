using System.Reflection;
using System.Reflection.Metadata;
using System.Reflection.PortableExecutable;
using System.Text.Json;
var results = new List<object>();
foreach (var file in Directory.GetFiles(args[0], "*.dll").Order()) {
 try {
 using var stream = File.OpenRead(file); using var pe = new PEReader(stream);
 if (!pe.HasMetadata) continue;
 var r = pe.GetMetadataReader(); var a = r.GetAssemblyDefinition();
 string TypeName(TypeDefinition t) => r.GetString(t.Namespace)+"."+r.GetString(t.Name);
 var types = new List<object>(); var imports = new List<object>();
 foreach(var th in r.TypeDefinitions) {
  var t = r.GetTypeDefinition(th); var tn=TypeName(t);
  var methods=new List<string>(); var fields=new List<string>();
  foreach(var mh in t.GetMethods()) {
   var m=r.GetMethodDefinition(mh); string name=r.GetString(m.Name);
   methods.Add(name+":"+Convert.ToHexString(r.GetBlobBytes(m.Signature)));
   if((m.Attributes & MethodAttributes.PinvokeImpl)!=0) {
    var i=m.GetImport(); imports.Add(new {type=tn,method=name,library=r.GetString(r.GetModuleReference(i.Module).Name),entry=r.GetString(i.Name)});
   }
  }
  foreach(var fh in t.GetFields()) {var f=r.GetFieldDefinition(fh); fields.Add(r.GetString(f.Name)+":"+Convert.ToHexString(r.GetBlobBytes(f.Signature)));}
  types.Add(new {name=tn,methods,fields,compilerGenerated=tn.Contains('<')});
 }
 var refs=r.AssemblyReferences.Select(h=>r.GetAssemblyReference(h)).Select(x=>new{name=r.GetString(x.Name),version=x.Version.ToString()}).ToArray();
 var members=r.MemberReferences.Select(h=>r.GetMemberReference(h)).Select(x=>{
  string parent=x.Parent.Kind==HandleKind.TypeReference ? r.GetString(r.GetTypeReference((TypeReferenceHandle)x.Parent).Namespace)+"."+r.GetString(r.GetTypeReference((TypeReferenceHandle)x.Parent).Name) : x.Parent.Kind.ToString();
  return parent+"::"+r.GetString(x.Name);
 }).Distinct().Order().ToArray();
 results.Add(new {file=Path.GetFileName(file),name=r.GetString(a.Name),version=a.Version.ToString(),machine=pe.PEHeaders.CoffHeader.Machine.ToString(),corflags=pe.PEHeaders.CorHeader!.Flags.ToString(),references=refs,types,pinvokes=imports,memberReferences=members});
 } catch(Exception e) {results.Add(new{file=Path.GetFileName(file),error=e.ToString()});}
}
Console.WriteLine(JsonSerializer.Serialize(results,new JsonSerializerOptions{WriteIndented=true}));
