# Release 0.3.33: first-run Setup on fresh boxes (demo-box evidence, 22 Oct 2026)

0.3.32 plus the Agent Service at official main `634fe96` (`3c45698` + wizard-agent-service #90). It is on `latest` only, and `stable` stays 0.3.32.

## What failed

On a fresh install of stable 0.3.32 on the demo box ([promote-0.3.32.md](promote-0.3.32.md), Test B), first-run Setup never opened:
- `/wizard/v1/setup` returned 404.
- Opening Setup by hand showed "This Wizard doesn't have Setup yet".

The pinned Agent Service `e7bfd6d` is older than the Setup API.

## Fixes (each with a regression test)

| Change | Test | Negative control |
|---|---|---|
| Agent Service pin moves to official main (adds #24 Setup API, #43 ui-preferences) | n/a (pin) | n/a |
| wizard-agent-service #90: the Setup host guard also allows the https host of the app that `provides: shell` in the read-only `apps.json`. Without it, a fresh box (no `settings.json` yet) answered 403 `host_not_allowed` through Tailscale Serve. Found on the demo box with a `3c45698` candidate. | `tests/phone-setup.test.ts`, 2 new cases. Other apps' hosts, plain-http views and forwarded attacker hosts stay 403. | the new case fails on the old `service.mjs`. Full suite: 1044 passed, and CI is green. |
| wizard-os #153: from 0.3.33 on, `check_release.py` fails a release whose Agent Service lacks a stable `/wizard/` route from `spec/AGENT_SERVICE_API.md` | `ServiceRoutes` unit tests | 0.3.32's pin fails it (5 setup routes and chats-views). |

## Release

- wizard-os #154 (merge `b053eda`): `releases/0.3.33.json`, sha256 `ae75530ccc94323b701fbf34cbb93b1ca12e347f51ab450df1a936be6902aa3b`. WAM #162 mirrors it byte for byte onto `latest`.
- Agent Service image: `ghcr.io/humanitylabs-org/wizard-agent-service:sha-634fe96…` @ `sha256:51b19dd831994af016bee0de48d0e3e1161aaa8d9947cf073ab6007b65e8277a` (amd64+arm64, Publish run 39723089025). `check_release` passes, including the new route guard.

## Demo box: clean fresh 0.3.33 from the public installer (04:50–05:05 UTC)

The box was wiped first. Then, as root: `WIZARD_RELEASE=0.3.33 bash -s start` with the public `os.sh`.

| Check | Result |
|---|---|
| Install | done, exit 0. Outcome `ok`. `release.json` reads 0.3.33 `pinned`, 25/25 ok. Troubleshooter `ready`. |
| First-run Setup | The shell logs `first_run:true` → `open`. The Setup window opens by itself and shows "One thing to set up for now · Use Wizard on your phone", and the app POSTs `seen` (`first_run` is then `false`). |
| Settings redesign | Desktop has two panes, and all 6 category pages render. Phone shows the short index with summaries. No 4xx on any Agent Service route, and the only 404s are `ux-version.txt` and the phone shell's optional `/api/system/*` probes, as on 0.3.32. |
| Troubleshooter | 200 with "All working". It opens as a hosted shell window. |
| Store | Status is complete. A Wisdom Get went `installed`/`running` in about 8s and flipped to Open, and Open rendered `/wisdom/`. |
| Host guard | Through Serve, Host `demo.<tailnet>.ts.net:8796` returns `{"first_run":true,…}`, while Host `attacker.example` returns 403 `host_not_allowed`. |

The same checks also passed on an installer rerun from 0.3.32 to the 0.3.33 file before the cut. That run served the same bytes from a local `WIZARD_RELEASE_BASE`.

Screenshots in the operator cache: `demo-retest-fresh0333pub-*`, `demo-retest-fresh0333-{setup-desktop,settings-desktop,settings-phone}.png` (vision-checked).

## Classification: soak, not fast-track

`e7bfd6d..634fe96` also carries Agent Service features:
- #68: default agent, with a one-time store migration that keeps `.bak` baselines;
- #42: multi-account; account changes stay off unless `WIZARD_ACCOUNT_CHANGES=1`;
- #72: Chats install;
- #71: own app screens;
- #87: restricted heavy relay, off by default;
- fixes #63, #61, #73, #76, #78, #86.

Under DECISIONS #82 this is not a fix-only release. It keeps the 72h soak on `latest`, and it needs the demo-box upgrade test from 0.3.32 before a plain `promote 0.3.33 --from 0.3.32`.
