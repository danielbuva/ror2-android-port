# Public repository privacy and IP audit

Audited 2026-09-12 PDT before resuming L5a. Scope: all advertised GitHub branches/tags, their reachable history, current local commits queued for publication, tracked source/configuration, commit identities, and exposed repository collaboration/download surfaces. Raw findings and the original Git bundle remain private under ignored work/privacy-audit/.

## Findings and remediation

- Bootstrap captures exposed the authorized ADB serial, adopted-storage UUID and exact backing paths, display/device identifiers, local home/install paths, editor instance/session metadata and a personal email in tool output. Authentication notes described local sign-in/session state. These files are removed from tracking and history, not merely redacted in the latest tree. Local files remain available for existing health checks.
- The environment report now uses placeholders and local-only evidence references; personal installation paths and authentication-session narrative are removed.
- The Turnip reference retains upstream URL, release date/tag, artifact name/hash/size. Its copied third-party release body is removed; no upstream driver binary was tracked.
- Author/committer email metadata is replaced by the repository owner's public GitHub noreply identity. Future local commits use that identity. Public repository/source URLs and upstream author attribution are retained.
- Environment output is ignored by default, with a four-file reviewed allowlist. The staged-content privacy gate rejects common identifiers, raw captures and proprietary payload extensions. Regression tests cover raw JSON, placeholders, private values in documentation and disguised middleware payloads.

## Tracked files sanitized

- environment/ENVIRONMENT_REPORT.md
- environment/turnip-target.json

## Tracked files removed (private local copies retained)

- environment/auth-notes.md
- environment/bootstrap.log
- environment/device-profile.json
- environment/doctor-result.json
- environment/mcp-check.json
- environment/mcp-exercise.json
- environment/scrcpy-check.log
- environment/smoke-auto-result.json
- environment/smoke-logcat.txt
- environment/smoke-result.json
- environment/smoke-screenshot.png
- environment/steamcmd-check.log
- environment/tool-versions.json

## Audit coverage and limits

The initial scan covered 16 reachable commits and 222 distinct historical blobs across 131 paths, including two local commits not yet on the remote. The only tracked binary was the bootstrap screenshot, now removed. No original game binaries, exported game assets, decompiled source trees, proprietary middleware, Wwise banks, signing keys or packaged builds were found in reachable Git history. Authored transformation/probe code, standard source-only Unity smoke settings, public dependency references, API/type names and content hashes remain. This is a repository-content assessment, not a determination of rights to distribute a game or middleware.

Gitleaks scanned the initial reachable history with redaction enabled and found no credential-token matches. That does not imply absence of every possible secret: custom identifier/path/email checks and manual source/provenance review found the privacy issues above. Only values and files needed for the public tooling are retained; no private raw findings are embedded in this report.

GitHub inspection found one public branch, no tags, no reported forks, and zero issues/PRs, releases, Actions runs/artifacts or commit comments. No wiki refs were advertised (the wiki endpoint was unavailable). These are observations at audit time, not guarantees about external clones or caches. The public repository owner's identity and ordinary public upstream links remain intentionally visible.

## Publication and verification

History cleanup was prepared in an isolated local mirror after preserving the original history, then published with an exact lease for the observed remote main tip. A fresh public mirror verified all 13 removed paths absent from reachable history, zero known private identifier/home/email matches, a clean Gitleaks scan and the matching sanitized main tip. Fifteen host tests and doctor pass. The private commit map is retained beside checkpoint receipts; historical device evidence keeps its original commit attribution. Local app snapshot refs and backup bundles are private and must never be mirror-pushed.

**Residual exposure verified:** after publication, GitHub still returned the previous remote commit by its SHA through the Git commit API. Its old metadata/content must be treated as still retrievable until GitHub purges the unreachable objects. A force-push replaces reachable history but cannot erase third-party clones or guarantee removal of GitHub cached old-commit views. GitHub documents contacting Support for residual sensitive-data references/caches where eligible; no Support message is sent by this audit. See [GitHub's sensitive-data removal guidance](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/removing-sensitive-data-from-a-repository).

Re-run `python3 scripts/audit-public.py` after staging future changes. Re-run a dedicated secret scanner over history before public releases, and review actual staged content for IP/provenance rather than relying solely on filename/pattern rules.
