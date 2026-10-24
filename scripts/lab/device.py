from common import *
import time
import re
import shlex
import zipfile
import copy
import common
from build_timing import PhaseTiming
from device_context import (
    ACTIVATION_MARKER,
    DeviceContextError,
    command_selectors,
    migrate_legacy_receipts,
    receipt_directory,
    select_device,
    storage_policy,
    validate_receipt_directory,
)

PACKAGE = "dev.ror2lab.arm64"
ADB = "/opt/homebrew/bin/adb"


def require_device_access(*, force=False):
    if common.lane_config():
        raise RuntimeError("Build lanes do not own devices; use canonical device commands with explicit APK/payload paths")
    if (force or os.environ.get("LAB_COORDINATION_GUARD") == "1") and (ROOT / "work/coordination/claude-r9.lock").exists():
        raise RuntimeError("Device access blocked by work/coordination/claude-r9.lock")


def physical_display_states(text):
    """Read physical internal panel states; virtual/logical duplicates don't count."""
    states = []
    for line in text.splitlines():
        if "DisplayDeviceInfo{" in line and re.search(r"\btype INTERNAL\b", line):
            match = re.search(r"\bstate (OFF|ON|DOZE|DOZE_SUSPEND|UNKNOWN)\b", line)
            if match:
                states.append(match[1])
    return states


def validate_apk_identity(apk, expected_package=PACKAGE):
    aapt = Path(os.environ["UNITY_ANDROID_ROOT"]) / "SDK/build-tools" / toolchain()["android_build_tools"] / "aapt"
    metadata = run([aapt, "dump", "badging", apk]).stdout.decode(errors="replace")
    package = re.search(r"^package: name='([^']+)'", metadata, re.M)
    if not package or package[1] != expected_package:
        label = "the single owned lab package" if expected_package == PACKAGE else "the separate bootstrap package"
        raise RuntimeError("APK must use " + label + "; refusing another app identity")


