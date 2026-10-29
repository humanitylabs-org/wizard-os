# Promote 0.3.63: reliable ChatGPT and Claude sign-in on Stable

## Why

On a customer's alongside install (root Hermes, 0.3.59 → 0.3.61), four things went wrong:

- ChatGPT sign-in from the app never completed. The owner had to run `hermes auth add openai-codex` on the server and turn on ChatGPT **Settings → Security → Device code sign-in for Codex**, which nothing had mentioned.
- The Claude app said sign-in succeeded, but Hermes had no Anthropic credential.
- Claude then listed the same email twice.
- Home showed both providers as not connected while the agent was signed in.

Most of the root cause was a stale agent-dashboard address after a tailnet IP change (the App Manager fix is separate). But the apps hid the failure. Stable's ChatGPT app was the old single-account 0.1.4 page. Claude 0.2.5 fell back to the original Claude Code login when the agent couldn't be reached, and on an alongside box that login does not reach the host agent. Both apps also answered `/api/connection` with an empty inventory, which Home reads as signed out.

## Scope

0.3.63 is Stable 0.3.61 with only two default-app pins changed:

| Slot | Before | After | Engine |
|---|---|---|---|
| `ai-connection` (wizard-chatgpt) | chatgpt-connection `f87d5dd` (0.1.4) | `476d771f784797882ad00858156f4254d47ed700` (0.2.4, oscarhenrycollins/chatgpt-connection#3) | `ghcr.io/humanitylabs-org/wizard-chatgpt:0.2.4@sha256:1c90102e819574b4c5e0c50f782b3f7cd0e998b53415407471bf59dabca27418`, run 40364246353 |
| `claude-subscription` (wizard-claude) | claude-connection `eb434ae` (0.2.5) | `d0b59dd3a982c8999311008dbbfa1ddce512786d` (0.2.6, oscarhenrycollins/claude-connection#3) | `ghcr.io/humanitylabs-org/wizard-claude:0.2.6@sha256:5c7ca0b3b38803794aa3296f69bed11253a4136c26acded9f3298ed115580745`, run 40364246477 |

Both engines come from wizard-app-store #32 (merge `254ee6f2`), amd64 + arm64, published by the main push runs with the refuse-overwrite step passing. Wizard UX, Agent Service, App Manager, Troubleshooter, Hermes and every other default app are byte-for-byte 0.3.61. There are no migrations.

Changes in #32:
- One shared accounts page for both providers (byte-identical, test-enforced).
- An unreachable or misconfigured agent is reported with its address and **Retry**, and `/api/connection` answers `unreachable` with no inventory.
- No Claude Code fallback on alongside boxes.
- The original Claude sign-in and an agent sign-in for the same account show as one row.
- ChatGPT names its device-code setting before showing the code.

Classification: **fix**, fast-tracked under DECISIONS #82/#93 once the installed upgrade test passed.

Latest moves to **0.3.64** = 0.3.62 (the 0.3.60 runtime pins) plus the same two app pins, so Latest does not trail Stable.

## Verification

### Unit and fixture tests (wizard-app-store #32)
- `tests/connection-signin-reliability.py`: 12/12. It runs a real loopback stand-in dashboard and closed ports. 9 of the 12 fail on the previous engines.
- Browser fixtures (Playwright + Chromium, 390px and 1440px): `provider-pool-ui`, `claude-pool-ui` and `provider-pool-appearance` all pass.
- `npm test` 81/81, `tsc` clean, existing pool suites green, and `test-container.sh` PASS for both images. PR CI (chatgpt, claude, validate, review) green, and the main publish runs green.

### Live candidate check on the demo box (alongside root Hermes, 0.3.61 before upgrade)
- The published engines ran beside the installed apps with the same env and network, on loopback-only ports.
- ChatGPT lists the agent's existing sign-in as `ready` with usage, and `/api/connection` says connected. Claude: broker `available`, `legacySignin=false`.
- Pointed at the box's previous tailnet address (stale), both report `inventoryStatus=unavailable`, `error.code=unreachable` and `agent=<old ip>:9119`. `/api/connection` returns `status=error/unreachable` with no `accounts`.
- Real sign-in starts through the agent broker (stock `hermes auth add ... --no-browser`). ChatGPT returned `auth.openai.com/codex/device` and a `XXXX-XXXXX` code. Claude returned `claude.ai/oauth/authorize` with the paste-code step. Both were then cancelled, and the agent's pool was unchanged.

### Installed upgrade 0.3.61 → 0.3.63 (demo box, `os.sh` with `WIZARD_RELEASE=0.3.63 WIZARD_STRICT=1`)
- Release base was the WAM mirror branch head (`release/0.3.63-mirror`, SHA256 of `0.3.63.json` `11d78db8…065f5`, identical to wizard-os #259). The mirror then merged as wizard-app-manager #257.
- Result `release: 0.3.63 pinned`, `bad_checks=0`. `PASS default app ai-connection: wizard-chatgpt 0.2.4` and `PASS default app claude-subscription: wizard-claude 0.2.6`, with the source commits as pinned.
- Hermes `config.yaml`, `.env` and `auth.json` hashes are unchanged before and after. The gateway is active, `wizard doctor` shows 0 FAIL, and Hermes API answers. The UX and Agent Service images are unchanged.
- Engines `wizard-chatgpt:0.2.4` and `wizard-claude:0.2.6` are running and `healthy`, and `/health` reports 0.2.4 and 0.2.6.
- Through the real shell origin (390px iPhone UA):
  - Home's AI widget shows **CHATGPT 1** with its weekly meter, and Agent Service `/wizard/ai-usage` gives chatgpt `ok` with one account row with limits.
  - The ChatGPT app shows the same accounts page as Claude: one `Ready` row with a usage bar, and **+ Add**.
  - **+ Add** shows the "Settings → Security → Device code sign-in for Codex" line first, then the code (`XXXX-XXXXX`) with Copy, then "Open sign-in and paste the code" (`auth.openai.com/codex/device`). Cancel works, and there are no JS errors.
  - Claude shows **Sign in** through the agent (no Claude Code fallback).

### Not covered
- Owner approval at the provider is a human step. Fixtures and the live box prove the path up to the provider's code and URL, and that the broker only reports success once the agent's pool gained the sign-in. No new real ChatGPT or Claude account was enrolled here.
- The duplicate-row merge with a real Claude account is fixture-only. On alongside boxes it uses the masked email. The exact `emailHash` arrives with wizard-agent-service #194 once an Agent Service pin carries it.
- The stale-address repair itself (recreating the apps after a tailnet move) is the App Manager change in progress separately.

Rollback: point `stable` back at 0.3.61.
