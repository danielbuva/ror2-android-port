"""Qualify local signed source graphs through the owned Android installer."""

import json
from pathlib import Path, PurePosixPath
import tarfile
import time
import zipfile

from alpha_acquisition import FolderImport, GIB, IMPORT, cohort, stage_folder
from installed_alpha import InstalledAlphaDevice, installer_trust, preflight_releases, release_tools, verify_installed


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
NIGHTLY_CASES = ("signed-source-import", "staged-baseline-install", "nightly-baseline-tour")
TOOL_CASE = "signed-tools-acquired"


def acquired_sources(inventories, root, inputs, *, on_phone=False):
    inventory = inventories[0]
    if any(other != inventory for other in inventories[1:]):
        raise ValueError("staged update pair must use the same signed acquired-tool inventory")
    if on_phone:
        inventory = {name: pin for name, pin in inventory.items() if "url" not in pin}
    if bool(inventory) != (root is not None):
        raise ValueError("staged request must supply an acquired_source only for signed acquired tools")
    if not inventory:
        return {}
    source = Path(root).resolve(strict=True)
    return {name: (inputs.verify_acquired(source, name, pin), pin) for name, pin in inventory.items()}


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


class StagedTools(FolderImport):
    def folder_tool_hashes(self):
        return {name.removeprefix("acquired/"): pin["sha256"] for name, pin in self.acquired_inventory.items() if "url" not in pin}

    def stage_tool_folder(self, phone):
        if not self.acquired:
            return
        target = self.stage_root + "/Tools"
        phone.shell("mkdir", target, label="staged-create-tool-folder")
        self.transfer_acquired(phone, target, private=False)
        self.verify_tree(phone, target, self.folder_tool_hashes())

    def transfer_acquired(self, phone, root, *, private):
        prefix = ["run-as", self.installer.PACKAGE] if private else []
        with phone.transport.extract_tar([*prefix, "tar", "-xf", "-", "-C", root], label="staged-acquired-transfer", timeout=1200) as archive:
            for name, (source, pin) in self.acquired.items():
                info = tarfile.TarInfo(name if private else name.removeprefix("acquired/"))
                info.mode = 0o700 if source.stat().st_mode & 0o111 else 0o600
                info.size = pin["bytes"]
                with source.open("rb") as stream:
                    archive.addfile(info, stream)

    def stage_acquired(self, phone):
        package = self.installer.PACKAGE
        root = "files/owner-input"
        phone.require_owned_installer()
        phone.storage()
        phone.shell("run-as", package, "mkdir", "-p", root, label="staged-acquired-directory")
        phone.shell("run-as", package, "test", "!", "-e", root + "/acquired", label="staged-acquired-must-be-fresh")
        self.transfer_acquired(phone, root, private=True)
        self.verify_acquired(phone)

    def verify_acquired(self, phone):
        hashes = {name.removeprefix("acquired/"): pin["sha256"] for name, pin in self.acquired_inventory.items()}
        self.verify_tree(phone, "files/owner-input/acquired", hashes, private=True)

    def acquire_tools(self, phone, plan):
        phone.require_owned_installer()
        phone.shell("run-as", self.installer.PACKAGE, "test", "!", "-e", "files/owner-input/acquired", label="staged-acquired-must-be-fresh")
        if self.folder_tool_hashes():
            self.choose(phone, "tree", "Tools", tools=True)
        phone.tap("Acquire / resume required tools")
        deadline = time.monotonic() + phone.timeout
        while time.monotonic() < deadline:
            phone.flow_metrics.sample()
            row = phone.read("tools-state.json") or {}
            state = row.get("state")
            if state == "TOOLS_READY":
                self.require(row.get("inventory_sha256") == plan["acquired_inputs_sha256"], "staged-acquired-receipt-mismatch")
                self.verify_acquired(phone)
                self.require_visible_status(phone, "Required tools: Required tools verified in private storage.")
                self.installer.DIAGNOSTICS.write("staged-acquired-tools.json", self.installer.encoded(row))
                return
            if state in {"TOOLS_UNAVAILABLE", "CANCELLED", "ERROR"}:
                self.installer.DIAGNOSTICS.write("staged-acquired-tools.json", self.installer.encoded(row))
                raise self.installer.Failure("staged-tool-acquisition-" + state.lower())
            time.sleep(1)
        raise self.installer.Failure("staged-tool-acquisition-timeout")


