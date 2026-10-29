# Promote 0.3.65: installer reruns keep ChatGPT and Claude connected

## Why

Heidi's install on 26 Oct 2026 was a root-owned stock Hermes from the official `install.sh --skip-setup`, installed with `os.sh start`, joined to our tailnet first and then moved to the customer's tailnet with `tailscale logout` and a rerun. It needed hand repairs:

1. The rerun rewrote the ChatGPT/Claude `app.env` and the host-dashboard unit to the new tailnet IP, but the app containers kept the old one. ChatGPT showed unreachable and Claude sign-in never reached Hermes. A Claude-less model picker followed, because the picker hides Claude when `/wizard-claude/api/accounts` fails.
2. The rerun finished box-only ("Tailscale is not connected yet") while the owner was approving.
3. The new tailnet had HTTPS certificates off. The install finished with only a note: no owner action and no link.
4. `wam updates` told the owner to "update this Hermes by hand" for the official installer's layout.

## What changes

0.3.65 is Stable 0.3.63 with **only** the App Manager pin moved: `e3f76a68` → `8607981008e9b5c3df6b685ed124d816988ce28f`. That commit is wizard-app-manager #259 on `maintenance/stable-0.3.57` and carries the same change as main #258 (`11a7c775`) and Latest #260 (`da2f01d1`).

- **Connection apps.** `wam alongside`, which every install and rerun runs, restarts each running app whose dashboard address or login changed, or whose running container still carries an old value (a tailnet move). Runtipi's restart regenerates `app.env` and force-recreates the containers. It does this only against a dashboard in state `ready`, and any app it can't restart is reported as degraded.
- **HTTPS-off owner step.** HTTPS certificates being off is now an explicit owner step: `needs_owner` with https://login.tailscale.com/admin/dns. The install continues by itself once a real `tailscale cert` succeeds, and `os.md` has the owner message word for word.
- **Tailscale sign-in.** After a successful `tailscale up`, the installer never runs a second `up`. It polls for Running until the deadline, with a grace period after a shown link.
- **Hermes updates.** An official-installer Hermes reports `self_updating` with `hermes update`.

Every app, Wizard UX, Agent Service, Troubleshooter and the Hermes pin are byte-for-byte 0.3.63. There are no migrations.

Latest moves to **0.3.66**: the 0.3.64 runtime pins plus the same App Manager change on the Latest branch (`da2f01d1`), so Latest never trails Stable.

## Evidence

All runs used disposable KVM guests on oscar-main (Ubuntu 24.04.5, 4 vCPU, 8 GB). Each had root stock **Hermes v0.22.5 from the official installer `--skip-setup`** and `hermes gateway install`, like Heidi's box.

The tailnets are local **headscale** instances, so the owner's login approval can be driven with `headscale auth register`. That stands in for the owner opening the link. Headscale cannot issue HTTPS certificates, so:

- turning HTTPS **on** was simulated with a test-only `tailscale` wrapper that reports `CertDomains` and accepts `tailscale cert` once a flag file exists;
- `tailscale serve` links stay unavailable (headscale returns 501). That is why each run ends "box-only" and the Troubleshooter notes a missing route. It is a test-infrastructure limit, not a product result.

### Old Stable reproduces the incident (0.3.61 public `os.sh`)

The guest went through a fresh install on tailnet A (100.91.0.1), then `tailscale logout`, then a rerun on tailnet B, approved about 18 s after the link appeared.

- **Incident 3:** the rerun ended `done` with the box-only note "HTTPS certificates is off …".
- **Incident 1:** `app.env` and the dashboard unit moved to `100.126.0.1`, but the `wizard-chatgpt-engine` and `wizard-claude-engine` containers kept `WIZARD_*_HERMES_URL=http://100.91.0.1:9119`. Their `/api/connection` hung 20 s and 15 s.
- **Incident 2** did not reproduce: the old loop waited for the approval. The fix hardens the success path against a second `up`, which is the failure mode Codex flagged and the tests model.

### Fresh install, 0.3.65 (exact manifest SHA256 `4407ed73…`, public `os.sh` = main `fa9271d0…`)

