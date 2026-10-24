"""Execute the real async MCP bootstrap against authored preference/bridge doubles."""

from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SDK = Path("/Applications/Unity/Hub/Editor/2021.3.45f2/Unity.app/Contents")


class BootstrapMcpTests(unittest.TestCase):
    def test_lane_endpoint_capture_restores_global_preferences_and_cancels_resume(self):
        mono = SDK / "MonoBleedingEdge/bin/mono"
        csc = SDK / "MonoBleedingEdge/lib/mono/msbuild/Current/bin/Roslyn/csc.exe"
        if not mono.is_file() or not csc.is_file():
            self.skipTest("optional pinned Mono/Roslyn is unavailable")
        with tempfile.TemporaryDirectory() as directory:
            scratch = Path(directory)
            stub = scratch / "AuthoredBridge.cs"
            stub.write_text("""
using System;
using System.Collections.Generic;
using System.Threading.Tasks;
namespace UnityEditor {
 public static class EditorPrefs {
  static Dictionary<string,string> values=new Dictionary<string,string>();
  public static bool HasKey(string k){return values.ContainsKey(k);}
  public static string GetString(string k,string d){return values.ContainsKey(k)?values[k]:d;}
  public static void SetString(string k,string v){values[k]=v;}
  public static void DeleteKey(string k){values.Remove(k);}
  public static bool GetBool(string k,bool d){return values.ContainsKey(k)?values[k]=="true":d;}
  public static void SetBool(string k,bool v){values[k]=v?"true":"false";}
 }
 public static class SessionState {public static bool erased;public static void EraseBool(string key){if(key=="MCPForUnity.ResumeHttpAfterReload")erased=true;}}
 public static class EditorApplication {public static Action delayCall;}
 namespace Callbacks {public sealed class DidReloadScripts:Attribute {public DidReloadScripts(int order){}}}
}
namespace UnityEngine {public static class Debug {public static bool done;public static void Log(object value){done=value.ToString()=="BOOTSTRAP_MCP_CONNECTED=True";}}}
namespace MCPForUnity.Editor.Services {
 public sealed class Bridge {public string url;public int stops;public Task StopAsync(){stops++;return Task.CompletedTask;}
  public Task<bool> StartAsync(){url=UnityEditor.EditorPrefs.GetString("MCPForUnity.HttpUrl","");return Task.FromResult(true);}}
 public static class MCPServiceLocator {public static Bridge Bridge=new Bridge();}
}
public static class Host {
 public static int Main(string[] args){
  Environment.SetEnvironmentVariable("ROR2LAB_MCP_HTTP_URL","http://127.0.0.1:9081");
  Environment.SetEnvironmentVariable("ROR2LAB_MCP_PREF_LOCK",args[0]);
  UnityEditor.EditorPrefs.SetString("MCPForUnity.HttpUrl","http://127.0.0.1:8080");
  UnityEditor.EditorPrefs.SetBool("MCPForUnity.UseHttpTransport",false);
  BootstrapMcp.Connect();
  if(!UnityEngine.Debug.done)return 1;
  if(MCPForUnity.Editor.Services.MCPServiceLocator.Bridge.url!="http://127.0.0.1:9081")return 2;
  if(UnityEditor.EditorPrefs.GetString("MCPForUnity.HttpUrl","")!="http://127.0.0.1:8080")return 3;
  if(UnityEditor.EditorPrefs.GetBool("MCPForUnity.UseHttpTransport",true))return 4;
  if(!UnityEditor.SessionState.erased||MCPForUnity.Editor.Services.MCPServiceLocator.Bridge.stops!=1)return 5;
  UnityEditor.EditorPrefs.DeleteKey("MCPForUnity.HttpUrl");BootstrapMcp.Connect();
  if(UnityEditor.EditorPrefs.HasKey("MCPForUnity.HttpUrl"))return 6;
  return 0;
 }
}
""")
            executable = scratch / "bootstrap.exe"
            result = subprocess.run(
                [str(mono), str(csc), "-nologo", "-out:" + str(executable), str(ROOT / "android/Assets/Editor/BootstrapMcp.cs"), str(stub)],
                capture_output=True,
                text=True,
                timeout=60,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            result = subprocess.run([str(mono), str(executable), str(scratch / "prefs.lock")], capture_output=True, text=True, timeout=20)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
