using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using RoR2;
using UnityEngine;
using UnityEngine.Events;
using UnityEngine.Networking;
using UnityEngine.AddressableAssets;

// Original purchase/selection/shrine code; owned layout, presentation and observations.
public sealed partial class MovementBatchProbe {
 [Serializable] public class CommerceObservation {public string source,item,costType;public uint netId;public int cost,purchases;public bool available,hidden,purchased;}
 [Serializable] public class CommercePurchase {public float at,healthAfter,shieldAfter;public string source,costType;public int cost;public uint moneyAfter;public bool debugAssisted;}
 [Serializable] public class CommercePlacement {public string source,scene;public Vector3 position,sourceScale,placedScale;public float radius,spawnDistance,requiredDistance;}
 [Serializable] public class CommerceReport {public string scope,lastMessage;public int shops,chanceShrines,bloodShrines,healingShrines,messages;public bool cleaned;public CommerceObservation[] objects;public List<CommercePurchase> purchases=new List<CommercePurchase>();public List<CommercePlacement> placements=new List<CommercePlacement>();public List<HealingWardObservation> healingWards=new List<HealingWardObservation>();}
 readonly List<PurchaseInteraction> commercePurchases=new List<PurchaseInteraction>();
 readonly List<MultiShopController> commerceShops=new List<MultiShopController>();
 readonly List<GameObject> commerceOwned=new List<GameObject>();
 readonly List<GameObject> commerceTemplates=new List<GameObject>();
 readonly Dictionary<PurchaseInteraction,UnityAction<CostTypeDef.PayCostContext,CostTypeDef.PayCostResults>> commerceListeners=new Dictionary<PurchaseInteraction,UnityAction<CostTypeDef.PayCostContext,CostTypeDef.PayCostResults>>();
 readonly Dictionary<PurchaseInteraction,int> commercePurchaseCounts=new Dictionary<PurchaseInteraction,int>();
 int commerceEffectIndex=-1,commerceEffectBaseline,commerceDirectShrineEffectLoads;bool ownsCommerceMessages;
 public static float CommerceRadius(GameObject source){
  float radius=0;var center=source.transform.position;
  foreach(var renderer in source.GetComponentsInChildren<Renderer>(true)){
   var bounds=renderer.bounds;var delta=bounds.center-center;
   radius=Mathf.Max(radius,new Vector2(Mathf.Abs(delta.x)+bounds.extents.x,Mathf.Abs(delta.z)+bounds.extents.z).magnitude);
  }
  var shop=source.GetComponent<MultiShopController>();
  if(shop&&shop.terminalPrefab)foreach(var position in shop.terminalPositions)radius=Mathf.Max(radius,Vector3.ProjectOnPlane(position.position-center,Vector3.up).magnitude+CommerceRadius(shop.terminalPrefab));
  if(radius<=0||float.IsNaN(radius)||float.IsInfinity(radius))throw new InvalidOperationException("Original commerce model footprint invalid: "+source.name);
  return radius;
 }
 GameObject PrepareCommerceSupport(Result cfg){
  if(cfg.worldCommerceAssets==null||cfg.worldCommerceAssets.Length==0)return null;
  commerceEffectIndex=Array.IndexOf(cfg.objectiveSupportPaths,"Prefabs/Effects/ShrineUseEffect");Check(commerceEffectIndex>=0,"Original shrine effect provider absent");
  var effect=objectiveSupportSources[commerceEffectIndex];Check(effect&&effect.GetComponent<EffectComponent>(),"Original shrine effect component missing");
  commerceEffectBaseline=(int)typeof(UnityEngine.ResourceManagement.AsyncOperations.AsyncOperationHandle<GameObject>).GetProperty("ReferenceCount",BindingFlags.Instance|BindingFlags.NonPublic).GetValue(objectiveSupportLeases[commerceEffectIndex]);
  Check(commerceEffectBaseline>0,"Original shrine effect lease absent");
  foreach(var renderer in effect.GetComponentsInChildren<Renderer>(true)){worldLootSourceMaterials.Add(renderer,renderer.sharedMaterials);worldLootSourceLayers[renderer.gameObject]=renderer.gameObject.layer;}PresentCommerceModel(effect.transform);return effect;
 }
 void PresentCommerceModel(Transform root){
  foreach(var renderer in root.GetComponentsInChildren<Renderer>(true)){
   if(!worldPresented.Add(renderer.GetInstanceID()))continue;
   // Native terminal clones inherit the owned template materials. Reusing those
   // copies preserves the first source-driven shader selection and its bindings.
   renderer.sharedMaterials=renderer.sharedMaterials.Select(source=>{if(!source)return null;if(worldMaterials.Contains(source))return source;var copy=new Material(source);copy.shader=Resources.Load<Shader>("StageSurfacePreview");copy.shaderKeywords=new string[0];AndroidMaterialPresentation.Apply(source,copy);worldMaterials.Add(copy);return copy;}).ToArray();
   if(!renderer.GetComponent<Collider>())renderer.gameObject.layer=30;
  }
 }
 void ConfigureCommerceObject(GameObject obj){
  var allowed=new[]{typeof(NetworkIdentity),typeof(MultiShopController),typeof(ShopTerminalBehavior),typeof(PurchaseInteraction),typeof(ShrineChanceBehavior),typeof(ShrineBloodBehavior),typeof(ShrineHealingBehavior),typeof(PickupDisplay),typeof(ModelLocator),typeof(EntityLocator),typeof(ChildLocator),typeof(PingInfoProvider),typeof(AnimationEvents),typeof(SpecialObjectAttributes)};
  foreach(var behaviour in obj.GetComponentsInChildren<MonoBehaviour>(true))behaviour.enabled=allowed.Contains(behaviour.GetType());
  foreach(var animator in obj.GetComponentsInChildren<Animator>(true)){animator.enabled=true;animator.cullingMode=AnimatorCullingMode.AlwaysAnimate;}
  PresentCommerceModel(obj.transform);
 }
 void WatchCommercePurchase(PurchaseInteraction purchase){
  Check(purchase&&!commerceListeners.ContainsKey(purchase),"Duplicate or missing original commerce purchase component");commercePurchases.Add(purchase);commercePurchaseCounts[purchase]=0;
  UnityAction<CostTypeDef.PayCostContext,CostTypeDef.PayCostResults> listener=(context,result)=>{
   commercePurchaseCounts[purchase]++;if((purchase.GetComponent<ShrineBloodBehavior>()||purchase.GetComponent<ShrineHealingBehavior>()))commerceDirectShrineEffectLoads++;
   Check(context.activatorBody==worldPlayer&&context.purchaseInteraction==purchase,"Original commerce purchase context changed");r.commerce.purchases.Add(new CommercePurchase{at=r.world.seconds,source=purchase.name,cost=context.cost,costType=purchase.costType.ToString(),moneyAfter=worldPlayer.master.money,healthAfter=worldPlayer.healthComponent.health,shieldAfter=worldPlayer.healthComponent.shield,debugAssisted=r.debugAcceleration!=null&&r.debugAcceleration.everAssisted});Save();
  };commerceListeners.Add(purchase,listener);purchase.onDetailedPurchaseServer.AddListener(listener);
 }
 void PrepareWorldCommerce(Result cfg,Vector3 origin){
  if(cfg.worldCommerceAssets==null||cfg.worldCommerceAssets.Length==0)return;
  Check((cfg.worldCommerceAssets.Length==4||cfg.worldCommerceAssets.Length==5)&&commerceEffectIndex>=0,"Original world commerce contract incomplete");r.phase="integrated-world-commerce";Save();
  if(r.commerce==null){r.commerce=new CommerceReport{scope="Original multishop terminal generation/choice/closure, chance shrine RNG/failure/refresh/drops, blood shrine health cost/gold/refresh and healing shrine native ward/radius/refresh. Authored near-entry layout/material adapter; no original SceneDirector placement, equipment, platform text-chat or normal health-cost acceptance under invincibility."};
   Check(!activeBodyClient.handlers.ContainsKey(59),"Unowned platform chat handler");ownsCommerceMessages=true;
   activeBodyClient.RegisterHandler(59,message=>{var native=ChatMessageBase.Instantiate(message.reader.ReadByte());Check(native!=null,"Original local gameplay message type missing");native.Deserialize(message.reader);r.commerce.messages++;var subject=native as Chat.SubjectFormatChatMessage;var simple=native as Chat.SimpleChatMessage;r.commerce.lastMessage=subject!=null?subject.baseToken:(simple!=null?simple.baseToken:native.GetType().Name);});
  }
  // Reserve the original camera orbit plus each unscaled source model footprint.
  // The old 8m offsets let tall terminals occupy the initial third-person view.
  var directions=new[]{Vector3.right,Vector3.left,Vector3.forward,Vector3.back,new Vector3(1,0,1).normalized,new Vector3(-1,0,1).normalized,new Vector3(1,0,-1).normalized,new Vector3(-1,0,-1).normalized};int start=0;
  var placed=new List<CommercePlacement>();CharacterCameraParamsData cameraParams;worldPlayer.GetComponent<CameraTargetParams>().CalcParams(out cameraParams);float cameraOrbit=cameraParams.idealLocalCameraPos.value.magnitude;
  foreach(var path in cfg.worldCommerceAssets){
   var source=artifactBundle.LoadAsset<GameObject>(path);Check(source&&source.GetComponentsInChildren<Component>(true).All(x=>x),"Original commerce source references missing: "+path);RaycastHit ground=default(RaycastHit);bool found=false;
   float radius=CommerceRadius(source),required=Mathf.Max(14,cameraOrbit+radius+2);
   for(int ring=0;ring<3&&!found;ring++)for(int i=0;i<directions.Length;i++){
    var candidate=origin+directions[(start+i)%directions.Length]*(required+ring*4);
    if(!Physics.Raycast(candidate+Vector3.up*20,Vector3.down,out ground,50,LayerIndex.world.mask,QueryTriggerInteraction.Ignore)||ground.collider.gameObject.scene!=stageGeometryScene||ground.normal.y<=.9f||Mathf.Abs(ground.point.y-origin.y)>=2||!InsideSourceStageBounds(ground.point))continue;
    if(placed.Any(x=>Vector3.ProjectOnPlane(x.position-ground.point,Vector3.up).magnitude<x.radius+radius+1))continue;
    found=true;start=(start+i+1)%directions.Length;break;
   }
   if(!found)continue;var obj=Instantiate(source,worldStaging.transform);obj.name=source.name;worldObjects.Add(obj);commerceOwned.Add(obj);ConfigureCommerceObject(obj);obj.transform.position=ground.point+Vector3.up*.4f;
   var placement=new CommercePlacement{source=source.name,scene=r.stageProgress.current,position=obj.transform.position,radius=radius,spawnDistance=Vector3.ProjectOnPlane(obj.transform.position-origin,Vector3.up).magnitude,requiredDistance=required,sourceScale=source.transform.localScale,placedScale=obj.transform.localScale};
   Check(placement.spawnDistance>=required-.1f&&placement.sourceScale==placement.placedScale,"Commerce spawn/camera clearance changed source scale");placed.Add(placement);r.commerce.placements.Add(placement);
   var shop=obj.GetComponent<MultiShopController>();if(shop){Check(!shop.doEquipmentInstead&&!shop.isTripleDroneVendor&&shop.terminalPositions.Length==3,"Original item-only multishop contract differs");var template=Instantiate(shop.terminalPrefab,worldStaging.transform);commerceTemplates.Add(template);commerceOwned.Add(template);ConfigureCommerceObject(template);var terminal=template.GetComponent<ShopTerminalBehavior>();Check(terminal&&terminal.selfGeneratePickup&&terminal.dropTable is BasicPickupDropTable,"Original self-generating item terminal contract differs");terminal.dropTable=ObjectiveDropTable(terminal.dropTable);((BasicPickupDropTable)terminal.dropTable).RegenerateDropTable(Run.instance);Check(terminal.dropTable.GetPickupCount()>0,"Original terminal selector empty");shop.terminalPrefab=template;}
   var chance=obj.GetComponent<ShrineChanceBehavior>();if(chance){Check(chance.dropTable,"Original chance shrine drop table absent");Check(chance.effectPrefabShrineRewardNormal,"Original chance shrine normal effect absent");chance.dropTable=ObjectiveDropTable(chance.dropTable);var table=chance.dropTable as BasicPickupDropTable;Check(table,"Original chance shrine table type changed");table.RegenerateDropTable(Run.instance);Check(table.GetPickupCount()>0,"Original chance shrine source selector empty");}
   obj.transform.SetParent(null,true);obj.SetActive(true);NetworkServer.Spawn(obj);
   if(shop){commerceShops.Add(shop);foreach(var terminal in shop.terminalGameObjectsList){Check(terminal&&terminal.GetComponent<ShopTerminalBehavior>()&&terminal.GetComponent<NetworkIdentity>().netId.Value!=0,"Original multishop terminal factory/network identity failed");commerceOwned.Add(terminal);worldObjects.Add(terminal);PresentCommerceModel(terminal.transform);WatchCommercePurchase(terminal.GetComponent<PurchaseInteraction>());}r.commerce.shops++;}
   else{WatchCommercePurchase(obj.GetComponent<PurchaseInteraction>());if(chance)r.commerce.chanceShrines++;else if(obj.GetComponent<ShrineHealingBehavior>()){r.commerce.healingShrines++;}else{Check(obj.GetComponent<ShrineBloodBehavior>(),"Unknown original shrine");r.commerce.bloodShrines++;}}
  }
 }
 void ObserveWorldCommerce(){
  if(r.commerce==null)return;
  ObserveHealingCommerceWards();
  foreach(var purchase in commercePurchases){if(!purchase)continue;var terminal=purchase.GetComponent<ShopTerminalBehavior>();if(terminal&&terminal.pickupDisplay){var model=(GameObject)typeof(PickupDisplay).GetField("modelObject",BindingFlags.NonPublic|BindingFlags.Instance).GetValue(terminal.pickupDisplay);if(model)PresentCommerceModel(model.transform);}}
  if(Time.frameCount%30!=0)return;
  r.commerce.objects=commercePurchases.Where(x=>x).Select(x=>{var terminal=x.GetComponent<ShopTerminalBehavior>();var pickup=terminal?PickupCatalog.GetPickupDef(terminal.Networkpickup.pickupIndex):null;return new CommerceObservation{source=x.name,netId=x.netId.Value,cost=x.cost,costType=x.costType.ToString(),available=x.available,purchases=commercePurchaseCounts[x],item=pickup==null?null:pickup.internalName,hidden=terminal&&terminal.Networkhidden,purchased=terminal&&terminal.NetworkhasBeenPurchased};}).ToArray();
 }
 GameObject AffordableWorldCommerce(){return commercePurchases.FirstOrDefault(x=>x&&x.available&&x.costType==CostTypeIndex.Money&&commercePurchaseCounts[x]==0&&worldPlayer.master.money>=x.cost)?.gameObject;}
 void CleanupWorldCommerce(bool final=false){
  CleanupHealingCommerceWards();
  foreach(var pair in commerceListeners)if(pair.Key)pair.Key.onDetailedPurchaseServer.RemoveListener(pair.Value);commerceListeners.Clear();commercePurchases.Clear();commercePurchaseCounts.Clear();commerceShops.Clear();
  foreach(var template in commerceTemplates)if(template)Destroy(template);commerceTemplates.Clear();
  if(!final)return;
  if(ownsCommerceMessages&&activeBodyClient!=null){activeBodyClient.UnregisterHandler(59);ownsCommerceMessages=false;}
  if(commerceEffectIndex>=0){var lease=objectiveSupportLeases[commerceEffectIndex];int extra=(int)typeof(UnityEngine.ResourceManagement.AsyncOperations.AsyncOperationHandle<GameObject>).GetProperty("ReferenceCount",BindingFlags.Instance|BindingFlags.NonPublic).GetValue(lease)-commerceEffectBaseline;Check(extra==commerceDirectShrineEffectLoads,"Unattributed original blood/healing shrine effect loads");for(int i=0;i<extra;i++)Addressables.Release(lease.Result);commerceEffectIndex=-1;}
 }
}
