# Promote 0.3.39: installed upgrade from stable 0.3.38

## Decision and scope

Miguel authorized releasing and promoting wizard-ux #456. It changes the default first-run tour for everyone: the Command beat is gone (Talk → Hide → end card), each beat has its own "Skip this step", "Skip tour" still ends the whole tour, and a hold during the tour is steered back instead of advancing. Because it changes a default, this promotion uses the DECISIONS #93 feature fast-track (`--classification feature`), not a fix classification. Per DECISIONS #96 clause 4, the cut, mirror and promotion PRs request a non-author review (defleur-agents).

0.3.39 is 0.3.38 with one pin moved: wizard-ux `3965b609` → `c8433e34` (the #456 merge; `default_apps.shell.commit` follows). UX ride-alongs on main since 3965b60 (first-parent): #451 and #455 (home-screen pinning from the New desk grid and Desks), #449 and #418 (document-scrolled Chats reading place, no duplicate Sending bubble or scroll leap), #431 (quieter Change Wizard on the Reach screen). App Manager, Agent Service, Hermes and default app pins are unchanged. No migrations, owner-data deletion or Hermes update.

## Published pins

Manifest `releases/0.3.39.json` SHA256 `6aa5201e633339f71b3854c13dff30189d0a03d57799854713c1455e19a60243` (canonical wizard-os #203, byte-identical WAM mirror #202).

| Component | Commit | Public image digest |
|---|---|---|
| Wizard UX (changed) | `c8433e348f1e715a5652089411f11d401a7860bc` | `sha256:57bb8e26154aeec5a1316497ab6e22570858a842b6e8ecda7890568ea594ee19` |
| Agent Service | `6424db094d03af255b7ec35cb731bfc0087c61ef` | `sha256:840a371ca864755e01490ab7e5e31a1fc8bd0d698637ecd7e9b1523b3419a9b8` |
| App Manager | `d926eec199c6440249c799677ff87585ece76a96` | `sha256:07df73e79ee3bea5465cd27d90f99191317075e7a669678a8d066c51473d4116` |

UX publish run [40102061327](https://github.com/humanitylabs-org/wizard-ux/actions/runs/40102061327): validate, publish, attest and anonymous-pull all succeeded; `docker buildx imagetools inspect` shows amd64 and arm64.

## Installed upgrade — 24 Oct 2026 UTC

The demo is an existing alongside install on stable **0.3.38**, with a host Hermes and three existing sessions. It was upgraded with the published supported installer, not with hand-edited Compose or a locally built image:

```sh
curl -fsSL https://aiwizards.com/os.sh -o os.sh   # sha256 8080457e…a8bed7c4
WIZARD_RELEASE=0.3.39 WIZARD_STRICT=1 \
  WIZARD_RELEASE_BASE=https://raw.githubusercontent.com/humanitylabs-org/wizard-app-manager/9afb926a5d5a8d394a3b45fe74197c57aee238d9/releases \
  bash os.sh start
bash os.sh status
wizard doctor; wam doctor; wam updates
```

`WIZARD_RELEASE_BASE` pointed at the WAM mirror PR head (#202 `9afb926`), whose `0.3.39.json` is byte-identical to canonical. That was needed only because the mirror was not yet on WAM main. The installer did the rest exactly as it would from main.

- Installer `done`, outcome `ok`, no failed or degraded items. Release readback: `release=0.3.39`, `status=pinned`, `install_rc=0`, mode alongside. All 23 checks passed (14 core), including the UX image `sha256:57bb8e26…` and default-app shell source `c8433e34`.
- `wizard doctor` and `wam doctor`: exit 0, 27 PASS, no FAIL or WARN. The bridge served 21 gateway tools. `wam updates`: installed 0.3.39, update_available false.
- Preservation (before vs after): the boot ID, the config.yaml/.env/SOUL.md hashes, the Hermes source commit, the session-file hashes and all three session IDs are identical. Only the wizard-ux container image changed (7add31c7 → 57bb8e26); Agent Service is unchanged. No wipe and no reboot; the only restart was the installer's normal deferred Hermes restart.

## Live installed shell proof

Checked through the real demo HTTPS Serve origin (`demo-2.tail6adf1a.ts.net:8796`):

- The served `core/tour.js` SHA256 `43f83ea3…f43e204` is byte-identical to `web/core/tour.js` at c8433e3. It contains "Skip this step", and its beats are Talk, Hide and Done. The 0.3.38 file had a `Command` beat and no per-step skip.
- Playwright Chromium, phone 390×844 (touch) and desktop 1440×900, with every non-GET request stubbed so the demo was not written to. **15/15 passed:**
  - The tour beats are Talk, Hide, Done; beat 1 reads "1 of 2 · Talk" with two progress dots, "Skip this step" and "Skip tour".
  - No beat mentions a command. "Skip this step" goes Talk → Hide → end card without ending the tour.
  - The end card shows only the Tap and Swipe ↓ glyphs (no Hold); tapping it finishes and remembers.
  - "Skip tour" from beat 2 ends the tour. No phone page errors.
  - desktop.html returns 200, shows no phone tour overlay and has no page errors.
- Screenshots were inspected visually. In the phone tour, the "Skip tour" pill sits over the dimmed header icons. This is cosmetic, and the pill is unchanged by #456.

## Tests and receipts

- Online `tools/check_release.py releases/0.3.39.json`: release ok. The catalog DRIFT lines are informational and are the same kind as 0.3.38's.
- `promote_stable.py check`: channels ok. OS unittests: 159 run, OK, 19 skipped.
- WAM release tests (channels, pins, split, public metadata, bootstrap, index permissions): 79 passed.
- wizard-ux #456 itself: npm test 733/733; tour-skip-step 10/10 (main before it: 1/10); qa-tour 38/38 at phone and desktop.

| Receipt | SHA256 |
|---|---|
| installed-upgrade.log | `091eec4931182b9cb1f52fe0419c867875ceedf13c10047193f83e88e3faa8d3` |
| installed-release.json | `b7ba57c07cceeeb29b4892ac36ded2a6789c3280e54509c672632cc58117ade5` |
| preservation.json | `a3555799b216042a4a7705c9048e89cb0a7a474af19585e33a50ff83166aa6ce` |
| doctor.log | `4dffb5b3bb32c024d7a7f08c18fcf53fccf3e92e37b2a690146771e8fc67eeeb` |
| browser-tour.json | `4a7ff32e52ede7c26f0dcb50ff7024e8b4a9978426ef2f6eb20c8a417ebff791` |
| served-tour.js | `43f83ea3d96630033f8ef0a38492b10c345ae4ed2c4d7741757595a03f43e204` |

## Not checked / remaining caveats

- Older Automatic updaters accept only fix fast-tracks (WAM #200, open P1), so they will not take this feature promotion automatically. Update now and the installer both work. The demo was upgraded with the installer, not with Automatic.
- No fresh-install box was available without a wipe, so no fresh install was tested. The real voice beat was not driven with a physical microphone; the browser check used Skip this step, and Talk/Hide gesture handling is covered by #456's qa-tour.
