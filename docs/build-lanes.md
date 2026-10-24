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
It stops only receipt-matched editor/server processes, retains configuration,
logs and receipts under canonical `work/coordination/build-lanes/`, then deletes
the checkout/work clone. Published artifacts remain. Persistent locks live
outside deleted lanes so removal/recreation cannot split contenders. The pruner
uses this same teardown for old stopped lanes; active/recent lanes are retained.
Creation and teardown record free space; every build requires at least 100 GiB
free. APFS logical sizes do not represent extra physical allocation.
