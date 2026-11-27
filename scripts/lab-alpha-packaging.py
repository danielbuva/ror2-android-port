#!/usr/bin/env python3
"""Alpha packaging and acquisition acceptance on a root-leased /lab phone.

Reuses the existing installer acceptance/cleanup owner, never a second installer
or signer. Additional ART checks execute the actual importer under the fresh test
package UID via run-as/app_process (not the SAF picker or ordinary app UI).
No game input, production key, APK, or private identifier is published.
"""

import argparse
from contextlib import contextmanager
import copy
import importlib.util
import inspect
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import time
import traceback

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("alpha_packaging_installer", ROOT / "scripts/lab-installer-updates.py")
INSTALLER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(INSTALLER)
IMPORT_CASES = (
    "folder-validated",
    "folder-cancelled-without-accepted-output",
    "folder-unknown-refused",
    "folder-unsupported-refused",
    "zip-validated",
    "zip-cancelled-without-accepted-output",
    "zip-unknown-refused",
    "zip-unsupported-refused",
    "zip-traversal-refused",
    "source-unchanged",
    "honest-progress",
)
SAF_CASES = (
    "saf-picker-cancelled",
    "saf-unknown-refused",
    "saf-unsupported-refused",
    "saf-incomplete-folder-refused",
    "saf-invalid-zip-refused",
    "saf-import-cancelled",
    "saf-folder-validated",
    "saf-zip-validated",
    "saf-sources-unchanged",
)
PACKAGE_CASES = ("alpha-identity-issued-binding", "same-key-forward-update-and-rollback", "issued-ledger-cold-restart")
HASH = re.compile(r"[0-9a-f]{64}")


def require(condition, reason):
    if not condition:
        raise INSTALLER.Failure(reason)


def verify_issue(receipt, ledger, installed_version, previous=None):
    """Compare actual installed readback with durable issuance, never emit values."""
    require(isinstance(receipt, dict) and isinstance(ledger, dict), "alpha-receipt-missing")
    require(receipt.get("application_id") == INSTALLER.GAME == ledger.get("application_id"), "alpha-identity-mismatch")
    version = receipt.get("version_code")
    require(
        type(version) is int and type(installed_version) is int and 1 <= version <= 2100000000 and version == installed_version,
        "alpha-installed-version-mismatch",
    )
    require(receipt.get("installed_readback_verified") is True, "alpha-installed-readback-unverified")
    require(ledger.get("schema") == 1 and type(ledger.get("last_issued")) is int and ledger["last_issued"] == version, "alpha-issued-high-water-mismatch")
    issues = ledger.get("issues")
    require(isinstance(issues, dict), "alpha-issued-ledger-missing")
    row = issues.get(str(version))
    require(isinstance(row, dict) and row.get("status") == "signed", "alpha-issued-binding-missing")
    for field, receipt_field in (
        ("apk_sha256", "sha256"),
        ("payload_sha256", "payload_sha256"),
        ("signer_sha256", "signer_sha256"),
        ("source_sha256", "source_sha256"),
        ("input_sha256", "input_sha256"),
        ("toolchain_sha256", "toolchain_sha256"),
    ):
        value = row.get(field)
        require(isinstance(value, str) and HASH.fullmatch(value) is not None and value == receipt.get(receipt_field), "alpha-issued-binding-mismatch")
    require(row.get("publisher_version_code") == receipt.get("release", {}).get("version_code"), "alpha-publisher-version-mismatch")
    require(row.get("purpose") == receipt.get("purpose") and row.get("purpose") in {"update", "rollback"}, "alpha-issued-purpose-mismatch")
    if previous is not None:
        prior, prior_ledger = previous
        require(version > prior["version_code"] and receipt["signer_sha256"] == prior["signer_sha256"], "alpha-same-key-forward-order-mismatch")
        require(all(issues.get(code) == value for code, value in prior_ledger["issues"].items()), "alpha-issued-history-changed")


