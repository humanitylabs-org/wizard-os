# Promote 0.3.68: current Agent Service and Wizard UX, exact AI account matching

## Why

Stable 0.3.65 pinned Agent Service `6424db09`, 183 commits behind main, and Wizard UX on a Stable-only branch. Several fixes that customers hit on 26 Oct 2026 were stuck on main:

- The Agent Service host plugin reports a one-way `emailHash` per provider account (#196) and says so (#203). Without it the Claude app matched its original Claude Code sign-in to an agent row by masked email (`h***@e***`), which can't tell `heidi@` from `hank@`.
- Setup says a phone is connected only after it opens Wizard (#191). Security dependency updates (#195).
- Model picker (wizard-ux #572, fixed by #573): Claude models were missing for up to 5 minutes after a sign-in and were hidden silently when the Claude app didn't answer.
- Home's AI widget labelled a ChatGPT sign-in `openai-codex-oauth-1`.

## What changes (vs 0.3.67, the backup line; vs Stable 0.3.65 it also adds 0.3.67's backup bundle)

- Agent Service `6424db09` → main `b1f8d2c1` (image `sha256:59cc1672…`, run 40464828166). The open sign-in recovery PRs #199/#200/#201 are not included.
- Wizard UX `4b9264d3` → main `d53b2b24` (image `sha256:5b661b07…`, run 40465748639), including #573.
- Claude 0.2.6 → **0.2.8** (claude-connection `43f6a412`, engine `sha256:7e795608…`) and ChatGPT 0.2.4 → **0.2.6** (chatgpt-connection `f73b8487`, engine `sha256:72be4ede…`), both from wizard-app-store #33/#34/#36:
  - Claude merges the original sign-in with an agent row only on the exact `emailHash`. Masked-email matching remains only for older agent services that report no hashes.
  - `/api/connection` names rows that carry Hermes' default labels by position (`ChatGPT`, `ChatGPT 2`, `Claude 2`), so Home shows those names. Owner nicknames are kept.
  - The accounts page follows design rules v0 (#34).
- App Manager, Troubleshooter, Hermes and every other default app are exactly 0.3.67's.

## Evidence

The runs used disposable KVM guests on oscar-main (Ubuntu 24.04, 4 vCPU, 6 GB) with root stock Hermes v0.22.5 from the official installer (`--skip-setup`) and `hermes gateway install`. Both guests joined a local headscale tailnet; headscale stands in for the owner's login approval and has no HTTPS certificates or Serve (see promote-0.3.65.md). Each upgrade ran with the public command: `curl -fsSL https://aiwizards.com/os.sh | WIZARD_RELEASE=0.3.68 WIZARD_STRICT=1 bash -s start` (os.sh = main `fa9271d0…`).

### Upgrade 0.3.65 → 0.3.68 (`--from 0.3.65`)

The guest was installed earlier on 0.3.65 (WAM `8607981008e9`, ChatGPT 0.2.4, Claude 0.2.6, Agent Service `840a371c`). On restart its headscale node had expired, so it rejoined with a **new tailnet IP** (100.126.0.1 → 100.77.0.3). Before the upgrade, its dashboard unit and both connection apps were still on the old address: `/api/connection` hung for 20 s and 15 s.

Timeline: 07:28:43 start, 07:33:45 last app recreated, then `done`.

- `release.json`: pinned 0.3.68, 0 failed checks. WAM checkout `da2f01d17feb`. `wizard doctor` and `wam doctor` 0 FAIL.
- Hermes `config.yaml`, `.env` and `SOUL.md` hashes are unchanged; there is no `auth.json` on this box. Hermes is still v0.22.5; gateway and dashboard are active; API `/health` 200.
- Running images: Agent Service `59cc167250c9`, UX `5b661b073d6a`, ChatGPT engine `72be4ede5a2e`, Claude engine `7e7956086a2f`, plus the backup line's voice and connection-router. Files, browser, notifications, secret-drop and transcriber kept their StartedAt.
- Log line: "Restarted with the current agent address: wizard-chatgpt, wizard-claude". The dashboard unit moved to `--host 100.77.0.3`. Both engines reach the dashboard (200), and `/api/connection` answers in 0.9 s and 0.2 s (`not_connected`, 0 accounts).
- The host plugin answers with `identity: {emailHash: 'sha256-16'}` through the Claude app's `/api/accounts`.
- `/wizard/ai-usage`: ChatGPT and Claude providers are `ok`.

### Upgrade 0.3.61 → 0.3.68 (`--from 0.3.61`)

The test started from a fresh guest:

1. Official Hermes install.
2. `tailscale up --login-server` against headscale.
3. Public `os.sh` with `WIZARD_RELEASE=0.3.61`. The Tailscale link was approved through headscale, and the install reached `done` at 07:47:11 (WAM `e3f76a68ea49`, 0 failed checks, doctor 0 FAIL).
4. The upgrade, 07:48:17 → 07:52:30 (about 4 min).

Result:

- `release.json`: pinned 0.3.68, 0 failed checks, WAM `da2f01d17feb`, `wizard doctor` and `wam doctor` 0 FAIL.
- Hermes `config.yaml` (`13a542c3…`), `.env` (`99af3bea…`) and `SOUL.md` hashes are identical before and after the upgrade. Hermes is still v0.22.5; gateway and dashboard are active; API 200.
- Running images: the same five new digests as above. Both engines reach the dashboard on `100.77.0.4` (200), and `/api/connection` answers in 0.19 s and 0.10 s.
- The Claude app's `/api/accounts` carries `identity.emailHash`, and `/wizard/ai-usage` lists ChatGPT and Claude as `ok`.
- A phone-size Chromium render of the upgraded shell Home has no page errors and shows the AI widget with CHATGPT and CLAUDE (0 accounts on the test box).

### Tests

- wizard-agent-service #203: CI green. The new unittest fails on main and passes on the branch (10/10).
- wizard-app-store #33/#36: CI green (store, unit, container, Playwright). The sign-in reliability suite passes 15/15; its 3 new tests fail on the old engines.
- wizard-ux #573: CI green. Live-shell browser QA on desktop and phone with a hanging and a 502 Claude app shows the note and a refetch on reopen; the same QA on main shows neither (https://github.com/humanitylabs-org/wizard-ux/pull/573#issuecomment-6435903585).
- `tools/check_release.py releases/0.3.68.json` (online): ok. `tools/tests`: 213 OK. WAM release tests: 83 passed.

## Not covered

- A real Tailscale control plane, real HTTPS certificates and Serve links (headscale). The Troubleshooter reports `degraded` because headscale returns 501 for Serve, the same infra limit as 0.3.65. Server meters on Home read "Unavailable" through the SSH-forwarded test view for the same reason.
- Real ChatGPT/Claude sign-ins, so emailHash merging was not observed on a signed-in account. The hash contract is covered by tests on both sides.
- Backup/restore/Undo. WAM is unchanged from 0.3.67, and its Thales backup acceptance is owned by the Archimedes team (wizard-os #251).
- A physical phone.
- The alongside host plugin installs from Agent Service main HEAD (`pinned: false`; this run got `718148a9`, whose `hermes-plugin/` is identical to `b1f8d2c1`). This is pre-existing behaviour, not changed here.
