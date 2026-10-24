using System;
using System.Linq;
using System.Reflection;
using RoR2;
using EntityStates.Commando.CommandoWeapon;
namespace EntityStates.Commando.CommandoWeapon {
 public class FirePistol2 {
  public static string firePistolSoundString;
  public static object muzzleEffectPrefab,hitEffectPrefab,tracerEffectPrefab;
  public static float damageCoefficient=1,force=200,baseDuration=.15f;
 }
 public class FireBarrage {
  public static string fireBarrageSoundString;
  public static object effectPrefab,hitEffectPrefab,tracerEffectPrefab;
 }
}
namespace EntityStates.Commando {
 public class DodgeState {public static string dodgeSoundString;public static object jetEffect;}
}
namespace RoR2 {
 public struct FieldValue {public string stringValue;}
 public struct SerializedField {public string fieldName;public FieldValue fieldValue;}
 public struct FieldCollection {public SerializedField[] serializedFields;}
 public class EntityStateConfiguration {
  public FieldCollection serializedFieldsCollection;
  public bool destroyed;
  public static implicit operator bool(EntityStateConfiguration value) {return value!=null&&!value.destroyed;}
 }
}
public sealed class SessionConfig {public bool integratedWorld,combatSpine;public string primaryFireConfigAsset="fire",primaryReloadConfigAsset="reload";}
public sealed class SessionReport {public bool integratedWorld;public PortSession.PrimaryFireReport primary;public object combat;}
public sealed class Bundle {
 public EntityStateConfiguration fire=new EntityStateConfiguration();
 public EntityStateConfiguration reload=new EntityStateConfiguration {serializedFieldsCollection=new FieldCollection {serializedFields=new[]{new SerializedField {fieldName="enterSoundString",fieldValue=new FieldValue {stringValue="native-reload"}}}}};
 public T LoadAsset<T>(string name) where T:class {return (name=="fire"?fire:reload) as T;}
}
public sealed class PortSession {
 public sealed class PrimaryFireOperandSnapshot {}
 public sealed class PrimaryFireReport {public bool silentFixture;public PrimaryFireOperandSnapshot lastOperands;public float damageCoefficient,force,baseDuration;}
 public SessionReport r=new SessionReport();public Bundle artifactBundle=new Bundle();public int cleaned;
 public void Check(bool value,string message) {if(!value)throw new Exception(message);}
 public EntityStateConfiguration[] PrepareCombatConfigs(SessionConfig cfg) {r.combat=new object();return new EntityStateConfiguration[0];}
 public void CleanupCombatConfigs() {cleaned++;}
 public sealed class PrimaryFireSession {
  readonly PortSession coordinator;FieldInfo[] spineFields;object[] spinePrior;EntityStateConfiguration spineReload;
  public PrimaryFireSession(PortSession owner) {coordinator=owner;}
  static EntityStateConfiguration Instantiate(EntityStateConfiguration source) {return new EntityStateConfiguration {serializedFieldsCollection=source.serializedFieldsCollection};}
  static void Destroy(EntityStateConfiguration value) {value.destroyed=true;}
  __PRODUCTION_MEMBERS__
 }
}
public static class PrimaryAudioHarness {
 static void Need(bool value,string message) {if(!value)throw new Exception(message);}
 public static void Main() {
  foreach(bool integrated in new[]{false,true})foreach(bool combat in new[]{false,true}) {
   FirePistol2.firePistolSoundString="prior-pistol";
   FireBarrage.fireBarrageSoundString="prior-barrage";
   EntityStates.Commando.DodgeState.dodgeSoundString="prior-dodge";
   var owner=new PortSession();owner.r.integratedWorld=integrated;
   var session=new PortSession.PrimaryFireSession(owner);
   var cfg=new SessionConfig {integratedWorld=integrated,combatSpine=combat};
   var configs=session.PrepareSpineConfigs(cfg,new EntityStateConfiguration());
   var reload=configs[2];
   Need(reload.serializedFieldsCollection.serializedFields[0].fieldValue.stringValue==(integrated?"native-reload":""),"reload selection");
   Need(owner.artifactBundle.reload.serializedFieldsCollection.serializedFields[0].fieldValue.stringValue=="native-reload","original reload mutated");
   Need(owner.r.primary.silentFixture==!integrated,"silent fixture report");
   FirePistol2.firePistolSoundString="native-pistol";
   FireBarrage.fireBarrageSoundString="native-barrage";
   EntityStates.Commando.DodgeState.dodgeSoundString="native-dodge";
   FirePistol2.muzzleEffectPrefab=FirePistol2.hitEffectPrefab=FirePistol2.tracerEffectPrefab=new object();
   session.ApplySpineExclusions();
   Need(FirePistol2.firePistolSoundString==(integrated?"native-pistol":""),"pistol native sound");
   Need(FireBarrage.fireBarrageSoundString==(!combat||integrated?"native-barrage":""),"barrage sound");
   Need(EntityStates.Commando.DodgeState.dodgeSoundString==(!combat||integrated?"native-dodge":""),"dodge sound");
   Need(FirePistol2.muzzleEffectPrefab==null&&FirePistol2.hitEffectPrefab==null&&FirePistol2.tracerEffectPrefab==null,"effect exclusions retained");
   Need(FirePistol2.damageCoefficient==1&&FirePistol2.force==200&&FirePistol2.baseDuration==.15f,"gameplay fields changed");
   session.Dispose();session.Dispose();
   Need(reload.destroyed&&FirePistol2.firePistolSoundString=="prior-pistol","owned clone/static teardown");
   if(combat)Need(FireBarrage.fireBarrageSoundString=="prior-barrage"&&EntityStates.Commando.DodgeState.dodgeSoundString=="prior-dodge","combat static teardown");
  }
 }
}
