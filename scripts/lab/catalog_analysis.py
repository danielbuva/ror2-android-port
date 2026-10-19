"""R2–R4's catalog analysis, regenerated on the host inside the destination (J725).

The live pipeline's audit, native container inventory and reconcile run unchanged
(`whole_catalog.*_into`) into `<destination>/.rebuild/catalog-inputs/`. They read only the
legitimate installation, the accepted export and decompilation, and public recipes. The three
typed-import corrections measured once by Unity come from a public recipe. Nothing here
writes a live pointer or reads a previous analysis.
"""

import shutil
from pathlib import Path

from common import RECIPE, read, sha, write

OUTPUTS = (
    "original-catalog-contract.json",
    "source-catalog.json",
    "source-guid-index.json",
    "source-guid-repairs.json",
    "host-closure.json",
    "native-conversions.json",
    "typed-import-conversions.json",
    "reconciled-closure.json",
)


def typed_corrections(input_id):
    recipe = read(RECIPE / "catalog-typed-corrections.json")
    if recipe["schema"] != 1 or recipe["input_id"] != input_id:
        raise RuntimeError("Typed import corrections require accepted input")
    return recipe


def regenerate(work, out, input_id):
    """Write the complete analysis cohort into `out`; refuses any incomplete inspection."""
    from whole_catalog import audit_into, native_inventory_into, reconcile_into

    audit_into(out, work=work)
    native = out / "native-containers"
    native.mkdir(exist_ok=True)
    inspected = native_inventory_into(out, native, work=work)
    if not inspected["success"]:
        raise RuntimeError("Original container inspection incomplete; inspect " + str(native / "result.json"))
    corrections = typed_corrections(input_id)
    if corrections["catalog_sha256"] != read(out / "host-closure.json")["source_catalog_sha256"]:
        raise RuntimeError("Typed import corrections belong to a different shipped catalog")
    # reconcile_into checks this receipt against the regenerated metadata, as in the live pipeline.
    write(out / "typed-import-conversions.json", dict(metadata_sha256=sha(out / "source-catalog.json"), conversions=corrections["conversions"]))
    reconcile_into(out, native, work=work)


def ensure(work, destination, input_id):
    """Return the destination's analysis directory, regenerating it once per destination."""
    out = Path(destination) / ".rebuild/catalog-inputs"
    marker = out / "analysis-complete.json"
    if marker.is_file():
        record = read(marker)
        if record.get("input_id") == input_id and all((out / name).is_file() and sha(out / name) == record["outputs"].get(name) for name in OUTPUTS):
            return out
    # Replace only the analysis cohort; R3's integration attempts beside it are kept.
    out.mkdir(parents=True, exist_ok=True)
    marker.unlink(missing_ok=True)
    for name in OUTPUTS:
        (out / name).unlink(missing_ok=True)
    shutil.rmtree(out / "native-containers", ignore_errors=True)
    regenerate(Path(work), out, input_id)
    missing = [name for name in OUTPUTS if not (out / name).is_file()]
    if missing:
        raise RuntimeError("Catalog analysis incomplete: " + ", ".join(missing))
    write(marker, dict(input_id=input_id, outputs={name: sha(out / name) for name in OUTPUTS}))
    return out
