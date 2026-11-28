"""Exercise the installer’s signed input plan with Android document grants."""

import hashlib
import json
from pathlib import Path
import re
import secrets
import shlex
import time
from urllib.parse import unquote, urlsplit
import xml.etree.ElementTree as ET
import zipfile


DOCUMENTS = ("com.android.documentsui", "com.google.android.documentsui")
EXTERNAL_PROVIDER = "com.android.externalstorage.documents"
SUPPORTED_ZIP = "Archive/Supported.zip"
INVALID_ZIP = "Invalid/Invalid.zip"
IMPORT = "files/owner-input/import"
CONTROL = "acquisition-control.json"
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
    expected = {row["path"]: row["sha256"] for row in manifest["files"]}
    sizes = {row["path"]: row["bytes"] for row in manifest["files"]}
    if source is None:
        return None, manifest, expected, sum(sizes.values())
    root = Path(source).resolve(strict=True)
    actual = {}
    for path in root.rglob("*"):
        if path.is_symlink() or not (path.is_file() or path.is_dir()):
            raise ValueError("nonregular-acquisition-source-entry")
        if path.is_file():
            actual[path.relative_to(root).as_posix()] = path.stat().st_size
    if actual != sizes:
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


def stage_folder(phone, source, paths, target):
    # Precreate parents for ADB's file sync on emulated storage.
    parents = sorted({str(Path(path).parent) for path in paths} - {"."})
    directories = [target, *(f"{target}/{parent}" for parent in parents)]
    phone.command("shell", shlex.join(["mkdir", "-p", *directories]), label="acquisition-cohort-directory")
    children = sorted({path.split("/")[0] for path in paths})
    phone.command("push", *(source / child for child in children), target + "/", label="acquisition-stage-folder", timeout=900)


def picker_node(tree, *labels, ids=(), clickable=False):
    package = tree.find("node").get("package")
    resource_ids = {f"{namespace}:id/{name}" for namespace in (package, "android") for name in ids}
    names = {label.casefold() for label in labels}
    matches = [
        node
        for node in tree.iter("node")
        if node.get("package") == package
        and node.get("enabled") == "true"
        and (not clickable or node.get("clickable") == "true")
        and (not resource_ids or node.get("resource-id") in resource_ids)
        and (node.get("text", "").casefold() in names or node.get("content-desc", "").casefold() in names)
    ]
    if len(matches) > 1:
        raise ValueError("acquisition-ambiguous-visible-control")
    return matches[0] if matches else None


def selected_document(preferences, kind, relative_path, *, tools=False):
    values = {entry.get("name"): entry.text for entry in ET.fromstring(preferences).findall("string")}
    uri = urlsplit(values.get("tool_source_uri" if tools else "source_uri") or "")
    actual_kind = "tree" if tools else values.get("source_kind")
    if actual_kind != kind or uri.scheme != "content" or uri.netloc != EXTERNAL_PROVIDER:
        return False
    segment = "tree" if kind == "tree" else "document"
    prefix, _, document = uri.path.rpartition("/")
    return prefix == "/" + segment and unquote(document) == "primary:" + relative_path and not (uri.query or uri.fragment)


def dispatch_control(phone, installer, action):
    command = {"action": action, "id": secrets.token_hex(8)}
    pending = CONTROL + ".pending"
    phone.put(pending, installer.encoded(command))
    prefix = "files/owner-input/"
    phone.shell("run-as", installer.PACKAGE, "mv", prefix + pending, prefix + CONTROL, label="acquisition-publish-control")
    deadline = time.monotonic() + min(phone.timeout, 15)
    while time.monotonic() < deadline:
        if phone.read("acquisition-control-ack.json") == command:
            return
        time.sleep(0.2)
    raise installer.Failure("acquisition-control-unacknowledged-" + action)


