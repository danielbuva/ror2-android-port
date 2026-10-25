"""Produce fixed-target generic Android packaging from the owner's pinned SDK.

Experimental support, separate from game content/code production. No Editor,
project, game/accepted APK input, download, signing or installation is used.
"""

import argparse
import importlib.util
import os
import json
from pathlib import Path
import shutil
import time
import xml.etree.ElementTree as ET
import zipfile

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("package_sdk_inputs", HERE / "sdk_inputs.py")
SDK = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SDK)
SPEC = importlib.util.spec_from_file_location("package_native_tools", HERE.parent / "owner-code/native.py")
NATIVE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(NATIVE)
TOOL_JARS = {
    "r8-4.0.52.jar": "fa389bea8e55b3e074684a870e59ed14f91dfcb5ef102a846e63550a3d70ac66",
    "gradle-7.4.2.jar": "d426478af963bd2276feb840fc97b8590edb1392670f587e838fd63f829fbd24",
    "gradle-api-7.4.2.jar": "8e3666641b5927851b830a8ab80ef90ccec3780305c7cc4e6972291114404aeb",
    "builder-7.4.2.jar": "346ca459bd3b4b3a1148f6c8ad31b69049e84f269132eddd6d28e2d513dd360e",
    "sdk-common-30.4.2.jar": "3c5517b9a65fd33c2a1caeab787306d4e3bb233713e7bb47bacddcd84db2ea0d",
    "common-30.4.2.jar": "1adc8a7156526618fe2d3243067a1d61c90c43f6b52515edaafe862bfb156f28",
    "layoutlib-api-30.4.2.jar": "6b668eb1875462d558d5130061321b504385a69c4c1303036da4793768ed592b",
    "guava-31.1-jre.jar": "a42edc9cab792e39fe39bb94f3fca655ed157ff87a8af78e1d6ba5b07c4a00ab",
    "javawriter-2.5.0.jar": "fcfb09fb0ea0aa97d3cfe7ea792398081348e468f126b3603cb3803f240197f0",
    "kotlin-stdlib-1.7.10.jar": "e771fe74250a943e8f6346713201ff1d8cb95c3a5d1a91a22b65a9e04f6a8901",
    "asm-9.2.jar": "b9d4fe4d71938df38839f0eca42aaaa64cf8b313d678da036f0cb3ca199b47f5",
    "asm-commons-9.2.jar": "be4ce53138a238bb522cd781cf91f3ba5ce2f6ca93ec62d46a162a127225e0a6",
    "zipflinger-7.4.2.jar": "d82b239494dd262e65cd94b2edf96c9b5cf19c7afbfc84f2601749f50e15c765",
}

PLATFORM_SHA = "96ccfdc84d15fad4e22d76cbb8ef38b150a4b56327957067875ca7e18113a424"
AAPT_SHAS = {
    "2139ac7d52fa511c5847784c7950badbb6b1aa6a5b82de6f8e514f871e15a294",
    "78f4adbe27a5278ea2fb37e4a4cc704fa3cedf0b46b2873a3e3bba4e15de4880",
}
ANDROID = "http://schemas.android.com/apk/res/android"
ET.register_namespace("android", ANDROID)


def attr(name):
    return "{" + ANDROID + "}" + name


def sdk_state(sdk):
    files = SDK.FILES | SDK.ANDROID_FILES
    for name, (size, digest) in files.items():
        path = sdk / name
        if path.resolve(strict=True) != path or not path.is_file() or path.stat().st_size != size or NATIVE.sha(path) != digest:
            raise ValueError("pinned Android SDK input differs: " + name)
    return {name: digest for name, (_, digest) in files.items()}


