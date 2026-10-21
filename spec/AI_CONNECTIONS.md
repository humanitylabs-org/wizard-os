# AI connections: one app per provider

Status: **Decided (Miguel, 15 Oct 2026)**, decision #61. Agent use of logins changed by James, 21 Oct 2026, #79. Replaces the single "AI Accounts" app (`wizard-ai-accounts`) as the way a Wizard signs in to AI providers.

## The rule

Each AI provider gets its own small **connection app** in the Wizard App Store: `Claude`, `ChatGPT`, later `OpenRouter`, `Tinfoil`, and so on. The owner installs only the providers he uses. Each app owns exactly one sign-in, shows its own Connect / Test / Disconnect page, and reports its status and usage through one shared read-only contract (below). Nothing else on the box reads another app's login.

Why per provider instead of one central app:
- Every provider signs in differently (Claude Code login, ChatGPT device code, API keys). One app per provider keeps each one small and testable.
- Each app is pinned and updated on its own. The Claude login CLI must stay version-matched with the agent image; that bump no longer forces a release of every other provider.
- Uninstalling or breaking one provider can't sign you out of another.
- The "one place to see everything" a central app gave is the shell's job: Home → Resources → AI accounts already lists every connection.

## What every connection app ships

`wizard.md`:
- `type: external`, `category: system`
- `provides: [ai-connection, <provider>-subscription]` (or `<provider>-api-key`). `ai-connection` is how the Agent Service finds it in `apps.json`.
- a `view` (the Connect page) and an `mcp` with one read-only `connection_status` tool.

HTTP, served on the app's own port:

```
GET /api/connection        read-only, never returns a token
```

```jsonc
{
  "contract": "wizard.ai-connection/1",
  "provider": "claude",            // stable id, also the row id the shell shows
  "name": "Claude",
  "status": "connected",           // connected | not_connected | expired | error
  "plan": "Max 20x",               // or null
  "account": "label shown to the owner, e.g. email or org", 
  "usage": {                       // null when the provider has no usage API or status != connected
    "fetchedAt": "2026-10-15T14:43:46.821Z",
    "limits": [ { "id": "weekly", "label": "Week", "usedPercent": 12.0, "remainingPercent": 88, "resetsAt": "ISO" } ],
    "paid": null                   // same shape the Agent Service emits today for extra usage
  },
  "error": null                    // { "code": "signed_out|expired|unreachable|provider_error", "message": "..." }
}
```

The `limits[]` and `paid` shapes are exactly the provider rows `GET /wizard/ai-usage` already returns (wizard-agent-service `server/ai-usage.mjs`), so the shell needs no change.

Rules:
- The app reads its own login only to call its provider. No route serves, copies or logs a token. No other app mounts the login, with one exception: a provider whose terms allow only its official client (Claude) may export its login folder as an owner-granted **share** so that client can run inside the agent ([below](#agents-using-a-connection)).
- The login lives in the app's own app-data folder (`${APP_DATA_DIR}`), never a Docker named volume, so an App Manager backup or a box move carries it and nobody signs in again.
- The app is the only process that renews its login. Renewed tokens rotate, so after a box move the old box must stay stopped.
- `/api/connection` answers within 10 s and caches provider reads for 60 s. A provider outage returns the last good `usage` for at most 30 min with `error.code: unreachable`, then `usage: null`.
- Box-only: the same refusal rules as other owner-data routes (requests carrying `tailscale-user-login`, `x-forwarded-for`, `forwarded`, `x-real-ip` or `cf-*` are refused), because the port is also on the tailnet.

## Agent Service

`GET /wizard/ai-usage` builds its `providers[]` from every running app in `apps.json` that `provides: ai-connection`, calling each app's `/api/connection` on its local address. The existing host-file readers (`~/.claude/.credentials.json`, Hermes' Codex pool) stay as a fallback for a provider with no connection app installed, so alongside boxes that sign in on the host keep working.

## Agents using a connection

Decided by James, 21 Oct 2026 (#79). Each connection app owns its login; agents use it through the app and never sign in themselves.

**ChatGPT: model gateway.** The ChatGPT app does the device-code sign-in, stores the login in its app-data and is the only refresher. It serves a box-only gateway at `http://wizard-chatgpt:8801/v1` (`/responses`, `/responses/compact`, `/models`, and the usage routes), which injects the real token and account headers. Callers authenticate with a per-install local key the app generates; that key is not a ChatGPT credential. On Connect the app registers itself with Hermes through the dashboard API: Hermes' native `openai-codex` provider with `HERMES_CODEX_BASE_URL` set to the gateway and the local key as a manual credential-pool entry (no refresh token), plus a named custom endpoint as fallback. It never changes Hermes' default model. The native provider keeps Codex web search, the usage display and server-side compaction, which a plain custom endpoint loses. Disconnect removes the login, the pool row and the endpoint. Proven 21 Oct 2026 on a live sign-in: reply, tool call, streaming, app-owned renewal, a stopped-copy move without re-login, and Disconnect, with Hermes connecting only to the gateway.

**Claude: shared login folder.** Anthropic allows a subscription login to be used only by its own Claude Code client, so a token gateway is not allowed for Claude. Hermes uses Claude through Nous's Claude Subscription DirectSDK plugin, which runs the official Claude Code CLI against a config folder. The Claude app keeps that folder in its app-data and declares it as a share (`shares: [{id: claude-login, path: claude}]`). Hermes Agent declares `mounts: [{app: wizard-claude, share: claude-login, path: /claude}]`; once the owner grants it, the App Manager bind-mounts the folder into Hermes ([WIZARD_MD.md](WIZARD_MD.md#shared-folders), [PERMISSIONS.md](PERMISSIONS.md#share-grants)). Both sides run the official CLI, which renews under its own cross-process lock (`.oauth_refresh.lock` in the folder: re-read under the lock, then compare-and-swap), so two copies never break each other's login. Keep the Claude CLI in both images on compatible versions. The old fixed volume `wizard-ai-accounts-claude` is copied into the Claude app's folder once on upgrade and then left unused.

## Running models for apps (proposed, #65)

Connection apps report status today and run nothing for apps. [CONNECTION_ROUTER.md](CONNECTION_ROUTER.md) proposes an additive `wizard.ai-connection/2`: `/api/connection` lists the provider's models with their tier (`fast`, `standard`, `frontier`), and `POST /api/infer` runs one isolated call that only the Connection Router may make.

## Migration from AI Accounts

1. Install `Claude` (and `ChatGPT` if used). On first start the App Manager copies the old `wizard-ai-accounts-claude` volume into the Claude app's folder, so it shows Connected immediately.
2. Uninstall AI Accounts. The old volume is no longer used; delete it after the Claude app reports Connected.
3. A box that signed in to ChatGPT inside Hermes keeps working until the owner presses Connect in the ChatGPT app; registration refuses to run while Hermes still holds its own Codex login, and the page says to remove it first.
4. AI Accounts stays in the store marked deprecated until both replacements are published, then is hidden.
