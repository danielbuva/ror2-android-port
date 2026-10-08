using System;
using System.Linq;
using System.Collections.Generic;
using RoR2;
using UnityEngine;

// Original chest tables, state/animation events and factories; adapted near-entry placement.
public sealed partial class MovementBatchProbe {
 [Serializable] public class WorldChestSpec {public string name,asset,openingClip;}
 [Serializable] public class WorldChestObservation {public string source,scene,table,costType;public uint netId;public int cost,domain,rolledPickup;public bool opened;}
 [Serializable] public class ChestBreadthReport {public int sourceVariants,placed,opened;public List<WorldChestObservation> objects=new List<WorldChestObservation>();public string scope="Original large/legendary/stealth/category chest selection, purchase, animation/ejection contracts; owned source tables and adapted placement. Registration/placement is not purchase/drop acceptance or original SceneDirector population.";}
 readonly Dictionary<ChestBehavior,WorldChestObservation> worldBreadthChests=new Dictionary<ChestBehavior,WorldChestObservation>();
 Type[] WorldChestTypes(Result cfg){
  if(cfg.worldChestBreadth==null)return new Type[0];
  return cfg.worldChestBreadth.SelectMany(spec=>{var source=artifactBundle.LoadAsset<GameObject>(spec.asset);Check(source,"Original chest state source absent");var chest=source.GetComponent<ChestBehavior>();return new[]{chest.openState.stateType,chest.closingState.stateType}.Concat(source.GetComponents<EntityStateMachine>().SelectMany(machine=>new[]{machine.initialStateType.stateType,machine.mainStateType.stateType}));}).Where(type=>type!=null).Distinct().ToArray();
 }
 void AddWorldChestBreadth(Result cfg,Vector3 origin){
  if(cfg.worldChestBreadth==null||cfg.worldChestBreadth.Length==0)return;
  if(r.chestBreadth==null)r.chestBreadth=new ChestBreadthReport();
  // Serialized inline reports may already exist before any live content is owned.
  r.chestBreadth.sourceVariants=cfg.worldChestBreadth.Length;
  worldBreadthChests.Clear();var directions=new[]{new Vector3(1,0,1).normalized,new Vector3(-1,0,1).normalized,new Vector3(1,0,-1).normalized,new Vector3(-1,0,-1).normalized,Vector3.right,Vector3.left};
  for(int i=0;i<cfg.worldChestBreadth.Length;i++){
   var spec=cfg.worldChestBreadth[i];var source=artifactBundle.LoadAsset<GameObject>(spec.asset);Check(source&&source.name==spec.name,"Original additional chest identity absent");var chest=source.GetComponent<ChestBehavior>();Check(chest&&chest.dropTable&&source.GetComponent<PurchaseInteraction>()&&source.GetComponent<ModelLocator>(),"Original chest purchase/table/model contract absent: "+spec.name);
   var table=ObjectiveDropTable(chest.dropTable);Call(table,"Regenerate",Run.instance);Check(table.GetPickupCount()>0,"Original additional chest eligible selector empty: "+spec.name);
   OwnChestAnimationSources(source.GetComponent<ModelLocator>().modelTransform,spec.openingClip);
   GameObject obj=null;float distance=Mathf.Max(11,CommerceRadius(source)+9);
   for(int ring=0;ring<3&&!obj;ring++){var candidate=origin+directions[i%directions.Length]*(distance+ring*4);if(InsideSourceStageBounds(candidate))obj=CreateWorldInteractable(source,candidate,true,table);}
   if(!obj)continue;var placed=obj.GetComponent<ChestBehavior>();var purchase=obj.GetComponent<PurchaseInteraction>();worldChests.Add(placed);
   var row=new WorldChestObservation{source=spec.name,scene=SceneCatalog.GetSceneDefForCurrentScene().cachedName,table=chest.dropTable.name,cost=purchase.cost,costType=purchase.costType.ToString(),domain=table.GetPickupCount(),netId=placed.netId.Value,rolledPickup=-1};Check(row.netId!=0&&ReferenceEquals(placed.dropTable,table),"Owned original chest network/table assignment failed");worldBreadthChests.Add(placed,row);r.chestBreadth.objects.Add(row);r.chestBreadth.placed++;
  }
 }
 void ObserveWorldChestBreadth(){if(r.chestBreadth==null)return;foreach(var pair in worldBreadthChests){if(!pair.Key)continue;pair.Value.opened=pair.Key.NetworkisChestOpened;pair.Value.rolledPickup=pair.Key.currentPickup.pickupIndex.value;}r.chestBreadth.opened=r.chestBreadth.objects.Count(x=>x.opened);}
}
