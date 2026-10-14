using System.Collections;
using System.Reflection;
using RoR2;
using UnityEngine;

// Observe original detachment/following/destruction; never move or turn the model in the harness.
public sealed partial class MovementBatchProbe {
 GameObject ownedDetachedModel;
 bool IsAutomaticModel(){return IsNovaInput()||IsAutomaticSkill()||r.id.StartsWith("body-state-spawn-state-auto-model-");}
 void PrepareAutomaticModel(CharacterBody body){
  var locator=body.modelLocator;var model=locator.modelTransform;
  Check(locator&&model&&model.parent==locator.modelBaseTransform&&!locator.enabled,"Original model pre-Start identity/isolation");
  Check(typeof(ModelLocator).GetField("modelParentTransform",BindingFlags.Instance|BindingFlags.NonPublic).GetValue(locator)==null,"ModelLocator Start already ran");
  Check(locator.autoUpdateModelTransform&&!locator.dontDetatchFromParent&&!locator.preserveModel,"Recovered model lifecycle settings changed");
  ownedDetachedModel=model.gameObject;model.gameObject.SetActive(false); // Detachment must not activate the unproven child callbacks.
  r.modelTarget=model.name;r.modelParent=locator.modelBaseTransform.name;Save();
 }
 void ObserveAutomaticModelFollow(CharacterBody body){
  var locator=body.modelLocator;var model=locator.modelTransform;var parent=locator.modelBaseTransform;
  Check(locator.enabled&&model&&model.gameObject==ownedDetachedModel&&!model.parent&&(!model.gameObject.activeInHierarchy||IsPlayableSpine()),"Original detached model identity/isolation");
  Check(typeof(ModelLocator).GetField("modelParentTransform",BindingFlags.Instance|BindingFlags.NonPublic).GetValue(locator)==parent,"Original model Start parent cache");
  // The source ModelLocator tilts floor-normalized models (Treebot) before
  // applying the parent rotation. Compare against that original pose.
  var normal=(Vector3)typeof(ModelLocator).GetField("currentNormal",BindingFlags.Instance|BindingFlags.NonPublic).GetValue(locator);
  var expectedRotation=Quaternion.FromToRotation(Vector3.up,normal)*parent.rotation;
  float position=Vector3.Distance(model.position,parent.position),rotation=Quaternion.Angle(model.rotation,expectedRotation);
  r.modelPositionError=Mathf.Max(r.modelPositionError,position);r.modelRotationError=Mathf.Max(r.modelRotationError,rotation);r.modelFollowFrames++;
  Check(position<.001f&&rotation<.03f,"Original LateUpdate model follow pose");r.modelDetached=true;
 }
 IEnumerator VerifyAutomaticModelDestruction(){
  if(!IsAutomaticModel()||string.IsNullOrEmpty(r.modelTarget))yield break;
  // Root destruction invokes original OnDestroy, whose model destruction is also deferred.
  for(int frame=0;ownedDetachedModel&&frame<3;frame++)yield return null;
  r.modelDestroyed=!ownedDetachedModel;
  // Genuine integrated death/abandonment may end before the isolated proof's
  // sampling quota. Still require observed native follow and actual destruction.
  int requiredFrames=r.integratedWorld||!string.IsNullOrEmpty(r.firstFailure)?1:301;
  Check(r.modelDetached&&r.modelFollowFrames>=requiredFrames&&r.modelDestroyed,"Original detached model lifecycle before provider release: followed="+r.modelFollowFrames+" required="+requiredFrames+" destroyed="+r.modelDestroyed);Save();
 }
}
