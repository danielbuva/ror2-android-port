using System;
using System.Linq;
using System.Reflection;
namespace UnityEngine {
 public sealed class DefaultExecutionOrder : Attribute {public DefaultExecutionOrder(int order) {}}
 public class MonoBehaviour {public bool enabled;public object fixtureComponent;protected T GetComponent<T>() where T:class {return fixtureComponent as T;}}
}
namespace RoR2.Projectile {public sealed class ProjectileController {public string startSound;}}
public static class GameAudioOriginalOwner {public static bool Ready;}
public sealed class AkSource : UnityEngine.MonoBehaviour {}
public sealed class OtherSource : UnityEngine.MonoBehaviour {}
public sealed class Body {
 public UnityEngine.MonoBehaviour[] components;
 public T[] GetComponents<T>() {return components.Cast<T>().ToArray();}
}
public static class SourceAudioContract {
 static void Need(bool value,string message) {if(!value)throw new Exception(message);}
 static int PreserveRoot(Body body) {__ROOT_LOOP__ return preservedAudioRootCallbacks;}
 public static void Main() {
  foreach(bool ready in new[]{false,true}) {
   GameAudioOriginalOwner.Ready=ready;
   var first=new AkSource {enabled=true};var second=new AkSource {enabled=false};var other=new OtherSource {enabled=true};
   int count=PreserveRoot(new Body {components=new UnityEngine.MonoBehaviour[]{first,second,other}});
   Need(count==(ready?1:0)&&first.enabled==ready&&!second.enabled&&!other.enabled,"authored root audio only; no new enable and other callbacks remain controlled");
   foreach(string name in new[]{"native-flight","",null}) {
    var instance=new RoR2.Projectile.ProjectileController {startSound=name};
    var boundary=new SilentProjectileBoundary {fixtureComponent=instance};int before=SilentProjectileBoundary.prepared;
    typeof(SilentProjectileBoundary).GetMethod("Awake",BindingFlags.NonPublic|BindingFlags.Instance).Invoke(boundary,null);
    Need(instance.startSound==(ready&&!string.IsNullOrEmpty(name)?name:null),"source flight event or original absent-event branch");
    Need(SilentProjectileBoundary.prepared==before+1,"one boundary callback");
   }
  }
 }
}
