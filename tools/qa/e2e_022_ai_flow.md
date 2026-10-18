# Release 0.2.2 AI-workflow acceptance (`e2e_022_ai_flow.py`)

Owner-level AI acceptance on **one** retained AMD64 guest, through the real
installed Wizard UX. Runs after `e2e_022_ui_proof.py`. Default guest
`fresh-022-candidate-amd64` (`--vm alongside-022-amd64` allowed). Thales only,
admitted through the heavy queue by the acceptance owner.

## Command

From a detached checkout of the pushed commit
(`/Volumes/ThalesMedia/wizard-os/e2e-022/ai-flow-source`):

```sh
/opt/homebrew/bin/python3 tools/qa/e2e_022_ai_flow.py \
  --root /Volumes/ThalesMedia/wizard-os/e2e-022 \
  --node /opt/homebrew/bin/node \
  --playwright-module /Volumes/ThalesMedia/wizard-manager/qa/node_modules/playwright \
  --vm fresh-022-candidate-amd64 --wait-minutes 75 --poll-seconds 20 --idle-grace-minutes 30
```

Suggested queue timeout: 10800 s (start + preflight ≈ 15 min, chat ≤ 20 min,
DeFleur ≤ 75 min, final readback/Files/stop ≈ 20 min). A missing DeFleur install
adds up to 40 min. Exit 0 = every step passed; 2 = a step failed;
`RECEIPT=<path>` is printed last either way.

Local checks (no VM): `python3 tools/qa/test_e2e_022_ai_flow.py`,
`python3 -m py_compile tools/qa/e2e_022_ai_*.py`, `node --check tools/qa/e2e_022_ai_browser.cjs`.

## Flow

1. Refuses unless macOS, root `/Volumes/ThalesMedia/**/e2e-022`, named guest,
   clean tracked source, and guest **Stopped** (refuses a Running guest). Takes
   `ui-proof.lock` + `ai-flow.lock`. Applies the Lima port-forward ignore rules,
   starts the guest, and stops it in `finally` (force-stop fallback), reading
   back `Stopped`.
2. Guest preflight (`e2e_022_ai_guest.py preflight`):
   - marketplace ready;
   - `GET 127.0.0.1:8795/api/accounts` inside the guest, read once after it
     answers. Asserts Claude `status == connected`. The AI Accounts page is never
     opened, captured, or forwarded to the host;
   - DeFleur: skipped if `apps.json` shows 0.7.0-testing @ `76c544a…` and the one
     running container's RepoDigests include `sha256:d837622c…`. Otherwise it runs
     the real `wam install defleur-video` and reads back version, commit,
     publisher, digest, shared `/media` mount and health;
   - image digests (RepoDigests + arch) for the hermes-agent, wizard-ux,
     wizard-agent-service and defleur-video containers, with the Hermes digest
     compared to `sha256:ac89f5f9…`;
   - synthetic clip: reuses the newest valid 8–12 s
     `media/Videos/{ui-proof,ai-flow}-*/release-acceptance-source.mp4`.
     Otherwise it generates one the same way the ui-proof runner does;
   - before snapshot: Hermes `skills/` (path + sha256), and `config.yaml`
     `model.provider` / `model.default` only. `.env` and `auth.json` are checked
     for existence only.
3. A process-owned SSH tunnel forwards only the Wizard shell port. Playwright
   (`e2e_022_ai_browser.cjs`, phase `ai`, mobile 412×892):
   - **Chat:** New chat, model chip, picker. The short list has one row per
     family, so its "Claude Opus" row may be a different Opus id. If the chip
     title isn't `claude-opus-5-5` afterwards, the runner uses **More models**
     and the exact catalogue row (`WosModels.options` index =
     `sheetHtml(all)` order). If a pointer target is covered, the runner records
     what covers it and activates the target with keyboard focus + Enter.
     If the picker can't select the model at all, the fallback uses the UI's
     own routes (`POST /wizard/hermes/api/sessions` +
     `POST …/sessions/:id/model {model, provider, require_model_lock}`) and
     records `method: route-fallback`. After that it types
     `Reply with exactly the word READY.` and sends. Asserts:
     - the captured outbox `POST /v1/runs` carries the required model/provider
       with `require_model_lock: true`;
     - an assistant reply arrives;
     - the service's `GET /api/sessions/:id` reports `claude-opus-5-5` (or
       `…[1m]`) on `claude-subscription-directsdk-experimental`.

     It takes screenshots, then opens the thread and presses Back once
     (must stay on Wizard). A desktop context reads the thread back and also
     does Back.
   - **DeFleur:** guest media snapshot, then a NEW chat on the same model with
     exactly `edit <clip> from my Files with DeFleur`. `<clip>` is the file
     name, plus its folder only when the name is ambiguous. Every 20 s it records
     the session/run status and the count of new videos.
     - If the agent goes idle with a question, it answers once:
       `Trim the pauses and add captions, then save it to my Files.`
     - It stops when a new video exists and the agent is idle, or on
       approval-request (never approved), failure, the idle grace period with
       no output, or 75 min.
     - Then it opens the thread, takes a screenshot and presses Back once.
4. Guest final:
   - Media diff before/after under the shared media root. Every new/changed
     video gets size, sha256, ffprobe streams/duration and a full decode. Passes
     only if one is a valid video (duration > 0, video stream) whose hash
     differs from the source. The runner never creates the output.
   - Skills diff. Each new/changed `SKILL.md` that mentions DeFleur is checked
     as a **pointer**: it must not be identical to the installed DeFleur app
     skill and must be ≤ 60 lines. It fails if it shares ≥ 5 substantive lines
     (≥ 40 chars), or ≥ 20 %, with the app skill, and it must reference the
     app, its MCP, or its skill. No new DeFleur skill = pass ("no copy written").
   - Model readback: config.yaml model keys before/after, plus Hermes
     `state.db` session model columns, read-only.
5. Phase `files`: `?open=files`, walk to the output's folder, screenshot,
   Back once. It must stay on Wizard, with Files still open for a nested folder.

## Evidence

`<root>/evidence/ai-flow-<UTC>/` (0700, files 0600):
- `receipt.json`: host, `source_revision`, source hashes, argv, guest, images,
  clip, `defleur_message`, step verdicts `0-preflight`…`5-accounts-page-never-opened`,
  `output_video`, `skills_diff`, `model_readback`, screenshot hashes, cleanup;
- `guest-*.json`;
- `browser-ai.json` and `browser-files.json`, which contain request
  route/model fields only, never bodies beyond the typed text;
- PNGs.

Every receipt passes through a key/value sanitizer. Raw child stdout/stderr is
never stored.

## Not asserted

- READY being the *exact* reply. It is recorded as `reply_is_exactly_ready`;
  the assertion is that a reply arrived on the right route.
- That the edit matches the request (pauses trimmed, captions burned in).
- Hermes `config.yaml` default changing. A per-chat pick doesn't set the
  global default; before/after are only recorded.
- Physical Android. AI Accounts sign-in itself. The alongside guest, unless
  chosen with `--vm`.
- Lines a pointer skill paraphrases from the app skill below the 40-char /
  5-line threshold.
