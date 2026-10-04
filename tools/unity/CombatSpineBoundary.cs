using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using EntityStates;
using EntityStates.Commando;
using EntityStates.Commando.CommandoWeapon;
using RoR2;
using RoR2.Projectile;
using UnityEngine;
using UnityEngine.Networking;

// Integrated original skills and damage. Owned visuals/audio exclusions do not replace simulation.
public sealed partial class MovementBatchProbe {
 [Serializable] public class CombatReport {
  public int secondaryEntries,utilityEntries,specialEntries,projectiles,projectileSoundGuards,damageEvents;
  public float healthBefore,healthAfter,damageDealt,lastDamage;
  public string bodyState,weaponState,secondaryDefinition,utilityDefinition,specialDefinition;
  public bool targetServer,targetHurtBox,cleaned;public Vector3 targetCenter,aimOrigin;public int hurtBoxLayer,hurtBoxes;
 }
 readonly List<EntityStateConfiguration> combatConfigs=new List<EntityStateConfiguration>();
 readonly HashSet<int> observedProjectiles=new HashSet<int>();
 GameObject projectileTemplateHost,projectileHost,targetHost,targetVisual;
 GameObject ownedFMJ;CharacterBody targetBody;Material combatMaterial;Texture2D combatTexture;
 EntityState lastCombatBody,lastCombatWeapon;
 EntityStateConfiguration[] PrepareCombatConfigs(Result cfg){
  r.combat=new CombatReport();SilentProjectileBoundary.prepared=0;
  foreach(var asset in new[]{cfg.secondaryConfigAsset,cfg.utilityConfigAsset,cfg.specialConfigAsset}){
   var original=artifactBundle.LoadAsset<EntityStateConfiguration>(asset);Check(original,"Original default skill configuration missing: "+asset);
   var copy=Instantiate(original);copy.serializedFieldsCollection.serializedFields=original.serializedFieldsCollection.serializedFields.ToArray();
   for(int i=0;i<copy.serializedFieldsCollection.serializedFields.Length;i++){
    var name=copy.serializedFieldsCollection.serializedFields[i].fieldName;
    if(name=="attackSoundString")copy.serializedFieldsCollection.serializedFields[i].fieldValue.stringValue="";
    if(name=="effectPrefab"&&((Type)copy.targetType)==typeof(FireFMJ))copy.serializedFieldsCollection.serializedFields[i].fieldValue.objectValue=null;
    if(name=="projectilePrefab"){
     var originalProjectile=copy.serializedFieldsCollection.serializedFields[i].fieldValue.objectValue as GameObject;Check(originalProjectile,"Original FMJ projectile missing");
     projectileTemplateHost=new GameObject("Owned silent projectile template");projectileTemplateHost.SetActive(false);
     ownedFMJ=Instantiate(originalProjectile,projectileTemplateHost.transform);ownedFMJ.SetActive(true);
     ownedFMJ.AddComponent<SilentProjectileBoundary>();
     foreach(var component in ownedFMJ.GetComponentsInChildren<MonoBehaviour>(true)){
      if(component.GetType().Name.StartsWith("Ak",StringComparison.Ordinal)){DestroyImmediate(component);continue;}
      foreach(var field in component.GetType().GetFields(BindingFlags.Public|BindingFlags.Instance)){
       // Original AkEventIdArg bypasses native ID lookup only for null, not empty strings.
       if(field.FieldType==typeof(string)&&field.Name.IndexOf("sound",StringComparison.OrdinalIgnoreCase)>=0)field.SetValue(component,null);
       if(typeof(NetworkSoundEventDef).IsAssignableFrom(field.FieldType)||field.Name=="flightSoundLoop")field.SetValue(component,null);
       if(field.FieldType==typeof(GameObject)&&new[]{"ghostPrefab","impactEffect","impactEffectPrefab","hitEffectPrefab"}.Contains(field.Name))field.SetValue(component,null);
      }
     }
     // Readability marker follows the actual original projectile, without changing its motion/collision.
     var marker=GameObject.CreatePrimitive(PrimitiveType.Cube);DestroyImmediate(marker.GetComponent<Collider>());marker.name="Owned FMJ marker";marker.layer=30;marker.transform.SetParent(ownedFMJ.transform,false);marker.transform.localScale=new Vector3(.15f,.15f,1.5f);
     combatMaterial=new Material(Resources.Load<Shader>("CommandoPreview"));combatTexture=new Texture2D(1,1);combatTexture.SetPixel(0,0,Color.cyan);combatTexture.Apply();combatMaterial.mainTexture=combatTexture;marker.GetComponent<Renderer>().sharedMaterial=combatMaterial;
     copy.serializedFieldsCollection.serializedFields[i].fieldValue.objectValue=ownedFMJ;
    }
   }
   combatConfigs.Add(copy);
  }
  return combatConfigs.ToArray();
 }
 void PrepareCombatScene(CharacterBody player,Result cfg){
  r.phase="integrated-combat-setup";Save();Check(!ProjectileManager.instance,"Existing projectile manager");
  projectileHost=new GameObject("Owned original projectile manager");projectileHost.AddComponent<ProjectileManager>();
  if(cfg.integratedWorld){GlobalEventManager.onServerDamageDealt+=ObserveCombatDamage;return;}
  targetHost=Instantiate(artifactBundle.LoadAsset<GameObject>(cfg.bodyAsset));targetHost.name="Owned original damage target";
  foreach(var component in targetHost.GetComponentsInChildren<MonoBehaviour>(true)){
   component.enabled=false;if(component.GetType().Name.StartsWith("Ak",StringComparison.Ordinal))DestroyImmediate(component);
  }
  foreach(var renderer in targetHost.GetComponentsInChildren<Renderer>(true))renderer.enabled=false;
  foreach(var collider in targetHost.GetComponentsInChildren<Collider>(true))collider.enabled=false;
  targetBody=targetHost.GetComponent<CharacterBody>();Call(targetBody,"Awake");Call(targetBody.healthComponent,"Awake");Call(targetBody.teamComponent,"Awake");
  // Same recovered direct animator binding as the accepted player display, before original Awake.
  var animator=targetBody.modelLocator.modelTransform.GetComponent<Animator>();animator.avatar=artifactBundle.LoadAsset<Avatar>(cfg.displayAssets[1]);animator.runtimeAnimatorController=artifactBundle.LoadAsset<RuntimeAnimatorController>(cfg.displayAssets[0]);animator.enabled=false;
  targetBody.teamComponent.teamIndex=TeamIndex.Monster;targetBody.baseMaxHealth=5000;targetBody.RecalculateStats();targetBody.healthComponent.health=targetBody.maxHealth;
  targetHost.transform.position=player.transform.position+Vector3.forward*5;
  var hurt=targetBody.mainHurtBox;foreach(var box in targetBody.hurtBoxGroup.hurtBoxes){box.enabled=true;box.teamIndex=TeamIndex.Monster;box.GetComponent<Collider>().enabled=true;for(var t=box.transform;t&&t!=targetHost.transform;t=t.parent)t.gameObject.SetActive(true);}
  NetworkServer.Spawn(targetHost);targetHost.SetActive(true);Physics.SyncTransforms();
  targetVisual=GameObject.CreatePrimitive(PrimitiveType.Capsule);DestroyImmediate(targetVisual.GetComponent<Collider>());targetVisual.name="Owned target health display";targetVisual.layer=30;targetVisual.transform.position=hurt.transform.position;targetVisual.GetComponent<Renderer>().sharedMaterial=combatMaterial;
  r.combat.targetServer=targetBody.isServer;r.combat.targetHurtBox=hurt.healthComponent==targetBody.healthComponent;r.combat.healthBefore=targetBody.healthComponent.health;
  r.combat.targetCenter=targetBody.corePosition;r.combat.aimOrigin=player.inputBank.aimOrigin;r.combat.hurtBoxLayer=hurt.gameObject.layer;r.combat.hurtBoxes=targetBody.hurtBoxGroup.hurtBoxes.Length;
  r.combat.secondaryDefinition=((ScriptableObject)player.skillLocator.secondary.skillDef).name;r.combat.utilityDefinition=((ScriptableObject)player.skillLocator.utility.skillDef).name;r.combat.specialDefinition=((ScriptableObject)player.skillLocator.special.skillDef).name;
  Check(r.combat.targetServer&&r.combat.targetHurtBox&&r.combat.healthBefore==5000,"Original target server/hurtbox/health contract");
  GlobalEventManager.onServerDamageDealt+=ObserveCombatDamage;Save();
 }
 Vector2 CombatAim(CharacterBody player){var delta=targetBody.corePosition-player.inputBank.aimOrigin;return new Vector2(delta.x,delta.z).normalized;}
 void ObserveCombatDamage(DamageReport report){if(r.integratedWorld){if(report.attackerBody!=worldPlayer)return;}else if(report.victimBody!=targetBody)return;r.combat.damageEvents++;r.combat.lastDamage=report.damageDealt;r.combat.damageDealt+=report.damageDealt;}
 void ObserveCombat(CharacterBody player,EntityStateMachine machine){
  var weapon=player.skillLocator.primary.stateMachine.state;r.combat.weaponState=weapon.GetType().FullName;r.combat.bodyState=machine.state.GetType().FullName;
  if(weapon!=lastCombatWeapon){if(weapon is FireFMJ)r.combat.secondaryEntries++;if(weapon is FireBarrage)r.combat.specialEntries++;lastCombatWeapon=weapon;}
  if(machine.state!=lastCombatBody){if(machine.state is DodgeState)r.combat.utilityEntries++;lastCombatBody=machine.state;}
  foreach(var projectile in FindObjectsOfType<ProjectileController>())observedProjectiles.Add(projectile.GetInstanceID());r.combat.projectiles=observedProjectiles.Count;r.combat.projectileSoundGuards=SilentProjectileBoundary.prepared;
  r.combat.healthAfter=targetBody?targetBody.healthComponent.health:0;
 }
 void CleanupCombatScene(){
  GlobalEventManager.onServerDamageDealt-=ObserveCombatDamage;
  foreach(var projectile in FindObjectsOfType<ProjectileController>())NetworkServer.Destroy(projectile.gameObject);
  if(targetHost){targetHost.SetActive(false);NetworkServer.UnSpawn(targetHost);Destroy(targetHost);}if(targetVisual)Destroy(targetVisual);if(projectileHost)Destroy(projectileHost);
  if(r.combat!=null)r.combat.cleaned=true;
 }
 void CleanupCombatConfigs(){foreach(var cfg in combatConfigs)if(cfg)Destroy(cfg);combatConfigs.Clear();if(projectileTemplateHost)Destroy(projectileTemplateHost);if(combatMaterial)Destroy(combatMaterial);if(combatTexture)Destroy(combatTexture);}
}
