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

public sealed partial class MovementBatchProbe {
 bool ownsLoadoutTables,ownsSkillCatalog;
 bool ownsBodySettingsTransform;
 Func<IResourceLocation,string> priorBodySettingsTransform,ownedBodySettingsTransform;
 // A separate closure owns only path strings, never this session or its report.
 static Func<IResourceLocation,string> CreateBodySettingsTransform(string original,string local){return loc=>loc.InternalId==original?local:loc.InternalId;}
 object priorLoadoutDefaults,priorBodyInfos;
 readonly Dictionary<object,object> priorViewables=new Dictionary<object,object>();
 readonly HashSet<ViewablesCatalog.Node> priorViewableChildren=new HashSet<ViewablesCatalog.Node>();
 static FieldInfo LoadoutField(string name){return typeof(Loadout.BodyLoadoutManager).GetField(name,BindingFlags.NonPublic|BindingFlags.Static);}
 static FieldInfo ViewableField(string name){return typeof(ViewablesCatalog).GetField(name,BindingFlags.NonPublic|BindingFlags.Static);}
 void PrepareLoadoutTables(GameObject prefab){
  Check(!SkillCatalog.allSkillDefs.Any()&&!SkillCatalog.allSkillFamilies.Any(),"Existing skill catalog ownership");
  priorLoadoutDefaults=LoadoutField("defaultBodyLoadouts").GetValue(null);priorBodyInfos=LoadoutField("allBodyInfos").GetValue(null);
  Check(priorLoadoutDefaults==null&&priorBodyInfos==null,"Existing loadout defaults ownership");
  var slots=prefab.GetComponents<GenericSkill>();Check(slots.Length==4,"Original Commando skill-slot count");
  bool complete=r.liveCatalogs!=null;
  var selectedFamilies=BodyCatalog.allBodyPrefabs.SelectMany(x=>x.GetComponents<GenericSkill>()).Select(x=>x.skillFamily).Where(x=>x).Distinct().ToArray();
  var families=complete?WholeCatalogComposed.CategoryFamily(RoR2.ContentManagement.AddressablesLabels.skillFamily,selectedFamilies):selectedFamilies;
  Check(families.Length>=4&&families.All(x=>x&&x.variants.Length>0&&x.defaultVariantIndex<x.variants.Length),"Actual family/default-variant contract");
  // A source Copycat family has an empty variant. Register it unchanged; never invent a SkillDef.
  var selectedDefs=families.SelectMany(x=>x.variants.Select(v=>v.skillDef)).Where(x=>x).Distinct().ToArray();
  var defs=complete?WholeCatalogComposed.CategoryFamily(RoR2.ContentManagement.AddressablesLabels.skillDef,selectedDefs):selectedDefs;
  if(complete){r.liveCatalogs.skills=defs.Length;r.liveCatalogs.skillFamilies=families.Length;r.liveCatalogs.emptySkillVariants=families.Sum(family=>family.variants.Count(variant=>!variant.skillDef));}
  ownsSkillCatalog=true;StaticCall(typeof(SkillCatalog),"SetSkillDefs",(object)defs);StaticCall(typeof(SkillCatalog),"SetSkillFamilies",(object)families);
  foreach(var family in families)Check(SkillCatalog.GetSkillFamily(family.catalogIndex)==family,"Original family catalog identity");
  foreach(var def in defs)Check(SkillCatalog.GetSkillDef(def.skillIndex)==def,"Original skill catalog identity");
  Check(SurvivorCatalog.GetSurvivorIndexFromBodyIndex(prefab.GetComponent<CharacterBody>().bodyIndex)==SurvivorIndex.None,"Unexpected survivor-specific viewable context");
  var map=(IDictionary)ViewableField("fullNameToNodeMap").GetValue(null);foreach(DictionaryEntry entry in map)priorViewables.Add(entry.Key,entry.Value);
  var root=(ViewablesCatalog.Node)ViewableField("rootNode").GetValue(null);foreach(var child in root.children)priorViewableChildren.Add(child);
  ownsLoadoutTables=true;r.phase="original-loadout-initialize";Save();StaticCall(typeof(Loadout.BodyLoadoutManager),"Init");
  var body=prefab.GetComponent<CharacterBody>();var defaults=(Array)LoadoutField("defaultBodyLoadouts").GetValue(null);
  Check(defaults!=null&&defaults.Length==BodyCatalog.bodyCount,"Original default body loadout missing");var loadout=new Loadout();Check(loadout.bodyLoadoutManager.GetSkinIndex(body.bodyIndex)==0,"Original default skin");
  for(int i=0;i<slots.Length;i++)Check(loadout.bodyLoadoutManager.GetSkillVariant(body.bodyIndex,i)==slots[i].skillFamily.defaultVariantIndex,"Original default skill variant");
 }
 void CleanupLoadoutTables(){
  if(ownsLoadoutTables){
   LoadoutField("defaultBodyLoadouts").SetValue(null,priorLoadoutDefaults);LoadoutField("allBodyInfos").SetValue(null,priorBodyInfos);
   var root=(ViewablesCatalog.Node)ViewableField("rootNode").GetValue(null);foreach(var child in root.children.ToArray())if(!priorViewableChildren.Contains(child))child.SetParent(null);
   var map=(IDictionary)ViewableField("fullNameToNodeMap").GetValue(null);map.Clear();foreach(var pair in priorViewables)map.Add(pair.Key,pair.Value);ownsLoadoutTables=false;
  }
  if(ownsSkillCatalog){StaticCall(typeof(SkillCatalog),"SetSkillFamilies",(object)new SkillFamily[0]);StaticCall(typeof(SkillCatalog),"SetSkillDefs",(object)new SkillDef[0]);ownsSkillCatalog=false;}
 }

