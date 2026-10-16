using System;
using System.Collections;
using System.Linq;
using EntityStates.Missions.Goldshores;
using RoR2;
using UnityEngine;
using UnityEngine.Networking;

// The original scene, mission FSM, beacon purchases, boss and return portal own
// the gameplay. This boundary supplies the existing additive-stage context and
// optional unattended input through the same player controls used elsewhere.
public sealed partial class MovementBatchProbe {
 [Serializable] public class GoldshoresMissionReport {
  public string scope,state,returnScene;
  public bool diagnosticShrineSpawned,shrinePurchased,entryPortalUsed,sceneEntered,missionActive,bossDefeated,exitBegan,exitFinished;
  public int beaconsSpawned,beaconsRequired,beaconsActive,beaconsReadyToFight;
 }
 GoldshoresMissionController goldshoresMission;
 void PlaceGoldshoresDiagnosticShrine(){
  if(!r.goldshoresRoute||stageGeometryScene.name=="goldshores"||r.goldshores!=null&&r.goldshores.entryPortalUsed)return;
  Check(r.debugOptions!=null&&!string.IsNullOrWhiteSpace(r.debugOptions.purpose)&&DirectorCore.instance&&Run.instance&&worldPlayer,"Diagnostic Gold shrine requires an explicitly selected live-stage purpose");
  // Prefer the original SceneDirector placement. Only a selected diagnostic
  // route adds one original card through the original DirectorCore when absent.
  if(FindObjectsOfType<PortalStatueBehavior>().Any(statue=>statue&&statue.portalType==PortalStatueBehavior.PortalType.Goldshores&&statue.gameObject.scene==stageGeometryScene))return;
  var source=WholeCatalogComposed.LoadOwnedContent<InteractableSpawnCard>("Assets/WholeGame/RoR2/Base/Interactables/Shrines/ShrineGoldshoresAccess/iscShrineGoldshoresAccess.asset");
  Check(source&&source.name=="iscShrineGoldshoresAccess"&&source.prefab,"Original Gold shrine card unavailable");
  var card=WholeInteractableCard(source);
  var placement=new DirectorPlacementRule{placementMode=DirectorPlacementRule.PlacementMode.NearestNode,position=worldPlayer.corePosition,minDistance=4f,maxDistance=24f};
  var obj=DirectorCore.instance.TrySpawnObject(new DirectorSpawnRequest(card,placement,Run.instance.stageRng));
  Check(obj&&obj.GetComponent<PortalStatueBehavior>()&&obj.GetComponent<PortalStatueBehavior>().portalType==PortalStatueBehavior.PortalType.Goldshores&&obj.GetComponent<PurchaseInteraction>(),"Original DirectorCore could not place the selected Gold shrine");
  worldObjects.Add(obj);commerceOwned.Add(obj);WatchCommercePurchase(obj.GetComponent<PurchaseInteraction>());
  if(r.goldshores==null)r.goldshores=new GoldshoresMissionReport();r.goldshores.diagnosticShrineSpawned=true;
  Save();
 }
 bool IsGoldshoresEntryPortal(SceneExitController exit){
  return exit&&stageGeometryScene.IsValid()&&stageGeometryScene.name!="goldshores"&&worldTeleporter&&exit!=worldTeleporter.sceneExitController&&worldTeleporter.isCharged&&worldTeleporter.shouldAttemptToSpawnGoldshoresPortal&&exit.destinationScene&&exit.destinationScene.cachedName=="goldshores";
 }
 bool IsGoldshoresReturnPortal(SceneExitController exit){
  return exit&&stageGeometryScene.IsValid()&&stageGeometryScene.name=="goldshores"&&goldshoresMission&&goldshoresMission.entityStateMachine.state is Exit&&exit.useRunNextStageScene&&exit.destinationScene&&exit.destinationScene==Run.instance.nextStageScene;
 }

