"""Exercise typed method discovery and the production damage-macro setup."""

import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EDITOR = Path("/Applications/Unity/Hub/Editor/2021.3.45f2/Unity.app/Contents/MonoBleedingEdge")


def member(source, signature):
    start = source.index(signature)
    opening = source.index("{", start)
    depth = 0
    for index in range(opening, len(source)):
        depth += (source[index] == "{") - (source[index] == "}")
        if depth == 0:
            return source[start : index + 1]
    raise AssertionError(signature)


FIXTURE = r"""
using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
namespace HG.Reflection {
 public abstract class SearchableAttribute:Attribute {
  public object target {get;private set;}
  static readonly Dictionary<Type,List<SearchableAttribute>> lists=new Dictionary<Type,List<SearchableAttribute>>();
  public static List<SearchableAttribute> GetInstances<T>() {List<SearchableAttribute> value;return lists.TryGetValue(typeof(T),out value)?value:null;}
  private static void RegisterAttribute(SearchableAttribute value,object target) {
   value.target=target;
   for(var type=value.GetType();type!=null&&typeof(SearchableAttribute).IsAssignableFrom(type);type=type.BaseType) {
    if(!lists.ContainsKey(type))lists[type]=new List<SearchableAttribute>();lists[type].Add(value);
   }
  }
 }
}
[AttributeUsage(AttributeTargets.Method,AllowMultiple=true,Inherited=false)]
class DamageMacroMethodAttribute:HG.Reflection.SearchableAttribute {
 public string searchableName;public DamageMacroMethodAttribute(string name){searchableName=name;}
}
[AttributeUsage(AttributeTargets.All)] class UnrelatedAttribute:Attribute {
 public UnrelatedAttribute(){throw new Exception("unrelated attribute constructed");}
}
class DamageMacroCatalog {
 public static Dictionary<string,int> macroNameToIndexReadOnly=new Dictionary<string,int>();
 public static int Calls;
 private static void Initialize() {
  Calls++;
  foreach(var value in HG.Reflection.SearchableAttribute.GetInstances<DamageMacroMethodAttribute>()) {
   var method=(MethodInfo)value.target;
   var callback=(Func<int>)Delegate.CreateDelegate(typeof(Func<int>),method);
   macroNameToIndexReadOnly.Add(((DamageMacroMethodAttribute)value).searchableName,callback());
  }
 }
}
namespace EntityStates.Chef {
 [Unrelated] class Sear {
  [Unrelated,DamageMacroMethod("ChefFireDamage"),DamageMacroMethod("ChefBoostedFireDamage"),
   DamageMacroMethod("ChefBoostedIceDamage"),DamageMacroMethod("ChefIceDamage")]
  private static int Fire(){return 42;}
 }
}
class Base {
 [DamageMacroMethod("MidasTouch")] public static int Touch(){return 1;}
}
class Derived:Base {}
class Other {
 [DamageMacroMethod("VultureHunterLaser")] private static int Laser(){return 2;}
 [DamageMacroMethod("EngiHealMechanical")] internal static int Heal(){return 3;}
}
[AttributeUsage(AttributeTargets.Method,Inherited=false)] class MessageAttribute:Attribute {}
class Messages {
 [Message] private static void PrivateHandler(){}
 [Message] public void InvalidInstanceHandler(){}
}
class Coordinator {
 public Runtime r=new Runtime();public bool stageSourceObjects=true;
 public void Check(bool yes,string message){if(!yes)throw new Exception(message);}
}
class Runtime {public object liveCatalogs=new object();}
class PortSession {
 static bool originalDamageMacrosReady;
 Coordinator coordinator=new Coordinator();
 public static void StaticCall(Type type,string name,params object[] arguments) {
  type.GetMethod(name,BindingFlags.Static|BindingFlags.NonPublic).Invoke(null,arguments);
 }
 DISCOVERY
 PREPARE
 static void Assert(bool yes,string message){if(!yes)throw new Exception(message);}
 static void Main() {
  var assembly=typeof(PortSession).Assembly;
  var macros=OriginalMethodAttributes<DamageMacroMethodAttribute>(assembly,assembly).ToArray();
  Assert(macros.Length==7,"duplicate assemblies or inherited methods changed the family");
  Assert(macros.Count(x=>x.Value.Name=="Fire")==4,"multiple attributes on a private method lost");
  var messages=OriginalMethodAttributes<MessageAttribute>(assembly).ToArray();
  Assert(messages.Length==2&&messages.Any(x=>!x.Value.IsStatic),"invalid instance contract must remain visible");
  Assert(messages.Any(x=>x.Value.IsPrivate&&x.Value.IsStatic),"private handler missing");
  // An explicit diagnostic may already have registered all attributes on one method.
  foreach(var pair in macros.Where(x=>x.Value.Name=="Fire"))
   StaticCall(typeof(HG.Reflection.SearchableAttribute),"RegisterAttribute",pair.Key,pair.Value);
  var owner=new PortSession();owner.PrepareOriginalDamageMacros();owner.PrepareOriginalDamageMacros();
  Assert(DamageMacroCatalog.Calls==1,"native initializer repeated across sessions");
  Assert(HG.Reflection.SearchableAttribute.GetInstances<DamageMacroMethodAttribute>().Count==7,"existing methods duplicated");
  Assert(HG.Reflection.SearchableAttribute.GetInstances<HG.Reflection.SearchableAttribute>().Count==7,"native base registration lost");
  Assert(DamageMacroCatalog.macroNameToIndexReadOnly["ChefIceDamage"]==42,"native method binding lost");
  Console.WriteLine("PASS typed method discovery and native macro consumer");
 }
}
"""


class OriginalMethodDiscoveryTests(unittest.TestCase):
    def test_typed_discovery_and_native_macro_setup(self):
        mono = EDITOR / "bin/mono"
        csc = EDITOR / "lib/mono/msbuild/Current/bin/Roslyn/csc.exe"
        if not mono.is_file() or not csc.is_file():
            self.skipTest("exact editor Mono/Roslyn unavailable")
        world = (ROOT / "tools/unity/runtime/world/IntegratedWorldBoundary.cs").read_text()
        stage = (ROOT / "tools/unity/runtime/stage/IntegratedStageBoundary.cs").read_text()
        source = FIXTURE.replace("DISCOVERY", member(world, "static IEnumerable<KeyValuePair<T, MethodInfo>> OriginalMethodAttributes<T>"))
        # The outer coordinator wrapper has the same name; select the session method.
        source = source.replace("PREPARE", member(stage, "public void PrepareOriginalDamageMacros()"))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "Fixture.cs"
            path.write_text(source)
            assembly = path.with_suffix(".exe")
            built = subprocess.run([str(mono), str(csc), "/nologo", "/out:" + str(assembly), str(path)], capture_output=True, text=True)
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            ran = subprocess.run([str(mono), str(assembly)], capture_output=True, text=True)
            self.assertEqual(ran.returncode, 0, ran.stdout + ran.stderr)
            self.assertIn("PASS typed method discovery", ran.stdout)