class Device:
    _awake_devices = {}

    def __init__(self, selector=None, work_root=None):
        require_device_access()
        selected_work_root = work_root if work_root is not None else common.WORK
        self._work_root = Path(os.path.abspath(os.fspath(selected_work_root)))
        configuration = copy.deepcopy(read(self.work_root / "config/local.json"))
        lines = run([ADB, "devices"]).stdout.decode().splitlines()[1:]
        inventory = [{"serial": p[0], "state": p[1]} for line in lines if len(p := line.split()) >= 2]
        cli, env = command_selectors()
        if selector is not None:
            if cli is not None and selector != cli:
                raise RuntimeError("Conflicting device selectors")
            cli = selector
        serial = select_device(configuration, inventory, cli_selector=cli, env_selector=env)
        self.base = [ADB, "-s", serial]
        self.serial = serial
        self.configuration = configuration
        self.settings = dict(configuration) if serial == configuration["device_serial"] else {}
        self.settings.update(configuration.get("device_settings", {}).get(serial, {}))
        self.settings["storage_mode"] = storage_policy(configuration, serial)
        self.receipt_root = receipt_directory(self.work_root, {"serial": serial, "default_serial": configuration["device_serial"]})
        self.display_awakened = False

    @property
    def work_root(self):
        return getattr(self, "_work_root", WORK)

    def _validated_receipt_root(self):
        try:
            selected = receipt_directory(
                self.work_root,
                {"serial": self.serial, "default_serial": self.configuration["device_serial"]},
            )
            root = validate_receipt_directory(self.work_root, self.receipt_root)
        except DeviceContextError as exc:
            raise RuntimeError("Selected-device receipt directory is unsafe") from exc
        if root != selected:
            raise RuntimeError("Selected-device receipt root changed; recreate the device context")
        return root

    def receipt(self, name):
        if Path(name).name != name or not name.endswith(".json"):
            raise ValueError("Receipt name must be a JSON basename")
        root = self._validated_receipt_root()
        path = root / name
        if path.is_symlink():
            raise RuntimeError("Device receipt cannot be a symlink")
        if path.exists() and not path.is_file():
            raise RuntimeError("Device receipt must be a regular file")
        return path

    def evidence_directory(self, *components):
        """Return a validated local evidence directory without creating it."""
        if not components:
            raise ValueError("At least one evidence directory component is required")
        for component in components:
            if not isinstance(component, str) or not component or component in (".", "..") or "/" in component or "\\" in component or "\x00" in component:
                raise ValueError("Evidence directory components must be safe names")
        root = self._validated_receipt_root()
        candidate = root.joinpath(*components)
        try:
            return validate_receipt_directory(self.work_root, candidate)
        except DeviceContextError as exc:
            raise RuntimeError("Selected-device evidence directory is unsafe") from exc

    def read_receipt(self, name):
        value = read(self.receipt(name))
        if not isinstance(value, dict):
            raise RuntimeError("Device receipt must be a JSON object")
        serial = value.get("serial")
        if serial is not None and serial != self.serial:
            raise RuntimeError("Device receipt belongs to another serial")
        # Old snapshots lack serials. Only the legacy default or a verified
        # migration marker may associate those bytes with the selected device.
        if serial is None and self.receipt_root != self.work_root / "device":
            marker = self.receipt(ACTIVATION_MARKER)
            if not marker.exists() or read(marker).get("serial") != self.serial:
                raise RuntimeError("Device receipt lacks selected serial identity")
        if name == "runtime.json":
            self.validate_runtime(value)
        return value

    def write_receipt(self, name, value):
        require_device_access()
        if name == "runtime.json":
            self.validate_runtime(value)
        write(self.receipt(name), dict(value, serial=self.serial))

    def validate_runtime(self, value):
        path = value.get("persistentDataPath") if isinstance(value, dict) else None
        pattern = r"/(?:storage/(?:emulated/[0-9]+|[A-Za-z0-9-]+)|sdcard)/Android/data/" + re.escape(PACKAGE) + r"/files"
        if not isinstance(path, str) or not re.fullmatch(pattern, path):
            raise RuntimeError("Unexpected runtime content path")
        storage = self.storage()
        parts = self.sh("df", "-k", path).splitlines()[-1].split()
        selected = storage["internal"] if storage["mode"] == "internal" else storage["adopted"]
        if int(parts[1]) * 1024 != selected["total_bytes"]:
            raise RuntimeError("Runtime payload path is not backed by the selected " + storage["mode"] + " volume")

    def migrate_receipts(self):
        require_device_access(force=True)
        if self.serial != self.configuration["device_serial"] or self.receipt_root != self.work_root / "device":
            raise RuntimeError("Only the legacy configured default needs receipt migration")
        proof = self.owned()
        result = migrate_legacy_receipts(
            self.receipt_root,
            self.work_root / "device" / self.serial,
            serial=self.serial,
            ownership_proof=proof,
            coordination_lock=ROOT / "work/coordination/claude-r9.lock",
            install_counter=self.install_counter(),
        )
        self.receipt_root = result["directory"]
        return {key: str(value) if isinstance(value, Path) else value for key, value in result.items()}

    @classmethod
    def sleep_awakened(cls):
        errors = []
        for key, instance in list(cls._awake_devices.items()):
            try:
                instance.display(False)
            except Exception as error:
                errors.append(str(error))
        return errors

    def cmd(self, *args, check=True, timeout=120):
        require_device_access()
        return run(self.base + list(args), check=check, timeout=timeout).stdout.decode(errors="replace").strip()

    def sh(self, *args, check=True):
        return self.cmd("shell", shlex.join(str(a) for a in args), check=check)

    def display(self, awake):
        if not self.settings.get("sleep_display_when_idle", False):
            return False
        models = self.settings.get("display_models")
        if models is None and self.serial == self.configuration["device_serial"]:
            models = ["Retroid Pocket Nova"]
        model = self.sh("getprop", "ro.product.model")
        if not isinstance(models, list) or not models or model not in models:
            raise RuntimeError("Idle display control needs an explicitly authorized exact model (legacy default: Nova)")
        count = self.settings.get("display_count", 1)
        if not isinstance(count, int) or isinstance(count, bool) or count < 1:
            raise RuntimeError("Invalid physical display_count")
        key = (str(self.receipt_root), self.serial)
        thor = model == "AYN Thor"
        if thor and count != 2:
            raise RuntimeError("Thor display control requires display_count 2")
        owner = self._awake_devices.get(key, self)
        if awake:
            self.display_awakened = True
            self._awake_devices.setdefault(key, self)
        try:
            if thor and awake:
                if not hasattr(owner, "thor_display_mode"):
                    original = self.sh("settings", "get", "system", "dual_screen_display_mode")
                    if original not in {"0", "1", "2"}:
                        raise RuntimeError("Unknown Thor dual-screen mode; refusing to change it")
                    owner.thor_display_mode = original
                self.sh("settings", "put", "system", "dual_screen_display_mode", "1")
            # Sleep first so a failed setting restore cannot leave OLEDs awake.
            self.sh("input", "keyevent", "KEYCODE_WAKEUP" if awake else "KEYCODE_SLEEP")
            if thor and not awake and hasattr(owner, "thor_display_mode"):
                original = owner.thor_display_mode
                self.sh("settings", "put", "system", "dual_screen_display_mode", original)
                if self.sh("settings", "get", "system", "dual_screen_display_mode") != original:
                    raise RuntimeError("Thor dual-screen mode was not restored")
                del owner.thor_display_mode
            expected = "Awake" if awake else "Asleep"
            deadline = time.monotonic() + 5
            verified_since = None
            while time.monotonic() < deadline:
                if "mWakefulness=" + expected in self.sh("dumpsys", "power"):
                    if count > 1:
                        display = self.sh("dumpsys", "display")
                        panels = physical_display_states(display)
                        if len(panels) != count or (not awake and any(state != "OFF" for state in panels)) or (awake and "ON" not in panels):
                            verified_since = None
                            time.sleep(0.25)
                            continue
                        if thor and awake:
                            # The vendor mode can merely draw a black overlay.
                            # Require the physical panel itself to report OFF.
                            named = re.findall(r'DisplayDeviceInfo\{"([^"]+)"(?=[^\n]*\btype INTERNAL\b)[^\n]*\bstate (OFF|ON)\b', display)
                            if sorted(named) != [("Built-in Screen", "ON"), ("Screen-2", "OFF")]:
                                verified_since = None
                                time.sleep(0.25)
                                continue
                            if verified_since is None:
                                verified_since = time.monotonic()
                            # Wake transitions can briefly resemble top-only
                            # power before the lower panel finishes waking.
                            if time.monotonic() - verified_since < 1:
                                time.sleep(0.25)
                                continue
                    self.display_awakened = owner.display_awakened = awake
                    if not awake:
                        self._awake_devices.pop(key, None)
                    return True
                verified_since = None
                time.sleep(0.25)
            if thor and awake:
                raise RuntimeError("Thor requires Built-in Screen ON and Screen-2 OFF; vendor mode alone did not establish top-only power")
            raise RuntimeError("Selected device displays did not reach " + expected + "; inspect current power state")
        except Exception as error:
            if thor and awake:
                try:
                    self.display(False)
                except Exception as cleanup:
                    error.add_note("Thor display cleanup failed: " + str(cleanup))
            raise

    def exists(self):
        return ("package:" + PACKAGE) in self.sh("pm", "list", "packages", PACKAGE).splitlines()

    def owned(self):
        receipt = self.receipt("installed.json")
        if not receipt.exists():
            raise RuntimeError("No lab ownership receipt; refusing to modify an existing package")
        r = self.read_receipt("installed.json")
        if r["serial"] != self.serial or r["package"] != PACKAGE or self.sh("pm", "path", PACKAGE) != r["package_path"]:
            raise RuntimeError("Package placement/ownership changed; inspect before modifying")
        return r

    def storage(self):
        mode = self.settings["storage_mode"]
        if mode not in ["adopted", "internal"]:
            raise RuntimeError("Unknown explicitly configured storage mode")
        lines = [x.split() for x in self.sh("sm", "list-volumes", "all").splitlines() if x.startswith("private:") and " mounted " in x]
        if mode == "adopted" and (len(lines) != 1 or not re.fullmatch("[a-fA-F0-9-]+", lines[0][2])):
            raise RuntimeError("Expected exactly one mounted adopted private volume")
        if mode == "internal" and lines:
            raise RuntimeError("Internal-only device now has adopted storage; review device configuration")
        uuid = lines[0][2] if mode == "adopted" else None

        def df(path):
            text = self.sh("df", "-k", path)
            parts = text.splitlines()[-1].split()
            return {"path": path, "total_bytes": int(parts[1]) * 1024, "free_bytes": int(parts[3]) * 1024, "raw": text}

        result = {
            "serial": self.serial,
            "mode": mode,
            "uuid": uuid,
            "internal": df("/data"),
            "adopted": df("/mnt/expand/" + uuid) if uuid else None,
            "shared": df("/sdcard"),
            "install_location": self.sh("pm", "get-install-location"),
        }
        self.write_receipt("storage.json", result)
        return result

    def install(self, apk, mode="streaming"):
        timing = PhaseTiming()
        apk = Path(apk)
        if mode not in {"streaming", "incremental"}:
            raise RuntimeError("Unknown install transport")
        with timing.phase("apk_validation_hash"):
            validate_apk_identity(apk)
            apk_hash = sha(apk)
        if self.exists():
            self.owned()
        with timing.phase("storage_query"):
            storage = self.storage()
        transport = ["--streaming", "--no-incremental"]
        idsig_hash = None
        if mode == "incremental":
            idsig = Path(str(apk) + ".idsig")
            if not idsig.is_file() or idsig.is_symlink():
                raise RuntimeError("Incremental install requires the APK's generated v4 .idsig sidecar")
            if not re.search(r"^feature:android\.software\.incremental_delivery(?:=\d+)?$", self.sh("pm", "list", "features"), re.M):
                raise RuntimeError("Selected device does not advertise incremental delivery; use streaming")
            # adb's explicit mode verifies the sidecar and must fail rather than
            # silently substituting a different transport for this measurement.
            idsig_hash = sha(idsig)
            transport = ["--incremental", "--wait"]
        limit = self.settings.get("apk_install_limit")
        counter = self.install_counter()
        prior_counter = read(counter) if counter.exists() else {"serial": self.serial, "dispatched": 0}
        used = prior_counter.get("dispatched", 0)
        if prior_counter.get("serial") != self.serial or not isinstance(used, int) or isinstance(used, bool) or used < 0:
            raise RuntimeError("Invalid selected-device install counter; inspect before installing")
        if limit is not None:
            if not isinstance(limit, int) or isinstance(limit, bool) or limit < 1:
                raise RuntimeError("Invalid APK installation limit")
            if used >= limit:
                if self.exists():
                    prior = self.owned()
                    if prior["apk_sha256"] == apk_hash:
                        return dict(prior, reused=True, install_output="Existing receipted identical APK reused; no installation dispatched")
                raise RuntimeError("Authorized APK installation limit exhausted; retain current APK")
        self.install_capacity(apk, storage)
        write(counter, {"serial": self.serial, "dispatched": used + 1, "apk_sha256": apk_hash, "status": "dispatched; verify installation receipt"})
        t = time.monotonic()
        try:
            with timing.phase("adb_install"):
                output = self.cmd("install", *transport, "-r", "--force-uuid", storage["uuid"] or "internal", str(apk), timeout=240)
        except Exception as error:
            self.write_receipt(
                "install-attempt.json",
                {"success": False, "apk_sha256": apk_hash, "transport": mode, "error": str(error), "storage": storage, "timing": timing.report()},
            )
            raise
        with timing.phase("placement_query"):
            package_path = self.sh("pm", "path", PACKAGE)
            details = self.sh("dumpsys", "package", PACKAGE)
        r = {
            "serial": self.serial,
            "package": PACKAGE,
            "apk": str(apk),
            "apk_sha256": apk_hash,
            "package_path": package_path,
            "details": details,
            "seconds": time.monotonic() - t,
            "install_output": output,
            "storage": storage,
            "transport": mode,
            "v4_idsig_sha256": idsig_hash,
            "timing": timing.report(),
        }
        self.write_receipt("installed.json", r)
        expected = "/data/app/" if storage.get("mode") == "internal" else "/mnt/expand/" + storage["uuid"] + "/"
        if expected not in r["package_path"]:
            raise RuntimeError("Placement verification failed; lab receipt saved, inspect before next action")
        return r

    def validate_apk(self, apk, expected_package):
        validate_apk_identity(apk, expected_package)

    def install_counter(self):
        receipt_root = self._validated_receipt_root()
        legacy_root = self.work_root / "device"
        if receipt_root == legacy_root:
            parent = self.work_root / "device-install-limits"
            try:
                parent = validate_receipt_directory(self.work_root, parent)
            except DeviceContextError as exc:
                raise RuntimeError("Selected-device install-counter directory is unsafe") from exc
            path = parent / (digest(self.serial) + ".json")
            if path.is_symlink() or (path.exists() and not path.is_file()):
                raise RuntimeError("Selected-device install counter is not a regular file")
            return path
        return self.receipt("device-install-limit.json")

    def install_capacity(self, apk, storage):
        """Shared lab/bootstrap capacity gate; no device writes or package changes."""
        apk = Path(apk)
        with zipfile.ZipFile(apk) as z:
            abis = {n.split("/")[1] for n in z.namelist() if n.startswith("lib/") and n.endswith(".so")}
            native = sum(i.file_size for i in z.infolist() if i.filename.startswith("lib/"))
        if abis != {"arm64-v8a"}:
            raise RuntimeError("APK must contain only arm64-v8a; found " + str(abis))
        reserve_mib = self.settings.get("internal_reserve_mib", 1024)
        if not isinstance(reserve_mib, int) or isinstance(reserve_mib, bool) or reserve_mib < 1024:
            raise RuntimeError("internal_reserve_mib must reserve at least 1024 MiB")
        reserve = reserve_mib * 1024**2
        estimate = apk.stat().st_size * 3 + native
        if storage["internal"]["free_bytes"] < reserve + estimate:
            raise RuntimeError("Insufficient internal installation scratch headroom; do not move/remove games")
        volume = storage["internal"] if storage.get("mode") == "internal" else storage["adopted"]
        if volume["free_bytes"] < estimate + reserve:
            raise RuntimeError("Insufficient selected storage headroom")
        return {"estimate_bytes": estimate, "reserve_bytes": reserve}

    def launch(self):
        self.owned()
        self.display(True)
        self.sh("am", "force-stop", PACKAGE)
        start = self.sh("date", "+%s.%N")
        launch = self.sh("am", "start", "-W", "-n", PACKAGE + "/com.unity3d.player.UnityPlayerActivity")
        deadline = time.monotonic() + 45
        logs = ""
        pid = ""
        while time.monotonic() < deadline:
            pid = self.sh("pidof", PACKAGE, check=False).strip()
            if pid:
                logs = self.cmd("logcat", "-d", "--pid=" + pid, "-v", "epoch", "Unity:I", "AndroidRuntime:E", "*:S")
                if "LAB_READY" in logs:
                    break
            time.sleep(1)
        snapshots = []
        for line in logs.splitlines():
            if "LAB_SNAPSHOT {" in line:
                try:
                    snapshots.append(json.loads(line.split("LAB_SNAPSHOT ", 1)[1]))
                except ValueError:
                    pass
        if not snapshots:
            match = re.search(r'"persistentDataPath":"([^"]+)"', logs)
            if match:
                path = match.group(1)
                if not path.endswith("/Android/data/" + PACKAGE + "/files"):
                    raise RuntimeError("Unexpected diagnostic path")
                snapshots.append(json.loads(self.sh("cat", path + "/snapshot.json")))
        if snapshots:
            self.write_receipt("runtime.json", snapshots[-1])
        result = {
            "launch": launch,
            "pid": pid,
            "device_start": start,
            "checkpoint": "LAB_READY" in logs,
            "managed_assembly": "LAB_MANAGED_ASSEMBLY_OK" in logs,
            "geometry": "LAB_GEOMETRY_OK" in logs,
            "log": logs,
        }
        self.write_receipt("last-run.json", result)
        if not result["checkpoint"]:
            raise RuntimeError("Runtime checkpoint failed; inspect selected-device last-run.json and ./dev crash")
        return result

    def sync(self, payload_directory=None):
        timing = PhaseTiming()
        self.owned()
        runtime = self.read_receipt("runtime.json")
        path = runtime["persistentDataPath"]
        with timing.phase("storage_query"):
            storage = self.storage()
        if not path.endswith("/Android/data/" + PACKAGE + "/files"):
            raise RuntimeError("Unexpected runtime content path; inspect storage before extending sync policy")
        if storage["mode"] == "adopted":
            # Refuse a physical-internal emulated root before creating or transferring data.
            parts = self.sh("df", "-k", path).splitlines()[-1].split()
            if int(parts[1]) * 1024 != storage["adopted"]["total_bytes"]:
                raise RuntimeError("Runtime payload path is not backed by the selected adopted volume")
        dest = path + "/payload"
        self.sh("mkdir", "-p", dest)
        files = list((Path(payload_directory) if payload_directory is not None else self.work_root / "generated-android-data").glob("*"))
        if payload_directory is not None and not files:
            raise RuntimeError("Payload directory is empty or missing")
        manifest = []
        for p in sorted(files):
            if not p.is_file() or p.suffix == ".manifest":
                continue
            with timing.phase("local_hash"):
                h = sha(p)
            remote = dest + "/" + p.name
            if not re.fullmatch("[A-Za-z0-9_.-]+", p.name):
                raise RuntimeError("Unsafe payload filename")
            with timing.phase("remote_hash"):
                existing = self.sh("sha256sum", remote, check=False).split()
            changed = not existing or existing[0] != h
            if changed:
                volume = storage["internal"] if storage.get("mode") == "internal" else storage["adopted"]
                if volume["free_bytes"] < p.stat().st_size * 2 + 1024**3:
                    raise RuntimeError("Payload exceeds selected free space")
                with timing.phase("push"):
                    self.cmd("push", str(p), remote + ".partial", timeout=300)
                with timing.phase("transfer_verification"):
                    got = self.sh("sha256sum", remote + ".partial").split()[0]
                if got != h:
                    raise RuntimeError("Transferred payload hash mismatch")
                self.sh("mv", remote + ".partial", remote)
            manifest.append({"name": p.name, "sha256": h, "bytes": p.stat().st_size, "transferred": changed})
        result = {"runtime_path": path, "backing_df": self.sh("df", "-k", path), "files": manifest, "timing": timing.report()}
        self.write_receipt("sync.json", result)
        return result

    def collect(self, kind, out):
        if kind in ["all", "screenshot"]:
            self.display(True)
        out.mkdir(parents=True, exist_ok=True)
        result = {}
        if kind in ["all", "logs"]:
            pid = self.sh("pidof", PACKAGE, check=False).strip()
            logs = self.cmd("logcat", "-d", *(["--pid=" + pid] if pid else []), "-v", "threadtime", "Unity:I", "AndroidRuntime:E", "*:S")
            (out / "unity.log").write_text(logs)
        if kind in ["all", "crash"]:
            (out / "crash.log").write_text(self.cmd("logcat", "-b", "crash", "-d", "-v", "threadtime"))
            (out / "exit-info.txt").write_text(self.sh("dumpsys", "activity", "exit-info", PACKAGE, check=False))
            (out / "tombstone-access.txt").write_text(self.sh("ls", "/data/tombstones", check=False) or "Not accessible on this non-root device")
        if kind in ["all", "screenshot"]:
            require_device_access()
            data = run(self.base + ["exec-out", "screencap", "-p"]).stdout
            if not data.startswith(b"\x89PNG\r\n\x1a\n"):
                raise RuntimeError("Invalid screenshot")
            (out / "screenshot.png").write_bytes(data)
        if kind in ["all", "perf"]:
            for name, args in {
                "memory": ["dumpsys", "meminfo", PACKAGE],
                "gfxinfo": ["dumpsys", "gfxinfo", PACKAGE],
                "thermal": ["dumpsys", "thermalservice"],
                "cpu": ["dumpsys", "cpuinfo"],
            }.items():
                (out / (name + ".txt")).write_text(self.sh(*args, check=False))
            # Some Android builds omit HAL temperatures but expose read-only kernel zones.
            # Preserve raw values/types; calibration, sentinel filtering and throttling are
            # separate observations. The Linux temperature ABI uses millidegree Celsius.
            zones = 'for z in /sys/class/thermal/thermal_zone*; do [ -r "$z/type" ] && [ -r "$z/temp" ] || continue; t=$(cat "$z/type" 2>/dev/null); v=$(cat "$z/temp" 2>/dev/null); [ -n "$t" ] && [ -n "$v" ] || continue; printf "%s\\t%s\\t%s\\n" "${z##*/}" "$t" "$v"; done'
            (out / "thermal-zones.txt").write_text(self.sh("sh", "-c", zones, check=False))
            if self.receipt("runtime.json").exists():
                path = self.read_receipt("runtime.json")["persistentDataPath"]
                for name in ["snapshot.json", "exceptions.jsonl"]:
                    text = self.sh("cat", path + "/" + name, check=False)
                    if text:
                        (out / name).write_text(text)
                (out / "private-path.txt").write_text(self.sh("run-as", PACKAGE, "pwd", check=False))
                (out / "native-maps.txt").write_text(
                    self.sh("run-as", PACKAGE, "cat", "/proc/" + self.sh("pidof", PACKAGE, check=False).strip() + "/maps", check=False)
                )
        return {"artifacts": str(out.relative_to(self.work_root.parent))}

    def reset(self):
        if not self.exists():
            return {"removed": False, "reason": "package absent"}
        self.owned()
        result = self.cmd("uninstall", PACKAGE)
        self.receipt("installed.json").unlink()
        return {"uninstall": result, "removed": not self.exists()}


