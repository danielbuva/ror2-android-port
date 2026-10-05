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
  public string state,escapeState,error,scope,inputObjective;public string[] batteryStates,elevatorStates;
  public Vector3 inputDestination;public int livingEncounterMembers,extractionZones;public bool gameOver;
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
  report.livingEncounterMembers=encounters.Where(x=>x.combatSquad).Sum(x=>x.combatSquad.memberCount);report.extractionZones=UnityEngine.Object.FindObjectsOfType<EscapeSequenceExtractionZone>().Length;report.gameOver=Run.instance&&Run.instance.isGameOverServer;
 }
 bool MoonWorldStimulus(CharacterBody player,NovaInputBridge bridge,float elapsed){
  Check(moonBatteries&&moonEncounter&&moonEscape,"Original Moon input context missing");
  var position=player.characterMotor.Motor.TransientPosition;var interactor=player.GetComponent<Interactor>();
  if(moonBatteries.numChargedBatteries<moonBatteries.numRequiredBatteries){
   var zones=moonRoots.SelectMany(x=>x.GetComponentsInChildren<HoldoutZoneController>(true)).Where(x=>x.gameObject.activeInHierarchy&&x.GetComponent<PurchaseInteraction>()).ToArray();
   var active=zones.FirstOrDefault(x=>x.enabled&&x.charge<1&&x.GetComponent<EntityStateMachine>().state is EntityStates.Missions.Moon.MoonBatteryActive);
   var battery=active?active:zones.Where(x=>x.GetComponent<PurchaseInteraction>().GetInteractability(interactor)==Interactability.Available).OrderBy(x=>Vector3.Distance(x.transform.position,position)).FirstOrDefault();
   if(!battery){bridge.movement=Vector2.zero;SetMoonInputObjective("Wait for source battery state",position);return true;}
   NavigateWorldInput(player,bridge,battery.transform.position,active?Mathf.Max(1,battery.currentRadius*.25f):1,battery.name,elapsed);
   if(active){MoonCombatInput(player,bridge,elapsed);SetMoonInputObjective("Charge original battery and fight",battery.transform.position);}
   else{AimMoonInteraction(player,bridge,battery.gameObject,elapsed);SetMoonInputObjective("Activate original battery",battery.transform.position);}
   return true;
  }
  if(moonEscape.mainStateMachine.state is EscapeSequenceController.EscapeSequenceMainState){
   var extraction=UnityEngine.Object.FindObjectsOfType<EscapeSequenceExtractionZone>().OrderBy(x=>Vector3.Distance(x.transform.position,position)).FirstOrDefault();
   if(extraction){NavigateWorldInput(player,bridge,extraction.transform.position,Mathf.Max(1,extraction.radius*.25f),extraction.name,elapsed);SetMoonInputObjective("Reach original extraction zone",extraction.transform.position);}
   else{bridge.movement=Vector2.zero;SetMoonInputObjective("Wait for source extraction activation",position);}
   MoonCombatInput(player,bridge,elapsed);return true;
  }
  var arena=moonRoots.SelectMany(x=>x.GetComponentsInChildren<AllPlayersTrigger>(true)).Single();var arenaCollider=arena.GetComponent<Collider>();Check(arenaCollider,"Original arena trigger collider missing");
  bool belowArena=position.y<arenaCollider.bounds.min.y-20;
  if(belowArena){
   var volume=moonRoots.SelectMany(x=>x.GetComponentsInChildren<JumpVolume>(true)).Where(x=>x.gameObject.activeInHierarchy&&x.enabled).OrderBy(x=>Vector3.Distance(x.transform.position,position)).FirstOrDefault();
   Check(volume,"Original charged elevator jump volume missing");var collider=volume.GetComponent<Collider>();Check(collider&&collider.enabled,"Original elevator trigger collider missing");
   NavigateWorldInput(player,bridge,collider.bounds.center,.3f,volume.name,elapsed);SetMoonInputObjective("Enter original elevator launch volume",collider.bounds.center);MoonCombatInput(player,bridge,elapsed);return true;
  }
  var enemies=directorActors.Where(x=>x.body&&x.body.healthComponent.alive).ToArray();
  if(enemies.Length>0){
   var nearest=enemies.OrderBy(x=>Vector3.Distance(x.body.corePosition,position)).First();var away=position-DirectorPhysicsPosition(nearest.body);away.y=0;var distance=away.magnitude;
   bridge.movement=distance<20?new Vector2(away.x,away.z).normalized:distance>35?-new Vector2(away.x,away.z).normalized:new Vector2(away.z,-away.x).normalized;
   bridge.diagnosticSprint=distance<16;bridge.diagnosticUtility=distance<16&&player.skillLocator.utility.CanExecute();bridge.DiagnosticJump(elapsed%1.8f<.25f);MoonCombatInput(player,bridge,elapsed);SetMoonInputObjective("Fight original scripted encounter",nearest.body.corePosition);
  }else{
   NavigateWorldInput(player,bridge,arenaCollider.bounds.center,1,arena.name,elapsed);SetMoonInputObjective("Enter original arena trigger / wait for next phase",arenaCollider.bounds.center);
  }
  return true;
 }
 void SetMoonInputObjective(string objective,Vector3 destination){r.world.objective=objective;r.moon.inputObjective=objective;r.moon.inputDestination=destination;}
 void AimMoonInteraction(CharacterBody player,NovaInputBridge bridge,GameObject target,float elapsed){
  var collider=target.GetComponentsInChildren<Collider>(true).FirstOrDefault(x=>x.enabled&&x.GetComponent<EntityLocator>()&&x.GetComponent<EntityLocator>().entity==target);
  var aim=(collider?collider.bounds.center:target.transform.position)-player.inputBank.aimOrigin;bridge.diagnosticAim=aim.normalized;bridge.aim=new Vector2(aim.x,aim.z).normalized;
  if(worldDriver.currentInteractable==target&&elapsed-worldLastPress>.5f){bridge.diagnosticInteract=true;worldLastPress=elapsed;}
 }
 void MoonCombatInput(CharacterBody player,NovaInputBridge bridge,float elapsed){
  var enemy=directorActors.Where(x=>x.body&&x.body.healthComponent.alive).OrderBy(x=>Vector3.Distance(x.body.corePosition,player.corePosition)).FirstOrDefault();if(enemy==null)return;
  var aim=enemy.body.corePosition-player.inputBank.aimOrigin;bridge.diagnosticAim=aim.normalized;bridge.aim=new Vector2(aim.x,aim.z).normalized;bridge.diagnosticPrimary=true;bridge.diagnosticSecondary=elapsed%4<.2f;bridge.diagnosticSpecial=elapsed%10<.2f;
 }
 void CleanupMoonMission(){
  if(moonRoots!=null)foreach(var root in moonRoots)if(root)root.SetActive(false);
  moonEncounter=null;moonBatteries=null;moonEscape=null;moonRoots=null;if(r.moon!=null)r.moon.cleaned=true;
 }
}
