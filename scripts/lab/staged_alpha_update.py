"""Qualify a local signed source-graph pair through the owned Android installer."""

import json
from pathlib import Path
import time

from alpha_acquisition import FolderImport, GIB, IMPORT, cohort, stage_folder
from installed_alpha import InstalledAlphaDevice, installer_trust, preflight_update, release_tools, verify_installed


ASSETS = ("release.json", "release.sig", "public-tools.zip")
CASES = (
    "signed-source-import",
    "staged-baseline-install",
    "staged-baseline-native-save",
    "staged-update-available",
    "staged-in-place-rebuild",
    "staged-native-save-retained",
    "staged-updated-native-play",
    "staged-up-to-date",
)


def verify_incremental(receipt, source, changed, unchanged, attempts, require):
    proof = receipt.get("incremental", {})
    rebuilt, reused = proof.get("rebuilt", []), proof.get("reused", [])
    jobs = proof.get("producer_jobs", {})
    require(
        len(rebuilt) == len(set(rebuilt))
        and len(reused) == len(set(reused))
        and set(rebuilt) <= set(changed)
        and set(unchanged) <= set(reused)
        and not set(rebuilt).intersection(reused)
        and set(rebuilt + reused) == set(changed + unchanged),
        "staged-rebuild-entry-coverage",
    )
    require(set(jobs) == set(source["jobs"]) and set(jobs.values()) <= {"executed", "reused"}, "staged-signed-producer-coverage")
    require(attempts > 0 and attempts == list(jobs.values()).count("executed"), "staged-producer-execution-count")
    if unchanged:
        require("reused" in jobs.values() and bool(rebuilt), "staged-update-did-not-rebuild-and-reuse")
    else:
        require(not reused and "reused" not in jobs.values(), "staged-fresh-build-reused-output")
    return proof


