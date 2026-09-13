using Mono.Cecil;
using Mono.Cecil.Cil;
using System.Security.Cryptography;
using System.Text.Json;

// Copies only explicitly selected self-contained types. Does not decompile/recompile,
// alter retained method bodies, or provide a game startup/entitlement adapter.
static class Slice {
    static string Hash(byte[] b) => Convert.ToHexString(SHA256.HashData(b)).ToLowerInvariant();
    public static void Run(string[] args) {
        string input=Path.GetFullPath(args[0]), output=Path.GetFullPath(args[1]);
        string work=Path.GetFullPath("work")+Path.DirectorySeparatorChar;
        if(!output.StartsWith(work,StringComparison.Ordinal)||input==output||File.Exists(output))throw new InvalidOperationException("Slice output must be a new file under ignored work/");
        var resolver=new DefaultAssemblyResolver();resolver.AddSearchDirectory(Path.GetDirectoryName(input)!);
        using var a=AssemblyDefinition.ReadAssembly(input,new ReaderParameters { AssemblyResolver=resolver });
        var m=a.MainModule;var names=args.Skip(2).ToHashSet();
        var selected=m.Types.Where(t=>names.Contains(t.FullName)).ToArray();
        if(selected.Length!=names.Count || names.Count==0)throw new InvalidOperationException("Selected types do not match input");
        var module=m.Types.Single(t=>t.Name=="<Module>");
        if(module.HasMethods||module.HasFields)throw new InvalidOperationException("Module initializer requires separate review");
        var refs=new HashSet<string>();
        void Type(TypeReference? t) {
            if(t==null || t is GenericParameter)return;
            if(t is GenericInstanceType g)foreach(var arg in g.GenericArguments)Type(arg);
            if(t is TypeSpecification s){Type(s.ElementType);return;}
            if(t.Scope is AssemblyNameReference r)refs.Add(r.Name);
            else if(t.Scope==m && !names.Contains(t.FullName))throw new InvalidOperationException("Slice is not closed: "+t.FullName);
        }
        void Member(MemberReference? member) {
            if(member==null)return;
            if(member is TypeReference t){Type(t);return;}
            Type(member.DeclaringType);
            if(member is MethodReference method){Type(method.ReturnType);foreach(var p in method.Parameters)Type(p.ParameterType);if(method is GenericInstanceMethod g)foreach(var t2 in g.GenericArguments)Type(t2);}
            if(member is FieldReference f)Type(f.FieldType);
        }
        void Attributes(ICustomAttributeProvider owner) {
            foreach(var c in owner.CustomAttributes){
                Member(c.Constructor);
                // Primitive/enum arguments cannot introduce a hidden type reference.
                // Leave their original blobs intact; decoding enums can invoke a legacy GAC resolver.
                if(c.Constructor.Parameters.Any(p=>p.ParameterType.FullName=="System.Type"))
                    foreach(var arg in c.ConstructorArguments){Type(arg.Type);if(arg.Value is TypeReference t)Type(t);}
            }
        }
        string Body(MethodDefinition method) {
            if(!method.HasBody)return "";
            string Op(object? x)=>x switch{null=>"",Instruction i=>"offset:"+i.Offset,Instruction[] list=>string.Join(",",list.Select(i=>i.Offset)),MemberReference r=>r.FullName,ParameterDefinition p=>"p:"+p.Index,VariableDefinition v=>"v:"+v.Index,_=>x.ToString()??""};
            string text=string.Join("\n",method.Body.Instructions.Select(i=>i.OpCode.Name+" "+Op(i.Operand)));
            text+="\nlocals:"+string.Join(",",method.Body.Variables.Select(v=>v.VariableType.FullName));
            text+="\nhandlers:"+string.Join(",",method.Body.ExceptionHandlers.Select(h=>$"{h.HandlerType}:{h.TryStart?.Offset}:{h.TryEnd?.Offset}:{h.HandlerStart?.Offset}:{h.HandlerEnd?.Offset}:{h.CatchType?.FullName}"));
            return Hash(System.Text.Encoding.UTF8.GetBytes(text));
        }
        foreach(var t in selected){
            if(t.HasNestedTypes)throw new InvalidOperationException("Nested types require separate selection support");
            Type(t.BaseType);Attributes(t);foreach(var i in t.Interfaces)Type(i.InterfaceType);
            foreach(var f in t.Fields){Type(f.FieldType);Attributes(f);}
            foreach(var method in t.Methods){
                Member(method);Attributes(method);
                if(method.CustomAttributes.Any(c=>c.AttributeType.Name=="RuntimeInitializeOnLoadMethodAttribute"))throw new InvalidOperationException("Startup methods are outside slice scope");
                foreach(var o in method.Overrides)Member(o);
                if(method.HasBody){foreach(var v in method.Body.Variables)Type(v.VariableType);foreach(var i in method.Body.Instructions)if(i.Operand is MemberReference r)Member(r);foreach(var h in method.Body.ExceptionHandlers)Type(h.CatchType);}
            }
        }
        var before=selected.SelectMany(t=>t.Methods).ToDictionary(x=>x.FullName,Body);
        var removedAttributes=a.CustomAttributes.Where(c=>c.AttributeType.FullName=="HG.Reflection.SearchableAttribute/OptInAttribute").Select(c=>c.AttributeType.FullName).ToArray();
        // Full-game discovery registration does not apply to the isolated mathematical slice.
        // Preserve compiler/runtime attributes and validate their references as well.
        foreach(var c in a.CustomAttributes.ToArray())if(removedAttributes.Contains(c.AttributeType.FullName))a.CustomAttributes.Remove(c);
        Attributes(a);Attributes(m);m.Resources.Clear();
        foreach(var t in m.Types.ToArray())if(t!=module&&!names.Contains(t.FullName))m.Types.Remove(t);
        foreach(var r in m.AssemblyReferences.ToArray())if(!refs.Contains(r.Name))m.AssemblyReferences.Remove(r);
        Directory.CreateDirectory(Path.GetDirectoryName(output)!);a.Write(output);
        using var verify=AssemblyDefinition.ReadAssembly(output);
        var after=verify.MainModule.Types.SelectMany(t=>t.Methods).ToDictionary(x=>x.FullName,Body);
        if(before.Count!=after.Count||before.Any(p=>!after.TryGetValue(p.Key,out var h)||h!=p.Value))throw new InvalidOperationException("Retained method IL changed");
        Console.WriteLine(JsonSerializer.Serialize(new{success=true,inputSha256=Hash(File.ReadAllBytes(input)),outputSha256=Hash(File.ReadAllBytes(output)),assemblyIdentity=verify.Name.FullName,types=names,retainedMethods=before.Count,methodFingerprints=before,retainedMethodBodiesUnchanged=true,references=refs,removedAssemblyAttributes=removedAttributes,scope="Type-pruned method-IL preservation; no full closure or startup proof"},new JsonSerializerOptions{WriteIndented=true}));
    }
}
