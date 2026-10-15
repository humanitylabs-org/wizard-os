# AI connections: one app per provider

Status: **Decided (Miguel, 15 Oct 2026)**, decision #61. Replaces the single "AI Accounts" app (`wizard-ai-accounts`) as the way a Wizard signs in to AI providers.

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
- The app reads its own login only to call its provider. No route serves, copies or logs a token, and no other app mounts the login.
- `/api/connection` answers within 10 s and caches provider reads for 60 s. A provider outage returns the last good `usage` for at most 30 min with `error.code: unreachable`, then `usage: null`.
- Box-only: the same refusal rules as other owner-data routes (requests carrying `tailscale-user-login`, `x-forwarded-for`, `forwarded`, `x-real-ip` or `cf-*` are refused), because the port is also on the tailnet.

## Agent Service

`GET /wizard/ai-usage` builds its `providers[]` from every running app in `apps.json` that `provides: ai-connection`, calling each app's `/api/connection` on its local address. The existing host-file readers (`~/.claude/.credentials.json`, Hermes' Codex pool) stay as a fallback for a provider with no connection app installed, so alongside boxes that sign in on the host keep working.

## Agents using a connection

Unchanged for Claude: the Claude app keeps the shared volume name `wizard-ai-accounts-claude` mounted at `/claude`, so Hermes Agent (Wizard build) and existing sign-ins carry over with no reconnect. ChatGPT stays Hermes' own device-code login driven from the ChatGPT app (Codex refresh tokens are single-use, so no shared token file).

## Migration from AI Accounts

1. Install `Claude` (and `ChatGPT` if used). Claude reuses the existing sign-in volume, so it shows Connected immediately.
2. Uninstall AI Accounts. The volume survives because the Claude app still uses it.
3. AI Accounts stays in the store marked deprecated until both replacements are published, then is hidden.