class StagedUpdate(FolderImport):
    def __init__(self, installer, require, request):
        super().__init__(installer, require)
        self.apk = Path(request["installer_apk"]).resolve(strict=True)
        self.apk_hash = request["installer_sha256"]
        self.game_label = request["game_label"]
        require(isinstance(self.game_label, str) and bool(self.game_label.strip()), "staged-game-label-required")
        version = request["installer_version"]
        self.directories = {name: Path(request[name + "_release"]).resolve(strict=True) for name in ("baseline", "update")}
        self.pair = preflight_update(self.apk, self.apk_hash, version, *self.directories.values(), include_install_plan=True)
        require(bool(self.pair["changed_entries"]) and bool(self.pair["unchanged_entries"]), "staged-pair-must-exercise-change-and-reuse")
        self.trust = installer_trust(self.apk, self.apk_hash)
        tools = installer.HostTools(installer.toolchain_context())
        manifest = installer.run([tools.build / "aapt", "dump", "badging", self.apk], label="inspect-staged-installer-manifest").decode()
        installer.require_installer_manifest(manifest, version)
        owner = release_tools()
        importer = owner.module("staged_update_importer", owner.HERE / "game_import.py")
        self.current = cohort(request["current_inventory"], request["current_source"], importer)
        self.inputs = {}
        for name in self.directories:
            plan = self.pair[name]["input_plan"]
            matching = [row for row in plan["supported_versions"] if row["manifest"] == self.current[1]]
            require(len(matching) == 1, "staged-pair-does-not-admit-current-originals")
            self.inputs[name] = matching[0]["manifest_sha256"]
        self.releases = {name: {asset: directory / asset for asset in ASSETS} for name, directory in self.directories.items()}
        self.stage_target = self.stage_root + "/Originals"

    def stage(self, phone):
        source, _, hashes, size = self.current
        phone.storage_reserve = (
            20 * GIB
            + 2 * self.apk.stat().st_size
            + 2 * size
            + max(self.pair[name]["input_plan"]["workspace_bytes"] + files["public-tools.zip"].stat().st_size for name, files in self.releases.items())
        )
        phone.storage()
        free = phone.available(phone.shell("df", "-k", self.external_root, label="staged-shared-free-before"))
        self.require(free >= 20 * GIB + size, "staged-shared-storage-reserve")
        phone.shell("mkdir", self.stage_root, label="staged-create-owned-download-directory")
        self.owned_stage = True
        stage_folder(phone, source, hashes, self.stage_target)
        self.verify_tree(phone, self.stage_target, hashes)

    def import_originals(self, phone):
        phone.tap("Prepare signed installation plan")
        source = self.pair["baseline"]
        state = phone.wait_state({"INPUTS_REQUIRED"})
        self.require(
            state.get("release", {}).get("version_code") == source["publisher_version_code"] and phone.read("install-inputs.json") == source["input_plan"],
            "staged-signed-input-plan-not-selected",
        )
        self.choose(phone, "tree", "Originals")
        phone.tap("Import / resume game files")
        result = self.wait_import(phone, "IMPORTED", timeout=phone.timeout)
        _, manifest, hashes, size = self.current
        self.require(
            result.get("manifest_sha256") == self.inputs["baseline"]
            and result.get("game_version") == manifest["game_version"]
            and result.get("completed") == result.get("total") == size,
            "staged-import-receipt-mismatch",
        )
        self.verify_tree(phone, IMPORT + "/files", hashes, private=True)
        self.verify_tree(phone, self.stage_target, hashes)
        self.cleanup(phone)
        self.owned_stage = False

    def install(self, phone, name, previous=None):
        source = self.pair[name]
        attempts = phone.producer_attempt_count() if previous is not None else 0
        phone.storage_reserve = 20 * GIB + source["input_plan"]["workspace_bytes"] + self.releases[name]["public-tools.zip"].stat().st_size
        phone.storage()
        phone.tap("Reconstruct and install verified game")
        # After Android readback, only the ordinary free-space floor is due.
        phone.storage_reserve = 20 * GIB
        receipt = phone.installed(source["publisher_version_code"], previous, require_pending_prompt=previous is None)
        deadline = time.monotonic() + min(phone.timeout, 30)
        while phone.read("pending-install.json") is not None:
            self.require(time.monotonic() < deadline, "staged-install-retention-still-active")
            time.sleep(0.25)
        self.require(receipt.get("source_sha256") == source["source_sha256"], "staged-installed-source-mismatch")
        if previous is None:
            changed, unchanged = sorted(receipt["release"]["entries"]), []
        else:
            changed, unchanged = self.pair["changed_entries"], self.pair["unchanged_entries"]
            self.require(
                receipt.get("profile_retention_verified") is True
                and all(receipt.get(field) == previous[field] for field in ("input_sha256", "toolchain_sha256")),
                "staged-update-changed-owner-inputs-or-toolchain",
            )
        verify_incremental(receipt, source, changed, unchanged, phone.producer_attempt_count() - attempts, self.require)
        device = InstalledAlphaDevice(phone.serial, self.installer.ROOT / "work")
        device.installed = verify_installed(
            device,
            self.installer.PACKAGE,
            self.apk_hash,
            self.trust,
            source["source_sha256"],
            self.releases[name]["public-tools.zip"],
            staged=True,
        )
        return receipt, device

    def play(self, phone, device, name):
        from device_session import INSTALLED_ALPHA, prepare_launch, run_workload, save

        output = self.installer.DIAGNOSTICS.directory / (name + "-play")
        output.mkdir()
        result = dict(
            success=False,
            mode=INSTALLED_ALPHA,
            apk_sha256=device.installed["apk_sha256"],
            installed_release=device.installed,
            keyguard={},
        )
        try:
            result["admission"] = phone.thermal.between_sessions(cool_start=True)
            prepare_launch(device, result["keyguard"])
            run_workload(
                device,
                phone.thermal,
                {"mode": INSTALLED_ALPHA, "duration_seconds": min(phone.timeout, 600), "retain_native_loss": name == "baseline"},
                output,
                result,
                start_attempt=result["installed_release"]["attempt"],
            )
            if name == "update":
                menu = json.loads((output / "start-menu.json").read_bytes())
                profile = json.loads((output / "world-start.json").read_bytes()).get("profile", {})
                self.require(
                    menu.get("settings", {}).get("recovery") == "validated-primary"
                    and profile.get("recovery") == "validated-primary"
                    and profile.get("reconciledRuns") == 0,
                    "staged-updated-game-did-not-load-retained-native-state",
                )
            result["success"] = True
        except BaseException as error:
            result["first_failure"] = str(error) or type(error).__name__
            raise
        finally:
            save(output / "terminal.done.json", result)
            if not phone.thermal.cancelled.is_set():
                phone.require_owned_installer()
                self.require(phone.package_hash(self.installer.GAME) == device.installed["apk_sha256"], "staged-play-ownership-changed")
                phone.shell("am", "force-stop", self.installer.GAME, label="staged-stop-owned-game")
        phone.start()

    def native_hashes(self, device):
        from settings_write_interrupt_check import persistence_hashes

        self.require(not device.sh("pidof", device.package, check=False), "staged-persistence-requires-stopped-game")
        runtime = "/sdcard/Android/data/" + device.package + "/files"
        device.validate_runtime({"persistentDataPath": runtime})
        names = ("android-profile-v1", "offline-settings-v1", "offline-run-results-v1")
        hashes = persistence_hashes(device, runtime, *names)
        self.require(
            all(runtime + "/" + name + "/" + file in hashes for name, file in zip(names, ("profile.json", "preferences.json", "profile.json"))),
            "staged-native-primary-files-missing",
        )
        self.require(
            any(path.startswith(runtime + "/offline-run-results-v1/run-") and path.endswith(".xml") for path in hashes), "staged-native-run-result-missing"
        )
        return {path.removeprefix(runtime + "/"): digest for path, digest in hashes.items()}

    def run(self, phone, passed):
        installer = self.installer
        metrics = phone.flow_metrics = installer.FlowMetrics(phone)

        def stage(name):
            installer.set_phase(name)
            return metrics.stage(name)

        installer.set_phase("staged-pre-install-checks")
        self.require(not phone.occupied(installer.GAME) and not phone.occupied(installer.PACKAGE), "occupied-package-no-fresh-run-ownership")
        self.stage(phone)
        with stage("fresh-installer"):
            phone.install(self.apk)
            phone.require_owned_installer()
            self.require(phone.installer_hash == self.apk_hash, "staged-installer-changed")
        phone.install_consent_label = self.game_label
        with installer.server() as service:
            baseline = self.pair["baseline"]["publisher_version_code"]
            update = self.pair["update"]["publisher_version_code"]
            base = installer.publish(service, self.releases["baseline"], baseline)
            port = "tcp:" + str(service.server_port)
            phone.command("reverse", "--no-rebind", port, port, label="staged-reverse-create")
            phone.reverse_port = service.server_port
            phone.put("debug-release-source.json", installer.encoded({"enabled": True, "base_url": base}))
            with stage("signed-source-import"):
                phone.start()
                phone.check(baseline)
                self.require(any("TEST RELEASE SOURCE" in node.get("text", "") for node in phone.ui().iter("node")), "debug-source-warning-not-visible")
                self.import_originals(phone)
                passed("signed-source-import")
            with stage("visible-install-permission"):
                request, checkpoint = (phone.read(name) for name in ("update-request.json", "install-checkpoint.json"))
                downloads = service.requests.count("/public-tools.zip")
                phone.allow_visible_install_permission()
                self.require(
                    phone.read("update-request.json") == request
                    and phone.read("install-checkpoint.json") == checkpoint
                    and service.requests.count("/public-tools.zip") == downloads,
                    "staged-permission-return-started-work",
                )
            with stage("baseline-reconstruct-and-install"):
                first, device = self.install(phone, "baseline")
                passed("staged-baseline-install")
            with stage("baseline-play"):
                self.play(phone, device, "baseline")
                before = self.native_hashes(device)
                passed("staged-baseline-native-save")
            with stage("check-for-updates"):
                installer.publish(service, self.releases["update"], update)
                changes = phone.check(update)
                self.require_visible_status(
                    phone,
                    "Signed update available",
                    f"Changed outputs: {len(self.pair['changed_entries'])}; removed: {len(self.pair['removed_entries'])}",
                )
                self.require(
                    changes.get("installed_manifest_known") is True
                    and all(changes.get(key) == self.pair[key] for key in ("changed_entries", "removed_entries"))
                    and "/public-tools.zip" not in service.requests
                    and phone.read("installed-release.json") == first,
                    "staged-update-check-did-not-report-signed-diff-before-reconstruction",
                )
                passed("staged-update-available")
            with stage("in-place-update"):
                second, device = self.install(phone, "update", first)
                passed("staged-in-place-rebuild")
            with stage("verify-profile-settings"):
                after = self.native_hashes(device)
                installer.DIAGNOSTICS.write("staged-native-persistence.json", installer.encoded({"before": before, "after": after}))
                self.require(before == after, "staged-native-persistence-changed-before-cold-launch")
                passed("staged-native-save-retained")
            with stage("updated-play"):
                self.play(phone, device, "update")
                passed("staged-updated-native-play")
            with stage("check-up-to-date"):
                installer.publish(service, self.releases["update"], update)
                phone.check(update, "UP_TO_DATE")
                self.require_visible_status(phone, "The installed game is up to date.")
                self.require(
                    "/public-tools.zip" not in service.requests and phone.read("installed-release.json") == second, "staged-current-check-started-work"
                )
                passed("staged-up-to-date")
