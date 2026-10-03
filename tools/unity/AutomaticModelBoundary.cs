using System.Collections;
using System.Reflection;
using RoR2;
using UnityEngine;

// Observe original detachment/following/destruction; never move or turn the model in the harness.
public sealed partial class MovementBatchProbe {
 GameObject ownedDetachedModel;
 bool IsAutomaticModel(){return IsAutomaticSkill()||r.id.StartsWith("body-state-spawn-state-auto-model-");}
 void PrepareAutomaticModel(CharacterBody body){
  var locator=body.modelLocator;var model=locator.modelTransform;
  Check(locator&&model&&model.parent==locator.modelBaseTransform&&!locator.enabled,"Original model pre-Start identity/isolation");
  Check(typeof(ModelLocator).GetField("modelParentTransform",BindingFlags.Instance|BindingFlags.NonPublic).GetValue(locator)==null,"ModelLocator Start already ran");
  Check(locator.autoUpdateModelTransform&&!locator.dontDetatchFromParent&&!locator.preserveModel&&!locator.normalizeToFloor,"Recovered model lifecycle settings changed");
  ownedDetachedModel=model.gameObject;model.gameObject.SetActive(false); // Detachment must not activate the unproven child callbacks.
  r.modelTarget=model.name;r.modelParent=locator.modelBaseTransform.name;Save();
 }
 void ObserveAutomaticModelFollow(CharacterBody body){
  var locator=body.modelLocator;var model=locator.modelTransform;var parent=locator.modelBaseTransform;
  Check(locator.enabled&&model&&model.gameObject==ownedDetachedModel&&!model.parent&&!model.gameObject.activeInHierarchy,"Original detached model identity/isolation");
  Check(typeof(ModelLocator).GetField("modelParentTransform",BindingFlags.Instance|BindingFlags.NonPublic).GetValue(locator)==parent,"Original model Start parent cache");
  float position=Vector3.Distance(model.position,parent.position),rotation=Quaternion.Angle(model.rotation,parent.rotation);
  r.modelPositionError=Mathf.Max(r.modelPositionError,position);r.modelRotationError=Mathf.Max(r.modelRotationError,rotation);r.modelFollowFrames++;
  Check(position<.001f&&rotation<.03f,"Original LateUpdate model follow pose");r.modelDetached=true;
 }
 IEnumerator VerifyAutomaticModelDestruction(){
  if(!IsAutomaticModel()||string.IsNullOrEmpty(r.modelTarget))yield break;
  // Root destruction invokes original OnDestroy, whose model destruction is also deferred.
  for(int frame=0;ownedDetachedModel&&frame<3;frame++)yield return null;
  r.modelDestroyed=!ownedDetachedModel;Check(r.modelDetached&&r.modelFollowFrames>300&&r.modelDestroyed,"Original detached model destruction before provider release");Save();
 }
}