class FolderImport:
    def __init__(self, installer, require):
        self.installer, self.require = installer, require
        self.stage_name = "LabAcquisition-" + secrets.token_hex(8)
        self.external_root = "/sdcard/Download"
        self.stage_root = f"{self.external_root}/{self.stage_name}"
        self.owned_stage = False

    def tree_hashes(self, phone, root, *, private=False):
        script = f"cd {shlex.quote(root)} && find . -type f -exec sha256sum {{}} +"
        args = ["run-as", self.installer.PACKAGE] if private else []
        raw = phone.command("shell", shlex.join([*args, "sh", "-c", script]), label="acquisition-tree-hashes", timeout=300)
        return hash_listing(raw)

    def verify_tree(self, phone, root, expected, *, private=False):
        self.require(self.tree_hashes(phone, root, private=private) == expected, "acquisition-tree-hash-mismatch")

    def cleanup(self, phone):
        if self.owned_stage:
            phone.shell("rm", "-rf", self.stage_root, label="acquisition-remove-owned-external-directory")
            phone.shell("test", "!", "-e", self.stage_root, label="acquisition-external-directory-absent")

    def picker_tree(self, phone):
        tree = phone.ui_windows(DOCUMENTS, recovery=False)
        phone.prompt_nodes(tree, DOCUMENTS)
        return tree

    def click_picker(self, phone, tree, labels, label, *, ids=(), clickable=False):
        node = picker_node(tree, *labels, ids=ids, clickable=clickable)
        self.require(node is not None, label + "-unavailable")
        phone.tap_prompt_node(node, label)

    def click_document(self, phone, name):
        tree = self.picker_tree(phone)
        # A long list or a clipped grid card can hide the document title.
        for direction in (-1, 1):
            for _ in range(5):
                node = picker_node(tree, name, ids=("title",))
                if node is not None:
                    phone.tap_prompt_node(node, "acquisition-select-document")
                    return
                scroll = next((node for node in tree.iter("node") if node.get("scrollable") == "true"), None)
                if scroll is None:
                    break
                bounds = list(map(int, re.findall(r"\d+", scroll.get("bounds", ""))))
                self.require(len(bounds) == 4, "acquisition-picker-scroll-bounds")
                x1, y1, x2, y2 = bounds
                x, top, bottom = (x1 + x2) // 2, y1 + (y2 - y1) // 5, y2 - (y2 - y1) // 5
                start, end = (bottom, top) if direction < 0 else (top, bottom)
                phone.shell("input", "swipe", str(x), str(start), str(x), str(end), "250", label="acquisition-scroll-documents")
                tree = self.picker_tree(phone)
        raise self.installer.Failure("acquisition-document-not-visible")

    def require_selection(self, phone, kind, name, *, tools=False):
        preferences = phone.command(
            "shell", "run-as", self.installer.PACKAGE, "cat", "shared_prefs/owner-phone-flow.xml", label="acquisition-selected-document", idempotent=True
        )
        self.require(selected_document(preferences, kind, f"Download/{self.stage_name}/{name}", tools=tools), "acquisition-selected-document-mismatch")

    def choose(self, phone, kind, name=None, *, via_control=False, tools=False):
        if tools:
            self.require(kind == "tree" and not via_control, "acquisition-tools-require-real-folder-picker")
            phone.tap("Choose SDK / tool folder")
        elif via_control:
            dispatch_control(phone, self.installer, "choose-folder" if kind == "tree" else "choose-zip")
        else:
            phone.tap("Choose game folder" if kind == "tree" else "Choose game ZIP")
        tree = self.picker_tree(phone)
        if name is None:
            phone.shell("input", "keyevent", "KEYCODE_BACK", label="acquisition-cancel-focused-picker")
            phone.ui_windows((self.installer.PACKAGE,), recovery=False)
            return
        self.click_picker(phone, tree, ("show roots",), "acquisition-show-picker-locations", clickable=True)
        # Select the device root. The separate Downloads provider can omit ADB-staged files.
        device_name = phone.shell("settings", "get", "global", "device_name", label="acquisition-local-storage-label").decode().strip()
        model = phone.shell("getprop", "ro.product.model", label="acquisition-device-model").decode().strip()
        labels = tuple(name for name in (device_name, model, "internal storage", "internal shared storage") if name and name != "null")
        self.click_picker(phone, self.picker_tree(phone), labels, "acquisition-open-local-storage-root", ids=("title",))
        for part in ("Download", self.stage_name, *name.split("/")):
            self.click_document(phone, part)
        if kind == "tree":
            for text in ("Use this folder", "Allow"):
                self.click_picker(phone, self.picker_tree(phone), (text,), "acquisition-confirm-folder-grant", clickable=True)
        phone.ui_windows((self.installer.PACKAGE,), recovery=False)
        if not tools:
            observed = phone.read("update-state.json")
            self.require(
                observed and observed.get("state") == "INPUT_REQUIRED" and "Source selected." in observed.get("message", ""),
                "acquisition-source-selection-unverified",
            )
        self.require_selection(phone, kind, name, tools=tools)

    def restart_installer(self, phone, kind, name):
        phone.require_owned_installer()
        phone.shell("am", "force-stop", self.installer.PACKAGE, label="acquisition-stop-installer-before-reopen")
        phone.start(repeat_notification_denial=True)
        self.require_selection(phone, kind, name)

    def wait_import(self, phone, expected, *, timeout=360):
        deadline = time.monotonic() + min(phone.timeout, timeout)
        while time.monotonic() < deadline:
            row = phone.read("import-state.json")
            if row:
                state = row.get("state")
                if expected == "COPYING" and state == "IMPORTING" and 0 < row.get("completed", 0) < row.get("total", 0):
                    return row
                if state in {"ERROR", "IMPORTED", "CANCELLED"}:
                    self.require(expected == state, "acquisition-unexpected-import-terminal")
                    return row
            time.sleep(0.5)
        raise self.installer.Failure("acquisition-import-timeout")


