// Subsystem: session (game path). Owner map: docs/ARCHITECTURE.md#ownership.
// Session phases: setup SelectOwnedRunSeed (OfflineRunSeedSession.SelectOwnedRunSeed); teardown — (Dispose is a no-op).
using System;
using System.Globalization;

// Supply offline entropy at the existing Run seed boundary, preserving native RNGs.
public sealed partial class PortSession {
 OfflineRunSeedSession offlineRunSeedSession;
 OfflineRunSeedSession GetOfflineRunSeedSession(){if(offlineRunSeedSession==null)offlineRunSeedSession=new OfflineRunSeedSession(this);return offlineRunSeedSession;}
 ulong SelectOwnedRunSeed(SessionConfig cfg){return GetOfflineRunSeedSession().SelectOwnedRunSeed(cfg);}

 // Create on first selection and retain the cache across calls. The session id
 // still selects when to refresh; there are no resources to release at teardown.
 sealed class OfflineRunSeedSession : IDisposable {
  readonly PortSession coordinator;
  ulong? ownedRunSeed;int ownedRunSeedSession=-1;string ownedRunSeedSource;
  public OfflineRunSeedSession(PortSession coordinator){this.coordinator=coordinator;}
  public ulong SelectOwnedRunSeed(SessionConfig cfg){
   if(ownedRunSeedSession==coordinator.r.session&&ownedRunSeed.HasValue){if(coordinator.r.rewards!=null)coordinator.r.rewards.seedSource=ownedRunSeedSource;return ownedRunSeed.Value;}
   ulong selected;
   if(!string.IsNullOrEmpty(coordinator.r.runSeedOverride)){
    ulong seed;bool parsed=ulong.TryParse(coordinator.r.runSeedOverride,NumberStyles.None,CultureInfo.InvariantCulture,out seed);coordinator.Check(cfg.integratedWorld&&parsed,"Invalid explicit offline run seed");
    ownedRunSeedSource="explicit recorded developer selection";selected=seed;
   }
   else if(cfg.integratedWorld&&coordinator.r.freePlay&&cfg.freshRunSeed){ownedRunSeedSource="Android offline entropy adapter; native Run RNG initialization";selected=BitConverter.ToUInt64(Guid.NewGuid().ToByteArray(),0);}
   else{ownedRunSeedSource="inherited bounded fixture";selected=140;}
   ownedRunSeed=selected;ownedRunSeedSession=coordinator.r.session;if(coordinator.r.rewards!=null)coordinator.r.rewards.seedSource=ownedRunSeedSource;return selected;
  }
  public void Dispose(){}
 }
}
