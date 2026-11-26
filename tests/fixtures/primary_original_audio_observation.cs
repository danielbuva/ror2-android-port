using System;
using System.Linq;
using System.Reflection;
using UnityEngine;
using RoR2;
using EntityStates.Commando.CommandoWeapon;
namespace UnityEngine {
 public static class Time {public static float realtimeSinceStartup=12f;}
 public sealed class GameObject {public AkGameObj source;}
}
namespace RoR2 {
 public sealed class CharacterBody {public GameObject gameObject=new GameObject();public bool networkIdentity;public T GetComponent<T>() where T:class {return gameObject.source as T;}public static implicit operator bool(CharacterBody body) {return body!=null;}}
 public static class Util {public static bool HasEffectiveAuthority(bool authority) {return authority;}}
 public static class WwiseIntegrationManager {public static bool noAudio;}
}
namespace EntityStates.Commando.CommandoWeapon {public sealed class FirePistol2 {public static string firePistolSoundString="native-pistol";}}
public sealed class AkGameObj {public bool enabled;public static implicit operator bool(AkGameObj value) {return value!=null;}}
public enum AKRESULT {AK_Success=1,AK_Fail=2,AK_IDNotFound=15}
public sealed class AkObjectInfoArray : IDisposable {
 public static int disposed;public readonly int capacity;
 public AkObjectInfoArray(int capacity) {this.capacity=capacity;}
 public void Dispose() {disposed++;}
}
public sealed class AkWorldTransform : IDisposable {
 public static int disposed;
 public void Dispose() {disposed++;}
}
public static class PortSessionOriginalAudioOwner {public static bool PassivePcmCaptureRequested;}
public static class GameAudioOriginalOwner {public static bool Ready;public static ulong SuccessfulOriginalRenderFrames;}
public static class AkSoundEngine {
 public const ulong AK_INVALID_GAME_OBJECT=ulong.MaxValue;public const uint AK_INVALID_PLAYING_ID=0;
 public static int calls,eventReads,volumeReads;public static AKRESULT returnedResult=AKRESULT.AK_Success;public static bool fail,registered;public static uint count;
 public static bool IsGameObjectRegistered(GameObject body) {calls++;return registered;}
 public static uint GetIDFromString(string name) {calls++;return 77;}
 public static ulong emitterId=123;
 public static int objectReads,positionReads;public static bool failEventQuery;
 public static ulong GetAkGameObjectID(GameObject body) {calls++;return emitterId;}
 public static AKRESULT QueryAudioObjectIDs(string name,ref uint count,AkObjectInfoArray objects) {
  objectReads++;
  if(name!="native-pistol"||count!=8||objects.capacity!=8)throw new Exception("first event name and query capacity");
  if(failEventQuery)throw new InvalidOperationException("synthetic event lookup failure");
  count=3;return AKRESULT.AK_Success;
 }
 public static AKRESULT GetPosition(ulong id,AkWorldTransform position) {
  positionReads++;
  if(id!=123||position==null)throw new Exception("first native emitter ID");
  return AKRESULT.AK_IDNotFound;
 }
 public static AKRESULT GetPlayingIDsFromGameObject(ulong id,ref uint available,uint[] ids) {
  calls++;if(fail)throw new InvalidOperationException("synthetic native query failure");
  if(id!=123||available!=8||ids.Length!=8)throw new Exception("query ownership/capacity");
  for(int i=0;i<Math.Min(count,8U);i++)ids[i]=(uint)(11+i);
  available=count;return returnedResult;
 }
 public static bool pistolPlaying;
 public static uint GetEventIDFromPlayingID(uint id) {calls++;eventReads++;return id==11&&pistolPlaying?77U:88U;}
 public static AKRESULT GetRTPCValue(string name,ulong obj,uint playing,out float value,ref int type) {
  calls++;volumeReads++;if(name!="Volume_SFX"||obj!=AK_INVALID_GAME_OBJECT||playing!=0||type!=1)throw new Exception("global source RTPC query");
  value=100;type=0;return AKRESULT.AK_Success;
 }
}
public sealed class SessionReport {public bool integratedWorld;public PortSession.PrimaryFireReport primary;}
public sealed class PortSession {
 public sealed class PrimaryFireOperandSnapshot {}
 __REPORT__
 public SessionReport r=new SessionReport();
 public sealed class AudioHarness {
  readonly PortSession coordinator;public AudioHarness(PortSession owner) {coordinator=owner;}
  public bool preserveOriginalAudio=true;
  FieldInfo postObserverField;Action<uint,object> postObserver;
  public void Capture(CharacterBody body,PrimaryFireReport report) {
   ObserveRejectedPrimaryAudioPost(report);ObserveOriginalPrimaryAudio(body,report);
  }
  __PRODUCTION__
 }
}
public static class AudioContract {
 static void Need(bool value,string message) {if(!value)throw new Exception(message);}
 public static void Main() {
  var owner=new PortSession();var harness=new PortSession.AudioHarness(owner);var body=new CharacterBody();
  body.gameObject.source=new AkGameObj {enabled=false};var report=new PortSession.PrimaryFireReport();owner.r.primary=report;
  harness.AttachPrimaryPostObserver(body);
  Need(!report.sourceAudioPostObserverAttached&&AndroidCommandoPostObserver.Returned==null,"default-off post witness");
  harness.Capture(body,report);Need(!report.sourceAudioObservationCaptured&&AkSoundEngine.calls==0,"unrequested query");
  PortSessionOriginalAudioOwner.PassivePcmCaptureRequested=true;owner.r.integratedWorld=true;
  harness.Capture(body,report);Need(!report.sourceAudioObservationCaptured&&AkSoundEngine.calls==0,"unready query");
  GameAudioOriginalOwner.Ready=true;owner.r.integratedWorld=false;
  harness.Capture(body,report);Need(!report.sourceAudioObservationCaptured&&AkSoundEngine.calls==0,"historical fixture query");
  owner.r.integratedWorld=true;harness.AttachPrimaryPostObserver(body);
  Need(report.sourceAudioPostObserverAttached,"explicit post witness");
  AndroidCommandoPostObserver.Record(3,body.gameObject);
  body.networkIdentity=true;AndroidCommandoPostObserver.Record(4,new GameObject());
  Need(report.sourceAudioPostReturns==0,"foreign and non-authority emitters are ignored");
  WwiseIntegrationManager.noAudio=true;
  GameAudioOriginalOwner.SuccessfulOriginalRenderFrames=1;
  AndroidCommandoPostObserver.Record(0,body.gameObject);harness.Capture(body,report);
  Need(report.sourceAudioPostReturns==1&&report.sourceAudioPostAcceptedReturns==0&&report.sourceAudioPlayingQueryAttempts==0&&AkSoundEngine.calls==2,"invalid returns capture managed state and native emitter ID");
  Need(report.sourceAudioObservationCaptured&&report.sourceAudioNoAudioAtFirstPost&&report.sourceAudioFirstPostRenderFrame==1&&report.sourceAudioSoundName=="native-pistol","first zero return records the original managed gate and sound name");
  WwiseIntegrationManager.noAudio=false;
  GameAudioOriginalOwner.SuccessfulOriginalRenderFrames=0;
  AndroidCommandoPostObserver.Record(11,body.gameObject);AndroidCommandoPostObserver.Record(12,body.gameObject);
  Need(report.sourceAudioPostReturns==3&&report.sourceAudioPostAcceptedReturns==2&&report.sourceAudioPostPlayingId==11,"keep the first accepted return");
  harness.Capture(body,report);
  Need(report.sourceAudioObservationCaptured&&report.sourceAudioObservationRealtime==12&&report.sourceAudioNoAudioAtFirstPost&&report.sourceAudioFirstPostRenderFrame==1,"keep the first source observation after acceptance");
  Need(report.sourceAudioGameObjectPresent&&!report.sourceAudioGameObjectEnabled&&!report.sourceAudioManagedRegistered&&!body.gameObject.source.enabled,"observation must not repair registration or enable source components");
  Need(report.sourceAudioPlayingQueryReturned&&report.sourceAudioPlayingQueryResult==1&&report.sourceAudioPlayingIdCount==0&&report.sourceAudioPlayingQueryAttempts==1,"first native query can validly have no voices");
  Need(report.sourceAudioExpectedEventId==77&&report.sourceAudioVolumeQueryReturned&&report.sourceAudioVolumeQueryResult==1&&report.sourceAudioVolumeReturnedType==0&&report.sourceAudioVolumeValue==100,"original event/global volume observations");
  int before=AkSoundEngine.calls;Time.realtimeSinceStartup=99;harness.Capture(body,report);
  Need(AkSoundEngine.calls==before,"no duplicate query on the same audio render frame");
  AkSoundEngine.count=2;GameAudioOriginalOwner.SuccessfulOriginalRenderFrames=1;harness.Capture(body,report);
  Need(!report.sourceAudioExpectedEventObserved&&report.sourceAudioEventIds.SequenceEqual(new uint[]{88,88}),"unrelated active voices do not prove the pistol event");
  AkSoundEngine.pistolPlaying=true;GameAudioOriginalOwner.SuccessfulOriginalRenderFrames=2;harness.Capture(body,report);
  Need(report.sourceAudioExpectedEventObserved&&report.sourceAudioPlayingQueryAttempts==3&&report.sourceAudioPlayingQueryRenderFrame==2&&report.sourceAudioPlayingIds.SequenceEqual(new uint[]{11,12})&&report.sourceAudioEventIds.SequenceEqual(new uint[]{77,88}),"later original service frame confirms exact event");
  before=AkSoundEngine.calls;GameAudioOriginalOwner.SuccessfulOriginalRenderFrames=3;harness.Capture(body,report);
  Need(AkSoundEngine.calls==before&&report.sourceAudioObservationRealtime==12&&AkSoundEngine.volumeReads==1,"keep matched voice and first source metadata");
  report=new PortSession.PrimaryFireReport {sourceAudioPostAcceptedReturns=1};AkSoundEngine.fail=true;harness.Capture(body,report);
  Need(!report.sourceAudioPlayingQueryReturned&&!report.sourceAudioVolumeQueryReturned&&report.sourceAudioObservationError.Contains("synthetic native query failure"),"read-only query failure remains bounded data");
  before=AkSoundEngine.calls;GameAudioOriginalOwner.SuccessfulOriginalRenderFrames++;harness.Capture(body,report);
  Need(AkSoundEngine.calls==before,"no query retry after native exception");
  AkSoundEngine.fail=false;AkSoundEngine.returnedResult=AKRESULT.AK_Fail;AkSoundEngine.eventReads=0;
  report=new PortSession.PrimaryFireReport {sourceAudioPostAcceptedReturns=1};harness.Capture(body,report);
  Need(report.sourceAudioPlayingQueryReturned&&report.sourceAudioPlayingQueryResult==2&&report.sourceAudioPlayingIds==null&&report.sourceAudioEventIds==null&&AkSoundEngine.eventReads==0,"failed native query cannot invent active IDs");
  AkSoundEngine.returnedResult=AKRESULT.AK_Success;
  AkSoundEngine.fail=false;AkSoundEngine.count=99;report=new PortSession.PrimaryFireReport {sourceAudioPostAcceptedReturns=1};harness.Capture(body,report);
  Need(report.sourceAudioPlayingIdCount==99&&report.sourceAudioPlayingIds.Length==8&&report.sourceAudioEventIds.Length==8,"native available count cannot grow retained arrays");
  AkSoundEngine.count=0;report=new PortSession.PrimaryFireReport {sourceAudioPostAcceptedReturns=1};
  for(int frame=0;frame<24;frame++) {
   GameAudioOriginalOwner.SuccessfulOriginalRenderFrames++;harness.Capture(body,report);
  }
  Need(!report.sourceAudioExpectedEventObserved&&report.sourceAudioPlayingQueryAttempts==12,"empty voice results have a bounded retry budget");
  Need(AkSoundEngine.objectReads==0&&AkSoundEngine.positionReads==0,"a no-audio gate rejection does not query native state");

  AndroidCommandoPostObserver.Returned=null;
  report=new PortSession.PrimaryFireReport();owner.r.primary=report;harness.AttachPrimaryPostObserver(body);
  ulong firstFrame=GameAudioOriginalOwner.SuccessfulOriginalRenderFrames;
  AndroidCommandoPostObserver.Record(0,body.gameObject);harness.Capture(body,report);
  Need(report.sourceAudioFirstPostRejected&&report.sourceAudioFirstPostEmitterId==123&&
       !report.sourceAudioRejectedPostQueryAttempted&&AkSoundEngine.objectReads==0&&AkSoundEngine.positionReads==0,
       "rejected native post waits for a later service frame");
  FirePistol2.firePistolSoundString="later-event";AkSoundEngine.emitterId=456;
  GameAudioOriginalOwner.SuccessfulOriginalRenderFrames++;harness.Capture(body,report);
  Need(report.sourceAudioRejectedPostQueryRenderFrame==firstFrame+1&&report.sourceAudioEventObjectsQueryReturned&&
       report.sourceAudioEventObjectsQueryResult==1&&report.sourceAudioEventObjectCount==3&&
       report.sourceAudioEmitterPositionQueryReturned&&report.sourceAudioEmitterPositionQueryResult==15&&
       report.sourceAudioPlayingQueryAttempts==0,"record raw independent event and emitter results using first post operands");
  GameAudioOriginalOwner.SuccessfulOriginalRenderFrames++;harness.Capture(body,report);
  Need(AkSoundEngine.objectReads==1&&AkSoundEngine.positionReads==1&&AkObjectInfoArray.disposed==1&&AkWorldTransform.disposed==1,
       "both native query buffers are disposed after one attempt");

  FirePistol2.firePistolSoundString="native-pistol";AkSoundEngine.emitterId=123;
  AndroidCommandoPostObserver.Returned=null;
  report=new PortSession.PrimaryFireReport();owner.r.primary=report;harness.AttachPrimaryPostObserver(body);
  AndroidCommandoPostObserver.Record(0,body.gameObject);AkSoundEngine.failEventQuery=true;
  GameAudioOriginalOwner.SuccessfulOriginalRenderFrames++;harness.Capture(body,report);
  GameAudioOriginalOwner.SuccessfulOriginalRenderFrames++;harness.Capture(body,report);
  Need(!report.sourceAudioEventObjectsQueryReturned&&report.sourceAudioEventObjectsQueryError.Contains("synthetic event lookup failure")&&
       report.sourceAudioEmitterPositionQueryReturned&&AkSoundEngine.objectReads==2&&AkSoundEngine.positionReads==2&&
       AkObjectInfoArray.disposed==2&&AkWorldTransform.disposed==2,"event exception still releases the buffer and allows one emitter lookup");
  AndroidCommandoPostObserver.Returned=(_, __)=>throw new Exception("observer failure");
  AndroidCommandoPostObserver.Record(11,body.gameObject);
 }
}
