"""Exercise the installer’s signed input plan through the Android file picker."""

import hashlib
import json
from pathlib import Path
import re
import secrets
import shlex
import time
import zipfile


DOCUMENTS = ("com.android.documentsui", "com.google.android.documentsui")
IMPORT = "files/owner-input/import"
GIB = 1024**3


def cohort(inventory, source, importer):
    raw = json.loads(Path(inventory).read_bytes())
    manifest = importer.validate_manifest(
        {
            "schema": 1,
            "game_version": "Steam " + str(raw["steam"]["buildid"]),
            "files": [{"path": row["path"], "bytes": row["size"], "sha256": row["sha256"]} for row in raw["files"]],
        }
    )
    root = Path(source).resolve(strict=True)
    expected = {row["path"]: row["sha256"] for row in manifest["files"]}
    actual = {}
    for path in root.rglob("*"):
        if path.is_symlink() or not (path.is_file() or path.is_dir()):
            raise ValueError("nonregular-acquisition-source-entry")
        if path.is_file():
            actual[path.relative_to(root).as_posix()] = path.stat().st_size
    if actual != {row["path"]: row["bytes"] for row in manifest["files"]}:
        raise ValueError("acquisition-source-inventory-mismatch")
    return root, manifest, expected, sum(actual.values())


def hash_listing(raw):
    result = {}
    for line in raw.decode().splitlines():
        match = re.fullmatch(r"([0-9a-f]{64})  \./(.+)", line)
        if not match or match[2] in result:
            raise ValueError("acquisition-hash-listing-invalid")
        result[match[2]] = match[1]
    return result


def select_node(tree, texts, *, ids=(), clickable=False):
    package = tree.find("node").get("package")
    matches = [
        node
        for node in tree.iter("node")
        if node.get("package") == package
        and node.get("enabled") == "true"
        and (not clickable or node.get("clickable") == "true")
        and (node.get("text", "").casefold() in texts or node.get("content-desc", "").casefold() in texts)
        and (not ids or node.get("resource-id") in {package + ":id/" + name for name in ids})
    ]
    if len(matches) > 1:
        raise ValueError("acquisition-ambiguous-visible-control")
    return matches[0] if matches else None


