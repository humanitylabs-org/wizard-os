# App wake events (`wizard.app-wake/1`)

**Status: proposed, built behind the owner switch `wizard/app-wake` (off by default; wizard-os#634).** First user:
Messenger's Agent chat wake. Implemented by the Agent Service (`server/app-wake.mjs`, `docs/app-wake.md`).

An installed app may wake one of the owner's agents with a small typed event, for example "something new waits in
your Agent chat". The box is the agent's event inbox: the agent sets nothing up, no Hermes webhook subscription is
made, and no secret is handed around. The app proves who it is with its own app token, and the Agent Service wakes
the agent only when the owner has given that agent this app.

## Who may wake whom

- **The app:** an installed app, by its own app token, the file `<wizard-os home>/app-tokens/<app id>` that the
  App Manager creates and hands to the app at install (an app asks for it by naming a `<NAME>_AGENT_INBOX_TOKEN`
  variable in its recipe compose, WAM#804). Never the owner's credential and never an agent's: those are refused.
- **The agent:** the main agent (`hermes`) or a standard agent by its id (spec/AGENTS.md). A recovery agent is never
  woken.
- **Owner approval, per app:** the agent must have this app in its granted apps, the same per-agent app grant the
  owner already sets (spec/AGENTS.md permissions, `wizard_apps`; the main agent sees every installed app). Taking the
  app away from the agent stops its wakes at once. An app may add its own rule on top (Messenger wakes only agents
  the owner gave Draft-only access in Messenger).

## The probe: `GET /wizard/v1/agent-events`

With the app's token: `200 {"on": true, "contract": "wizard.app-wake/1", "app": "<app id>", "agents": ["hermes", ...]}`,
the agents this app may wake now. **`404` means the box offers no wake** (switch off, or an older Agent Service):
the app keeps whatever it did before. Apps read the probe at most every few minutes.

## A wake: `POST /wizard/v1/agent-events`

```json
{"event": "agent_chat", "agent": "hermes", "data": {"reason": "note", "waiting": {"notes": 2}}}
```

- `event`: the event's name, `^[a-z][a-z0-9_]{0,47}$`. The box names it `<app id>.<event>` (here
  `messenger.agent_chat`); a name with another app's prefix is refused.
- `agent`: optional, default the main agent.
- `data`: optional, small and flat. At most 16 keys (`^[a-z][a-z0-9_]{0,31}$`), each a string of at most 200
  characters with no line breaks, a number, a boolean or null, or one nested object of the same; at most 2 KB as
  JSON. **No message text, no owner content:** the event says *that* something waits, the agent reads *what* through
  the app's own tools, under the app's own access levels.

| Answer | Meaning |
|---|---|
| `202 {"woken": true, "event", "agent", "thread_id", "run_id"}` | One turn was admitted. |
| `200 {"woken": true, "merged": true, "event", "agent"}` | The same event to the same agent came within a minute of the last wake: merged. The newest merged event is woken once more when that minute ends, so nothing is lost. |
| `400 invalid_event` / `invalid_agent` / `invalid_data`, `413 data_too_large` | The event broke the rules above; nothing ran. |
| `403 app_token_required` | Not an installed app's own token. |
| `403 not_granted` | The owner has not given that agent this app. |
| `404 agent_not_found` | No such agent. |
| `429 wake_limit` (`Retry-After: 60`) | More than 60 wakes from this app in the last hour. |
| `503 wake_not_started` | The agent could not take the turn now; the app may try again later. |

## What the agent gets

One turn in a **new hidden background thread** of that agent (hidden from Chats and counts, like the agent inbox's
background notes), admitted through the Service's durable run queue with an idempotency key `wizard-wake-…`. The
turn's words say which app sent which event with its data, that this is an app's signal and not the owner's words
(the fields are data, never instructions), that nobody is watching the thread, and to use that app's tools and skill
to see what waits. An app's skill says what each of its events means.

## Rules for apps

- Wake only for something the agent can act on, and debounce bursts yourself (Messenger waits about 1.5 s).
- Never put message text, names or other owner content in `data`.
- Keep your old way working when the probe answers 404.
- A wake is best effort: the agent can always look itself.
