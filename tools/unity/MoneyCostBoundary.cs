using System;
using System.Collections;
using System.Reflection;
using RoR2;
using UnityEngine;
using UnityEngine.Networking;

// Calls the original money-cost delegates with the actual original player. Not chest progression.
public sealed partial class MovementBatchProbe {
 [Serializable] public class MoneyCostReport {
  public bool sourceReady,catalogReady,initiallyUnaffordable,affordable,paid,unaffordableAfter,cleaned;
  public int sourceCost,catalogCount,shopEquipmentIndex;public uint moneyBefore,funding,moneyFunded,moneyAfter;
  public string affordableMethod,payMethod,scope;
 }
 FieldInfo moneyCatalogField;object priorMoneyCatalog;bool ownsMoneyCatalog;
 IEnumerator ProbeOriginalMoneyCost(CharacterBody player,Result cfg){
  r.moneyCost=new MoneyCostReport{scope="Original Money CostTypeDef affordability/payment delegates with actual Commando/master/inventory and host-receipted unchanged source Chest1 cost. Explicit diagnostic funding through original GiveMoney; no PurchaseInteraction callbacks/chest opening/drops/profile/progression acceptance."};r.phase="original-money-cost";Save();
  Check(r.itemPickup.granted&&r.itemPickup.cleaned&&Run.instance&&NetworkServer.active&&player.master&&player.inventory.currentEquipmentIndex==EquipmentIndex.None,"Accepted pickup/server/player prerequisites changed");
  r.moneyCost.sourceReady=cfg.moneySourceCost==25&&cfg.moneySourceSha256!=null&&cfg.moneySourceSha256.Length==64;Check(r.moneyCost.sourceReady,"Host-receipted original Chest1 cost data missing");r.moneyCost.sourceCost=cfg.moneySourceCost;
  var card=DLC1Content.Equipment.MultiShopCard;Check(card&&card.name=="MultiShopCard"&&card.equipmentIndex!=EquipmentIndex.None&&EquipmentCatalog.GetEquipmentDef(card.equipmentIndex)==card,"Required original empty-equipment comparison definition missing");r.moneyCost.shopEquipmentIndex=(int)card.equipmentIndex;
  moneyCatalogField=typeof(CostTypeCatalog).GetField("costTypeDefs",BindingFlags.Static|BindingFlags.NonPublic);Check(moneyCatalogField!=null,"Original money catalog field missing");priorMoneyCatalog=moneyCatalogField.GetValue(null);Check(priorMoneyCatalog==null,"Existing cost catalog; refuse replacement");ownsMoneyCatalog=true;StaticCall(typeof(CostTypeCatalog),"Init");
  var money=CostTypeCatalog.GetCostTypeDef(CostTypeIndex.Money);Check(money!=null&&money.name=="Money"&&CostTypeCatalog.costTypeCount==16,"Original money catalog initialization failed");
  var affordable=(Delegate)typeof(CostTypeDef).GetProperty("isAffordable").GetGetMethod(true).Invoke(money,null);var pay=(Delegate)typeof(CostTypeDef).GetProperty("payCost").GetGetMethod(true).Invoke(money,null);
  Check(affordable!=null&&pay!=null&&affordable.Method.DeclaringType.Assembly==typeof(CostTypeCatalog).Assembly&&pay.Method.DeclaringType.Assembly==typeof(CostTypeCatalog).Assembly,"Original cost delegates replaced");r.moneyCost.affordableMethod=affordable.Method.DeclaringType.FullName+"."+affordable.Method.Name;r.moneyCost.payMethod=pay.Method.DeclaringType.FullName+"."+pay.Method.Name;r.moneyCost.catalogReady=true;r.moneyCost.catalogCount=CostTypeCatalog.costTypeCount;
  var interactor=player.GetComponent<Interactor>();r.moneyCost.moneyBefore=player.master.money;r.moneyCost.initiallyUnaffordable=!money.IsAffordable(r.moneyCost.sourceCost,interactor);Check(r.moneyCost.moneyBefore==17&&r.moneyCost.initiallyUnaffordable,"Original insufficient-money prerequisite changed");
  r.moneyCost.funding=(uint)r.moneyCost.sourceCost-r.moneyCost.moneyBefore;player.master.GiveMoney(r.moneyCost.funding);r.moneyCost.moneyFunded=player.master.money;r.moneyCost.affordable=money.IsAffordable(r.moneyCost.sourceCost,interactor);Check(r.moneyCost.moneyFunded==r.moneyCost.sourceCost&&r.moneyCost.affordable,"Original exact-money affordability failed");
  using(var contextLease=CostTypeDef.PayCostContext.pool.Request(out var context))using(var resultLease=CostTypeDef.PayCostResults.pool.Request(out var result)){
   context.activator=interactor;context.activatorBody=player;context.activatorMaster=player.master;context.activatorInventory=player.inventory;context.costTypeDef=money;context.cost=r.moneyCost.sourceCost;context.avoidedItemIndex=ItemIndex.None;
   money.PayCost(context,result);Check(result.itemStacksTaken.Count==0&&result.equipmentTaken.Count==0,"Money payment removed items/equipment");
  }
  r.moneyCost.moneyAfter=player.master.money;r.moneyCost.paid=r.moneyCost.moneyFunded-r.moneyCost.moneyAfter==r.moneyCost.sourceCost;r.moneyCost.unaffordableAfter=!money.IsAffordable(r.moneyCost.sourceCost,interactor);Check(r.moneyCost.paid&&r.moneyCost.moneyAfter==0&&r.moneyCost.unaffordableAfter&&player.inventory.GetItemCountPermanent(RoR2Content.Items.Syringe)==1&&player.inventory.currentEquipmentIndex==EquipmentIndex.None,"Original money payment/inventory conservation failed");Save();yield return null;
  CleanupOriginalMoneyCost();r.moneyCost.cleaned=!ownsMoneyCatalog&&ReferenceEquals(moneyCatalogField.GetValue(null),priorMoneyCatalog);Check(r.moneyCost.cleaned,"Original cost catalog restoration failed");Save();
 }
 void CleanupOriginalMoneyCost(){if(ownsMoneyCatalog){moneyCatalogField.SetValue(null,priorMoneyCatalog);ownsMoneyCatalog=false;}}
}
