# Promote 0.3.143: the Troubleshooter guardian repairs by default on Stable, and an owner's report-only choice is never lost

## Decision and scope

James (9 Nov 2026) approved making the guardian act by default on every box (he replied "defaults" after the explanation of what it fixes on its own: restart a broken link, undo a fresh Agent Service update that broke it, start a repair).

Classification: **feature** (`--fast-track --classification feature`, DECISIONS #93).

**0.3.143 replaces 0.3.140.** wizard-os #484 recorded 0.3.140 as Stable, but before the public mirror moved an independent source review found three ways an owner's report-only choice could turn into repairs on (App Manager 9f793620). The stable mirror PR (wizard-app-manager #547) was held and closed as superseded, so **0.3.140 was never served as Stable by the public mirror**; no box was offered it as Stable. Its promotion record stays in wizard-os as history (records are immutable); this promotion moves `releases/stable` from 0.3.140 to 0.3.143.

0.3.143 is Stable 0.3.134 plus exactly one component move (cut in wizard-os #487, commit 83b5d8c, merged 35c37a5 at 2026-11-09T13:56:29Z; `releases/0.3.143.json` sha256 `b958b531845369412e9fff0224b4e707f619d678f2627862409467cd84698dc9`):

| Component | 0.3.134 | 0.3.143 | Change |
|---|---|---|---|
| App Manager (host tooling) | `525e9d3d` | `7d60346f` | wizard-app-manager#542 (guardian repairs by default) + #548 (the owner's report-only choice is never lost), see below. |
| App Manager image | `v4.10.2-wizard.993-4ef2963` | `v4.10.2-wizard.1052-17c8d9c` | Newest published main image (source_commit 17c8d9cd; `check_release` proves no image input changed up to 7d60346f). Latest has run this image since 0.3.104 (6 Nov). |

What the App Manager move does for the guardian:

- **#542 (9f793620):** `wam troubleshooter` writes `GUARDIAN_ACT=1` on fresh installs and on boxes whose host.env holds the old App Manager default; `wam troubleshooter --report-only` keeps it report-only (saved in `~/.wizard-os/guardian.json`, kept across updates), `--act` turns repairs back on; hand-installed Troubleshooters untouched.
- **#548 (merge 7d60346f), the fix that replaced 0.3.140:**
  1. A quoted hand edit (`GUARDIAN_ACT="0"` / `'0'`) is read the way systemd reads it (report-only), not as repairs on. A value that is neither 0 nor 1 never turns repairs on.
  2. An unreadable `guardian.json` stays report-only (`set_by: unreadable`) instead of falling back to the default; a missing file is still the default.
  3. Overlapping installs: the choice and host.env are read and written together under a short lock, so a `--report-only` run during another install's download is what ends up in host.env.
- **#546 (33de0444):** App Manager writes the gateway's grant keys for apps with tools, behind feature switch `wizard/gateway-keys`, **off** by default (no behaviour change unless switched on).

The move also carries every other App Manager main PR between 525e9d3d and 7d60346f, which Latest has been running (listed in docs/acceptance/promote-0.3.140.md; the only additions since 9f793620 are #546, #548 and release mirrors).

Every other pin (Wizard UX, Agent Service, Troubleshooter 9088a25, default apps, Hermes) is byte-for-byte 0.3.134.

Why now: fresh installs and Stable boxes should fix a broken link to the agent by themselves instead of only reporting it, and an owner who chose report-only must keep that choice.

Risk: the guardian acts on the box (bounded restarts, an undo of a fresh Agent Service update that broke the link, a repair through the box's AI connection). Owners who want it off run `wam troubleshooter --report-only`. Rollback below.

Note: `components.wizard-troubleshooter.note` in 0.3.143 says the units are installed "(... report-only)" in its first clause and then states the guardian repairs by default from App Manager 9f793620; the second sentence is the current behaviour (wizard-app-manager #544 review, corrected in wizard-app-manager `releases/README.md`).

## Verification

- **wizard-app-manager#548** (merged 7d60346f, Codex review no findings, CI green: test, backend, builder-verify, gitleaks, CodeQL, review):
  - **Fail-first:** the 16 new tests run against main e1c6c90 (= #542 behaviour): **15 failed, 22 passed** (the unquoted-with-blanks case already worked). Output kept privately, sha256 `1e2b52922290dca1fb33ba144e2c79585920822b4958d3e3d3f6277fd708d59f`.
  - **With the fix:** `tests/test_troubleshooter_native.py` + `test_troubleshooter_default.py`: **42 passed**.
  - **Independent probe:** the reviewer's own probe (written outside the fix, `probe-fixed.py` sha256 `1639f963b586f4b0…`) pointed at the fixed branch: all five cases (quoted hand edits, unclear values, malformed saved off-choice, report-only chosen during another install's fetch) report **no counterexample** (output sha256 `2c4c0c838b47a7fa…`).
- **wizard-app-manager#546** (merged 33de0444): CI green; feature switch off by default.
- **wizard-os #487** (the cut): `check_release.py` (online) ok for 0.3.143 and 0.3.144, `promote_stable.py check` ok, published-release tests 44 passed; CI (contracts, Wizard style, review) green.
- Mirrored to wizard-app-manager in #550 (`verify_mirror`: 4 files byte-identical to wizard-os main@35c37a55).

### Installed upgrade 0.3.134 → 0.3.143 on a disposable KVM guest (forum)

Job `heavy_0a9cc0dc37dd45da86ef98cbf838acc9` (log sha256 `a6bb8e13ee9d680c130531cfb32766a63d95369d57674df6b9fe4557233faa87`), run `20261109T135337Z-0.3.134-to-0.3.143`.

**Result: PASSED** (20261109T135337Z → 20261109T140641Z UTC)

**Rig.** Disposable KVM guest on oscar-main (Ubuntu 24.04 cloud image overlay, 4 vCPU, 8 GB, user-mode NAT, loopback-only SSH). Root stock Hermes (Hermes Agent v0.23.0 (2026.9.24) · stable · local 2bd378ed1b8d) from the official installer (`--skip-setup`) + `hermes gateway install`; Tailscale joined to a local headscale with a pre-auth key (stands in for the owner's approval); a test-only `tailscale` wrapper simulates HTTPS turned on. Headscale has no Serve, so installs end box-only. Nothing ran on a real box. Upgrade release base: http://10.0.2.2:32985. os.sh sha256 `2ee8f5c8fc4386a9…`.

- Install 0.3.134 (public command, agent-run, `WIZARD_STRICT=1`): done in 566 s; release.json 0.3.134 pinned.
- Upgrade to 0.3.143: done in 123 s; release.json 0.3.143 pinned, 27 checks, 0 failed.
- Hermes config.yaml/.env/SOUL.md: identical (config.yaml `f8eceb68…`, .env `49132ddc…`, SOUL.md `36c1f5a2…`).
- After: Hermes API /health 200, gateway active, shell 302, `wizard doctor` FAIL 0, `wam doctor` FAIL 0.

<details><summary>Containers after the upgrade</summary>

```
browser_wizardapps-browser-1 sha256:1b668429b3511ab407d8e00648891631b0b1a4d7e15e3ca70f38ab5b91ad4ab4 2026-11-09T14:01:36.257410608Z
browser_wizardapps-browser-engine-1 sha256:0dc9356ce1428962cddcf938dab712a8c56de79adc326f9138298f13df440071 2026-11-09T14:01:36.132434799Z
files_wizardapps-files-1 sha256:1b668429b3511ab407d8e00648891631b0b1a4d7e15e3ca70f38ab5b91ad4ab4 2026-11-09T13:59:19.025058393Z
files_wizardapps-files-engine-1 sha256:a469ea076d4a1b4b1d86a41d130f2f536cd9da996a2b1fb39c0d7635f9d89b9a 2026-11-09T13:59:18.887994769Z
notifications_wizardapps-notifications-1 sha256:1b668429b3511ab407d8e00648891631b0b1a4d7e15e3ca70f38ab5b91ad4ab4 2026-11-09T14:02:14.773747244Z
notifications_wizardapps-notifications-engine-1 sha256:4c599cf0818965782f93f652bd843e92714992e84d6b88ad17713dc0951cda1f 2026-11-09T14:02:14.935639798Z
runtipi sha256:e92d0564b04e08949a1ce84576da584b53ce00f6f3b27e3b7e79d1662063e7f8 2026-11-09T14:05:21.259463325Z
runtipi-db sha256:834a046089d76edd1d2e81c4741f3ad5d1853646ededc86c2708936aad31c1ed 2026-11-09T13:54:56.394652971Z
runtipi-queue sha256:8425b8435b0203e87292cf1a4a7e5f8108c610bbd8217f8cc952f43628b24987 2026-11-09T13:54:56.528875904Z
runtipi-reverse-proxy sha256:4cda3393930dceff030e144b46260e96e1337c9cfaa4fed81c90cb8f4d498f57 2026-11-09T13:55:11.723581185Z
runtipi-wizard-release-index-1 sha256:e92d0564b04e08949a1ce84576da584b53ce00f6f3b27e3b7e79d1662063e7f8 2026-11-09T14:04:17.979554938Z
secret-drop_wizardapps-secret-drop-1 sha256:1b668429b3511ab407d8e00648891631b0b1a4d7e15e3ca70f38ab5b91ad4ab4 2026-11-09T14:01:50.090217438Z
secret-drop_wizardapps-secret-drop-engine-1 sha256:29ebc6a7846e6036afc471dc6ddcee31a9cac3a0ce8f00d59cd1186c80c03302 2026-11-09T14:01:49.979550932Z
transcriber_wizardapps-transcriber-1 sha256:1b668429b3511ab407d8e00648891631b0b1a4d7e15e3ca70f38ab5b91ad4ab4 2026-11-09T13:58:56.247905863Z
transcriber_wizardapps-transcriber-engine-1 sha256:2163775b6df5e451a71200e8f675fed68dbd8ab184fc604453d549e486f22fd2 2026-11-09T13:58:56.128725249Z
wizard-agent-service_wizardapps-wizard-agent-service-1 sha256:d1b9282dad321b20321582f6d7c0e32c88f07330c6e82ff029bd952129424ee4 2026-11-09T13:59:27.371864347Z
wizard-chatgpt_wizardapps-wizard-chatgpt-1 sha256:1b668429b3511ab407d8e00648891631b0b1a4d7e15e3ca70f38ab5b91ad4ab4 2026-11-09T14:00:11.838269805Z
wizard-chatgpt_wizardapps-wizard-chatgpt-engine-1 sha256:abe83ddb8fe1e54347f94b5057740ba5da2309691f20b5692db476967638b445 2026-11-09T14:00:11.704142648Z
wizard-claude_wizardapps-wizard-claude-1 sha256:1b668429b3511ab407d8e00648891631b0b1a4d7e15e3ca70f38ab5b91ad4ab4 2026-11-09T14:01:03.894852634Z
wizard-claude_wizardapps-wizard-claude-engine-1 sha256:e839af7cdc32c875fcefec9189ae4e29509ea78b3b52d922416285c9e2eb81bb 2026-11-09T14:01:03.761801852Z
wizard-connection-router_wizardapps-wizard-connection-router-1 sha256:71e9721efc3904c76862b83613d6e88a1c5edff26432152f3727073fde417ecf 2026-11-09T14:02:53.28990954Z
wizard-ux_wizardapps-wizard-ux-1 sha256:b4785d8eef3d1aa9690fc0bafd7fa8de16da45aa67da99f291f26e4d81131efe 2026-11-09T13:59:38.647257159Z
wizard-voice-service_wizardapps-wizard-voice-service-1 sha256:a279274949c03bd8fe244f083f727e41f51d7040e58a48288089621f5ab27e89 2026-11-09T14:02:45.182116455Z
```
</details>

### Guardian readback on the guest (extra, outside the rig's gate)

| | GUARDIAN_ACT | marker line | wizard-guardian.timer | Troubleshooter status `guardian` |
|---|---|---|---|---|
| Before (0.3.134) | `0` | 0 | active | none (older App Manager) |
| After (0.3.143) | `1` | 1 | active | `{"act": true, "set_by": "default"}` |

`acts_after_upgrade: true`. The upgrade turned the old default into repairs on, with no owner choice invented (`~/.wizard-os/guardian.json` absent before and after).

Report files (private forum scratch, run `20261109T135337Z-0.3.134-to-0.3.143`, job heavy_0a9cc0dc): `report.md` sha256 `85782e50fb305c602e2afa4ce5af23ca1255f0b140f99a37c3055579996c5fc1`, `report.json` sha256 `3af726d4960a7f984200aa9d15f09766df8c75dd5f9aea5bb1b223d4f3c90497`, `guardian.json` sha256 `2e40b3e9324be124525e1f52f4190c6897be9a190198f70d8d7a90e3c0e56989`.

**Disclosed:** the 0.3.134 install used the public mirror; the 0.3.143 candidate was served by the rig from **wizard-os 83b5d8c (the head of PR #487)**, not fetched from the public mirror (`releases/0.3.143.json` sha256 `b958b531…`, identical to the file merged to main in 35c37a5 and to the mirrored file). A wrapper added only the guardian readback above; the rig ran unchanged.

## Not checked / caveats

- The rig has no Tailscale Serve, so the Troubleshooter reports `degraded` (not mounted on every shell address: Serve 501) before and after; known rig limit, not a release failure.
- The guardian was not made to repair anything on the rig (no injected fault); its acting code is unchanged Troubleshooter 9088a25, already on Stable in report-only mode.
- #548's owner-choice paths (quoted edits, unreadable file, overlapping installs) were proven by tests and the probe, not on the guest; the guest exercised the default path only.
- Not run: a fresh install of 0.3.143, real Tailscale/HTTPS/Serve, real chats and sign-ins, phones.
- Boxes on 0.3.26–0.3.31 set to Automatic skip a fast-tracked stable as `unpromoted` (Update now still works).

Rollback: point `releases/stable` back at 0.3.134 in both repos (it has a valid promotion record). A single box: `wam troubleshooter --report-only`.
