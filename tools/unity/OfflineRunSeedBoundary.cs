// Subsystem: session (game path). Owner map: docs/ARCHITECTURE.md#ownership.
// Session phases: setup SelectOwnedRunSeed; teardown —.
using System;
using System.Globalization;

// Supply offline entropy at the existing Run seed boundary, preserving native RNGs.
public sealed partial class MovementBatchProbe {
 ulong? ownedRunSeed;int ownedRunSeedSession=-1;string ownedRunSeedSource;
 ulong SelectOwnedRunSeed(Result cfg){
  if(ownedRunSeedSession==r.session&&ownedRunSeed.HasValue){if(r.rewards!=null)r.rewards.seedSource=ownedRunSeedSource;return ownedRunSeed.Value;}
  ulong selected;
  if(!string.IsNullOrEmpty(r.runSeedOverride)){
   ulong seed;bool parsed=ulong.TryParse(r.runSeedOverride,NumberStyles.None,CultureInfo.InvariantCulture,out seed);Check(cfg.integratedWorld&&parsed,"Invalid explicit offline run seed");
   ownedRunSeedSource="explicit recorded developer selection";selected=seed;
  }
  else if(cfg.integratedWorld&&r.freePlay&&cfg.freshRunSeed){ownedRunSeedSource="Android offline entropy adapter; native Run RNG initialization";selected=BitConverter.ToUInt64(Guid.NewGuid().ToByteArray(),0);}
  else{ownedRunSeedSource="inherited bounded fixture";selected=140;}
  ownedRunSeed=selected;ownedRunSeedSession=r.session;if(r.rewards!=null)r.rewards.seedSource=ownedRunSeedSource;return selected;
 }
}
