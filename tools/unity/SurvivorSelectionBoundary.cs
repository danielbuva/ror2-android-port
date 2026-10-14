using System;
using System.Linq;
using RoR2;
using UnityEngine;

// Ordinary selection remains limited to shipped, freely available survivors.
// An explicit developer-only base survivor selection can exercise original code
// without granting an unlock or claiming normal-run acceptance.
public sealed partial class MovementBatchProbe {
 GameObject selectedBodyStaging;
 bool SelectedSourceSurvivor(){return r!=null&&!string.IsNullOrEmpty(r.selectedSurvivor)&&r.selectedSurvivor!="Commando";}
 GameObject SelectedPlayerPrefab(Result cfg){
  if(string.IsNullOrEmpty(r.selectedSurvivor))r.selectedSurvivor="Commando";
  if(r.selectedSurvivor=="Commando")return artifactBundle.LoadAsset<GameObject>(cfg.bodyAsset);
  Check(cfg.integratedWorld&&r.liveCatalogs!=null,"Unsupported offline survivor selection");
  var definitions=WholeCatalogComposed.CategoryFamily(RoR2.ContentManagement.AddressablesLabels.survivorDef,Array.Empty<SurvivorDef>());
  var survivor=definitions.SingleOrDefault(value=>value&&value.cachedName==r.selectedSurvivor);
  Check(survivor&&survivor.bodyPrefab&&!survivor.hidden&&!survivor.GetRequiredExpansion()&&!survivor.GetRequiredEntitlement(),"Selected survivor requires an unavailable original expansion or entitlement");
  bool locked=survivor.unlockableDef||!string.IsNullOrEmpty(survivor.unlockableName);
  Check(!locked||r.developerSurvivorOverride&&r.debugOptions!=null&&!string.IsNullOrWhiteSpace(r.debugOptions.purpose)&&r.debugOptions.purpose.Length<=160,"Selected survivor requires an original unlock; developer selection needs an explicit diagnostic purpose");
  Check(!r.developerSurvivorOverride||locked,"Developer survivor override is limited to locked base survivors");
  var body=survivor.bodyPrefab.GetComponent<CharacterBody>();
  Check(body&&body.bodyIndex!=BodyIndex.None&&BodyCatalog.GetBodyPrefab(body.bodyIndex)==survivor.bodyPrefab,"Selected source survivor/body catalog identity differs");
  return survivor.bodyPrefab;
 }
}
