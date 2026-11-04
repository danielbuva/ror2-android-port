using System;
using System.IO;
using System.Collections.Generic;
using System.Web.Script.Serialization;
namespace UnityEngine {
 public static class Application { public static string persistentDataPath; }
 public static class Debug { public static bool isDebugBuild=true; }
 public static class JsonUtility {
  public static T FromJson<T>(string json) {
   var values=(Dictionary<string,object>)new JavaScriptSerializer().DeserializeObject(json);
   var value=Activator.CreateInstance(typeof(T),true);
   foreach(var pair in values){var field=typeof(T).GetField(pair.Key);if(field!=null)field.SetValue(value,Convert.ChangeType(pair.Value,field.FieldType));}
   return (T)value;
  }
 }
}
namespace UnityEngine.Profiling.Memory.Experimental {
 [Flags] public enum CaptureFlags { ManagedObjects=1,NativeObjects=2 }
 public static class MemoryProfiler {
  public static int calls; public static string path; public static CaptureFlags flags;
  public static Action<string,bool> callback; public static bool throws,synchronous;
  public static void TakeSnapshot(string file,Action<string,bool> finished,CaptureFlags requested) {
   calls++;if(throws)throw new IOException("authored failure");path=file;callback=finished;flags=requested;
   if(synchronous){File.WriteAllText(file,"authored synchronous snapshot");finished(file,true);}
  }
  public static void Reset(){calls=0;path=null;callback=null;throws=false;synchronous=false;}
 }
}
class Run { public static bool instance; }
class NetworkServer { public static bool active; }
class NetworkClient { public static bool active; }
public sealed partial class PortSession {
 public class Report { public string attempt="authored"; public int session=2; }
 public Report r=new Report(); public int sessionIndex=2,saves;
 public static implicit operator bool(PortSession owner)=>owner!=null;
 void Save(){saves++;}
 public SessionResourceSample Capture(){var sample=new SessionResourceSample();CaptureCompletedMemorySnapshot(sample);return sample;}
 public bool RootRequested()=>CompletedRootWalkRequested();
}
static class Program {
 static void Need(bool value,string reason){if(!value)throw new Exception(reason);}
 static void Select(string json){File.WriteAllText(Path.Combine(UnityEngine.Application.persistentDataPath,"movement-batch-selection.json"),json);}
 static void Main(string[] args){
  UnityEngine.Application.persistentDataPath=args[1];Directory.CreateDirectory(args[1]);
  var keep=Path.Combine(args[1],"unrelated-profile.json");File.WriteAllText(keep,"authored preserved profile");
  switch(args[0]){
   case "admission":
    Select("{\"attempt\":\"authored\",\"diagnosticCompletedMemorySnapshots\":true}");
    for(int index=1;index<=5;index++){
     UnityEngine.Profiling.Memory.Experimental.MemoryProfiler.Reset();var sample=new PortSession{sessionIndex=index}.Capture();
     Need(sample.memorySnapshotRequested==(index==2||index==4),"wrong snapshot menu");
     Need(UnityEngine.Profiling.Memory.Experimental.MemoryProfiler.calls==((index==2||index==4)?1:0),"unexpected native request");
    }
    Select("{\"attempt\":\"authored\",\"diagnosticCompletedMemorySnapshots\":true,\"diagnosticCompletedMemorySnapshotFinalSession\":13}");
    for(int index=1;index<=13;index++){
     UnityEngine.Profiling.Memory.Experimental.MemoryProfiler.Reset();var sample=new PortSession{sessionIndex=index}.Capture();
     Need(sample.memorySnapshotRequested==(index==2||index==13),"late series captured the wrong menu");
    }
    Select("{\"attempt\":\"foreign\",\"diagnosticCompletedMemorySnapshots\":true}");
    Need(!new PortSession().Capture().memorySnapshotRequested,"foreign attempt captured memory");
    Select("{\"attempt\":\"authored\"}");Need(!new PortSession().Capture().memorySnapshotRequested,"default-on memory capture");
    Select("invalid JSON");Need(!new PortSession().Capture().memorySnapshotRequested,"malformed selector captured memory");
    Select("{\"attempt\":\"authored\",\"diagnosticCompletedRootWalkSession\":2}");
    Need(new PortSession().RootRequested()&&!new PortSession{sessionIndex=3}.RootRequested(),"existing root-walk admission changed");
    break;
   case "idle-only":
    Select("{\"attempt\":\"authored\",\"diagnosticCompletedMemorySnapshots\":true}");
    for(int blocked=0;blocked<4;blocked++){
     UnityEngine.Profiling.Memory.Experimental.MemoryProfiler.Reset();UnityEngine.Debug.isDebugBuild=blocked!=0;Run.instance=blocked==1;NetworkServer.active=blocked==2;NetworkClient.active=blocked==3;
     var sample=new PortSession().Capture();Need(sample.memorySnapshotComplete&&!sample.memorySnapshotSuccess&&UnityEngine.Profiling.Memory.Experimental.MemoryProfiler.calls==0,"captured a live/release player");
    }
    break;
   case "transaction":
    Select("{\"attempt\":\"authored\",\"diagnosticCompletedMemorySnapshots\":true}");
    var owner=new PortSession();var pending=owner.Capture();var path=UnityEngine.Profiling.Memory.Experimental.MemoryProfiler.path;
    Need(pending.memorySnapshotRequested&&!pending.memorySnapshotComplete,"claimed completion before native callback");
    Need(UnityEngine.Profiling.Memory.Experimental.MemoryProfiler.flags==(UnityEngine.Profiling.Memory.Experimental.CaptureFlags)3,"captured unnecessary data or omitted managed/native objects");
    Need(Path.GetDirectoryName(path)==Path.Combine(args[1],"diagnostics","session-memory")&&Path.GetFileName(path)==pending.memorySnapshotFile,"snapshot escaped owned diagnostic directory");
    File.WriteAllText(path,"authored snapshot bytes");UnityEngine.Profiling.Memory.Experimental.MemoryProfiler.callback(path,true);
    Need(pending.memorySnapshotComplete&&pending.memorySnapshotSuccess&&owner.saves==1,"completed file was not reported durably");
    var second=owner.Capture();Need(second.memorySnapshotFile!=pending.memorySnapshotFile&&File.ReadAllText(path)=="authored snapshot bytes","new request overwrote prior evidence");
    break;
   case "sync-completion":
    Select("{\"attempt\":\"authored\",\"diagnosticCompletedMemorySnapshots\":true}");
    UnityEngine.Profiling.Memory.Experimental.MemoryProfiler.synchronous=true;
    var starting=new PortSession();starting.r.session=0;var sync=starting.Capture();
    Need(sync.memorySnapshotComplete&&sync.memorySnapshotSuccess&&starting.saves==0,"synchronous callback published transient session zero");
    break;
   case "refusal":
    Select("{\"attempt\":\"authored\",\"diagnosticCompletedMemorySnapshots\":true}");
    for(int failure=0;failure<3;failure++){
     var session=new PortSession();UnityEngine.Profiling.Memory.Experimental.MemoryProfiler.throws=failure==2;var failed=session.Capture();
     if(failure!=2){var actual=UnityEngine.Profiling.Memory.Experimental.MemoryProfiler.path;if(failure==1)File.WriteAllText(actual,"authored");UnityEngine.Profiling.Memory.Experimental.MemoryProfiler.callback(failure==1?actual+".foreign":actual,true);}
     Need(failed.memorySnapshotComplete&&!failed.memorySnapshotSuccess&&!string.IsNullOrEmpty(failed.memorySnapshotError),"missing/wrong-path/throw claimed snapshot success");
    }
    break;
   default:throw new Exception("Unknown fixture case");
  }
  Need(File.ReadAllText(keep)=="authored preserved profile","capture modified unrelated data");Console.WriteLine(args[0]+": PASS");
 }
}
