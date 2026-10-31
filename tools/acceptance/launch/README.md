# Launch audits 8 and 9: isolated acceptance runner

Contract: `spec/LAUNCH_AUDITS_8_9.md`. CLI implementation is in WAM's `wizard-cli/wizard`.

## Placement and execution

Stage **pushed commits**, never a live owner checkout. Set `WIZARD_ACCEPT_ROOT` to a
private directory on the build machine's work volume. Keep all Lima images, caches,
VMs, runs and state under it. `run.py` is a durable **heavy** worker entry, not a
command to run inside a conversational terminal or a cron shell. Submit its argv
and cwd using `wizard_heavy_submit`; receipt is the turn boundary. Set the worker's
`WIZARD_WORK_ROOT` to the mounted work volume on macOS, or an existing reserved
work directory on Linux. The acceptance directory must be strictly below it.
The runner admits native macOS/arm64 (VZ) and Linux/x86_64 (QEMU/KVM) only, reusing
`release_gate.native_vm_config` and its digest-pinned image. Linux also reuses
the release gate's 24 GiB guest disk budget; Mac keeps its 50 GiB guest. Preflight
requires 250 GiB reserve plus guest disk, 1 GiB metadata and (when enabled)
9 GiB phone scratch: 284 GiB for Linux onboarding. Host commands refuse a
depleted reserve, but forced stop/delete always remain available.

The runner accepts `--root`, `--release`, `--previous-release`, and `--cli` (the
frozen WAM CLI source mounted into the guest). Both VM installs use the **public**
`https://aiwizards.com/os.sh` and release pins. No `WAM_REF` or verifier override.
`WIZARD_PRIVATE_ACCESS=none` explicitly postpones enrollment in the legacy daily
lane. The opt-in onboarding lane below adds a dedicated ChatGPT sign-in; it never
uses an owner's existing provider login. Frozen CLI probes do not modify the shipped profile. This is not
proof that an unreleased CLI change is already in a released installer.

- `launch-real-use`: persistent native Ubuntu 24.04 appliance; never automatically deleted.
- `launch-clean-<run-id>`: disposable **candidate** clean install and strict shell/Setup
  first-contact journey; deleted, then recreated from empty disk for a separate
  previous-release fixture baseline → public candidate upgrade → strict readback.
  Only one disposable VM exists at a time. This adds a third public install, not
  a third concurrent VM. Evidence paths are distinct and never overwritten.
- `runs/<id>/private-run.log`: private installer/debug output; **never upload/comment**.
- `runs/<id>/receipt.json`, `receipts.jsonl`: bounded receipts, SHA256-linked.
- `persistent-state.json`: the last verified public fixture reading position.
- `intervention-cursor.txt`: last guest interactive-login check; wtmp covers interactive
  TTY logins, not a claim to detect a privileged actor hiding noninteractive changes.

`journey.py` imports a deterministic three-file ZIP containing only the attributed
opening of Lincoln's public-domain Gettysburg Address. It refuses unrelated library
entries. It exercises the installed app API, reads text, changes progress, snapshots
with SQLite's backup API, changes progress again, restores and reads back the older
value. A VM reboot then repeats the retained journey. The source unit tests for this
fixture are not a substitute for an installed-app receipt.

`tunnel.py` runs the contact command using the real mapped SSH port, pre-pins the
fixture's host public key, opens the shell and Setup API through that forward, and
closes it. It never turns off host-key checking. Loopback forwarding is on the
operator host only; no LAN shell listener is created. The native command leaves NAT
host/port overrides explicit. It is HTTP first-contact proof, **not browser rendering
or two-skin screenshots**; those remain separate acceptance evidence.

## First-contact release boundary (0.3.32 → 0.3.33)

The frozen 0.3.32 `wizard-ux` nginx recipe already proxies `/wizard/...` to
Agent Service; `view.local` is the correct same-origin owner front door. Its
Agent Service pin `e7bfd6d`, however, predates `/wizard/v1/setup`. A shell 200 plus
Setup 404 on that baseline is the documented release defect corrected by 0.3.33's
`634fe96` pin, not an SSH target or API path error. Do not redirect contact to the
headless Agent Service port (it does not serve the shell) or patch the old profile.

The candidate clean install and every upgraded/retained candidate journey must
pass both shell and Setup probes, including boolean `first_run`. `wizard contact`
now fails explicitly when only HTML works. The older release is exercised only as
`upgrade-baseline` for reading-state continuity: it still validates pins, shell,
report, public reading and restore, but writes `contact: null`, `setup_route: null`
and `first_contact: not-evaluated-upgrade-baseline`. That is not a first-contact
pass. The upgraded candidate repeats the strict forward and Setup proof. Expected
release identity is checked for every journey, and per-case forward/JSON evidence
is retained separately. A candidate Setup 404 still fails the run.

## Daily schedule and reporting

Target schedule: **09:15 UTC daily**, local delivery. The control plane must submit
one frozen heavy job per date (idempotent key), never execute Lima outside the worker.
After completion fetch only `receipt.json` and use:

```
python3 tools/acceptance/launch/publish.py RECEIPT.json --issue 140
```

