# Release defaults, gate timing and the Store panel (card 6 / #389 release blockers)

Status: **decided** for O5 (Miguel delegated the decision on 3 Nov 2026; recorded here as he decided it). O1 and O4 are implementation rules that follow from decisions already made. Draft PRs: wizard-app-manager #425 (O4 + O5, stacked on #422), wizard-ux #874 (O1, stacked on #873). The boundary stays default-off and nothing here releases it.

Background: run 2 of the #389 rehearsal ([dossier](../../acceptance/browser-trust-rehearsal-389.md), evidence branch `evidence/browser-trust-package-acceptance`) left five open items. O2 (build-from-source apps from a test pin) and O3 (Connection Router `tools/list` 400) were pre-existing bugs. They are fixed as ordinary PRs off main: wizard-app-manager #424 and wizard-connection-router #10.

## O5. Browser grants for release default apps (decided)

A fresh box had no browser grants, so with the boundary on, the default Notifications window said "needs permission from the owner".

**Decision.**

1. **Release defaults are granted their own declared operations.** An app pinned as a release default gets every operation its **installed** `wizard.md` `browser_contract` declares, at install or upgrade, with no owner prompt. "Pinned as a release default" means:
   - the running release's `default_apps` row names its app id, repo and full commit;
   - the installed copy came from exactly that repo and commit.

   The release review stands in for the owner's tick.
2. **Recorded with its provenance.** Each grant row records:
   - `by: "release-default"`, plus the release `version`, the pinned `commit` and `source_id`;
   - the installation, `contract_digest` and the `permission_revision` it produced.

   The owner (or the Store) can always tell a default grant from one they gave themselves.
3. **Only during a release run.** Grants are written only while the installer or upgrade names the release (`WIZARD_RELEASE_PINS`); a receipt never grants. They are written whether or not the boundary is on: they are inert while it is off, so turning it on later needs no owner step for the defaults.
4. **Never over an owner decision.** If any grant row exists for that installation and source, nothing is written. That covers a release-default grant, an owner's grant and an owner's revoke (zero-operation tombstone). A revoke survives every later upgrade.
5. **An increase on update waits for the owner.** When an update declares more than the recorded grant, the extra operations are not granted. The App Manager's projection lists them as `ungranted`, and the Store's update prompt (or `wam browser-grants grant`) asks the owner. A decrease takes effect at once, because the projection only ever grants declared operations.
6. **Everything else starts with nothing.** Store, private, share-link and test-pin installs, and a default the owner moved to another repo or commit, get no grants until the owner approves them.
7. **Reinstall = new installation.** A reinstall outside a release run starts with no grants. Grants bind to installation + source, as in SPEC-CARD1.

Implementation: `wam/browser_admission.py` `release_default_grants`, called from `write_registry`. Tests: `tests/test_browser_release_blockers.py`, where every O5 rule above has a case.

## O4. A gate change takes effect before WAM returns

After the switch, Files served cross-site frames **ungated** until a manual restart. Its own-tab env was written by `wam links` after the switch had already restarted it.

**Rule.**
- Every App Manager write that changes an app's boundary env records that app. The writes covered are:
  - the bare flag, the listener credential, the gateway key and the own-tab origin;
  - removing all of these when the boundary is off.
- Before the command returns, the App Manager restarts each recorded app that is **running**. Stopped apps pick the env up on their next start. An unchanged env records nothing, so a steady box never restarts anything.
- `wam app start|restart` writes the app's boundary env **before** Runtipi recreates the container, so that start applies it. The same projection runs as for `wam apps`, and other apps it changes are restarted. With the boundary off and no gate env present, a start is a plain start.
- The own-tab origin is written from the last `wam links` result during the projection itself, so a restart never runs ahead of it.

Tests: `tests/test_browser_release_blockers.py`. They record the env each restart saw, so the order is checked.

## O1. The App Store is a shell-controlled panel

In its opaque window, the Store's reads of `/wizard-os-home/store-data/*` were refused from Origin:null, so it showed "The App Index isn't reachable right now". That refusal is correct: owner APIs get no CORS. REVIEW-BRIEF already says Store, Agents and Setup stay shell-controlled panels.

**Rule.**
- **Shell power, scoped to one window.** The shell answers typed Store operations (`store.call`) for **only** its built-in App Store window. That window is `app-store` from the shell's own catalogue, with no `source`, at `/wizard-os-home/store/index.html`. An installed app never gets them, whatever its id.
- **No grant or contract.** This is not an installed app's power, so no WAM grant or `browser_contract` is involved.
- **Fixed paths, exact arguments.** Each operation maps to one fixed owner path, and the frame never names a URL, method or header. The operations are:
  - reads: `catalog`, `installed.runtipi`, `installed.wizard`, `link`, `router.needs`, `install.status`, `remove.plan`, `remove.status`, `app.agents`;
  - owner changes: `install` (install/update/switch), `remove`, `router.approve`.
- **Owner changes need the owner in shell UI first.** The confirmation uses the same Review chip, dialog, wake delay, trusted activation and 3-per-minute budget as shell intents. A script in the Store's frame can ask, but never decide.
- **The Store page itself.** It loads the boundary client and a small bridge. The bridge turns exactly those requests into the typed operations and refuses anything else under those prefixes. It also receives the skin over the boundary port, so the Store follows Landscapes Light like other opaque apps. Outside the opaque window (boundary off, own tab) the bridge does nothing.

Tests: wizard-ux `tests/browser-boundary-store.test.mjs`.

## Not decided here

The supported product switch for the boundary (today it is still the rehearsal script), default grants for non-default system apps, and Agents/Setup as panels.
