# Wizard OS settings and bootstrap v1

**Owner:** Jan (Agent Service). **Status:** implemented on `wizard-agent-service` branch `feature/stock-hermes`, tested on a fresh stock-Hermes VM, 9 Oct 2026. Not yet merged.

Nothing in Wizard UX knows who you are, what you call your agent, where you live or which apps you have. A Wizard OS box says so in one small file, and every front end asks the Agent Service for it.

## `settings.json`

- **Location:** `$WIZARD_OS_HOME/settings.json` (default `~/.wizard-os/settings.json`), next to `apps.json`.
- **Written by:** the installer (first run), and later by Settings in Wizard UX. Hand-editing is fine; it is re-read on every request.
- **Read by:** the Agent Service only. Front ends get it through `GET /wizard/v1/bootstrap`.
- **Not secret.** No keys or tokens ever go in it.

```json
{
  "schema": 1,
  "owner": { "name": "James", "place": "Bangkok, Thailand" },
  "agent": { "name": "Archimedes" },
  "clock": { "timezone": "Asia/Bangkok", "day_starts_at": "06:00" },
  "voice": { "language": "en", "vocabulary": ["ICONSIAM", "Suvarnabhumi", "Thonglor", "Mizel"] }
}
```

| Field | Meaning | Default |
|---|---|---|
| `owner.name` | What the UX and every agent call the person. Lives here, not in one agent's memory, so swapping or adding an agent keeps it. | empty (UX says "you") |
| `owner.place` | Free text. Helps voice correct local place names. | empty |
| `agent.name` | What the person calls their Wizard. | `Wizard` |
| `clock.timezone` | IANA zone for "today", "yesterday" and Day/Week views. | empty = the device's own zone |
| `clock.day_starts_at` | When "today" starts for Ready vs Yesterday (`HH:MM`). | `00:00` |
| `voice.language` | Speech-to-text language hint. | empty = auto |
| `voice.vocabulary` | Names voice should spell right (people, places, apps). | empty |

Rules: readers ignore unknown fields; adding a field is not a version bump; renaming or removing one is.

## `launcher.json` (optional)

The person's own links that are not Wizard apps (private web apps, bookmarks). Same folder. Installed Wizard apps come from `apps.json`; this file is only for extras.

```json
{ "schema": 1, "links": [ { "id": "cinequeue", "name": "CineQueue", "url": "/cinequeue/", "icon": "🎬", "desc": "Your watch queue", "colors": ["#ff5c7a", "#7a2bff"] } ] }
```

URLs must be same-origin paths (`/x/`) or `https://`.

## `GET /wizard/v1/bootstrap`

The first call every Wizard front end makes.

```json
{
  "bootstrap": 1,
  "api": "wizard-agent-service/1",
  "settings": { "...normalised settings.json..." },
  "settings_source": "file | default | invalid",
  "capabilities": {
    "voice": true, "router": true, "files": true, "approvals": true, "steer": true,
    "joined_delegation": true, "markdown": true
  },
  "endpoints": {
    "apps": "/wizard/v1/apps", "sessions": "/wizard/hermes/api/sessions", "runs": "/wizard/hermes/v1/runs",
    "transcribe": "/wizard/voice/transcribe", "route": "/wizard/v1/route", "upload": "/wizard/files/upload"
  }
}
```

- A capability is `true` only when it works right now. For example, `voice` is true only when the transcription slot answers its health check. The UX hides the matching control when a capability is false.
- An empty endpoint means "not on this box".
- `joined_delegation` / `markdown` say what the agent behind the service supports (see "Agent compatibility").

## `GET /wizard/v1/apps`

`apps.json` apps plus `launcher.json` links, reduced to what a launcher tile needs (`id`, `name`, `desc`, `url`, `icon`, `colors`, `status`, `system`, `source`).

## `POST /wizard/v1/route` (optional: the orb command router)

Present only when the box configures a router model (`WIZARD_ROUTER_URL` + `WIZARD_ROUTER_MODEL`, any OpenAI-compatible chat endpoint). It classifies one spoken sentence as a phone/UI command ("open CineQueue", "next desk", "directions to ICONSIAM"), a reply to the window in front, or a request for the agent. It uses `owner.place` and the clock from `settings.json`. Without it, everything said to the orb goes to the agent.

## Agent compatibility

The Agent Service works with stock Hermes. `WIZARD_JOINED_DELEGATION`:
- `prefer` (default for new installs): use joined delegation and Markdown rendering when Hermes advertises them in `/v1/capabilities`; otherwise send a plain run. Stock Hermes already runs delegated work inline for API runs, so the reply still arrives in the same run.
- `require`: refuse runs (503) unless Hermes advertises joined delegation. For boxes that rely on it.
- `off`: never ask for it.

## `fast_router` (added 9 Oct 2026)

Which model routes orb utterances. Fields: `account` (whose subscription pays), `model`, and until
shared accounts exist `endpoint` (OpenAI-compatible chat URL) + `key_env` (name of the env var holding
the key; the key never goes in this file). Absent means no router: voice goes straight to the agent.
Bootstrap exposes `account` and `model` only. Plan: `docs/FAST_ROUTER_AND_ACCOUNTS.md`.
