# Launch v1 audits 8 and 9

Implements the acceptance contract for #139 and #140, under the rollout umbrella #25.
This adds host diagnostics and an isolated acceptance appliance, not a new auth surface.

## 8 — headless first contact and shareable report

An owner who installs through SSH already has a trusted, encrypted path to the box.
Before Tailscale, `wizard contact` prints an SSH local-forward command and a browser
URL for the installed shell. The target is discovered from the active SSH connection
and the shell slot's loopback `view.local`; no fixed owner address is shipped. Run
the printed SSH command **on the owner's computer**, keep it open, then open the
loopback browser URL there. Existing SSH host-key verification and authentication
remain mandatory. This is the same owner-only loopback entry as sitting at the box;
it is not an unauthenticated LAN entry and must not bind any new public listener.
The installer prints it for a usable fresh install. A missing SSH context produces
an explicit action to reconnect by SSH, never an invented reachable address. A
failed shell probe produces failure, not a working-link claim. A non-default SSH
port is carried into the command. Remote forwarding, Funnel and Tailscale SSH are
not enabled. Only then use Setup → Use Wizard on your phone (PHONE_SETUP.md).
No one-time LAN code is needed because SSH supplies authentication and encryption.
This baseline requires SSH-capable owner access; phone-only first contact is not claimed.

`wizard report` prints a single JSON diagnostics document; redirect stdout to save it.
It works with broken chat and without network or provider credentials. It includes:
CLI/Python/OS versions, release identity/status and pin mismatch counts, expected and
observed source/image digests, selected service states, update policy, and bounded
recent error **classes and counts** from fixed Wizard service journals. It must never
serialize arbitrary log lines, error messages, URLs, names, content, environment,
process arguments, container inspect/config, auth stores, app data or private paths.
An allowlisted projection, not regex cleanup of a raw archive, is the privacy boundary.
Unknown/invalid fields are omitted. Unavailable probes are explicit. Nothing uploads.
Secret-canary regression tests plant opaque tokens, passwords, emails, tailnet addresses,
URL credentials/query tokens and private text in every accepted input and probe output;
none may occur in the serialized report, including error paths.

## 9 — persistent shipped-profile signal

One isolated Ubuntu 24.04 ARM appliance on the Thales work volume is kept across runs.
It installs the public installer and the selected released profile without bypassing
pin verification. Harness changes are tested as an explicitly recorded source overlay
AFTER a shipped-profile baseline; an overlay is never called a released install.
A second disposable Ubuntu VM supplies the daily clean-install case. Never point at
an owner's live install, import personal data, sign in to a provider or create new
Wizard conversations. Heavy VM runs require the durable worker.

The non-private workflow is Wisdom public-domain reading: install the catalog app,
import one small clearly attributed public-domain collection, open its actual reader,
read content, set reading progress, and fetch again to verify that progress. No AI call,
private starter archive, made-up response or substitute workflow is allowed. If the
catalog does not provide the app, record a failure rather than running an ad-hoc app.
Every retained-state run first verifies the previous reading progress, then advances
it through the installed API. A stopped-container restart and a SQLite backup/restore
of this fixture's own app state prove restart/restore continuity (not OS disaster
recovery; the separate backup audit owns that gate). Release upgrade is in place via
the public installer with an explicit target and a post-upgrade workflow readback.

Daily at 09:15 UTC, a control-plane cron submits the frozen runner to the durable
worker and posts one sanitized receipt as a comment to #140. No new Wizard thread.
Failed steps and missing runs remain failures. Manual/operator intervention appends
an immutable failure record and resets the uninterrupted observation window; it
cannot be erased by a successful retry. The runner does not repair anything silently.
Each receipt binds source revisions, installed release/pins, clean/retained case,
workflow read/write/readback, first-contact probe, restore result and intervention count.
The feature gate is at least 72 continuous wall-clock hours on the same candidate,
with daily successful journeys and no unrecorded gaps/interventions; a new candidate
or any failure resets the window. Bootstrap and one full run do not prove 72 hours.
The persistent VM is kept, the disposable clean-install VM is deleted after each run.
At least four consecutive successful daily receipts must span 72 hours; a missed
calendar slot is failure. All timestamps and gate arithmetic use UTC. Upgrades and
source overlays reset the window; each run records overlay paths (never installer
or pin-verifier changes). No overlay run counts as shipped-profile soak. Guest SSH
login history is checked for non-runner logins and becomes an intervention failure.
Receipts form a SHA256-linked local ledger; GitHub comments are editable mirrors,
not immutable storage. Public comments contain fixture IDs, not private host paths.
Only the isolated fixture's reading database may be restored: snapshot at progress A,
advance to B, restore via SQLite backup API, assert A. A no-op restore is failure.
Setup evidence means route rendering, not enrolled phone access. ARM results do not
claim amd64 coverage. SSH server-side addresses are discovery hints, not guaranteed
reachable behind NAT; explicitly record any host/port override. A sudo-stripped SSH
environment requires explicit --ssh-host/--ssh-port; do not guess another login's target.

## Required evidence before closing

- Fable spec review; focused diagnostics/contact tests, including privacy canaries.
- Fresh Ubuntu 24.04 public-install receipt; forwarded owner shell opens pre-Tailscale,
  non-loopback listeners remain absent, Setup route works, another unauthenticated
  network path has not been created. New UI is not added; existing shell screenshots
  in two skins are journey evidence, not a claim that the harness changes appearance.
- Initial and scheduled full clean/retained journeys, upgrade and fixture restore,
  scheduler readback, persistent appliance location, and comments on #139/#140.
- CI green and fresh-box proof before merge; elapsed soak remains independently pending.
