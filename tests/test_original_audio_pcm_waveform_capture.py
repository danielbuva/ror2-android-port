from __future__ import annotations

import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = ROOT
UNITY = (
    Path(
        os.environ.get(
            "UNITY_EDITOR_PATH",
            "/Applications/Unity/Hub/Editor/2021.3.45f2/Unity.app/Contents",
        )
    )
    / "MonoBleedingEdge"
)
MONO = UNITY / "bin/mono"
CSC = UNITY / "lib/mono/msbuild/Current/bin/Roslyn/csc.exe"
AUDIO = SOURCE_ROOT / "tools/unity/support/audio"
BOOTSTRAP = AUDIO / "bootstrap"
CORE = AUDIO / "core"
SESSION = SOURCE_ROOT / "tools/unity/runtime/session"
HARNESS = SOURCE_ROOT / "tests/PcmWaveformCaptureFinalizerHarness.cs"
TARGET_CAPTURE_STUBS = ROOT / "tests/fixtures/target_capture_session_compile_stubs.cs"


class PcmWaveformCaptureIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not MONO.is_file() or not CSC.is_file():
            raise unittest.SkipTest("pinned Unity 2021.3.45f2 Mono/Roslyn compiler unavailable")

    def test_actual_preterm_window_readback_and_postterm_persistence(self) -> None:
        sources = [
            CORE / "GameAudioOriginalPassivePcmContract.cs",
            CORE / "GameAudioOriginalReadiness.cs",
            CORE / "GameAudioOriginalOwner.cs",
            CORE / "PointSoundDiagnosticObserver.cs",
            CORE / "OriginalOwnerProbeObserver.cs",
            BOOTSTRAP / "GameAudioOriginalPreparation.cs",
            BOOTSTRAP / "NativeWwiseMonitorLease.cs",
            BOOTSTRAP / "PassivePcmCaptureWindow.cs",
            BOOTSTRAP / "GameAudioOriginalAndroidNativeBootstrap.cs",
            BOOTSTRAP / "OriginalGameAudioPassivePcmOwner.cs",
            BOOTSTRAP / "PcmWaveformReadbackV1.cs",
            ROOT / "tests/fixtures/point_sound/PointSoundBuildPin.cs",
            TARGET_CAPTURE_STUBS,
            HARNESS,
        ]
        with tempfile.TemporaryDirectory(prefix="pcm-finalizer-host-", dir=ROOT) as temp_name:
            executable = Path(temp_name) / "pcm-finalizer.exe"
            built = subprocess.run(
                [
                    str(MONO),
                    str(CSC),
                    "-nologo",
                    "-langversion:latest",
                    "-define:GAME_AUDIO_HOST_TEST",
                    "-target:exe",
                    "-out:" + str(executable),
                    *(str(source) for source in sources),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            ran = subprocess.run(
                [str(MONO), str(executable)],
                cwd=temp_name,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(ran.returncode, 0, ran.stdout + ran.stderr)
            self.assertIn("PASS actual bootstrap Term observer", ran.stdout)

    def test_bootstrap_and_session_owner_compile_with_additive_contract(self) -> None:
        common = [
            CORE / "GameAudioOriginalPassivePcmContract.cs",
            CORE / "GameAudioOriginalReadiness.cs",
            CORE / "GameAudioOriginalOwner.cs",
            CORE / "PointSoundDiagnosticObserver.cs",
            CORE / "OriginalOwnerProbeObserver.cs",
            BOOTSTRAP / "GameAudioOriginalPreparation.cs",
            BOOTSTRAP / "NativeWwiseMonitorLease.cs",
            BOOTSTRAP / "PassivePcmCaptureWindow.cs",
            BOOTSTRAP / "GameAudioOriginalAndroidNativeBootstrap.cs",
            BOOTSTRAP / "OriginalGameAudioPassivePcmOwner.cs",
            BOOTSTRAP / "PcmWaveformReadbackV1.cs",
            ROOT / "tests/fixtures/point_sound/PointSoundBuildPin.cs",
            TARGET_CAPTURE_STUBS,
        ]
        session = [
            CORE / "GameAudioOriginalPassivePcmContract.cs",
            CORE / "GameAudioOriginalReadiness.cs",
            CORE / "GameAudioOriginalOwner.cs",
            CORE / "PointSoundDiagnosticObserver.cs",
            CORE / "OriginalOwnerProbeObserver.cs",
            BOOTSTRAP / "GameAudioOriginalPreparation.cs",
            SESSION / "OriginalMusicControllerContract.cs",
            SESSION / "PortSessionOriginalMusicControllerOwner.cs",
            SESSION / "MusicPcmJoinObserver.cs",
            SESSION / "AkMusicPcmJoinQueryAdapter.cs",
            SESSION / "PortSessionOriginalAudioOwner.cs",
            SESSION / "OriginalNetworkSoundEventCatalogOwner.cs",
            ROOT / "tests/fixtures/original_audio/network_sound/NetworkSoundApiCompileStubs.cs",
            ROOT / "tests/fixtures/point_sound/PointSoundBuildPin.cs",
            TARGET_CAPTURE_STUBS,
        ]
        with tempfile.TemporaryDirectory(prefix="pcm-owner-compile-", dir=ROOT) as temp_name:
            temp = Path(temp_name)
            for label, sources in (("bootstrap", common), ("session", session)):
                output = temp / (label + ".dll")
                built = subprocess.run(
                    [
                        str(MONO),
                        str(CSC),
                        "-nologo",
                        "-langversion:latest",
                        "-target:library",
                        "-out:" + str(output),
                        *(str(source) for source in sources),
                    ],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
                self.assertTrue(output.is_file())

    def test_owner_root_and_preterm_postterm_call_sites_are_narrow(self) -> None:
        owner = (BOOTSTRAP / "OriginalGameAudioPassivePcmOwner.cs").read_text()
        bootstrap = (BOOTSTRAP / "GameAudioOriginalAndroidNativeBootstrap.cs").read_text()
        window = (BOOTSTRAP / "PassivePcmCaptureWindow.cs").read_text()
        session = (SESSION / "PortSessionOriginalAudioOwner.cs").read_text()
        helper = (BOOTSTRAP / "PcmWaveformReadbackV1.cs").read_text()
        old_lease = (BOOTSTRAP / "NativeWwiseMonitorLease.cs").read_text()
        self.assertIn("bootstrap.CapturePrivatePersistentDataRoot", owner)
        self.assertIn("if (!resolverInstalled)", bootstrap)
        self.assertIn("waveformFinalizer.ReadBeforeOriginalTerm", window)
        self.assertIn("lease.CaptureUnregisterCallSucceeded", window)
        self.assertIn("GameAudioOriginalOwner.OriginalTermsReturned", session)  # idempotent Update fallback
        self.assertIn("PersistWaveformAfterOriginalTerms()", session)
        callback_term = bootstrap.split("public void ObserveCallbackManagerTermReturned()", 1)[1].split("private static", 1)[0]
        self.assertLess(
            callback_term.index("monitor.RecordCallbackManagerTermReturned()"),
            callback_term.index("monitor.DisarmAfterReturnedTerms()"),
        )
        self.assertLess(
            callback_term.index("monitor.DisarmAfterReturnedTerms()"),
            callback_term.index("RunAfterVerifiedTerms(monitor"),
        )
        self.assertIn("capture_id", helper)
        self.assertIn('Guid.NewGuid().ToString("N")', helper)
        self.assertIn("FileMode.CreateNew", helper)
        self.assertIn("HasVerifiedPostTermDisarm", helper)
        self.assertIn("post_term_disarm_unverified", helper)
        self.assertIn("RecordUnverifiedTermDisarmSafely", bootstrap)
        self.assertEqual(
            len(re.findall(r'\[DllImport\("AkSoundEngine", EntryPoint =', old_lease)),
            11,
        )
        self.assertEqual(len(re.findall(r"\[DllImport\(Library, EntryPoint =", helper)), 2)
        self.assertNotIn("WwiseDiag_CaptureReadbackV1", old_lease)
        self.assertNotIn("WwiseDiag_CaptureCopyV1", old_lease)

    def test_status_means_raw_persisted_not_host_wav_exported(self) -> None:
        helper = (BOOTSTRAP / "PcmWaveformReadbackV1.cs").read_text()
        owner = (BOOTSTRAP / "OriginalGameAudioPassivePcmOwner.cs").read_text()
        session = (SESSION / "PortSessionOriginalAudioOwner.cs").read_text()
        contract = (CORE / "GameAudioOriginalPassivePcmContract.cs").read_text()
        self.assertIn("raw_pcm_persisted", helper)
        self.assertIn("original_engine_term_returned", helper)
        self.assertIn("original_callback_manager_term_returned", helper)
        self.assertIn("post_term_disarm_verified", helper)
        self.assertIn("WaveformRawPersisted", owner)
        self.assertIn("WaveformRawPersisted", contract)
        self.assertIn("passivePcmWaveformRawPersisted", session)


if __name__ == "__main__":
    unittest.main()
