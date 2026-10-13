using System;
using System.Collections.Generic;
using System.IO;
using Path=System.IO.Path;
using System.Linq;
using Assets.RoR2.Scripts.Platform;
using RoR2;
using UnityEngine;

// Original pickup identities, profile discovery storage and both native
// achievement classes. Only the host inputs are synthetic; all definitions,
// callbacks, thresholds and rewards belong to the shipped game.
public static class AndroidDiscoveryHost {
 static void Check(bool condition,string message){if(!condition)throw new InvalidOperationException(message);}
 public static object Run(AndroidProgressionBoundary owner,UserProfile original,string directory){
  Check(owner!=null&&owner.ready&&original!=null&&PickupCatalog.pickupCount>0&&owner.pickupDiscoveryDefinitions.Length==2,"Native pickup-discovery fixture unavailable");
  var tier1=ItemCatalog.allItemDefs.Where(def=>def&&def.tier==ItemTier.Tier1).Select(def=>PickupCatalog.FindPickupIndex(def.itemIndex)).Where(index=>index.isValid).Distinct().Take(10).ToArray();
  var equipment=Enumerable.Range(0,EquipmentCatalog.equipmentCount).Select(i=>EquipmentCatalog.GetEquipmentDef((EquipmentIndex)i)).Where(def=>def).Select(def=>PickupCatalog.FindPickupIndex(def.equipmentIndex)).Where(index=>index.isValid).Distinct().Take(5).ToArray();
  Check(tier1.Length==10&&equipment.Length==5&&tier1.Concat(equipment).Distinct().Count()==15,"Shipped item/equipment discovery definitions are incomplete");
  var expected=owner.pickupDiscoveryDefinitions.ToDictionary(def=>def.identifier,def=>def);
  Check(expected.ContainsKey("Discover10UniqueTier1")&&expected.ContainsKey("Discover5Equipment"),"Original discovery achievements changed");
  var reports=new List<AndroidProgressionBoundary.DiscoveryReport>();
  Action<UserProfile,PickupIndex> callback=(candidate,pickup)=>reports.Add(owner.ApplyDiscoveryCandidate(candidate,pickup));
  var store=new AndroidOfflineProfile(directory,Array.Empty<Guid>(),null,callback);
  Check(store.profile.statSheet.GetUnlockableCount()==0&&!store.profile.HasAchievement("Discover10UniqueTier1")&&!store.profile.HasAchievement("Discover5Equipment"),"Discovery fixture is not a fresh native profile");
  for(int i=0;i<tier1.Length;i++){
   Check(store.DiscoverPickup(tier1[i]),"Original tier-one pickup was not discovered");
   Check(store.profile.HasDiscoveredPickup(tier1[i])&&store.profile.HasAchievement("Discover10UniqueTier1")== (i==9),"Original unique tier-one threshold differs");
   Check(reports.Last().awarded.SequenceEqual(i==9?new[]{"Discover10UniqueTier1"}:Array.Empty<string>()),"Original tier-one achievement callback fired at wrong count");
  }
  for(int i=0;i<equipment.Length;i++){
   Check(store.DiscoverPickup(equipment[i]),"Original equipment pickup was not discovered");
   Check(store.profile.HasDiscoveredPickup(equipment[i])&&store.profile.HasAchievement("Discover5Equipment")== (i==4),"Original equipment threshold differs");
   Check(reports.Last().awarded.SequenceEqual(i==4?new[]{"Discover5Equipment"}:Array.Empty<string>()),"Original equipment achievement callback fired at wrong count");
  }
  var itemReward=UnlockableCatalog.GetUnlockableDef(expected["Discover10UniqueTier1"].unlockableRewardIdentifier);
  var equipmentReward=UnlockableCatalog.GetUnlockableDef(expected["Discover5Equipment"].unlockableRewardIdentifier);
  AndroidProgressionBoundary.RequireDefinition(itemReward);AndroidProgressionBoundary.RequireDefinition(equipmentReward);
  Check(store.profile.statSheet.HasUnlockable(itemReward)&&store.profile.statSheet.HasUnlockable(equipmentReward),"Native pickup achievement rewards missing");
  uint coins=expected.Values.Aggregate(0u,(total,def)=>HGMath.UintSafeAdd(total,def.lunarCoinReward));
  Check(store.profile.coins==coins&&store.profile.totalCollectedCoins==coins&&store.appliedRuns==0,"Original discovery reward or result independence differs");
  var primary=Path.Combine(directory,"profile.json");string accepted=File.ReadAllText(primary);int callbackCount=reports.Count;
  Check(!store.DiscoverPickup(equipment[0])&&reports.Count==callbackCount&&File.ReadAllText(primary)==accepted,"Duplicate pickup discovery changed the profile");
  var reloaded=new AndroidOfflineProfile(directory,null,null,callback);
  Check(tier1.Concat(equipment).All(index=>reloaded.profile.HasDiscoveredPickup(index))&&reloaded.profile.HasAchievement("Discover10UniqueTier1")&&reloaded.profile.HasAchievement("Discover5Equipment")&&reloaded.profile.coins==coins&&reports.Count==callbackCount&&File.ReadAllText(primary)==accepted,"Native pickup discoveries did not survive a cold reload");
  Check(PlatformSystems.activityManager==null&&reloaded.profile.onPickupDiscovered==null&&original.statSheet.GetUnlockableCount()==0,"Native discovery fixture retained callbacks or altered the original profile");
  return new{success=true,originalItemDefinitions=tier1.Length,originalEquipmentDefinitions=equipment.Length,nativeAchievements=2,discovered=15,awarded=expected.Keys.OrderBy(value=>value,StringComparer.Ordinal).ToArray(),localCoins=coins,duplicateIgnored=true,coldReload=true,resultLedgerUnchanged=true,platformUnavailable=true};
 }
}
