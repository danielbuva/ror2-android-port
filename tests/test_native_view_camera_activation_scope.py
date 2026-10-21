import pathlib
import subprocess
import tempfile
import unittest

REPO = pathlib.Path(__file__).resolve().parents[1]
UNITY_MONO = pathlib.Path("/Applications/Unity/Hub/Editor/2021.3.45f2/Unity.app/Contents/MonoBleedingEdge/bin")


class CameraUpdatePumpTests(unittest.TestCase):
    def test_authored_marker_runs_against_hosted_original_lifecycle_contract(self):
        mcs = UNITY_MONO / "mcs"
        mono = UNITY_MONO / "mono"
        if not mcs.is_file() or not mono.is_file():
            self.skipTest("pinned Unity Mono compiler/runtime unavailable")
        with tempfile.TemporaryDirectory(prefix="camera-update-pump-") as temporary:
            output = pathlib.Path(temporary) / "fixture.exe"
            subprocess.run(
                [
                    str(mcs),
                    "-langversion:7.2",
                    "-out:" + str(output),
                    str(REPO / "tests/fixtures/native_camera/stubs.cs"),
                    str(REPO / "tools/unity/runtime/input/AndroidNativeSourceViewOnlyRigMarker.cs"),
                    str(REPO / "tests/fixtures/native_camera/Program.cs"),
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            completed = subprocess.run([str(mono), str(output)], check=True, capture_output=True, text=True)
            self.assertIn("PASS owned-only original EarlyUpdate pump", completed.stdout)

    def test_owner_waits_for_context_before_set_override(self):
        source = (REPO / "tools/unity/runtime/input/AndroidNativeSourceCameraRigOwner.cs").read_text()
        late_update = source[source.index("    void LateUpdate()") : source.index("    public bool IsOwnedNullViewerRig")]
        context_gate = late_update.index("markerContextReadyMethod.Invoke")
        install = late_update.index("cameraRig.SetOverrideCam(this, 0f)")
        self.assertLess(context_gate, install)
        self.assertIn('"waiting for the owned original CameraRigController update context"', late_update)
        remove = source[source.index("    void RemoveOwnedOverride()") : source.index("    public void GetCameraState")]
        self.assertLess(remove.index("if (!HasOriginalUpdateContext())"), remove.index("cameraRig.SetOverrideCam(null, 0f)"))
        self.assertIn("Destroying the owned rig lets its original OnDestroy clear", remove)
        self.assertIn("RetireOwnedView", late_update)
        retire = source[source.index("    void RetireOwnedView(") : source.index("    bool HasOriginalUpdateContext()")]
        self.assertIn("DisposeOwnedView();", retire)
        self.assertIn("Destroy(retiredRoot)", retire)
        self.assertIn("terminallyRetired = true", retire)
        self.assertNotIn("RoR2Application.onUpdate", source)
        fidelity = source[source.index("    string WithCameraFidelity(") : source.index("    static InvalidOperationException Refuse(")]
        self.assertIn("reduced fidelity: source-prefab defaults; original Console absent", fidelity)
        self.assertIn("return fidelity +", fidelity)
        self.assertLess(len("reduced fidelity: source-prefab defaults; original Console absent"), 160)
        report = (REPO / "tools/unity/runtime/input/AndroidNativeSourceSkinLifecycle.cs").read_text()
        self.assertIn("ShortText(nativeCameraOwner.status, 160)", report)

    def test_transform_verifier_requires_single_owned_original_callback(self):
        source = (REPO / "tools/assembly-transforms/VerifyNativeViewCameraTransform.cs").read_text()
        self.assertIn('x.Name == "TryPumpOriginalEarlyUpdate"', source)
        self.assertIn("System.Void System.Action::Invoke()", source)
        self.assertIn("RoR2.RoR2Application::get_instance()", source)
        self.assertIn("UnityEngine.Behaviour::get_isActiveAndEnabled()", source)


if __name__ == "__main__":
    unittest.main()