def smoke(apk):
    d = Device()
    out = WORK / "runs" / (now() + "-" + sha(apk)[:12])
    out.mkdir(parents=True)
    result = {"success": False, "apk_sha256": sha(apk), "run_id": out.name, "started": now()}
    had_package = d.exists()
    try:
        result["install"] = d.install(apk)
        d.launch()
        result["sync"] = d.sync()
        result["runtime"] = d.launch()
        time.sleep(3)
        d.collect("all", out)
        runtime = result["runtime"]
        result["success"] = runtime["checkpoint"] and runtime["managed_assembly"] and runtime["geometry"]
        result["graphics_gate"] = "G2" if runtime["geometry"] else "G1"
        result["failure_class"] = None if result["success"] else "runtime-checkpoint"
    except Exception as e:
        result["error"] = str(e)
        result["failure_class"] = "install-storage" if "storage" in str(e).lower() else "first-failure"
        try:
            if "install" in result:
                d.collect("all", out)
        except Exception as collection_error:
            result["collection_error"] = str(collection_error)
    finally:
        # Only remove a package first installed by this smoke transaction.
        if not had_package and d.receipt("installed.json").exists():
            try:
                result["cleanup"] = d.reset()
            except Exception as e:
                result["cleanup_error"] = str(e)
                result["success"] = False
        write(out / "result.json", result)
        write(WORK / "runs/latest.json", {"path": str(out.relative_to(ROOT)), "success": result["success"]})
    print(json.dumps({"success": result["success"], "artifacts": str(out.relative_to(ROOT)), "error": result.get("error")}, indent=2))
    if not result["success"]:
        raise RuntimeError("Smoke failed: " + str(out))
