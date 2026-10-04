using RoR2.Projectile;
using UnityEngine;

// Unity normalizes serialized null strings on clone. Set the original no-event branch on the instance.
[DefaultExecutionOrder(-20000)]
public sealed class SilentProjectileBoundary : MonoBehaviour {
 public static int prepared;
 void Awake(){GetComponent<ProjectileController>().startSound=null;prepared++;}
}