def manifest(sdk):
    """Merge generic SDK entry points with the authored fixed-target settings."""
    root = SDK.xml((sdk / "Apk/LauncherManifest.xml").read_bytes())
    root.set("package", "dev.ror2lab.arm64")
    root.set(attr("installLocation"), "auto")
    root.set(attr("versionCode"), "1")
    root.set(attr("versionName"), "1.0")
    root.insert(0, ET.Element("uses-sdk", {attr("minSdkVersion"): "23", attr("targetSdkVersion"): "30"}))
    application = root.find("application")
    root.remove(application)
    ET.SubElement(root, "uses-feature", {attr("name"): "android.hardware.vulkan.version"})
    for name in ("INTERNET", "CHANGE_WIFI_MULTICAST_STATE"):
        ET.SubElement(root, "uses-permission", {attr("name"): "android.permission." + name})
    for name in ("sensor.accelerometer", "touchscreen", "touchscreen.multitouch", "touchscreen.multitouch.distinct"):
        ET.SubElement(root, "uses-feature", {attr("name"): "android.hardware." + name, attr("required"): "false"})
    root.append(application)
    application.set(attr("debuggable"), "true")
    application.set(attr("extractNativeLibs"), "true")
    activity = SDK.xml((sdk / "Apk/UnityManifest.xml").read_bytes()).find("application/activity")
    application.append(activity)
    for name, value in {
        "launchMode": "singleTask",
        "screenOrientation": "fullUser",
        "configChanges": "mcc|mnc|locale|touchscreen|keyboard|keyboardHidden|navigation|orientation|screenLayout|uiMode|screenSize|smallestScreenSize|fontScale|layoutDirection|density",
        "hardwareAccelerated": "false",
        "resizeableActivity": "false",
    }.items():
        activity.set(attr(name), value)
    ET.SubElement(activity, "meta-data", {attr("name"): "android.notch_support", attr("value"): "true"})
    for name, value in {
        "unity.splash-mode": "0",
        "unity.splash-enable": "true",
        "unity.launch-fullscreen": "true",
        "notch.config": "portrait|landscape",
        "unity.auto-report-fully-drawn": "true",
    }.items():
        ET.SubElement(application, "meta-data", {attr("name"): name, attr("value"): value})
    ET.indent(root, space="    ")
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def resources(sdk, android_jar, aapt, output, *, formatter, prefix=()):
    """Compile SDK resources and the authored package settings in a new root."""
    sdk, aapt, output = Path(sdk).absolute(), Path(aapt).absolute(), Path(output).absolute()
    android_jar = NATIVE.canonical(str(Path(android_jar).absolute()))
    if aapt != aapt.resolve(strict=True) or NATIVE.sha(aapt) not in AAPT_SHAS or NATIVE.sha(android_jar) != PLATFORM_SHA:
        raise ValueError("pinned AAPT2/platform input required")
    state = sdk_state(sdk)
    NATIVE.disjoint(output, [sdk, aapt, android_jar])
    output.mkdir(mode=0o700)
    for name in ("logs", "tmp", "res", "apk"):
        (output / name).mkdir()
    result = {"success": False, "sdk_files": state, "editor_actions": 0, "game_input_files": 0}
    started = time.monotonic()
    try:
        for name in SDK.ANDROID_FILES:
            if name.startswith("Apk/res/"):
                path = output / "res" / name.removeprefix("Apk/res/")
                path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(sdk / name, path)
        strings = output / "res/values/strings.xml"
        root = SDK.xml(strings.read_bytes())
        next(node for node in root if node.get("name") == "app_name").text = "RoR2 Porting Lab"
        strings.write_bytes(ET.tostring(root, encoding="utf-8", xml_declaration=True))
        (output / "manifest-source.xml").write_bytes(manifest(sdk))
        NATIVE.invoke(
            [*formatter, "manifest", str(output / "manifest-source.xml"), str(output / "AndroidManifest.xml")],
            output,
            "format-manifest",
            env=dict(os.environ, LC_ALL="C", TMPDIR=str(output / "tmp")),
        )
        NATIVE.invoke(
            [*prefix, str(aapt), "compile", "--no-crunch", "--dir", str(output / "res"), "-o", str(output / "compiled.zip")],
            output,
            "compile-resources",
            env=dict(os.environ, LC_ALL="C", TMPDIR=str(output / "tmp")),
        )
        NATIVE.invoke(
            [
                *prefix,
                str(aapt),
                "link",
                "-o",
                str(output / "resources.apk"),
                "--manifest",
                str(output / "AndroidManifest.xml"),
                "-I",
                str(android_jar),
                "--min-sdk-version",
                "23",
                "--target-sdk-version",
                "30",
                "--version-code",
                "1",
                "--version-name",
                "1.0",
                "--compile-sdk-version-code",
                "30",
                "--compile-sdk-version-name",
                "11",
                "--output-text-symbols",
                str(output / "R.txt"),
                str(output / "compiled.zip"),
            ],
            output,
            "link-resources",
            env=dict(os.environ, LC_ALL="C", TMPDIR=str(output / "tmp")),
        )
        with zipfile.ZipFile(output / "resources.apk") as archive:
            for name in archive.namelist():
                if name not in ("AndroidManifest.xml", "resources.arsc") and not name.startswith("res/"):
                    raise ValueError("unexpected Android resource output")
                target = output / "apk" / NATIVE.relative(name)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(archive.read(name))
        for library in ("libmain.so", "libunity.so"):
            path = output / "apk/lib/arm64-v8a" / library
            path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(sdk / "Variations/il2cpp/Development/Libs/arm64-v8a" / library, path)
        result.update(success=True, files={str(p.relative_to(output)): NATIVE.sha(p) for p in sorted((output / "apk").rglob("*")) if p.is_file()})
        if sdk_state(sdk) != state:
            raise ValueError("Android SDK inputs changed")
        return result
    finally:
        result["seconds"] = time.monotonic() - started
        (output / "result.json").write_text(json.dumps(result, indent=2) + "\n")


