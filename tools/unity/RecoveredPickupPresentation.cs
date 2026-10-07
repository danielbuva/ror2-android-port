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
 public void Present(CharacterMasterNotificationQueue.NotificationInfo info){
  var item=info.data as ItemDef;var equipment=info.data as EquipmentDef;
  if(item){title.text=RecoveredHudPresentation.Label(item.nameToken);description.text=RecoveredHudPresentation.Label(item.pickupToken);nativeFade.iconImage.texture=item.pickupIconTexture;title.color=ColorCatalog.GetColor(item.colorIndex);}
  else if(equipment){title.text=RecoveredHudPresentation.Label(equipment.nameToken);description.text=RecoveredHudPresentation.Label(equipment.pickupToken);nativeFade.iconImage.texture=equipment.pickupIconTexture;title.color=ColorCatalog.GetColor(equipment.colorIndex);}
  else throw new System.InvalidOperationException("Unsupported recovered pickup notification type");
  if(info.overrides!=null){if(!string.IsNullOrEmpty(info.overrides.titleText))title.text=RecoveredHudPresentation.Label(info.overrides.titleText);if(!string.IsNullOrEmpty(info.overrides.descriptionText))description.text=RecoveredHudPresentation.Label(info.overrides.descriptionText);nativeFade.iconImage.color=info.overrides.iconColor;}
  if(nativeFade.extraPanel)nativeFade.extraPanel.gameObject.SetActive(false);
  if(nativeFade.tempPanel)nativeFade.tempPanel.gameObject.SetActive(info.isTemporary);
 }
}
