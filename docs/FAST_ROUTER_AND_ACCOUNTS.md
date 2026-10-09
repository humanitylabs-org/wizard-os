# Fast router and shared accounts: plan (9 Oct 2026)

**Status:** step 1 is live on James's daily Wizard. Steps 2-4 wait on Miguel's shared-accounts work.

## What the fast router is
When the user taps the orb and speaks, one small fast model decides in about a second whether the words are
- a phone or UI command ("open CineQueue", "directions to ICONSIAM"),
- a reply to the window in front ("yes, go ahead"), or
- a request for the agent.

This call does **not** go through the agent harness (Hermes). It is the Agent Service calling one model
directly, because a full agent turn takes several seconds and would make the orb feel slow.

## Step 1, live now: the choice is a setting
`~/.wizard-os/settings.json` holds:

```json
"fast_router": {
  "account": "tinfoil",
  "model": "deepseek-v4-1-flash",
  "endpoint": "http://127.0.0.1:3301/v1/chat/completions",
  "key_env": "WIZARD_ROUTER_KEY"
}
```

- `account` names whose subscription pays for it. `model` is that account's fast model.
- `endpoint` + `key_env` are the stop-gap way to reach it today. The key itself stays in the service
  environment and never appears in settings or in the bootstrap.
- With no `fast_router`, voice still works and everything goes to the agent (slower for commands).
- Bootstrap reports `capabilities.router` and the `fast_router` account/model, never the key.

## Benchmark (9 Oct 2026, 20 utterances x same prompt, all 100% correct)
| Model | Account | Median | Slow end |
|---|---|---|---|
| Grok 4.20 non-reasoning | xAI | 0.85s | 1.1s |
| Claude Haiku 4.5 | Claude | 0.87s | 2.2s |
| DeepSeek V4.1 Flash | Tinfoil | 1.04s | 4.4s |
| GPT-6 Luna | ChatGPT | 1.26s | 2.4s |
| gpt-5.4-mini / codex-spark | ChatGPT | ~1.95s | ~3s |

Default fast model per account: Claude -> Haiku 4.5, ChatGPT -> GPT-6 Luna, xAI -> Grok 4.20 non-reasoning,
Tinfoil -> DeepSeek Flash.

## Where this is going: accounts connected once, shared by every agent
Today a user connects Claude or ChatGPT inside Hermes, and every other harness or app would have to
connect it again. The target (Miguel, App Manager / system apps):

- Each subscription is its own Wizard OS **account service**: Claude, ChatGPT, xAI, Tinfoil. It is
  connected once and owns the login and token refresh.
- Agents (Hermes, OpenClaw, others) and Wizard OS services (Agent Service, router, transcriber) borrow
  from it. Nobody else stores the credential.
- The **first account connected becomes the default fast router**. The user can change it in settings.

## Migration steps
1. **Done.** Router choice in `settings.json` (`fast_router`), endpoint + key env as a stop-gap.
2. **When Miguel's account service lands:** `fast_router` keeps only `account` and `model`. The Agent
   Service asks the account service for a short-lived way to call that model; `endpoint`/`key_env`
   become optional overrides for self-hosted routers.
3. **Installer / onboarding:** whichever account is connected first writes `fast_router` with that
   account's default fast model from the table above.
4. **James migrates** from the Tinfoil stop-gap to his account service entry. Same model, same privacy.

## Open questions for Miguel
- Interface the account service exposes to local services: a local OpenAI-compatible proxy per account,
  or a token broker.
- Whether subscription OAuth (Claude/ChatGPT) allows calls outside the vendor's own CLI, per each
  provider's terms. Hermes already does this for its own turns, so the account service can follow
  Hermes's existing approach.
