# Historical authored Init transform

`transform_init.py.txt` is a readable byte-exact archival source artifact,
SHA-256 `91c72d254ba9473d93ffb18c4be2233be1781b6072b08571aed7f607e76e9b37`.
It is independently authored historical parsing/serialization code from the
J740/J744 investigation, with minimum bank/plugin/device/bus identities. It
contains no bank/media data, SDK implementation or copied wwiser implementation.
The existing recipe audit and current public `wwise_init_platform.py` describe
the preferred current producer; this artifact exists only where the historical
receipt's actual source hash is required by unchanged downstream guards.

Its old comments and receipt scope remain literal historical text. They are not
new runtime/routing approval. The wrapper does not substitute a historical hash
into a new execution receipt: it materializes and executes these exact bytes,
then rehashes the actual source and resulting bank/receipt. Readable `.txt`
source templates already exist for C# tools in this repository. This historical
artifact retains its original formatting; current wrapper/test Python passes
Ruff. Do not reformat or silently update the artifact to repair another contract.

Use the formatted, input-gated
[`owner-code/legacy_init.py`](../owner-code/legacy_init.py), rather than invoking
the historical artifact directly. It verifies the full accepted owner inventory
and original configured bank before materializing any code. The archive's own
exact-bank, ignored-output and exclusive-write guards remain intact. Generated
source is retained under `work/legacy-init-tools/<owned-run>/transform_init.py`
at the historical root-relative depth; bank, receipt, logs and terminal result
stay in the explicitly requested new private output. No original bank is edited.
No private historical path, prebuilt bank, Editor or project is required.

```sh
python tools/phone-build/owner-code/legacy_init.py \
  --owner-work /absolute/checkout/work \
  --output /absolute/checkout/work/new-init-output
```

The archived path guard requires this checkout's `work` root and Git ignore
configuration. Other work roots refuse before execution; phone hosting is
unqualified. The owner retains failures and materialized code for review; after
recording evidence, remove only its explicit output and recorded materialized
run directory. No current game build automatically uses these files. Publishing
authored tooling grants no middleware/media rights or broader routing fidelity.
