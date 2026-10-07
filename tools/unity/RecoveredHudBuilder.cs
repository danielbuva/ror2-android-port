#if UNITY_EDITOR
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using Newtonsoft.Json.Linq;
using RoR2.UI;
using TMPro;
using UnityEditor;
using UnityEngine;
using UnityEngine.UI;

// Generate only ignored presentation variants. Original exports are read-only.
public static class RecoveredHudBuilder {
 const string Output="Assets/LabLoadingScene/Resources/RecoveredUI";
 static readonly Dictionary<Material,Material> fontMaterials=new Dictionary<Material,Material>();
 static TMP_FontAsset defaultFont;static Shader fontShader;
 static void StageStrings(string attemptDirectory){
  var work=Path.GetFullPath(Path.Combine(Application.dataPath,"../.."));var config=JObject.Parse(File.ReadAllText(Path.Combine(work,"config/local.json")));
  var directory=Path.Combine((string)config["game_path"],"Risk of Rain 2_Data/StreamingAssets/Language/en");var values=new SortedDictionary<string,string>();var sources=new List<object>();
  foreach(var file in Directory.GetFiles(directory,"*.json").OrderBy(x=>x)){
   var bytes=File.ReadAllBytes(file);var data=JObject.Parse(File.ReadAllText(file));var tokens=data["strings"] as JObject;if(tokens==null)continue;
   foreach(var row in tokens.Properties())if(row.Value.Type==JTokenType.String)values[row.Name]=(string)row.Value;
   using(var hash=System.Security.Cryptography.SHA256.Create())sources.Add(new {file=Path.GetFileName(file),sha256=BitConverter.ToString(hash.ComputeHash(bytes)).Replace("-","").ToLowerInvariant()});
  }
  Require(values.ContainsKey("TITLE_SINGLEPLAYER")&&values.ContainsKey("SUBMENU_QUIT"),"Original English menu tokens absent");
  var table=new RecoveredHudPresentation.Strings{entries=values.Select(x=>new RecoveredHudPresentation.Entry{key=x.Key,value=x.Value}).ToArray()};
  File.WriteAllText(Output+"/Strings.json",JsonUtility.ToJson(table));AssetDatabase.ImportAsset(Output+"/Strings.json",ImportAssetOptions.ForceSynchronousImport);
  File.WriteAllText(Path.Combine(attemptDirectory,"ui-language-provenance.json"),Newtonsoft.Json.JsonConvert.SerializeObject(new {entries=values.Count,sources=sources,scope="Original English strings for owned presentation only; no stock Language/platform startup"},Newtonsoft.Json.Formatting.Indented));
 }
 static void Require(bool condition,string message){if(!condition)throw new InvalidOperationException(message);}
 static Transform Named(GameObject root,string name){return root.GetComponentsInChildren<Transform>(true).FirstOrDefault(t=>t.name==name);}
 static void Hide(GameObject root,params string[] names){foreach(var t in root.GetComponentsInChildren<Transform>(true))if(names.Contains(t.name))t.gameObject.SetActive(false);}
 static TMP_Text Text(Transform parent,string name){var text=parent.GetComponentsInChildren<TMP_Text>(true).FirstOrDefault(t=>t.name==name);Require(text,"Source text missing: "+name);return text;}
 static TMP_Text NewText(Transform parent,TMP_Text source,string name){var text=UnityEngine.Object.Instantiate(source,parent,false);text.name=name;var rect=text.rectTransform;rect.anchorMin=Vector2.zero;rect.anchorMax=Vector2.one;rect.offsetMin=rect.offsetMax=Vector2.zero;return text;}
 static void Normalize(GameObject root){
  Require(root.GetComponentsInChildren<Component>(true).All(x=>x),"Missing source UI script/reference: "+root.name);
  foreach(var controller in root.GetComponentsInChildren<LanguageTextMeshController>(true)){var text=controller.GetComponent<TMP_Text>();if(!text)text=controller.GetComponentInChildren<TMP_Text>(true);if(text)text.text=RecoveredHudPresentation.Label(controller.token);}
  foreach(var text in root.GetComponentsInChildren<TMP_Text>(true)){
   // These stock glyph tags synchronously request platform sprite catalogs.
   // Current owned bindings use explicit measured button labels instead.
   if(text.text.Contains("<sprite"))text.gameObject.SetActive(false);
   if(!text.font)text.font=defaultFont;
   var hg=text as HGTextMeshProUGUI;if(hg)hg.useLanguageDefaultFont=false;
   var source=text.fontSharedMaterial?text.fontSharedMaterial:text.font.material;Material material;
   if(!fontMaterials.TryGetValue(source,out material)){material=new Material(source);material.name="Owned mobile font "+source.name;material.shader=fontShader;AssetDatabase.CreateAsset(material,Output+"/FontMaterial"+fontMaterials.Count+".mat");fontMaterials.Add(source,material);}
   text.fontSharedMaterial=material;text.raycastTarget=false;
  }
  foreach(var group in root.GetComponentsInChildren<CanvasGroup>(true))group.alpha=1;
  foreach(var canvas in root.GetComponentsInChildren<Canvas>(true))if(canvas.transform==root.transform){canvas.renderMode=RenderMode.ScreenSpaceOverlay;canvas.worldCamera=null;canvas.sortingOrder=50;}
  foreach(var graphic in root.GetComponentsInChildren<Graphic>(true))if(!(graphic is TMP_Text)&&!(graphic is TMP_SubMeshUI))graphic.material=Graphic.defaultGraphicMaterial;
  var remove=root.GetComponentsInChildren<MonoBehaviour>(true).Where(component=>!(component is TMP_Text)&&!(component is TimerText)&&!(component is BuffIcon)&&!(component is GenericNotification)&&!(component is RecoveredPickupPresentation)&&!(component is RecoveredHudPresentation)&&component.GetType().Namespace!="UnityEngine.UI").ToList();
  while(remove.Count>0){
   var leaf=remove.FirstOrDefault(candidate=>!remove.Any(other=>other!=candidate&&other.gameObject==candidate.gameObject&&other.GetType().GetCustomAttributes(typeof(RequireComponent),true).Cast<RequireComponent>().Any(r=>new[]{r.m_Type0,r.m_Type1,r.m_Type2}.Any(t=>t!=null&&t.IsAssignableFrom(candidate.GetType())))));
   Require(leaf,"Generated UI component dependency cycle");remove.Remove(leaf);UnityEngine.Object.DestroyImmediate(leaf);
  }
  foreach(var component in root.GetComponentsInChildren<Animator>(true))UnityEngine.Object.DestroyImmediate(component);
  foreach(var component in root.GetComponentsInChildren<Rigidbody>(true))UnityEngine.Object.DestroyImmediate(component);
 }
 static Image Bar(HealthBar source,HealthBarStyle.BarStyle style,string name){
  var obj=UnityEngine.Object.Instantiate(source.style.barPrefab,source.barContainer,false);obj.name=name;var image=obj.GetComponent<Image>();Require(image,"Source health subbar image absent");image.sprite=style.sprite;image.color=style.baseColor;image.type=style.imageType;image.raycastTarget=false;return image;
 }
 static void Save(GameObject root,string name){
  Require(root.GetComponentsInChildren<Component>(true).All(x=>x),"Generated UI missing scripts");
  root.GetComponent<RecoveredHudPresentation>().Validate();root.SetActive(false);PrefabUtility.SaveAsPrefabAsset(root,Output+"/"+name+".prefab");UnityEngine.Object.DestroyImmediate(root);
 }
 public static string Generate(string attemptDirectory){
  Require(!EditorApplication.isCompiling&&!BuildPipeline.isBuildingPlayer&&!EditorApplication.isPlaying,"UI generation requires idle editor");
  var roots=JObject.Parse(File.ReadAllText(Path.Combine(attemptDirectory,"hud-source-roots.json")));Directory.CreateDirectory(Output);
  Require(!File.Exists(Output+"/Hud.prefab"),"Archive existing UI generation before regenerating");
  StageStrings(attemptDirectory);fontMaterials.Clear();fontShader=AssetDatabase.LoadAssetAtPath<Shader>(Output+"/FontShader/TMP_SDF-Mobile.shader");Require(fontShader&&!ShaderUtil.ShaderHasError(fontShader),"Native mobile font shader absent or failed");
  var source=AssetDatabase.LoadAssetAtPath<GameObject>((string)roots["hudSource"]);Require(source&&!source.activeSelf,"Inactive source HUD absent");
  defaultFont=source.GetComponentsInChildren<TMP_Text>(true).First(t=>t.font&&t.font.name.StartsWith("tmpRiskofRainFont")).font;
  // The stock text runtime needs settings before the offline menu, not platform startup.
  var settingsSource=AssetDatabase.LoadAssetAtPath<TMP_Settings>("Assets/LabLoadingScene/ObjectiveClosure/TextMesh Pro/FormerResources/TMP Settings.asset");Require(settingsSource,"Source TMP settings absent");
  var settings=UnityEngine.Object.Instantiate(settingsSource);AssetDatabase.CreateAsset(settings,"Assets/LabLoadingScene/Resources/TMP Settings.asset");
  var settingsFields=new SerializedObject(settings);settingsFields.FindProperty("m_defaultFontAsset").objectReferenceValue=defaultFont;settingsFields.ApplyModifiedPropertiesWithoutUndo();
  var settingsField=typeof(TMP_Settings).GetField("s_Instance",System.Reflection.BindingFlags.Static|System.Reflection.BindingFlags.NonPublic);var priorSettings=settingsField.GetValue(null);settingsField.SetValue(null,settings);
  try {
  var hud=UnityEngine.Object.Instantiate(source);hud.name="Owned recovered HUD";
  var native=hud.GetComponent<HUD>();var view=hud.AddComponent<RecoveredHudPresentation>();
  view.currentHealth=native.healthBar.currentHealthText;view.fullHealth=native.healthBar.fullHealthText;view.level=native.levelText.targetText;view.money=native.moneyText.targetText;view.experienceFill=native.expBar.fillRectTransform;
  view.healthFill=Bar(native.healthBar,native.healthBar.style.instantHealthBarStyle,"Owned health fill");view.shieldFill=Bar(native.healthBar,native.healthBar.style.shieldBarStyle,"Owned shield fill");view.barrierFill=Bar(native.healthBar,native.healthBar.style.barrierBarStyle,"Owned barrier fill");
  view.skills=native.skillIcons.Select(x=>new RecoveredHudPresentation.SkillView{icon=x.iconImage,cooldown=x.cooldownText,stock=x.stockText,key=Text(x.transform,"SkillKeyText"),ready=x.isReadyPanelObject}).ToArray();
  foreach(var skill in native.skillIcons){if(skill.cooldownRemapPanel)skill.cooldownRemapPanel.gameObject.SetActive(false);if(skill.flashPanelObject)skill.flashPanelObject.SetActive(false);Hide(skill.gameObject,"FlashPanel, Expanding");}
  foreach(var equipment in native.equipmentIcons)if(equipment)equipment.gameObject.SetActive(false);
  var spectator=hud.GetComponentInChildren<SpectatorLabel>(true);if(spectator)spectator.gameObject.SetActive(false);
  string[] keys={"X","Y","LB","RB"};for(int i=0;i<4;i++)view.skills[i].key.text=keys[i];
  var boss=hud.GetComponentInChildren<HUDBossHealthBarController>(true);Require(boss,"Source boss view absent");view.bossContainer=boss.container;view.bossFill=boss.fillRectImage;view.bossName=boss.bossNameLabel;view.bossHealth=boss.healthLabel;boss.bossSubtitleLabel.text="";
  view.inventoryRoot=(RectTransform)native.itemInventoryDisplay.transform;
  var icons=UnityEngine.Object.Instantiate(AssetDatabase.LoadAssetAtPath<GameObject>((string)roots["itemIconSource"]),hud.transform,false);icons.name="Owned inactive item template";var item=icons.GetComponent<ItemIcon>();Require(item&&item.image&&item.stackText,"Source item icon bindings absent");var template=icons.AddComponent<RecoveredHudPresentation>();template.itemImage=item.image;template.itemCount=item.stackText;view.itemTemplate=template;icons.SetActive(false);if(item.glowImage)item.glowImage.gameObject.SetActive(false);if(item.durationImage)item.durationImage.gameObject.SetActive(false);
  Hide(icons,"Managed_Sprite_ItemCounter","Timer");template.itemCount.gameObject.SetActive(true);template.itemCount.text="";
  var grid=view.inventoryRoot.gameObject.AddComponent<GridLayoutGroup>();grid.cellSize=((RectTransform)icons.transform).sizeDelta;grid.cellSize=new Vector2(Mathf.Max(48,grid.cellSize.x),Mathf.Max(48,grid.cellSize.y));grid.spacing=Vector2.zero;grid.constraint=GridLayoutGroup.Constraint.FixedColumnCount;grid.constraintCount=12;
  var buffs=hud.GetComponentInChildren<BuffDisplay>(true);Require(buffs&&buffs.buffIconPrefab,"Source buff presentation absent");view.buffRoot=(RectTransform)buffs.transform;view.buffWidth=buffs.iconWidth;
  var buffObject=UnityEngine.Object.Instantiate(buffs.buffIconPrefab,hud.transform,false);buffObject.name="Owned inactive buff template";buffObject.SetActive(false);view.buffTemplate=buffObject.GetComponent<BuffIcon>();
  var notices=hud.GetComponentInChildren<NotificationUIController>(true);Require(notices,"Source notification controller absent");view.notificationRoot=(RectTransform)notices.transform;
  var noticeField=typeof(NotificationUIController).GetField("genericNotificationPrefab",System.Reflection.BindingFlags.Instance|System.Reflection.BindingFlags.NonPublic);
  var noticeSource=(GameObject)noticeField.GetValue(notices);Require(noticeSource,"Original generic notification prefab absent");
  var noticeObject=UnityEngine.Object.Instantiate(noticeSource,hud.transform,false);noticeObject.name="Owned inactive pickup template";noticeObject.SetActive(false);
  var notice=noticeObject.GetComponent<GenericNotification>();view.notificationTemplate=noticeObject.AddComponent<RecoveredPickupPresentation>();view.notificationTemplate.nativeFade=notice;view.notificationTemplate.title=notice.titleTMP;view.notificationTemplate.description=notice.descriptionText.GetComponent<TMP_Text>();
  if(notice.previousIconImage)notice.previousIconImage.gameObject.SetActive(false);if(notice.extraPanel)notice.extraPanel.gameObject.SetActive(false);if(notice.tempPanel)notice.tempPanel.gameObject.SetActive(false);
  view.stage=Text(Named(hud,"MapNameCluster"),"MainText");Text(view.stage.transform.parent,"Subtext").text="";
  var info=UnityEngine.Object.Instantiate(AssetDatabase.LoadAssetAtPath<GameObject>((string)roots["runInfoSource"]),Named(hud,"UpperRightCluster"),false);info.SetActive(true);
  view.timer=Text(Named(info,"TimerPanel"),"TimerText");view.timerFormatter=view.timer.GetComponent<TimerText>();Require(view.timerFormatter&&view.timerFormatter.format,"Original timer formatter absent");
  view.stageCount=Text(Named(info,"StageCountRoot"),"Stage Text");view.ambientLevel=Text(Named(info,"AmbientLevelRoot"),"Level Text");
  var difficulty=info.GetComponentInChildren<DifficultyBarController>(true);Require(difficulty&&difficulty.segmentDefs.Length>0,"Source difficulty style absent");view.difficultySegments=difficulty.segmentDefs;view.levelsPerSegment=difficulty.levelsPerSegment;
  // Keep a truthful current-tier label over source artwork. Scrolling, animated
  // gear/flash and stock profile-dependent difficulty presentation remain open.
  view.difficulty=NewText(difficulty.transform,view.stageCount,"Owned difficulty tier");view.difficulty.alignment=TextAlignmentOptions.Center;view.difficultyBackground=difficulty.difficultyBarBackdrop;
  difficulty.segmentContainer.gameObject.SetActive(false);foreach(var gear in difficulty.wormGearImages)gear.gameObject.SetActive(false);
  Hide(info,"Managed_Sprite_Timer","DifficultyIcon","ArtifactPanel","DifficultyTutorial");
  var objectiveStrip=Named(info,"ObjectiveStrip");Require(objectiveStrip,"Source objective strip absent");objectiveStrip.gameObject.SetActive(true);view.objective=Text(objectiveStrip,"Label");view.objectiveLayout=objectiveStrip.GetComponent<LayoutElement>();view.objective.gameObject.SetActive(true);view.objective.color=Color.white;objectiveStrip.localScale=Vector3.one;
  Hide(hud,"SteamBuildLabel","DebugStats","TutorialObjectiveText","ScoreboardPanel","InspectPanelArea","CinematicUI","VoiceChatNotifications","VoiceChatNotificationManager","ChatBoxRoot","CharacterStats","LunarCoinRoot","VoidCoinRoot","SharedSufferingRoot","Managed_Sprite_HP","RemoteOp","MovePanel","AimPanel","AimPanel (1)","AimPanel (2)","AimPanel (3)","EquipmentRoot","EquipmentCluster","SprintCluster","Hitmarker","CrosshairExtras");
  view.buffRoot.gameObject.SetActive(true);view.notificationRoot.gameObject.SetActive(true);
  foreach(var t in hud.GetComponentsInChildren<Transform>(true))if(t.name.StartsWith("TUTORIAL:"))t.gameObject.SetActive(false);
  native.mainContainer.SetActive(true);native.mainUIPanel.SetActive(true);view.currentHealth.transform.parent.gameObject.SetActive(true);view.currentHealth.gameObject.SetActive(true);view.fullHealth.gameObject.SetActive(true);
  var crosshair=UnityEngine.Object.Instantiate(AssetDatabase.LoadAssetAtPath<GameObject>((string)roots["crosshairSource"]),Named(hud,"CrosshairCanvas"),false);crosshair.SetActive(true);
  var crosshairSource=crosshair.GetComponent<CrosshairController>();Require(crosshairSource,"Source crosshair layout controller absent");view.spreadPositions=crosshairSource.spriteSpreadPositions;view.spreadImages=crosshairSource.remapSprites;view.spreadAngle=crosshairSource.maxSpreadAngle;view.minSpreadAlpha=crosshairSource.minSpreadAlpha;view.maxSpreadAlpha=crosshairSource.maxSpreadAlpha;
  var spriteRows=JArray.Parse(File.ReadAllText(Path.Combine(attemptDirectory,"native-crosshair-sprites.json")));var sprites=new Dictionary<string,Sprite>();
  foreach(var image in crosshair.GetComponentsInChildren<Image>(true)){var original=image.sprite;Require(original,"Original crosshair sprite absent");Sprite sprite;if(!sprites.TryGetValue(original.name,out sprite)){var row=spriteRows.Single(x=>(string)x["m_Name"]==original.name);var rect=row["m_Rect"];var bounds=new Rect((float)rect["x"],(float)rect["y"],(float)rect["width"],(float)rect["height"]);Require(bounds.xMin>=0&&bounds.yMin>=0&&bounds.xMax<=original.texture.width&&bounds.yMax<=original.texture.height,"Measured original crosshair rectangle exceeds texture");sprite=Sprite.Create(original.texture,bounds,original.pivot/original.rect.size,(float)row["m_PixelsToUnits"],0,SpriteMeshType.FullRect,original.border);sprite.name="Owned full-rectangle "+original.name;AssetDatabase.CreateAsset(sprite,Output+"/"+sprite.name+".asset");sprites.Add(original.name,sprite);}image.sprite=sprite;}
  foreach(var part in view.spreadPositions)part.target.localPosition=part.zeroPosition;foreach(var image in view.spreadImages)image.color=new Color(1,1,1,view.minSpreadAlpha);
  Normalize(hud);Save(hud,"Hud");
  var menu=UnityEngine.Object.Instantiate(AssetDatabase.LoadAssetAtPath<GameObject>((string)roots["menuSource"]));Require(!menu.activeSelf,"Source menu must be inactive");menu.name="Owned recovered offline menu";var menuView=menu.AddComponent<RecoveredHudPresentation>();menuView.isMenu=true;
  GameObject startObject=null,quitObject=null;Graphic startGraphic=null,quitGraphic=null;ColorBlock startColors=ColorBlock.defaultColorBlock,quitColors=startColors;
  foreach(var button in menu.GetComponentsInChildren<HGButton>(true)){
   bool start=button.name=="GenericMenuButton (Singleplayer)",quit=button.name=="GenericMenuButton (Quit)";
   if(!start&&!quit){button.gameObject.SetActive(false);continue;}
   if(start){startObject=button.gameObject;startGraphic=button.targetGraphic;startColors=button.colors;}else{quitObject=button.gameObject;quitGraphic=button.targetGraphic;quitColors=button.colors;}
  }
  Hide(menu,"FadePanel","MiscOptionsPanel","MiscInfo","SteamBuildLabel (1)","TextPanel","PatchNotesPanel","PublicTestPanel","GenericGlyphAndDescription","GenericGlyphAndDescription (3)");var panel=Named(menu,"ButtonPanel (JUICED)");Require(panel,"Source menu panel absent");panel.gameObject.SetActive(true);
  Normalize(menu);Require(startObject&&quitObject,"Source menu actions absent");menuView.startButton=startObject.AddComponent<Button>();menuView.startButton.targetGraphic=startGraphic;menuView.startButton.colors=startColors;menuView.quitButton=quitObject.AddComponent<Button>();menuView.quitButton.targetGraphic=quitGraphic;menuView.quitButton.colors=quitColors;
  Text(startObject.transform,"ButtonText").text=RecoveredHudPresentation.Label("TITLE_SINGLEPLAYER")+" (A)";Text(quitObject.transform,"ButtonText").text=RecoveredHudPresentation.Label("SUBMENU_QUIT");Save(menu,"Menu");AssetDatabase.SaveAssets();
  var generated=AssetDatabase.LoadAssetAtPath<GameObject>(Output+"/Hud.prefab");return "Generated inactive source HUD/menu variants; "+generated.GetComponentsInChildren<Component>(true).Length+" HUD components, "+fontMaterials.Count+" owned font materials";
  } finally {settingsField.SetValue(null,priorSettings);}
 }
}
#endif
