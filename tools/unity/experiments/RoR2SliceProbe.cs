using System;
using System.IO;
using RoR2;
using UnityEngine;

// Authored acceptance assertions invoking original retained IL, not reimplementations.
public static class RoR2SliceProbe {
    [Serializable] public class Config { public string attempt, inputHash, sliceHash; }
    [Serializable] public class Result { public string attempt,utc,error,inputHash,sliceHash;public int pid,assertions;public bool success;public float apex,duration;public Vector3 position;public uint mask; }
    static void Check(bool condition,Result r,string label){if(!condition)throw new Exception(label);r.assertions++;}
    static bool Near(float a,float b){return Mathf.Abs(a-b)<0.0001f;}
    [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
    public static void Run(){
        var asset=Resources.Load<TextAsset>("RoR2SliceProbe");if(!asset)return;
        var cfg=JsonUtility.FromJson<Config>(asset.text);
        var r=new Result {attempt=cfg.attempt,inputHash=cfg.inputHash,sliceHash=cfg.sliceHash,utc=DateTime.UtcNow.ToString("o")};
#if UNITY_ANDROID && !UNITY_EDITOR
        using(var process=new AndroidJavaClass("android.os.Process"))r.pid=process.CallStatic<int>("myPid");
#endif
        try{
            r.apex=Trajectory.CalculateApex(10f,-10f);Check(Near(r.apex,5f),r,"apex");
            r.duration=Trajectory.CalculateFlightDuration(10f,-10f);Check(Near(r.duration,2f),r,"flight duration");
            r.position=Trajectory.CalculatePositionAtTime(new Vector3(1,2,3),new Vector3(4,10,-2),2f,-10f);
            Check((r.position-new Vector3(9,2,-1)).sqrMagnitude<0.000001f,r,"ballistic position");
            var origin=new Vector3(0,0,0);var destination=new Vector3(12,3,8);
            var velocity=Trajectory.CalculateInitialVelocityFromTime(origin,destination,2f,-10f,0f,float.PositiveInfinity);
            Check((Trajectory.CalculatePositionAtTime(origin,velocity,2f,-10f)-destination).sqrMagnitude<0.000001f,r,"solve and integrate trajectory");
            var mask=new ProcChainMask();
            Check(!mask.HasProc(ProcType.Behemoth)&&!mask.HasProc(ProcType.Missile),r,"empty proc mask");
            mask.AddProc(ProcType.Behemoth);mask.AddProc(ProcType.Missile);mask.AddProc(ProcType.Missile);
            Check(mask.HasProc(ProcType.Behemoth)&&mask.HasProc(ProcType.Missile)&&mask.mask==3u,r,"idempotent independent proc bits");
            var copy=mask;Check(copy.Equals(mask)&&copy.GetHashCode()==mask.GetHashCode(),r,"value equality");
            mask.RemoveProc(ProcType.Behemoth);r.mask=mask.mask;
            Check(!mask.HasProc(ProcType.Behemoth)&&mask.HasProc(ProcType.Missile)&&mask.mask==2u,r,"selective proc removal");
            Check(!copy.Equals(mask),r,"independent value copy");
            mask.RemoveProc(ProcType.Behemoth);Check(mask.mask==2u,r,"absent removal");
            r.success=true;
        }catch(Exception e){r.error=e.ToString();Debug.LogException(e);}
        File.WriteAllText(System.IO.Path.Combine(Application.persistentDataPath,"ror2-slice.json"),JsonUtility.ToJson(r,true));
        Debug.Log("LAB_ROR2_SLICE "+r.success+" assertions="+r.assertions+" "+r.attempt);
    }
}
