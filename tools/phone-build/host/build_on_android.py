"""Build the authored sandbox fixture on Android with explicit supplied tools.

Usage: python3 -I -S build_on_android.py OWNED_TOOL_ROOT NEW_OUTPUT
The staging directory supplies android.jar, d8.jar and apksigner.jar privately.
"""

import hashlib
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import zipfile


def build(tool_root, output):
    source = Path(__file__).resolve().parent
    tool_root = Path(tool_root).resolve(strict=True)
    output = Path(output).resolve()
    output.mkdir(mode=0o700, parents=False, exist_ok=False)
    os.umask(0o077)
    native = tool_root / "usr"
    packaging = tool_root / "packaging/usr"
    java = packaging / "lib/jvm/java-21-openjdk/bin/java"
    env = dict(os.environ)
    env["LD_LIBRARY_PATH"] = ":".join(str(tool_root / part) for part in ("packaging/usr/lib", "python/usr/lib", "usr/lib"))
    env["ROR2_PHONE_SIGNING_PASSWORD"] = secrets.token_urlsafe(40)
    result = {"schema": 1, "success": False, "commands": [], "inputs": {}, "disposable_key": True, "password_persisted": False}

    def run(command, label):
        command = [str(part) for part in command]
        process = subprocess.run(command, env=env, capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=180)
        (output / (label + ".log")).write_text(process.stdout + process.stderr)
        result["commands"].append({"label": label, "args": command, "exit": process.returncode})
        if process.returncode:
            raise RuntimeError(label + " exit " + str(process.returncode))

    try:
        for name in ("NativeProbe.c", "HostProbeActivity.java", "AndroidManifest.xml", "build_on_android.py", "android.jar", "d8.jar", "apksigner.jar"):
            result["inputs"][name] = hashlib.sha256((source / name).read_bytes()).hexdigest()
        binary = output / "libtoolprobe.so"
        run(
            [
                native / "bin/clang-21",
                "--target=aarch64-linux-android24",
                "--sysroot=" + str(native),
                "-resource-dir=" + str(native / "lib/clang/21"),
                "--ld-path=" + str(native / "bin/lld"),
                "-B" + str(native / "lib"),
                "-L/system/lib64",
                "-O2",
                "-fPIE",
                "-pie",
                source / "NativeProbe.c",
                "-o",
                binary,
            ],
            "native-compile-link",
        )
        run([binary], "shell-control")
        classes = output / "classes"
        classes.mkdir()
        run(
            [
                java.with_name("javac"),
                "-source",
                "8",
                "-target",
                "8",
                "-bootclasspath",
                source / "android.jar",
                "-d",
                classes,
                source / "HostProbeActivity.java",
            ],
            "javac",
        )
        class_jar = output / "classes.jar"
        with zipfile.ZipFile(class_jar, "w", zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(classes.rglob("*.class")):
                archive.write(path, path.relative_to(classes).as_posix())
        dex = output / "dex"
        dex.mkdir()
        run([java, "-cp", source / "d8.jar", "com.android.tools.r8.D8", "--min-api", "24", "--lib", source / "android.jar", "--output", dex, class_jar], "dex")
        unsigned = output / "unsigned.apk"
        run([packaging / "bin/aapt", "package", "-f", "-M", source / "AndroidManifest.xml", "-I", source / "android.jar", "-F", unsigned], "aapt")
        with zipfile.ZipFile(unsigned, "a", zipfile.ZIP_DEFLATED) as archive:
            archive.write(dex / "classes.dex", "classes.dex")
            archive.write(binary, "lib/arm64-v8a/libtoolprobe.so")
            archive.write(binary, "assets/control.bin")
        aligned = output / "aligned.apk"
        signed = output / "signed.apk"
        run([packaging / "bin/zipalign", "-P", "16", "-v", "4", unsigned, aligned], "align")
        run(
            [
                java.with_name("keytool"),
                "-genkeypair",
                "-alias",
                "phonefixture",
                "-dname",
                "CN=Local Authored Fixture",
                "-keystore",
                output / "owner.p12",
                "-storetype",
                "PKCS12",
                "-storepass:env",
                "ROR2_PHONE_SIGNING_PASSWORD",
                "-keypass:env",
                "ROR2_PHONE_SIGNING_PASSWORD",
                "-keyalg",
                "RSA",
                "-keysize",
                "2048",
                "-validity",
                "3650",
                "-noprompt",
            ],
            "keytool",
        )
        run(
            [
                java,
                "-jar",
                source / "apksigner.jar",
                "sign",
                "--ks",
                output / "owner.p12",
                "--ks-key-alias",
                "phonefixture",
                "--ks-pass",
                "env:ROR2_PHONE_SIGNING_PASSWORD",
                "--key-pass",
                "env:ROR2_PHONE_SIGNING_PASSWORD",
                "--out",
                signed,
                aligned,
            ],
            "sign",
        )
        run([java, "-jar", source / "apksigner.jar", "verify", "--verbose", "--print-certs", signed], "verify")
        run([packaging / "bin/zipalign", "-c", "-P", "16", "-v", "4", signed], "alignment-check")
        result.update(success=True, apk_sha256=hashlib.sha256(signed.read_bytes()).hexdigest(), native_sha256=hashlib.sha256(binary.read_bytes()).hexdigest())
    except Exception as error:
        result["failure"] = str(error)
    finally:
        env.pop("ROR2_PHONE_SIGNING_PASSWORD", None)
        (output / "build-result.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({key: value for key, value in result.items() if key != "commands"}))
    return result["success"]


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    raise SystemExit(0 if build(*sys.argv[1:]) else 1)
