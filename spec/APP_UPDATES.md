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
nightly timer and the runner checks the saved mode again before each app starts. An app
already updating is allowed to finish safely. **Update apps now** is a deliberate one-run
action and never enables Automatic. The existing default may remain Automatic; installer
reruns must preserve a saved Manual choice. The setting uses the existing owner-only Store
listener and existing app-update implementation, not a second scheduler or app authority.

## Owner code is not disposable

Automatic is permission to update an unmodified managed package, not permission to discard
owner code. Exact owner selections, developer builds, holds and release-managed components
stay outside this app updater. Supported custom views and My skin remain separate owner
layers and retain their existing merge/conflict behaviour.

Source/build packages receive a recorded file inventory when copied from a pinned release.
Before applying an update, verify the installed copy still matches that inventory. A changed,
unreadable or older unrecorded source copy is held for owner review, including on a manual
bulk run: the word Update is not permission to erase modifications. Recheck before mutation.
Do not replace an existing source directory with different bytes. Cleanup may delete only
source copies that still match their recorded inventory; keep modified or unrecorded copies.
This is accidental-change protection, not a security attestation against a hostile owner.

Suggested resolution: show the upstream diff, retain an export/backup of owner edits, and let
the owner choose a merge, keep their version, or explicitly replace it. The implementation
in this proposal does **not** invent a replace/reset permission. That destructive-resolution
UX remains a separate owner decision; until then the update refuses with a reason. Image
container mutations cannot be reliably inferred from host source inventories: use a pinned
own package or supported custom view, not edits inside a disposable container.

## Acceptance

- Manual survives installer timer reconciliation; queued automatic work cannot start another
  app after the owner switches to Manual. Manual Update now still works without changing mode.
- Invalid/foreign browser writes cannot change policy or trigger updates; failed readback is
  never presented as a successful saved setting.
- Changed, added, deleted and symlink-modified source, missing inventories, local selections
  and custom views are protected. Cleanup and same-commit preparation do not erase them.
- Phone and desktop show both scopes; two skins retain their appearance and state. Browser
  acceptance runs on the configured worker, not the control-plane host.

Reuse:
- settings: EXTEND WosUpdates through WosSettings.register.
- app lifecycle: EXTEND wam.app_updates and packaging's existing pinned source lifecycle.
- authority: REUSE StoreHandler owner/origin/peer checks.
- owner views and skins: REUSE existing views and My skin ownership, never edit them here.
