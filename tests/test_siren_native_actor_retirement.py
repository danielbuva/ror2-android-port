"""Exercise actual Siren actor death observation and retirement with host doubles."""

from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "tools/unity/runtime/stage/SirenEncounterBoundary.cs"
EDITOR = Path("/Applications/Unity/Hub/Editor/2021.3.45f2/Unity.app/Contents/MonoBleedingEdge")


def declaration(source, marker):
    start = source.index(marker)
    opening = source.index("{", start)
    depth = 0
    for index in range(opening, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[start : index + 1]
    raise AssertionError("unclosed " + marker)


STUBS = r"""
using System; using System.Collections.Generic; using System.Linq;
public class UObject { public bool exists=true; public static implicit operator bool(UObject o) => !ReferenceEquals(o,null)&&o.exists; }
public struct NetworkInstanceId {
 public uint Value; public NetworkInstanceId(uint value){Value=value;} public static NetworkInstanceId Invalid => new NetworkInstanceId(0);
 public static bool operator ==(NetworkInstanceId a,NetworkInstanceId b)=>a.Value==b.Value;
 public static bool operator !=(NetworkInstanceId a,NetworkInstanceId b)=>a.Value!=b.Value;
 public override bool Equals(object o)=>o is NetworkInstanceId id&&Value==id.Value; public override int GetHashCode()=>(int)Value;
}
public class GameObject:UObject {
 public int scene=1; public uint id; public NetworkIdentity identity; public HealthComponent health;
 public T GetComponent<T>() where T:class => typeof(T)==typeof(NetworkIdentity)?identity as T:health as T;
}
public class NetworkIdentity:UObject { public NetworkInstanceId netId; public bool isServer=true; }
public class HealthComponent:UObject { public bool alive; }
public enum TeamIndex { Player, Monster }
public class MinionOwnership:UObject { public NetworkInstanceId NetworkownerMasterId; }
public class CharacterMaster:UObject {
 public GameObject gameObject,bodyPrefab; public NetworkInstanceId netId; public TeamIndex teamIndex=TeamIndex.Monster;
 public UObject playerCharacterMasterController; public MinionOwnership minionOwnership; public CharacterBody body;
 public bool terminal=true; public bool IsDeadAndOutOfLivesServer()=>terminal; public CharacterBody GetBody()=>body;
}
public class CharacterBody:UObject { public GameObject gameObject; public CharacterMaster master; public int bodyIndex; }
public class DamageReport { public CharacterBody victimBody; public HealthComponent victim; public CharacterMaster victimMaster; }
public static class BodyCatalog {
 public static readonly GameObject Boss=new GameObject(),Probe=new GameObject();
 public static GameObject FindBodyPrefab(string n)=>n=="Boss"?Boss:Probe; public static int FindBodyIndex(string n)=>n=="Boss"?1:2;
}
public static class NetworkServer {
 public static bool active=true; public static uint FailDestroyId;
 public static readonly Dictionary<uint,GameObject> Objects=new Dictionary<uint,GameObject>();
 public static readonly Dictionary<uint,int> DestroyCalls=new Dictionary<uint,int>();
 public static GameObject FindLocalObject(NetworkInstanceId id)=>Objects.TryGetValue(id.Value,out var o)?o:null;
 public static void Destroy(GameObject body) {
  DestroyCalls[body.id]=DestroyCalls.ContainsKey(body.id)?DestroyCalls[body.id]+1:1;
  if(FailDestroyId==body.id)throw new InvalidOperationException("injected destroy failure");
  Objects.Remove(body.id);body.exists=false;if(body.identity!=null)body.identity.exists=false;if(body.health!=null)body.health.exists=false;
 }
}
public class CombatSquad:UObject { public List<CharacterMaster> readOnlyMembersList=new List<CharacterMaster>(); }
public class ScriptedCombatEncounter:UObject { public CombatSquad combatSquad=new CombatSquad(); }
public class ReportData {
 public bool retirementRefusedForeignMember,retirementRequestsIssued,retirementPreflightPassed;
 public int encounterSquadMembersAtCleanup;
 public int retiredBossBodiesRequested,retiredBossMastersRequested,retiredProbeBodiesRequested,retiredProbeMastersRequested;
 public int naturallyRetiredBossMasters,naturallyRetiredProbeMasters;
}
public class Harness {
 const string OriginalBossBodyName="Boss",OriginalProbeBodyName="Probe";
 int scene=1; bool disposed,cleanupStarted,ownsActivatedSceneInstance=true; ReportData Report=new ReportData();
 ScriptedCombatEncounter encounter=new ScriptedCombatEncounter(); readonly HashSet<uint> ownedBossNetworkIds=new HashSet<uint>();
 readonly List<OwnedMaster> ownedBossMasters=new List<OwnedMaster>(),ownedProbeMasters=new List<OwnedMaster>();
"""

CASES = r"""
 static void Need(bool value,string message){if(!value)throw new Exception(message);}
 static void Refuses(Action action,string message){bool refused=false;try{action();}catch(InvalidOperationException){refused=true;}Need(refused,message);}
 OwnedMaster Add(uint id,bool probe=false) {
  var root=new GameObject{id=id};var body=new GameObject{id=id+1000,identity=new NetworkIdentity{netId=new NetworkInstanceId(id+1000)},health=new HealthComponent()};
  var master=new CharacterMaster{gameObject=root,netId=new NetworkInstanceId(id),bodyPrefab=probe?BodyCatalog.Probe:BodyCatalog.Boss};
  var character=new CharacterBody{gameObject=body,master=master,bodyIndex=probe?2:1};master.body=character;
  var row=new OwnedMaster{master=master,networkId=master.netId};
  if(probe){row.ownerNetworkId=new NetworkInstanceId(77);master.minionOwnership=new MinionOwnership{NetworkownerMasterId=row.ownerNetworkId};ownedProbeMasters.Add(row);}
  else {ownedBossMasters.Add(row);ownedBossNetworkIds.Add(id); }
  NetworkServer.Objects[id]=root;NetworkServer.Objects[id+1000]=body;return row;
 }
 DamageReport Damage(OwnedMaster row)=>new DamageReport{victimMaster=row.master,victimBody=row.master.body,victim=row.master.body.gameObject.health};
 void KillMaster(OwnedMaster row){row.master.exists=false;row.master.gameObject.exists=false;NetworkServer.Objects.Remove(row.networkId.Value);}
 void KillBody(OwnedMaster row){var body=row.deathBody;body.exists=false;body.identity.exists=false;body.health.exists=false;NetworkServer.Objects.Remove(body.id);}
 static void Main() {
  // A terminal original death is necessary; no observed event manufactures destruction.
  var natural=new Harness();var row=natural.Add(1);var damage=natural.Damage(row);
  damage.victim.alive=true;natural.OnNativeActorDeath(damage);Need(!row.nativeDeathObserved,"living victim accepted");damage.victim.alive=false;
  row.master.terminal=false;natural.OnNativeActorDeath(damage);Need(!row.nativeDeathObserved,"revivable death accepted");row.master.terminal=true;
  natural.cleanupStarted=true;natural.OnNativeActorDeath(damage);Need(!row.nativeDeathObserved,"cleanup death accepted");natural.cleanupStarted=false;
  natural.disposed=true;natural.OnNativeActorDeath(damage);Need(!row.nativeDeathObserved,"disposed death accepted");natural.disposed=false;
  NetworkServer.active=false;natural.OnNativeActorDeath(damage);Need(!row.nativeDeathObserved,"client death accepted");NetworkServer.active=true;
  natural.OnNativeActorDeath(damage);Need(row.nativeDeathObserved,"exact native terminal death not captured");
  Refuses(()=>natural.ValidateNaturallyDestroyedMaster(row),"death alone accepted as destroyed master");
  natural.KillMaster(row);natural.KillBody(row);
  natural.ValidateOwnedMaster(row,"Boss",NetworkInstanceId.Invalid,"boss");natural.RequestDestroy(row,false);natural.RequestDestroy(row,false);
  Need(row.naturallyRetired&&!row.masterDestroyRequestCompleted&&natural.Report.naturallyRetiredBossMasters==1,"native master misreported or counted twice");
  Need(!NetworkServer.DestroyCalls.ContainsKey(1)&&!NetworkServer.DestroyCalls.ContainsKey(1001),"naturally destroyed actor destroyed again");

  // Master destruction may precede corpse retirement; only that captured dead corpse is cleaned.
  var corpse=new Harness();var corpseRow=corpse.Add(2);corpse.OnNativeActorDeath(corpse.Damage(corpseRow));corpse.KillMaster(corpseRow);
  corpse.ValidateOwnedMaster(corpseRow,"Boss",NetworkInstanceId.Invalid,"boss");corpse.RequestDestroy(corpseRow,false);corpse.RequestDestroy(corpseRow,false);
  Need(NetworkServer.DestroyCalls[1002]==1&&!NetworkServer.DestroyCalls.ContainsKey(2),"corpse/master destroy ownership changed");
  Need(corpse.Report.retiredBossBodiesRequested==1&&corpse.Report.retiredBossMastersRequested==0&&corpse.Report.naturallyRetiredBossMasters==1,"corpse request attribution wrong");

  var probe=new Harness();var probeRow=probe.Add(3,true);probe.OnNativeActorDeath(probe.Damage(probeRow));probe.KillMaster(probeRow);probe.KillBody(probeRow);probe.RequestDestroy(probeRow,true);
  Need(probe.Report.naturallyRetiredProbeMasters==1&&probe.Report.naturallyRetiredBossMasters==0,"probe retirement attributed as boss");

  // Every unknown/replaced native operand must refuse before any destructive request.
  for(int change=0;change<9;change++) {
   var bad=new Harness();var entry=bad.Add((uint)(10+change));bad.OnNativeActorDeath(bad.Damage(entry));bad.KillMaster(entry);
   if(change==0)entry.nativeDeathObserved=false;
   if(change==1)NetworkServer.Objects[entry.networkId.Value]=new GameObject();
   if(change==2)NetworkServer.Objects[entry.deathBodyId.Value]=new GameObject();
   if(change==3)entry.deathHealth.alive=true;
   if(change==4)entry.deathBody.identity=new NetworkIdentity{netId=entry.deathBodyId};
   if(change==5)entry.deathBody.health=new HealthComponent();
   if(change==6)entry.deathBody.scene=2;
   if(change==7){entry.deathBody.exists=false;}
   if(change==8){bad.KillBody(entry);NetworkServer.Objects[entry.deathBodyId.Value]=new GameObject();}
   Refuses(()=>bad.RequestDestroy(entry,false),"unknown/replaced native actor accepted "+change);
   Need(!entry.naturallyRetired&&bad.Report.naturallyRetiredBossMasters==0&&!NetworkServer.DestroyCalls.ContainsKey(entry.deathBodyId.Value),"refusal mutated actor "+change);
  }
  for(int change=0;change<6;change++) {
   var bad=new Harness();var entry=bad.Add((uint)(30+change),true);var report=bad.Damage(entry);
   if(change==0)report.victimMaster=new CharacterMaster();
   if(change==1)report.victim=new HealthComponent();
   if(change==2)entry.master.teamIndex=TeamIndex.Player;
   if(change==3)entry.master.minionOwnership.NetworkownerMasterId=new NetworkInstanceId(999);
   if(change==4)report.victimBody.bodyIndex=99;
   if(change==5)NetworkServer.Objects[entry.master.body.gameObject.id]=new GameObject();
   bad.OnNativeActorDeath(report);Need(!entry.nativeDeathObserved,"foreign death authorized retirement "+change);
  }
  var retry=new Harness();var retryRow=retry.Add(4);retry.OnNativeActorDeath(retry.Damage(retryRow));retry.KillMaster(retryRow);
  NetworkServer.FailDestroyId=1004;Refuses(()=>retry.RequestDestroy(retryRow,false),"injected corpse destroy did not fail");
  Need(!retryRow.naturallyRetired&&retry.Report.naturallyRetiredBossMasters==0,"failed request advanced retirement");
  NetworkServer.FailDestroyId=0;retry.RequestDestroy(retryRow,false);retry.RequestDestroy(retryRow,false);
  Need(NetworkServer.DestroyCalls[1004]==2&&retry.Report.retiredBossBodiesRequested==1&&retry.Report.naturallyRetiredBossMasters==1,"exact corpse retry lost progress");
  var live=new Harness();var liveRow=live.Add(5);live.ValidateOwnedMaster(liveRow,"Boss",NetworkInstanceId.Invalid,"boss");live.RequestDestroy(liveRow,false);live.RequestDestroy(liveRow,false);
  Need(NetworkServer.DestroyCalls[5]==1&&NetworkServer.DestroyCalls[1005]==1&&live.Report.naturallyRetiredBossMasters==0,"existing live cleanup changed");
  var squad=new Harness();var boss=squad.Add(77);var minion=squad.Add(79,true);
  squad.OnNativeActorDeath(squad.Damage(boss));squad.KillMaster(boss);squad.KillBody(boss);
  squad.encounter.combatSquad.readOnlyMembersList.Add(new CharacterMaster());
  Refuses(squad.RetireEncounterSquadMembers,"foreign squad member accepted");
  Need(!NetworkServer.DestroyCalls.ContainsKey(79)&&!NetworkServer.DestroyCalls.ContainsKey(1079),"foreign member refusal mutated another actor");
  squad.encounter.combatSquad.readOnlyMembersList.Clear();squad.RetireEncounterSquadMembers();squad.RetireEncounterSquadMembers();
  Need(squad.Report.retirementPreflightPassed&&squad.Report.naturallyRetiredBossMasters==1&&squad.Report.retiredProbeMastersRequested==1,
    "whole mixed natural/live actor cohort failed preflight/retirement");
  Need(NetworkServer.DestroyCalls[79]==1&&NetworkServer.DestroyCalls[1079]==1&&!NetworkServer.DestroyCalls.ContainsKey(77),"whole squad double-retired a native master");
  Console.WriteLine("native-actor-retirement-contracts-passed");
 }
}
"""


class SirenNativeActorRetirementTests(unittest.TestCase):
    def test_production_observation_validation_and_requests(self):
        mono = EDITOR / "bin/mono"
        csc = EDITOR / "lib/mono/msbuild/Current/bin/Roslyn/csc.exe"
        if not mono.is_file() or not csc.is_file():
            self.skipTest("pinned Unity Mono/Roslyn unavailable")
        source = SOURCE.read_text()
        markers = [
            "sealed class OwnedMaster",
            "void OnNativeActorDeath(",
            "void CaptureNativeActorDeath(",
            "void ValidateNaturallyDestroyedMaster(",
            "void ValidateOwnedMaster(",
            "void RequestDestroy(",
            "void RetireEncounterSquadMembers()",
        ]
        code = STUBS + "\n".join(declaration(source, marker) for marker in markers) + CASES
        with tempfile.TemporaryDirectory(prefix="siren-native-retirement-") as folder:
            root = Path(folder)
            cs, exe = root / "contract.cs", root / "contract.exe"
            cs.write_text(code)
            compile_result = subprocess.run([str(mono), str(csc), "-nologo", "-langversion:9", f"-out:{exe}", str(cs)], capture_output=True, text=True)
            self.assertEqual(compile_result.returncode, 0, compile_result.stdout + compile_result.stderr)
            result = subprocess.run([str(mono), str(exe)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("native-actor-retirement-contracts-passed", result.stdout)

    def test_owned_subscription_retires_before_actor_mutation(self):
        source = SOURCE.read_text()
        release = declaration(source, "void Release()")
        self.assertLess(release.index("GlobalEventManager.onCharacterDeathServer -= OnNativeActorDeath"), release.index("RetireEncounterSquadMembers"))
        callback = declaration(source, "void OnNativeActorDeath(") + declaration(source, "void CaptureNativeActorDeath(")
        for forbidden in ("TakeDamage", "Suicide", "Destroy(", "BeginEncounter(", "SetOwner("):
            self.assertNotIn(forbidden, callback)


if __name__ == "__main__":
    unittest.main()