def parse_import_output(output):
    """Exact allowlist: never forward arbitrary subprocess stdout to GitHub."""
    expected = ["PASS " + case for case in IMPORT_CASES]
    require(output.decode("utf-8", errors="replace").splitlines() == expected, "android-importer-contract-failed")
    return IMPORT_CASES


class Phone(INSTALLER.Phone):
    storage_reserve = 20 * 1024**3

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.packaging_history = []
        self.thermal = None

    def execute(self, *args, **kwargs):
        if self.thermal is not None and self.thermal.cancelled.is_set():
            raise INSTALLER.Failure("alpha-packaging-thermal-cancellation")
        return super().execute(*args, **kwargs)

    def start(self, *, repeat_notification_denial=False):
        device = self.thermal.device
        if not device.display_awakened:
            require(device.display(True), "alpha-packaging-idle-display-policy-required")
        return super().start(repeat_notification_denial=repeat_notification_denial)

    @contextmanager
    def active_display(self):
        device = self.thermal.device
        try:
            require(device.display(True), "acquisition-idle-display-policy-required")
            yield
        finally:
            if device.display_awakened:
                require(device.display(False), "acquisition-display-cleanup-not-verified")

    @contextmanager
    def observe_thermal(self, *, duration=1800, require_continuous_trace=False):
        sys.path.insert(0, str(ROOT / "scripts/lab"))
        from alpha_stability_batch import _GameThermalOwner
        from device import Device

        phone = self

        class PackagingThermal(_GameThermalOwner):
            maximum_sample_gap = 0.0

            def sample(self, all_zones=False):
                self.phase = INSTALLER.CURRENT_PHASE
                previous = self.previous
                result = super().sample(all_zones=all_zones)
                if not all_zones and previous is not None:
                    self.maximum_sample_gap = max(self.maximum_sample_gap, self.previous - previous)
                return result

            def terminate_game(self):
                if not self.cancelled.is_set():
                    return  # Normal teardown belongs to the installer owner.
                # Use the separate observation transport: the acceptance path
                # refuses further ADB calls once cancellation is latched.
                for package, digest in ((INSTALLER.PACKAGE, phone.installer_hash if phone.owned_installer else None), (INSTALLER.GAME, phone.alpha_hash)):
                    if not digest or not self.device.sh("pidof", package, check=False, timeout=0.7):
                        continue
                    path = self.device.sh("pm", "path", package, timeout=0.7)
                    if not re.fullmatch(r"package:/[^\n]+", path):
                        raise RuntimeError("Thermal stop package placement unverified")
                    observed = self.device.sh("sha256sum", path[8:], timeout=4).split()
                    if not observed or observed[0] != digest:
                        raise RuntimeError("Thermal stop package hash unverified")
                    self.device.sh("am", "force-stop", package, timeout=2)

        diagnostics = INSTALLER.DIAGNOSTICS
        thermal = PackagingThermal(Device(self.serial), None, diagnostics.directory / "thermal.jsonl", time.monotonic() + duration)
        self.thermal = thermal
        try:
            thermal.cool()
            thermal.start()
            try:
                yield
            finally:
                try:
                    if thermal.device.display_awakened:
                        require(thermal.device.display(False), "alpha-packaging-display-cleanup-not-verified")
                finally:
                    thermal.finish()
            require(not require_continuous_trace or thermal.maximum_sample_gap <= 1, "staged-thermal-trace-gap")
        except RuntimeError as error:
            diagnostics.write("thermal-error.json", INSTALLER.encoded({"error": str(error)}))
            raise INSTALLER.Failure("alpha-packaging-thermal-evidence-failed") from error
        finally:
            self.thermal = None
            diagnostics.write(
                "thermal-summary.json",
                INSTALLER.encoded(
                    {
                        "admission_battery": thermal.admission_battery,
                        "peak_cpu_gpu_celsius": thermal.peak_cpu_gpu_celsius,
                        "time_above_80_seconds": thermal.time_above_80_seconds,
                        "maximum_sample_gap_seconds": thermal.maximum_sample_gap,
                        "error": thermal.error,
                    }
                ),
            )

    def installed(self, publisher, previous=None, *, require_pending_prompt=False):
        receipt = super().installed(publisher, previous, require_pending_prompt=require_pending_prompt)
        if INSTALLER.DIAGNOSTICS is not None:
            INSTALLER.DIAGNOSTICS.write("installed-alpha-" + str(len(self.packaging_history) + 1) + ".json", INSTALLER.encoded(receipt))
        ledger = self.read("work/releases/issued-versions.json")
        output = self.shell("dumpsys", "package", INSTALLER.GAME, label="alpha-installed-version-readback").decode()
        versions = set(re.findall(r"\bversionCode=(\d+)\b", output))
        require(len(versions) == 1, "alpha-installed-version-unavailable")
        verify_issue(receipt, ledger, int(next(iter(versions))), self.packaging_history[-1] if self.packaging_history else None)
        self.packaging_history.append((copy.deepcopy(receipt), copy.deepcopy(ledger)))
        return receipt


