# Current isolated build lanes

Canonical commands retain their existing work tree, editor, MCP port and lock.
For an independent prepared build context, commit the source checkout and run:

```sh
./dev lane --action create --name second
LAB_LANE=second ./dev editor --target lab --action open
LAB_LANE=second ./dev preflight --host-only
LAB_LANE=second ./dev prototype --action whole-catalog-code-build
```

Creation takes the canonical mutex only while cloning prepared state with
APFS `cp -c -R`; no full-copy fallback is allowed. It includes the project and
Library, generated content, configuration and existing producer inputs. Old
caches, device receipts, live editor state and retired storage are excluded.
Each lane owns a detached Git checkout under `.local/build-lanes/NAME/checkout`,
private writable Gradle/user state, Unity instance, loopback MCP server and
persistent lock. The caller's committed HEAD is selected under that lock for
each operation. Keep HEAD fixed until completion. Other lanes and the canonical
build may run concurrently without switching the primary source checkout.

Creation and every build or editor-open refresh authored runtime, Editor and
plugin inputs from the selected lane checkout. Inherited extra C# is removed
only when its bytes match an identified predecessor Git source. Retirement
receipts retain the commit, source path, source/metadata hashes and removed
paths. Unknown or edited files refuse, preserving them for inspection.

The audio producer compiles the lane's own sources using a small APFS reference
clone with camera/music overlays unwound. Only its three authored DLLs and
metadata are replaced in the live project. Verified preimages are retained in
`work/lane-authored-audio` until ordinary composition restores them before its
existing audio/overlay steps. The full audio receipt and generated content keep
their existing bytes and bindings. This runs inside the private lock and never
changes canonical staging. Existing lanes gain this behavior on their next
build from an updated checkout; no recreation is required. Frozen-content checks
remain in force: a genuinely different plugin cohort can still require a normal
full lane build to establish its own baseline. A plain `./dev build` refuses a
pending changed plugin cohort; use a whole-catalog build action so the ordinary
composition owner can produce the complete current audio receipt.

The pinned MCP transport captures its endpoint at connection but uses global
EditorPrefs for setup. The authored bootstrap briefly serializes connection
setup, captures the lane endpoint, restores preferences and handles domain
reload through per-editor SessionState. Builds use separate MCP ports; every
editor action still verifies its exact project before mutation.

The first normal lane build establishes its own iteration anchor. An inherited
content mismatch requires a normal full lane build, retaining the existing
input-drift checks. Subsequent C# changes may use `whole-catalog-fast-build`;
acceptance builds retain their ordinary settings. Completed APK/payload/symbol
artifacts are APFS-cloned and verified in canonical `work/build-cache/lane-*`.
`NAME/latest-build.json` names those persistent outputs without replacing the
canonical current-build or iteration pointers.

Lane commands never access devices. Unset `LAB_LANE`, acquire the ordinary
global device lease and use explicit published APK/payload paths through the
canonical install/sync commands. OLED and storage rules remain unchanged.

```sh
./dev lane --action list
./dev lane --action remove --name second
```

Removal refuses a busy lane or a device receipt still referencing its checkout.
It stops receipt-matched editor/server processes and Gradle daemons through
the lane's private Gradle home. It retains configuration, MCP/editor logs and
receipts under canonical `work/coordination/build-lanes/`, then deletes
the checkout/work clone. Published artifacts remain. Persistent locks live
outside deleted lanes so removal/recreation cannot split contenders. The pruner
uses this same teardown for old stopped lanes; active/recent lanes are retained.
Creation and teardown record free space; every build requires at least 100 GiB
free. APFS logical sizes do not represent extra physical allocation.

## Iteration bundle compression

The accepted bundle setting already uses `ChunkBasedCompression` (LZ4HC).
Keep that default for acceptance. To evaluate content changes without bundle
compression, use an isolated lane:

```sh
LAB_LANE=second ./dev prototype --action whole-catalog-build --bundle-compression uncompressed
```

This still builds the complete bundle map, preserving dependency packing.
Unity's existing incremental bundle builder reuses unchanged bundles. A repeat
of the uncompressed action skips the entire bundle phase only when the staged
content inputs, allowed player-code membership and every generated payload hash
match its separate `whole-catalog-uncompressed-base.json`. Content or payload
changes rebuild the map. It never updates the normal frozen-payload ledger or
APK splice anchor. The result is marked iteration-only.

After uncompressed work, run an ordinary full lane build to restore LZ4 bundles
and establish the normal code/fast-build anchor. Normal code-only actions retain
their existing frozen-payload checks and refuse an uncompressed payload. No
compression option is accepted in the canonical context or destination rebuild.
Bundle timing and bounded start/end log markers identify the measured phase;
they do not claim that all bundle serialization time is compression.
Repeated normal builds can also vary serialized records; the journal records
the measured comparison limits. The uncompressed option adds no device or
byte-equivalence acceptance claim.

Measured concurrency, compression costs, comparison limits and cleanup evidence
are recorded once in [J1078](PORTING_JOURNAL.md#j1078--isolate-parallel-build-lanes-and-measure-iteration-bundle-compression).
