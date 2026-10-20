"""Execute the extracted production ObserveEnemy body against native-lifetime doubles."""

import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "tools/unity/runtime/world/EnemySpineBoundary.cs"
EDITOR_MONO = Path("/Applications/Unity/Hub/Editor/2021.3.45f2/Unity.app/Contents/MonoBleedingEdge")


def extract_method(source, declaration):
    start = source.index(declaration)
    opening = source.index("{", start)
    depth = 0
    for pos in range(opening, len(source)):
        if source[pos] == "{":
            depth += 1
        elif source[pos] == "}":
            depth -= 1
            if depth == 0:
                return source[start : pos + 1]
    raise AssertionError("unclosed production method")


STUBS = r"""
using System;
using UnityEngine;
using RoR2;
namespace UnityEngine {
 public class Object { public bool destroyed; public static implicit operator bool(Object x) { return !ReferenceEquals(x,null) && !x.destroyed; } }
 public class GameObject : Object { public T GetComponent<T>() where T:class { return component as T; } public object component; }
 public class Transform : Object { public Vector3 position; }
 public struct Vector3 { public float x,y,z; public Vector3(float x,float y,float z){this.x=x;this.y=y;this.z=z;} public float magnitude { get { return (float)Math.Sqrt(x*x+y*y+z*z); } } public static Vector3 operator -(Vector3 a,Vector3 b){return new Vector3(a.x-b.x,a.y-b.y,a.z-b.z);} }
 public static class Mathf { public static float Max(float a,float b){return Math.Max(a,b);} }
}
namespace RoR2 {
 public class HealthComponent : UnityEngine.Object { public float health; public bool alive; }
 public class CharacterMotor : UnityEngine.Object { public UnityEngine.Vector3 velocity; public bool isGrounded; }
 public class CharacterBody : UnityEngine.Object { public UnityEngine.GameObject gameObject=new UnityEngine.GameObject(); public UnityEngine.Transform transform=new UnityEngine.Transform(); public CharacterMotor characterMotor; public HealthComponent healthComponent; public int killCountServer; }
 public class BaseAI : UnityEngine.Object { public Target currentEnemy; public EntityStateMachine stateMachine; public class Target { public CharacterBody characterBody; } }
 public class EntityState {}
 public class EntityStateMachine : UnityEngine.Object { public EntityState state; public static EntityStateMachine bodyMachine; public static EntityStateMachine FindByCustomName(UnityEngine.GameObject go,string name){return bodyMachine;} }
 public class Corpse : UnityEngine.Object {}
}
namespace EntityStates.BeetleMonster { public class HeadbuttState : RoR2.EntityState {} }
public sealed class EnemyReport {
 public bool targetFound,dead,naturalBodyDestroyed,naturalMasterDestroyed,preservedCorpseObserved;
 public int aiFrames,headbutts,groundedFrames,groundedBeforeDamage,enemyDamageEvents,playerKillsAfter;
 public float pathLength,planarPathLength,maxFall,planarBeforeDamage,maxFallBeforeDamage,health,playerHealth;
 public string aiState,bodyState;
 public UnityEngine.Vector3 position,spawnPosition,velocity;
}
public sealed class SessionReport { public EnemyReport enemy; }
public sealed class Coordinator {
 public SessionReport r=new SessionReport(); public RoR2.BaseAI enemyAI; public RoR2.CharacterBody enemyBody,enemyPlayer; public UnityEngine.GameObject enemyMasterHost;
 public int rewards, navigation, actors;
 public void ObserveEnemyRewards(){rewards++;} public void ObserveOriginalNavigation(){navigation++;} public void ObserveDirectorActors(){actors++;}
}
public sealed class EnemySpineHost {
 public Coordinator coordinator=new Coordinator(); public RoR2.EntityState priorEnemyState; public UnityEngine.Vector3 priorEnemyPosition; public UnityEngine.GameObject enemyDetachedModel;
"""


class ProductionObserverHostTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mono = EDITOR_MONO / "bin/mono"
        cls.csc = EDITOR_MONO / "lib/mono/msbuild/Current/bin/Roslyn/csc.exe"

    def test_production_observer_tolerates_native_retirement_and_preserves_live_samples(self):
        if not self.mono.exists() or not self.csc.exists():
            self.skipTest("pinned Unity Mono compiler unavailable")
        method = extract_method(SOURCE.read_text(), "public void ObserveEnemy()")
        harness = (
            STUBS
            + method
            + r"""
}
public static class Program {
 static void Need(bool ok,string message){if(!ok)throw new Exception(message);}
 static void Main(){
  // A defeat observer may call this owner when this feature was never prepared.
  var empty=new EnemySpineHost(); empty.ObserveEnemy();
  Need(empty.coordinator.rewards==0 && empty.coordinator.navigation==1 && empty.coordinator.actors==1,"missing enemy report must skip reward sampling but preserve independent nav/director observers");

  // Native-style partial teardown: BaseAI survives but its cached target and state
  // machine are gone; the body remains while its motor/health are gone; the player
  // body remains for a frame after its health component disappears.
  var retiring=new EnemySpineHost(); var report=new EnemyReport { aiFrames=4, dead=true, health=25, playerHealth=80, playerKillsAfter=2, groundedFrames=7, aiState="prior-ai", enemyDamageEvents=0, spawnPosition=new UnityEngine.Vector3(0,10,0) };
  retiring.coordinator.r.enemy=report;
  retiring.coordinator.enemyAI=new RoR2.BaseAI { currentEnemy=null, stateMachine=null };
  retiring.coordinator.enemyBody=new RoR2.CharacterBody { transform=new UnityEngine.Transform { position=new UnityEngine.Vector3(3,7,4) },
    characterMotor=new RoR2.CharacterMotor { destroyed=true }, healthComponent=new RoR2.HealthComponent { destroyed=true } };
  retiring.coordinator.enemyPlayer=new RoR2.CharacterBody { healthComponent=new RoR2.HealthComponent { destroyed=true }, killCountServer=9 };
  RoR2.EntityStateMachine.bodyMachine=null;
  retiring.ObserveEnemy();
  Need(report.aiFrames==5 && report.aiState=="prior-ai" && !report.targetFound,"AI target/state disappearance should be a skipped sample");
  Need(report.bodyState==null && report.position.x==3 && report.pathLength>0,"body position should still sample while unavailable state/motor/health retain prior state");
  Need(report.health==25 && report.playerHealth==80 && report.playerKillsAfter==9,"destroyed health must preserve previous health while remaining fields update");
  Need(report.planarBeforeDamage>0 && report.maxFallBeforeDamage>0,"path/fall samples must continue for a body without a live CharacterMotor");
  Need(report.dead && report.groundedFrames==7 && retiring.coordinator.rewards==1 && retiring.coordinator.navigation==1 && retiring.coordinator.actors==1,"prior observations and sibling observers must remain intact");

  // With native components still live, production observer keeps its successful data path.
  var live=new EnemySpineHost(); var player=new RoR2.CharacterBody { healthComponent=new RoR2.HealthComponent { health=61, alive=true }, killCountServer=3 };
  var body=new RoR2.CharacterBody { transform=new UnityEngine.Transform { position=new UnityEngine.Vector3(0,8,0) },
    characterMotor=new RoR2.CharacterMotor { velocity=new UnityEngine.Vector3(1,0,0), isGrounded=true },
    healthComponent=new RoR2.HealthComponent { health=42, alive=true } };
  var bodyState=new RoR2.EntityStateMachine { state=new EntityStates.BeetleMonster.HeadbuttState() };
  RoR2.EntityStateMachine.bodyMachine=bodyState;
  live.coordinator.r.enemy=new EnemyReport { spawnPosition=new UnityEngine.Vector3(0,10,0) };
  live.coordinator.enemyPlayer=player; live.coordinator.enemyBody=body;
  live.coordinator.enemyAI=new RoR2.BaseAI { currentEnemy=new RoR2.BaseAI.Target { characterBody=player }, stateMachine=new RoR2.EntityStateMachine { state=new RoR2.EntityState() } };
  live.coordinator.enemyMasterHost=new UnityEngine.GameObject(); live.ObserveEnemy();
  Need(live.coordinator.r.enemy.targetFound && live.coordinator.r.enemy.aiFrames==1 && live.coordinator.r.enemy.aiState==typeof(RoR2.EntityState).FullName,"live AI sample");
  Need(live.coordinator.r.enemy.health==42 && live.coordinator.r.enemy.playerHealth==61 && live.coordinator.r.enemy.playerKillsAfter==3,"live health sample");
  Need(live.coordinator.r.enemy.groundedFrames==1 && live.coordinator.r.enemy.groundedBeforeDamage==1 && live.coordinator.r.enemy.headbutts==1,"live motor/state sample");

  // A previously dead actor can lose the body/master/model on separate native frames;
  // the observed corpse signal remains bounded to the known detached model.
  var gone=new EnemySpineHost(); var detached=new UnityEngine.GameObject { component=new RoR2.Corpse() }; gone.enemyDetachedModel=detached;
  gone.coordinator.r.enemy=new EnemyReport { dead=true };
  gone.coordinator.enemyAI=new RoR2.BaseAI { destroyed=true };
  gone.coordinator.enemyBody=new RoR2.CharacterBody { destroyed=true };
  gone.coordinator.enemyPlayer=new RoR2.CharacterBody { destroyed=true };
  gone.coordinator.enemyMasterHost=new UnityEngine.GameObject { destroyed=true };
  gone.ObserveEnemy();
  Need(gone.coordinator.r.enemy.naturalBodyDestroyed && gone.coordinator.r.enemy.naturalMasterDestroyed && gone.coordinator.r.enemy.preservedCorpseObserved,"destroyed body/AI/master and retained corpse observation");
  // A live AI with a native target wrapper that has not yet selected a target is normal.
  var noTarget=new EnemySpineHost(); noTarget.coordinator.r.enemy=new EnemyReport(); noTarget.coordinator.enemyAI=new RoR2.BaseAI { currentEnemy=null };
  noTarget.ObserveEnemy(); Need(noTarget.coordinator.r.enemy.aiFrames==1 && !noTarget.coordinator.r.enemy.targetFound,"null currentEnemy is an unavailable target sample");
  Console.WriteLine("production_observer_native_retirement_cases=5; live_sample_preserved=true; native_execution_claimed=false");
 }
}
"""
        )
        with tempfile.TemporaryDirectory() as temp:
            scratch = Path(temp)
            source = scratch / "ObserverHost.cs"
            output = scratch / "ObserverHost.exe"
            source.write_text(harness)
            compiled = subprocess.run(
                [str(self.mono), str(self.csc), "-nologo", "-langversion:9", "-out:" + str(output), str(source)], cwd=scratch, capture_output=True, text=True
            )
            self.assertEqual(compiled.returncode, 0, compiled.stdout + compiled.stderr)
            executed = subprocess.run([str(self.mono), str(output)], cwd=scratch, capture_output=True, text=True)
            self.assertEqual(executed.returncode, 0, executed.stdout + executed.stderr)
            self.assertIn("production_observer_native_retirement_cases=5", executed.stdout)


if __name__ == "__main__":
    unittest.main()