| Time (UTC) | Event |
|---|---|
| 17:46:39 | `start` |
| 17:47:12 | `needs_owner` with the Tailscale link |
| 17:47:24 | Link approved |
| 17:47:29 | `needs_owner` "Your Tailscale network needs HTTPS turned on once …" + https://login.tailscale.com/admin/dns |
| 17:48:03 | HTTPS "turned on" (flag file) |
| 17:48:08 | `tailscale cert` probe succeeded; status back to `running` |
| 17:55:36 | `done` (about 9 min end to end, including both owner steps) |

Result:

- `release.json`: pinned 0.3.65, 0 failed checks, 0 `FAIL` lines; `wizard doctor` 0 FAIL.
- ChatGPT 0.2.4 and Claude 0.2.6 engines run with `HERMES_URL=http://100.77.0.2:9119`. From inside each container the dashboard is reachable (HTTP 200), and `/api/connection` answers in 0.13 s / 0.05 s (`not_connected`, `accountCount: 0`).
- `wam updates` → `hermes: self_updating, command: hermes update`.

### Tailnet move on the same box (public command: `os.sh | WIZARD_RELEASE=0.3.65 bash -s start`)

The move went from tailnet C (100.77.0.2) to a new tailnet D:

| Time (UTC) | Event |
|---|---|
| 17:58:44 | `tailscale logout`, then `start` |
| 17:58:52 | Link shown |
| 17:59:07 | Link approved |
| 17:59:15 | HTTPS owner step |
| 17:59:44 | HTTPS on |
| 18:01:49 | `done` (3 min 5 s) |

Result:

- The log says "Restarted with the current agent address: wizard-chatgpt, wizard-claude". Both containers were recreated at 18:01:21 and 18:01:35 with `http://100.126.0.1:9119`.
- No container env, `app.env` or the dashboard unit still contains `100.77.0.2`.
- Both engines reach the dashboard (200); `/api/connection` answers in 0.10 s / 0.06 s.
- 0 FAIL lines; `wizard doctor` 0 FAIL.

### Repair of a box left stale by old code (candidate `a4af2e0`, same tree as #259 apart from two review follow-ups)

On the box from the 0.3.61 reproduction, whose containers were still on the old IP, a plain rerun recreated both apps. `/api/connection` went from 15–20 s hangs to under 0.01 s, and both engines reach the dashboard.

### Upgrade test 0.3.63 → 0.3.65 (`--from 0.3.63`)

The test used the guest after a public-command install of stable **0.3.63** (WAM `e3f76a68`, ChatGPT 0.2.4, Claude 0.2.6). The upgrade ran 18:08:12 → 18:10:05 with `os.sh | WIZARD_RELEASE=0.3.65 WIZARD_STRICT=1 bash -s start`.

- `release.json`: pinned 0.3.65, 0 failed checks; WAM checkout `8607981008e9`.
- Hermes `config.yaml`, `.env`, `SOUL.md` and `auth.json` hashes are unchanged.
- Hermes is still v0.22.5; gateway and dashboard are active; API `/health` 200; `wizard doctor` and `wam doctor` 0 FAIL.
- Healthy-rerun no-op: only `runtipi` and the release index were recreated. Every app container, including ChatGPT and Claude, kept its StartedAt and image, and both still reach the dashboard.

### Tests

- wizard-app-manager #258/#259/#260: CI green.
  - Full local suite: 1243 passed on main, 786 on Stable and 1135 on Latest.
  - 11 new or changed tests fail on the old code: stale running container, docker reader, alongside recreate and its install.sh reporting, HTTPS owner step continues and its deadline fallback, cert must really issue, approved login waited for, needs_owner status rendering, official Hermes layout, and the Claude-login schedule.
  - Codex findings (no second `up`; no recreate against a failed dashboard; login included in the stale check) were fixed with tests and resolved.
- wizard-os `tools/tests` on main with 0.3.65/0.3.66: 213 OK. `check_release.py`: ok for both (DRIFT lines are informational).

## Not covered

- A real Tailscale control plane, real HTTPS certificates and real `tailscale serve` links. The guest used headscale plus the wrapper described above.
- A real ChatGPT/Claude sign-in. The engines' reachability to the agent dashboard was verified; the owner's provider sign-in is a human step.
- A physical phone.

The model-picker cache (incident 6) is tracked in wizard-ux#572. Hermes, the Agent Service and the dashboard plugin show a new credential immediately; the gap is the shell's 5-minute cache, plus Claude being hidden silently when the Claude app is unreachable.