This posts a sanitized, deduplicated issue comment and verifies the exact posted
comment by ID. It does not create a Wizard thread. `publish.py` is not a scheduler
and does not prove a daily job is installed. Do not enable the daily schedule before
one initial end-to-end run succeeds; post failures as failures, without repair/retry
being counted as uninterrupted soak. Any in-place candidate upgrade resets the window.

The gate requires four consecutive successful UTC daily receipts spanning at least
72 real hours, same candidate, no gaps/interventions/overlays. A single bootstrap
run cannot satisfy it. The runner presently fails a retained candidate mismatch;
changing candidates requires an explicit operator intervention/reset, not a silent
daily installer upgrade. Do not close #140 merely because unit tests pass.

## Lightweight checks

```
python3 -m unittest tools/tests/test_launch_audits.py -v
python3 -m py_compile tools/acceptance/launch/*.py
bash -n tools/acceptance/launch/bootstrap.sh
```

These check fixture provenance, real SQLite backup/restore semantics, gate reset
conditions, receipt chaining and comment-canary rejection; they do not run VMs.

## Real first chat and second-owner Android (#87 / #88)

Implementation/reuse plan:
- REUSE: public installer, installed Agent Service bootstrap/run/history APIs,
  ChatGPT app's pushed OAuth implementation and existing UI, Android Connect and
  exported thread handoff, android-build-thales SDK/API35 and shared worker lock.
- EXTEND: `run.py` clean journey; `tunnel.py` exposes its host-key-verified forward
  as a context manager for a temporary HTTPS transport to that **same** guest.
- NEW: acceptance-only credential lease / phone assertions / login access gate;
  no new production auth, chat, pairing or UI implementation.

Keep the running daily stage and its retained VM **unchanged**. Stage a new pushed
wizard-os commit, frozen WAM CLI and pushed `chatgpt-connection` source. Set
`--oauth-source` to the exact directory containing `codex.py`, not its archive
wrapper. Inspect archive member paths rather than assuming every archive has one
leading directory. The runner rejects a missing helper before starting any VM;
`first_chat.validate_oauth_source` performs the same metadata-only preflight without
reading credentials, importing the helper, renewing OAuth or contacting a provider.
Use a new,
short acceptance root, outside the directory holding host secrets. An onboarding
receipt is labelled `launch-onboarding-87-88` and can never satisfy the daily soak.
The default daily invocation still does not require a credential or emulator.

### Dedicated sign-in (the only owner action)

Run `login.py --oauth-source CHATGPT_SOURCE --state SECRETS/chatgpt --origin HTTPS_ORIGIN`
under the build machine's service supervisor, bound to loopback. Give it a new,
private Tailscale Serve HTTPS port (never reset existing Serve configuration).
Share only the `owner-link` generated in the private state directory. Owner opens
that link, presses **Connect**, then approves the code on the official ChatGPT
page. The app UI and OAuth are reused unmodified; the acceptance wrapper adds a
Secure, HttpOnly, SameSite capability cookie. No device codes, request paths,
tokens, upstream bodies or credentials are logged. The station does not connect
to any existing Hermes dashboard, change its defaults or register a pool entry.

`connection.json` is app-owned, 0600, in the build machine's 0700 secrets directory,
**outside source and every guest mount**, including already-running retained VMs.
Older daily VMs mount their entire acceptance root: use a host-only backing directory
outside that root and a `secrets` directory symlink at the required logical path.
Verify from the retained guest (including sudo) that a harmless probe file through
that symlink is unreadable, without changing the VM/stage. `run.py` also checks the
old fixture's mount configurations against the resolved credential path. Do not
archive it, put it in an argv/env,
or copy an owner's live Hermes auth. The host alone renews the new login. Guest
receives only its short-lived access token, never the rotating refresh token.

### Frozen heavy worker invocation

```
env WIZARD_WORK_ROOT=WORK_VOLUME python3 tools/acceptance/launch/run.py \
  --root NEW_SHORT_ACCEPTANCE_ROOT --release 0.3.40 --previous-release 0.3.39 \
  --cli FROZEN_WAM/wizard-cli/wizard --onboarding-only \
  --first-chat-secret SECRETS/chatgpt/connection.json --secrets-root SECRETS \
  --oauth-source CHATGPT_SOURCE --phone-config PRIVATE_PHONE_CONFIG.json
```

Submit this as a **heavy** job; never start a VM/emulator in a conversational SSH
shell. `--onboarding-only` creates one disposable VM, installs the public release,
runs the existing shell/Setup/reading journey, then chat + phone, and deletes the VM
in `finally`. It never starts or mutates `launch-real-use`. For a separate full
acceptance root, omitting this flag also retains the original upgrade/soak cases.