def produce(request):
    """One source-only SDK Android slice, with exact public-tool admission."""
    if set(request) - {"aapt_prefix"} != {"sdk", "android_jar", "aapt", "java", "javac", "jars", "output"}:
        raise ValueError("explicit SDK, platform, public tools and new output required")
    paths = {name: NATIVE.canonical(request[name]) for name in ("sdk", "android_jar", "aapt", "java", "javac")}
    if set(request["jars"]) != set(TOOL_JARS):
        raise ValueError("exact public Android Java tool cohort required")
    jars = {name: NATIVE.canonical(request["jars"][name]) for name in TOOL_JARS}
    if any(NATIVE.sha(path) != TOOL_JARS[name] for name, path in jars.items()):
        raise ValueError("public Android Java tool hash differs")
    state = sdk_state(paths["sdk"])
    output = Path(request["output"])
    NATIVE.disjoint(output, [*paths.values(), *jars.values()])
    if shutil.disk_usage(output.parent).free < 2 * 1024**3:
        raise RuntimeError("insufficient Android packaging reserve")
    output.mkdir(mode=0o700)
    for name in ("logs", "tmp", "helper"):
        (output / name).mkdir()
    started = time.monotonic()
    result = {"success": False, "game_input_files": 0, "editor_actions": 0, "jars": TOOL_JARS}
    try:
        classpath = os.pathsep.join(str(p) for p in jars.values())
        NATIVE.invoke(
            [str(paths["javac"]), "-source", "11", "-target", "11", "-cp", classpath, "-d", str(output / "helper"), str(HERE / "SdkAndroidCode.java")],
            output,
            "compile-helper",
            env=dict(os.environ, LC_ALL="C", TMPDIR=str(output / "tmp")),
        )
        java = [str(paths["java"]), "-Xmx512m", "-XX:ActiveProcessorCount=2", "-cp", str(output / "helper") + os.pathsep + classpath, "SdkAndroidCode"]
        resources(paths["sdk"], paths["android_jar"], paths["aapt"], output / "resources", formatter=java, prefix=request.get("aapt_prefix", []))
        NATIVE.invoke(
            [*java, str(paths["sdk"]), str(paths["android_jar"]), str(output / "resources/R.txt"), str(output / "dex")],
            output,
            "produce-dex",
            env=dict(os.environ, LC_ALL="C", TMPDIR=str(output / "tmp")),
        )
        tree = output / "resources/apk"
        for name in ("classes.dex", "classes2.dex", "classes3.dex", "classes4.dex"):
            shutil.copyfile(output / "dex" / name, tree / name)
        if sdk_state(paths["sdk"]) != state or any(NATIVE.sha(path) != TOOL_JARS[name] for name, path in jars.items()):
            raise ValueError("Android SDK/tool inputs changed")
        result.update(success=True, files={str(p.relative_to(tree)): NATIVE.sha(p) for p in sorted(tree.rglob("*")) if p.is_file()})
        return result
    finally:
        result["seconds"] = time.monotonic() - started
        (output / "result.json").write_text(json.dumps(result, indent=2) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", required=True, help="private explicit SDK/tool paths and new output")
    args = parser.parse_args()
    print(json.dumps(produce(json.loads(Path(args.request).read_text()))))


if __name__ == "__main__":
    main()
