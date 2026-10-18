// Subsystem: catalog/resources (game path). Owner map: docs/ARCHITECTURE.md#ownership.
// Session phases: setup RegisterBodyCatalog, RegisterOriginalSkins (BodyCatalogSession); teardown CleanupBodyCatalog coordinates CleanupOriginalSkins, CleanupLoadoutTables (Dispose), template/catalog and composed release.
using System;
using System.Collections;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Collections.Generic;
using RoR2.Skills;
using Path = System.IO.Path;
using RoR2;
using UnityEngine;
using UnityEngine.AddressableAssets;
using UnityEngine.AddressableAssets.Initialization;
using UnityEngine.AddressableAssets.ResourceLocators;
using UnityEngine.AddressableAssets.ResourceProviders;
using UnityEngine.ResourceManagement.AsyncOperations;
using UnityEngine.ResourceManagement.ResourceLocations;

public sealed partial class PortSession {
 bool ownsBodyAvailability;
 ResourceAvailability priorBodyAvailability;
 readonly Dictionary<int,GameObject> priorCatalogBodyTemplates=new Dictionary<int,GameObject>();
 void CleanupBodyCatalog(){
  Check(LegacyResourcesAPI.ActiveCount==0,"Refuse teardown with pending portrait callbacks");
  CleanupOriginalSkins();
  CleanupLoadoutTables();
  RestoreCatalogBodyTemplates();
  if(ownsBodyAvailability){BodyCatalog.availability=priorBodyAvailability;ownsBodyAvailability=false;}
  if(ownsBodyCatalog){StaticCall(typeof(BodyCatalog),"SetBodyPrefabs",(object)new GameObject[0]);Check(BodyCatalog.bodyCount==0,"Owned catalog reset failed");ownsBodyCatalog=false;}
  if(artifactBundle){artifactBundle.Unload(true);artifactBundle=null;}
  ReleaseObjectiveBundlePreload();CleanupRecoveredText();
  if(Resources.Load<TextAsset>("WholeCatalogBootstrap"))WholeCatalogComposed.Release();
  RestoreBodySettingsTransform();if(r.liveCatalogs!=null){r.liveCatalogs.bodySkillCleanup=BodyCatalog.bodyCount==0&&SkillCatalog.skillCount==0&&SkillCatalog.skillFamilyCount==0;}
 }
 BodyCatalogSession bodyCatalogSession;
 BodyCatalogSession GetBodyCatalogSession(){if(bodyCatalogSession==null)bodyCatalogSession=new BodyCatalogSession(this);return bodyCatalogSession;}
 static FieldInfo SkinField(string name){return BodyCatalogSession.SkinField(name);}
 IEnumerator RegisterOriginalSkins(){return GetBodyCatalogSession().RegisterOriginalSkins();}
 void CleanupOriginalSkins(){GetBodyCatalogSession().CleanupOriginalSkins();}
 static Func<IResourceLocation,string> CreateBodySettingsTransform(string original,string local){return BodyCatalogSession.CreateBodySettingsTransform(original,local);}
 static FieldInfo LoadoutField(string name){return BodyCatalogSession.LoadoutField(name);}
 static FieldInfo ViewableField(string name){return BodyCatalogSession.ViewableField(name);}
 void PrepareLoadoutTables(GameObject prefab){GetBodyCatalogSession().PrepareLoadoutTables(prefab);}
 void CleanupLoadoutTables(){GetBodyCatalogSession().Dispose();}
 IEnumerator RegisterBodyCatalog()=>GetBodyCatalogSession().RegisterBodyCatalog();
 void AdaptComposedEffectAudio(EffectDef definition){GetBodyCatalogSession().AdaptComposedEffectAudio(definition);}
 void SetCatalogBodyTemplate(int index,GameObject template){GetBodyCatalogSession().SetCatalogBodyTemplate(index,template);}
 void BindCatalogBodyTemplate(GameObject template){GetBodyCatalogSession().BindCatalogBodyTemplate(template);}
 void RestoreCatalogBodyTemplates(){GetBodyCatalogSession().RestoreCatalogBodyTemplates();}
 void InitializeComposedEffects(System.Collections.Generic.IEnumerable<EffectDef> definitions){GetBodyCatalogSession().InitializeComposedEffects(definitions);}
 void RegisterComposedEffects(System.Collections.Generic.IEnumerable<EffectDef> definitions){GetBodyCatalogSession().RegisterComposedEffects(definitions);}
 void RestoreComposedEffects(EffectDef[] previous){GetBodyCatalogSession().RestoreComposedEffects(previous);}
 BuffDef[] UpdatedComparisonBuffs(SessionConfig cfg){return GetBodyCatalogSession().UpdatedComparisonBuffs(cfg);}
 ItemDef[] UpdatedComparisonItems(SessionConfig cfg){return GetBodyCatalogSession().UpdatedComparisonItems(cfg);}
 void RestoreBodySettingsTransform(){GetBodyCatalogSession().RestoreBodySettingsTransform();}

