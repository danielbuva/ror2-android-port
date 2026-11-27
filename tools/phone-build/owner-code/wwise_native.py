"""Rebuild the owner-supplied Android Wwise integration with a local Clang."""

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import struct
import time

NATIVE_SPEC = importlib.util.spec_from_file_location("owner_wwise_native_stage", Path(__file__).with_name("native.py"))
native = importlib.util.module_from_spec(NATIVE_SPEC)
NATIVE_SPEC.loader.exec_module(native)

LIBRARY = "libAkSoundEngine.so"
DIAGNOSTICS = Path(__file__).resolve().with_name("wwise-native")
POLICY = native.ROOT / "recipe/owner-wwise-native.json"
EXPORTS_SHA256 = "2952bcc16fa9e6765aeacefdfc089f8c9eb24797a9c799013f37a1bf61799079"
DEPENDENCIES = {"libOpenSLES.so", "libandroid.so", "libc.so", "libdl.so", "liblog.so", "libm.so", "libz.so"}
ANDROID_SOURCES = (
    "AkDefaultIOHookDeferred.cpp",
    "AkFileHelpers.cpp",
    "SoundEngine_wrap.cxx",
    "stdafx.cpp",
)
COMMON_SOURCES = (
    "AkFileLocationBase.cpp",
    "AkFilePackage.cpp",
    "AkFilePackageLUT.cpp",
    "AkGeneratedSoundBanksResolver.cpp",
    "AkUnityErrorMessageTranslator.cpp",
)
ARCHIVES = (
    "AkMusicEngine",
    "AkSpatialAudio",
    "AkMemoryMgr",
    "AkStreamMgr",
    "CommunicationCentral",
    "AkSoundEngine",
    "AkSilenceSource",
    "AkSineSource",
    "AkToneSource",
    "AkSynthOneSource",
    "AkVorbisDecoder",
    "AkOpusDecoder",
    "AkAudioInputSource",
    "Ak3DAudioBedMixerFX",
    "AkCompressorFX",
    "AkDelayFX",
    "AkExpanderFX",
    "AkFlangerFX",
    "AkGainFX",
    "AkGuitarDistortionFX",
    "AkHarmonizerFX",
    "AkMatrixReverbFX",
    "AkMeterFX",
    "AkParametricEQFX",
    "AkPeakLimiterFX",
    "AkPitchShifterFX",
    "AkRecorderFX",
    "AkRoomVerbFX",
    "AkStereoDelayFX",
    "AkTimeStretchFX",
    "AkTremoloFX",
    "zip",
)


def audit_library(path):
    data = path.read_bytes()
    spec = importlib.util.spec_from_file_location("wwise_abi", native.ROOT / "tools/wwise-android-abi/generate.py")
    abi = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(abi)
    exports = abi.native_exports(data)
    digest = hashlib.sha256("\n".join(sorted(exports)).encode()).hexdigest()
    if digest != EXPORTS_SHA256:
        raise ValueError("Wwise dynamic exports differ from the qualified Android ABI")

    table_offset = struct.unpack_from("<Q", data, 40)[0]
    entry_size, count = struct.unpack_from("<HH", data, 58)
    sections = list(struct.iter_unpack("<IIQQQQIIQQ", data[table_offset : table_offset + entry_size * count]))
    (dynamic,) = [row for row in sections if row[1] == 6]  # SHT_DYNAMIC
    strings_offset, strings_size = sections[dynamic[6]][4:6]
    strings = data[strings_offset : strings_offset + strings_size]
    start, size = dynamic[4:6]
    names = {1: [], 14: []}  # DT_NEEDED, DT_SONAME
    for tag, offset in struct.iter_unpack("<qQ", data[start : start + size]):
        if tag in names:
            end = strings.find(b"\0", offset)
            if end <= offset:
                raise ValueError("invalid native ELF dynamic name")
            names[tag].append(strings[offset:end].decode("ascii"))
    if sorted(names[1]) != sorted(DEPENDENCIES) or names[14] != [LIBRARY]:
        raise ValueError("Wwise ELF dependencies or SONAME differ")

    table_offset = struct.unpack_from("<Q", data, 32)[0]
    entry_size, count = struct.unpack_from("<HH", data, 54)
    headers = struct.iter_unpack("<IIQQQQQQ", data[table_offset : table_offset + entry_size * count])
    alignments = [row[7] for row in headers if row[0] == 1]  # PT_LOAD
    if not alignments or min(alignments) < 16384:
        raise ValueError("Wwise ELF requires 16 KiB load alignment")
    return {
        "sha256": hashlib.sha256(data).hexdigest(),
        "bytes": len(data),
        "exports": len(exports),
        "exports_sha256": digest,
        "dependencies": sorted(DEPENDENCIES),
        "load_alignment": min(alignments),
        "soname": LIBRARY,
    }


def verify_build(library, pin):
    if set(pin) != {"path", "sha256", "bytes"}:
        raise ValueError("explicit Wwise producer receipt pin required")
    receipt = native.canonical(pin["path"]).read_bytes()
    if len(receipt) != pin["bytes"] or hashlib.sha256(receipt).hexdigest() != pin["sha256"]:
        raise ValueError("Wwise producer receipt differs from the dependency pin")
    build = json.loads(receipt)
    actual = audit_library(library)
    if build.get("schema") != 1 or build.get("success") is not True or build.get("overlay_sha256") != native.sha(POLICY) or build.get("library") != actual:
        raise ValueError("Wwise library differs from the successful producer receipt")
    return actual["sha256"]


