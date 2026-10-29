# Latest 0.3.85: upgrading boxes keep their apps connected

Latest only. Stable stays 0.3.83 until James agrees to promote (asked on wizard-os #333).

0.3.85 is 0.3.84 plus one pin change:

| Component | 0.3.84 | 0.3.85 | Change |
|---|---|---|---|
| App Manager (host source) | `89cd51e8` | `30e3e1ab` | #349 (Recommended fix, failing-first tests): the upgrade settles each box's connection mode once. `wam/` Python only; every declared image input is byte-identical from `9cabb592`, so the App Manager image pin (`sha256:7e6c8b4a…`) stays. |

Images, Hermes, Agent Service, Wizard UX and every default app pin are unchanged from 0.3.84.

## What owners see

- **A box that already runs apps its owner installed and never chose how apps connect:** apps stay able to talk to each other, like before isolation (Settings › Connections › Details: Keep apps apart is off). The owner gets one notification: "Your apps stay connected … To keep apps apart, open Settings › Connections, tap Details and turn on Keep apps apart."
- **A new box (only Wizard's own apps):** apps are kept apart (Declared) from the first run.
- **A box whose owner already chose:** unchanged.

## Upgrade-safety review (why this release exists)

The Connections work Miguel asked to release was already on both channels before this cut, through other threads' release trains:

| Work | First release carrying it | On Stable since |
|---|---|---|
| App Manager #271 (one network per connection, Declared by default), #278, #283, #288, #290 (fixed-name volumes keep working), #293, #294, #297, #298, #300, #302, #310 | 0.3.74 | 0.3.74 (29 Oct) |
| App Manager #323, #328 (Agents, per-agent switches, Restore defaults), #331; Agent Service #265 (a turned-off app is refused in plain words; image `sha-24f3cd0a`, from 0.3.79) | 0.3.80 | 0.3.81 |
| App Manager #336, #339, #340 (Settings embed); Wizard UX #739 (Name your Wizard), #740 (Connections Settings tab), #742 | 0.3.82 | 0.3.82 |

Checks:

1. **Boxes that never chose a mode became Declared on update, with no migration.** Apps installed before isolation keep their installed `wizard.md`; if it has no `uses:` for an app they call, Declared cuts the link. Seen on Miguel's box (Music → YouTube Music, Search → Tinfoil; fixed there by hand with owner grants). Catalog now: Search 0.3.1 declares `tinfoil-api-key` (an app update reaches boxes); Music declares `music-source` but under the **same** version string `0.2.0-test.2` as the old install, so app updates never deliver it; Money and Cloudflare declare their links in the published versions; Card Benefits is not indexed. So an upgrading box can lose links → #349. Decision: **existing boxes with owner-installed apps → Open (safe side, as before isolation; sensitive apps and Disconnects still hold); new boxes → Declared**, decided once and recorded. Where wam can't read `wizard-grants.json` (often root-owned), an API-reported Open is kept; a Declared there can't be told apart from no choice and follows the same rule (the owner is told).
2. **#289 fixed-name volumes:** the fix is App Manager #290 ("installed apps with a fixed-name volume keep working after an App Manager upgrade"), included since 0.3.74.
3. **Agent Service #265:** in the Latest/Stable Agent Service image `sha-24f3cd0a` since 0.3.79 (`git merge-base --is-ancestor 069bf0c9 24f3cd0a`); release JSONs pin the Agent Service image, so the per-agent refusal ships with every release.
4. Runtipi dashboard owner auto-sign-in leftovers exist only on Miguel's box; not a release concern.

## Verification

- App Manager #349: 14 tests in `tests/test_connection_mode_settle.py` (all fail on `89cd51e8`), CI green (test, backend, CodeQL, gitleaks, review), Codex clean on the merged head after two findings were fixed (notice retried until Notifications takes it; API-reported Open kept).
- `tools/check_release.py releases/0.3.85.json`: ok (DRIFT lines informational). `promote_stable.py cut 0.3.85`, `check`: channels ok.

### Installed upgrade 0.3.83 → 0.3.84 → 0.3.85 on a disposable KVM guest, 30 Oct 2026 UTC

Rig: `tools/acceptance/upgrade-rig/kvm_upgrade.py` (Ubuntu 24.04 overlay, golden root Hermes v0.22.5, local headscale, public os.sh for every step), driven step by step so owner apps could be installed between steps; nothing ran on a real box.

1. Install 0.3.83 (public mirror, agent-run, `WIZARD_STRICT=1`): done in ~10 min.
2. As the owner, `wam install` two apps that don't declare each other: YouTube Music and Smart Home. Probe on 0.3.83: no mode recorded, Declared; YouTube Music cannot reach Smart Home on any of its addresses (HTTP 000; Smart Home reaches itself: 302, positive control).
3. Upgrade to **0.3.84** (previous Latest, public mirror): done in ~2.5 min; release.json 0.3.84 pinned, 27 checks, 0 failed; still Declared and still cut (000).
4. Upgrade to **0.3.85** (`WIZARD_RELEASE_BASE=http://10.0.2.2:18979` serving this branch's `releases/`, `0.3.85.json` sha256 `73a059e3…` identical to the PR; disclosed: the candidate was not yet mirrored): done in 123 s; release.json 0.3.85 pinned, 27 checks, 0 failed (App Manager commit `30e3e1ab`, image `sha256:7e6c8b4a…`).
   - Mode recorded **open**; `connection_mode_settled` = open ("existing box: apps installed before isolation keep their connections"), notice **sent**; the Notifications inbox holds exactly one "Your apps stay connected" notification. A second `wam bootstrap` changes nothing.
   - YouTube Music reaches Smart Home over the mesh (302). No app container was restarted (uptimes continuous across the upgrade).
   - All containers up/healthy; Hermes API 200, gateway active, shell 302; `wizard doctor` FAIL 0, `wam doctor` FAIL 0; Hermes config.yaml/.env/SOUL.md byte-identical.
   - Connections: the shell's Settings carries the Connections tab (`/wizard-os-home/core/settings.js`); the owner route `store-install/_connections/` answers "owner only" (403) locally as designed; the App Manager Connections view answers 200.
   - Agent tools: MCP `tools/list` for every app identical before and after (browser 3, files 5, notifications 4, secret-drop 4, smart-home 5, transcriber 2, chatgpt 1, claude 1, voice 2, youtube-music 3).
- Evidence (private scratch, `~/.hermes/cache/scratch/connrig/`): `step-hop1.json` sha256 `5a00ab64…`, `step-hop2.json` sha256 `3373b53e…`, `hop2.log` sha256 `5ed6982a…`.

## Not checked / caveats

- The rig has no Tailscale Serve, so the Settings › Connections tab itself (shown only when the owner route answers the signed-in owner's device) was not rendered in a browser on the guest; its code and the route were checked.
- A Music → YouTube Music pair could not be exercised on amd64 (Music's selected archive is arm64-only); the pair used has the same shape (neither declares the other).
- Boxes freshly installed on 0.3.74–0.3.84 that have owner apps and never chose become Open on this update (more permissive, nothing breaks; the owner is told).
- No Stable promotion is requested by this PR.