 void PrepareGoldshoresStage(){
  Check(stageGeometryScene.name=="goldshores"&&stageSourceObjects&&!objectiveStage&&!worldTeleporter,"Gold Shores requires its original source scene without a normal teleporter");
  r.objective=new ObjectiveReport{scope="Gold Shores original mission; no ordinary teleporter",ready=false};
  if(r.goldshores==null)r.goldshores=new GoldshoresMissionReport();
  r.goldshores.scope="Original Gold shrine/portal and Gold Shores beacon, boss, return-portal lifecycle; Android additive scene and optional assisted input";
  r.goldshores.sceneEntered=true;
  objectiveStageHost=new GameObject("Owned Gold Shores stage handoff");objectiveStageHost.SetActive(false);objectiveStageHost.AddComponent<NetworkIdentity>();
  objectiveStage=objectiveStageHost.AddComponent<Stage>();typeof(Stage).GetProperty("sceneDef").SetValue(objectiveStage,SceneCatalog.GetSceneDefForCurrentScene());Call(objectiveStage,"OnEnable");
  Check(Stage.instance==objectiveStage,"Original Gold Shores stage handoff missing");Save();
 }
 IEnumerator BeginGoldshoresMission(){
  Check(stageGeometryScene.name=="goldshores"&&stageSourceObjects&&Stage.instance==objectiveStage&&DirectorCore.instance&&wholeSceneDirector,"Gold Shores mission context unavailable");
  var missions=stageGeometryScene.GetRootGameObjects().SelectMany(root=>root.GetComponentsInChildren<GoldshoresMissionController>(true)).ToArray();
  Check(missions.Length==1&&missions[0].transform.parent==sourceSceneInfoRoot.transform&&!missions[0].gameObject.activeSelf,"Original Gold Shores mission object differs");
  var mission=missions[0];Check(mission.entityStateMachine&&mission.beaconSpawnCard&&mission.beaconsRequiredToSpawnBoss==4&&mission.beaconsToSpawnOnMap==7,"Original Gold Shores beacon/mission contract differs");
  mission.beaconSpawnCard=(InteractableSpawnCard)WholeInteractableCard(mission.beaconSpawnCard);
  goldshoresMission=mission;mission.gameObject.SetActive(true);yield return null;
  Check(GoldshoresMissionController.instance==mission&&mission.entityStateMachine.state is ActivateBeacons&&mission.beaconCount>=mission.beaconsRequiredToSpawnBoss,"Original Gold Shores mission did not start or place enough beacons");
  ObserveGoldshoresMission();Save();
 }
 void ObserveGoldshoresMission(){
  if(!goldshoresMission||r.goldshores==null)return;
  var report=r.goldshores;report.missionActive=GoldshoresMissionController.instance==goldshoresMission;
  report.state=goldshoresMission.entityStateMachine.state==null?"uninitialized":goldshoresMission.entityStateMachine.state.GetType().Name;
  report.beaconsRequired=goldshoresMission.beaconsRequiredToSpawnBoss;report.beaconsSpawned=goldshoresMission.beaconCount;
  report.beaconsActive=goldshoresMission.beaconsActive;report.beaconsReadyToFight=goldshoresMission.beaconsToSpawnOnMap;
  report.bossDefeated|=goldshoresMission.entityStateMachine.state is Exit;
 }
 bool GoldshoresRouteStimulus(CharacterBody player,NovaInputBridge bridge,float elapsed){
  if(!r.goldshoresRoute||worldManualTakeover)return false;
  Check(r.debugAcceleration!=null&&r.debugAcceleration.everAssisted,"Gold Shores unattended route must be marked assisted");
  if(stageGeometryScene.name=="goldshores"){
   Check(player.corePosition.y>-500f,"Gold Shores unattended route fell below recovered terrain without a source out-of-bounds recovery");
   ObserveGoldshoresMission();
   Check(goldshoresMission&&r.goldshores.missionActive,"Original Gold Shores mission became unavailable");
   var portal=FindObjectsOfType<SceneExitController>().FirstOrDefault(exit=>exit&&exit.useRunNextStageScene&&exit.gameObject.scene==stageGeometryScene);
   if(r.goldshores.bossDefeated&&portal){GoldshoresApproach(player,bridge,portal.gameObject,elapsed,"Use original Gold Shores return portal");return true;}
   var beacon=goldshoresMission.beaconInstanceList.Where(obj=>obj&&obj.GetComponent<PurchaseInteraction>()&&obj.GetComponent<PurchaseInteraction>().available).OrderBy(obj=>Vector3.SqrMagnitude(obj.transform.position-player.corePosition)).FirstOrDefault();
   if(beacon){
    var purchase=beacon.GetComponent<PurchaseInteraction>();
    if(purchase.CanBeAffordedByInteractor(player.GetComponent<Interactor>()))GoldshoresApproach(player,bridge,beacon,elapsed,"Activate original Gold Shores beacon");
    else{r.world.objective="Earn original beacon cost";ObjectiveCombatInput(player,bridge,elapsed,Vector2.zero,false);}
    return true;
   }
   r.world.objective="Defeat original Gold Shores boss";ObjectiveCombatInput(player,bridge,elapsed,Vector2.zero,false);return true;
  }
  if(r.goldshores!=null&&r.goldshores.exitFinished)return false;
  if(worldTeleporter&&worldTeleporter.shouldAttemptToSpawnGoldshoresPortal){
   if(r.goldshores==null)r.goldshores=new GoldshoresMissionReport();r.goldshores.shrinePurchased=true;
   if(worldTeleporter.isCharged){
    var portal=FindObjectsOfType<SceneExitController>().FirstOrDefault(exit=>exit&&exit!=worldTeleporter.sceneExitController&&exit.destinationScene&&exit.destinationScene.cachedName=="goldshores");
    if(portal){GoldshoresApproach(player,bridge,portal.gameObject,elapsed,"Use original Gold Shores portal");return true;}
   }
   return ObjectiveWorldStimulus(player,bridge,elapsed);
  }
  var shrine=FindObjectsOfType<PortalStatueBehavior>().Where(statue=>statue&&statue.portalType==PortalStatueBehavior.PortalType.Goldshores&&statue.gameObject.scene==stageGeometryScene&&statue.GetComponent<PurchaseInteraction>()&&statue.GetComponent<PurchaseInteraction>().available).OrderBy(statue=>Vector3.SqrMagnitude(statue.transform.position-player.corePosition)).FirstOrDefault();
  if(!shrine)return false; // The original director did not place one on this stage.
  var interaction=shrine.GetComponent<PurchaseInteraction>();
  if(interaction.CanBeAffordedByInteractor(player.GetComponent<Interactor>()))GoldshoresApproach(player,bridge,shrine.gameObject,elapsed,r.goldshores!=null&&r.goldshores.diagnosticShrineSpawned?"Buy diagnostic original Gold Shores shrine":"Buy naturally placed Gold Shores shrine");
  else{r.world.objective="Earn original Gold shrine cost";ObjectiveCombatInput(player,bridge,elapsed,Vector2.zero,false);}
  return true;
 }
 void GoldshoresApproach(CharacterBody player,NovaInputBridge bridge,GameObject target,float elapsed,string purpose){
  r.world.objective=purpose;
  NavigateWorldInput(player,bridge,target.transform.position,1.2f,target.name,elapsed);
  var collider=target.GetComponentsInChildren<Collider>(true).FirstOrDefault(value=>value.enabled&&!value.isTrigger);
  var aim=(collider?collider.bounds.center:target.transform.position)-player.inputBank.aimOrigin;
  bridge.aim=new Vector2(aim.x,aim.z).normalized;bridge.diagnosticAim=aim.normalized;
  if(worldDriver.currentInteractable==target&&elapsed-worldLastPress>.5f){bridge.diagnosticInteract=true;worldLastPress=elapsed;}
 }
}