def prepare_common(common, output):
    policy = json.loads(POLICY.read_text())
    serializer = common / "AkCallbackSerializer.cpp"
    stubs = common / "AkSoundEngineStubs.cpp"
    callback = policy["callback_serializer"]
    engine = policy["engine_stubs"]
    if native.sha(serializer) != callback["stock_sha256"] or native.sha(stubs) != engine["stock_sha256"]:
        raise ValueError("Wwise stock source differs from the overlay policy")
    lines = serializer.read_text().splitlines(keepends=True)
    # These splice positions are for the exact stock hash checked above.
    lines[335:337] = [callback["monitor_level"], *(line.replace("in_uErrorLevel", "monitorErrorLevel") for line in lines[335:337])]
    lines[303:304] = [callback["record_monitor"], lines[303].removesuffix(")\n") + " &&\n", callback["when_armed"]]
    lines[126:127] = [callback["monitor_scope"], "\t" + lines[126]]
    lines[45:45] = [callback["declarations"]]
    stub_lines = stubs.read_bytes().splitlines(keepends=True)
    del stub_lines[87]  # The licensed archive roster lacks the optional Reflect plug-in.
    transformed = (output / serializer.name, output / stubs.name)
    transformed[0].write_bytes("".join(lines).encode())
    transformed[1].write_bytes(b"".join(stub_lines))
    if [native.sha(path) for path in transformed] != [callback["output_sha256"], engine["output_sha256"]]:
        raise ValueError("Wwise overlay differs from the qualified source")
    return transformed


def run(stock, sysroot, clang, linker, resource_dir, output):
    stock, sysroot, clang, resource_dir = [native.canonical(path) for path in (stock, sysroot, clang, resource_dir)]
    # Keep ld.lld's executable name when the host tool is a symlink to the
    # multi-call lld binary. Android provides a named executable directly.
    native.canonical(linker.resolve(strict=True))
    native.canonical(linker.parent)
    output = Path(output)
    native.disjoint(output, (stock, sysroot, resource_dir, DIAGNOSTICS))
    sdk = stock / "sdk"
    integration = stock / "integration/Wwise/AkSoundEngine"
    target = sysroot / "usr/lib/aarch64-linux-android"
    platform = target / "21"
    runtime = sysroot.parent / "lib64/clang/14.0.7/lib/linux"
    includes = [
        integration / "Android",
        sdk / "include",
        integration / "Common",
        sdk / "samples/SoundEngine/Android/libzip/lib",
    ]
    archives = [
        *(sdk / f"Android_arm64-v8a/Profile/lib/lib{name}.a" for name in ARCHIVES),
        target / "libc++_static.a",
        target / "libc++abi.a",
        runtime / "aarch64/libunwind.a",
        runtime / "libclang_rt.builtins-aarch64-android.a",
    ]
    command = [clang, "--driver-mode=gcc", "-fintegrated-cc1", "--target=aarch64-linux-android21", f"--sysroot={sysroot}", f"-resource-dir={resource_dir}"]
    cflags = [
        "-DANDROID",
        "-DNDEBUG",
        "-D_FORTIFY_SOURCE=2",
        "-O2",
        "-fPIC",
        "-fstack-protector-strong",
        "-ffunction-sections",
        "-fdata-sections",
    ]
    cxxflags = [
        "-nostdinc++",
        "-isystem",
        sysroot / "usr/include/c++/v1",
        "-DAUDIOKINETIC",
        "-std=c++14",
        "-fvisibility=hidden",
        "-fno-exceptions",
        "-fno-rtti",
        "-fno-strict-aliasing",
        "-fno-omit-frame-pointer",
        "-Wno-deprecated-declarations",
        *[f"-I{path}" for path in includes],
    ]
    output.mkdir(mode=0o700)
    for name in ("logs", "objects", "tmp", "common"):
        (output / name).mkdir()
    env = dict(os.environ, TMPDIR=str(output / "tmp"))
    started = time.monotonic()
    result = {"schema": 1, "success": False, "clang_sha256": native.sha(clang), "linker_sha256": native.sha(linker)}
    try:
        serializer, stubs = prepare_common(integration / "Common", output / "common")
        sources = [
            *(integration / "Android" / name for name in ANDROID_SOURCES),
            serializer,
            *(integration / "Common" / name for name in COMMON_SOURCES),
            stubs,
            DIAGNOSTICS / "WwiseManagedDiagBridge.cpp",
            DIAGNOSTICS / "PcmReadbackRingV1.cpp",
        ]
        objects = []
        for source in sources:
            obj = output / "objects" / (source.stem + ".o")
            native.invoke(list(map(str, [*command, *cflags, *cxxflags, "-c", source, "-o", obj])), output, source.stem, env=env)
            objects.append(obj)
        artifact = output / LIBRARY
        native.invoke(
            list(
                map(
                    str,
                    [
                        *command,
                        f"--ld-path={linker}",
                        "-nostdlib",
                        "-shared",
                        f"-Wl,-soname,{LIBRARY},--gc-sections,--build-id=sha1,--no-rosegment,-z,max-page-size=16384",
                        "-Wl,--as-needed,--no-undefined",
                        platform / "crtbegin_so.o",
                        *objects,
                        *archives,
                        f"-L{platform}",
                        "-lOpenSLES",
                        "-landroid",
                        "-llog",
                        "-ldl",
                        "-lz",
                        "-lm",
                        "-lc",
                        platform / "crtend_so.o",
                        "-o",
                        artifact,
                    ],
                )
            ),
            output,
            "link",
            env=env,
        )
        result.update(success=True, library=audit_library(artifact), overlay_sha256=native.sha(POLICY))
        return result
    finally:
        result["seconds"] = round(time.monotonic() - started, 3)
        native.write(output / "result.json", result)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("stock", "sysroot", "clang", "linker", "resource_dir", "output"):
        parser.add_argument("--" + name.replace("_", "-"), required=True, type=Path)
    run(**vars(parser.parse_args()))