class Acquisition(FolderImport):
    def __init__(self, installer, require, request, config, temporary):
        super().__init__(installer, require)
        self.apk = config["installer_apk"]
        self.apk_hash = config["installer_sha256"]
        tools = installer.HostTools(config)
        manifest = installer.run([tools.build / "aapt", "dump", "badging", self.apk], label="inspect-cached-installer-manifest").decode()
        installer.require_installer_manifest(manifest, config["installer_version"])
        components = installer.run(
            [tools.build / "aapt", "dump", "xmltree", self.apk, "AndroidManifest.xml"], label="inspect-acquisition-document-fixture"
        ).decode()
        fixture = "dev.ror2lab.phonebuildhostfixture.AcquisitionFixture"
        require(all(f'="{fixture}${component}"' in components for component in ("Result", "Provider")), "acquisition-fixture-apk-required")
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
            directory = temporary / f"acquisition-release-{version}"
            self.releases[version] = installer.release_fixture(public, authored, version, directory, private, self.key, required_catalog=catalog)
            with zipfile.ZipFile(directory / "public-tools.zip") as bundle:
                plan = public.load_json(bundle.read("bundle-index.json"))["install_plan"]
            self.plans[version] = inputs.input_description(plan, catalog)
        self.archive = temporary / "Supported.zip"
        self.invalid_archive = temporary / "Invalid.zip"
        self.results = {}

    def prepare_archive(self):
        source, manifest, _, _ = self.current
        with zipfile.ZipFile(self.archive, "w", compression=zipfile.ZIP_STORED) as archive:
            for row in manifest["files"]:
                archive.write(source / row["path"], row["path"])
        with self.archive.open("rb") as stream:
            self.archive_hash = hashlib.file_digest(stream, "sha256").hexdigest()
        with zipfile.ZipFile(self.invalid_archive, "w") as archive:
            archive.writestr("Sample.txt", "one")
            archive.writestr("sample.txt", "two")
        self.invalid_archive_hash = hashlib.sha256(self.invalid_archive.read_bytes()).hexdigest()

    def staged_unchanged(self, phone):
        self.verify_tree(phone, self.stage_root + "/Supported", self.current[2])
        self.verify_tree(phone, self.stage_root + "/Older", self.older[2])
        self.verify_tree(phone, self.stage_root + "/Incomplete", {})
        for name, expected in ((SUPPORTED_ZIP, self.archive_hash), (INVALID_ZIP, self.invalid_archive_hash)):
            archive = phone.shell("sha256sum", self.stage_root + "/" + name, label="acquisition-zip-hash", timeout=300).decode().split()
            self.require(len(archive) == 2 and archive[0] == expected, "acquisition-staged-zip-mismatch")

    def stage(self, phone):
        archive_bytes = self.archive.stat().st_size
        staged = self.current[3] + self.older[3] + archive_bytes + self.invalid_archive.stat().st_size
        reserve = 20 * GIB + 2 * self.apk.stat().st_size + staged + 2 * self.current[3]
        phone.storage_reserve = reserve
        phone.storage()
        free = phone.available(phone.shell("df", "-k", self.external_root, label="acquisition-shared-free-before"))
        self.require(free >= reserve, "acquisition-shared-storage-reserve")
        phone.shell("mkdir", self.stage_root, label="acquisition-owned-external-directory")
        self.owned_stage = True
        for folder, entry in (("Supported", self.current), ("Older", self.older)):
            stage_folder(phone, entry[0], entry[2], self.stage_root + "/" + folder)
        phone.shell("mkdir", *(f"{self.stage_root}/{name}" for name in ("Incomplete", "Archive", "Invalid")), label="acquisition-control-directories")
        for archive, name in ((self.archive, SUPPORTED_ZIP), (self.invalid_archive, INVALID_ZIP)):
            phone.command("push", archive, self.stage_root + "/" + name, label="acquisition-stage-zip", timeout=900)
        self.staged_unchanged(phone)
        phone.storage_reserve = 20 * GIB + self.apk.stat().st_size + 2 * self.current[3]
        phone.storage()
        self.results["staged"] = {"bytes": staged, "shared_free_before": free, "zip_bytes": archive_bytes}

    def prepare_plan(self, phone, service, version):
        self.installer.publish(service, self.releases[version], version)
        if version > 1:
            dispatch_control(phone, self.installer, "check")
            update = phone.wait_state({"UPDATE_AVAILABLE"})
            self.require(update.get("release", {}).get("version_code") == version, "acquisition-release-version-not-observed")
        dispatch_control(phone, self.installer, "prepare")
        state = phone.wait_state({"INPUTS_REQUIRED"})
        plan = phone.read("install-inputs.json")
        expected = self.plans[version]
        self.require(
            state.get("release", {}).get("version_code") == version and plan and plan.get("catalog_sha256") == expected["catalog_sha256"],
            "acquisition-signed-plan-not-selected",
        )

    def visible_status(self, phone, state, detail):
        phone.require_visible_status("Game import: " + state, *detail)

    def no_admitted_output(self, phone, *, no_import=False):
        self.require(phone.read("owner-apk-ready.json") is None and not phone.occupied(self.installer.GAME), "acquisition-unverified-apk-admitted")
        if no_import:
            phone.shell("run-as", self.installer.PACKAGE, "test", "!", "-e", IMPORT, label="acquisition-no-private-import")

    def run_case(self, phone, case, kind, name, expected, passed, *, message=(), select=True):
        self.installer.set_phase(case)
        if select:
            self.choose(phone, kind, name, via_control=True)
        if expected == "IMPORTED":
            self.restart_installer(phone, kind, name)
        start = time.monotonic()
        dispatch_control(phone, self.installer, "import")
        row = self.wait_import(phone, "COPYING" if expected == "CANCELLED" else expected)
        result = self.results[case] = {}
        if expected == "CANCELLED":
            result["cancel_observed"] = row["state"]
            result["copied_bytes_at_cancel"] = row["completed"]
            result["total_bytes"] = row["total"]
            dispatch_control(phone, self.installer, "cancel")
            row = self.wait_import(phone, expected)
        self.require(all(part in row.get("message", "") for part in message), "acquisition-import-report-mismatch")
        self.visible_status(phone, expected, message)
        if expected == "CANCELLED":
            control = phone.read("update-control.json")
            self.require(control and control.get("action") == "cancel" and control.get("id"), "acquisition-cancel-control-unverified")
            retained = self.tree_hashes(phone, IMPORT + "/files", private=True)
            self.require(retained.items() < self.current[2].items(), "acquisition-cancel-retained-unverified-files")
            partials = phone.shell("run-as", self.installer.PACKAGE, "find", IMPORT + "/native-staging", "-type", "f", label="acquisition-cancel-partials")
            self.require(not partials.strip(), "acquisition-cancel-left-partial-files")
            result["verified_checkpoint_files"] = len(retained)
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
            result.update(files=len(self.current[2]), bytes=self.current[3], reopened_after_force_stop=True)
            phone.require_owned_installer()
            phone.shell("run-as", self.installer.PACKAGE, "rm", "-rf", IMPORT, label="acquisition-reset-owned-import-root")
            phone.shell("run-as", self.installer.PACKAGE, "test", "!", "-e", IMPORT, label="acquisition-verified-private-reset")
        passed(case)

    def run(self, phone, passed):
        installer = self.installer
        installer.set_phase("acquisition-storage-and-staging")
        self.require(not phone.occupied(installer.GAME) and not phone.occupied(installer.PACKAGE), "occupied-package-no-fresh-run-ownership")
        phone.storage_reserve = 20 * GIB + 2 * self.apk.stat().st_size + self.current[3] * 3 + self.older[3] + self.archive.stat().st_size
        phone.storage()
        installer.set_phase("acquisition-fresh-installer")
        phone.install(self.apk)
        phone.require_owned_installer()
        self.require(phone.installer_hash == self.apk_hash, "acquisition-installer-changed")
        installer.DIAGNOSTICS.write("acquisition-installer-owned.json", installer.encoded({"package": installer.PACKAGE, "sha256": self.apk_hash}))
        phone.storage_reserve = 20 * GIB + 2 * self.current[3]
        phone.storage()
        with installer.server() as service:
            self.run_import_flow(phone, passed, service)
        installer.set_phase("acquisition-source-readback")
        self.staged_unchanged(phone)
        passed("saf-sources-unchanged")
        installer.DIAGNOSTICS.write("acquisition-result.json", installer.encoded(self.results))

    def run_import_flow(self, phone, passed, service):
        installer = self.installer
        base = f"http://127.0.0.1:{service.server_port}/"
        phone.command("reverse", "--no-rebind", "tcp:" + str(service.server_port), "tcp:" + str(service.server_port), label="acquisition-reverse-create")
        phone.reverse_port = service.server_port
        phone.put(
            "debug-release-source.json", installer.encoded({"enabled": True, "base_url": base, "key_id": installer.KEY_ID, "public_key": self.key.decode()})
        )
        installer.set_phase("acquisition-storage-and-staging")
        self.stage(phone)
        local_code = phone.package_paths(installer.PACKAGE)[0][8:]
        self.results["installed_storage"] = {
            "code_free": phone.available(phone.shell("df", "-k", local_code, label="acquisition-installed-code-free")),
            "private_free": phone.available(phone.shell("run-as", installer.PACKAGE, "df", "-k", ".", label="acquisition-installed-private-free")),
            "shared_free": phone.available(phone.shell("df", "-k", self.stage_root, label="acquisition-installed-shared-free")),
        }
        with phone.active_display():
            self.run_picker_cases(phone, passed, service)

    def run_picker_cases(self, phone, passed, service):
        installer = self.installer
        installer.set_phase("acquisition-picker-start")
        phone.start()
        self.results["document_delivery"] = EXTERNAL_PROVIDER
        self.results["control_delivery"] = "private-lab-command-to-installer-button"
        self.prepare_plan(phone, service, 1)
        installer.set_phase("saf-picker-cancelled")
        prior = phone.read("update-state.json")
        self.choose(phone, "tree", via_control=True)
        self.require(phone.read("update-state.json") == prior and phone.read("import-state.json") is None, "acquisition-picker-cancellation-changed-state")
        self.no_admitted_output(phone, no_import=True)
        passed("saf-picker-cancelled")
        supported = self.current[1]["game_version"]
        unknown = ("unknown (no complete reviewed fingerprint matched)", "Supported versions: [" + supported + "]", "Input refused.")
        self.run_case(phone, "saf-unknown-refused", "tree", "Older", "ERROR", passed, message=unknown)
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
        self.run_case(phone, "saf-incomplete-folder-refused", "tree", "Incomplete", "ERROR", passed, message=unknown)
        self.run_case(phone, "saf-invalid-zip-refused", "zip", INVALID_ZIP, "ERROR", passed, message=("Case-aliased ZIP entry",))
        self.run_case(phone, "saf-import-cancelled", "tree", "Supported", "CANCELLED", passed, message=("Verified files retained",))
        imported = ("Imported verified game files locally",)
        self.run_case(phone, "saf-folder-validated", "tree", "Supported", "IMPORTED", passed, message=imported, select=False)
        self.run_case(phone, "saf-zip-validated", "zip", SUPPORTED_ZIP, "IMPORTED", passed, message=imported)
