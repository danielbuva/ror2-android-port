using System;
using System.Collections;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using RoR2;
using UnityEngine;
using UnityEngine.Networking;

// Diagnostic source-spawned pickup; original catalog, wait, permission, grant and stats remain in charge.
public sealed partial class MovementBatchProbe {
 [Serializable] public class ItemPickupReport {
  public bool catalogReady,factory,earlyDisabled,available,granted,destroyed,statsChanged,cleaned,iconLoaded;
  public int catalogCount,itemIndex,pickupIndex,countBefore,countAfter,acquisitionsBefore,acquisitionsAfter;public uint netId;
  public float waitDuration,waitSeconds,attackSpeedBefore,attackSpeedAfter;public string grantMethod,scope;
 }
 readonly Dictionary<FieldInfo,object> priorPickupFields=new Dictionary<FieldInfo,object>();IDictionary pickupNameMap,pickupTierMap;ResourceAvailability priorPickupAvailability;bool ownsPickupCatalog;
 GameObject pickupTemplates,pickupTemplate,pickupObject;GenericPickupController ownedPickup;ItemDef pickupSyringe;Texture pickupIcon;
 void DrawItemPickupObservation(){if(r.itemPickup==null||!r.itemPickup.catalogReady)return;GUI.Label(new Rect(20,185,800,30),"Original Syringe pickup | count: "+r.itemPickup.countAfter+" | attack speed: "+r.itemPickup.attackSpeedAfter.ToString("F2"));if(pickupIcon)GUI.DrawTexture(new Rect(20,220,64,64),pickupIcon,ScaleMode.ScaleToFit);}
 IEnumerator ProbeOriginalItemPickup(CharacterBody player,Result cfg){
  r.itemPickup=new ItemPickupReport{scope="Original source-spawned base Syringe through original factory/delay/server interaction/grant/natural stats; diagnostic subset catalogs and source icon, owned PickupDisplay omitted. No chest/drop-table/progression/profile/client effects/original pickup model/physical interaction acceptance."};r.phase="original-item-catalog";Save();
  Check(Run.instance&&r.runClock.originalCallbacks&&r.barrel.cleaned&&NetworkServer.active&&!NetworkClient.active&&PickupCatalog.pickupCount==0,"Accepted clock/barrel/server or empty pickup catalog changed");
  pickupSyringe=artifactBundle.LoadAsset<ItemDef>(cfg.statItemAsset);var junk=artifactBundle.LoadAsset<ItemDef>(cfg.junkAsset);
  Check(pickupSyringe&&pickupSyringe.name=="Syringe"&&pickupSyringe==RoR2Content.Items.Syringe&&!pickupSyringe.requiredExpansion&&!pickupSyringe.unlockableDef&&pickupSyringe.tier==ItemTier.Tier1&&junk&&junk==DLC3Content.Items.Junk,"Original Syringe/Junk item definition contract failed");
  Check(ItemCatalog.GetItemDef(pickupSyringe.itemIndex)==pickupSyringe&&ItemCatalog.GetItemDef(junk.itemIndex)==junk&&!Run.instance.IsItemExpansionLocked(pickupSyringe.itemIndex)&&Run.instance.IsItemExpansionLocked(junk.itemIndex),"Original catalog/allowed base item/internal-only Junk scope changed");
  var flags=BindingFlags.Static|BindingFlags.NonPublic;foreach(var name in new[]{"entries","itemIndexToPickupIndex","equipmentIndexToPickupIndex","artifactIndexToPickupIndex","miscPickupIndexToPickupIndex","droneIndexToPickupIndex","<pickupCount>k__BackingField"}){var field=typeof(PickupCatalog).GetField(name,flags);Check(field!=null,"Original pickup catalog field missing: "+name);priorPickupFields[field]=field.GetValue(null);}
  pickupNameMap=(IDictionary)typeof(PickupCatalog).GetField("nameToPickupIndex",flags).GetValue(null);pickupTierMap=(IDictionary)typeof(PickupCatalog).GetField("itemTierToPickupIndex",flags).GetValue(null);Check(pickupNameMap.Count==0&&pickupTierMap.Count==0,"Existing pickup lookup maps");priorPickupAvailability=PickupCatalog.availability;ownsPickupCatalog=true;
  var defs=ItemCatalog.allItemDefs.Select(item=>item.CreatePickupDef()).ToArray();PickupCatalog.SetEntries(defs);
  foreach(var def in defs)Check(PickupCatalog.GetPickupDef(PickupCatalog.FindPickupIndex(def.itemIndex))==def&&PickupCatalog.FindPickupIndex(def.internalName)==def.pickupIndex,"Original item/pickup catalog identity round trip failed");
  var index=PickupCatalog.FindPickupIndex(pickupSyringe.itemIndex);var pickupDef=PickupCatalog.GetPickupDef(index);Check(pickupDef.itemIndex==pickupSyringe.itemIndex&&pickupDef.attemptGrant.Method.DeclaringType==typeof(ItemDef)&&pickupDef.attemptGrant.Method.Name=="AttemptGrant","Original item grant delegate changed");
  r.itemPickup.catalogCount=PickupCatalog.pickupCount;r.itemPickup.itemIndex=(int)pickupSyringe.itemIndex;r.itemPickup.pickupIndex=index.value;r.itemPickup.grantMethod=pickupDef.attemptGrant.Method.DeclaringType.FullName+"."+pickupDef.attemptGrant.Method.Name;r.itemPickup.catalogReady=true;
  pickupIcon=pickupSyringe.pickupIconTexture;r.itemPickup.iconLoaded=pickupIcon&&pickupIcon.width>1&&pickupIcon.height>1;Check(r.itemPickup.iconLoaded,"Original Syringe icon not recovered");
  var source=GenericPickupSource(cfg);Check(source&&source.name=="GenericPickup"&&source.GetComponentsInChildren<Component>(true).All(x=>x),"Original GenericPickup prefab/reference contract failed");
  pickupTemplates=new GameObject("Owned inactive pickup template");pickupTemplates.SetActive(false);pickupTemplate=Instantiate(source,pickupTemplates.transform);pickupTemplate.name=source.name;
  foreach(var component in pickupTemplate.GetComponentsInChildren<MonoBehaviour>(true)){if(component.GetType().Name.StartsWith("Ak",StringComparison.Ordinal)){DestroyImmediate(component);continue;}component.enabled=component is NetworkIdentity||component is GenericPickupController||component is EntityLocator;}
  var templateController=pickupTemplate.GetComponent<GenericPickupController>();Check(templateController&&templateController.waitDuration==.5f,"Original pickup half-second delay changed");if(templateController.pickupDisplay)templateController.pickupDisplay.gameObject.SetActive(false);templateController.pickupDisplay=null;pickupTemplate.SetActive(true);
  r.itemPickup.countBefore=player.inventory.GetItemCountPermanent(pickupSyringe);r.itemPickup.acquisitionsBefore=player.inventory.itemAcquisitionOrder.Count;r.itemPickup.attackSpeedBefore=player.attackSpeed;Check(r.itemPickup.countBefore==0&&Mathf.Abs(r.itemPickup.attackSpeedBefore-1)<.001f,"Original empty Syringe/base attack speed prerequisite changed");
  var info=new GenericPickupController.CreatePickupInfo{prefabOverride=pickupTemplate,position=player.characterMotor.Motor.TransientPosition+Vector3.right*4,rotation=Quaternion.identity,pickup=new UniquePickup{pickupIndex=index}};ownedPickup=GenericPickupController.CreatePickup(in info);Check(ownedPickup,"Original pickup factory returned no controller");pickupObject=ownedPickup.gameObject;yield return null;
  r.itemPickup.netId=pickupObject.GetComponent<NetworkIdentity>().netId.Value;r.itemPickup.factory=r.itemPickup.netId!=0&&ownedPickup.pickup.pickupIndex==index&&!ownedPickup.pickup.isTempItem&&!ownedPickup.Recycled&&!ownedPickup.Duplicated;r.itemPickup.waitDuration=ownedPickup.waitDuration;
  var interactor=player.GetComponent<Interactor>();r.itemPickup.earlyDisabled=ownedPickup.GetInteractability(interactor)==Interactability.Disabled;Check(r.itemPickup.factory&&r.itemPickup.earlyDisabled,"Original factory identity/initial delay contract failed");
  var waitStart=(Run.FixedTimeStamp)typeof(GenericPickupController).GetField("waitStartTime",BindingFlags.Instance|BindingFlags.NonPublic).GetValue(ownedPickup);
  float deadline=Time.realtimeSinceStartup+2;while(ownedPickup.GetInteractability(interactor)!=Interactability.Available&&Time.realtimeSinceStartup<deadline){yield return null;ObserveOriginalRunClock();Check(player.inventory.GetItemCountPermanent(pickupSyringe)==0,"Pickup granted before controlled interaction");}
  r.itemPickup.waitSeconds=waitStart.timeSince;r.itemPickup.available=ownedPickup.GetInteractability(interactor)==Interactability.Available;Check(r.itemPickup.available&&r.itemPickup.waitSeconds>=.5f&&r.itemPickup.waitSeconds<.7f,"Original clock wait/permission contract incomplete");
  r.phase="original-item-grant";Save();interactor.AttemptInteraction(pickupObject);r.itemPickup.countAfter=player.inventory.GetItemCountPermanent(pickupSyringe);r.itemPickup.acquisitionsAfter=player.inventory.itemAcquisitionOrder.Count;r.itemPickup.granted=r.itemPickup.countAfter==1&&r.itemPickup.acquisitionsAfter==r.itemPickup.acquisitionsBefore+1&&player.inventory.GetItemCountPermanent(junk)==0;Check(r.itemPickup.granted,"Original item grant/acquisition order failed");
  yield return null;yield return null;r.itemPickup.destroyed=!pickupObject;Check(r.itemPickup.destroyed,"Consumed original pickup not destroyed");deadline=Time.realtimeSinceStartup+2;while(Mathf.Abs(player.attackSpeed-1.15f)>.001f&&Time.realtimeSinceStartup<deadline)yield return null;
  r.itemPickup.attackSpeedAfter=player.attackSpeed;r.itemPickup.statsChanged=Mathf.Abs(r.itemPickup.attackSpeedAfter-r.itemPickup.attackSpeedBefore*1.15f)<.001f;Check(r.itemPickup.statsChanged,"Original Syringe inventory/stat recalculation failed");Save();yield return new WaitForSeconds(2);
  CleanupOriginalItemPickup();yield return null;yield return null;r.itemPickup.cleaned=!pickupObject&&!pickupTemplates&&!pickupTemplate&&!ownsPickupCatalog&&PickupCatalog.pickupCount==0&&pickupNameMap.Count==0&&pickupTierMap.Count==0;Check(r.itemPickup.cleaned,"Owned pickup/catalog teardown incomplete");Save();
 }
 void CleanupOriginalItemPickup(){
  if(pickupObject){if(NetworkServer.active)NetworkServer.Destroy(pickupObject);else Destroy(pickupObject);}if(pickupTemplates)Destroy(pickupTemplates);
  if(ownsPickupCatalog){pickupNameMap.Clear();pickupTierMap.Clear();foreach(var field in priorPickupFields)field.Key.SetValue(null,field.Value);PickupCatalog.availability=priorPickupAvailability;ownsPickupCatalog=false;}
 }
}
