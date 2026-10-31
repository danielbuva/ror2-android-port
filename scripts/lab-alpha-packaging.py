#!/usr/bin/env python3
"""Synthetic alpha packaging acceptance; run only on the root-leased /lab phone.

Reuses the existing installer acceptance/cleanup owner, never a second installer
or signer. Additional ART checks execute the actual importer under the fresh test
package UID via run-as/app_process (not the SAF picker or ordinary app UI).
No game input, production key, APK, or private identifier is published.
"""

import argparse
import copy
import importlib.util
import inspect
import json
import os
from pathlib import Path
import re
import sys
import tempfile

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
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.packaging_history = []

    def installed(self, publisher, previous=None):
        receipt = super().installed(publisher, previous)
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
    phone.start()
    require(phone.read("work/releases/issued-versions.json") == history[-1][1], "alpha-issued-ledger-cold-restart-mismatch")
    require(phone.read("installed-release.json") == history[-1][0], "alpha-receipt-cold-restart-mismatch")
    require(phone.package_hash(INSTALLER.GAME) == history[-1][0]["sha256"], "alpha-package-cold-restart-mismatch")
    passed("issued-ledger-cold-restart")


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
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--allow-test-installs", action="store_true")
    parser.add_argument("--allow-test-notifications", action="store_true")
    parser.add_argument("--timeout", type=int, default=1200)
    args = parser.parse_args(argv)
    phone = None
    completed = set()
    failed = False
    phase = "setup"

    def passed(case):
        require(case in INSTALLER.CASES + PACKAGE_CASES + IMPORT_CASES and case not in completed, "unexpected-acceptance-case")
        completed.add(case)
        print("PASS " + case, flush=True)

    try:
        serial = os.environ.get("LAB_DEVICE_SERIAL")
        require(bool(serial), "LAB_DEVICE_SERIAL-required-use-authorized-lab-runner")
        require(args.timeout > 0, "positive-timeout-required")
        kwargs = {"allow_test_installs": args.allow_test_installs}
        if args.allow_test_notifications:
            require("allow_test_notifications" in inspect.signature(INSTALLER.Phone).parameters, "merge-installer-notification-authorization-first")
            kwargs["allow_test_notifications"] = True
        INSTALLER.DIAGNOSTICS = INSTALLER.PrivateDiagnostics(ROOT / "work/coordination/alpha-packaging-acceptance")
        config = INSTALLER.read_context()
        phone = Phone(serial, args.timeout, **kwargs)
        with tempfile.TemporaryDirectory(prefix="ror2-synthetic-alpha-", dir="/tmp") as name:
            temporary = Path(name).resolve()
            require(not temporary.is_relative_to(ROOT.resolve()), "throwaway-root-must-be-outside-repository")
            phase = "compile-importer-harness"
            INSTALLER.set_phase(phase)
            dex = compile_import_harness(config, temporary)
            phase = "installer-acceptance"
            INSTALLER.acceptance(phone, config, temporary, passed)
            phase = "alpha-receipt-acceptance"
            INSTALLER.set_phase(phase)
            check_packaging_history(phone, passed)
            phase = "android-importer-acceptance"
            INSTALLER.set_phase(phase)
            import_acceptance(phone, dex, passed)
    except INSTALLER.Failure as error:
        # Existing installer Failure codes are authored constants, not raw logs.
        print("FAIL alpha-packaging phase=" + phase + " reason=" + str(error), flush=True)
        failed = True
    except Exception:
        print("FAIL alpha-packaging phase=" + phase + " reason=unexpected-local-error-see-private-evidence", flush=True)
        failed = True
    finally:
        if phone is not None:
            INSTALLER.set_phase("cleanup")
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
    if not failed:
        print("SCOPE synthetic-only; SAF/provider UI, legitimate cohorts, power-loss and game-profile acceptance NOT RUN", flush=True)
    return int(failed)


if __name__ == "__main__":
    sys.exit(main())
