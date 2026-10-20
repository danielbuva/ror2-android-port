"""Execute the production Siren retirement method and cleanup cursor with host doubles."""

import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OWNER = ROOT / "tools/unity/runtime/stage/SirenSourceEntrySession.cs"
CLEANUP = ROOT / "tools/unity/runtime/stage/SirenEncounterBoundary.cs"
EDITOR = Path("/Applications/Unity/Hub/Editor/2021.3.45f2/Unity.app/Contents/MonoBleedingEdge")

FIXTURE = r"""
public class OwnerHarness
{
    sealed class SourceEgg
    {
        public bool selected = true, observed = true, retired;
        public GameObject body;
        public NetworkIdentity identity;
        public NetworkInstanceId networkId;
        public Vector3 expectedPosition;
        public Quaternion expectedRotation;
    }
    sealed class Report { public bool exactEggBijection = true; public int retiredEggCount; }
    readonly System.Collections.Generic.List<SourceEgg> sourceEggs = new System.Collections.Generic.List<SourceEgg>();
    readonly Report report = new Report();
    bool globalDispatchAttempted = true, complete = true, captureFailure;
    static void Assert(bool condition, string message) { if (!condition) throw new System.Exception(message); }
    void VerifyNoUntrackedSourceEggs() { }

    static void Main()
    {
        var recoverable = new OwnerHarness();
        SourceEgg one = recoverable.Add(1), two = recoverable.Add(2), three = recoverable.Add(3);
        NetworkServer.FailUnSpawnId = 2;
        int cursor = 0; System.Exception first = null, step;
        System.Action retire = recoverable.RetireOwnedEggs;
        Assert(!SirenEncounterContract.TryAdvanceCleanupStep(ref cursor, 0, retire, ref first, out step),
            "later source egg failure must retain cleanup step");
        Assert(cursor == 0 && three.retired && !three.body && two.body && one.body && recoverable.report.retiredEggCount == 1,
            "successful earlier retirement must remain an exact local completion");
        NetworkServer.FailUnSpawnId = 0;
        Assert(SirenEncounterContract.TryAdvanceCleanupStep(ref cursor, 0, retire, ref first, out step),
            "retry must finish known remaining source cohort");
        Assert(cursor == 1 && one.retired && two.retired && three.retired && recoverable.report.retiredEggCount == 3,
            "retry progress/report must include every source egg once");
        Assert(NetworkServer.UnSpawnCalls[1] == 1 && NetworkServer.UnSpawnCalls[2] == 2 && NetworkServer.UnSpawnCalls[3] == 1,
            "retry must skip the completed row and retry only the failed row");
        Assert(UnityEngine.Object.DestroyCalls[1] == 1 && UnityEngine.Object.DestroyCalls[2] == 1 && UnityEngine.Object.DestroyCalls[3] == 1,
            "completed egg roots must never be destroyed twice");

        var uncertain = new OwnerHarness();
        SourceEgg four = uncertain.Add(4), five = uncertain.Add(5);
        UnityEngine.Object.FailDestroyId = 4;
        int uncertainCursor = 0; System.Exception uncertainFirst = null, uncertainFailure;
        System.Action uncertainRetire = uncertain.RetireOwnedEggs;
        Assert(!SirenEncounterContract.TryAdvanceCleanupStep(ref uncertainCursor, 0, uncertainRetire,
            ref uncertainFirst, out uncertainFailure), "destruction failure after unspawn must retain step");
        Assert(five.retired && !five.body && !four.retired && four.body &&
            NetworkServer.FindLocalObject(four.networkId) == null, "uncertain row must retain explicit partial state");
        int uncertainDestroyCalls = UnityEngine.Object.DestroyCalls[4];
        UnityEngine.Object.FailDestroyId = 0;
        Assert(!SirenEncounterContract.TryAdvanceCleanupStep(ref uncertainCursor, 0, uncertainRetire,
            ref uncertainFirst, out uncertainFailure), "unmapped unretired row must refuse blind destruction retry");
        Assert(uncertainCursor == 0 && UnityEngine.Object.DestroyCalls[4] == uncertainDestroyCalls &&
            uncertain.report.retiredEggCount == 1, "unknown row must remain retained without destructive retry or overcount");

        var moved = new OwnerHarness(); SourceEgg six = moved.Add(6); six.identity.transform.position = new Vector3(2, 0, 0);
        bool refused = false;
        try { moved.RetireOwnedEggs(); } catch (System.InvalidOperationException) { refused = true; }
        Assert(refused && !six.retired && six.body && !UnityEngine.Object.DestroyCalls.ContainsKey(6),
            "moved unretired captured egg must refuse native destruction");
        System.Console.WriteLine("production-partial-retirement-retry-passed");
    }
    SourceEgg Add(uint id)
    {
        var body = new GameObject { Id = id };
        var identity = new NetworkIdentity { netId = new NetworkInstanceId(id), isServer = true };
        var row = new SourceEgg { body = body, identity = identity, networkId = identity.netId,
            expectedPosition = identity.transform.position, expectedRotation = identity.transform.rotation };
        sourceEggs.Add(row); NetworkServer.Register(row.networkId, row.body); return row;
    }
"""


