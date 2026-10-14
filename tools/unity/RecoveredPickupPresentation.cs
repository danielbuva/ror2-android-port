using RoR2;
using RoR2.UI;
using TMPro;
using UnityEngine;

// Source-layout notification. Timing/fading remain original; only unavailable
// stock language/service bindings are replaced with locally recovered strings.
public sealed class RecoveredPickupPresentation : MonoBehaviour {
 public GenericNotification nativeFade;
 public AnimateUIAlpha nativeFlash;
 public TMP_Text title,description;
 public bool iconLoaded {get{return nativeFade&&nativeFade.iconImage&&nativeFade.iconImage.enabled&&nativeFade.iconImage.texture;}}
 public void Present(CharacterMasterNotificationQueue.NotificationInfo info){
  var item=info.data as ItemDef;var equipment=info.data as EquipmentDef;var drone=info.data as DroneDef;
  if(item){title.text=RecoveredHudPresentation.Label(item.nameToken);description.text=RecoveredHudPresentation.Label(item.pickupToken);title.color=ColorCatalog.GetColor(item.colorIndex);}
  else if(equipment){title.text=RecoveredHudPresentation.Label(equipment.nameToken);description.text=RecoveredHudPresentation.Label(equipment.pickupToken);title.color=ColorCatalog.GetColor(equipment.colorIndex);}
  else if(drone){title.text=RecoveredHudPresentation.Label(drone.nameToken);description.text=RecoveredHudPresentation.Label(drone.pickupToken);title.color=ColorCatalog.GetColor(drone.color);if(info.upgradeCount>0)title.text=Util.GetNameFromUpgradeCount(title.text,info.upgradeCount);}
  else throw new System.InvalidOperationException("Unsupported recovered pickup notification type: "+(info.data==null?"null":info.data.GetType().FullName));
  var image=nativeFade.iconImage;var loader=image.GetComponent<AsyncRawImage>();if(!loader)loader=image.gameObject.AddComponent<AsyncRawImage>();
  loader.renderer=image;loader.disableWhileLoading=true;loader.loadOnAssigned=true;loader.enabled=true;image.enabled=false;
  nativeFade.asyncIconImage=loader;loader.SetAssetOrDirectReference(item?(AsyncIconProvider)item:equipment?(AsyncIconProvider)equipment:drone);
  if(info.overrides!=null){if(!string.IsNullOrEmpty(info.overrides.titleText))title.text=RecoveredHudPresentation.Label(info.overrides.titleText);if(!string.IsNullOrEmpty(info.overrides.descriptionText))description.text=RecoveredHudPresentation.Label(info.overrides.descriptionText);nativeFade.iconImage.color=info.overrides.iconColor;}
  if(nativeFade.extraPanel)nativeFade.extraPanel.gameObject.SetActive(drone&&info.showExtra);
  if(nativeFade.tempPanel)nativeFade.tempPanel.gameObject.SetActive(info.isTemporary);
 }
}
