"""Exercise exact roster GUI-state ownership across menu retirement."""

from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
EDITOR = Path("/Applications/Unity/Hub/Editor/2021.3.45f2/Unity.app/Contents")

HOST = r"""
using System;
using System.Collections.Generic;
using System.Reflection;
using UnityEngine;
namespace UnityEngine {
 public static class GUI { public static object current; private static object GetTopScrollView(){return current;} }
 internal static class GUIStateObjects {
  private static Dictionary<int,object> s_StateCache=new Dictionary<int,object>();
  public static Dictionary<int,object> Cache {get{return s_StateCache;}}
 }
}
class Program {
 static void Check(bool ok,string reason){if(!ok)throw new Exception(reason);}
 static void Main(string[] args){
  if(args.Length!=0){
   var sdk=Assembly.LoadFrom(args[0]);
   var top=sdk.GetType("UnityEngine.GUI").GetMethod("GetTopScrollView",BindingFlags.Static|BindingFlags.NonPublic);
   var cache=sdk.GetType("UnityEngine.GUIStateObjects").GetField("s_StateCache",BindingFlags.Static|BindingFlags.NonPublic);
   Check(top!=null&&top.GetParameters().Length==0&&top.ReturnType.FullName=="UnityEngine.ScrollViewState","Pinned scroll stack changed");
   Check(cache!=null&&cache.FieldType==typeof(Dictionary<int,object>),"Pinned GUI cache changed");
   Console.WriteLine("editor-layout: PASS");return;
  }
  var cacheEntries=GUIStateObjects.Cache;var foreign=new object();cacheEntries[99]=foreign;
  var owner=new OfflineRosterScrollStateOwner();var second=new OfflineRosterScrollStateOwner();
  var a=new object();cacheEntries[1]=a;GUI.current=a;owner.Capture();owner.Capture();
  var b=new object();cacheEntries[2]=b;GUI.current=b;owner.Capture();
  var c=new object();cacheEntries[3]=c;GUI.current=c;second.Capture();
  Check(cacheEntries.Count==4,"Capture changed live scroll states");
  var replacement=new object();cacheEntries[2]=replacement;
  owner.Dispose();owner.Dispose();
  Check(!cacheEntries.ContainsKey(1)&&ReferenceEquals(cacheEntries[2],replacement)&&ReferenceEquals(cacheEntries[3],c)&&ReferenceEquals(cacheEntries[99],foreign),"Retirement exceeded exact ownership");
  second.Dispose();cacheEntries.Remove(2);
  for(int session=0;session<40;session++){
   var state=new object();cacheEntries[100+session]=state;GUI.current=state;owner.Capture();
   Check(cacheEntries.Count==2,"Live roster state lost");owner.Dispose();
   Check(cacheEntries.Count==1&&ReferenceEquals(cacheEntries[99],foreign),"Retired roster accumulated or foreign state changed");
  }
  Console.WriteLine("ownership: PASS");
 }
}
"""


class OfflineRosterScrollStateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mono = EDITOR / "MonoBleedingEdge/bin/mono"
        compiler = EDITOR / "MonoBleedingEdge/lib/mono/msbuild/Current/bin/Roslyn/csc.exe"
        if not cls.mono.is_file() or not compiler.is_file():
            raise unittest.SkipTest("pinned Unity Mono/Roslyn unavailable")
        cls.temp = tempfile.TemporaryDirectory(prefix="roster-scroll-state-")
        cls.addClassCleanup(cls.temp.cleanup)
        folder = Path(cls.temp.name)
        production = (ROOT / "tools/unity/runtime/session/SurvivorSelectionBoundary.cs").read_text()
        helper = production[production.index("internal sealed class OfflineRosterScrollStateOwner") :]
        source = folder / "Host.cs"
        source.write_text(HOST + "\n" + helper)
        cls.exe = folder / "Host.exe"
        compiled = subprocess.run(
            [str(cls.mono), str(compiler), "-nologo", "-out:" + str(cls.exe), str(source)],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if compiled.returncode:
            raise AssertionError(compiled.stdout + compiled.stderr)

    def test_retirement_removes_only_exact_roster_states_and_allows_next_menu(self):
        result = subprocess.run([str(self.mono), str(self.exe)], capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("ownership: PASS", result.stdout)

    def test_pinned_editor_has_the_captured_stack_and_cache_layout(self):
        module = EDITOR / "Managed/UnityEngine/UnityEngine.IMGUIModule.dll"
        result = subprocess.run([str(self.mono), str(self.exe), str(module)], capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("editor-layout: PASS", result.stdout)
