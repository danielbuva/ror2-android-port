using System;
using System.IO;
using Unity.Burst;
using Unity.Collections;
using Unity.Jobs;
using UnityEngine;

public static class CollectionsRuntimeProbe {
    [Serializable] public class Config { public string attempt; }
    [Serializable] public class Result { public string attempt,utc,error; public int pid,sum,afterRemoval; public bool success,burstExecuted,burstEnabled; }
    [BurstCompile(CompileSynchronously=true)]
    public struct SumJob : IJob {
        [ReadOnly] public NativeArray<int> values;
        public NativeArray<int> result;
        [BurstDiscard] static void Managed(ref int flag) { flag=0; }
        public void Execute() {
            int sum=0;for(int i=0;i<values.Length;i++)sum+=values[i];
            result[0]=sum;int flag=1;Managed(ref flag);result[1]=flag;
        }
    }
    [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
    public static void Run() {
        var asset=Resources.Load<TextAsset>("CollectionsRuntimeProbe");if(!asset)return;
        var cfg=JsonUtility.FromJson<Config>(asset.text);
        var r=new Result {attempt=cfg.attempt,utc=DateTime.UtcNow.ToString("o"),burstEnabled=BurstCompiler.IsEnabled};
#if UNITY_ANDROID && !UNITY_EDITOR
        using(var process=new AndroidJavaClass("android.os.Process"))r.pid=process.CallStatic<int>("myPid");
#endif
        try {
            using(var values=new NativeList<int>(Allocator.TempJob))
            using(var result=new NativeArray<int>(2,Allocator.TempJob)) {
                values.Add(7);values.Add(11);values.Add(13);
                new SumJob {values=values.AsArray(),result=result}.Schedule().Complete();
                r.sum=result[0];r.burstExecuted=result[1]==1;
                values.RemoveAtSwapBack(0);
                var slice=values.AsArray().Slice();r.afterRemoval=slice[0]+slice[1];
                if(r.sum!=31||r.afterRemoval!=24)throw new Exception("Collections result mismatch");
            }
            r.success=true;
        }catch(Exception e){r.error=e.ToString();Debug.LogException(e);}
        File.WriteAllText(Path.Combine(Application.persistentDataPath,"collections-probe.json"),JsonUtility.ToJson(r,true));
        Debug.Log("LAB_COLLECTIONS_PROBE "+r.success+" burst="+r.burstExecuted+" "+r.attempt);
    }
}
