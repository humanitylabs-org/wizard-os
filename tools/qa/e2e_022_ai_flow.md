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
     - If the agent goes idle with a question or asks for an OK (DeFleur asks
       before cutting and rendering), it answers like an owner, at most twice:
       `Yes, go ahead with those cuts and captions. Skip the motion graphic.
       Render it and save it to my Files.`, then `Yes, go ahead and render it
       to my Files.` A tool-level approval gate is never approved.
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

## Alongside: owner Claude, sign-in, then the same AI flow

These are **source-only handoff commands**, not proof of a live pass. Both jobs
require the retained guest to begin **Stopped**, and stop it afterwards. They
must not overlap another owner of this guest. They never operate on the fresh
guest when `--vm alongside-022-amd64` is selected. Submit through the existing
Thales job admission path; do not start them from Telos.

Both jobs use cwd:
`/Volumes/ThalesMedia/wizard-os/e2e-022/ai-flow-source` at the pushed detached HEAD.

### A. Owner sign-in hold (timeout 10800 seconds)

```sh
/opt/homebrew/bin/python3 tools/qa/e2e_022_signin_window.py hold \
  --root /Volumes/ThalesMedia/wizard-os/e2e-022 \
  --vm alongside-022-amd64 --guest-port 8797 \
  --node /opt/homebrew/bin/node \
  --playwright /Volumes/ThalesMedia/wizard-manager/qa/node_modules/playwright \
  --https-port 18449 --relay-port 18450 --tunnel-port 18451 --minutes 90
```

This is a local copy of the audited sign-in runner, **not a modification of
os-runner**. Guest port defaults to 8795 for the existing package page; alongside
requires 8797 and `hold`. The relay's owner identity check, path/header allowlists,
non-body/query/cookie logging, handler ownership check, Serve snapshot comparison
and single-handler removal are unchanged (unit tests fingerprint their ASTs).
443, 8447 and 8847 are explicitly forbidden as the test HTTPS port. There is no
`serve reset`. Expiry closes only this handler, tunnel, one-shot container and VM.

Before exposing the page, `hold` runs `e2e_022_alongside_claude.py setup` and
`signin-page` inside the guest as its login owner. Afterwards it runs
`signin-page --stop`, including failures after an attempted container launch.
The hold's `/api/accounts` status check targets the **one-shot owner directory**,
not the app's shared named volume. It reports connected, expires, or is stopped;
expiry is not evidence of a successful sign-in. The emitted receipt names the
window expiry and run directory. Its existing rendering check precedes the
interactive sign-in window and does not capture the OAuth code/login form.

`setup`:
- Requires the existing isolated guest marker, non-root owner, stock launcher and
  an existing Wizard link. UID/GID are discovered at runtime, **not assumed 501**.
- Installs `~/.local/bin/claude` **2.1.296**, authenticating the official npm AMD64
  archive against the **same SHA512 integrity** as the image's
  `fetch-claude-code.py`:
  `+m01urgelnI+VJxPaKPEK0wixgq42uZ8PeCaUk5tX/8YoDBvSmC/REVQG2jQfJAr8dxunpjJ600FvLrcj1WWTw==`.
  The recipe contains no SHA256 pin. Setup derives archive/binary SHA256 from
  those authenticated bytes, verifies staged and installed binary SHA256, and
  records both. Repeat setup checks the installed SHA256 and avoids downloading
  an unchanged binary. It never executes a model request.
- Installs `NousResearch/hermes-plugin-claude-subscription-directsdk` at
  `ef73726cfaf2fa0ee041e55572f406e2c24fed83` with native
  `hermes plugins install … --ref … --no-enable --no-deps`, verifies all nine
  pinned file SHA256s from the image recipe, and adds the manifest provider name
  to `plugins.enabled` through `hermes config`. The existing Wizard plugin pin
  comes from its link journal or native install metadata; there is no main-branch
  fallback.
- Stores `DISABLE_AUTOUPDATER=1` via `hermes config`. Only when the gateway's
  declared systemd PATH cannot resolve the pinned binary does it set
  `CLAUDE_SUBSCRIPTION_DIRECTSDK_COMMAND`. A conflicting binary or unavailable
  service PATH fails closed. **It does not set model/provider defaults.**
- Temporarily unlinks first, compares both files to the link journal's original
  pre-link hashes, installs/enables the owner's provider while unlinked, then
  re-links with the same pinned Wizard plugin. This is necessary because native
  `wizard unlink` restores the whole previous `plugins.enabled` list. It would
  otherwise remove a provider enabled after the link. Every config/env mutation
  uses native Hermes/Wizard commands. `~/.e2e-022-alongside-claude/setup.json` records
  original pre-link, before, setup-unlinked and after-linked SHA256s; no file values.

