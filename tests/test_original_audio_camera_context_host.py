"""Execute the production context decisions and release body without an editor."""

from pathlib import Path
import os
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
EDITOR = Path(os.environ.get("UNITY_EDITOR_PATH", "/Applications/Unity/Hub/Editor/2021.3.45f2/Unity.app/Contents"))
MONO = EDITOR / "MonoBleedingEdge/bin/mono"
CSC = EDITOR / "MonoBleedingEdge/lib/mono/msbuild/Current/bin/Roslyn/csc.exe"


def extract_method(source, signature):
    start = source.index(signature)
    opening = source.index("{", start)
    depth = 0
    for index in range(opening, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[start : index + 1]
    raise AssertionError(f"unterminated method: {signature}")


def extract_release(source):
    start = source.index("    public void ReleaseAudioContext()")
    opening = source.index("{", start)
    depth = 0
    for index in range(opening, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[start : index + 1]
    raise AssertionError("unterminated production release method")


class OriginalAudioCameraContextHostTests(unittest.TestCase):
    def test_production_lifecycle_and_release(self):
        if not MONO.is_file() or not CSC.is_file():
            self.skipTest("pinned Unity Mono/Roslyn unavailable")
        method = extract_release((ROOT / "tools/unity/runtime/input/AndroidNativeSourceCameraRigOwner.cs").read_text())
        # Only Unity lifetime and list observations are synthetic. The executed
        # decision helper and release method are the actual production bodies.
        release = (
            r"""using System;
class Handle { public static implicit operator bool(Handle value) { return !ReferenceEquals(value, null); } }
class GameObject : Handle { public bool activeSelf = true; }
class Camera : Handle { public bool enabled; }
class Rig : Handle { public bool hasOverride; }
class ProductionRelease
{
    public bool audioContextOnly = true, audioContextReady = true, terminallyRetired;
    bool audioContextReleaseStarted;
    public bool audioContextReleasePreparedForDestroy, audioContextDestroyRequested;
    public bool capturedGlobalSceneCamera, membershipKnown = true, membershipPresent;
    bool sourceDefaultListenerTeardownObserved, managedSourceDefaultListenerPresentAfterDisableCaptured;
    bool managedSourceDefaultListenerPresentAfterDisable;
    public GameObject stagingRoot = new GameObject();
    Camera viewCamera = new Camera();
    Rig cameraRig = new Rig();
    public int disposeCalls, destroyRequests;
    void DisposeOwnedView() {
        disposeCalls++;
        stagingRoot.activeSelf = false;
        sourceDefaultListenerTeardownObserved = true;
        managedSourceDefaultListenerPresentAfterDisableCaptured = membershipKnown;
        managedSourceDefaultListenerPresentAfterDisable = membershipPresent;
    }
    void Destroy(GameObject target) {
        if (!ReferenceEquals(target, stagingRoot)) throw new Exception("foreign destroy");
        destroyRequests++;
    }
    bool TryReadExactManagedListenerMembership(out bool present) { present = membershipPresent; return membershipKnown; }
"""
            + method
            + "\n}\n"
        )
        with tempfile.TemporaryDirectory(prefix="audio-context-host-") as name:
            temp = Path(name)
            extracted = temp / "ProductionRelease.cs"
            extracted.write_text(release)
            executable = temp / "AudioContext.exe"
            compiled = subprocess.run(
                [
                    str(MONO),
                    str(CSC),
                    "-nologo",
                    "-langversion:latest",
                    "-target:exe",
                    f"-out:{executable}",
                    str(ROOT / "tools/unity/runtime/input/AndroidNativeSourceCameraRigContract.cs"),
                    str(ROOT / "tests/fixtures/native_camera/AudioContextLifecycleProgram.cs"),
                    str(extracted),
                ],
                capture_output=True,
                text=True,
                timeout=60,
            )
            self.assertEqual(compiled.returncode, 0, compiled.stdout + compiled.stderr)
            ran = subprocess.run([str(MONO), str(executable)], capture_output=True, text=True, timeout=30)
            self.assertEqual(ran.returncode, 0, ran.stdout + ran.stderr)
            self.assertIn("production release checks", ran.stdout)
            self.assertIn("31 camera Start-window decisions and report projections", ran.stdout)

    def test_start_window_and_report_are_wired_to_live_sampled_operands(self):
        owner = (ROOT / "tools/unity/runtime/input/AndroidNativeSourceCameraRigOwner.cs").read_text()
        late = extract_method(owner, "    void LateUpdate()")
        self.assertIn("bool rigActiveAndEnabled = cameraRig.isActiveAndEnabled", late)
        self.assertIn("bool rigActiveInHierarchy = cameraRig.gameObject.activeInHierarchy", late)
        self.assertIn("bool cameraModeIsPlayerBasic = !cameraModeIsNull &&", late)
        self.assertIn("audioContextRigActiveAndEnabled = rigActiveAndEnabled", late)
        self.assertIn("audioContextRigActiveInHierarchy = rigActiveInHierarchy", late)
        self.assertIn("IsValidStartupClock(", late)
        self.assertIn("audioContextStartupDeadlineExpired =", late)
        world = (ROOT / "tools/unity/runtime/world/IntegratedWorldBoundary.cs").read_text()
        observe = extract_method(world, "        void ObserveOriginalAudioCameraContext()")
        self.assertIn("CreateStartObservation(", observe)
        self.assertIn("startObservation.rigActiveAndEnabled", observe)
        self.assertIn("startObservation.rigActiveInHierarchy", observe)
        self.assertIn("audioContextStartupClockValid", observe)
        self.assertIn("audioContextStartupDeadlineExpired", observe)
        self.assertIn("audioContextRigActiveAndEnabledObserved", observe)
        self.assertIn("audioContextRigActiveInHierarchyObserved", observe)


if __name__ == "__main__":
    unittest.main()
