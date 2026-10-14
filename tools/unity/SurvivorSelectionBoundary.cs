using System;
using System.Linq;
using RoR2;
using UnityEngine;

// Select only shipped, freely available survivor metadata for the owned offline run.
// The Android profile and expansion gates remain authoritative for later additions.
public sealed partial class MovementBatchProbe {
 GameObject selectedBodyStaging;
 bool SelectedHuntress(){return r!=null&&r.selectedSurvivor=="Huntress";}
 GameObject SelectedPlayerPrefab(Result cfg){
  if(string.IsNullOrEmpty(r.selectedSurvivor))r.selectedSurvivor="Commando";
  if(r.selectedSurvivor=="Commando")return artifactBundle.LoadAsset<GameObject>(cfg.bodyAsset);
  Check(cfg.integratedWorld&&r.selectedSurvivor=="Huntress"&&r.liveCatalogs!=null,"Unsupported offline survivor selection");
  var definitions=WholeCatalogComposed.CategoryFamily(RoR2.ContentManagement.AddressablesLabels.survivorDef,Array.Empty<SurvivorDef>());
  var survivor=definitions.SingleOrDefault(value=>value&&value.cachedName==r.selectedSurvivor);
  Check(survivor&&survivor.bodyPrefab&&!survivor.hidden&&!survivor.unlockableDef&&string.IsNullOrEmpty(survivor.unlockableName)&&!survivor.GetRequiredExpansion()&&!survivor.GetRequiredEntitlement(),"Selected survivor requires an unavailable original unlock or entitlement");
  var body=survivor.bodyPrefab.GetComponent<CharacterBody>();
  Check(body&&body.bodyIndex!=BodyIndex.None&&BodyCatalog.GetBodyPrefab(body.bodyIndex)==survivor.bodyPrefab,"Selected source survivor/body catalog identity differs");
  return survivor.bodyPrefab;
 }
}
