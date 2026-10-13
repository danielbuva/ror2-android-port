using System;
using System.Collections.Generic;
using System.Linq;
using RoR2;
using UnityEngine;

// Original native stage pools in whole-catalog mode; legacy filtered decks remain a rollback path.
// Card/category weights, availability and placement fields remain original; excluded content is explicit.
public sealed partial class MovementBatchProbe {
 [Serializable] public class StageCombatDeckSpec {public string name,asset;public int cards,categories,excluded;}
 [Serializable] public class StageCombatSpawn {public string card;public int count;}
 [Serializable] public class StageCombatDeckReport {public string stage;public string[] cards;public int excluded;public bool nativePool,nativeScenePopulation;public int initialInteractableCredits,remainingInteractableCredits,playerSpawnPoints,droneDefinitions,availableDrones,pickupDefinitions,lunarLoot;public List<string> placedInteractables=new List<string>();public string[] interactableCards;public List<StageCombatSpawn> spawned=new List<StageCombatSpawn>();}
 readonly HashSet<CharacterMaster> stageCombatActors=new HashSet<CharacterMaster>();StageCombatDeckReport currentStageCombatDeck;
 void SelectStageCombatDeck(Result cfg,string stage){
  if(cfg.stageCombatDecks==null||cfg.stageCombatDecks.Length==0||stage=="moon2")return;
  var spec=cfg.stageCombatDecks.SingleOrDefault(x=>x.name==stage);Check(spec!=null,"Recovered stage combat deck absent: "+stage);
  if(r.liveCatalogs!=null){
   var native=SelectWholeStagePool(stage);var nativeCards=native.categories.SelectMany(category=>category.cards).ToArray();
   if(automaticDeck)Destroy(automaticDeck);automaticDeck=native;
   r.director.scope="Original ClassicStageInfo/DccsPool/DCCSBlender population selection and native card availability; complete owned actor catalog. Android scene transport/input/audio boundaries remain; registration is not all-content behavior acceptance.";
   currentStageCombatDeck=new StageCombatDeckReport{stage=stage,cards=nativeCards.Select(card=>card.GetSpawnCard().name).ToArray(),excluded=0,nativePool=true,interactableCards=wholeStageInfo.interactableCategories?wholeStageInfo.interactableCategories.categories.SelectMany(category=>category.cards).Select(card=>card.GetSpawnCard().name).ToArray():new string[0]};
   r.director.stageDecks.Add(currentStageCombatDeck);if(rewardDirector)rewardDirector.monsterCards=native;return;
  }
  var source=artifactBundle.LoadAsset<DirectorCardCategorySelection>(spec.asset);Check(source&&source.categories.Length==spec.categories,"Stage deck source categories differ");
  var deck=Instantiate(source);var cards=deck.categories.SelectMany(x=>x.cards).ToArray();Check(cards.Length==spec.cards&&cards.Length>0,"Stage deck supported card count differs");
  var supported=new[]{rewardCard}.Concat(objectiveCards).ToDictionary(x=>x.name,x=>x);
  foreach(var card in cards){CharacterSpawnCard owned;Check(card.spawnCard&&supported.TryGetValue(card.spawnCard.name,out owned),"Stage deck references unavailable actor");card.spawnCard=supported[card.spawnCard.name];Check(card.selectionWeight>0&&!card.requiredUnlockableDef&&!card.forbiddenUnlockableDef&&string.IsNullOrEmpty(card.requiredUnlockable)&&string.IsNullOrEmpty(card.forbiddenUnlockable),"Stage card profile restriction unavailable");}
  if(automaticDeck)Destroy(automaticDeck);automaticDeck=deck;
  r.director.scope="Original continuous director/credits/targeting with supported source base-stage category/card contracts; inherited startup Beetle, incomplete actors/DLC/family pools/SceneDirector/platform context. Actual population recorded per stage; catalog registration is not actor acceptance.";
  currentStageCombatDeck=new StageCombatDeckReport{stage=stage,cards=cards.Select(x=>x.spawnCard.name).ToArray(),excluded=spec.excluded};r.director.stageDecks.Add(currentStageCombatDeck);
  if(rewardDirector)rewardDirector.monsterCards=deck;
 }
 void RecordStageCombatSpawn(GameObject obj,CharacterBody player){
  var master=obj.GetComponent<CharacterMaster>();Check(master&&currentStageCombatDeck!=null,"Stage combat spawn has no owned deck context");
  // Compare the owned body template; the native clone is a separate network identity.
  var candidates=(currentStageCombatDeck.nativePool?wholeSpawnCards.Values:new[]{rewardCard}.Concat(objectiveCards)).Where(card=>currentStageCombatDeck.cards.Contains(card.name)&&card.prefab.GetComponent<CharacterMaster>().bodyPrefab==master.bodyPrefab).ToArray();
  var chosen=currentStageCombatDeck.nativePool?(DirectorCard)typeof(CombatDirector).GetField("currentMonsterCard",System.Reflection.BindingFlags.Instance|System.Reflection.BindingFlags.NonPublic).GetValue(rewardDirector):null;
  var card=chosen!=null?chosen.GetSpawnCard() as CharacterSpawnCard:candidates.SingleOrDefault();
  Check(card&&candidates.Contains(card),"Native director spawn does not match its actual selected card");
  Check(card&&currentStageCombatDeck.cards.Contains(card.name),"Native stage director spawned outside its supported deck");
  var row=currentStageCombatDeck.spawned.FirstOrDefault(x=>x.card==card.name);if(row==null){row=new StageCombatSpawn{card=card.name};currentStageCombatDeck.spawned.Add(row);}row.count++;
  if(IsObjectiveActor(master.GetBody())){stageCombatActors.Add(master);return;}RecordDirectorActor(obj,player);
 }
 void CleanupStageCombatDecks(){stageCombatActors.Clear();currentStageCombatDeck=null;}
}
