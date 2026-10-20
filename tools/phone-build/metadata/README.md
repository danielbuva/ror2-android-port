# Read-only SDK metadata inventory

Current experimental host support for the authored root-production investigation.
This tool uses supplied Cecil to read managed metadata without executing inspected
assemblies. It records type/base identity and explicit native-class/type attributes,
with input hashes before and after reading. It never emits a linker root or edits
an SDK/game assembly. Raw SDK-derived reports stay under ignored `work/`.

Build using .NET 10 and `-p:CecilPath=SUPPLIED_CECIL.dll`, then pass an ignored
input JSON and a new output path. Input rows are `assemblies` entries with explicit
`group` and `path` fields. Duplicate inputs, input drift and output overwrites fail.
This is a host observation tool, not an Android build-tool qualification.

Compare explicit attribute identity and hierarchy against a hash-bound exact-editor
oracle. Keep short-name guesses separate; matching a name alone does not establish
native namespace, module or base identity, nor scene usage/root completeness.
No captured SDK root table is embedded or redistributed by this tool.
