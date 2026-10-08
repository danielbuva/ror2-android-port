using System;
using System.Globalization;

// Supply offline entropy at the existing Run seed boundary, preserving native RNGs.
public sealed partial class MovementBatchProbe {
 ulong SelectOwnedRunSeed(Result cfg){
  if(!string.IsNullOrEmpty(r.runSeedOverride)){
   ulong seed;Check(cfg.integratedWorld&&ulong.TryParse(r.runSeedOverride,NumberStyles.None,CultureInfo.InvariantCulture,out seed),"Invalid explicit offline run seed");
   r.rewards.seedSource="explicit recorded developer selection";return ulong.Parse(r.runSeedOverride,CultureInfo.InvariantCulture);
  }
  if(cfg.integratedWorld&&r.freePlay&&cfg.freshRunSeed){r.rewards.seedSource="Android offline entropy adapter; native Run RNG initialization";return BitConverter.ToUInt64(Guid.NewGuid().ToByteArray(),0);}
  r.rewards.seedSource="inherited bounded fixture";return 140;
 }
}
