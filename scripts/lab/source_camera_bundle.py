"""Compile the existing source-camera program candidate in an isolated SDK project."""

import json
import os
from pathlib import Path
import shutil
import subprocess

from common import ROOT, WORK
from build_lock import HOST_BUILD_LOCK, host_build_lock
from shader_postprocessing_uber import RECIPE, digest, generate_candidate


def build(target):
    request = json.loads(Path(target).read_text())
    config = json.loads((WORK / "config/reconstruction.json").read_text())
    candidate, manifest = generate_candidate(WORK, ROOT / config["projects"][0], config["input_id"], allow_create=False)
    if "source_guids" in request:
        wanted = set(request["source_guids"])
        programs = [row for row in manifest["programs"] if row["source_guid"] in wanted]
        if not wanted or {row["source_guid"] for row in programs} != wanted:
            raise ValueError("Requested source camera program GUIDs are absent")
        manifest = {**manifest, "programs": programs}
    output = Path(request["output"]).resolve()
    if not output.is_relative_to(WORK):
        raise ValueError("Program bundle output must stay under ignored work")
    output.mkdir(parents=True, exist_ok=False)
    (output / ".prune-keep").touch()
    project = output / "project"
    from phone_content import stage

    stage(project)
    # The SDK fixture supplies project settings only; compile no fixture gameplay.
    shutil.rmtree(project / "Assets")
    (project / "Assets/Editor").mkdir(parents=True)
    fixture = ROOT / "tools/phone-build/SourceCameraProgramBundle.cs"
    shutil.copyfile(fixture, project / "Assets/Editor" / fixture.name)
    recipe = json.loads(RECIPE.read_text())
    for kind in ("includes", "programs"):
        for row in manifest[kind]:
            relative = recipe["include_target_prefix"] + row["package_path"] if kind == "includes" else row["target"]
            source = candidate / row["candidate_path"]
            dest = project / relative
            dest.parent.mkdir(parents=True, exist_ok=True)
            for suffix in ("", ".meta"):
                shutil.copyfile(str(source) + suffix, str(dest) + suffix)
    programs = []
    for row in manifest["programs"]:
        kernels = [{"name": name, "x": group[0], "y": group[1], "z": group[2]} for name, group in zip(row["kernels"], row["kernel_thread_groups"], strict=True)]
        programs.append({"target": row["target"], "kernels": kernels})
    (project / "programs.json").write_text(json.dumps({"programs": programs}))
    receipt = {
        "success": False,
        "device_accepted": False,
        "phone_producer_qualified": False,
        "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "candidate_manifest_sha256": digest(candidate / "manifest.json"),
        "fixture_sha256": digest(fixture),
        "recipe_sha256": digest(RECIPE),
        "programs": manifest["programs"],
        "includes": manifest["includes"],
    }
    args = [
        os.environ["UNITY_EDITOR"],
        "-batchmode",
        # Kernel reflection needs a real host graphics device, even though the
        # supplier bundle targets Android/Vulkan. Null graphics has no kernels.
        "-force-metal",
        "-quit",
        "-projectPath",
        str(project),
        "-buildTarget",
        "Android",
        "-executeMethod",
        "SourceCameraProgramBundle.Build",
        "-logFile",
        str(output / "editor.log"),
    ]
    try:
        with host_build_lock(HOST_BUILD_LOCK, operation="Source camera program bundle", timeout=1):
            subprocess.run(args, check=True, timeout=1200)
        actual = json.loads((output / "compiled.json").read_text())
        bundle = output / "bundles/source-camera-programs"
        if actual.get("count") != len(manifest["programs"]) or actual.get("unity") != "2021.3.45f2":
            raise ValueError("Program bundle compilation receipt differs")
        receipt.update(success=True, compiled=actual, bundle={"path": str(bundle), "sha256": digest(bundle), "bytes": bundle.stat().st_size})
        return receipt
    finally:
        (output / "result.json").write_text(json.dumps(receipt, indent=2) + "\n")
        # Preserve receipts and compiled supplier; discard the isolated editor cache.
        shutil.rmtree(project)
