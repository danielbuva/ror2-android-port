using System;
using System.Linq;
using EntityStates;
using RoR2;
using UnityEngine;
using UnityEngine.ResourceManagement.ResourceLocations;
using UnityEngine.ResourceManagement.ResourceProviders;

// Original source stage populations and champion selection; unsupported cards stay explicit.
public sealed partial class MovementBatchProbe {
 bool StagePopulationState(Type type,Result cfg){
  if(cfg.stagePopulationFamilies==null)return false;
  var families=new[]{"Titan","Vagrant","Jellyfish","GreaterWisp","Bell","Bison","Imp","HermitCrab","MiniMushroom","ClayBruiser","LemurianBruiser","Parent","ImpBoss","ClayBoss","RoboBallBoss","RoboBallMini","Grandparent"};
  var namespaces=new[]{"TitanMonster","VagrantMonster","JellyfishMonster","GreaterWispMonster","Bell","Bison","ImpMonster","HermitCrab","MiniMushroom","ClayBruiserMonster","LemurianBruiserMonster","ParentMonster","ImpBossMonster","ClayBoss","RoboBallBoss","RoboBallMini","GrandParentBoss"};
  if(cfg.stagePopulationFamilies.Contains("ClayBruiser")&&(type.Namespace??"").StartsWith("EntityStates.ClayBruiser.",StringComparison.Ordinal))return true;
  if(cfg.stagePopulationFamilies.Contains("Grandparent")&&new[]{"EntityStates.GrandParent","EntityStates.GrandParentSun"}.Contains(type.Namespace))return true;
  if(cfg.stagePopulationFamilies.Contains("Vagrant")&&type.Namespace=="EntityStates.VagrantNovaItem")return true;
  for(int i=0;i<namespaces.Length;i++)if(cfg.stagePopulationFamilies.Contains(families[i])&&
   (type.Namespace=="EntityStates."+namespaces[i]||(type.Namespace??"").StartsWith("EntityStates."+namespaces[i]+".",StringComparison.Ordinal)))return true;
  return false;
 }
 void PrepareStageBossDeck(Result cfg){
  objectiveBossDeck=Instantiate(automaticDeck);
  var champions=objectiveBossDeck.categories.SelectMany(x=>x.cards).Where(x=>x.spawnCard&&
   x.spawnCard.prefab.GetComponent<CharacterMaster>().bodyPrefab.GetComponent<CharacterBody>().isChampion&&
   !(x.spawnCard as CharacterSpawnCard).forbiddenAsBoss).ToArray();
  if(cfg.sourceStageBossDeck&&champions.Length>0){
   // CombatDirector performs original IsAvailable filtering and weighted choice.
   // Retain the full source subset: category weights contribute to that selection.
   r.objective.eligibleBossCards=champions.Select(x=>x.spawnCard.name).ToArray();
   r.objective.bossSelectionScope="Original native champion/availability/weighted selection from supported source stage deck";
  }else{
   var queen=objectiveCards.Single(x=>x.name=="cscBeetleQueen");var category=objectiveBossDeck.categories[0];var bossCard=category.cards[0];
   bossCard.spawnCard=queen;bossCard.selectionWeight=1;category.name="Champions";category.selectionWeight=2;category.cards=new[]{bossCard};objectiveBossDeck.categories=new[]{category};
   r.objective.eligibleBossCards=new[]{queen.name};r.objective.bossSelectionScope="Inherited Queen fallback; source stage champion closure unavailable";
  }
 }
 void PrepareStagePopulationSupport(Result cfg){
  if(string.IsNullOrEmpty(cfg.stageVagrantOverlayAsset))return;
  var source=objectiveBundlePreload.Result.GetAssetBundle().LoadAsset<Material>(cfg.stageVagrantOverlayAsset);Check(source&&source.name=="matVagrantEnergized","Original Vagrant energized overlay absent");
  var key="Materials/matVagrantEnergized";string guid;Check(LegacyResourcesAPI.GetGuid(key,out guid)&&guid==cfg.stageVagrantOverlayKey,"Original Vagrant overlay legacy identity differs");
  objectiveLocator.Add(guid,new ResourceLocationBase(guid,cfg.stageVagrantOverlayAsset,typeof(BundledAssetProvider).FullName,typeof(Material),objectiveBundleLocation));
 }
}