def check_packaging_history(phone, passed):
    history = phone.packaging_history
    require(len(history) == 3, "alpha-update-series-incomplete")
    require([row[0].get("purpose") for row in history] == ["update", "update", "rollback"], "alpha-update-series-purpose")
    require(history[2][0]["payload_sha256"] == history[0][0]["payload_sha256"], "alpha-rollback-payload-mismatch")
    passed("alpha-identity-issued-binding")
    passed("same-key-forward-update-and-rollback")
    phone.shell("am", "force-stop", INSTALLER.PACKAGE, label="alpha-installer-cold-stop")
    phone.start(repeat_notification_denial=True)
    require(phone.read("work/releases/issued-versions.json") == history[-1][1], "alpha-issued-ledger-cold-restart-mismatch")
    require(phone.read("installed-release.json") == history[-1][0], "alpha-receipt-cold-restart-mismatch")
    require(phone.package_hash(INSTALLER.GAME) == history[-1][0]["sha256"], "alpha-package-cold-restart-mismatch")
    passed("issued-ledger-cold-restart")
    if INSTALLER.DIAGNOSTICS is not None:
        INSTALLER.DIAGNOSTICS.write(
            "issued-packages.json",
            INSTALLER.encoded(
                [{field: receipt[field] for field in ("version_code", "purpose", "sha256", "payload_sha256", "signer_sha256")} for receipt, _ in history]
            ),
        )


def compile_import_harness(config, temporary):
    tools = INSTALLER.HostTools(config)
    sources = [ROOT / "tools/phone-build/managed-host/OwnerInputImport.java", ROOT / "tests/fixtures/AlphaPackagingHarness.java"]
    return tools.dex(sources, temporary / "alpha-importer-dex")


def import_acceptance(phone, dex, passed):
    require(phone.owned_installer and phone.package_hash(INSTALLER.PACKAGE) == phone.installer_hash, "alpha-importer-package-not-owned")
    phone.storage()
    # Fixed app-private namespace in a freshly installed package. No shell or
    # host paths supplied by a user, and no owner input directory is inspected.
    phone.put("alpha-packaging/classes.dex", dex)
    phone.shell("run-as", INSTALLER.PACKAGE, "chmod", "444", "files/owner-input/alpha-packaging/classes.dex", label="alpha-importer-readonly-dex")
    command = (
        'CLASSPATH="$PWD/files/owner-input/alpha-packaging/classes.dex" '
        "app_process /system/bin dev.ror2lab.phonebuildhostfixture.AlphaPackagingHarness "
        '"$PWD/files/owner-input/alpha-packaging/fixture" --android'
    )
    output = phone.shell("run-as", INSTALLER.PACKAGE, "sh", "-c", "'" + command + "'", label="alpha-importer-art", timeout=180)
    for case in parse_import_output(output):
        passed(case)


