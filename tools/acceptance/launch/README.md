# Launch audits 8 and 9: isolated acceptance runner

Contract: `spec/LAUNCH_AUDITS_8_9.md`. CLI implementation is in WAM's `wizard-cli/wizard`.

## Placement and execution

Stage **pushed commits**, never a live owner checkout. Set `WIZARD_ACCEPT_ROOT` to a
private directory on the build machine's work volume. Keep all Lima images, caches,
VMs, runs and state under it. `run.py` is a durable **heavy** worker entry, not a
command to run inside a conversational terminal or a cron shell. Submit its argv
and cwd using `wizard_heavy_submit`; receipt is the turn boundary.

The runner accepts `--root`, `--release`, `--previous-release`, and `--cli` (the
frozen WAM CLI source mounted into the guest). Both VM installs use the **public**
`https://aiwizards.com/os.sh` and release pins. No `WAM_REF` or verifier override.
`WIZARD_PRIVATE_ACCESS=none` explicitly postpones enrollment; no auth keys or provider
sign-ins are used. Frozen CLI probes do not modify the shipped profile. This is not
proof that an unreleased CLI change is already in a released installer.

- `launch-real-use`: persistent Ubuntu 24.04 ARM appliance; never automatically deleted.
- `launch-clean-<run-id>`: disposable clean install, previous-release journey, public
  upgrade to candidate, retained workflow readback; deleted after the run.
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
