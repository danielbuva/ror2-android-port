# Draft repository settings and publication steps

The proposed actions below require the owner's approval under the
[alpha publication policy](../ALPHA_POLICY.md#distribution-and-feedback).
Review the release, announcement, settings and templates as separate decisions.

| GitHub surface | Proposed action after approval |
| --- | --- |
| Issues | Keep Issues enabled. Move the two reviewed templates and `config.yml` to `.github/ISSUE_TEMPLATE/`. Keep blank issues enabled so reporters can use the existing prefilled browser links. |
| Actions environment | Configure `public-release` with the owner as a required reviewer, allow deployment from `owner-v*` tags only, and disable administrator bypass. |
| Release tag rulesets | Limit creation of `owner-v*` tags to the authorized publishing maintainer. Use a separate rule to block updates and deletion of existing release tags without a publisher bypass. |
| Publisher provisioning | Set `PUBLIC_RELEASE_PLAN_PATH`, `PUBLISHER_KEY_ID`, `PUBLISHER_PUBLIC_KEY` and the candidate's `PUBLIC_MINIMUM_INSTALLER_VERSION` when needed. Provision the existing matching `PUBLISHER_PRIVATE_KEY` as a GitHub Actions secret scoped to the release environment. |

[GitHub template documentation](https://docs.github.com/en/communities/using-templates-to-encourage-useful-issues-and-pull-requests/configuring-issue-templates-for-your-repository) ·
[GitHub environment documentation](https://docs.github.com/en/actions/how-tos/deploy/configure-and-manage-deployments/manage-environments)

1. Match the approved commit, input support and installer trust to the
   [public release contract](../../tools/phone-build/owner-apk/README.md#publishing-and-checking-updates).
   Confirm clean public-input bootstrap, dependency redistribution rights,
   ordinary gameplay, and on-phone install and same-key update with native
   profile/settings retention. Use the [alpha checklist](../public-alpha.md)
   for the full release gate.
2. Fill the draft fields from the approved receipts. Review the exact public
   file list and artifact provenance. The current workflow publishes
   `release.json`, `release.sig` and `public-tools.zip` from a reviewed plan.
   Confirm the approved installer and setup guide are available to the intended
   testers and the installed updater trusts the publisher key. Releases with
   the reviewed Unity smoke source require installer version 5 or later.
3. After settings and release approval, an authorized maintainer creates the
   `owner-v<versionCode>` tag on the reviewed commit and the owner reviews the
   environment job. That job publishes a GitHub release with a short default
   description. Replace it with the approved release notes. Check the actual
   published assets and **Check for updates** discovery before posting the
   approved announcement. The installer reads GitHub's latest published release.
4. After template approval, open both the Settings feedback draft and the
   baseline feedback draft with harmless sample text. Verify that the existing
   `/issues/new` route retains the title and body and that each template appears
   in the chooser. Close the previews without submitting them.
