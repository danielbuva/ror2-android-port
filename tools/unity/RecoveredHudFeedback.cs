using System;
using System.Collections.Generic;
using RoR2;
using RoR2.UI;
using RoR2.Items;
using UnityEngine;

public sealed partial class RecoveredHudPresentation {
 public RectTransform buffRoot,notificationRoot;
 public BuffIcon buffTemplate;public float buffWidth;
 public RecoveredPickupPresentation notificationTemplate;
 readonly Dictionary<BuffIndex,BuffIcon> buffViews=new Dictionary<BuffIndex,BuffIcon>();
 CharacterMasterNotificationQueue feedbackQueue;CharacterMaster feedbackMaster;
 CharacterMasterNotificationQueue.NotificationInfo currentNotice;
 RecoveredPickupPresentation notificationView;bool ownsFeedbackQueue;
 float priorQueueFixedTime=-1;
 void ValidateFeedback(){
  if(!buffRoot||!buffTemplate||!buffTemplate.iconImage||!buffTemplate.stackCount||buffWidth<=0||!notificationRoot||!notificationTemplate||!notificationTemplate.nativeFade||!notificationTemplate.nativeFade.canvasGroup||!notificationTemplate.title||!notificationTemplate.description)
   throw new InvalidOperationException("Recovered feedback source references absent");
 }
 public void QueuePickup(CharacterMaster master,UniquePickup pickup){
  if(master!=feedbackMaster||!feedbackQueue||!master.hasAuthority)throw new InvalidOperationException("Original pickup queue authority/owner changed");
  var def=PickupCatalog.GetPickupDef(pickup.pickupIndex);var item=def==null?null:ItemCatalog.GetItemDef(def.itemIndex);
  if(def==null||item&&item.hidden)return;
  // Preserve the original game's suppression of already-transformed pickups.
  var transformed=ContagiousItemManager.GetTransformedItemIndex(item?item.itemIndex:ItemIndex.None);
  if(item&&transformed!=ItemIndex.None&&master.inventory.GetItemCountEffective(transformed)>0)return;
  CharacterMasterNotificationQueue.PushPickupNotification(master,pickup.pickupIndex,pickup.isTempItem,pickup.upgradeValue);
 }
 void PresentFeedback(CharacterBody body,Observation report){
  if(!feedbackQueue){
   feedbackMaster=body.master;
   if(feedbackMaster.GetComponent<CharacterMasterNotificationQueue>())throw new InvalidOperationException("Unowned pickup notification queue");
   feedbackQueue=CharacterMasterNotificationQueue.GetNotificationQueueForMaster(feedbackMaster);ownsFeedbackQueue=true;
  }
  if(body.master!=feedbackMaster)throw new InvalidOperationException("Recovered feedback master changed");
  // The composed master remains intentionally inactive. Its original queue
  // otherwise never dequeues; supply only that scheduler using the native clock.
  // An active master retains Unity's own FixedUpdate, with no duplicate tick.
  if(!feedbackQueue.gameObject.activeInHierarchy&&Run.instance&&priorQueueFixedTime!=Run.instance.fixedTime){
   feedbackQueue.FixedUpdate();priorQueueFixedTime=Run.instance.fixedTime;report.notificationClockTicks++;report.ownedNotificationScheduler=true;
  }
  report.notificationFixedTime=Run.instance?Run.instance.fixedTime:0;report.notificationT=feedbackQueue.GetCurrentNotificationT();
  int visible=0;
  foreach(var index in BuffCatalog.nonHiddenBuffIndices){
   int count=body.GetBuffCount(index);BuffIcon icon;
   if(count<=0){if(buffViews.TryGetValue(index,out icon))icon.gameObject.SetActive(false);continue;}
   var def=BuffCatalog.GetBuffDef(index);if(!def||!def.iconSprite)continue;
   if(!buffViews.TryGetValue(index,out icon)){icon=Instantiate(buffTemplate,buffRoot,false);icon.name="Owned original buff icon "+index;buffViews.Add(index,icon);}
   bool changed=icon.buffDef!=def||icon.buffCount!=count;icon.buffDef=def;icon.buffCount=count;icon.gameObject.SetActive(true);
   icon.rectTransform.anchoredPosition=new Vector2(visible*buffWidth,0);icon.UpdateIcon();if(changed){icon.Flash();report.buffUpdates++;}visible++;
  }
  report.buffs=visible;report.peakBuffs=Mathf.Max(report.peakBuffs,visible);report.nativeNotificationQueue=true;
  var notice=feedbackQueue.GetCurrentNotification();
  if(!ReferenceEquals(notice,currentNotice)){
   if(notificationView)Destroy(notificationView.gameObject);notificationView=null;currentNotice=notice;report.notification="";
   if(notice!=null){notificationView=Instantiate(notificationTemplate,notificationRoot,false);notificationView.Present(notice);notificationView.gameObject.SetActive(true);report.pickupNotifications++;report.notification=notificationView.title.text;}
  }
  if(notificationView)notificationView.nativeFade.SetNotificationT(feedbackQueue.GetCurrentNotificationT());
 }
 public void CleanupFeedback(Observation report){
  if(notificationView)Destroy(notificationView.gameObject);notificationView=null;currentNotice=null;
  if(ownsFeedbackQueue&&feedbackQueue)Destroy(feedbackQueue);feedbackQueue=null;feedbackMaster=null;ownsFeedbackQueue=false;
  buffViews.Clear();report.feedbackCleaned=true;
 }
}
