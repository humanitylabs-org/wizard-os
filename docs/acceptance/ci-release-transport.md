# Operator-dispatched release acceptance

`Release acceptance` is a manual, main-only GitHub Actions transport to the existing
Agent Service durable heavy worker. It closes the gap where this repository's CI
could check source contracts but could not submit the actual release test. It does
not promote a release or change any acceptance criterion.

Run the workflow with the published candidate version, its exact manifest SHA256,
and `preflight_only=true` first. The preflight is read-only: it compares canonical
and anonymous public manifest bytes, checks the existing external work volume and
shared lock, the Lima toolchain, and 275 GiB genuinely free. Missing configuration
is a named refusal, not a fallback to another disk, fresh lock or direct VM launch.

The existing runner must inherit `WIZARD_CI_ROOT` and `WIZARD_CI_WORKER_LOCK`.
`WIZARD_WORK_ROOT` selects the mounted work volume; older runners may use the
external volume containing `WIZARD_CI_ROOT`, matching the established image-CI
placement rule. If host-heavy root/lock settings are present, they must agree.
No worker token, private SSH key, provider login or new paid capacity is required.

After a passed preflight, dispatch with `preflight_only=false`. Only the two fixed
old baselines (0.3.39 and 0.3.40), the selected public candidate, and its manifest's
exact public WAM commit can run. There is no user-supplied command or source URL.
The source is archived from the exact main workflow SHA into a unique short path
on the work volume. The unchanged worker is fetched from one full public source
commit and verified by SHA256 before use.

CI is an independent operator control plane, not an agent continuation. It never
calls the host relay as a made-up owner session. Its stable isolated spool lives
under the work volume's `ra/spool`; it does not edit Service queue/authority state.
The real worker supplies durable claims, memory/disk health admission, never-retry
recovery, deadlines, cancellation and the **existing configured Android/VM lock**.
The VM entry verifies the inherited lock inode. There is no second heavy capacity:
other dispatchers and this CI transport contend for the same existing lock.

The unchanged `release_gate.py` runs twice, each with its own empty root and the
exact-hashed `backup_class_fixture.py`. Each run independently creates a candidate
fresh guest, then a separate baseline guest, upgrades it using the public installer,
and exercises installed-WAM export/verify/import/receipt and distinct-baseline Undo.
The 24 GiB guest and 250 GiB reserve remain unchanged. No owner installation,
retained daily VM, host Tailscale state or provider credentials is modified.

Raw private logs stay on the worker; Actions receives only bounded machine receipts
and source/hash identities, not log contents or internal machine paths. Existing
stages are never erased or silently reused. A failed journey remains a failure.
The workflow's manual preflight is not release acceptance, and neither is a green
contracts run. Stable can move only after both actual gate receipts pass and the
separate browser/Android gates pass, using the supported promotion command.
