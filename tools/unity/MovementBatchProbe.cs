using System;
using System.Collections;
using System.IO;
using System.Reflection;
using RoR2;
using KinematicCharacterController;
using UnityEngine;
using UnityEngine.Networking;

// Each experiment runs in a fresh process. Inactive roots prevent automatic startup; selected lifecycle calls are explicit.
public sealed class MovementBatchProbe : MonoBehaviour {
 [Serializable] public class Result {public string attempt,id,phase,error,artifactAsset,jumpBoostAsset,jumpStrikeAsset,bodyAsset,masterAsset,lunarPrimaryAsset,lunarSecondaryAsset,lunarUtilityAsset,lunarSpecialAsset,batteryAsset,glassAsset,voidEquipmentAsset,potionAsset;public int pid;public bool success,cleanup;public float x,y,z,gravity,peak,sourceGravity,maxHealth,moveSpeed,damage,jumpPower,level;public int assertions,jumpEvents,awakeEvents,inventoryEvents,statsEvents,skillCount;public uint bodyId,masterId;}
 Result r;GameObject host,obstacle,eventHost,artifactHost;bool ownsServer;ArtifactDef[] priorArtifacts;ArtifactDef priorFallArtifact;AssetBundle artifactBundle;RunArtifactManager artifactManager;
 void Check(bool value,string message){r.assertions++;if(!value)throw new Exception(message);}
 static void Call(object obj,string method,params object[] args){obj.GetType().GetMethod(method,BindingFlags.NonPublic|BindingFlags.Instance).Invoke(obj,args);}
 void Save(){File.WriteAllText(System.IO.Path.Combine(Application.persistentDataPath,"movement-batch-"+r.id+".json"),JsonUtility.ToJson(r,true));}
 [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)] static void Init(){if(Resources.Load<TextAsset>("MovementBatchProbe"))new GameObject("Isolated movement batch").AddComponent<MovementBatchProbe>();}
 IEnumerator Start(){
  yield return new WaitForSeconds(8);
  var path=System.IO.Path.Combine(Application.persistentDataPath,"movement-batch-selection.json");if(!File.Exists(path))yield break;
  r=JsonUtility.FromJson<Result>(File.ReadAllText(path));var config=JsonUtility.FromJson<Result>(Resources.Load<TextAsset>("MovementBatchProbe").text);if(r.attempt!=config.attempt)yield break;
#if UNITY_ANDROID && !UNITY_EDITOR
  using(var process=new AndroidJavaClass("android.os.Process"))r.pid=process.CallStatic<int>("myPid");
#endif
  r.phase="started";Save();
  try{
   switch(r.id){case "team-manager-context":TeamContextProbe();break;case "run-singleton-context":RunContextProbe();break;case "body-motor-awake":case "body-skill-awake":case "body-team-context":case "body-original-stats":case "body-adoption-content":case "body-inventory-adoption":case "body-network-state":case "body-network-spawn":case "master-network-spawn":case "body-master-id":case "body-buff-storage":case "body-awake":case "body-registration":case "master-awake":BodyLifecycle();break;case "state-jump-items":case "state-jump-inventory":case "state-jump-event":case "state-jump-input":LandingContext();break;case "gravity-rules":GravityRules();break;case "gravity-source-jump":case "state-ground-motion":case "state-ground-reverse":case "state-ground-wall":case "gravity-fall":case "gravity-jump-land":case "state-input":case "state-motion":LandingContext();break;case "buttons":Buttons();break;case "input":Input();break;case "motor-output":MotorOutput();break;case "motor-acceleration":MotorAcceleration();break;case "global-lifecycle":case "artifact-catalog":case "artifact-manager":case "landing-context":LandingContext();break;case "integrated-free":case "integrated-wall":case "integrated-jump":case "integrated-land":Integrated();break;default:throw new Exception("Unknown experiment");}
   r.success=true;
  }catch(Exception e){r.error=e.ToString();}
  finally{try{CleanupLanding();}catch(Exception e){r.error+=" Cleanup: "+e;r.success=false;}if(obstacle)Destroy(obstacle);if(host)Destroy(host);if(ownsServer)NetworkServer.Shutdown();r.cleanup=!ownsServer||!NetworkServer.active;r.success&=r.cleanup;r.phase="complete";Save();}
 }
 void Buttons(){
  var b=new InputBankTest.ButtonState();Check(!b.justPressed&&!b.justReleased,"Initial edge");
  b.PushState(true);Check(b.justPressed&&!b.justReleased,"Press edge");b.hasPressBeenClaimed=true;
  b.PushState(true);Check(!b.justPressed&&b.down&&b.hasPressBeenClaimed,"Hold/claim");
  b.PushState(false);Check(b.justReleased&&!b.hasPressBeenClaimed,"Release/claim reset");b.PushState(false);Check(!b.justReleased,"Repeated release");
  b.PushState(true);Check(b.justPressed,"Second press");
 }
 InputBankTest InactiveInput(){host=new GameObject("Inactive input fixture");host.SetActive(false);return host.AddComponent<InputBankTest>();}
 void Input(){
  var bank=InactiveInput();Check(!host.activeInHierarchy,"Body lifecycle unexpectedly active");
  bank.SetRawMoveStates(new Vector2(.8f,0));Check(!bank.rawMoveRight.down,"Press threshold");
  bank.SetRawMoveStates(new Vector2(1,0));Check(bank.rawMoveRight.justPressed,"Right press");
  bank.SetRawMoveStates(new Vector2(.2f,0));Check(bank.rawMoveRight.down&&!bank.rawMoveRight.justPressed,"Hysteresis hold");
  bank.SetRawMoveStates(new Vector2(.05f,0));Check(bank.rawMoveRight.justReleased,"Hysteresis release");
  bank.SetRawMoveStates(new Vector2(-1,-1));Check(bank.rawMoveLeft.justPressed&&bank.rawMoveDown.justPressed&&!bank.rawMoveUp.down,"Opposite axes");
  bank.aimDirection=new Vector3(3,0,4);Check(Vector3.Distance(bank.aimDirection,new Vector3(.6f,0,.8f))<.00001f,"Aim normalization");
  bank.aimDirection=Vector3.zero;Check(bank.aimDirection==host.transform.forward,"Zero aim fallback");
  Check(!bank.CheckAnyButtonDown(),"Empty button set");bank.jump.PushState(true);Check(bank.CheckAnyButtonDown(),"Jump aggregation");
 }
 CharacterMotor InactiveMotor(){
  host=new GameObject("Inactive motor fixture");host.SetActive(false);host.AddComponent<CapsuleCollider>();return host.AddComponent<CharacterMotor>();
 }
 void MotorOutput(){
  var motor=InactiveMotor();motor.velocity=new Vector3(2,3,-4);var v=Vector3.zero;motor.UpdateVelocity(ref v,.02f);
  Check(v==motor.velocity,"Velocity callback changed value");var q=Quaternion.Euler(10,20,30);motor.UpdateRotation(ref q,.02f);Check(q==Quaternion.identity,"Motor rotation callback");
  Check(!host.activeInHierarchy,"Body lifecycle active");r.x=v.x;r.y=v.y;r.z=v.z;
 }
 void MotorAcceleration(){
  Check(!NetworkServer.active&&!NetworkClient.active,"Existing network session");
  host=new GameObject("Owned motor identity");var identity=host.AddComponent<NetworkIdentity>();
  Check(NetworkServer.Listen("127.0.0.1",0),"Local listen failed");ownsServer=true;NetworkServer.Spawn(host);Check(identity.isServer&&identity.netId.Value!=0,"Spawn failed");
  host.SetActive(false);host.AddComponent<CapsuleCollider>();var motor=host.AddComponent<CharacterMotor>();var kinematic=host.AddComponent<KinematicCharacterMotor>();
  Call(motor,"Awake");motor.SetupCharacterMotor(kinematic);Call(motor,"UpdateAuthority");Check(motor.hasEffectiveAuthority&&Util.HasEffectiveAuthority(identity),"Original authority failed");
  var body=host.GetComponent<CharacterBody>();
  // Explicit diagnostic stat inputs; this does not exercise RecalculateStats or body startup.
  typeof(CharacterBody).GetProperty("moveSpeed").SetValue(body,7f);typeof(CharacterBody).GetProperty("acceleration").SetValue(body,10f);
  motor.airControl=1;motor.moveDirection=Vector3.right;motor.velocity=Vector3.zero;
  Call(motor,"PreMove",.1f);Check(Mathf.Abs(motor.velocity.x-1)<.0001f,"First acceleration step");
  for(int i=0;i<9;i++)Call(motor,"PreMove",.1f);Check(Mathf.Abs(motor.velocity.x-7)<.0001f,"Speed cap");r.x=motor.velocity.x;
  motor.moveDirection=Vector3.zero;for(int i=0;i<10;i++)Call(motor,"PreMove",.1f);Check(motor.velocity.sqrMagnitude<.000001f,"Braking");
  Check(!host.activeInHierarchy&&host.transform.position==Vector3.zero,"Unexpected activation/translation");
  NetworkServer.UnSpawn(host);
 }
 void Integrated(){
  Check(!NetworkServer.active&&!NetworkClient.active,"Existing session");host=new GameObject("Original integrated motor");host.layer=30;var identity=host.AddComponent<NetworkIdentity>();
  Check(NetworkServer.Listen("127.0.0.1",0),"Local listen failed");ownsServer=true;NetworkServer.Spawn(host);Check(identity.isServer&&identity.netId.Value!=0,"Spawn failed");
  host.SetActive(false);host.AddComponent<CapsuleCollider>();var motor=host.AddComponent<CharacterMotor>();var k=host.AddComponent<KinematicCharacterMotor>();
  Call(motor,"Awake");Call(k,"Awake");motor.SetupCharacterMotor(k);Call(motor,"UpdateAuthority");Check(motor.hasEffectiveAuthority,"Original authority failed");
  k.SetCapsuleDimensions(.5f,2,1);k.CollidableLayers=1<<30;k.StableGroundLayers=1<<30;k.InteractiveRigidbodyHandling=false;k.SetGroundSolvingActivation(false);k.SetPosition(new Vector3(0,10,0));
  var body=host.GetComponent<CharacterBody>();typeof(CharacterBody).GetProperty("moveSpeed").SetValue(body,7f);typeof(CharacterBody).GetProperty("acceleration").SetValue(body,10f);typeof(CharacterBody).GetProperty("jumpPower").SetValue(body,5f);
  if(r.id=="landing-context"||r.id.StartsWith("gravity-")||r.id.StartsWith("state-")){typeof(CharacterBody).GetProperty("characterMotor").SetValue(body,motor);typeof(CharacterBody).GetField("transform",BindingFlags.NonPublic|BindingFlags.Instance).SetValue(body,host.transform);}
  motor.airControl=1;motor.moveDirection=Vector3.right;motor.velocity=Vector3.zero;
  if(r.id.StartsWith("gravity-")||r.id.StartsWith("state-")){Additional(motor,k,body);NetworkServer.UnSpawn(host);return;}
  if(r.id=="integrated-wall"||(r.id=="integrated-land"||r.id=="landing-context")){
   obstacle=new GameObject("Owned integrated collision fixture");obstacle.layer=30;var box=obstacle.AddComponent<BoxCollider>();
   if(r.id=="integrated-wall"){obstacle.transform.position=new Vector3(2,11,0);box.size=new Vector3(1,10,20);motor.disableAirControlUntilCollision=true;motor.velocity=Vector3.right*7;}
   else{obstacle.transform.position=new Vector3(0,9.5f,0);box.size=new Vector3(20,1,20);k.SetPosition(new Vector3(0,10.2f,0));k.SetGroundSolvingActivation(true);motor.moveDirection=Vector3.zero;motor.velocity=Vector3.down;}
   Physics.SyncTransforms();
  }
  if(r.id=="integrated-jump"){motor.Jump(1,1);Check(motor.velocity==new Vector3(7,5,0),"Original Jump impulse mismatch");}
  r.phase="original-motor-solver";Save();
  Step(k,r.id=="integrated-jump"?25:50);r.x=k.TransientPosition.x;r.y=k.TransientPosition.y;r.z=k.TransientPosition.z;
  if(r.id=="integrated-free"){
   Check(Mathf.Abs(r.x-4.62f)<.01f,"Integrated acceleration displacement");Check(Mathf.Abs(motor.velocity.x-7)<.001f,"Velocity cap");motor.moveDirection=Vector3.zero;Step(k,50);Check(motor.velocity.sqrMagnitude<.000001f,"Integrated braking");
  }else if(r.id=="integrated-wall"){Check(r.x>.9f&&r.x<1.01f,"Original motor wall position outside expected boundary");Check(!motor.disableAirControlUntilCollision,"Original movement callback not observed");}
  else if(r.id=="integrated-jump")Check(Mathf.Abs(r.x-3.5f)<.01f&&Mathf.Abs(r.y-12.5f)<.01f,"Jump velocity integration");
  else Check(k.GroundingStatus.IsStableOnGround,"Original landing not stable");
  Check(!host.activeInHierarchy,"Unexpected body lifecycle");NetworkServer.UnSpawn(host);
 }
 static void Step(KinematicCharacterMotor k,int ticks){for(int i=0;i<ticks;i++){k.UpdatePhase1(.02f,true);k.UpdatePhase2(.02f,true);k.SetPositionAndRotation(k.TransientPosition,k.TransientRotation);}}

 static void StaticCall(Type type,string name,params object[] args){type.GetMethod(name,BindingFlags.Static|BindingFlags.NonPublic).Invoke(null,args);}
 void LandingContext(){
  Check(!GlobalEventManager.instance&&!RunArtifactManager.instance,"Existing game manager context");
  if(r.id=="global-lifecycle"||r.id=="landing-context"||r.id.StartsWith("gravity-")||r.id.StartsWith("state-")){
   eventHost=new GameObject("Owned event context");eventHost.SetActive(false);var manager=eventHost.AddComponent<GlobalEventManager>();Call(manager,"OnEnable");Check(GlobalEventManager.instance==manager,"Original event singleton assignment failed");
   if(r.id=="global-lifecycle"){Call(manager,"OnDisable");Check(!GlobalEventManager.instance,"Original event singleton release failed");return;}
  }
  var cfg=JsonUtility.FromJson<Result>(Resources.Load<TextAsset>("MovementBatchProbe").text);
  artifactBundle=AssetBundle.LoadFromFile(System.IO.Path.Combine(Application.persistentDataPath,"payload","commando-prefab-lab"));Check(artifactBundle,"Artifact bundle missing");
  var artifact=artifactBundle.LoadAsset<ArtifactDef>(cfg.artifactAsset);Check(artifact&&artifact.cachedName=="WeakAssKnees"&&artifact.nameToken=="ARTIFACT_WEAKASSKNEES_NAME","Wrong recovered artifact");
  Check(artifact.unlockableDef&&artifact.smallIconSelectedSprite&&artifact.smallIconDeselectedSprite&&artifact.pickupModelPrefab,"Artifact closure incomplete");
  var defs=typeof(ArtifactCatalog).GetField("artifactDefs",BindingFlags.NonPublic|BindingFlags.Static);priorArtifacts=(ArtifactDef[])defs.GetValue(null);priorFallArtifact=RoR2Content.Artifacts.weakAssKneesArtifactDef;Check(priorArtifacts.Length==0,"Existing artifact catalog; refusing replacement");
  StaticCall(typeof(ArtifactCatalog),"SetArtifactDefs",new object[]{new[]{artifact}});Check(ArtifactCatalog.artifactCount==1&&ArtifactCatalog.GetArtifactDef(artifact.artifactIndex)==artifact,"Original catalog identity failed");
  if(r.id=="artifact-catalog")return;
  StaticCall(typeof(RunArtifactManager),"Init");artifactHost=new GameObject("Inactive artifact context");artifactHost.SetActive(false);artifactManager=artifactHost.AddComponent<RunArtifactManager>();
  Call(artifactManager,"Awake");Call(artifactManager,"OnEnable");Check(RunArtifactManager.instance==artifactManager&&!artifactManager.IsArtifactEnabled(artifact),"Original artifact manager disabled-state mismatch");
  Check(!artifactHost.activeInHierarchy,"Run lifecycle unexpectedly active");
  if(r.id=="artifact-manager")return;
  priorFallArtifact=RoR2Content.Artifacts.weakAssKneesArtifactDef;Check(!priorFallArtifact,"Existing fall artifact binding");RoR2Content.Artifacts.WeakAssKnees=artifact;
  Integrated();
 }
 void CleanupLanding(){
  if(artifactManager){Call(artifactManager,"OnDisable");Call(artifactManager,"OnDestroy");}
  if(artifactHost)Destroy(artifactHost);
  if(eventHost){Call(eventHost.GetComponent<GlobalEventManager>(),"OnDisable");Destroy(eventHost);}
  if(priorArtifacts!=null){RoR2Content.Artifacts.WeakAssKnees=priorFallArtifact;StaticCall(typeof(ArtifactCatalog),"SetArtifactDefs",new object[]{priorArtifacts});StaticCall(typeof(RunArtifactManager),"Init");}
  if(artifactBundle)artifactBundle.Unload(true);
 }

 void GravityRules(){
  var g=new CharacterGravityParameters();Check(g.CheckShouldUseGravity(),"Default gravity");g.channeledAntiGravityGranterCount=1;Check(!g.CheckShouldUseGravity(),"Channeled antigravity");g.antiGravityNeutralizerCount=1;Check(g.CheckShouldUseGravity(),"Neutralizer precedence");g.environmentalAntiGravityGranterCount=1;Check(!g.CheckShouldUseGravity(),"Environmental precedence");
 }
 void Additional(CharacterMotor motor,KinematicCharacterMotor k,CharacterBody body){
  if(r.id.StartsWith("state-jump-")){JumpInputContext(motor,k,body);return;}
  if(r.id.StartsWith("state-ground-")){GroundedState(motor,k);return;}
  if(r.id.StartsWith("gravity-")){
   var savedGravity=Physics.gravity;try{
   if(r.id=="gravity-source-jump"){var cfg=JsonUtility.FromJson<Result>(Resources.Load<TextAsset>("MovementBatchProbe").text);Check(cfg.sourceGravity<0,"Missing measured source gravity");Physics.gravity=new Vector3(0,cfg.sourceGravity,0);}
   motor.gravityParameters=new CharacterGravityParameters{environmentalAntiGravityGranterCount=1};Check(!motor.useGravity,"Antigravity setter");motor.gravityParameters=new CharacterGravityParameters();Check(motor.useGravity,"Gravity setter did not enable original gravity");r.gravity=Physics.gravity.y;Check(r.gravity<0,"Expected downward gravity");motor.moveDirection=Vector3.zero;
   if(r.id=="gravity-fall"){
    Step(k,25);r.y=k.TransientPosition.y;Check(Mathf.Abs(motor.velocity.y-r.gravity*.5f)<.001f,"Gravity velocity");Check(Mathf.Abs(r.y-(10+r.gravity*.02f*.02f*325))<.001f,"Gravity integration");
   }else{
    obstacle=new GameObject("Owned gravity floor");obstacle.layer=30;obstacle.transform.position=new Vector3(0,9.5f,0);obstacle.AddComponent<BoxCollider>().size=new Vector3(20,1,20);Physics.SyncTransforms();k.SetGroundSolvingActivation(true);k.SetPosition(new Vector3(0,10.2f,0));Step(k,40);Check(k.GroundingStatus.IsStableOnGround,"Initial gravity landing");
    motor.Jump(0,1);r.peak=k.TransientPosition.y;for(int i=0;i<100;i++){Step(k,1);r.peak=Mathf.Max(r.peak,k.TransientPosition.y);}r.y=k.TransientPosition.y;Check(r.peak>(r.id=="gravity-source-jump"?10.2f:10.5f),"Jump did not rise");Check(k.GroundingStatus.IsStableOnGround&&Mathf.Abs(r.y-10.01f)<.02f,"Gravity jump did not land");Check(motor.jumpCount==0,"Original landing jump reset");
   }
   }finally{Physics.gravity=savedGravity;}
   Check(Physics.gravity==savedGravity,"Gravity restoration");
  }else{
   var input=host.AddComponent<InputBankTest>();var machine=host.AddComponent<EntityStateMachine>();Call(machine,"Awake");var state=new EntityStates.GenericCharacterMain();machine.SetState(state);Check(machine.state==state&&machine.commonComponents.inputBank==input,"Original state entry or component cache");
   input.moveVector=Vector3.right;input.aimDirection=new Vector3(3,0,4);
   if(r.id=="state-input"){
    input.emoteRequest=2;input.jump.PushState(true);Call(state,"GatherInputs");var flags=BindingFlags.NonPublic|BindingFlags.Instance;
    Check((Vector3)typeof(EntityStates.GenericCharacterMain).GetField("moveVector",flags).GetValue(state)==Vector3.right,"State move input");Check((bool)typeof(EntityStates.GenericCharacterMain).GetField("jumpInputReceived",flags).GetValue(state),"State jump edge");Check(input.emoteRequest==-1,"Emote consumption");input.jump.hasPressBeenClaimed=true;Call(state,"GatherInputs");Check(!(bool)typeof(EntityStates.GenericCharacterMain).GetField("jumpInputReceived",flags).GetValue(state),"Claimed jump not excluded");
   }else{
    motor.moveDirection=Vector3.zero;for(int i=0;i<50;i++){machine.ManagedFixedUpdate(.02f);Step(k,1);}r.x=k.TransientPosition.x;Check(Mathf.Abs(r.x-4.62f)<.01f,"Original state-driven displacement");input.moveVector=Vector3.zero;for(int i=0;i<50;i++){machine.ManagedFixedUpdate(.02f);Step(k,1);}Check(motor.moveDirection==Vector3.zero&&motor.velocity.sqrMagnitude<.000001f,"State-driven stop");
   }
   Call(machine,"OnDestroy");Check(machine.state==null&&motor.moveDirection==Vector3.zero,"Original state exit cleanup");
  }
  Check(!host.activeInHierarchy,"Unexpected body activation");
 }

 void GroundedState(CharacterMotor motor,KinematicCharacterMotor k){
  var savedGravity=Physics.gravity;EntityStateMachine machine=null;
  try{
   var cfg=JsonUtility.FromJson<Result>(Resources.Load<TextAsset>("MovementBatchProbe").text);Check(cfg.sourceGravity<0,"Missing source gravity");Physics.gravity=new Vector3(0,cfg.sourceGravity,0);r.gravity=Physics.gravity.y;
   motor.gravityParameters=new CharacterGravityParameters{environmentalAntiGravityGranterCount=1};motor.gravityParameters=new CharacterGravityParameters();Check(motor.useGravity,"Original gravity not active");motor.moveDirection=Vector3.zero;
   obstacle=new GameObject("Owned grounded state floor");obstacle.layer=30;obstacle.transform.position=new Vector3(0,9.5f,0);obstacle.AddComponent<BoxCollider>().size=new Vector3(40,1,40);
   if(r.id=="state-ground-wall"){var wall=new GameObject("Owned state wall");wall.transform.SetParent(obstacle.transform);wall.layer=30;wall.transform.position=new Vector3(2,11,0);wall.AddComponent<BoxCollider>().size=new Vector3(1,10,20);}
   Physics.SyncTransforms();k.SetGroundSolvingActivation(true);k.SetPosition(new Vector3(0,10.2f,0));Step(k,40);Check(k.GroundingStatus.IsStableOnGround,"State fixture failed initial landing");
   var input=host.AddComponent<InputBankTest>();machine=host.AddComponent<EntityStateMachine>();Call(machine,"Awake");var state=new EntityStates.GenericCharacterMain();machine.SetState(state);Check(machine.state==state,"Original grounded state entry");input.moveVector=Vector3.right;
   for(int i=0;i<50;i++){machine.ManagedFixedUpdate(.02f);Step(k,1);}r.x=k.TransientPosition.x;r.y=k.TransientPosition.y;
   Check(k.GroundingStatus.IsStableOnGround&&Mathf.Abs(r.y-10.01f)<.02f,"State movement lost grounding");
   if(r.id=="state-ground-wall")Check(r.x>.9f&&r.x<1.01f,"State movement crossed wall boundary");
   else Check(Mathf.Abs(r.x-4.62f)<.02f,"Grounded state acceleration displacement");
   if(r.id=="state-ground-reverse"){
    input.moveVector=Vector3.left;for(int i=0;i<100;i++){machine.ManagedFixedUpdate(.02f);Step(k,1);}r.z=k.TransientPosition.x;
    Check(r.z<r.x-3&&Mathf.Abs(motor.velocity.x+7)<.001f,"Original input reversal failed");Check(k.GroundingStatus.IsStableOnGround,"Reversal lost grounding");
   }
   input.moveVector=Vector3.zero;for(int i=0;i<50;i++){machine.ManagedFixedUpdate(.02f);Step(k,1);}Check(Mathf.Abs(motor.velocity.x)<.001f&&motor.moveDirection==Vector3.zero,"Grounded state failed to stop");Check(k.GroundingStatus.IsStableOnGround,"Stopped state lost grounding");Check(!host.activeInHierarchy,"Body unexpectedly active");
  }finally{if(machine)Call(machine,"OnDestroy");Physics.gravity=savedGravity;}
  Check(machine.state==null&&motor.moveDirection==Vector3.zero,"Grounded state exit cleanup");Check(Physics.gravity==savedGravity,"Gravity not restored");
 }

 void JumpInputContext(CharacterMotor motor,KinematicCharacterMotor k,CharacterBody body){
  if(r.id=="state-jump-event"){
   Check(body.isServer&&body.hasAuthority&&body.netId.Value!=0,"Body server identity not available");
   body.onJump+=CountJump;try{body.TriggerJumpEventGlobally();Check(r.jumpEvents==1,"Original authority jump event missing");}finally{body.onJump-=CountJump;}
   Check(!NetworkClient.active,"Unexpected client; server-only dispatch fixture");return;
  }
  var cfg=JsonUtility.FromJson<Result>(Resources.Load<TextAsset>("MovementBatchProbe").text);
  var boost=artifactBundle.LoadAsset<ItemDef>(cfg.jumpBoostAsset);var strike=artifactBundle.LoadAsset<ItemDef>(cfg.jumpStrikeAsset);
  Check(boost&&strike&&boost.name=="JumpBoost"&&strike.name=="JumpDamageStrike","Wrong recovered jump items");
  Check(boost.pickupIconSprite&&strike.pickupIconSprite&&boost.pickupModelPrefab&&strike.pickupModelPrefab,"Missing serialized item references");
  Check(ItemCatalog.itemCount==0&&ItemCatalog.tier1ItemList.Count==0&&ItemCatalog.tier2ItemList.Count==0&&ItemCatalog.tier3ItemList.Count==0&&ItemCatalog.lunarItemList.Count==0,"Existing item catalog; refuse replacement");
  var priorItems=RoR2.ContentManagement.ContentManager._itemDefs;
  var oldBoost=RoR2Content.Items.JumpBoost;var oldStrike=DLC3Content.Items.JumpDamageStrike;Inventory inventory=null;GameObject inventoryHost=null;var savedGravity=Physics.gravity;EntityStateMachine machine=null;
  try{
   RoR2.ContentManagement.ContentManager._itemDefs=new ItemDef[0];
   StaticCall(typeof(ItemCatalog),"SetItemDefs",new object[]{new[]{boost,strike}});
   Check(ItemCatalog.itemCount==2&&boost.itemIndex!=strike.itemIndex&&ItemCatalog.GetItemDef(boost.itemIndex)==boost&&ItemCatalog.GetItemDef(strike.itemIndex)==strike,"Original item catalog identity");
   Check(ItemCatalog.FindItemIndex("JumpBoost")==boost.itemIndex&&ItemCatalog.FindItemIndex("JumpDamageStrike")==strike.itemIndex,"Original item name lookup");
   if(r.id!="state-jump-items"){
    inventoryHost=new GameObject("Inactive original inventory");inventoryHost.SetActive(false);inventoryHost.AddComponent<NetworkIdentity>();inventory=inventoryHost.AddComponent<Inventory>();Call(inventory,"Awake");
    Check(inventory.GetItemCountEffective(boost)==0&&inventory.GetItemCountEffective(strike)==0,"Empty original inventory counts");
    Check(inventory.GetItemCountPermanent(boost)==0&&inventory.GetItemCountPermanent(strike)==0,"Empty permanent inventory counts");
    var stacks=typeof(Inventory).GetField("effectiveItemStacks",BindingFlags.Instance|BindingFlags.NonPublic|BindingFlags.Public);
    Check(((ItemCollection)stacks.GetValue(inventory)).isValid,"Original pooled item storage invalid");
    if(r.id=="state-jump-input"){
     Check(!oldBoost&&!oldStrike,"Existing original item bindings");RoR2Content.Items.JumpBoost=boost;DLC3Content.Items.JumpDamageStrike=strike;
     typeof(CharacterBody).GetProperty("inventory").SetValue(body,inventory);typeof(CharacterBody).GetProperty("maxJumpCount").SetValue(body,1);body.baseJumpCount=1;
     Check(body.isServer&&body.hasAuthority,"Original body authority missing");body.onJump+=CountJump;
     Check(cfg.sourceGravity<0,"Missing original gravity");Physics.gravity=new Vector3(0,cfg.sourceGravity,0);r.gravity=Physics.gravity.y;
     motor.gravityParameters=new CharacterGravityParameters{environmentalAntiGravityGranterCount=1};motor.gravityParameters=new CharacterGravityParameters();motor.moveDirection=Vector3.zero;
     obstacle=new GameObject("Owned input jump floor");obstacle.layer=30;obstacle.transform.position=new Vector3(0,9.5f,0);obstacle.AddComponent<BoxCollider>().size=new Vector3(40,1,40);Physics.SyncTransforms();k.SetGroundSolvingActivation(true);k.SetPosition(new Vector3(0,10.2f,0));Step(k,40);Check(k.GroundingStatus.IsStableOnGround,"Jump input initial grounding");
     var input=host.AddComponent<InputBankTest>();machine=host.AddComponent<EntityStateMachine>();Call(machine,"Awake");machine.SetState(new EntityStates.GenericCharacterMain());
     input.jump.PushState(true);machine.ManagedFixedUpdate(.02f);Check(motor.jumpCount==1&&motor.velocity.y>0&&r.jumpEvents==1,"Original input did not produce jump/event");
     input.jump.PushState(false);r.peak=k.TransientPosition.y;
     for(int i=0;i<100;i++){machine.ManagedFixedUpdate(.02f);Step(k,1);r.peak=Mathf.Max(r.peak,k.TransientPosition.y);}
     r.y=k.TransientPosition.y;Check(r.peak>10.2f,"Input jump did not rise");Check(k.GroundingStatus.IsStableOnGround&&Mathf.Abs(r.y-10.01f)<.02f&&motor.jumpCount==0,"Input jump did not land/reset");Check(r.jumpEvents==1,"Unexpected repeated jump events");
    }
    Call(inventory,"OnDestroy");StaticCall(typeof(Inventory),"StaticFixedUpdate");Check(!((ItemCollection)stacks.GetValue(inventory)).isValid,"Original inventory disposal failed");inventory=null;
   }
  }finally{
   try{if(machine)Call(machine,"OnDestroy");body.onJump-=CountJump;if(inventory){Call(inventory,"OnDestroy");StaticCall(typeof(Inventory),"StaticFixedUpdate");}}
   finally{Physics.gravity=savedGravity;RoR2Content.Items.JumpBoost=oldBoost;DLC3Content.Items.JumpDamageStrike=oldStrike;typeof(CharacterBody).GetProperty("inventory").SetValue(body,null);StaticCall(typeof(ItemCatalog),"SetItemDefs",new object[]{new ItemDef[0]});ItemCatalog.tier1ItemList.Clear();ItemCatalog.tier2ItemList.Clear();ItemCatalog.tier3ItemList.Clear();ItemCatalog.lunarItemList.Clear();RoR2.ContentManagement.ContentManager._itemDefs=priorItems;if(inventoryHost)Destroy(inventoryHost);}
  }
  Check(ItemCatalog.itemCount==0&&RoR2.ContentManagement.ContentManager._itemDefs==priorItems&&Physics.gravity==savedGravity,"Jump fixture restoration");Check(!host.activeInHierarchy,"Body lifecycle unexpectedly active");
 }
 void CountJump(){r.jumpEvents++;}

 void BodyLifecycle(){
  Check(!NetworkServer.active&&!NetworkClient.active,"Unexpected network session");
  if(r.id=="master-awake"||r.id=="master-network-spawn"){MasterLifecycle();return;}
  var fields=typeof(BuffCatalog).GetFields(BindingFlags.Static|BindingFlags.Public|BindingFlags.NonPublic);var previous=new System.Collections.Generic.Dictionary<FieldInfo,object>();
  foreach(var f in fields)if(f.FieldType.IsArray)previous[f]=f.GetValue(null);
  var names=(IDictionary)typeof(BuffCatalog).GetField("nameToBuffIndex",BindingFlags.NonPublic|BindingFlags.Static).GetValue(null);Check(names.Count==0,"Existing buff catalog; refuse diagnostic replacement");
  Action restoreAdoption=null;TeamComponent team=null;GenericSkill[] initializedSkills=null;CharacterMotor initializedMotor=null;
  GameObject linkedMasterHost=null;CharacterMaster linkedMaster=null;Inventory linkedInventory=null;
  CharacterBody body=null;Action<Transform> modelSubscription=null;Action<CharacterBody> awake=observed=>{if(observed==body)r.awakeEvents++;};bool registered=false;
  try{
   StaticCall(typeof(BuffCatalog),"SetBuffDefs",new object[]{new BuffDef[0]});Check(BuffCatalog.buffCount==0,"Empty diagnostic buff catalog initialization");
   var first=BuffCatalog.GetPerBuffBuffer<int>();var second=BuffCatalog.GetPerBuffBuffer<int>();Check(first.Length==0&&second.Length==0&&!ReferenceEquals(first,second),"Original buff buffer allocation");
   if(r.id!="body-buff-storage"){
    var cfg=JsonUtility.FromJson<Result>(Resources.Load<TextAsset>("MovementBatchProbe").text);artifactBundle=AssetBundle.LoadFromFile(System.IO.Path.Combine(Application.persistentDataPath,"payload","commando-prefab-lab"));Check(artifactBundle,"Body bundle missing");var prefab=artifactBundle.LoadAsset<GameObject>(cfg.bodyAsset);Check(prefab&&!prefab.activeSelf,"Recovered body root not isolated");
    if(r.id=="body-adoption-content"||r.id=="body-inventory-adoption"||r.id=="body-original-stats"){restoreAdoption=PrepareAdoption(cfg);if(r.id=="body-adoption-content")return;}
    host=Instantiate(prefab);body=host.GetComponent<CharacterBody>();Check(body&&!host.activeInHierarchy,"Recovered body missing or active");foreach(var component in host.GetComponentsInChildren<Component>(true))Check(component,"Missing recovered body script");
    CharacterBody.onBodyAwakeGlobal+=awake;try{Call(body,"Awake");}finally{CharacterBody.onBodyAwakeGlobal-=awake;}
    modelSubscription=(Action<Transform>)Delegate.CreateDelegate(typeof(Action<Transform>),body,typeof(CharacterBody).GetMethod("OnModelChanged",BindingFlags.NonPublic|BindingFlags.Instance));
    Check(r.awakeEvents==1,"Original body awake event");Check(body.networkIdentity==host.GetComponent<NetworkIdentity>()&&body.characterMotor==host.GetComponent<CharacterMotor>()&&body.inputBank==host.GetComponent<InputBankTest>(),"Original body component caches");
    Check(body.healthComponent==host.GetComponent<HealthComponent>()&&body.skillLocator==host.GetComponent<SkillLocator>(),"Original health/skill references");Check(body.modelLocator&&body.modelLocator.modelTransform&&body.hurtBoxGroup&&body.mainHurtBox&&body.coreTransform,"Recovered model/hurtbox/core linkage");
    Check(body.hurtBoxGroup==body.modelLocator.modelTransform.GetComponent<HurtBoxGroup>()&&body.mainHurtBox==body.hurtBoxGroup.mainHurtBox,"Original hurtbox identity");Check(Mathf.Abs(body.radius-host.GetComponent<CapsuleCollider>().radius)<.0001f,"Original capsule radius cache");
    var buffs=(int[])typeof(CharacterBody).GetField("buffs",BindingFlags.NonPublic|BindingFlags.Instance).GetValue(body);Check(buffs!=null&&buffs.Length==0,"Original body buff storage");
    var network=host.GetComponent<NetworkStateMachine>();Check(network,"Recovered network state-machine missing");var machines=(EntityStateMachine[])typeof(NetworkStateMachine).GetField("stateMachines",BindingFlags.NonPublic|BindingFlags.Instance).GetValue(network);Check(machines.Length>0,"Recovered network state-machine list");foreach(var machine in machines)Check(machine&&machine.gameObject==host,"Recovered state-machine linkage");
    if(r.id=="body-motor-awake"||r.id=="body-original-stats"){initializedMotor=body.characterMotor;Call(initializedMotor,"Awake");var capsule=host.GetComponent<CapsuleCollider>();Check(initializedMotor.capsuleHeight==capsule.height&&initializedMotor.capsuleRadius==capsule.radius,"Original motor capsule cache");Check(initializedMotor.initialCapsuleHeight==capsule.height&&initializedMotor.initialCapsuleRadius==capsule.radius,"Original initial capsule dimensions");Check(Mathf.Abs(body.bestFitRadius-Mathf.Max(body.radius,capsule.height))<.0001f,"Original body effect bounds");}
    if(r.id=="body-skill-awake"){initializedSkills=host.GetComponents<GenericSkill>();InitializeSkills(body,initializedSkills);}
    if(r.id=="body-team-context"){team=body.teamComponent;Check(team,"Recovered team component missing");Call(team,"Awake");Check(team.body==body,"Original team body cache");team.teamIndex=TeamIndex.None;team.teamIndex=TeamIndex.Player;Check(TeamComponent.GetTeamMembers(TeamIndex.Player).Contains(team),"Original team membership");foreach(var hurt in body.hurtBoxGroup.hurtBoxes)Check(hurt.teamIndex==TeamIndex.Player,"Original hurtbox team propagation");Call(team,"OnDestroy");Check(!TeamComponent.GetTeamMembers(TeamIndex.Player).Contains(team),"Original team removal");team=null;}
    if(r.id=="body-network-state"){
     Call(network,"Awake");for(int i=0;i<machines.Length;i++)Check(machines[i].networkIndex==i&&machines[i].networker==network&&machines[i].networkIdentity==body.networkIdentity,"Original network state-machine binding");
    }
    if(r.id=="body-network-spawn"||r.id=="body-master-id"||r.id=="body-inventory-adoption"||r.id=="body-original-stats"){
     SpawnRecovered(host);Call(body,"UpdateAuthority");r.bodyId=body.networkIdentity.netId.Value;Check(body.hasEffectiveAuthority&&Util.HasEffectiveAuthority(body.networkIdentity),"Recovered body effective authority");
     if(r.id=="body-master-id"||r.id=="body-inventory-adoption"||r.id=="body-original-stats"){
      var masterPrefab=artifactBundle.LoadAsset<GameObject>(cfg.masterAsset);Check(masterPrefab&&!masterPrefab.activeSelf,"Recovered master not isolated");linkedMasterHost=Instantiate(masterPrefab);linkedInventory=linkedMasterHost.GetComponent<Inventory>();Call(linkedInventory,"Awake");linkedMaster=linkedMasterHost.GetComponent<CharacterMaster>();Call(linkedMaster,"Awake");SpawnRecovered(linkedMasterHost);Call(linkedMaster,"UpdateAuthority");r.masterId=linkedMaster.networkIdentity.netId.Value;
      Check(r.masterId!=r.bodyId&&linkedMaster.hasEffectiveAuthority,"Distinct recovered master identity/authority");Check(!body.inventory,"Unexpected adopted inventory before link");body.masterObject=linkedMasterHost;
      Check(body.GetMasterObjectId()==linkedMaster.networkIdentity.netId,"Original body master ID setter");Check(NetworkServer.FindLocalObject(body.GetMasterObjectId())==linkedMasterHost,"Actual server master resolution");Check(!body.inventory&&!linkedMaster.hasBody,"Unexpected inventory adoption or reciprocal link");Check(!linkedMasterHost.activeInHierarchy,"Master activation occurred");
      if(r.id=="body-inventory-adoption"||r.id=="body-original-stats"){
       r.phase="original-master-getter";Save();Action observed=()=>r.inventoryEvents++;body.onInventoryChanged+=observed;
       try{Check(body.masterObject==linkedMasterHost&&body.master==linkedMaster,"Original master getter identity");Check(body.inventory==linkedInventory&&body.isPlayerControlled,"Original inventory/player-controller adoption");Check(r.inventoryEvents==1,"Original inventory callback count");Check(body.masterObject==linkedMasterHost&&r.inventoryEvents==1,"Cached getter repeated callback");Check(!linkedMaster.hasBody,"Unexpected reciprocal link");Check(!host.GetComponent<CharacterBody.QuestVolatileBatteryBehaviorServer>(),"Empty equipment created quest behavior");}
       finally{body.onInventoryChanged-=observed;}
       if(r.id=="body-original-stats"){initializedSkills=host.GetComponents<GenericSkill>();InitializeSkills(body,initializedSkills);OriginalStats(body,cfg);}
      }
     }
    }
    if(r.id=="body-registration"){
     var count=CharacterBody.readOnlyInstancesList.Count;Call(body,"OnEnable");registered=true;Check(CharacterBody.readOnlyInstancesList.Count==count+1&&CharacterBody.readOnlyInstancesList.Contains(body),"Original body registration");Call(body,"OnDisable");registered=false;Check(CharacterBody.readOnlyInstancesList.Count==count&&!CharacterBody.readOnlyInstancesList.Contains(body),"Original body unregistration");
    }
    Check(!host.activeInHierarchy,"Broad body activation occurred");
   }
  }finally{
   if(initializedMotor)Call(initializedMotor,"OnDestroy");
   if(initializedSkills!=null)foreach(var skill in initializedSkills)Call(skill,"OnDestroy");
   if(team)Call(team,"OnDestroy");
   if(body&&body.inventory){var callback=(Action)Delegate.CreateDelegate(typeof(Action),body,typeof(CharacterBody).GetMethod("OnInventoryChanged",BindingFlags.NonPublic|BindingFlags.Instance));body.inventory.onInventoryChanged-=callback;}
   if(linkedMasterHost){NetworkServer.UnSpawn(linkedMasterHost);if(linkedMaster)Call(linkedMaster,"OnDestroy");if(linkedInventory){Call(linkedInventory,"OnDestroy");StaticCall(typeof(Inventory),"StaticFixedUpdate");}Destroy(linkedMasterHost);}
   if(host&&ownsServer){var id=host.GetComponent<NetworkIdentity>().netId;NetworkServer.UnSpawn(host);Check(!NetworkServer.FindLocalObject(id),"Body network object not removed");}
   if(registered)Call(body,"OnDisable");if(body&&body.modelLocator&&modelSubscription!=null)body.modelLocator.onModelChanged-=modelSubscription;
   foreach(var pair in previous)pair.Key.SetValue(null,pair.Value);if(restoreAdoption!=null)restoreAdoption();
  }
  foreach(var pair in previous)Check(ReferenceEquals(pair.Key.GetValue(null),pair.Value),"Buff catalog restoration");
 }
 void RestoreAdoption(ItemDef[] priorItems,FieldInfo[] fields,ItemDef[] old,EquipmentDef oldBattery){
  for(int i=0;i<fields.Length;i++)fields[i].SetValue(null,old[i]);RoR2Content.Equipment.QuestVolatileBattery=oldBattery;
  StaticCall(typeof(ItemCatalog),"SetItemDefs",new object[]{new ItemDef[0]});ItemCatalog.tier1ItemList.Clear();ItemCatalog.tier2ItemList.Clear();ItemCatalog.tier3ItemList.Clear();ItemCatalog.lunarItemList.Clear();RoR2.ContentManagement.ContentManager._itemDefs=priorItems;
  StaticCall(typeof(EquipmentCatalog),"SetEquipmentDefs",new object[]{new EquipmentDef[0]});
 }
 Action PrepareAdoption(Result cfg){
  Check(ItemCatalog.itemCount==0&&EquipmentCatalog.equipmentCount==0,"Existing catalog; refuse replacement");
  var paths=new[]{cfg.lunarPrimaryAsset,cfg.lunarSecondaryAsset,cfg.lunarUtilityAsset,cfg.lunarSpecialAsset};var names=new[]{"LunarPrimaryReplacement","LunarSecondaryReplacement","LunarUtilityReplacement","LunarSpecialReplacement"};var defs=new ItemDef[4];var fields=new FieldInfo[4];var old=new ItemDef[4];
  for(int i=0;i<4;i++){defs[i]=artifactBundle.LoadAsset<ItemDef>(paths[i]);Check(defs[i]&&defs[i].name==names[i],"Required recovered ItemDef identity "+names[i]);fields[i]=typeof(RoR2Content.Items).GetField(names[i]);old[i]=(ItemDef)fields[i].GetValue(null);Check(!old[i],"Existing item binding");}
  var battery=artifactBundle.LoadAsset<EquipmentDef>(cfg.batteryAsset);Check(battery&&battery.name=="QuestVolatileBattery","Required original EquipmentDef identity");var oldBattery=RoR2Content.Equipment.QuestVolatileBattery;Check(!oldBattery,"Existing equipment binding");var priorItems=RoR2.ContentManagement.ContentManager._itemDefs;
  Action restore=()=>RestoreAdoption(priorItems,fields,old,oldBattery);
  try{
   RoR2.ContentManagement.ContentManager._itemDefs=new ItemDef[0];StaticCall(typeof(ItemCatalog),"SetItemDefs",new object[]{defs});StaticCall(typeof(EquipmentCatalog),"SetEquipmentDefs",new object[]{new[]{battery}});
   for(int i=0;i<4;i++){Check(defs[i].itemIndex!=ItemIndex.None&&ItemCatalog.GetItemDef(defs[i].itemIndex)==defs[i]&&ItemCatalog.FindItemIndex(names[i])==defs[i].itemIndex,"Original Lunar catalog identity");fields[i].SetValue(null,defs[i]);}
   RoR2Content.Equipment.QuestVolatileBattery=battery;Check(battery.equipmentIndex!=EquipmentIndex.None&&EquipmentCatalog.GetEquipmentDef(battery.equipmentIndex)==battery,"Original battery catalog identity");Check(!EquipmentCatalog.GetEquipmentDef(EquipmentIndex.None),"Empty equipment must remain absent");Check(ItemCatalog.itemCount==4&&EquipmentCatalog.equipmentCount==1,"Diagnostic catalog size");
   return restore;
  }catch{restore();throw;}
 }
 void InitializeSkills(CharacterBody body,GenericSkill[] skills){
  Check(skills.Length>=4,"Recovered skill slots missing");r.phase="original-skill-awake";Save();
  foreach(var skill in skills){Check(skill.skillFamily&&skill.skillFamily.defaultSkillDef,"Recovered default skill missing");Call(skill,"Awake");Check(skill.characterBody==body&&skill.skillDef==skill.skillFamily.defaultSkillDef,"Original default skill assignment");Check(skill.stateMachine&&skill.stateMachine.gameObject==host,"Original skill state-machine resolution");var cooldown=(float)typeof(GenericSkill).GetField("finalRechargeInterval",BindingFlags.NonPublic|BindingFlags.Instance).GetValue(skill);Check(!float.IsNaN(cooldown)&&!float.IsInfinity(cooldown),"Invalid original cooldown");r.skillCount++;}
 }
 TeamManager CreateTeamContext(out GameObject owned){
  Check(!TeamManager.instance,"Existing team manager");owned=new GameObject("Inactive team context");owned.SetActive(false);owned.AddComponent<NetworkIdentity>();var manager=owned.AddComponent<TeamManager>();Call(manager,"OnEnable");Check(TeamManager.instance==manager,"Original team singleton assignment");Call(manager,"Start");
  for(TeamIndex index=TeamIndex.Neutral;index<TeamIndex.Count;index++)Check(manager.GetTeamExperience(index)==0&&manager.GetTeamLevel(index)==1&&manager.GetTeamNextLevelExperience(index)==20,"Original initial team level/experience");return manager;
 }
 void TeamContextProbe(){
  Check(!NetworkServer.active&&!NetworkClient.active,"Existing network session");Check(NetworkServer.Listen("127.0.0.1",0),"Team server listen");ownsServer=true;GameObject owned=null;TeamManager manager=null;
  try{manager=CreateTeamContext(out owned);manager.GiveTeamExperience(TeamIndex.Player,19);Check(manager.GetTeamLevel(TeamIndex.Player)==1,"Premature team level");manager.GiveTeamExperience(TeamIndex.Player,1);Check(manager.GetTeamExperience(TeamIndex.Player)==20&&manager.GetTeamLevel(TeamIndex.Player)==2,"Original level threshold");manager.SetTeamLevel(TeamIndex.Player,1);Check(manager.GetTeamLevel(TeamIndex.Player)==1&&manager.GetTeamExperience(TeamIndex.Player)==0,"Original level reset");}
  finally{if(manager)Call(manager,"OnDisable");if(owned)Destroy(owned);}Check(!TeamManager.instance,"Team singleton cleanup");
 }
 void RunContextProbe(){
  Check(!Run.instance,"Existing Run");var owned=new GameObject("Inactive Run singleton probe");owned.SetActive(false);var run=owned.AddComponent<Run>();
  try{Call(run,"OnEnable");Check(Run.instance==run&&!owned.activeInHierarchy,"Original Run singleton assignment");}finally{Call(run,"OnDisable");Destroy(owned);}Check(!Run.instance,"Original Run singleton cleanup");
 }
 void OriginalStats(CharacterBody body,Result cfg){
  Check(!Run.instance&&!RunArtifactManager.instance&&!TeamManager.instance,"Existing stats context");GameObject teamHost=null,runHost=null;TeamManager manager=null;Run run=null;RunArtifactManager artifacts=null;var team=body.teamComponent;bool healthAwake=false;
  var priorDefs=(ArtifactDef[])typeof(ArtifactCatalog).GetField("artifactDefs",BindingFlags.NonPublic|BindingFlags.Static).GetValue(null);var priorGlass=RoR2Content.Artifacts.glassArtifactDef;var oldVoid=DLC1Content.Equipment.EliteVoidEquipment;var oldPotion=RoR2Content.Equipment.LunarPotion;
  Check(priorDefs.Length==0&&!priorGlass&&!oldVoid&&!oldPotion,"Existing stats content bindings");
  Action<CharacterBody> observed=b=>{if(b==body)r.statsEvents++;};
  try{
   var glass=artifactBundle.LoadAsset<ArtifactDef>(cfg.glassAsset);var elite=artifactBundle.LoadAsset<EquipmentDef>(cfg.voidEquipmentAsset);var potion=artifactBundle.LoadAsset<EquipmentDef>(cfg.potionAsset);Check(glass&&elite&&potion,"Missing recovered stats definitions");
   StaticCall(typeof(EquipmentCatalog),"SetEquipmentDefs",new object[]{new[]{RoR2Content.Equipment.QuestVolatileBattery,elite,potion}});DLC1Content.Equipment.EliteVoidEquipment=elite;RoR2Content.Equipment.LunarPotion=potion;StaticCall(typeof(ArtifactCatalog),"SetArtifactDefs",new object[]{new[]{glass}});RoR2Content.Artifacts.Glass=glass;StaticCall(typeof(RunArtifactManager),"Init");
   manager=CreateTeamContext(out teamHost);Call(team,"Awake");team.teamIndex=TeamIndex.None;team.teamIndex=TeamIndex.Player;Check(team.body==body&&TeamComponent.GetTeamMembers(TeamIndex.Player).Contains(team),"Recovered player team context");
   runHost=new GameObject("Inactive stat Run context");runHost.SetActive(false);artifacts=runHost.AddComponent<RunArtifactManager>();run=runHost.GetComponent<Run>();Call(run,"OnEnable");Call(artifacts,"Awake");Call(artifacts,"OnEnable");Check(Run.instance==run&&!artifacts.IsArtifactEnabled(glass),"Original disabled Glass context");
   Call(body.healthComponent,"Awake");healthAwake=true;Check(body.healthComponent.body==body,"Original health body cache");body.onRecalculateStats+=observed;r.phase="original-recalculate-stats";Save();body.RecalculateStats();
   r.maxHealth=body.maxHealth;r.moveSpeed=body.moveSpeed;r.damage=body.damage;r.jumpPower=body.jumpPower;r.level=body.level;
   Check(r.statsEvents==1&&r.level==1,"Original stat completion/level");Check(Mathf.Abs(r.maxHealth-110)<.001f&&Mathf.Abs(r.moveSpeed-7)<.001f&&Mathf.Abs(r.damage-12)<.001f&&Mathf.Abs(r.jumpPower-15)<.001f,"Recovered Commando base stats");Check(!host.activeInHierarchy&&!runHost.activeInHierarchy,"Broad gameplay activation");
  }finally{
   body.onRecalculateStats-=observed;if(healthAwake)Call(body.healthComponent,"OnDestroy");if(team)Call(team,"OnDestroy");if(artifacts){Call(artifacts,"OnDisable");Call(artifacts,"OnDestroy");}if(run)Call(run,"OnDisable");if(runHost)Destroy(runHost);if(manager)Call(manager,"OnDisable");if(teamHost)Destroy(teamHost);
   RoR2Content.Artifacts.Glass=priorGlass;StaticCall(typeof(ArtifactCatalog),"SetArtifactDefs",new object[]{priorDefs});StaticCall(typeof(RunArtifactManager),"Init");DLC1Content.Equipment.EliteVoidEquipment=oldVoid;RoR2Content.Equipment.LunarPotion=oldPotion;
  }
 }
 void MasterLifecycle(){
  var cfg=JsonUtility.FromJson<Result>(Resources.Load<TextAsset>("MovementBatchProbe").text);artifactBundle=AssetBundle.LoadFromFile(System.IO.Path.Combine(Application.persistentDataPath,"payload","commando-prefab-lab"));Check(artifactBundle,"Master bundle missing");var prefab=artifactBundle.LoadAsset<GameObject>(cfg.masterAsset);Check(prefab&&!prefab.activeSelf,"Recovered master root not isolated");host=Instantiate(prefab);var master=host.GetComponent<CharacterMaster>();var inventory=host.GetComponent<Inventory>();Check(master&&inventory&&!host.activeInHierarchy,"Original master components missing or active");foreach(var c in host.GetComponentsInChildren<Component>(true))Check(c,"Missing recovered master script");
  bool inventoryAwake=false,masterAwake=false,registered=false;
  try{
   Call(inventory,"Awake");inventoryAwake=true;Call(master,"Awake");masterAwake=true;
   Check(master.inventory==inventory&&master.networkIdentity==host.GetComponent<NetworkIdentity>(),"Original master component caches");Check(master.playerCharacterMasterController==host.GetComponent<PlayerCharacterMasterController>()&&master.playerCharacterMasterController,"Original player-master controller linkage");Check(!master.GetBody()&&!master.hasBody,"Unexpected spawned body");
   if(r.id=="master-network-spawn"){SpawnRecovered(host);Call(master,"UpdateAuthority");r.masterId=master.networkIdentity.netId.Value;Check(master.hasEffectiveAuthority&&Util.HasEffectiveAuthority(master.networkIdentity),"Recovered master effective authority");}
   var count=CharacterMaster.readOnlyInstancesList.Count;Call(master,"OnEnable");registered=true;Check(CharacterMaster.readOnlyInstancesList.Count==count+1&&CharacterMaster.readOnlyInstancesList.Contains(master),"Original master registration");Call(master,"OnDisable");registered=false;Check(CharacterMaster.readOnlyInstancesList.Count==count,"Original master unregistration");Check(!host.activeInHierarchy,"Master startup unexpectedly active");
  }finally{if(ownsServer){var id=host.GetComponent<NetworkIdentity>().netId;NetworkServer.UnSpawn(host);Check(!NetworkServer.FindLocalObject(id),"Master network object not removed");}if(registered)Call(master,"OnDisable");if(masterAwake)Call(master,"OnDestroy");if(inventoryAwake){Call(inventory,"OnDestroy");StaticCall(typeof(Inventory),"StaticFixedUpdate");}}
 }

 void SpawnRecovered(GameObject target){
  if(!ownsServer){Check(!NetworkServer.active&&!NetworkClient.active,"Existing network session");Check(NetworkServer.Listen("127.0.0.1",0),"Owned server listen failed");ownsServer=true;}
  Check(!target.activeInHierarchy,"Recovered root unexpectedly active");var identity=target.GetComponent<NetworkIdentity>();Check(identity,"Recovered identity missing");NetworkServer.Spawn(target);Check(identity.isServer&&identity.netId.Value!=0&&NetworkServer.FindLocalObject(identity.netId)==target,"Original recovered object spawn/lookup failed");
 }

}
