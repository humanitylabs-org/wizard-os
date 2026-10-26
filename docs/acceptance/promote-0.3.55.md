# Promote 0.3.55: Troubleshooter repair fixes on Stable

## Decision and scope

Miguel's policy for the private launch: verified Recommended fixes merge immediately and may skip the soak (DECISIONS #82, fix fast-track; `--classification fix`). This promotion uses that path.

0.3.55 is Stable 0.3.53 plus **only** the Troubleshooter pin change. Compared with `releases/0.3.53.json`, the one runtime pin that changes is `components.wizard-troubleshooter.commit` (4b1f0ef → `c1b4c432fd7b162d23d42fb7d3d8fb049bee764e`) and its note. Everything else is metadata (`version`, `name`, `about`). Every image, App Manager, Agent Service, Hermes and default-app pin is byte-for-byte 0.3.53. The Troubleshooter is host tooling installed by `wam troubleshooter` as user systemd units; it has no image. No trunk features ride along: no backup/restore/Undo, Spaces or Android. No migrations, no owner-data deletion.

Troubleshooter changes in 4b1f0ef..c1b4c43 (first-parent; 3 merged PRs):

| PR | Merge | Change |
|---|---|---|
| wizard-troubleshooter #12 | `7e6cfc1` | One bounded, owner-approved repair tool set shared by Claude, ChatGPT and Tinfoil; host-independent paths. A box without a repair policy file gets no file/command grants, and every write/command needs an owner-page approval. |
| wizard-troubleshooter #13 | `c1b4c43` | Claude falls back to the agent's second Claude sign-in when the Claude app login hits its usage limit (same engine, same tools). |
| wizard-troubleshooter #10 | `eb27a16` | MIT license. No behavior change. |

No dependency change.

Latest testers keep the 0.3.54 backup bundle via 0.3.56 (0.3.54 plus the same Troubleshooter pin), cut onto `latest` in this PR.

## Published pins

Manifest `releases/0.3.55.json` SHA256 `f00d8bbd4360acc28144e03dd3bcbcf3c518f026ccdb05cf88598d59aad49000` (canonical wizard-os #248, merge `52562c79a35ff1b2e372d0d42a894620cfa09bc7`).

## Verification

- Troubleshooter main CI green on #12 and #13; 29/29 tests.
- Live owner-UI acceptance on the owner box (hand install at c1b4c43) for ChatGPT (gpt-6.1-sol) and Claude (claude-sonnet-5-5 through the second sign-in). Covered diagnostics, an approved RestartSec 5→6 write with daemon-reload and readback, and an approved restore to 5. The service was not restarted.
- `tools/check_release.py releases/0.3.55.json`: ok (DRIFT lines informational). `promote_stable.py check`: channels ok.

### Upgrade test 0.3.53 → 0.3.55, 26 Oct 2026 UTC

No demo box was reachable: `demo` and `demo-2` are offline, and `demo-3`'s node key has expired. So the upgrade was run in a disposable systemd container (Debian trixie, systemd as PID 1, an owner user with linger and a user session). It used the real WAM main `wam troubleshooter` (`103de84`) with `WIZARD_RELEASE_PINS` set to the canonical 0.3.53 file and then the 0.3.55 file. The box had a fresh layout and a stub `tailscale` that answers status and Serve.

- 0.3.53 install: `state: ready`, commit `4b1f0ef…`, pinned. The pinned official Node 22.23.2 was downloaded and its sha256 checked.
- Upgrade to 0.3.55: `state: ready`, commit `c1b4c432fd7b162d23d42fb7d3d8fb049bee764e`, clean checkout. `wizard-troubleshooter.service` and `wizard-guardian.timer` are active, the service has a new MainPID and `NRestarts=0`, and the `/troubleshoot` Serve route is unchanged.
- `GET /troubleshoot/api/ping` returns 200. The owner gate returns 403 both unauthenticated and with a forged `X-Forwarded-For`.
- The guardian ran report-only and succeeded (`actions: []`).
- `node --test` on the installed tree: 29/29 pass.

| Receipt (private scratch) | SHA256 |
|---|---|
| before.json (0.3.53 install) | `8b928b51ca64b4625284d4eca2c4643d7a907dcffc1aaf0a1c4e05cf61c888d6` |
| after.json (0.3.55 upgrade) | `bcb1d3da4887661cab4f0be3c800e5f9e0e990860fa45e2b7a86a031e353889a` |
| after-checks.txt | `0cd55cfa37ab7153bd1c75ebae59b6126d244023b893507ed34bb55b0ce6408c` |

## Not checked / caveats

- This was not a full installer upgrade on a real box. The demo boxes were unavailable, and the only changed pin is the host-tooling Troubleshooter, so the upgrade exercised exactly the `wam troubleshooter` step that `install.sh` runs. Images, shell, Agent Service and Hermes are unchanged from 0.3.53, so their acceptance carries over. Run the installer upgrade on `demo` when it is back.
- Owner-UI provider acceptance happened on the owner box, not on a fresh box. A fresh box with no sign-ins shows all engines as unavailable, which is expected.
- Boxes on 0.3.26–0.3.31 set to Automatic skip a fast-tracked stable as `unpromoted`; Update now still works. Boxes with a hand-installed Troubleshooter (units without the `wam troubleshooter` marker) are left as they are.

Rollback: point `releases/stable` back at 0.3.53 in both repos (it already has a valid promotion record).
