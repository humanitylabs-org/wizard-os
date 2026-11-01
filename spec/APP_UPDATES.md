# Owner-controlled app updates

Implementation proposal for review; no release or live configuration change is authorized by this document.

## Existing behaviour

App Manager #305 added an independent app-update mode (`auto` by default, `ask` saved in
`app-updates.json`), nightly updates, per-app holds, verification and rollback. Wizard OS
updates have a separate mode. The shell currently exposes only that system-release mode;
choosing Ask me there does not turn app updates off.

## Owner control

Settings → About & updates names the two scopes separately: **Wizard OS updates** and
**App updates**. App updates offers **Automatic** and **Manual**, shows the effective
saved choice and explains the default without calling it consent. Manual disables the
nightly timer and an automatic run checks the saved mode again before each app starts. An app
already updating is allowed to finish safely. **Update apps now** is a deliberate one-run
action and never enables Automatic. The existing default may remain Automatic; installer
reruns must preserve a saved Manual choice. The setting uses the existing owner-only Store
listener and existing app-update implementation, not a second scheduler or app authority.

Reading app-update status and opening or rendering Settings in either shell are local and
side-effect-free: they never create, rewrite or normalise `app-updates.json`, persist a source
inventory, or contact upstream. Installer reruns and timer reconciliation never create or change
the mode. An absent choice remains absent; the effective default is not a saved owner choice.
Legacy-baseline fetches happen only inside an update or verification run (owner-started,
automatic schedule, or installer verification), never as a side effect of a status read.

## Owner code is not disposable

Automatic is permission to update an unmodified managed package, not permission to discard
owner code. Exact owner selections, developer builds, holds and release-managed components
stay outside this app updater. Supported custom views and My skin remain separate owner
layers and retain their existing merge/conflict behaviour.

Source/build packages receive a recorded file inventory when copied from a pinned release.
Before applying an update, verify the installed copy still matches that inventory. For an older
copy missing its inventory, fetch trusted upstream at the **exact installed full commit**, not
the next prepared recipe, branch HEAD or a reused local cache. Only an exact file/directory/link
comparison may establish the baseline; persist the trusted expected inventory, never bless
unknown local bytes. Same-commit paths must not skip verification. An unavailable upstream or
missing/unreadable evidence means **cannot confirm this app is unchanged**, not **you changed it**.
Known differences and unverified copies remain held with distinct reasons, including on a manual
bulk run: Update is not permission to erase modifications. Retry verification on later runs.
Recheck before mutation. Installer reruns report held apps separately from
failed installs and do not mutate their prepared recipe/config. Reject raw update passthroughs
that cannot enforce the same checks.
Do not replace an existing same-commit source directory with different bytes. Cleanup may delete only
source copies that still match their recorded inventory; keep modified or unrecorded copies.
This is accidental-change protection, not a security attestation against a hostile owner.

Suggested resolution: show the upstream diff, retain an export/backup of owner edits, and let
the owner choose a merge, keep their version, or explicitly replace it. The implementation
in this proposal does **not** invent a replace/reset permission. That destructive-resolution
UX remains a separate owner decision; until then the update refuses with a reason. Image
container mutations cannot be reliably inferred from host source inventories: use a pinned
own package or supported custom view, not edits inside a disposable container.

## Acceptance

- Open Settings on phone and desktop, read status, then reconcile the installer timer:
  `app-updates.json` remains absent if unset, or byte-identical if present. Status makes no
  upstream request or source-inventory write. Changing app mode leaves the Wizard OS mode unchanged.
- Manual survives installer timer reconciliation; queued automatic work cannot start another
  app after the owner switches to Manual. Manual Update now still works without changing mode.
- Invalid/foreign browser writes cannot change policy or trigger updates; failed readback is
  never presented as a successful saved setting.
- Pristine legacy installs migrate only after exact installed-commit verification; changed,
  added, deleted and symlink-modified legacy source never receives a baseline. Unavailable
  upstream stays unverified, not owner-modified. Installer reruns and same-commit source
  preparation verify too. Local selections, cleanup and custom views remain protected.
- A pre-write status response cannot overwrite confirmed policy; Update apps now stays busy
  until status refresh completes, and failed refresh cannot enable a duplicate start.
- Phone and desktop show both scopes; two skins retain their appearance and state. Browser
  acceptance boots the real shells on the configured worker, not the control-plane host.
  James already ordered preserving Miguel's explicit skin overrides and My skin, including
  transparency: base defaults only; do not reask or force opacity on those layers (#703/#658).

Reuse:
- settings: EXTEND WosUpdates through WosSettings.register.
- app lifecycle: EXTEND wam.app_updates and packaging's existing pinned source lifecycle.
- authority: REUSE StoreHandler owner/origin/peer checks.
- owner views and skins: REUSE existing views and My skin ownership, never edit them here.
