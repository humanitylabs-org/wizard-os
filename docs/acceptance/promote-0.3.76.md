# Promote 0.3.76: Troubleshooter one-tap screen and app picker long-name fix on Stable

## Decision and scope

Miguel (29 Oct 2026): "ship as a fix PR". Owner rule: any fix is fast-tracked to Standard (Stable); features soak on Latest. Classification: **fix** (`--fast-track --classification fix`).

0.3.76 is Stable 0.3.74 plus exactly two pin changes (cut in wizard-os #319):

| Component | 0.3.74 | 0.3.76 | Change |
|---|---|---|---|
| Wizard UX | `db361987` (main) | `25f28781` (`release/stable-onboarding`) | db361987 + wizard-ux #726/#730 via Stable PR #729: app picker labels with a 13+ character word get `.nm.long` (token size, tile padding) so "Troubleshooter" shows whole instead of "Troubleshoote / r"; labels hyphenate instead of dropping a bare letter. Failing-first test `tests/launcher-long-names.test.mjs`. `git diff db361987 25f28781`: desktop.js, desktop.css, styles.css, the new test. |
| Troubleshooter (host tooling) | `c1b4c43` | `3e56f66` | #14 one step-by-step reconnect path for an expired AI sign-in; #16 past repair chats kept; #17 background reply probes off unless opted in; #18 Tinfoil check fix; #20 James's one-tap screen back, following the selected skin; #21 one-sentence status line + recent chats; #22 Check again, CSP allows the shell's same-origin kit/skin stylesheets; #23 `ts-` class prefix so skin stylesheets cannot restyle the page. |

Main's Wizard UX is not used: it carries 27 feature PRs since Stable (release train, 0.3.75 on Latest for the soak). Latest testers get the same Troubleshooter pin in 0.3.77 (0.3.75 runtime pins unchanged otherwise; its UX main 91218c83 already contains #726), cut onto `latest` in this PR so Latest never trails Stable.

Ride-alongs: the Troubleshooter's #16/#20–#22 change its screen (layout, sessions). Miguel classified them as fixes (the over-designed #15/#16 screen was reverted to James's original one-tap design). Risk: page-only for the screen; #17 lowers background model usage; no new permissions or routes.

## Published pins

- Wizard UX image `ghcr.io/humanitylabs-org/wizard-ux:sha-25f2878198d64ebb7c936138c568b5ae433a9452`, digest `sha256:bac458438d3e9811d526873a78433c57df0c23cffeeff32d1a420c9519fe38e0` (amd64 + arm64), workflow_dispatch run 40835930467 on `release/stable-onboarding` with `expected_sha`: validate, publish, attest, finalize, anonymous-pull all success.

## Verification

- `tools/check_release.py releases/0.3.76.json` and `0.3.77.json`: ok. `promote_stable.py check`: channels ok. wizard-os tools suite 244 OK (local).
- Wizard UX #729: CI green (build, smoke, regression, reuse, review, shared-features); full suite 1377/1377; the new test fails 2/2 on db361987 and passes on 25f28781; style check 0 errors.
- Troubleshooter main 3e56f66: 55/55 node tests and the hermetic browser QA 53/53; live on the owner box (oscar-main) in the Wizard shell in all 11 skins × desktop/phone with no element painting against the skin's light/dark scheme.

### Upgrade test 0.3.74 → 0.3.76, 29 Oct 2026 UTC

Disposable KVM guest (`tools/acceptance/upgrade-rig/kvm_upgrade.py`, Ubuntu 24.04, golden Hermes v0.22.5), public os.sh (sha256 `fa9271d0…`) for both runs. Install of 0.3.74 from the public mirror; upgrade with `WIZARD_RELEASE=0.3.76 WIZARD_STRICT=1 WIZARD_RELEASE_BASE=http://10.0.2.2:18977` serving this repo's `releases/` at the cut commit (disclosed: the candidate was not yet mirrored).

- 0.3.74 install: done (551 s).
- Upgrade to 0.3.76: done (154 s); release.json 0.3.76 pinned, 27 checks, 0 failed, including `image wizard-ux: sha256:bac45843…` and `default app source shell: 25f28781…`.
- After: Hermes API /health 200, gateway active, shell 302, `wizard doctor` FAIL 0, `wam doctor` FAIL 0; Hermes config.yaml/.env/SOUL.md byte-identical.
- Report: `report.md` sha256 `4e8b4533ef24b7fdadea2026c8a27d10b8cd965e0d591ca695fa5f38163b5384`, `report.json` sha256 `5ce461b9ce6c45bd7e392a6b510bf12a120763bc26952d914e5537d91d5eda87` (private scratch, run 20261029T073652Z-0.3.74-to-0.3.76).

## Not checked / caveats

- The rig has no Tailscale Serve, so the installer reports the Troubleshooter as running but not mounted on every shell address (known infrastructure limit of the rig, not a release failure). The exact installed Troubleshooter commit was not read back on the guest; 3e56f66 runs on the owner box.
- Boxes on 0.3.26–0.3.31 set to Automatic skip a fast-tracked stable as `unpromoted` (Update now still works). Hand-installed Troubleshooters (units without the `wam troubleshooter` marker) are left as they are.

Rollback: point `releases/stable` back at 0.3.74 in both repos (it has a valid promotion record).