`signin-page` resolves `.Image` from the one running `wizard-ai-accounts` engine,
reads its local image `RepoDigests`, requires AMD64 and uses that immutable
`sha256:<image-id>` with `--pull=never`. It **never pulls a new tag**. Its container
is `e2e-alongside-host-claude`, `--rm --user <uid>:<gid> --read-only --tmpfs /tmp`,
with `/home/<owner>/.claude:/claude` and only `127.0.0.1:8797:8795` published.
The owner directory is created 0700 and its ownership checked, never populated
from another account/store. `--stop` removes only that name with this runner's
ownership label. Docker uses the normal socket or `sudo -n docker` fallback.

The helper can also be dispatched independently from Thales (no lifecycle):

```sh
/opt/homebrew/bin/python3 tools/qa/e2e_022_alongside_claude.py status \
  --root /Volumes/ThalesMedia/wizard-os/e2e-022 --vm alongside-022-amd64
```

`status` calls owner `claude auth status --json`; it emits only subscription
logged-in boolean, allowlisted plan label and a masked email domain. No code
opens the contents of `~/.claude`, an auth store, or parses `.env` values.

### B. Alongside AI acceptance (timeout 10800 seconds)

Run only after A's receipt says **connected**:

```sh
/opt/homebrew/bin/python3 tools/qa/e2e_022_ai_flow.py \
  --root /Volumes/ThalesMedia/wizard-os/e2e-022 \
  --node /opt/homebrew/bin/node \
  --playwright-module /Volumes/ThalesMedia/wizard-manager/qa/node_modules/playwright \
  --vm alongside-022-amd64 --wait-minutes 75 --poll-seconds 20 --idle-grace-minutes 30
```

The guest helper also accepts `--vm alongside-022-amd64` directly. The host and
browser probes pass that mode explicitly and embed the public helper source;
there is no reliance on a previously installed QA module.

Alongside differences:
- `claude-connected`: owner CLI status, **not** the package's named-volume login.
- `owner-default-model`: owner `hermes config set model.provider
  claude-subscription-directsdk-experimental` and `hermes config set model.default
  claude-opus-5-5`, followed by `hermes gateway restart` and API health readback.
  Restart is present in stock Hermes `bebe448a2bdb57043ca8ebd820807bf7eed6320d`
  (`hermes_cli/subcommands/gateway.py`), verified from source, not exercised here.
- `agent-sees-apps`: host `mcp_servers.wizard`, `skills.external_dirs`, enabled
  Wizard plugin, plus DeFleur visible in Agent Service's actual `apps.json`.
  Container `agent-link` is omitted; alongside uses `wizard link`.
- Owner Hermes source commit and add-on file hashes replace the **inapplicable**
  Hermes-container digest check. A Hermes container is forbidden in this mode.
  Other image digests, Files writability, source clip, pinned DeFleur,
  browser model locks/READY, exact edit prompt, owner OKs, Back, pointer-only
  skills and output-video readback retain the same checks and browser script.
- Final `alongside-unlink` runs even after preflight/browser failure when the
  guest was reached. It first restores **only QA's temporary model/provider
  changes** using native Hermes config commands, then runs `wizard unlink`.
  Both config and env must exactly match the **setup-unlinked** SHA256s. The
  receipt separately shows the original pre-link hashes and whether they match;
  intended owner CLI/plugin setup changes are not misreported as drift. It then
  re-links in `finally` using the original Wizard plugin pin, restarts the gateway,
  and reads the host link/app contract back. No arbitrary drift is waived.
  Global QA defaults are therefore restored; the per-session model locks and the
  owner's new Claude login/plugin remain. Legacy scalar model IDs are restored
  with native `hermes config set model … --force`. Unsupported model shapes or
  pre-existing custom endpoint/credential route fields fail before mutation;
  switching providers can otherwise clear endpoint fields in stock Hermes.

Receipt verdict `6-alongside-unlink` is mandatory. Additional guest reports
include the setup/hash provenance and `alongside-unlink.json`. An absent final
unlink proof is a failed acceptance, never a pass based only on chat/video.

### Verification boundary

Local unit tests exercise argv, pin constants, masked status, port parsing,
relay security-function equivalence, alongside stage selection and both success
and byte-drift rollback/relink paths. Python compilation and Node syntax checks
are source verification only. Live owner UID/GID, systemd PATH, local AI Accounts
image ID/RepoDigests, sign-in, app access and completed AI output remain runtime
acceptance evidence; none were fabricated or fetched from the fresh guest.
