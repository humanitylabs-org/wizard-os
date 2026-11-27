# Shared Hermes lock and coordinated promotion

Proposed implementation of DECISIONS #74; approval needed from James and a
non-author admin before this all-install default ships. Hermes remains stock.

## One release authority

`releases/hermes-lock.json` is the canonical lock. App Manager vendors this file
as `wam/hermes-lock.json`; Agent Service vendors it beside `agent_runtime.py`.
Copies must be byte-identical in a promotion PR set. No updater discovers an
upstream latest/stable tag to install. Snapshot Hermes tag, full upstream commit,
official image digest and default agent recipe must equal the lock. Existing
historical snapshots are immutable; the release checker applies this comparison
to the current stable snapshot and new releases, not historical files.

While a lock move goes For testers first, the lock keeps the pin it replaced as
`previous` (`hermes`, `agent_recipe`, `runtime_image`, `why`). A release naming
**all** of `previous` (the stable snapshot still soaking) stays valid; a mix of
old and new never is, and `check_pin` alone only accepts the locked pin. Drop
`previous` once stable is on the new pin. The release train copies the lock's
recipe into each cut (wizard-app-store#92).

The initial lock **freezes the existing September baseline**, not a claim that
September is universally safe or that 0.21.7/0.22.x is safe. Its committed
acceptance record reports seven passing checks AND the known compacted-history
visibility limitation. Alongside installations retain their own runtime: never
automatically converge or downgrade them. The wrapper image is independently
pinned by manifest digest; its two Linux configs name the locked upstream commit.

## Paused means no unattended Hermes changes

Hermes automatic updates are paused independently of WizardOS/app updates.
Ordinary release reruns skip installed Hermes; a user-requested app update or
host update refuses until a reviewed promotion exists and the operator explicitly
sets `WIZARD_HERMES_PROMOTION` to its id. A missing, malformed, mismatched or
unavailable lock fails closed for Hermes. Dry-run/status remain read-only.
New installs consume the exact frozen recipe/image; existing runtimes are not
rewritten merely because policy is installed. Normal Apps UI and update-all
routes enforce the pause before status/queue mutation; an optional internal
`hermesPromotion` field forwards the explicit operator id but is not approval.
The backend index also pins Hermes when no owner selection exists. Direct upstream `hermes update`,
Docker/Runtipi administrator operations and owner cron jobs are outside these
Wizard entry points; operators must inventory and pause those separately. Do not
pause unrelated app timers. This policy does not patch or interpose stock Hermes.

## Review, recommend, approve, promote

1. Read upstream releases and open bugs daily; this is advisory only. Wait at
   least **seven complete days after publication**, not tag creation. Unknown
   publication dates fail the gate. Read unversioned reports as well as matches
   for session, database, gateway, compaction and history regressions.
2. Test the exact tag commit and each image architecture in an isolated fresh
   environment: send/read history, delegation, compaction, restart/integrity,
   cron, update and forced rollback. Canary on an approved test install for two
   to three days. Preserve the reports and known limitations.
3. Send a recommendation with exact revisions/digests, publication date, bug
   assessment, acceptance/canary evidence, backup/rollback procedure and cohort
   plan. A report is not an approval and seven days alone proves no safety.
4. A non-author admin (James for stable promotion) approves the recommendation.
   Update the canonical lock plus its vendors in linked PRs. A promotion record
   contains `id`, `published_at`, `approved_at`, `recommendation`, `approval`,
   `acceptance`, `canary`, `bug_review`, and `rollback` evidence URLs. Timestamp
   validation requires approved_at >= published_at + 7 days and not in the future.
   CI/local validation is not an approval. Never self-merge this change.
5. Cut the matching snapshot only after dependency PRs land. In a coordinated
   maintenance window, inventory each install and verify backups/quiet state;
   explicitly pass the approved promotion id to each host/container updater.
   Record successes and failures against one id. Pause the cohort at first
   regression. Unrelated Wizard apps continue their normal updates.

## Rollback

Keep each install's pre-change commit/image, dependency freeze and verified
private backups. Use the existing host transactional updater's verified rollback
on failure. Container operators restore the previous exact recipe/image with the
same home only when data compatibility is established. Never blindly restore an
old database over newer writes. A cross-version database rollback needs a tested
recovery plan and explicit owner approval. Stop admission, preserve the current
state and receipts, and recover manually if verification fails. Reverting the
lock is a separate reviewed rollback promotion, not a fleet-wide downgrade.
An install already newer than the frozen baseline stays there until reviewed;
there is no authorization to downgrade it in this PR.