class Acquisition:
    def __init__(self, installer, require, request, config, temporary):
        self.installer, self.require = installer, require
        self.apk = config["installer_apk"]
        self.apk_hash = config["installer_sha256"]
        self.stage_name = "LabAcquisition-" + secrets.token_hex(8)
        self.stage_root = "/sdcard/Download/" + self.stage_name
        self.owned_stage = False
        tools = installer.HostTools(config)
        manifest = installer.run([tools.build / "aapt", "dump", "badging", self.apk], label="inspect-cached-installer-manifest").decode()
        installer.require_installer_manifest(manifest, config["installer_version"])
        with zipfile.ZipFile(self.apk) as archive:
            trust = json.loads(archive.read("assets/release-trust.json"))
        require(installer.KEY_ID not in trust["keys"], "acquisition-test-publisher-collides")
        owner = installer.ROOT / "tools/phone-build/owner-apk"
        public = installer.module("acquisition_public", owner / "public_release.py")
        importer = installer.module("acquisition_importer", owner / "game_import.py")
        inputs = installer.module("acquisition_install_inputs", owner / "install_inputs.py")
        self.current = cohort(request["current_inventory"], request["current_source"], importer)
        self.older = cohort(request["older_inventory"], request["older_source"], importer)
        require(self.current[1]["game_version"] != self.older[1]["game_version"], "acquisition-cohorts-not-distinct")
        private, self.key = installer.publisher_keys(temporary, "acquisition")
        authored = installer.synthetic_inputs(tools, temporary)
        self.releases, self.plans = {}, {}
        for version, recognized in ((1, []), (2, [self.older[1]])):
            catalog = {"schema": 2, "supported": [self.current[1]], "recognized": recognized}
            self.releases[version] = installer.release_fixture(
                public, authored, version, temporary / f"acquisition-release-{version}", private, self.key, required_catalog=catalog
            )
            plan = {"workspace_bytes": 64 * 1024**2, "stages": []}
            self.plans[version] = inputs.input_description(plan, catalog)
        self.archive = temporary / "Supported.zip"
        self.results = {}

    def prepare_archive(self):
        source, manifest, _, _ = self.current
        with zipfile.ZipFile(self.archive, "w", compression=zipfile.ZIP_STORED) as archive:
            for row in manifest["files"]:
                archive.write(source / row["path"], row["path"])
        with self.archive.open("rb") as stream:
            self.archive_hash = hashlib.file_digest(stream, "sha256").hexdigest()

    def verify_tree(self, phone, root, expected, *, private=False):
        script = f"cd {shlex.quote(root)} && find . -type f -exec sha256sum {{}} +"
        args = ["run-as", self.installer.PACKAGE] if private else []
        raw = phone.command("shell", shlex.join([*args, "sh", "-c", script]), label="acquisition-tree-hashes", timeout=300)
        self.require(hash_listing(raw) == expected, "acquisition-tree-hash-mismatch")

    def staged_unchanged(self, phone):
        self.verify_tree(phone, self.stage_root + "/Supported", self.current[2])
        self.verify_tree(phone, self.stage_root + "/Older", self.older[2])
        archive = phone.shell("sha256sum", self.stage_root + "/Supported.zip", label="acquisition-zip-hash", timeout=300).decode().split()
        self.require(len(archive) == 2 and archive[0] == self.archive_hash, "acquisition-staged-zip-mismatch")

    def stage(self, phone):
        archive_bytes = self.archive.stat().st_size
        staged = self.current[3] + self.older[3] + archive_bytes
        reserve = 20 * GIB + 2 * self.apk.stat().st_size + staged + 2 * self.current[3]
        phone.storage_reserve = reserve
        phone.storage()
        free = phone.available(phone.shell("df", "-k", "/sdcard/Download", label="acquisition-shared-free-before"))
        self.require(free >= reserve, "acquisition-shared-storage-reserve")
        phone.shell("mkdir", self.stage_root, label="acquisition-owned-download-directory")
        self.owned_stage = True
        for folder, entry in (("Supported", self.current), ("Older", self.older)):
            target = self.stage_root + "/" + folder
            phone.shell("mkdir", target, label="acquisition-cohort-directory")
            children = sorted({path.split("/")[0] for path in entry[2]})
            phone.command("push", *(entry[0] / child for child in children), target + "/", label="acquisition-stage-folder", timeout=900)
        phone.command("push", self.archive, self.stage_root + "/Supported.zip", label="acquisition-stage-zip", timeout=900)
        self.staged_unchanged(phone)
        phone.storage_reserve = 20 * GIB + self.apk.stat().st_size + 2 * self.current[3]
        phone.storage()
        self.results["staged"] = {"bytes": staged, "shared_free_before": free, "zip_bytes": archive_bytes}

    def cleanup(self, phone):
        if self.owned_stage:
            phone.shell("rm", "-rf", self.stage_root, label="acquisition-remove-owned-download-directory")
            phone.shell("test", "!", "-e", self.stage_root, label="acquisition-download-directory-absent")

    def picker(self, phone):
        return phone.ui_windows(DOCUMENTS, recovery=False)

    def click_document(self, phone, name):
        tree = self.picker(phone)
        node = select_node(tree, (name.casefold(),), ids=("title",))
        self.require(node is not None, "acquisition-document-not-visible")
        phone.tap_prompt_node(node, "acquisition-select-document")

    def choose(self, phone, kind, name=None):
        phone.tap("Choose game folder" if kind == "tree" else "Choose game ZIP")
        tree = self.picker(phone)
        if name is None:
            phone.shell("input", "keyevent", "KEYCODE_BACK", label="acquisition-cancel-focused-picker")
            phone.ui_windows((self.installer.PACKAGE,), recovery=False)
            return
        # Use the local storage provider. Downloads can also be indexed by a
        # different provider whose root listing omits files staged by ADB.
        drawer = select_node(tree, ("show roots",), clickable=True)
        self.require(drawer is not None, "acquisition-picker-location-drawer-unavailable")
        phone.tap_prompt_node(drawer, "acquisition-show-picker-locations")
        model = phone.shell("getprop", "ro.product.model", label="acquisition-local-storage-label").decode().strip().casefold()
        roots = self.picker(phone)
        local = select_node(roots, (model, "internal storage", "internal shared storage", "sd card"), ids=("title",))
        self.require(local is not None, "acquisition-local-storage-root-unavailable")
        phone.tap_prompt_node(local, "acquisition-open-local-storage-root")
        self.click_document(phone, "Download")
        self.click_document(phone, self.stage_name)
        self.click_document(phone, name)
        if kind == "tree":
            for text in ("use this folder", "allow"):
                button = select_node(self.picker(phone), (text,), clickable=True)
                self.require(button is not None, "acquisition-folder-grant-control-unavailable")
                phone.tap_prompt_node(button, "acquisition-confirm-folder-grant")
        observed = phone.read("update-state.json")
        self.require(
            observed and observed.get("state") == "INPUT_REQUIRED" and "Source selected." in observed.get("message", ""),
            "acquisition-source-selection-unverified",
        )

    def prepare_plan(self, phone, service, version):
        self.installer.publish(service, self.releases[version], version)
        if version > 1:
            phone.check(version)
        phone.tap("Prepare signed installation plan")
        state = phone.wait_state({"INPUTS_REQUIRED"})
        plan = phone.read("install-inputs.json")
        expected = self.plans[version]
        self.require(
            state.get("release", {}).get("version_code") == version and plan and plan.get("catalog_sha256") == expected["catalog_sha256"],
            "acquisition-signed-plan-not-selected",
        )

    def wait_import(self, phone, expected):
        deadline = time.monotonic() + min(phone.timeout, 360)
        while time.monotonic() < deadline:
            row = phone.read("import-state.json")
            if row:
                state = row.get("state")
                if expected == "ACTIVE" and (state == "VALIDATING" or (state == "IMPORTING" and row.get("completed", 0) > 0)):
                    return row
                if state in {"ERROR", "IMPORTED", "CANCELLED"}:
                    self.require(expected == state, "acquisition-unexpected-import-terminal")
                    return row
            time.sleep(0.5)
        raise self.installer.Failure("acquisition-import-timeout")

    def visible_status(self, phone, state, detail):
        # The installer status TextView is first in a real ScrollView. Search
        # it from the top after interacting with controls below it.
        for _ in range(6):
            tree = phone.ui_windows((self.installer.PACKAGE,), recovery=False)
            for node in tree.iter("node"):
                text = node.get("text", "")
                if "Game import: " + state in text and all(part in text for part in detail):
                    return
            scroll = next((node for node in tree.iter("node") if node.get("scrollable") == "true"), None)
            if scroll is None:
                break
            bounds = list(map(int, re.findall(r"\d+", scroll.get("bounds", ""))))
            self.require(len(bounds) == 4, "acquisition-status-scroll-bounds")
            x1, y1, x2, y2 = bounds
            x = str((x1 + x2) // 2)
            phone.shell("input", "swipe", x, str(y1 + (y2 - y1) // 5), x, str(y2 - (y2 - y1) // 5), "250", label="acquisition-scroll-to-status")
        raise self.installer.Failure("acquisition-status-not-visible")

    def no_admitted_output(self, phone, *, no_import=False):
        self.require(phone.read("owner-apk-ready.json") is None and not phone.occupied(self.installer.GAME), "acquisition-unverified-apk-admitted")
        if no_import:
            phone.shell("run-as", self.installer.PACKAGE, "test", "!", "-e", IMPORT, label="acquisition-no-private-import")

    def run_case(self, phone, case, kind, name, expected, passed, *, message=()):
        self.installer.set_phase(case)
        self.choose(phone, kind, name)
        start = time.monotonic()
        phone.tap("Import / resume game files")
        row = self.wait_import(phone, "ACTIVE" if expected == "CANCELLED" else expected)
        result = self.results[case] = {}
        if expected == "CANCELLED":
            result["cancel_observed"] = row["state"]
            result["copied_bytes_at_cancel"] = row.get("completed", 0)
            phone.tap("Cancel (keep verified checkpoints)")
            row = self.wait_import(phone, expected)
        self.require(all(part in row.get("message", "") for part in message), "acquisition-import-report-mismatch")
        self.visible_status(phone, expected, message)
        result.update(state=expected, seconds=round(time.monotonic() - start, 3))
        result["installer_pss_bytes"] = self.installer.process_pss(
            phone.shell("dumpsys", "meminfo", "-s", self.installer.PACKAGE, label="acquisition-installer-memory")
        )
        result["private_free_bytes"] = phone.available(phone.shell("run-as", self.installer.PACKAGE, "df", "-k", ".", label="acquisition-private-free"))
        self.no_admitted_output(phone, no_import=expected == "ERROR")
        if expected == "IMPORTED":
            self.require(
                row.get("manifest_sha256") == self.plans[2]["manifest_sha256"]
                and row.get("game_version") == self.current[1]["game_version"]
                and row.get("completed") == row.get("total") == self.current[3],
                "acquisition-import-receipt-mismatch",
            )
            self.verify_tree(phone, IMPORT + "/files", self.current[2], private=True)
            result.update(files=len(self.current[2]), bytes=self.current[3])
        if expected != "ERROR":
            phone.require_owned_installer()
            phone.shell("run-as", self.installer.PACKAGE, "rm", "-rf", IMPORT, label="acquisition-reset-owned-import-root")
            phone.shell("run-as", self.installer.PACKAGE, "test", "!", "-e", IMPORT, label="acquisition-verified-private-reset")
        passed(case)

    def run(self, phone, passed):
        installer = self.installer
        installer.set_phase("acquisition-storage-and-staging")
        self.require(not phone.occupied(installer.GAME) and not phone.occupied(installer.PACKAGE), "occupied-package-no-fresh-run-ownership")
        self.stage(phone)
        installer.set_phase("acquisition-fresh-installer")
        phone.install(self.apk)
        phone.require_owned_installer()
        self.require(phone.installer_hash == self.apk_hash, "acquisition-installer-changed")
        installer.DIAGNOSTICS.write("acquisition-installer-owned.json", installer.encoded({"package": installer.PACKAGE, "sha256": self.apk_hash}))
        phone.storage_reserve = 20 * GIB + 2 * self.current[3]
        phone.storage()
        local_code = phone.package_paths(installer.PACKAGE)[0][8:]
        self.results["installed_storage"] = {
            "code_free": phone.available(phone.shell("df", "-k", local_code, label="acquisition-installed-code-free")),
            "private_free": phone.available(phone.shell("run-as", installer.PACKAGE, "df", "-k", ".", label="acquisition-installed-private-free")),
            "shared_free": phone.available(phone.shell("df", "-k", self.stage_root, label="acquisition-installed-shared-free")),
        }
        with installer.server() as service:
            base = f"http://127.0.0.1:{service.server_port}/"
            phone.command("reverse", "--no-rebind", "tcp:" + str(service.server_port), "tcp:" + str(service.server_port), label="acquisition-reverse-create")
            phone.reverse_port = service.server_port
            phone.put(
                "debug-release-source.json", installer.encoded({"enabled": True, "base_url": base, "key_id": installer.KEY_ID, "public_key": self.key.decode()})
            )
            phone.start()
            self.prepare_plan(phone, service, 1)
            installer.set_phase("saf-picker-cancelled")
            prior = phone.read("update-state.json")
            self.choose(phone, "tree")
            self.require(phone.read("update-state.json") == prior and phone.read("import-state.json") is None, "acquisition-picker-cancellation-changed-state")
            self.no_admitted_output(phone, no_import=True)
            passed("saf-picker-cancelled")
            supported = self.current[1]["game_version"]
            self.run_case(
                phone, "saf-unknown-refused", "tree", "Older", "ERROR", passed, message=("unknown (no complete reviewed fingerprint matched)", supported)
            )
            self.prepare_plan(phone, service, 2)
            self.run_case(
                phone,
                "saf-unsupported-refused",
                "tree",
                "Older",
                "ERROR",
                passed,
                message=("Found version: " + self.older[1]["game_version"], "Supported versions: [" + supported + "]", "Input refused."),
            )
            self.run_case(phone, "saf-import-cancelled", "tree", "Supported", "CANCELLED", passed)
            self.run_case(phone, "saf-folder-validated", "tree", "Supported", "IMPORTED", passed, message=("Imported verified game files locally",))
            self.run_case(phone, "saf-zip-validated", "zip", "Supported.zip", "IMPORTED", passed, message=("Imported verified game files locally",))
        installer.set_phase("acquisition-source-readback")
        self.staged_unchanged(phone)
        passed("saf-sources-unchanged")
        installer.DIAGNOSTICS.write("acquisition-result.json", installer.encoded(self.results))