First chat reads `/wizard/v1/bootstrap`, creates a Wizard thread through Agent
Service, selects the first safe text-model slug advertised by the dedicated host
ChatGPT connection's authenticated catalog, sends through `/wizard/hermes/v1/runs`,
waits for **completed + non-empty output + confirmed actual provider/model**, then
reads back an assistant message. The same selected slug is locked at thread creation,
send and runtime readback; there is no retired hardcoded slug or fallback retry.
Catalog errors fail closed before any guest credential injection.
The shipped Service has no `/wizard/v1` *send* API; the `/wizard/hermes/v1` route is
the actual shell send contract, not a direct Hermes bypass. Do not invent a
`/wizard/v1/chat` endpoint. Receipts record only `{passed, latency_ms, provider}`;
thread IDs and response text travel only through captured in-memory pipes to the
phone assertion. A model error is never interpreted as a reply. In `finally`, the
guest auth file is removed, the disposable Hermes engine restarted to drop cached
credentials, and the exact path read back to assert absence. VM deletion is an
additional containment layer, not a substitute for lease cleanup.

Failures append `first_chat_failure` to the **private** run log: fixed snippet
`install`/`chat`/`remove`, guest return code (null on timeout), and an allowlisted
stderr exception class. Host catalog/access failures use fixed `catalog`/`access`
stages, a null return code and the same class allowlist. Nested Docker failures use
the same class-only projection.
Raw stderr, argv, HTTP bodies, credential values, session IDs and response text are
never copied into that diagnostic or the public receipt. An install failure and a
subsequent cleanup failure each retain a separate diagnostic row.

### Android input and assertions

The private phone config contains host paths/settings, never provider credentials:

```
{"apk":"PUBLISHED_APK", "feed":"FROZEN_PUBLISHED_FEED.json",
 "sdk":"ANDROID_SDK", "work_root":"SHARED_WORKER_LOCK_DIRECTORY",
 "java_home":"JAVA21_HOME", "emulator_port":5682, "https_port":9450}
```

Freeze the **actual published** feed and APK together; record version/code drift
rather than relabelling a newer feed as an older version. Verify byte size, SHA256,
release signer, package and version/code before installation. No build or QA APK
is substituted. The source supports Android SDK/AVD placement from the
Android build tooling and takes the same `worker.lock` non-blockingly. On the
Linux worker, `work_root` is the heavy service's lock directory, not AndroidBuilds:
read its `--lock` argument from the user service and use the parent directory.
The inherited `WIZARD_HEAVY_LOCK_FD` must match that exact file's device/inode;
it is neither unlocked nor closed by the phone step. API35 uses x86_64 on Linux,
arm64-v8a on macOS, never a cross-architecture emulator.

Set `"tailscale_sudo": true` only on a worker with pre-authorized passwordless
`sudo -n tailscale` access and no configured unprivileged Tailscale operator. It
prefixes only the bounded Tailscale commands, never the VM or emulator, and keeps
the same dedicated-port conflict/preservation/cleanup checks. The default remains
unprivileged. It does not change operator permissions or reset Serve.

Append `--check-only` to the frozen invocation for host admission, OAuth helper
layout, credential permissions and guest-mount exclusion checks without creating
a VM or contacting the provider. This does not validate the APK, boot an emulator,
or prove a first chat; separately run `phone.validate_apk` against the frozen
feed/SDK and inspect `avdmanager list` / `emulator -version` before queuing.

The emulator has a new AVD/disk and no installed package or stored origin. It opens
the real native Connect before any owner server loads. A generic artifact proves
normal Main → first-run Connect; a published owner-upgrade artifact is identified
from its BuildConfig constant and enters the exported Connect activity directly,
never Main at its migration default. That entry is reported explicitly and is not
claimed as generic first-run proof. It pastes the new HTTPS address
into the real native control, uses a temporary unused Tailscale Serve port to the
verified SSH forward, and waits for the real shell. No mock shell, TLS bypass,
private CA, preferences injection, debug bridge or CDP. It opens the just-proven
chat with the release's native thread handoff and asserts the actual reply is
visible in accessibility XML. It exercises Back at nested thread and shell root
(the nested composer must really disappear), plus process-death persistence.
Unpaired root Back is also exercised for generic APKs, but deliberately not for
owner-default artifacts, where it would navigate to the old live server.

Only bounded pass/fail checks + APK identity enter a successful phone receipt.
The emulator uses the host's scoped MagicDNS resolver for the box's tailnet
suffix (read from `scutil --dns` on macOS, `/etc/resolv.conf` on Linux,
or `dns_server` in the phone config), as a
real phone running Tailscale would; otherwise it sees only the host's primary
resolver and cannot resolve the box address.
Failures retain completed checks and an allowlisted `failure_stage` (preflight,
APK validation/install, lock/AVD/emulator, Connect, HTTPS, address entry/pairing,
reply, Back, restart, crash or cleanup); a failed phone receipt fails the whole
onboarding run. Exception text, command output, URLs and session data are never
serialized. UI XML,
transcripts and screenshots are never retained. Emulator disk and temporary XML
are deleted, emulator stopped, and only the new HTTPS handler removed/read back
in `finally`; existing Serve handlers must remain identical. **Address pairing is
not QR proof. Emulator is not physical-device proof.** #88 still requires QR and
one real handset; #87's separate Mac/public-app gate also remains open.

Lightweight tests (not evidence of a model/emulator run):

```
python3 -m unittest tools/tests/test_launch_audits.py tools/tests/test_launch_onboarding.py -v
```
