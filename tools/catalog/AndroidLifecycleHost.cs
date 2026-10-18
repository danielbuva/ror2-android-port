using System;
using System.Linq;
using System.Reflection;
using RoR2;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Networking;
using UnityEngine.SceneManagement;

// Exercise the actual owned cleanup against a destroyed native body, without
// Play Mode, catalog initialization, profile changes or touching source assets.
public static class AndroidLifecycleHost {
 const BindingFlags Instance=BindingFlags.Instance|BindingFlags.Public|BindingFlags.NonPublic;
 sealed class Counter {public int calls;public void Hit(){calls++;}}
 static FieldInfo ProbeField(string name){return typeof(MovementBatchProbe).GetField(name,Instance)??throw new MissingFieldException(name);}
 static Delegate BodyEvent(CharacterBody body,string name){return (Delegate)(typeof(CharacterBody).GetField(name,Instance)??throw new MissingFieldException(name)).GetValue(body);}
 static void Require(bool condition,string message){if(!condition)throw new Exception(message);}
 static void ContainsExactly(Delegate callbacks,params Delegate[] expected){Require(callbacks!=null&&callbacks.GetInvocationList().SequenceEqual(expected),"Owned callback or sentinel identity differs");}
 static void Cleanup(MovementBatchProbe probe,string method){
  try{(typeof(MovementBatchProbe).GetMethod(method,Instance)??throw new MissingMethodException(method)).Invoke(probe,null);}
  catch(TargetInvocationException error){System.Runtime.ExceptionServices.ExceptionDispatchInfo.Capture(error.InnerException??error).Throw();}
 }
 public static object Run(){
  Require(!EditorApplication.isPlaying&&!EditorApplication.isCompiling&&!NetworkServer.active&&!NetworkClient.active&&!RoR2.Run.instance,"Require idle editor without a gameplay session");
  var scene=EditorSceneManager.NewPreviewScene();GameObject probeRoot=null,bodyRoot=null;CharacterBody body=null;
  var owned=new Counter();var sentinel=new Counter();
  Action ownedInventory=owned.Hit,sentinelInventory=sentinel.Hit;
  CharacterBody.JumpDelegate ownedJump=owned.Hit,sentinelJump=sentinel.Hit;
  try{
   probeRoot=new GameObject("Owned lifecycle host fixture");probeRoot.SetActive(false);SceneManager.MoveGameObjectToScene(probeRoot,scene);var probe=probeRoot.AddComponent<MovementBatchProbe>();
   ProbeField("r").SetValue(probe,new MovementBatchProbe.SessionReport{itemDisplays=new MovementBatchProbe.WorldItemDisplayReport()});
   bodyRoot=new GameObject("Owned inactive body fixture");bodyRoot.SetActive(false);SceneManager.MoveGameObjectToScene(bodyRoot,scene);body=bodyRoot.AddComponent<CharacterBody>();
   body.onInventoryChanged+=sentinelInventory;body.onInventoryChanged+=ownedInventory;body.onJump+=sentinelJump;body.onJump+=ownedJump;
   ProbeField("worldDisplayBody").SetValue(probe,body);ProbeField("worldDisplayInventoryChanged").SetValue(probe,ownedInventory);
   ProbeField("worldPlayer").SetValue(probe,body);ProbeField("worldFeatherJumped").SetValue(probe,ownedJump);
   UnityEngine.Object.DestroyImmediate(bodyRoot);bodyRoot=null;
   Require(!body&&!ReferenceEquals(body,null),"Fixture did not retain a destroyed managed body wrapper");
   ContainsExactly(BodyEvent(body,"onInventoryChanged"),sentinelInventory,ownedInventory);ContainsExactly(BodyEvent(body,"onJump"),sentinelJump,ownedJump);
   Cleanup(probe,"CleanupWorldItemDisplays");ContainsExactly(BodyEvent(body,"onInventoryChanged"),sentinelInventory);
   Require(ProbeField("worldDisplayInventoryChanged").GetValue(probe)==null,"Owned inventory callback field retained");
   Cleanup(probe,"CleanupWorldLootSupport");ContainsExactly(BodyEvent(body,"onJump"),sentinelJump);
   Require(ProbeField("worldFeatherJumped").GetValue(probe)==null,"Owned jump callback field retained");
   ((Action)BodyEvent(body,"onInventoryChanged"))();((CharacterBody.JumpDelegate)BodyEvent(body,"onJump"))();
   Require(owned.calls==0&&sentinel.calls==2,"Cleanup removed a sentinel or retained an owned callback");
   // Repeated teardown remains harmless and never removes unrelated callbacks.
   Cleanup(probe,"CleanupWorldItemDisplays");Cleanup(probe,"CleanupWorldLootSupport");
   ContainsExactly(BodyEvent(body,"onInventoryChanged"),sentinelInventory);ContainsExactly(BodyEvent(body,"onJump"),sentinelJump);
   return new{success=true,destroyedManagedWrapper=true,actualCleanupMethods=true,inventoryOwnedRemoved=true,jumpOwnedRemoved=true,sentinelsPreserved=true,repeatedCleanup=true,retainingRootProven=false,deviceLeakFixProven=false};
  }finally{
   if(!ReferenceEquals(body,null)){body.onInventoryChanged-=ownedInventory;body.onInventoryChanged-=sentinelInventory;body.onJump-=ownedJump;body.onJump-=sentinelJump;}
   if(bodyRoot)UnityEngine.Object.DestroyImmediate(bodyRoot);if(probeRoot)UnityEngine.Object.DestroyImmediate(probeRoot);EditorSceneManager.ClosePreviewScene(scene);
  }
 }
}
