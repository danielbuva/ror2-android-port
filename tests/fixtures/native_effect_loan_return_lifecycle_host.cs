// Authored external-contract doubles. No original game implementation included.
using System;
using System.Collections;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
public class GameObject
{
    public bool alive=true,activeSelf=true;
    public static implicit operator bool(GameObject value) { return value!=null&&value.alive; }
}
public class EffectManagerHelper
{
    public EffectPool OwningPool;public GameObject gameObject=new GameObject();public bool alive=true;
    public static implicit operator bool(EffectManagerHelper value) { return value!=null&&value.alive; }
}
public class EffectPool
{
    public readonly List<EffectManagerHelper> InUse=new List<EffectManagerHelper>();
    public readonly List<EffectManagerHelper> inactive=new List<EffectManagerHelper>(),deferred=new List<EffectManagerHelper>();
    public string mode="immediate";public int calls;public Action onReturn;
    public int InUseCount(){return InUse.Count;}
    public bool IsObjectInPool(EffectManagerHelper value){return inactive.Contains(value);}
    public void ReturnObject(EffectManagerHelper value)
    {
        calls++;if(onReturn!=null)onReturn();
        if(mode=="throw")throw new InvalidOperationException("authored native return refusal");
        if(mode=="deferred"){deferred.Add(value);return;}
        if(mode=="stuck")return;
        InUse.Remove(value);inactive.Add(value);value.gameObject.activeSelf=false;
    }
    public void FinishNativeDestruction()
    {
        foreach(var value in deferred){value.alive=value.gameObject.alive=false;InUse.Remove(value);value.OwningPool=null;}
        deferred.Clear();
    }
}
public static class EffectManager {public static Dictionary<GameObject,EffectPool> _EffectPrefabMap=new Dictionary<GameObject,EffectPool>();}
public static class Time {public static int frameCount;}
public static class Run {public static GameObject instance;}
public static class AssetAsyncLiaison
{
    public static int releases;
    public static void AssetAsyncReleaseAllReferences(bool force)
    {
        if(!force||EffectManager._EffectPrefabMap.Values.Any(p=>p.InUseCount()!=0))throw new Exception("External contract: no asset release with live loan");
        releases++;
    }
}
public partial class PortSession
{
    public bool ownsIntegratedPools=true;public int saves,orbCacheReleases,dependentReleases;public string firstFailure="";
    public readonly Report r=new Report();public readonly IntegratedStageSession Stage;public readonly RunClockSession Clock;
    public PortSession(){Stage=new IntegratedStageSession(this);Clock=new RunClockSession(this);}
    public sealed class Report {public StageReport stageProgress=new StageReport();public ClockReport runClock=new ClockReport();}
    public sealed class StageReport {public int effectLoansReturned;}
    public sealed class ClockReport {public int endRunEffectLoansReturned;public bool asyncAssetsReleased;}
    public void Check(bool value,string message){if(!value){if(firstFailure=="")firstFailure=message;throw new Exception(message);}}
    public void Save(){saves++;}
    public static FieldInfo RewardField(Type type,string name){return type.GetField(name,BindingFlags.Static|BindingFlags.Public|BindingFlags.NonPublic);}
    public IntegratedStageSession GetIntegratedStageSession(){return Stage;}
    public RunClockSession GetRunClockSession(){return Clock;}
    public void ReleaseObjectiveOrbCache(){orbCacheReleases++;}
    public partial class IntegratedStageSession
    {
        readonly PortSession coordinator;public IntegratedStageSession(PortSession value){coordinator=value;}
        public bool Retained {get{return pendingEffectLoanReturns!=null;}}
    }
    public partial class RunClockSession
    {
        readonly PortSession coordinator;bool ownsRunAsyncLifecycle=true;
        public RunClockSession(PortSession value){coordinator=value;}
        public bool Retained {get{return ownsRunAsyncLifecycle;}}
    }
}
public static class HostContract
{
    static void Check(bool value,string message){if(!value)throw new Exception("CONTRACT: "+message);}
    static PortSession Fresh(string mode,int count,out EffectPool pool)
    {
        Time.frameCount=100;Run.instance=null;AssetAsyncLiaison.releases=0;EffectManager._EffectPrefabMap=new Dictionary<GameObject,EffectPool>();
        pool=new EffectPool{mode=mode};EffectManager._EffectPrefabMap.Add(new GameObject(),pool);
        for(int i=0;i<count;i++)pool.InUse.Add(new EffectManagerHelper{OwningPool=pool});
        return new PortSession();
    }
    static void Refuses(IEnumerator iterator,string fragment)
    {
        try{iterator.MoveNext();}catch(Exception error){if(error.Message.Contains(fragment))return;throw;}
        throw new Exception("Expected refusal: "+fragment);
    }
    public static void Main()
    {
        EffectPool pool;var owner=Fresh("immediate",1,out pool);var iterator=owner.CleanupSeam();
        Check(!iterator.MoveNext(),"Immediate native return adds no frame wait");Check(pool.calls==1&&AssetAsyncLiaison.releases==1&&owner.dependentReleases==1&&!owner.Clock.Retained&&!owner.Stage.Retained,"Immediate cleanup completes exactly once");
        Check(owner.r.stageProgress.effectLoansReturned==1&&owner.r.runClock.endRunEffectLoansReturned==1,"Only proven retirements credited");
        owner=Fresh("deferred",7,out pool);iterator=owner.CleanupSeam();Check(iterator.MoveNext()&&iterator.Current==null,"Deferred native destruction yields actual next frame");
        Check(pool.calls==7&&pool.InUseCount()==7&&AssetAsyncLiaison.releases==0&&owner.dependentReleases==0&&owner.Stage.Retained&&owner.Clock.Retained,"All seven exact returns issued once, leases retained");
        pool.FinishNativeDestruction();Time.frameCount++;Check(!iterator.MoveNext(),"Native OnDestroy removal permits continuation");
        Check(pool.calls==7&&AssetAsyncLiaison.releases==1&&owner.dependentReleases==1&&owner.r.stageProgress.effectLoansReturned==7&&owner.r.runClock.endRunEffectLoansReturned==7,"Deferred retirement preserves counts/order");
        owner=Fresh("stuck",1,out pool);iterator=owner.CleanupSeam();Check(iterator.MoveNext(),"Stuck return reaches one fence");Time.frameCount++;Refuses(iterator,"Owned stage effect loans survived original return callbacks");
        Check(pool.calls==1&&AssetAsyncLiaison.releases==0&&owner.dependentReleases==0&&owner.Stage.Retained&&owner.Clock.Retained&&owner.r.stageProgress.effectLoansReturned==0,"Stuck native owner retained, no false credit or release");
        Refuses(owner.CleanupSeam(),"Owned stage effect loans survived original return callbacks");Check(pool.calls==1,"Refusal never reissues native return");
        owner=Fresh("deferred",1,out pool);iterator=owner.CleanupSeam();Check(iterator.MoveNext(),"Foreign-map test suspends");EffectManager._EffectPrefabMap=new Dictionary<GameObject,EffectPool>(EffectManager._EffectPrefabMap);Time.frameCount++;Refuses(iterator,"pool map changed");Check(pool.calls==1&&AssetAsyncLiaison.releases==0&&owner.Stage.Retained,"Foreign dictionary refuses without releasing");
        owner=Fresh("deferred",1,out pool);iterator=owner.CleanupSeam();Check(iterator.MoveNext(),"Foreign-pool test suspends");var key=EffectManager._EffectPrefabMap.Keys.Single();var foreign=new EffectPool();EffectManager._EffectPrefabMap[key]=foreign;Time.frameCount++;Refuses(iterator,"pool identity changed");Check(pool.calls==1&&foreign.calls==0&&AssetAsyncLiaison.releases==0,"Foreign pool never returned or released");
        owner=Fresh("immediate",2,out pool);var second=pool.InUse[1];var other=new EffectPool();pool.onReturn=()=>second.OwningPool=other;Refuses(owner.CleanupSeam(),"loan changed before");Check(pool.calls==1&&other.calls==0&&owner.Stage.Retained&&owner.Clock.Retained,"Foreign helper ownership refuses before second native callback");
        owner=Fresh("throw",1,out pool);Refuses(owner.CleanupSeam(),"authored native return refusal");Refuses(owner.CleanupSeam(),"did not finish issuing");Check(pool.calls==1&&AssetAsyncLiaison.releases==0&&owner.Stage.Retained,"Partial unknown callback never reissued");
        owner=Fresh("deferred",1,out pool);iterator=owner.CleanupSeam();Check(iterator.MoveNext(),"Interrupted iterator starts");((IDisposable)iterator).Dispose();pool.FinishNativeDestruction();Time.frameCount++;Check(!owner.CleanupSeam().MoveNext()&&pool.calls==1&&AssetAsyncLiaison.releases==1,"Interrupted fence retains and adopts exact batch without repeat return");
        owner=Fresh("deferred",1,out pool);iterator=owner.CleanupSeam();Check(iterator.MoveNext(),"Missing-frame test starts");pool.FinishNativeDestruction();Refuses(iterator,"did not cross a Unity frame");Check(AssetAsyncLiaison.releases==0,"No fabricated same-frame fence");
        owner=Fresh("deferred",1,out pool);Refuses(owner.SynchronousSeam(),"Owned stage effect loans survived original return callbacks");Check(pool.calls==1&&AssetAsyncLiaison.releases==0,"Original synchronous callback retains its strict guard");
        owner=Fresh("deferred",1,out pool);iterator=owner.TransportSeam();Check(iterator.MoveNext()&&owner.orbCacheReleases==0,"Transport retains scene dependencies until callbacks finish");pool.FinishNativeDestruction();Time.frameCount++;Check(!iterator.MoveNext()&&owner.orbCacheReleases==1&&pool.calls==1,"Transport continues once after native retirement");
        owner=Fresh("immediate",1,out pool);owner.ownsIntegratedPools=false;Refuses(owner.Stage.ReturnIntegratedStageEffectsAfterNativeCallbacks(),"ownership baseline");Check(pool.calls==0&&AssetAsyncLiaison.releases==0,"No foreign-pool return without owned baseline");
        Console.WriteLine("PASS: immediate/deferred/stuck/foreign/partial/interrupted/frame/transport native-effect return contracts");
    }
}