def declaration(source, marker):
    start = source.index(marker)
    opening = source.index("{", start)
    depth = 0
    for i in range(opening, len(source)):
        if source[i] == "{":
            depth += 1
        elif source[i] == "}":
            depth -= 1
            if depth == 0:
                return source[start : i + 1]
    raise AssertionError("unterminated " + marker)


STUBS = r"""
using System; using System.Collections.Generic; using System.Linq;
public struct NetworkInstanceId { public uint Value; public NetworkInstanceId(uint value) { Value = value; }
    public static bool operator ==(NetworkInstanceId a, NetworkInstanceId b) => a.Value == b.Value;
    public static bool operator !=(NetworkInstanceId a, NetworkInstanceId b) => a.Value != b.Value;
    public override bool Equals(object value) => value is NetworkInstanceId other && other.Value == Value;
    public override int GetHashCode() => (int)Value; }
public struct Vector3 { public float x,y,z; public Vector3(float a,float b,float c){x=a;y=b;z=c;} public static Vector3 operator -(Vector3 a, Vector3 b) => new Vector3{x=a.x-b.x,y=a.y-b.y,z=a.z-b.z};
    public float sqrMagnitude => x*x+y*y+z*z; }
public struct Quaternion { public static float Angle(Quaternion a, Quaternion b) => 0f; }
public sealed class Transform { public Vector3 position; public Quaternion rotation; }
public sealed class GameObject { public uint Id; public bool alive=true; public static implicit operator bool(GameObject value) => value != null && value.alive;
    public static bool operator !(GameObject value) => !(bool)value; }
public sealed class NetworkIdentity { public NetworkInstanceId netId; public bool isServer, alive=true; public Transform transform = new Transform();
    public static implicit operator bool(NetworkIdentity value) => value != null && value.alive; public static bool operator !(NetworkIdentity value) => !(bool)value; }
public static class NetworkServer { public static bool active=true; public static uint FailUnSpawnId;
    public static readonly Dictionary<uint,GameObject> Objects=new Dictionary<uint,GameObject>();
    public static readonly Dictionary<uint,int> UnSpawnCalls=new Dictionary<uint,int>();
    public static void Register(NetworkInstanceId id, GameObject body) => Objects[id.Value]=body;
    public static GameObject FindLocalObject(NetworkInstanceId id) => Objects.TryGetValue(id.Value,out var value) ? value : null;
    public static void UnSpawn(GameObject body) { UnSpawnCalls[body.Id]=UnSpawnCalls.ContainsKey(body.Id)?UnSpawnCalls[body.Id]+1:1;
        if(body.Id==FailUnSpawnId) throw new InvalidOperationException("injected UnSpawn failure"); Objects.Remove(body.Id); } }
namespace UnityEngine { public static class Object { public static uint FailDestroyId;
    public static readonly System.Collections.Generic.Dictionary<uint,int> DestroyCalls=new System.Collections.Generic.Dictionary<uint,int>();
    public static void DestroyImmediate(GameObject body) { DestroyCalls[body.Id]=DestroyCalls.ContainsKey(body.Id)?DestroyCalls[body.Id]+1:1;
        if(body.Id==FailDestroyId) throw new System.InvalidOperationException("injected destroy failure"); body.alive=false; } } }
public static class SirenSourceEntryContract {
"""


class SirenPartialRetirementTests(unittest.TestCase):
    def test_production_retirement_method_and_cursor_resume_exact_progress(self):
        mono = EDITOR / "bin/mono"
        csc = EDITOR / "lib/mono/msbuild/Current/bin/Roslyn/csc.exe"
        if not mono.is_file() or not csc.is_file():
            self.skipTest("pinned Unity Mono/Roslyn unavailable")
        owner = OWNER.read_text()
        cleanup = CLEANUP.read_text()
        methods = [
            declaration(owner, "public static bool PendingEggRowsAtCapturedPose<"),
            declaration(owner, "public static void RetirePendingEggRows<"),
            declaration(owner, "public static bool MayRetireSourceEggs("),
        ]
        method = declaration(owner, "void RetireOwnedEggs()")
        pose = declaration(owner, "static bool IsEggAtCapturedSpawnPose(SourceEgg row)")
        cursor = declaration(cleanup, "public static bool TryAdvanceCleanupStep(")
        code = STUBS + "\n".join(methods) + "\n}\npublic static class SirenEncounterContract {\n" + cursor + "\n}\n" + FIXTURE + method + pose + "}\n"
        with tempfile.TemporaryDirectory(prefix="siren-production-retry-") as temp:
            root = Path(temp)
            source = root / "fixture.cs"
            output = root / "fixture.exe"
            source.write_text(code)
            compiled = subprocess.run(
                [str(mono), str(csc), "-nologo", "-langversion:9", "-out:" + str(output), str(source)], cwd=root, capture_output=True, text=True
            )
            self.assertEqual(compiled.returncode, 0, compiled.stdout + compiled.stderr)
            executed = subprocess.run([str(mono), str(output)], cwd=root, capture_output=True, text=True)
            self.assertEqual(executed.returncode, 0, executed.stdout + executed.stderr)
            self.assertIn("production-partial-retirement-retry-passed", executed.stdout)
