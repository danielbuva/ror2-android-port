using System;
using System.Collections;
using System.Collections.Generic;
using System.Linq;
using RoR2;
using UnityEngine;
using UnityEngine.Networking;

// Owned Android activation/visual/input boundary around recovered original mission callbacks.
public sealed partial class MovementBatchProbe {
 ItemDef[] MoonItems(Result cfg){
  if(!cfg.moonMission)return new ItemDef[0];Check(cfg.moonCatalog!=null,"Original Moon metadata manifest missing");
  var names=new[]{"VoidMegaCrabItem","MasterCore","MasterBattery","ArtifactKey","PowerCube","PowerPyramid","PowerOrbSphere"};
  Check(cfg.moonCatalog.items.Length==names.Length,"Original Moon item metadata differs");var defs=new ItemDef[names.Length];
  for(int i=0;i<defs.Length;i++){
   defs[i]=artifactBundle.LoadAsset<ItemDef>(cfg.moonCatalog.items[i]);Check(defs[i]&&defs[i].name==names[i],"Original Moon ItemDef missing: "+names[i]);
   BindEnemyDefinition(i==0?typeof(DLC1Content.Items):i==3?typeof(RoR2Content.Items):typeof(DLC3Content.Items),names[i],defs[i]);
  }
  return defs; // Registration supplies indices, never inventory grants or unlocks.
 }
 BuffDef[] MoonBuffs(Result cfg){
  if(!cfg.moonMission)return new BuffDef[0];Check(cfg.moonCatalog!=null&&cfg.moonCatalog.buffs.Length==2,"Original Moon buff metadata differs");
  var names=new[]{"bdEliteLunar","bdCripple"};var fields=new[]{"AffixLunar","Cripple"};var defs=new BuffDef[2];
  for(int i=0;i<defs.Length;i++){defs[i]=artifactBundle.LoadAsset<BuffDef>(cfg.moonCatalog.buffs[i]);Check(defs[i]&&defs[i].name==names[i],"Original Moon BuffDef missing: "+names[i]);BindEnemyDefinition(typeof(RoR2Content.Buffs),fields[i],defs[i]);}
  return defs;
 }
 EquipmentDef[] MoonEquipment(Result cfg){
  if(!cfg.moonMission)return new EquipmentDef[0];Check(cfg.moonCatalog!=null&&cfg.moonCatalog.equipment.Length==1,"Original Lunar equipment metadata differs");
  var def=artifactBundle.LoadAsset<EquipmentDef>(cfg.moonCatalog.equipment[0]);Check(def&&def.name=="EliteLunarEquipment"&&def.passiveBuffDef==RoR2Content.Buffs.AffixLunar,"Original Lunar equipment/passive buff identity differs");
  BindEnemyDefinition(typeof(RoR2Content.Equipment),"AffixLunar",def);return new[]{def};
 }
 GameObject moonLunarMissile,moonCrippleEffect,previousMoonCripple;System.Reflection.FieldInfo moonCrippleSlot;bool ownsMoonCripple;
 int moonHelperIndex=-1,moonHelperReferences;GameObject moonTeleportHelper;
 int moonStealerIndex=-1,moonStealerReferences;GameObject moonStealerSource,moonTransferEffect,priorMoonTransferEffect;System.Reflection.FieldInfo moonTransferSlot;
 void PrepareMoonSupport(Result cfg){
  if(!cfg.moonMission)return;
  int missile=Array.IndexOf(cfg.objectiveSupportPaths,"Prefabs/Projectiles/LunarMissileProjectile"),cripple=Array.IndexOf(cfg.objectiveSupportPaths,"Prefabs/TemporaryVisualEffects/CrippleEffect");
  Check(missile>=0&&cripple>=0,"Original Lunar support manifest missing");
  moonHelperIndex=Array.IndexOf(cfg.objectiveSupportPaths,"SpawnCards/HelperPrefab");Check(moonHelperIndex>=0,"Original safe-teleport helper manifest missing");moonTeleportHelper=objectiveSupportSources[moonHelperIndex];Check(moonTeleportHelper&&moonTeleportHelper.name=="DirectorSpawnProbeHelperPrefab"&&moonTeleportHelper.GetComponentsInChildren<Component>(true).All(x=>x is Transform),"Original safe-teleport helper identity changed");moonHelperReferences=(int)typeof(UnityEngine.ResourceManagement.AsyncOperations.AsyncOperationHandle<GameObject>).GetProperty("ReferenceCount",System.Reflection.BindingFlags.Instance|System.Reflection.BindingFlags.NonPublic).GetValue(objectiveSupportLeases[moonHelperIndex]);Check(moonHelperReferences==1,"Unowned safe-teleport helper lease");
  moonLunarMissile=objectiveSupportSources[missile];Check(moonLunarMissile&&moonLunarMissile.GetComponent<RoR2.Projectile.ProjectileController>(),"Original Lunar missile component missing");
  moonStealerIndex=Array.IndexOf(cfg.objectiveSupportPaths,"Prefabs/NetworkedObjects/ItemStealController");Check(moonStealerIndex>=0,"Original final-phase item stealer manifest missing");moonStealerSource=objectiveSupportSources[moonStealerIndex];Check(moonStealerSource&&moonStealerSource.GetComponent<ItemStealController>()&&moonStealerSource.GetComponent<NetworkedBodyAttachment>()&&moonStealerSource.GetComponent<NetworkIdentity>(),"Original item stealer component contract missing");
  moonStealerReferences=(int)typeof(UnityEngine.ResourceManagement.AsyncOperations.AsyncOperationHandle<GameObject>).GetProperty("ReferenceCount",System.Reflection.BindingFlags.Instance|System.Reflection.BindingFlags.NonPublic).GetValue(objectiveSupportLeases[moonStealerIndex]);Check(moonStealerReferences==1,"Unowned item stealer provider lease");
  int transfer=Array.IndexOf(cfg.objectiveSupportPaths,"Prefabs/Effects/OrbEffects/ItemTransferOrbEffect");Check(transfer>=0,"Original item-transfer effect manifest missing");moonTransferEffect=objectiveSupportSources[transfer];Check(moonTransferEffect&&moonTransferEffect.GetComponent<EffectComponent>(),"Original item-transfer effect component missing");
  moonTransferSlot=typeof(RoR2.Orbs.ItemTransferOrb).GetField("orbEffectPrefab",System.Reflection.BindingFlags.Static|System.Reflection.BindingFlags.NonPublic);Check(moonTransferSlot!=null,"Original item-transfer effect slot missing");priorMoonTransferEffect=(GameObject)moonTransferSlot.GetValue(null);Check(!priorMoonTransferEffect,"Existing item-transfer effect binding");moonTransferSlot.SetValue(null,moonTransferEffect);
  moonCrippleSlot=BarrierSlot().DeclaringType.GetField("crippleEffectPrefab",System.Reflection.BindingFlags.Public|System.Reflection.BindingFlags.Static);
  Check(moonCrippleSlot!=null&&!ownsMoonCripple,"Original Cripple effect slot missing or already owned");previousMoonCripple=(GameObject)moonCrippleSlot.GetValue(null);
  Check(!previousMoonCripple,"Existing original Cripple effect slot; refuse replacement");
  var effect=objectiveSupportSources[cripple];Check(effect&&effect.GetComponent<TemporaryVisualEffect>(),"Original Cripple effect component missing");
  // Integrated gameplay does not initialize the optional isolated Barrier bundle.
  // Own this one measured slot and its real provider lease independently.
  moonCrippleEffect=effect;ownsMoonCripple=true;moonCrippleSlot.SetValue(null,effect);Check(ReferenceEquals(moonCrippleSlot.GetValue(null),effect),"Original Cripple effect binding failed");
 }
 void CleanupMoonSupport(){
  if(moonTransferSlot!=null){Check(ReferenceEquals(moonTransferSlot.GetValue(null),moonTransferEffect),"Original item-transfer effect ownership changed");moonTransferSlot.SetValue(null,priorMoonTransferEffect);moonTransferSlot=null;moonTransferEffect=null;}
  if(moonStealerIndex>=0&&objectiveSupportLeases!=null&&objectiveSupportLeases[moonStealerIndex].IsValid()){int extra=(int)typeof(UnityEngine.ResourceManagement.AsyncOperations.AsyncOperationHandle<GameObject>).GetProperty("ReferenceCount",System.Reflection.BindingFlags.Instance|System.Reflection.BindingFlags.NonPublic).GetValue(objectiveSupportLeases[moonStealerIndex])-moonStealerReferences;Check(extra>=0,"Item stealer reference baseline changed");for(int i=0;i<extra;i++)UnityEngine.AddressableAssets.Addressables.Release(moonStealerSource);}moonStealerIndex=-1;moonStealerSource=null;
  // Original Run/TeleportHelper sync requests retain the shared asset handle.
  // Source mission objects are inactive before this owned provider lease cleanup.
  if(moonHelperIndex>=0&&objectiveSupportLeases!=null&&objectiveSupportLeases[moonHelperIndex].IsValid()){int extra=(int)typeof(UnityEngine.ResourceManagement.AsyncOperations.AsyncOperationHandle<GameObject>).GetProperty("ReferenceCount",System.Reflection.BindingFlags.Instance|System.Reflection.BindingFlags.NonPublic).GetValue(objectiveSupportLeases[moonHelperIndex])-moonHelperReferences;Check(extra>=0,"Safe-teleport helper reference baseline changed");for(int i=0;i<extra;i++)UnityEngine.AddressableAssets.Addressables.Release(moonTeleportHelper);}
  moonHelperIndex=-1;moonTeleportHelper=null;
  if(ownsMoonCripple){Check(ReferenceEquals(moonCrippleSlot.GetValue(null),moonCrippleEffect),"Original Cripple slot ownership changed");moonCrippleSlot.SetValue(null,previousMoonCripple);ownsMoonCripple=false;}
  moonLunarMissile=null;moonCrippleEffect=null;
 }
 void BindMoonBodySupport(CharacterBody body){
  if(!moonLunarMissile||!body)return;
  var field=typeof(CharacterBody).GetField("lunarMissilePrefab",System.Reflection.BindingFlags.NonPublic|System.Reflection.BindingFlags.Instance);
  Check(field!=null&&field.GetValue(body)==null,"Unowned original Lunar missile cache");field.SetValue(body,moonLunarMissile);
 }
 bool OriginalActorEquipment(CharacterBody body){
  if(body.inventory.currentEquipmentIndex==EquipmentIndex.None)return true;
  return IsObjectiveActor(body)&&body.name.StartsWith("Lunar",StringComparison.Ordinal)&&RoR2Content.Equipment.AffixLunar&&
   body.inventory.currentEquipmentIndex==RoR2Content.Equipment.AffixLunar.equipmentIndex&&
   EquipmentCatalog.GetEquipmentDef(body.inventory.currentEquipmentIndex)==RoR2Content.Equipment.AffixLunar&&RoR2Content.Elites.Lunar.IsAvailable();
 }
 [Serializable] public class MoonMissionReport {
  public bool loaded,authority,cleaned,toggleInitialized,populationReady;public int batteries,required,charged,encounters,spawnedEncounters,sceneNetworkObjects,monsterCards;
  public string[] monsterCardNames,unmappedPoolCards;public float[] monsterCardWeights;
  public string state,escapeState,error,scope,inputObjective;public string[] batteryStates,elevatorStates;
  public int restoredBeamRenderers,activeBeamRenderers,liveBeamParticles;public MoonPillarMarker[] pillarMarkers;
  public int androidBeaconRenderers,activeAndroidBeacons;public bool farPillarVisibility;public string beaconPresentationError;
  public float observedGravityY;public MoonElevatorLaunch[] elevatorLaunches;
  public Vector3 inputDestination;public int livingEncounterMembers,extractionZones;public bool gameOver;
  public bool originalTimersScheduled,timersStopped,itemStealerObserved,dropshipHoldoutActive;public int fixedTimerTicks,pendingFixedTimers,cancelledOwnedTimers,liveItemStealers;
  public string[] dropshipStates;public float dropshipCharge,escapeSecondsRemaining;public Vector3 dropshipPosition;
  public float seconds;public List<string> transitions=new List<string>();
 }
 GameObject[] moonRoots;EntityStateMachine moonEncounter;MoonBatteryMissionController moonBatteries;EscapeSequenceController moonEscape;ClassicStageInfo moonStageInfo;DirectorCardCategorySelection priorMoonInteractables;
 void BindMoonActorVisuals(GameObject body,Transform model,ObjectiveActorSpec spec){
  if(spec.activations!=null)foreach(var activation in spec.activations){var target=body.transform.Find(activation.path);Check(target,"Original actor skin activation missing: "+spec.name+"/"+activation.path);target.gameObject.SetActive(activation.active);}
  foreach(var binding in spec.bindings){
   var target=body.transform.Find(binding.path);Check(target,"Original Moon visual transform missing: "+spec.name+"/"+binding.path);
   var renderer=target.GetComponent<Renderer>();var original=artifactBundle.LoadAsset<Material>(binding.material);Check(renderer&&original,"Original Moon renderer/material missing: "+binding.path);
   var material=Instantiate(original);material.shader=Resources.Load<Shader>("CommandoMaterialPreview");material.shaderKeywords=new string[0];material.SetFloat("_EmissionEnabled",0);if(spec.recoveredMaterials)AndroidMaterialPresentation.Apply(original,material);objectiveResources.Add(material);renderer.sharedMaterial=material;renderer.gameObject.layer=30;
   if(!string.IsNullOrEmpty(binding.mesh)){var mesh=artifactBundle.LoadAsset<Mesh>(binding.mesh);Check(mesh,"Original actor mesh missing");var skin=renderer as SkinnedMeshRenderer;var particles=renderer as ParticleSystemRenderer;if(skin){Check(mesh.bindposes.Length==skin.bones.Length,"Original actor bind pose mismatch");skin.sharedMesh=mesh;skin.updateWhenOffscreen=true;}else if(particles)particles.mesh=mesh;else{var filter=renderer.GetComponent<MeshFilter>();Check(filter,"Original actor static mesh filter absent: "+spec.name+"/"+binding.path);filter.sharedMesh=mesh;}}
  }
  // Original CharacterModel lifecycle remains presentation-disabled, as in the accepted actors.
  var cm=model.GetComponent<CharacterModel>();Check(cm,"Moon CharacterModel missing");cm.visibility=VisibilityLevel.Invisible;
  foreach(var renderer in model.GetComponentsInChildren<Renderer>(true))if(renderer.sharedMaterial){renderer.gameObject.layer=30;}
 }
 void ActivateMoonSource(IntegratedStageSpec spec){
  r.phase="moon-mission-activate";r.moon=new MoonMissionReport{scope="Recovered original Moon batteries, elevators, scripted boss phases, trigger/escape wiring. Android activation/material/continuous-body boundary; no forced charge, encounter death, completion or platform identity."};Save();
  try{
  moonRoots=stageGeometryScene.GetRootGameObjects();
  PrepareMoonTimers();
  Check(moonRoots.All(x=>!x.activeSelf),"Moon source root activation was not deferred");
  var info=moonRoots.SelectMany(x=>x.GetComponentsInChildren<SceneInfo>(true)).Single();info.gameObject.SetActive(true);
  Check(SceneInfo.instance==info&&info.groundNodes&&info.airNodes,"Original Moon SceneInfo/graphs missing");
  BindMoonPopulation();BindMoonSourceCards();
  foreach(var root in moonRoots)if(spec.activeRoots.Contains(root.name))root.SetActive(true);
  var sceneObjects=Resources.FindObjectsOfTypeAll<NetworkIdentity>().Where(x=>x.gameObject.hideFlags!=HideFlags.NotEditable&&x.gameObject.hideFlags!=HideFlags.HideAndDontSave&&!x.sceneId.IsEmpty()).ToArray();
  Check(sceneObjects.Length>0&&sceneObjects.All(x=>x.gameObject.scene==stageGeometryScene),"Unowned network scene objects before Moon activation");
  // Original server transport activates scene identities before spawning them. This
  // runs Awake/Generate on the serialized inactive Toggle, without choosing batteries.
  r.moon.sceneNetworkObjects=sceneObjects.Length;Check(NetworkServer.SpawnObjects(),"Original Moon network scene activation failed");
  var toggle=moonRoots.SelectMany(x=>x.GetComponentsInChildren<SceneObjectToggleGroup>(true)).Single();
  var toggleObjects=(GameObject[])typeof(SceneObjectToggleGroup).GetField("allToggleableObjects",System.Reflection.BindingFlags.NonPublic|System.Reflection.BindingFlags.Instance).GetValue(toggle);
  r.moon.toggleInitialized=toggleObjects!=null&&toggleObjects.Length==toggle.toggleGroups.Sum(x=>x.objects.Length);Check(r.moon.toggleInitialized,"Original Moon toggle Awake/Generate missing");Call(toggle,"ApplyActivations");
  moonBatteries=MoonBatteryMissionController.instance;moonEscape=moonRoots.SelectMany(x=>x.GetComponentsInChildren<EscapeSequenceController>(true)).Single();moonEncounter=moonRoots.SelectMany(x=>x.GetComponentsInChildren<EntityStateMachine>(true)).Single(x=>x.customName=="MissionController");
  Check(moonBatteries&&moonBatteries.numRequiredBatteries==4&&moonEscape&&moonEncounter,"Original Moon mission context missing");
  r.moon.loaded=true;r.moon.authority=NetworkServer.active&&worldPlayer.hasEffectiveAuthority;ObserveMoonMission();Save();
  }catch(Exception e){r.moon.error=e.ToString();if(string.IsNullOrEmpty(r.firstFailure)){r.firstFailure=e.GetBaseException().Message;r.firstFailurePhase=r.phase;}Save();throw;}
 }
 IEnumerator PrepareMoonWorld(){
  r.phase="moon-mission-context";Save();
  Check(moonBatteries&&moonEncounter&&moonEscape,"Recovered Moon mission did not activate");
  yield return null;ObserveMoonMission();
  Check(ClassicStageInfo.instance==moonStageInfo&&moonStageInfo.monsterSelection!=null&&moonStageInfo.monsterSelection.Count>0,"Original Moon stage population did not initialize");
  var selection=moonStageInfo.monsterSelection;var cards=Enumerable.Range(0,selection.Count).Select(i=>selection.GetChoice(i)).ToArray();
  r.moon.monsterCards=cards.Length;r.moon.monsterCardNames=cards.Select(x=>x.value.GetSpawnCard().name).ToArray();r.moon.monsterCardWeights=cards.Select(x=>x.weight).ToArray();
  Check(cards.All(x=>objectiveCards.Contains(x.value.GetSpawnCard() as CharacterSpawnCard)),"Original Moon selected an unsupported population card: "+string.Join(",",r.moon.monsterCardNames));
  if(moonStageInfo.interactableCategories&&moonStageInfo.interactableCategories!=priorMoonInteractables)objectiveResources.Add(moonStageInfo.interactableCategories);
  r.moon.populationReady=true;Save();
 }
 void BindMoonPopulation(){
  moonStageInfo=SceneInfo.instance.GetComponent<ClassicStageInfo>();Check(moonStageInfo&&ClassicStageInfo.instance==moonStageInfo,"Original Moon ClassicStageInfo missing");
  var field=typeof(ClassicStageInfo).GetField("monsterDccsPool",System.Reflection.BindingFlags.NonPublic|System.Reflection.BindingFlags.Instance);Check(field!=null,"Original Moon population field missing");var original=(DccsPool)field.GetValue(moonStageInfo);Check(original&&original.poolCategories!=null,"Original Moon population pool missing");
  var pool=Instantiate(original);pool.name=original.name;objectiveResources.Add(pool);var decks=new Dictionary<DirectorCardCategorySelection,DirectorCardCategorySelection>();var unmapped=new HashSet<string>();
  foreach(var category in pool.poolCategories){
   var entries=(category.alwaysIncluded??new DccsPool.PoolEntry[0]).Concat(category.includedIfConditionsMet??new DccsPool.ConditionalPoolEntry[0]).Concat(category.includedIfNoConditionsMet??new DccsPool.PoolEntry[0]);
   foreach(var entry in entries){
    Check(entry.dccs,"Original Moon pool entry is missing its selection");DirectorCardCategorySelection deck;
    if(!decks.TryGetValue(entry.dccs,out deck)){
     deck=Instantiate(entry.dccs);deck.name=entry.dccs.name;objectiveResources.Add(deck);decks.Add(entry.dccs,deck);
     foreach(var group in deck.categories)foreach(var card in group.cards){var source=card.GetSpawnCard() as CharacterSpawnCard;Check(source,"Original Moon population has an unsupported spawn-card type");var owned=objectiveCards.SingleOrDefault(x=>x.name==source.name);if(owned)card.spawnCard=owned;else unmapped.Add(source.name);}
    }
    entry.dccs=deck;
   }
  }
  // Pool/category weights and original availability/expansion checks remain intact.
  // Only known actor contracts bind to owned Android templates; selected unknowns fail.
  field.SetValue(moonStageInfo,pool);priorMoonInteractables=moonStageInfo.interactableCategories;r.moon.unmappedPoolCards=unmapped.OrderBy(x=>x).ToArray();
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
   director.onSpawnedServer.AddListener(QueueObjectiveDirectorActor);
   if(!director.monsterCards)continue;var deck=Instantiate(director.monsterCards);objectiveResources.Add(deck);
   foreach(var category in deck.categories)foreach(var card in category.cards){var source=card.spawnCard as CharacterSpawnCard;if(!source)continue;var owned=objectiveCards.SingleOrDefault(x=>x.name==source.name);Check(owned,"Original Moon director card has no compatible template: "+source.name);card.spawnCard=owned;}
   director.monsterCards=deck;
  }
 }
 void ObserveMoonMission(){
  if(r.moon==null||!moonEncounter)return;var report=r.moon;report.seconds=r.nova==null?0:r.nova.seconds;
  var state=moonEncounter.state==null?"uninitialized":moonEncounter.state.GetType().FullName;if(report.state!=state){report.state=state;report.transitions.Add(state);Save();}
  report.required=moonBatteries.numRequiredBatteries;report.charged=moonBatteries.numChargedBatteries;
  var batteries=moonRoots.SelectMany(x=>x.GetComponentsInChildren<HoldoutZoneController>(true)).Where(x=>x.gameObject.activeInHierarchy&&x.GetComponent<PurchaseInteraction>()).ToArray();report.batteries=batteries.Length;
  report.batteryStates=batteries.Select(x=>x.name+"|"+x.GetComponent<EntityStateMachine>().state+"|"+x.charge.ToString("F3")).ToArray();
  report.elevatorStates=moonRoots.SelectMany(x=>x.GetComponentsInChildren<EntityStateMachine>(true)).Where(x=>x.gameObject.name=="MoonElevator").Select(x=>x.state==null?"uninitialized":x.state.GetType().FullName).ToArray();
  ObserveMoonPillarMarkers(batteries);
  var encounters=moonRoots.SelectMany(x=>x.GetComponentsInChildren<ScriptedCombatEncounter>(true)).ToArray();report.encounters=encounters.Length;report.spawnedEncounters=encounters.Count(x=>x.hasSpawnedServer);report.escapeState=moonEscape.mainStateMachine.state==null?"uninitialized":moonEscape.mainStateMachine.state.GetType().FullName;
  report.livingEncounterMembers=encounters.Where(x=>x.combatSquad).Sum(x=>x.combatSquad.memberCount);report.extractionZones=UnityEngine.Object.FindObjectsOfType<EscapeSequenceExtractionZone>().Length;report.gameOver=Run.instance&&Run.instance.isGameOverServer;
  ObserveMoonEscape();
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
   else{
    // Keep genuine interaction aim in its source range. During travel, use the
    // established visible-hurtbox targeting rather than aiming at a distant goal
    // while a contact attacker follows the player down the bridge.
    bool canInteract=worldDriver.currentInteractable==battery.gameObject&&Vector3.Distance(position,battery.transform.position)<=interactor.maxInteractionDistance;
    if(!canInteract&&MoonCombatInput(player,bridge,elapsed)){r.world.travelDefenseFrames++;r.world.travelDefenseTarget=battery.name;SetMoonInputObjective("Defend while approaching original battery",battery.transform.position);}
    else{AimMoonInteraction(player,bridge,battery.gameObject,elapsed);SetMoonInputObjective("Activate original battery",battery.transform.position);}
   }
   return true;
  }
  if(moonEscape.mainStateMachine.state is EscapeSequenceController.EscapeSequenceMainState){
   // Commencement uses its dropship states, not the older extraction-zone type.
   // Travel through original arena exit MapZones, then enter the actual holdout.
   var ship=moonRoots.Single(x=>x.name=="Moon2DropshipZone");var holdout=ship.GetComponentInChildren<HoldoutZoneController>(true);
   var exit=moonRoots.SelectMany(x=>x.GetComponentsInChildren<MapZone>(true)).Where(x=>x.isActiveAndEnabled&&x.gameObject.name.StartsWith("MoonExitArenaOrb",StringComparison.Ordinal)).OrderBy(x=>Vector3.Distance(x.transform.position,position)).FirstOrDefault();
   if(position.y>r.moon.dropshipPosition.y+100&&exit){var collider=exit.GetComponent<Collider>();var target=collider?collider.bounds.center:exit.transform.position;NavigateWorldInput(player,bridge,target,.5f,exit.name,elapsed);SetMoonInputObjective("Enter original arena escape orb",target);}
   else if(holdout){NavigateWorldInput(player,bridge,holdout.transform.position,holdout.isActiveAndEnabled?Mathf.Max(1,holdout.currentRadius*.2f):1,ship.name,elapsed);SetMoonInputObjective(holdout.isActiveAndEnabled?"Charge original dropship":"Reach original dropship trigger",holdout.transform.position);}
   else{bridge.movement=Vector2.zero;SetMoonInputObjective("Wait for source dropship activation",position);}
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
 bool MoonCombatInput(CharacterBody player,NovaInputBridge bridge,float elapsed){
  var position=player.characterMotor.Motor.TransientPosition;var origin=player.inputBank.aimOrigin;
  var living=directorActors.Where(x=>x.body&&x.body.healthComponent.alive).ToArray();var actors=living.Where(x=>InsideSourceStageBounds(DirectorPhysicsPosition(x.body))).ToArray();
  var targets=actors.Select(x=>{bool visible;var point=WorldCombatAimPoint(x.body,origin,out visible);return new{actor=x,point,visible,distance=Vector3.Distance(point,origin)};}).ToArray();
  r.world.combatCandidates=living.Length;r.world.combatBoundsRejected=living.Length-actors.Length;r.world.combatVisibleCandidates=targets.Count(x=>x.visible);r.world.combatOccludedCandidates=targets.Length-r.world.combatVisibleCandidates;
  var target=targets.OrderBy(x=>!x.visible).ThenBy(x=>x.distance).FirstOrDefault();r.world.combatLineOfSight=target!=null&&target.visible;r.world.combatTarget=target!=null?target.actor.body.name:"";
  if(target==null)return false;
  r.world.combatTargetDistance=target.distance;r.world.combatAimOrigin=origin;r.world.combatAimTarget=target.point;r.world.combatTargetPhysicsPosition=DirectorPhysicsPosition(target.actor.body);r.world.combatTargetCorePosition=target.actor.body.corePosition;
  var nearest=actors.OrderBy(x=>Vector3.Distance(position,DirectorPhysicsPosition(x.body))).First();var away=position-DirectorPhysicsPosition(nearest.body);float distance=away.magnitude;away.y=0;r.world.combatThreatDistance=distance;
  if(distance<16&&player.characterMotor.isGrounded){
   SelectCombatMotion(player,bridge,new Vector2(away.x,away.z).normalized,actors,true);bridge.diagnosticSprint=true;
   if(bridge.movement.sqrMagnitude>.01f){bridge.DiagnosticJump(elapsed%1.8f<.25f);bridge.diagnosticUtility=player.skillLocator.utility.CanExecute();}
  }
  if(!target.visible)return false;
  var aim=target.point-origin;bridge.diagnosticAim=aim.normalized;bridge.aim=new Vector2(aim.x,aim.z).normalized;bridge.diagnosticPrimary=true;bridge.diagnosticSecondary=elapsed%4<.2f;bridge.diagnosticSpecial=elapsed%10<.2f;return true;
 }
 void CleanupMoonMission(){
  StopMoonTimers();
  CleanupMoonPillarPresentation();
  if(moonRoots!=null)foreach(var root in moonRoots)if(root)root.SetActive(false);
  CleanupMoonTimers();
  moonEncounter=null;moonBatteries=null;moonEscape=null;moonStageInfo=null;priorMoonInteractables=null;moonRoots=null;if(r.moon!=null)r.moon.cleaned=true;
 }
}