class ToolAcquisition(StagedTools):
    """Exercise the signed plan and both acquisition sources with no game package."""

    def __init__(self, installer, require, request, temporary):
        super().__init__(installer, require)
        self.apk = Path(request["installer_apk"]).resolve(strict=True)
        self.apk_hash = request["installer_sha256"]
        trust = installer_trust(self.apk, self.apk_hash)
        require(installer.KEY_ID not in trust["keys"], "acquisition-test-publisher-collides")
        tools = installer.HostTools(installer.toolchain_context())
        manifest = installer.run([tools.build / "aapt", "dump", "badging", self.apk], label="inspect-tool-acquisition-installer").decode()
        installer.require_installer_manifest(manifest, request["installer_version"])
        owner = release_tools()
        inputs = owner.module("tool_acquisition_inputs", owner.HERE / "install_inputs.py")
        self.acquired_inventory = inputs.acquired_inventory(request["tools_inventory"])
        self.acquired = acquired_sources([self.acquired_inventory], request.get("acquired_source"), inputs, on_phone=True)
        require(self.acquired and len(self.acquired) < len(self.acquired_inventory), "tool-fixture-requires-folder-and-https")
        private, self.key = installer.publisher_keys(temporary, "tools")
        authored = installer.synthetic_inputs(tools, temporary)
        self.release = installer.release_fixture(owner.public(), authored, 1, temporary / "tools-release", private, self.key, acquired=self.acquired_inventory)
        with zipfile.ZipFile(self.release["public-tools.zip"]) as archive:
            plan = json.loads(archive.read("bundle-index.json"))["install_plan"]
            self.plan = inputs.input_description(plan, json.loads(archive.read(plan["required_inputs"])), self.acquired_inventory)

    def run(self, phone, passed):
        installer = self.installer
        metrics = phone.flow_metrics = installer.FlowMetrics(phone)
        installer.set_phase("tool-acquisition")
        self.require(not phone.occupied(installer.GAME) and not phone.occupied(installer.PACKAGE), "occupied-package-no-fresh-run-ownership")
        phone.storage_reserve = 20 * GIB + 2 * self.apk.stat().st_size + self.plan["workspace_bytes"]
        phone.storage_reserve += sum(pin["bytes"] for pin in self.acquired_inventory.values()) + sum(pin["bytes"] for _, pin in self.acquired.values())
        phone.storage()
        free = phone.available(phone.shell("df", "-k", self.external_root, label="tool-fixture-shared-free"))
        self.require(free >= phone.storage_reserve, "tool-fixture-shared-storage-reserve")
        phone.shell("mkdir", self.stage_root, label="tool-fixture-owned-download-directory")
        self.owned_stage = True
        self.stage_tool_folder(phone)
        with metrics.stage("fresh-installer"):
            phone.install(self.apk)
            phone.require_owned_installer()
            self.require(phone.installer_hash == self.apk_hash, "staged-installer-changed")
        with installer.server() as service, phone.active_display(), metrics.stage("staged-acquired-tools"):
            base = installer.publish(service, self.release, 1)
            port = "tcp:" + str(service.server_port)
            phone.command("reverse", "--no-rebind", port, port, label="tool-acquisition-reverse-create")
            phone.reverse_port = service.server_port
            phone.put(
                "debug-release-source.json",
                installer.encoded({"enabled": True, "base_url": base, "key_id": installer.KEY_ID, "public_key": self.key.decode()}),
            )
            phone.start()
            phone.check(1)
            phone.tap("Prepare signed installation plan")
            phone.wait_state({"INPUTS_REQUIRED"})
            self.require(phone.read("install-inputs.json") == self.plan, "staged-signed-input-plan-not-selected")
            self.acquire_tools(phone, self.plan)
            self.require(phone.read("owner-apk-ready.json") is None and not phone.occupied(installer.GAME), "tool-fixture-created-game-output")
        passed(TOOL_CASE)


