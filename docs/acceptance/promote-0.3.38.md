# Promote 0.3.38: installed upgrade from stable 0.3.36

## Decision and scope

Miguel authorized the private-launch release and tested-stable promotion. This uses DECISIONS #93's feature fast-track, not a falsely fix-only classification: the 0.3.36 → 0.3.38 UX range includes the shared app kit (#382), My skin launch (#377), and chat search/new-chat adjustment (#433), in addition to objective fixes. Alongside chat-first launch changes its default while leaving VM onboarding unchanged. There are no new owner-data migrations, deletion, or Hermes updates. Risk: shared shell behavior and installer reconciliation; exact-image upgrade and both browser shells were exercised below. No other installation was changed.

## Published pins

Manifest `releases/0.3.38.json` SHA256:
`999fc2a33e0534478e23172d899fd4aa8bc1281724815bb62c6c42004f0862bf`.

| Component | Commit | Public image digest |
|---|---|---|
| App Manager | `d926eec199c6440249c799677ff87585ece76a96` | `sha256:07df73e79ee3bea5465cd27d90f99191317075e7a669678a8d066c51473d4116` |
| Agent Service | `6424db094d03af255b7ec35cb731bfc0087c61ef` | `sha256:840a371ca864755e01490ab7e5e31a1fc8bd0d698637ecd7e9b1523b3419a9b8` |
| Wizard UX | `3965b609e447dbb7fd73b1afc628d86f962e1f93` | `sha256:7add31c745aa5ea9aef60de453f85be99a781a584d7bf671a04c3970d4027e61` |

App Manager's image remains the official db4325a build: online `check_release.py` verified no image inputs changed through d926eec. Service publication [40088580225](https://github.com/humanitylabs-org/wizard-agent-service/actions/runs/40088580225), including anonymous amd64/arm64 pulls, and UX publication [40087814055](https://github.com/humanitylabs-org/wizard-ux/actions/runs/40087814055) succeeded. Service #149 was closed, not reopened: #150 superseded it; exact final-head comparison found omitted helper guards, fixed in #151 (three regressions fail against #150 and pass after restoration, 42/42). Service #151 main Quality and CodeQL passed.

## Installed upgrade — 24 Oct 2026 UTC

Existing alongside demo started on stable **0.3.36**, with a host Hermes and existing sessions. Used the published supported installer, not hand-edited Compose or a locally built candidate:

```sh
curl -fsSL https://aiwizards.com/os.sh -o os.sh
WIZARD_RELEASE=0.3.38 WIZARD_STRICT=1 bash os.sh start
bash os.sh status
wizard doctor
wam doctor
```

Installer completed (`state=done`, exit 0). Release readback recorded `release=0.3.38`, `status=pinned`, `install_rc=0`; every core/default-source check passed, including the exact three digests above. Existing Tailscale was recognized, not re-enrolled. No wipe or VPS reboot. Only the installer's normal deferred Hermes restart occurred. `wizard doctor` and `wam doctor`: all PASS, live bridge returned 21 gateway tools. Actual service configuration: user `0:0`, supplementary group `["1000"]`, cap_drop `["ALL"]`.

Preservation probe compared before/after: identical boot ID, identical config.yaml/.env/SOUL.md hashes, identical Hermes source revision, all three prior session IDs retained, identical pre-existing session-file hashes. All five assertions passed.

## Real installed HTTP and browser proof

Through the real demo HTTPS Serve origin, no mocked upload/transcription services:

- Legacy attachment POST: **201**, 65,590 bytes, byte-identical content GET. SHA256 `b0be764821af261b4f3d31ad4531f99a02624b9878f8ea787080f5509e12a612`.
- Resumable attachment create **201**, two PATCH chunks **204**, offset GET after each chunk, complete **200**, byte-identical content GET with the same hash.
- Raw WAV `/wizard/voice/transcribe`: **200**, actual local faster-whisper-small transcription of the public Whisper JFK test sample, correctly including “ask not what your country can do for you”.
- Multipart `/wizard-os-home/api/transcribe`: **200**, same real local speech model and expected transcription. This verifies real multipart upload, not microphone hardware capture.
- Live, unmapped-API browser sessions at phone 390×844 and desktop 1440×900: alongside quiet-launch marker, no auto Setup iframe or tour, ready phone checklist, optional Setup opens, no page errors, existing Ready conversation retained, no empty Yesterday/Past week groups. Screenshots visually inspected.
- Separate browser regression against the installed shell assets, with explicitly synthetic history/setup APIs: **34 assertions** across phone/desktop × empty/populated histories; populated Yesterday/Past week remain visible, optional Setup and phone tour work. This fixture test is not claimed as real historical owner data.

## Tests and audit receipts

Online `tools/check_release.py releases/0.3.38.json`: release ok (catalog DRIFT informational; installed sources match pins). `promote_stable.py check`: channels ok. OS unittest suite: 154 run, OK, 19 skipped. WAM release pins/split/public metadata/channel tests: 66 passed. WAM mirror #199 main test/CodeQL passed; OS cut #196 main contracts passed.

Receipts retained by release operator (SHA256):

| Receipt | SHA256 |
|---|---|
| installed-upgrade.log | `a17750199e14f2c0af5b78b519679a03e69673d8dfc13f2fd3be1db17cbb6e08` |
| installed-release.json | `a99512ddf94dd6ac3003934ded6187ee8614cff201fc5f508e247f73fd628afc` |
| preservation.json | `1003159ad6f59eb6fbd9b79ba5d468ddd381adadbdcffd550d3a358b57f2fde8` |
| http-upload-voice.json | `9b9a5c850d75ebe03c73719736edadc847502c9974249a74202f3b55b38328b6` |
| browser-live.json | `525ec231e048241cd8421ad99342a589b1f8d2311561b8049d10e2807f8e339d` |
| browser-history.log | `5d97fa28e995c1199fe14d8ae1b43475431370e3ad460aa96a228f1bc045015a` |
| doctor.log | `438b58e2df5170126927be95c0955a4a0c94289f7c107fd5f27adae8e8d05c14` |

## Not checked / remaining caveats

No fresh-install box was available without wiping an existing installation; no fresh wipe was attempted. No physical phone microphone or native app lock-screen capture was tested. The older broad qa-setup-app.cjs has pre-existing greeting/Grove-selector failures on baseline and candidate; the focused replacement launch regression is green. Existing dependency security advisories are not resolved by this launch release. Old Automatic updaters predating feature fast-track support may skip this promotion; explicit Update now/installer remains available. Two small synthetic binary upload proof files remain on this demo for independent readback; they contain no owner content.
