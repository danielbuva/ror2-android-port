using System;
using System.Linq;
using UnityEngine;
using RoR2;
using EntityStates.Commando.CommandoWeapon;
namespace UnityEngine {
 public static class Time {public static float realtimeSinceStartup=12f;}
 public sealed class GameObject {public AkGameObj source;}
}
namespace RoR2 {
 public sealed class CharacterBody {public GameObject gameObject=new GameObject();public T GetComponent<T>() where T:class {return gameObject.source as T;}}
}
namespace EntityStates.Commando.CommandoWeapon {public sealed class FirePistol2 {public static string firePistolSoundString="native-pistol";}}
public sealed class AkGameObj {public bool enabled;public static implicit operator bool(AkGameObj value) {return value!=null;}}
public enum AKRESULT {AK_Success=1,AK_Fail=2}
public static class PortSessionOriginalAudioOwner {public static bool PassivePcmCaptureRequested;}
public static class GameAudioOriginalOwner {public static bool Ready;}
public static class AkSoundEngine {
 public const ulong AK_INVALID_GAME_OBJECT=ulong.MaxValue;public const uint AK_INVALID_PLAYING_ID=0;
 public static int calls,eventReads;public static AKRESULT returnedResult=AKRESULT.AK_Success;public static bool fail,registered;public static uint count=2;
 public static bool IsGameObjectRegistered(GameObject body) {calls++;return registered;}
 public static uint GetIDFromString(string name) {calls++;return 77;}
 public static ulong GetAkGameObjectID(GameObject body) {calls++;return 123;}
 public static AKRESULT GetPlayingIDsFromGameObject(ulong id,ref uint available,uint[] ids) {
  calls++;if(fail)throw new InvalidOperationException("synthetic native query failure");
  if(id!=123||available!=8||ids.Length!=8)throw new Exception("query ownership/capacity");
  for(int i=0;i<Math.Min(count,8U);i++)ids[i]=(uint)(11+i);
  available=count;return returnedResult;
 }
 public static uint GetEventIDFromPlayingID(uint id) {calls++;eventReads++;return id==11?77U:88U;}
 public static AKRESULT GetRTPCValue(string name,ulong obj,uint playing,out float value,ref int type) {
  calls++;if(name!="Volume_SFX"||obj!=AK_INVALID_GAME_OBJECT||playing!=0||type!=1)throw new Exception("global source RTPC query");
  value=100;type=0;return AKRESULT.AK_Success;
 }
}
public sealed class SessionReport {public bool integratedWorld;}
public sealed class PortSession {
 public sealed class PrimaryFireOperandSnapshot {}
 __REPORT__
 public SessionReport r=new SessionReport();
 public sealed class AudioHarness {
  readonly PortSession coordinator;public AudioHarness(PortSession owner) {coordinator=owner;}
  public void Capture(CharacterBody body,PrimaryFireReport report) {ObserveOriginalPrimaryAudio(body,report);}
  __PRODUCTION__
 }
}
public static class AudioContract {
 static void Need(bool value,string message) {if(!value)throw new Exception(message);}
 public static void Main() {
  var owner=new PortSession();var harness=new PortSession.AudioHarness(owner);var body=new CharacterBody();
  body.gameObject.source=new AkGameObj {enabled=false};var report=new PortSession.PrimaryFireReport();
  harness.Capture(body,report);Need(!report.sourceAudioObservationCaptured&&AkSoundEngine.calls==0,"unrequested query");
  PortSessionOriginalAudioOwner.PassivePcmCaptureRequested=true;owner.r.integratedWorld=true;
  harness.Capture(body,report);Need(!report.sourceAudioObservationCaptured&&AkSoundEngine.calls==0,"unready query");
  GameAudioOriginalOwner.Ready=true;owner.r.integratedWorld=false;
  harness.Capture(body,report);Need(!report.sourceAudioObservationCaptured&&AkSoundEngine.calls==0,"historical fixture query");
  owner.r.integratedWorld=true;harness.Capture(body,report);
  Need(report.sourceAudioObservationCaptured&&report.sourceAudioObservationRealtime==12&&report.sourceAudioSoundName=="native-pistol","first source observation");
  Need(report.sourceAudioGameObjectPresent&&!report.sourceAudioGameObjectEnabled&&!report.sourceAudioManagedRegistered&&!body.gameObject.source.enabled,"observation must not repair registration or enable source components");
  Need(report.sourceAudioPlayingQueryReturned&&report.sourceAudioPlayingQueryResult==1&&report.sourceAudioPlayingIdCount==2&&report.sourceAudioPlayingIds.SequenceEqual(new uint[]{11,12})&&report.sourceAudioEventIds.SequenceEqual(new uint[]{77,88}),"bounded native voice results");
  Need(report.sourceAudioExpectedEventId==77&&report.sourceAudioVolumeQueryReturned&&report.sourceAudioVolumeQueryResult==1&&report.sourceAudioVolumeReturnedType==0&&report.sourceAudioVolumeValue==100,"original event/global volume observations");
  int before=AkSoundEngine.calls;Time.realtimeSinceStartup=99;harness.Capture(body,report);
  Need(AkSoundEngine.calls==before&&report.sourceAudioObservationRealtime==12,"one-shot query and immutable first sample");
  report=new PortSession.PrimaryFireReport();AkSoundEngine.fail=true;harness.Capture(body,report);
  Need(report.sourceAudioObservationCaptured&&!report.sourceAudioPlayingQueryReturned&&!report.sourceAudioVolumeQueryReturned&&report.sourceAudioObservationError.Contains("synthetic native query failure"),"read-only query failure remains bounded data");
  before=AkSoundEngine.calls;harness.Capture(body,report);Need(AkSoundEngine.calls==before,"no query retry after first failure");
  AkSoundEngine.fail=false;AkSoundEngine.returnedResult=AKRESULT.AK_Fail;AkSoundEngine.eventReads=0;
  report=new PortSession.PrimaryFireReport();harness.Capture(body,report);
  Need(report.sourceAudioPlayingQueryReturned&&report.sourceAudioPlayingQueryResult==2&&report.sourceAudioPlayingIds==null&&report.sourceAudioEventIds==null&&AkSoundEngine.eventReads==0,"failed native query cannot invent active IDs");
  AkSoundEngine.returnedResult=AKRESULT.AK_Success;
  AkSoundEngine.fail=false;AkSoundEngine.count=99;report=new PortSession.PrimaryFireReport();harness.Capture(body,report);
  Need(report.sourceAudioPlayingIdCount==99&&report.sourceAudioPlayingIds.Length==8&&report.sourceAudioEventIds.Length==8,"native available count cannot grow retained arrays");
 }
}