def main(argv=None):
    sys.path.insert(0, str(ROOT / "scripts/lab"))
    from staged_alpha_update import CASES as STAGED_CASES, StagedUpdate

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--qualify-install-prompts",
        action="store_true",
        help="Require visible permission and matching pending-user-action consent in the authorized synthetic workflow; never pregrant",
    )
    parser.add_argument("--allow-test-installs", action="store_true")
    parser.add_argument("--allow-test-notifications", action="store_true")
    parser.add_argument("--package-only", action="store_true", help="Qualify signed packages without running the direct importer harness")
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--acquisition-request", type=Path, help="Qualify actual SAF acquisition with local input inventories")
    source.add_argument("--staged-update-request", type=Path, help="Qualify a signed local source-release pair through the real installer")
    parser.add_argument("--toolhost-source-commit", help="Reuse an unmodified signed packaging fixture from this commit")
    parser.add_argument("--dry-run", action="store_true", help="Verify pinned toolhost and compile the acceptance inputs on the host")
    parser.add_argument("--timeout", type=int, default=1200)
    args = parser.parse_args(argv)
    if args.qualify_install_prompts and args.allow_test_installs:
        print("FAIL install-prompt-mode-conflict", flush=True)
        return 1
    if (args.acquisition_request or args.staged_update_request) and (
        args.package_only
        or args.qualify_install_prompts
        or args.allow_test_installs
        or args.allow_test_notifications
        or args.toolhost_source_commit is not None
    ):
        parser.error("source qualification uses a fresh installer with ordinary picker and install permissions")
    phone = None
    acquisition = None
    completed = set()
    failed = False
    phase = "setup"

    def passed(case):
        require(
            case in INSTALLER.CASES + (INSTALLER.PROMPT_CASES if args.qualify_install_prompts else ()) + PACKAGE_CASES + IMPORT_CASES + SAF_CASES + STAGED_CASES
            and case not in completed,
            "unexpected-acceptance-case",
        )
        completed.add(case)
        print("PASS " + case, flush=True)

    try:
        serial = os.environ.get("LAB_DEVICE_SERIAL")
        require(args.dry_run or bool(serial), "LAB_DEVICE_SERIAL-required-use-authorized-lab-runner")
        require(args.timeout > 0, "positive-timeout-required")
        kwargs = {"allow_test_installs": args.allow_test_installs}
        if args.allow_test_notifications:
            require("allow_test_notifications" in inspect.signature(INSTALLER.Phone).parameters, "merge-installer-notification-authorization-first")
            kwargs["allow_test_notifications"] = True
        INSTALLER.DIAGNOSTICS = INSTALLER.PrivateDiagnostics(ROOT / "work/coordination/alpha-packaging-acceptance")
        if args.staged_update_request:
            phase = "staged-update-host-preflight"
            acquisition = StagedUpdate(INSTALLER, require, json.loads(args.staged_update_request.read_bytes()))
            if args.dry_run:
                print("PASS staged-update signed source graphs and current input inventory precheck", flush=True)
                return 0
            phone = Phone(serial, args.timeout)
            phase = "staged-update"
            # Reserve separate windows for import and both builds, with time
            # left for play checks and cleanup before the outer runner exits.
            with phone.observe_thermal(duration=3 * args.timeout + 1200, require_continuous_trace=True):
                try:
                    acquisition.run(phone, passed)
                finally:
                    metrics, phone.flow_metrics = phone.flow_metrics, None
                    if metrics is not None:
                        INSTALLER.DIAGNOSTICS.write("phone-flow-metrics.json", INSTALLER.encoded(metrics.report(include_samples=True)))
            require(completed == set(STAGED_CASES), "staged-update-case-series-incomplete")
        else:
            request = json.loads(args.acquisition_request.read_bytes()) if args.acquisition_request else {}
            source_commit = request.get("toolhost_source_commit") if args.acquisition_request else args.toolhost_source_commit
            config = INSTALLER.read_context(source_commit) if source_commit is not None else INSTALLER.read_context()
            with tempfile.TemporaryDirectory(prefix="ror2-synthetic-alpha-", dir="/tmp") as name:
                temporary = Path(name).resolve()
                require(not temporary.is_relative_to(ROOT.resolve()), "throwaway-root-must-be-outside-repository")
                if args.acquisition_request:
                    phase = "acquisition-host-fixture"
                    from lab.alpha_acquisition import Acquisition

                    acquisition = Acquisition(INSTALLER, require, request, config, temporary)
                    if args.dry_run:
                        print("PASS alpha-acquisition signed catalogs and source inventory precheck", flush=True)
                        return 0
                    acquisition.prepare_archive()
                    phone = Phone(serial, args.timeout)
                    phase = "saf-acquisition"
                    with phone.observe_thermal():
                        acquisition.run(phone, passed)
                    require(completed == set(SAF_CASES), "acquisition-case-series-incomplete")
                else:
                    if not args.package_only:
                        phase = "compile-importer-harness"
                        INSTALLER.set_phase(phase)
                        dex = compile_import_harness(config, temporary)
                    if args.dry_run:
                        INSTALLER.prepare_artifacts(config, temporary)
                        print("PASS alpha-packaging host fixture", flush=True)
                        return 0
                    phone = Phone(serial, args.timeout, **kwargs)
                    phase = "thermal-admission"
                    INSTALLER.set_phase(phase)
                    with phone.observe_thermal():
                        phase = "installer-acceptance"
                        try:
                            INSTALLER.acceptance(phone, config, temporary, passed, qualify_install_prompts=args.qualify_install_prompts, record_metrics=True)
                        finally:
                            metrics, phone.flow_metrics = phone.flow_metrics, None
                            if metrics is not None:
                                INSTALLER.DIAGNOSTICS.write("phone-flow-metrics.json", INSTALLER.encoded(metrics.report(include_samples=True)))
                        phase = "alpha-receipt-acceptance"
                        INSTALLER.set_phase(phase)
                        check_packaging_history(phone, passed)
                        if not args.package_only:
                            phase = "android-importer-acceptance"
                            INSTALLER.set_phase(phase)
                            import_acceptance(phone, dex, passed)
    except INSTALLER.Failure as error:
        # Existing installer Failure codes are authored constants, not raw logs.
        if phase in ("saf-acquisition", "staged-update"):
            phase = INSTALLER.CURRENT_PHASE
        print("FAIL alpha-packaging phase=" + phase + " reason=" + str(error), flush=True)
        failed = True
    except Exception:
        if INSTALLER.DIAGNOSTICS is not None:
            INSTALLER.DIAGNOSTICS.write("alpha-packaging-error.log", traceback.format_exc().encode())
        print("FAIL alpha-packaging phase=" + phase + " reason=unexpected-local-error-see-private-evidence", flush=True)
        failed = True
    finally:
        if phone is not None:
            INSTALLER.set_phase("cleanup")
            if acquisition is not None:
                try:
                    acquisition.cleanup(phone)
                except Exception:
                    print("FAIL cleanup reason=owned-download-cleanup-not-verified", flush=True)
                    failed = True
            try:
                result = phone.cleanup()
                if result == "verified-absent":
                    print("PASS cleanup packages=verified-absent", flush=True)
                else:
                    print("SKIP cleanup packages=not-checked reason=no-owned-package-mutation", flush=True)
            except Exception:
                print("FAIL cleanup reason=owned-package-cleanup-not-verified", flush=True)
                failed = True
        INSTALLER.DIAGNOSTICS = None
    if not failed and not (args.acquisition_request or args.staged_update_request):
        print("SCOPE synthetic-only; SAF/provider UI, legitimate cohorts, power-loss and game-profile acceptance NOT RUN", flush=True)
    return int(failed)


if __name__ == "__main__":
    sys.exit(main())