class StagedUpdate(StagedTools):
    def __init__(self, installer, require, request, *, nightly=False):
        super().__init__(installer, require)
        self.nightly = nightly
        self.apk = Path(request["installer_apk"]).resolve(strict=True)
        self.apk_hash = request["installer_sha256"]
        self.game_label = request["game_label"]
        require(isinstance(self.game_label, str) and bool(self.game_label.strip()), "staged-game-label-required")
        version = request["installer_version"]
        names = ("baseline",) if nightly else ("baseline", "update")
        self.directories = {name: Path(request[name + "_release"]).resolve(strict=True) for name in names}
        self.pair = preflight_releases(self.apk, self.apk_hash, version, *self.directories.values(), include_install_plan=True)
        if not nightly:
            require(bool(self.pair["changed_entries"]) and bool(self.pair["unchanged_entries"]), "staged-pair-must-exercise-change-and-reuse")
        self.trust = installer_trust(self.apk, self.apk_hash)
        tools = installer.HostTools(installer.toolchain_context())
        manifest = installer.run([tools.build / "aapt", "dump", "badging", self.apk], label="inspect-staged-installer-manifest").decode()
        installer.require_installer_manifest(manifest, version)
        owner = release_tools()
        importer = owner.module("staged_update_importer", owner.HERE / "game_import.py")
        inputs = owner.module("staged_update_inputs", owner.HERE / "install_inputs.py")
        self.acquire_on_phone = request.get("acquire_on_phone", False)
        require(type(self.acquire_on_phone) is bool, "staged-invalid-acquire-on-phone-mode")
        inventories = [self.pair[name].get("acquired_inputs", {}) for name in names]
        self.acquired_inventory = inventories[0]
        if self.acquire_on_phone:
            require(bool(self.acquired_inventory) and "acquired_inputs_sha256" in self.pair["baseline"]["input_plan"], "staged-on-phone-tool-plan-required")
        if nightly and self.acquire_on_phone:
            require(request.get("acquired_source") is None, "nightly-tools-must-already-be-on-phone")
            self.acquired = {}
        else:
            self.acquired = acquired_sources(inventories, request.get("acquired_source"), inputs, on_phone=self.acquire_on_phone)
        self.acquired_bytes = sum(pin["bytes"] for pin in self.acquired_inventory.values())
        self.tool_stage_bytes = sum(pin["bytes"] for _, pin in self.acquired.values()) if self.acquire_on_phone else 0
        self.current = cohort(request["current_inventory"], None if nightly else request["current_source"], importer)
        self.inputs = {}
        for name in self.directories:
            plan = self.pair[name]["input_plan"]
            matching = [row for row in plan["supported_versions"] if row["manifest"] == self.current[1]]
            require(len(matching) == 1, "staged-pair-does-not-admit-current-originals")
            self.inputs[name] = matching[0]["manifest_sha256"]
        self.releases = {name: {asset: directory / asset for asset in ASSETS} for name, directory in self.directories.items()}
        self.originals = "Originals"
        if nightly:
            source = request["phone_source"]
            parts = PurePosixPath(source).parts
            require(
                len(parts) >= 2 and "/".join(parts) == source and all(part not in ("/", "..") for part in parts),
                "nightly-phone-source-must-be-relative-to-download",
            )
            self.stage_name = parts[0]
            self.stage_root = f"{self.external_root}/{self.stage_name}"
            self.originals = "/".join(parts[1:])
        self.stage_target = self.stage_root + "/" + self.originals

    def stage(self, phone):
        source, _, hashes, size = self.current
        phone.storage_reserve = (
            20 * GIB
            + 2 * self.apk.stat().st_size
            + (size if self.nightly else 2 * size)
            + self.acquired_bytes
            + self.tool_stage_bytes
            + max(self.pair[name]["input_plan"]["workspace_bytes"] + files["public-tools.zip"].stat().st_size for name, files in self.releases.items())
        )
        phone.storage()
        if self.nightly:
            self.verify_tree(phone, self.stage_target, hashes)
            if self.acquire_on_phone and (tool_hashes := self.folder_tool_hashes()):
                self.verify_tree(phone, self.stage_root + "/Tools", tool_hashes)
            return
        free = phone.available(phone.shell("df", "-k", self.external_root, label="staged-shared-free-before"))
        self.require(free >= 20 * GIB + size + self.tool_stage_bytes, "staged-shared-storage-reserve")
        phone.shell("mkdir", self.stage_root, label="staged-create-owned-download-directory")
        self.owned_stage = True
        stage_folder(phone, source, hashes, self.stage_target)
        self.verify_tree(phone, self.stage_target, hashes)
        if self.acquire_on_phone:
            self.stage_tool_folder(phone)

    def import_originals(self, phone):
        phone.tap("Prepare signed installation plan")
        source = self.pair["baseline"]
        state = phone.wait_state({"INPUTS_REQUIRED"})
        self.require(
            state.get("release", {}).get("version_code") == source["publisher_version_code"] and phone.read("install-inputs.json") == source["input_plan"],
            "staged-signed-input-plan-not-selected",
        )
        self.choose(phone, "tree", self.originals)
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
                {"mode": INSTALLED_ALPHA, "duration_seconds": min(phone.timeout, 600), "retain_native_loss": name == "baseline" and not self.nightly},
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
        if not self.nightly:
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

    def nightly_play(self, phone, device, receipt, stage):
        from whole_game_scoreboard import installed_census

        tour_failed = False
        try:
            with stage("baseline-play"):
                self.play(phone, device, "baseline")
        except Exception:
            tour_failed = True
            raise
        finally:
            if not phone.thermal.cancelled.is_set():
                try:
                    with stage("whole-game-scoreboard"):
                        self.require(phone.thermal.device.display(False), "nightly-census-display-sleep")
                        tour = self.installer.DIAGNOSTICS.directory / "baseline-play/terminal.done.json"
                        installed_census(phone, self.installer, receipt, device, tour)
                except Exception as error:
                    if not tour_failed:
                        raise
                    self.installer.DIAGNOSTICS.write("census-error.json", self.installer.encoded({"error": str(error)}))
                finally:
                    if tour_failed:
                        self.installer.set_phase("baseline-play")

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
        if self.acquired and not self.acquire_on_phone:
            with stage("staged-acquired-tools"):
                self.stage_acquired(phone)
        phone.install_consent_label = self.game_label
        with installer.server() as service:
            baseline = self.pair["baseline"]["publisher_version_code"]
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
            if self.acquire_on_phone:
                with stage("staged-acquired-tools"):
                    self.acquire_tools(phone, self.pair["baseline"]["input_plan"])
            self.cleanup(phone)
            self.owned_stage = False
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
            if self.nightly:
                self.nightly_play(phone, device, first, stage)
                passed("nightly-baseline-tour")
                return
            with stage("baseline-play"):
                self.play(phone, device, "baseline")
                before = self.native_hashes(device)
                passed("staged-baseline-native-save")
            update = self.pair["update"]["publisher_version_code"]
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
