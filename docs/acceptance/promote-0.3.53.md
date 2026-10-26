# Promote 0.3.53: installed upgrade from stable 0.3.39

## Decision and scope

Miguel (@mistermizel, non-author admin) authorized shipping the corrected onboarding fix straight to Stable ("push improved onboarding directly to stable", 26 Oct 2026) and approved these release PRs. This promotion uses the DECISIONS #82 fix fast-track (`--classification fix`).

0.3.53 is Stable 0.3.39 with **only** the wizard-ux onboarding fix. Compared with `releases/0.3.39.json`, the runtime pins that change are `components.wizard-ux`, `images.wizard-ux` and `default_apps.shell` (all to the same source). Everything else is metadata (`version`, `name`, `date`, `about`). App Manager, Agent Service, Hermes and every other default app are unchanged. No trunk feature bundle rides along: no backup/restore/Undo, Spaces, Android or other unaccepted Latest features. No migrations, no owner-data deletion, no Hermes update.

The UX source is the reviewed Stable-onboarding maintenance branch, not trunk. It contains the 0.3.51 alongside/desktop first-message orientation, replay, Settings/Esc handoff, slow-launch guard, readable WebKit copy, responsive Done and reachable Skip, plus the UX #535 safe-area correction (resolved safe-area padding and an in-flow spacer, so Done content stays scroll-reachable above the home indicator).

## Published pins

Manifest `releases/0.3.53.json` SHA256 `53bcbd64c56967add1bf70634c6139e7e022d28ccda39f36da58748eba301bcb` (canonical wizard-os #242, merge `71c9c5e09cdbcb10ff130ac219ba3ab9f71fe0a3`; byte-identical WAM mirror #239, merge `0086de3c1d908481ce9b4cde6a9a5b63ad8670f2`).

| Component | Commit | Public image digest |
|---|---|---|
| Wizard UX (changed) | `26c3b20fa484b79cb1b1836bfd05064195659360` | `sha256:03a93684174475546f38bcabd246894cecbde09bc6c78e4ae1178ed0045d91d9` |
| Agent Service, App Manager, Hermes, other default apps | unchanged from 0.3.39 | unchanged from 0.3.39 |

The official hosted maintenance publish run [40264433758](https://github.com/humanitylabs-org/wizard-ux/actions/runs/40264433758) built, signed, finalized and anonymously pulled amd64 and arm64.

## Installed upgrade, 26 Oct 2026 UTC

The authorized demo (alongside install on stable **0.3.39** with host Hermes) was upgraded by the supported installer using `WIZARD_RELEASE=0.3.53` and `WIZARD_RELEASE_BASE` pointed at the WAM mirror PR head `95495bf8069a76eaf2ceff040ce98e874b0728cd`. The anonymous raw manifest there was byte-identical to canonical before execution. The override was needed only because the mirror was not yet on WAM main. The mirror has since merged with the same bytes.

- Installed receipt: `release=0.3.53`, `status=pinned`, `install_rc=0`, all **23** checks true. Outcome `ok`, mode alongside, no failed or degraded items.
- The running UX container is healthy, and its RepoDigests match `sha256:03a93684…d91d9` exactly.
- `wam doctor` and `wizard doctor` both passed, including a real `wizard_apps` request through the bridge.
- The demo Hermes `config.yaml`, `.env` and `auth.json` SHA256 values were identical before and after. Credentials were not printed or copied between hosts.
- Actual installed **Chromium and WebKit, on the phone shell and the real desktop shell** (four cases) passed first launch, per-step Skip, exit, quiet reload, deep-link replay, visible Help replay, microphone-denied typing, readable instructions and no page errors.
- Both engines passed simulated native insets and rotation: 402×874 (top 59, bottom 34), 844×390 (top 0, bottom 21), 844×390 (top 59, bottom 34), then back to portrait. The last Tap row scrolls clear of the home indicator, and the real Skip tour control was clicked. The WebKit short-landscape screenshot was inspected visually.
- Real model inference succeeded from first-run onboarding on both phone and desktop. The returned assistant history contained the requested exact replies, not just a Sent marker. No owner conversations were used.

## Receipts

| Receipt | SHA256 |
|---|---|
| installed0353-release.json | `2814d5c086a70b36de3ab1e267f0a96b4db262afb3c1e47386605148fadda4e3` |
| installed0353-install.log | `d2b974d01183e2ec5fc9d318d9c1a62d0cee15e57aefb26f3340741720d70cb6` |
| installed0353-doctors.log | `0d5587b024d0aa49b136ad5b58c96ca03fc7ea25ff311c0e36c4b981e4a23a13` |
| installed0353-chromium/matrix.json | `bc88c0bc92090f6a664637e17a378116e7271bffb68ea0e1c0508af820d4e3ef` |
| installed0353-webkit/matrix.json | `eeb34e394ab8492a8dbe3f8e02af920d4b502373ff0733456d3a36f513e2af05` |
| installed0353-chat/real-chat.json | `2d9a5ffc1b4854e67f0e1a89aee8d3bdbfe24d140d7696032c0c370b6af47503` |

Public acceptance comments: wizard-os#242 (issuecomment-6407770372) and wizard-app-manager#239 (issuecomment-6407770762).

## Not checked / caveats

- A fresh 0.3.53 install was not run before promotion. Earlier fresh-install evidence for 0.3.51 is not counted for this release. The owner's fresh Telegram install test on the reset demo comes next.
- No physical microphone, real iOS safe-area device, Telegram webview or Add to Home Screen acceptance is claimed.
- Boxes on 0.3.26–0.3.31 set to Automatic skip a fast-tracked stable as `unpromoted` (Update now still works). 0.3.25 boxes take it on the next nightly run.
- Latest continuity (wizard-os #240 / WAM #237) is separate and is not promoted here.

Rollback: point `releases/stable` back at 0.3.39 in both repos (it already has a valid promotion record).