 IEnumerator RegisterBodyCatalog(){
  // Current original SpawnBody requires the game's PreSplash preset table.
  // This immutable application table is initialized once, not per session.
  if(BodyHandlingConfig.DefaultSettings==null){r.phase="original-body-handling-presets";Save();BodyHandlingConfig.Presets.InitializePresets();}
  Check(BodyHandlingConfig.DefaultSettings!=null&&BodyHandlingConfig.DefaultSettings.currentPreset==BodyHandlingPresetIndex.Initial,"Original body-handling presets unavailable");
  if(Resources.Load<TextAsset>("WholeCatalogBootstrap")){var shared=WholeCatalogComposed.Prepare();while(shared.MoveNext())yield return shared.Current;}
  Check(BodyCatalog.bodyCount==0&&LegacyResourcesAPI.ActiveCount==0,"Existing catalog/request ownership");
  r.phase="body-catalog-initialize";Save();
  var directory=Path.Combine(Application.persistentDataPath,"body-catalog-probe");Directory.CreateDirectory(directory);
  var catalog=Path.Combine(directory,"catalog.json");var settings=Path.Combine(directory,"settings.json");
  // Reuse the accepted controller probe's real, empty Addressables initialization.
  File.WriteAllText(catalog,"{\"m_LocatorId\":\"body-catalog-probe\",\"m_ProviderIds\":[],\"m_InternalIds\":[],\"m_KeyDataString\":\"AAAAAA==\",\"m_BucketDataString\":\"AAAAAA==\",\"m_EntryDataString\":\"AAAAAA==\",\"m_ExtraDataString\":\"\",\"m_resourceTypes\":[]}");
  var data=new ResourceManagerRuntimeData{BuildTarget="Android",DisableCatalogUpdateOnStartup=true,LogResourceManagerExceptions=true};
  data.CatalogLocations.Add(new ResourceLocationData(new[]{ResourceManagerRuntimeData.kCatalogAddress},catalog,typeof(ContentCatalogProvider),typeof(ContentCatalogData)));
  File.WriteAllText(settings,JsonUtility.ToJson(data));var originalSettings=Addressables.RuntimePath+"/settings.json";
  Check(!ownsBodySettingsTransform,"Existing owned settings transform");
  priorBodySettingsTransform=Addressables.InternalIdTransformFunc;ownedBodySettingsTransform=CreateBodySettingsTransform(originalSettings,settings);
  Addressables.InternalIdTransformFunc=ownedBodySettingsTransform;ownsBodySettingsTransform=true;r.catalogTransformInstalled=true;
  var init=Addressables.InitializeAsync();Addressables.ResourceManager.Acquire(init);
  var deadline=Time.realtimeSinceStartup+8;while(!init.IsDone&&Time.realtimeSinceStartup<deadline)yield return null;
  Check(init.IsDone&&init.Status==AsyncOperationStatus.Succeeded,"Real Addressables initialization failed");Addressables.Release(init);
  string mapped;const string key="Textures/BodyIcons/CommandoBody";
  Check(!LegacyResourcesAPI.GetGuid(key,out mapped),"Unexpected legacy portrait alias");
  var missing=LegacyResourcesAPI.LoadAsync<Texture2D>(key);deadline=Time.realtimeSinceStartup+3;
  while(!missing.IsDone&&Time.realtimeSinceStartup<deadline)yield return null;
  yield return null;
  Check(missing.IsDone&&missing.Status==AsyncOperationStatus.Failed&&missing.Result==null,"Missing portrait did not fail honestly");
  Check(missing.OperationException is InvalidKeyException,"Unexpected portrait failure class");Addressables.Release(missing);
  Check(LegacyResourcesAPI.ActiveCount==0,"Missing request callback not drained");
  var cfg=JsonUtility.FromJson<Result>(Resources.Load<TextAsset>("MovementBatchProbe").text);
  artifactBundle=AssetBundle.LoadFromFile(Path.Combine(Application.persistentDataPath,"payload","commando-prefab-lab"));Check(artifactBundle,"Body bundle missing");
  if(cfg.teleporterLoop){var preload=PreloadObjectiveBundle();while(preload.MoveNext())yield return preload.Current;}
  var prefab=artifactBundle.LoadAsset<GameObject>(cfg.bodyAsset);Check(prefab&&!prefab.activeSelf&&prefab.name=="CommandoBody","Unexpected body prefab");
  var body=prefab.GetComponent<CharacterBody>();var portrait=body.portraitIcon;
  Check(portrait&&portrait.name=="texCommandoIcon","Serialized portrait missing");
  r.phase="original-body-catalog-register";Save();
  var bodies=cfg.enemySpine?new[]{prefab,artifactBundle.LoadAsset<GameObject>(cfg.enemyBodyAsset)}:new[]{prefab};if(cfg.teleporterLoop)bodies=bodies.Concat(cfg.objectiveActors.Select(x=>artifactBundle.LoadAsset<GameObject>(x.body))).ToArray();
  if(cfg.integratedWorld&&Resources.Load<TextAsset>("WholeCatalogBootstrap")){
   bodies=WholeCatalogComposed.CategoryFamily(RoR2.ContentManagement.AddressablesLabels.characterBody,bodies.Distinct());
   r.liveCatalogs=new LiveCatalogReport{bodies=bodies.Length};

  }
  ownsBodyCatalog=true;StaticCall(typeof(BodyCatalog),"SetBodyPrefabs",(object)bodies);
  deadline=Time.realtimeSinceStartup+3;while(LegacyResourcesAPI.ActiveCount!=0&&Time.realtimeSinceStartup<deadline)yield return null;
  yield return null;yield return null;
  Check(LegacyResourcesAPI.ActiveCount==0,"Catalog portrait callback still pending");
  Check(BodyCatalog.bodyCount==bodies.Length&&body.bodyIndex!=(BodyIndex)(-1),"Original index assignment failed");
  Check(BodyCatalog.FindBodyIndex("CommandoBody")==body.bodyIndex&&BodyCatalog.FindBodyIndex("CommandoBody(Clone)")==body.bodyIndex,"Original name/index lookup failed");
  Check(BodyCatalog.GetBodyPrefab(body.bodyIndex)==prefab,"Original prefab lookup failed");
  Check(body.portraitIcon==portrait,"Missing-key callback replaced serialized portrait");
  Check(!prefab.activeSelf,"Catalog registration activated gameplay");
  if(cfg.initializeLoadoutTables)PrepareLoadoutTables(prefab);
  if(Resources.Load<TextAsset>("WholeCatalogBootstrap"))WholeCatalogComposed.ConfigureLocations();
 }
 ResourceAvailability priorComposedEffectAvailability;
 readonly Dictionary<int,GameObject> priorCatalogBodyTemplates=new Dictionary<int,GameObject>();
 void SetCatalogBodyTemplate(int index,GameObject template){
  ((GameObject[])RewardField(typeof(BodyCatalog),"bodyPrefabs").GetValue(null))[index]=template;
  ((CharacterBody[])RewardField(typeof(BodyCatalog),"bodyPrefabBodyComponents").GetValue(null))[index]=template.GetComponent<CharacterBody>();
  ((Component[][])RewardField(typeof(BodyCatalog),"bodyComponents").GetValue(null))[index]=template.GetComponents<Component>();
  ((GenericSkill[][])RewardField(typeof(BodyCatalog),"skillSlots").GetValue(null))[index]=template.GetComponents<GenericSkill>();
 }
 void BindCatalogBodyTemplate(GameObject template){
  var body=template.GetComponent<CharacterBody>();int index=(int)body.bodyIndex;
  var original=BodyCatalog.GetBodyPrefab(body.bodyIndex);
  Check(ownsBodyCatalog&&original&&original.name==template.name&&original!=template&&template.activeSelf&&!template.activeInHierarchy&&!priorCatalogBodyTemplates.ContainsKey(index),"Owned catalog body-template identity invalid: "+template.name);
  priorCatalogBodyTemplates.Add(index,original);SetCatalogBodyTemplate(index,template);
  Check(BodyCatalog.GetBodyPrefab(body.bodyIndex)==template&&BodyCatalog.GetBodyPrefabBodyComponent(body.bodyIndex)==body,"Original spawn catalog did not select the owned template");
 }
 void RestoreCatalogBodyTemplates(){foreach(var pair in priorCatalogBodyTemplates)SetCatalogBodyTemplate(pair.Key,pair.Value);priorCatalogBodyTemplates.Clear();}
 void InitializeComposedEffects(System.Collections.Generic.IEnumerable<EffectDef> definitions){
  priorComposedEffectAvailability=EffectCatalog.availability;
  // The composed path has no ContentManager additions array. The current
  // original providers supply no extra EffectDefs beyond their baked catalog.
  EffectCatalog.SetEntries(Array.Empty<EffectDef>());EffectCatalog.availability.MakeAvailable();
  Check(EffectCatalog.effectCount>0,"Original baked effect catalog unavailable");
  RegisterComposedEffects(definitions);
 }
 void RegisterComposedEffects(System.Collections.Generic.IEnumerable<EffectDef> definitions){
  var entries=(EffectDef[])RewardField(typeof(EffectCatalog),"entries").GetValue(null);
  foreach(var definition in definitions){
   var index=EffectCatalog.FindEffectIndex(definition.prefabName);
   Check(index!=EffectIndex.Invalid&&definition.prefabEffectComponent,"Original baked effect identity absent: "+definition.prefabName);
   typeof(EffectDef).GetProperty("index").SetValue(definition,index,null);
   definition.prefabEffectComponent.effectIndex=index;entries[(int)index]=definition;
  }
 }
 void RestoreComposedEffects(EffectDef[] previous){
  var entries=(EffectDef[])RewardField(typeof(EffectCatalog),"entries").GetValue(null);
  foreach(var definition in entries)if(definition.prefabEffectComponent)definition.prefabEffectComponent.effectIndex=EffectIndex.Invalid;
  RewardField(typeof(EffectCatalog),"entries").SetValue(null,previous);
  ((IDictionary)RewardField(typeof(EffectCatalog),"nameToEffectIndex").GetValue(null)).Clear();
  EffectCatalog.availability=priorComposedEffectAvailability;
 }
 BuffDef[] UpdatedComparisonBuffs(Result cfg){
  if(!cfg.integratedWorld||!Resources.Load<TextAsset>("WholeCatalogBootstrap"))return new BuffDef[0];
  var definitions=WholeCatalogComposed.BuffDefinitions();
  // The current original DLC4 provider maps Buffs fields to "bd" + field name.
  // Definition registration supplies comparisons; it grants no buff or expansion.
  var fields=typeof(DLC4Content.Buffs).GetFields(BindingFlags.Public|BindingFlags.Static);
  var selected=fields.Select(field=>definitions.SingleOrDefault(def=>def.name=="bd"+field.Name)).ToArray();
  Check(selected.All(def=>def)&&selected.Distinct().Count()==fields.Length,"Current original comparison buff identities missing or ambiguous");
  for(int i=0;i<fields.Length;i++)BindEnemyDefinition(typeof(DLC4Content.Buffs),fields[i].Name,selected[i]);
  return selected;
 }
 ItemDef[] UpdatedComparisonItems(Result cfg){
  if(!cfg.integratedWorld||!Resources.Load<TextAsset>("WholeCatalogBootstrap"))return new ItemDef[0];
  var definitions=WholeCatalogComposed.ItemDefinitions();
  var fields=typeof(DLC4Content.Items).GetFields(BindingFlags.Public|BindingFlags.Static);
  var selected=fields.Select(field=>definitions.SingleOrDefault(def=>def.name==field.Name)).ToArray();
  Check(selected.All(def=>def)&&selected.Distinct().Count()==fields.Length,"Current original comparison item identities missing or ambiguous");
  for(int i=0;i<fields.Length;i++)BindEnemyDefinition(typeof(DLC4Content.Items),fields[i].Name,selected[i]);
  return selected;
 }
 void CleanupBodyCatalog(){
  Check(LegacyResourcesAPI.ActiveCount==0,"Refuse teardown with pending portrait callbacks");
  CleanupLoadoutTables();
  RestoreCatalogBodyTemplates();
  if(ownsBodyCatalog){StaticCall(typeof(BodyCatalog),"SetBodyPrefabs",(object)new GameObject[0]);Check(BodyCatalog.bodyCount==0,"Owned catalog reset failed");ownsBodyCatalog=false;}
  if(artifactBundle){artifactBundle.Unload(true);artifactBundle=null;}
  ReleaseObjectiveBundlePreload();CleanupRecoveredText();
  if(Resources.Load<TextAsset>("WholeCatalogBootstrap"))WholeCatalogComposed.Release();
  RestoreBodySettingsTransform();if(r.liveCatalogs!=null){r.liveCatalogs.bodySkillCleanup=BodyCatalog.bodyCount==0&&SkillCatalog.skillCount==0&&SkillCatalog.skillFamilyCount==0;}
 }
 void RestoreBodySettingsTransform(){
  if(ownsBodySettingsTransform){
   Check(ReferenceEquals(Addressables.InternalIdTransformFunc,ownedBodySettingsTransform),"Owned settings transform replaced before cleanup");
   Addressables.InternalIdTransformFunc=priorBodySettingsTransform;
   Check(ReferenceEquals(Addressables.InternalIdTransformFunc,priorBodySettingsTransform),"Prior settings transform did not restore");
   ownsBodySettingsTransform=false;priorBodySettingsTransform=null;ownedBodySettingsTransform=null;r.catalogTransformRestored=true;
  }
 }
}
