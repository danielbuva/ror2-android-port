using Mono.Cecil;

var input = Path.GetFullPath(args[0]);
var output = Path.GetFullPath(args[1]);
using var assembly = AssemblyDefinition.ReadAssembly(input, new ReaderParameters { InMemory = true, ReadWrite = false });
var method = assembly.MainModule.Types.Single(t => t.Name == "ShapeFixture").Methods.Single(m => m.Name == "SzArray");
var array = new ArrayType(assembly.MainModule.TypeSystem.Int32);
array.Dimensions[0] = new ArrayDimension(0, null);
if (array.IsVector) throw new InvalidDataException("Fixture mutation did not create a rank-one non-vector array");
method.Parameters[0].ParameterType = array;
assembly.Write(output);
