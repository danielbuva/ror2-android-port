using System;
using System.Collections.Generic;
using RoR2;
using TMPro;
using UnityEngine;
using UnityEngine.UI;

// Owned read-only Android bindings over locally generated source-layout views.
// No LocalUser, stock profile, platform service or original HUD lifecycle is created.
public sealed partial class RecoveredHudPresentation : MonoBehaviour {
 [Serializable] public class Entry {public string key,value;}
 [Serializable] public class Strings {public Entry[] entries;}
 [Serializable] public class SkillView {public Image icon;public TMP_Text cooldown,stock,key;public GameObject ready;}
 [Serializable] public class Observation {
  public bool ready,menuVisible,cleaned;public int frames,items,skillSlots;public float health,shield,barrier,level,bossHealth,charge;
  public uint money;public float menuStartX,menuStartY;public int screenWidth,screenHeight;public string stage,objective,scope="Source layout/assets with owned Android data bindings; mobile font/UI shader approximation, not stock startup or PC parity.";
  public int buffs,peakBuffs,buffUpdates,pickupNotifications,notificationClockTicks;public bool nativeNotificationQueue,feedbackCleaned,ownedNotificationScheduler;public float notificationT,notificationFixedTime;public string notification;
 }
 public TMP_Text currentHealth,fullHealth,level,money,timer,objective,stage,bossName,bossHealth;
 public TMP_Text stageCount,ambientLevel,difficulty;public RoR2.UI.TimerText timerFormatter;public LayoutElement objectiveLayout;
 public RoR2.UI.DifficultyBarController.SegmentDef[] difficultySegments;public float levelsPerSegment;public Image difficultyBackground;
 public RectTransform experienceFill;public Image healthFill,shieldFill,barrierFill,bossFill;
 public GameObject bossContainer;public SkillView[] skills;public RectTransform inventoryRoot;
 public RecoveredHudPresentation itemTemplate;public RawImage itemImage;public TMP_Text itemCount;
 public Button startButton,quitButton;public bool isMenu;
 public RoR2.UI.CrosshairController.SpritePosition[] spreadPositions;public RawImage[] spreadImages;public float spreadAngle,minSpreadAlpha,maxSpreadAlpha;
 readonly Dictionary<ItemIndex,RecoveredHudPresentation> itemViews=new Dictionary<ItemIndex,RecoveredHudPresentation>();
 static Dictionary<string,string> strings;
 public static string Label(string token){
  if(strings==null){var file=Resources.Load<TextAsset>("RecoveredUI/Strings");if(!file)throw new InvalidOperationException("Recovered UI strings absent");strings=new Dictionary<string,string>();foreach(var e in JsonUtility.FromJson<Strings>(file.text).entries)strings[e.key]=e.value;}
  string value;return !string.IsNullOrEmpty(token)&&strings.TryGetValue(token,out value)?value:token??"";
 }
 public void Validate(){
  if(isMenu){if(!startButton||!quitButton)throw new InvalidOperationException("Recovered menu bindings absent");return;}
  if(!currentHealth||!fullHealth||!level||!money||!timer||!timerFormatter||!stageCount||!ambientLevel||!difficulty||!difficultyBackground||!objective||!objectiveLayout||!stage||!healthFill||!shieldFill||!barrierFill||!experienceFill||!bossFill||!bossContainer||!bossName||!bossHealth||!inventoryRoot||!itemTemplate||skills==null||skills.Length!=4)
   throw new InvalidOperationException("Recovered HUD source references absent");
  foreach(var s in skills)if(!s.icon||!s.cooldown||!s.stock||!s.key)throw new InvalidOperationException("Recovered skill display reference absent");
  ValidateFeedback();
 }
 public void BindMenu(Action start){Validate();startButton.onClick=new Button.ButtonClickedEvent();quitButton.onClick=new Button.ButtonClickedEvent();startButton.onClick.AddListener(()=>start());quitButton.onClick.AddListener(()=>Application.Quit());}
 public void Present(CharacterBody body,MovementBatchProbe.Result run,Observation report){
  if(!body||!body.master||!body.healthComponent)return;
  var health=body.healthComponent;float maximum=Mathf.Max(1,health.fullCombinedHealth);
  currentHealth.text=Mathf.CeilToInt(Mathf.Max(0,health.combinedHealth)).ToString();fullHealth.text=Mathf.CeilToInt(health.fullCombinedHealth).ToString();
  Fill(healthFill,0,health.health/maximum);Fill(shieldFill,health.health/maximum,health.shield/maximum);Fill(barrierFill,0,health.barrier/maximum);
  level.text=Mathf.FloorToInt(body.level).ToString();money.text=body.master.money.ToString();
  float xp=0;if(TeamManager.instance){var team=body.master.teamIndex;double lo=TeamManager.instance.GetTeamCurrentLevelExperience(team),hi=TeamManager.instance.GetTeamNextLevelExperience(team);if(hi>lo)xp=(float)((TeamManager.instance.GetTeamExperience(team)-lo)/(hi-lo));}
  experienceFill.anchorMax=new Vector2(Mathf.Clamp01(xp),1);
  float seconds=Run.instance?Run.instance.GetRunStopwatch():0;if(timerFormatter)timerFormatter.seconds=seconds;else timer.text=((int)seconds/60).ToString("00")+":"+((int)seconds%60).ToString("00");
  if(Run.instance&&stageCount&&ambientLevel){stageCount.text=string.Format(Label("STAGE_COUNT_FORMAT"),Run.instance.stageClearCount+1);ambientLevel.text=string.Format(Label("AMBIENT_LEVEL_DISPLAY_FORMAT"),Run.instance.ambientLevelFloor);}
  if(Run.instance&&difficulty&&difficultySegments!=null&&difficultySegments.Length>0){int tier=Mathf.Clamp(Mathf.FloorToInt((Run.instance.ambientLevel-1)/Mathf.Max(.001f,levelsPerSegment)),0,difficultySegments.Length-1);difficulty.text=Label(difficultySegments[tier].token);difficultyBackground.color=difficultySegments[tier].color;}
  string scene=run.stageProgress!=null?run.stageProgress.current:"golemplains";var def=SceneCatalog.GetSceneDefFromSceneName(scene);stage.text=def?Label(def.nameToken):scene;
  string task=run.world==null?"":run.world.objective;
  if(run.objective!=null&&run.objective.ready){task=run.objective.charging?"Charge the teleporter: "+Mathf.FloorToInt(run.objective.charge*100)+"%":run.objective.charged?"Use the teleporter":run.objective.bossSpawns>0&&!run.objective.bossDefeated?"Defeat the teleporter boss":"Find and activate the teleporter";}
  if(run.world!=null&&!string.IsNullOrEmpty(run.world.target))task+="\nB: "+run.world.target;
  objective.text=task;
  objectiveLayout.preferredHeight=Mathf.Max(objectiveLayout.minHeight,objective.GetPreferredValues(task,Mathf.Max(1,objective.rectTransform.rect.width),Mathf.Infinity).y+8);
  var slots=new[]{body.skillLocator.primary,body.skillLocator.secondary,body.skillLocator.utility,body.skillLocator.special};
  float spread=Mathf.Clamp01(body.spreadBloomAngle/Mathf.Max(.001f,spreadAngle));foreach(var part in spreadPositions)part.target.localPosition=Vector3.Lerp(part.zeroPosition,part.onePosition,spread);foreach(var image in spreadImages)image.color=new Color(1,1,1,Mathf.Lerp(minSpreadAlpha,maxSpreadAlpha,spread));
  for(int i=0;i<skills.Length;i++){var slot=slots[i];var view=skills[i];view.icon.sprite=slot?slot.icon:null;view.icon.enabled=slot&&slot.icon;view.cooldown.text=slot&&slot.stock==0?Mathf.CeilToInt(slot.cooldownRemaining).ToString():"";view.stock.text=slot&&slot.maxStock>1?slot.stock.ToString():"";if(view.ready)view.ready.SetActive(slot&&slot.IsReady());}
  var seen=new HashSet<ItemIndex>();
  foreach(var index in body.inventory.itemAcquisitionOrder){int count=body.inventory.GetItemCount(index);if(count<=0)continue;seen.Add(index);RecoveredHudPresentation icon;if(!itemViews.TryGetValue(index,out icon)){icon=Instantiate(itemTemplate,inventoryRoot,false);icon.name="Owned item icon "+index;icon.gameObject.SetActive(true);itemViews.Add(index,icon);}var item=ItemCatalog.GetItemDef(index);icon.itemImage.texture=item?item.pickupIconTexture:null;icon.itemCount.gameObject.SetActive(count>1);icon.itemCount.text=count>1?"x"+count:"";}
  foreach(var pair in itemViews)pair.Value.gameObject.SetActive(seen.Contains(pair.Key));
  bool boss=run.objective!=null&&run.objective.bossMaxHealth>0&&!run.objective.bossDefeated;bossContainer.SetActive(boss);
  if(boss){float ratio=run.objective.bossHealth/Mathf.Max(1,run.objective.bossMaxHealth);Fill(bossFill,0,ratio);bossHealth.text=Mathf.CeilToInt(run.objective.bossHealth)+" / "+Mathf.CeilToInt(run.objective.bossMaxHealth);var group=TeleporterInteraction.instance?TeleporterInteraction.instance.bossGroup:null;bossName.text=group&&!string.IsNullOrEmpty(group.bestObservedName)?group.bestObservedName:"Teleporter boss";}
  PresentFeedback(body,report);
  report.ready=true;report.frames++;report.items=seen.Count;report.skillSlots=skills.Length;report.health=health.health;report.shield=health.shield;report.barrier=health.barrier;report.level=body.level;report.money=body.master.money;report.stage=scene;report.objective=task;report.bossHealth=run.objective==null?0:run.objective.bossHealth;report.charge=run.objective==null?0:run.objective.charge;
 }
 static void Fill(Image image,float start,float amount){image.gameObject.SetActive(amount>0);var rect=image.rectTransform;rect.anchorMin=new Vector2(Mathf.Clamp01(start),0);rect.anchorMax=new Vector2(Mathf.Clamp01(start+amount),1);rect.offsetMin=rect.offsetMax=Vector2.zero;}
}