 // Retain this owner after cleanup. The coordinator preserves the catalog and
 // composed-hook order; Dispose releases loadout tables at their existing step.
 sealed class BodyCatalogSession : IDisposable {
  readonly PortSession coordinator;
  public BodyCatalogSession(PortSession coordinator){this.coordinator=coordinator;}
  bool ownsLoadoutTables,ownsSkillCatalog;
  bool ownsSkinCatalog;
  ResourceAvailability priorSkinAvailability;
  SkinDef[] priorSkinDefs;
  SkinDef[][] priorSkinsByBody;
  readonly Dictionary<SkinDef,SkinIndex> priorSkinIndices=new Dictionary<SkinDef,SkinIndex>();
  readonly Dictionary<string,SkinIndex> priorSkinNames=new Dictionary<string,SkinIndex>();
  public static FieldInfo SkinField(string name){return typeof(SkinCatalog).GetField(name,BindingFlags.NonPublic|BindingFlags.Static);}
  public IEnumerator RegisterOriginalSkins(){
   coordinator.Check(coordinator.r.liveCatalogs!=null&&BodyCatalog.availability.available&&ProjectileCatalog.catalogAvailability.available&&SkinCatalog.skinCount==0&&!ownsSkinCatalog,"Original skin catalog dependencies or ownership missing");
   priorSkinDefs=(SkinDef[])SkinField("allSkinDefs").GetValue(null);priorSkinsByBody=(SkinDef[][])SkinField("skinsByBody").GetValue(null);priorSkinAvailability=SkinCatalog.availability;
   var names=(Dictionary<string,SkinIndex>)SkinField("skinNameToIndex").GetValue(null);
   coordinator.Check(priorSkinDefs.Length==0&&priorSkinsByBody.Length==0&&names.Count==0&&!priorSkinAvailability.available,"Unowned original skin catalog state");
   foreach(var prefab in BodyCatalog.allBodyPrefabs){var locator=prefab.GetComponent<ModelLocator>();if(!locator||!locator.modelTransform)continue;var controller=locator.modelTransform.GetComponent<ModelSkinController>();if(!controller)continue;foreach(var skin in controller.skins)if(skin&&!priorSkinIndices.ContainsKey(skin))priorSkinIndices.Add(skin,skin.skinIndex);}
   foreach(var pair in names)priorSkinNames.Add(pair.Key,pair.Value);
   ownsSkinCatalog=true;coordinator.r.phase="original-skin-catalog-register";coordinator.Save();
   var method=typeof(SkinCatalog).GetMethod("Init",BindingFlags.NonPublic|BindingFlags.Static);
   coordinator.Check(method!=null,"Original skin initializer missing");
   var routine=(IEnumerator)method.Invoke(null,null);var deadline=Time.realtimeSinceStartup+180f;
   while(routine.MoveNext()){coordinator.Check(Time.realtimeSinceStartup<deadline,"Original skin catalog initialization timed out");yield return routine.Current;}
   coordinator.Check(SkinCatalog.availability.available&&SkinCatalog.skinCount==priorSkinIndices.Count&&priorSkinIndices.Keys.All(skin=>skin.runtimeSkin!=null&&SkinCatalog.GetSkinDef(skin.skinIndex)==skin),"Original skin baking or index identity differs");
   var commando=BodyCatalog.FindBodyIndex("CommandoBody");coordinator.Check(SkinCatalog.GetBodySkinCount(commando)>0&&SkinCatalog.GetBodySkinDef(commando,0),"Original Commando default skin missing");
  }
  public void CleanupOriginalSkins(){
   if(!ownsSkinCatalog)return;
   foreach(var pair in priorSkinIndices)if(pair.Key)pair.Key.skinIndex=pair.Value;
   SkinField("allSkinDefs").SetValue(null,priorSkinDefs);SkinField("skinsByBody").SetValue(null,priorSkinsByBody);
   var names=(Dictionary<string,SkinIndex>)SkinField("skinNameToIndex").GetValue(null);names.Clear();foreach(var pair in priorSkinNames)names.Add(pair.Key,pair.Value);
   SkinCatalog.availability=priorSkinAvailability;ownsSkinCatalog=false;priorSkinIndices.Clear();priorSkinNames.Clear();
   coordinator.Check(SkinCatalog.skinCount==0,"Original skin catalog outlived its owned body bundle");
  }
  bool ownsBodySettingsTransform;
  Func<IResourceLocation,string> priorBodySettingsTransform,ownedBodySettingsTransform;
  // A separate closure owns only path strings, never this session or its report.
  public static Func<IResourceLocation,string> CreateBodySettingsTransform(string original,string local){return loc=>loc.InternalId==original?local:loc.InternalId;}
  object priorLoadoutDefaults,priorBodyInfos;
  readonly Dictionary<object,object> priorViewables=new Dictionary<object,object>();
  readonly HashSet<ViewablesCatalog.Node> priorViewableChildren=new HashSet<ViewablesCatalog.Node>();
  public static FieldInfo LoadoutField(string name){return typeof(Loadout.BodyLoadoutManager).GetField(name,BindingFlags.NonPublic|BindingFlags.Static);}
  public static FieldInfo ViewableField(string name){return typeof(ViewablesCatalog).GetField(name,BindingFlags.NonPublic|BindingFlags.Static);}
  public void PrepareLoadoutTables(GameObject prefab){
   coordinator.Check(!SkillCatalog.allSkillDefs.Any()&&!SkillCatalog.allSkillFamilies.Any(),"Existing skill catalog ownership");
   priorLoadoutDefaults=LoadoutField("defaultBodyLoadouts").GetValue(null);priorBodyInfos=LoadoutField("allBodyInfos").GetValue(null);
   coordinator.Check(priorLoadoutDefaults==null&&priorBodyInfos==null,"Existing loadout defaults ownership");
   var slots=prefab.GetComponents<GenericSkill>();coordinator.Check(slots.Length==4,"Original Commando skill-slot count");
   bool complete=coordinator.r.liveCatalogs!=null;
   var selectedFamilies=BodyCatalog.allBodyPrefabs.SelectMany(x=>x.GetComponents<GenericSkill>()).Select(x=>x.skillFamily).Where(x=>x).Distinct().ToArray();
   var families=complete?WholeCatalogComposed.CategoryFamily(RoR2.ContentManagement.AddressablesLabels.skillFamily,selectedFamilies):selectedFamilies;
   coordinator.Check(families.Length>=4&&families.All(x=>x&&x.variants.Length>0&&x.defaultVariantIndex<x.variants.Length),"Actual family/default-variant contract");
   // A source Copycat family has an empty variant. Register it unchanged; never invent a SkillDef.
   var selectedDefs=families.SelectMany(x=>x.variants.Select(v=>v.skillDef)).Where(x=>x).Distinct().ToArray();
   var defs=complete?WholeCatalogComposed.CategoryFamily(RoR2.ContentManagement.AddressablesLabels.skillDef,selectedDefs):selectedDefs;
   if(complete){coordinator.r.liveCatalogs.skills=defs.Length;coordinator.r.liveCatalogs.skillFamilies=families.Length;coordinator.r.liveCatalogs.emptySkillVariants=families.Sum(family=>family.variants.Count(variant=>!variant.skillDef));}
   ownsSkillCatalog=true;PortSession.StaticCall(typeof(SkillCatalog),"SetSkillDefs",(object)defs);PortSession.StaticCall(typeof(SkillCatalog),"SetSkillFamilies",(object)families);
   foreach(var family in families)coordinator.Check(SkillCatalog.GetSkillFamily(family.catalogIndex)==family,"Original family catalog identity");
   foreach(var def in defs)coordinator.Check(SkillCatalog.GetSkillDef(def.skillIndex)==def,"Original skill catalog identity");
   coordinator.Check(SurvivorCatalog.GetSurvivorIndexFromBodyIndex(prefab.GetComponent<CharacterBody>().bodyIndex)==SurvivorIndex.None,"Unexpected survivor-specific viewable context");
   var map=(IDictionary)ViewableField("fullNameToNodeMap").GetValue(null);foreach(DictionaryEntry entry in map)priorViewables.Add(entry.Key,entry.Value);
   var root=(ViewablesCatalog.Node)ViewableField("rootNode").GetValue(null);foreach(var child in root.children)priorViewableChildren.Add(child);
   ownsLoadoutTables=true;coordinator.r.phase="original-loadout-initialize";coordinator.Save();PortSession.StaticCall(typeof(Loadout.BodyLoadoutManager),"Init");
   var body=prefab.GetComponent<CharacterBody>();var defaults=(Array)LoadoutField("defaultBodyLoadouts").GetValue(null);
   coordinator.Check(defaults!=null&&defaults.Length==BodyCatalog.bodyCount,"Original default body loadout missing");var loadout=new Loadout();coordinator.Check(loadout.bodyLoadoutManager.GetSkinIndex(body.bodyIndex)==0,"Original default skin");
   for(int i=0;i<slots.Length;i++)coordinator.Check(loadout.bodyLoadoutManager.GetSkillVariant(body.bodyIndex,i)==slots[i].skillFamily.defaultVariantIndex,"Original default skill variant");
  }
  public void CleanupLoadoutTables(){
   if(ownsLoadoutTables){
    LoadoutField("defaultBodyLoadouts").SetValue(null,priorLoadoutDefaults);LoadoutField("allBodyInfos").SetValue(null,priorBodyInfos);
    var root=(ViewablesCatalog.Node)ViewableField("rootNode").GetValue(null);foreach(var child in root.children.ToArray())if(!priorViewableChildren.Contains(child))child.SetParent(null);
    var map=(IDictionary)ViewableField("fullNameToNodeMap").GetValue(null);map.Clear();foreach(var pair in priorViewables)map.Add(pair.Key,pair.Value);ownsLoadoutTables=false;
   }
   if(ownsSkillCatalog){PortSession.StaticCall(typeof(SkillCatalog),"SetSkillFamilies",(object)new SkillFamily[0]);PortSession.StaticCall(typeof(SkillCatalog),"SetSkillDefs",(object)new SkillDef[0]);ownsSkillCatalog=false;}
  }
  public IEnumerator RegisterBodyCatalog(){
   // Current original SpawnBody requires the game's PreSplash preset table.
   // This immutable application table is initialized once, not per session.
   if(BodyHandlingConfig.DefaultSettings==null){coordinator.r.phase="original-body-handling-presets";coordinator.Save();BodyHandlingConfig.Presets.InitializePresets();}
   coordinator.Check(BodyHandlingConfig.DefaultSettings!=null&&BodyHandlingConfig.DefaultSettings.currentPreset==BodyHandlingPresetIndex.Initial,"Original body-handling presets unavailable");
   if(Resources.Load<TextAsset>("WholeCatalogBootstrap")){var shared=WholeCatalogComposed.Prepare();while(shared.MoveNext())yield return shared.Current;}
   coordinator.Check(BodyCatalog.bodyCount==0&&LegacyResourcesAPI.ActiveCount==0,"Existing catalog/request ownership");
   coordinator.r.phase="body-catalog-initialize";coordinator.Save();
   var directory=Path.Combine(Application.persistentDataPath,"body-catalog-probe");Directory.CreateDirectory(directory);
   var catalog=Path.Combine(directory,"catalog.json");var settings=Path.Combine(directory,"settings.json");
   // Reuse the accepted controller probe's real, empty Addressables initialization.
   File.WriteAllText(catalog,"{\"m_LocatorId\":\"body-catalog-probe\",\"m_ProviderIds\":[],\"m_InternalIds\":[],\"m_KeyDataString\":\"AAAAAA==\",\"m_BucketDataString\":\"AAAAAA==\",\"m_EntryDataString\":\"AAAAAA==\",\"m_ExtraDataString\":\"\",\"m_resourceTypes\":[]}");
   var data=new ResourceManagerRuntimeData{BuildTarget="Android",DisableCatalogUpdateOnStartup=true,LogResourceManagerExceptions=true};
   data.CatalogLocations.Add(new ResourceLocationData(new[]{ResourceManagerRuntimeData.kCatalogAddress},catalog,typeof(ContentCatalogProvider),typeof(ContentCatalogData)));
   File.WriteAllText(settings,JsonUtility.ToJson(data));var originalSettings=Addressables.RuntimePath+"/settings.json";
   coordinator.Check(!ownsBodySettingsTransform,"Existing owned settings transform");
   priorBodySettingsTransform=Addressables.InternalIdTransformFunc;ownedBodySettingsTransform=CreateBodySettingsTransform(originalSettings,settings);
   Addressables.InternalIdTransformFunc=ownedBodySettingsTransform;ownsBodySettingsTransform=true;coordinator.r.catalogTransformInstalled=true;
   var init=Addressables.InitializeAsync();Addressables.ResourceManager.Acquire(init);
   var deadline=Time.realtimeSinceStartup+8;while(!init.IsDone&&Time.realtimeSinceStartup<deadline)yield return null;
   coordinator.Check(init.IsDone&&init.Status==AsyncOperationStatus.Succeeded,"Real Addressables initialization failed");Addressables.Release(init);
   string mapped;const string key="Textures/BodyIcons/CommandoBody";
   coordinator.Check(!LegacyResourcesAPI.GetGuid(key,out mapped),"Unexpected legacy portrait alias");
   var missing=LegacyResourcesAPI.LoadAsync<Texture2D>(key);deadline=Time.realtimeSinceStartup+3;
   while(!missing.IsDone&&Time.realtimeSinceStartup<deadline)yield return null;
   yield return null;
   coordinator.Check(missing.IsDone&&missing.Status==AsyncOperationStatus.Failed&&missing.Result==null,"Missing portrait did not fail honestly");
   coordinator.Check(missing.OperationException is InvalidKeyException,"Unexpected portrait failure class");Addressables.Release(missing);
   coordinator.Check(LegacyResourcesAPI.ActiveCount==0,"Missing request callback not drained");
   // MovementBatchProbe is the unchanged resource/file name.
   var cfg=JsonUtility.FromJson<SessionConfig>(Resources.Load<TextAsset>("MovementBatchProbe").text);
   coordinator.artifactBundle=AssetBundle.LoadFromFile(Path.Combine(Application.persistentDataPath,"payload","commando-prefab-lab"));coordinator.Check(coordinator.artifactBundle,"Body bundle missing");
   if(cfg.teleporterLoop){var preload=coordinator.PreloadObjectiveBundle();while(preload.MoveNext())yield return preload.Current;}
   var prefab=coordinator.artifactBundle.LoadAsset<GameObject>(cfg.bodyAsset);coordinator.Check(prefab&&!prefab.activeSelf&&prefab.name=="CommandoBody","Unexpected body prefab");
   var body=prefab.GetComponent<CharacterBody>();var portrait=body.portraitIcon;
   coordinator.Check(portrait&&portrait.name=="texCommandoIcon","Serialized portrait missing");
   coordinator.r.phase="original-body-catalog-register";coordinator.Save();
   var bodies=cfg.enemySpine?new[]{prefab,coordinator.artifactBundle.LoadAsset<GameObject>(cfg.enemyBodyAsset)}:new[]{prefab};if(cfg.teleporterLoop)bodies=bodies.Concat(cfg.objectiveActors.Select(x=>coordinator.artifactBundle.LoadAsset<GameObject>(x.body))).ToArray();
   if(cfg.integratedWorld&&Resources.Load<TextAsset>("WholeCatalogBootstrap")){
    bodies=WholeCatalogComposed.CategoryFamily(RoR2.ContentManagement.AddressablesLabels.characterBody,bodies.Distinct());
    coordinator.r.liveCatalogs=new LiveCatalogReport{bodies=bodies.Length};

   }
   coordinator.ownsBodyCatalog=true;PortSession.StaticCall(typeof(BodyCatalog),"SetBodyPrefabs",(object)bodies);
   deadline=Time.realtimeSinceStartup+3;while(LegacyResourcesAPI.ActiveCount!=0&&Time.realtimeSinceStartup<deadline)yield return null;
   yield return null;yield return null;
   coordinator.Check(LegacyResourcesAPI.ActiveCount==0,"Catalog portrait callback still pending");
   coordinator.Check(BodyCatalog.bodyCount==bodies.Length&&body.bodyIndex!=(BodyIndex)(-1),"Original index assignment failed");
   coordinator.Check(BodyCatalog.FindBodyIndex("CommandoBody")==body.bodyIndex&&BodyCatalog.FindBodyIndex("CommandoBody(Clone)")==body.bodyIndex,"Original name/index lookup failed");
   coordinator.Check(BodyCatalog.GetBodyPrefab(body.bodyIndex)==prefab,"Original prefab lookup failed");
   coordinator.Check(body.portraitIcon==portrait,"Missing-key callback replaced serialized portrait");
   coordinator.Check(!prefab.activeSelf,"Catalog registration activated gameplay");
   if(cfg.initializeLoadoutTables)PrepareLoadoutTables(prefab);
   if(Resources.Load<TextAsset>("WholeCatalogBootstrap")){
    WholeCatalogComposed.ConfigureLocations();
    coordinator.priorBodyAvailability=BodyCatalog.availability;coordinator.Check(!coordinator.priorBodyAvailability.available,"Unowned original body availability");
    BodyCatalog.availability.MakeAvailable();coordinator.ownsBodyAvailability=true;
   }
  }
  ResourceAvailability priorComposedEffectAvailability;
  readonly Dictionary<EffectDef,string> priorComposedEffectSounds=new Dictionary<EffectDef,string>();
  public void AdaptComposedEffectAudio(EffectDef definition){
   // These owned runtime records are distinct from original baked assets.
   // Audio is unavailable; preserve visual dispatch and restore the event metadata.
   if(string.IsNullOrEmpty(definition.spawnSoundEventName)||priorComposedEffectSounds.ContainsKey(definition))return;
   priorComposedEffectSounds.Add(definition,definition.spawnSoundEventName);
   typeof(EffectDef).GetProperty("spawnSoundEventName").SetValue(definition,null,null);
   if(coordinator.r.rewards!=null)coordinator.r.rewards.unavailableEffectSounds=priorComposedEffectSounds.Count;
  }
  public void SetCatalogBodyTemplate(int index,GameObject template){
   ((GameObject[])PortSession.RewardField(typeof(BodyCatalog),"bodyPrefabs").GetValue(null))[index]=template;
   ((CharacterBody[])PortSession.RewardField(typeof(BodyCatalog),"bodyPrefabBodyComponents").GetValue(null))[index]=template.GetComponent<CharacterBody>();
   ((Component[][])PortSession.RewardField(typeof(BodyCatalog),"bodyComponents").GetValue(null))[index]=template.GetComponents<Component>();
   ((GenericSkill[][])PortSession.RewardField(typeof(BodyCatalog),"skillSlots").GetValue(null))[index]=template.GetComponents<GenericSkill>();
  }
  public void BindCatalogBodyTemplate(GameObject template){
   var body=template.GetComponent<CharacterBody>();int index=(int)body.bodyIndex;
   var original=BodyCatalog.GetBodyPrefab(body.bodyIndex);
   coordinator.Check(coordinator.ownsBodyCatalog&&original&&original.name==template.name&&original!=template&&template.activeSelf&&!template.activeInHierarchy&&!coordinator.priorCatalogBodyTemplates.ContainsKey(index),"Owned catalog body-template identity invalid: "+template.name);
   coordinator.priorCatalogBodyTemplates.Add(index,original);SetCatalogBodyTemplate(index,template);
   coordinator.Check(BodyCatalog.GetBodyPrefab(body.bodyIndex)==template&&BodyCatalog.GetBodyPrefabBodyComponent(body.bodyIndex)==body,"Original spawn catalog did not select the owned template");
  }
  public void RestoreCatalogBodyTemplates(){foreach(var pair in coordinator.priorCatalogBodyTemplates)SetCatalogBodyTemplate(pair.Key,pair.Value);coordinator.priorCatalogBodyTemplates.Clear();}
  public void InitializeComposedEffects(System.Collections.Generic.IEnumerable<EffectDef> definitions){
   priorComposedEffectAvailability=EffectCatalog.availability;
   // The composed path has no ContentManager additions array. The current
   // original providers supply no extra EffectDefs beyond their baked catalog.
   EffectCatalog.SetEntries(Array.Empty<EffectDef>());EffectCatalog.availability.MakeAvailable();
   coordinator.Check(EffectCatalog.effectCount>0,"Original baked effect catalog unavailable");
   RegisterComposedEffects(definitions);
   foreach(var definition in (EffectDef[])PortSession.RewardField(typeof(EffectCatalog),"entries").GetValue(null))AdaptComposedEffectAudio(definition);
  }
  public void RegisterComposedEffects(System.Collections.Generic.IEnumerable<EffectDef> definitions){
   var entries=(EffectDef[])PortSession.RewardField(typeof(EffectCatalog),"entries").GetValue(null);
   foreach(var definition in definitions){
    var index=EffectCatalog.FindEffectIndex(definition.prefabName);
    coordinator.Check(index!=EffectIndex.Invalid&&definition.prefabEffectComponent,"Original baked effect identity absent: "+definition.prefabName);
    typeof(EffectDef).GetProperty("index").SetValue(definition,index,null);
    definition.prefabEffectComponent.effectIndex=index;entries[(int)index]=definition;AdaptComposedEffectAudio(definition);
   }
  }
  public void RestoreComposedEffects(EffectDef[] previous){
   var entries=(EffectDef[])PortSession.RewardField(typeof(EffectCatalog),"entries").GetValue(null);
   foreach(var definition in entries)if(definition.prefabEffectComponent)definition.prefabEffectComponent.effectIndex=EffectIndex.Invalid;
   foreach(var pair in priorComposedEffectSounds)typeof(EffectDef).GetProperty("spawnSoundEventName").SetValue(pair.Key,pair.Value,null);priorComposedEffectSounds.Clear();
   if(coordinator.r.rewards!=null)coordinator.r.rewards.effectSoundMetadataRestored=true;
   PortSession.RewardField(typeof(EffectCatalog),"entries").SetValue(null,previous);
   ((IDictionary)PortSession.RewardField(typeof(EffectCatalog),"nameToEffectIndex").GetValue(null)).Clear();
   EffectCatalog.availability=priorComposedEffectAvailability;
  }
  public BuffDef[] UpdatedComparisonBuffs(SessionConfig cfg){
   if(!cfg.integratedWorld||!Resources.Load<TextAsset>("WholeCatalogBootstrap"))return new BuffDef[0];
   var definitions=WholeCatalogComposed.BuffDefinitions();
   // The current original DLC4 provider maps Buffs fields to "bd" + field name.
   // Definition registration supplies comparisons; it grants no buff or expansion.
   var fields=typeof(DLC4Content.Buffs).GetFields(BindingFlags.Public|BindingFlags.Static);
   var selected=fields.Select(field=>definitions.SingleOrDefault(def=>def.name=="bd"+field.Name)).ToArray();
   coordinator.Check(selected.All(def=>def)&&selected.Distinct().Count()==fields.Length,"Current original comparison buff identities missing or ambiguous");
   for(int i=0;i<fields.Length;i++)coordinator.BindEnemyDefinition(typeof(DLC4Content.Buffs),fields[i].Name,selected[i]);
   return selected;
  }
  public ItemDef[] UpdatedComparisonItems(SessionConfig cfg){
   if(!cfg.integratedWorld||!Resources.Load<TextAsset>("WholeCatalogBootstrap"))return new ItemDef[0];
   var definitions=WholeCatalogComposed.ItemDefinitions();
   var fields=typeof(DLC4Content.Items).GetFields(BindingFlags.Public|BindingFlags.Static);
   var selected=fields.Select(field=>definitions.SingleOrDefault(def=>def.name==field.Name)).ToArray();
   coordinator.Check(selected.All(def=>def)&&selected.Distinct().Count()==fields.Length,"Current original comparison item identities missing or ambiguous");
   for(int i=0;i<fields.Length;i++)coordinator.BindEnemyDefinition(typeof(DLC4Content.Items),fields[i].Name,selected[i]);
   return selected;
  }
  public void RestoreBodySettingsTransform(){
   if(ownsBodySettingsTransform){
    coordinator.Check(ReferenceEquals(Addressables.InternalIdTransformFunc,ownedBodySettingsTransform),"Owned settings transform replaced before cleanup");
    Addressables.InternalIdTransformFunc=priorBodySettingsTransform;
    coordinator.Check(ReferenceEquals(Addressables.InternalIdTransformFunc,priorBodySettingsTransform),"Prior settings transform did not restore");
    ownsBodySettingsTransform=false;priorBodySettingsTransform=null;ownedBodySettingsTransform=null;coordinator.r.catalogTransformRestored=true;
   }
  }
  public void Dispose(){CleanupLoadoutTables();}
 }
}
