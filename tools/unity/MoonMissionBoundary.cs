using System;
using System.Collections;
using System.Collections.Generic;
using System.Linq;
using RoR2;
using UnityEngine;
using UnityEngine.Networking;

// Owned Android activation/visual/input boundary around recovered original mission callbacks.
public sealed partial class MovementBatchProbe {
 [Serializable] public class MoonMissionReport {
  public bool loaded,authority,cleaned;public int batteries,required,charged,encounters,spawnedEncounters;
  public string state,escapeState,error,scope;public string[] batteryStates,elevatorStates;
  public float seconds;public List<string> transitions=new List<string>();
 }
 GameObject[] moonRoots;EntityStateMachine moonEncounter;MoonBatteryMissionController moonBatteries;EscapeSequenceController moonEscape;
 void BindMoonActorVisuals(GameObject body,Transform model,ObjectiveActorSpec spec){
  foreach(var binding in spec.bindings){
   var target=body.transform.Find(binding.path);Check(target,"Original Moon visual transform missing: "+spec.name+"/"+binding.path);
   var renderer=target.GetComponent<Renderer>();var original=artifactBundle.LoadAsset<Material>(binding.material);Check(renderer&&original,"Original Moon renderer/material missing: "+binding.path);
   var material=Instantiate(original);material.shader=Resources.Load<Shader>("CommandoMaterialPreview");material.shaderKeywords=new string[0];material.SetFloat("_EmissionEnabled",0);objectiveResources.Add(material);renderer.sharedMaterial=material;renderer.gameObject.layer=30;
   if(!string.IsNullOrEmpty(binding.mesh)){var mesh=artifactBundle.LoadAsset<Mesh>(binding.mesh);Check(mesh,"Original Moon mesh missing");var skin=renderer as SkinnedMeshRenderer;if(skin){Check(mesh.bindposes.Length==skin.bones.Length,"Original Moon bind pose mismatch");skin.sharedMesh=mesh;skin.updateWhenOffscreen=true;}else{var filter=renderer.GetComponent<MeshFilter>();Check(filter,"Moon static mesh filter absent");filter.sharedMesh=mesh;}}
  }
  // Original CharacterModel lifecycle remains presentation-disabled, as in the accepted actors.
  var cm=model.GetComponent<CharacterModel>();Check(cm,"Moon CharacterModel missing");cm.visibility=VisibilityLevel.Invisible;
  foreach(var renderer in model.GetComponentsInChildren<Renderer>(true))if(renderer.sharedMaterial){renderer.gameObject.layer=30;}
 }
 void ActivateMoonSource(IntegratedStageSpec spec){
  r.phase="moon-mission-activate";r.moon=new MoonMissionReport{scope="Recovered original Moon batteries, elevators, scripted boss phases, trigger/escape wiring. Android activation/material/continuous-body boundary; no forced charge, encounter death, completion or platform identity."};Save();
  moonRoots=stageGeometryScene.GetRootGameObjects();
  Check(moonRoots.All(x=>!x.activeSelf),"Moon source root activation was not deferred");
  var info=moonRoots.SelectMany(x=>x.GetComponentsInChildren<SceneInfo>(true)).Single();info.gameObject.SetActive(true);
  Check(SceneInfo.instance==info&&info.groundNodes&&info.airNodes,"Original Moon SceneInfo/graphs missing");
  BindMoonSourceCards();
  foreach(var root in moonRoots)if(spec.activeRoots.Contains(root.name))root.SetActive(true);
  foreach(var identity in moonRoots.SelectMany(x=>x.GetComponentsInChildren<NetworkIdentity>(true)))if(identity.gameObject.activeInHierarchy&&identity.netId.Value==0)NetworkServer.Spawn(identity.gameObject);
  var toggle=moonRoots.SelectMany(x=>x.GetComponentsInChildren<SceneObjectToggleGroup>(true)).Single();Call(toggle,"ApplyActivations");
  moonBatteries=MoonBatteryMissionController.instance;moonEscape=moonRoots.SelectMany(x=>x.GetComponentsInChildren<EscapeSequenceController>(true)).Single();moonEncounter=moonRoots.SelectMany(x=>x.GetComponentsInChildren<EntityStateMachine>(true)).Single(x=>x.customName=="MissionController");
  Check(moonBatteries&&moonBatteries.numRequiredBatteries==4&&moonEscape&&moonEncounter,"Original Moon mission context missing");
  r.moon.loaded=true;r.moon.authority=NetworkServer.active&&worldPlayer.hasEffectiveAuthority;ObserveMoonMission();Save();
 }
 IEnumerator PrepareMoonWorld(){
  r.phase="moon-mission-context";Save();
  Check(moonBatteries&&moonEncounter&&moonEscape,"Recovered Moon mission did not activate");
  yield return null;ObserveMoonMission();
 }
 void BindMoonSourceCards(){
  // Source spawn cards keep their cost/scaling/placement/squad contracts; owned templates
  // supply the same original body/master and measured default visual closure.
  foreach(var encounter in moonRoots.SelectMany(x=>x.GetComponentsInChildren<ScriptedCombatEncounter>(true))){
   for(int i=0;i<encounter.spawns.Length;i++){
    var info=encounter.spawns[i];var source=info.spawnCard as CharacterSpawnCard;Check(source,"Original Moon encounter has an unsupported spawn card");
    var card=objectiveCards.SingleOrDefault(x=>x.name==source.name);Check(card&&card.prefab,"Original Moon encounter template missing: "+source.name);info.spawnCard=card;encounter.spawns[i]=info;
   }
  }
  foreach(var director in moonRoots.SelectMany(x=>x.GetComponentsInChildren<CombatDirector>(true))){
   if(!director.monsterCards)continue;var deck=Instantiate(director.monsterCards);objectiveResources.Add(deck);
   foreach(var category in deck.categories)foreach(var card in category.cards){var source=card.spawnCard as CharacterSpawnCard;if(!source)continue;var owned=objectiveCards.SingleOrDefault(x=>x.name==source.name);Check(owned,"Original Moon director card has no compatible template: "+source.name);card.spawnCard=owned;}
   director.monsterCards=deck;director.onSpawnedServer.AddListener(QueueObjectiveDirectorActor);
  }
 }
 void ObserveMoonMission(){
  if(r.moon==null||!moonEncounter)return;var report=r.moon;report.seconds=r.nova==null?0:r.nova.seconds;
  var state=moonEncounter.state==null?"uninitialized":moonEncounter.state.GetType().FullName;if(report.state!=state){report.state=state;report.transitions.Add(state);Save();}
  report.required=moonBatteries.numRequiredBatteries;report.charged=moonBatteries.numChargedBatteries;
  var batteries=moonRoots.SelectMany(x=>x.GetComponentsInChildren<HoldoutZoneController>(true)).Where(x=>x.gameObject.activeInHierarchy&&x.GetComponent<PurchaseInteraction>()).ToArray();report.batteries=batteries.Length;
  report.batteryStates=batteries.Select(x=>x.name+"|"+x.GetComponent<EntityStateMachine>().state+"|"+x.charge.ToString("F3")).ToArray();
  report.elevatorStates=moonRoots.SelectMany(x=>x.GetComponentsInChildren<EntityStateMachine>(true)).Where(x=>x.gameObject.name=="MoonElevator").Select(x=>x.state==null?"uninitialized":x.state.GetType().FullName).ToArray();
  var encounters=moonRoots.SelectMany(x=>x.GetComponentsInChildren<ScriptedCombatEncounter>(true)).ToArray();report.encounters=encounters.Length;report.spawnedEncounters=encounters.Count(x=>x.hasSpawnedServer);report.escapeState=moonEscape.mainStateMachine.state==null?"uninitialized":moonEscape.mainStateMachine.state.GetType().FullName;
 }
 void CleanupMoonMission(){
  if(moonRoots!=null)foreach(var root in moonRoots)if(root)root.SetActive(false);
  moonEncounter=null;moonBatteries=null;moonEscape=null;moonRoots=null;if(r.moon!=null)r.moon.cleaned=true;
 }
}
