# Security inventory (Launch v1 · Audit 7, #138)

What each container on a Wizard box can reach: the Docker socket, sign-ins and secrets, and the owner's `media/` folder.
**Rule:** a sign-in mounts only into the agent and the connection app that owns it. A row that breaks the rule is a launch blocker.

Last checked: 22 Oct 2026, on Miguel's box (`oscarvps`, App Manager install, 35 containers) with `docker inspect`. Env-var names only; no values were read.

## 1. Live box

| Container | Docker socket | Sign-in / secret material | `media/` | Network |
|---|---|---|---|---|
| browser-qa-browser-1 | - | env: GPG_KEY | - | bridge |
| browser-qa-browser-engine-1 | - | - | - | bridge |
| browser/browser-1 | - | env: GPG_KEY | - | bridge |
| browser/browser-engine-1 | - | - | - | bridge |
| cinequeue/cinequeue-1 | - | env: GPG_KEY | - | bridge |
| defleur-video/defleur-video-1 | - | - | rw (/ ) | bridge |
| files/files-1 | - | env: GPG_KEY | rw (/ ) | bridge |
| files/files-engine-1 | - | env: FILES_PASSWORD | rw (/ ) | bridge |
| messenger/messenger-1 | - | env: MESSENGER_API_TOKEN, WN_SECRET_STORE, WN_KEYCHAIN_SERVICE | - | bridge |
| morning-report/morning-report-1 | - | env: GPG_KEY | ro (/Reports/morning-report ) | bridge |
| notifications/notifications-1 | - | ~/.hermes/cache/screenshots→~/.hermes/cache/screenshots ro<br>~/.hermes/sniper_reports→~/.hermes/sniper_reports ro<br>~/.hermes/cache/images→~/.hermes/cache/images ro<br>env: GPG_KEY | ro (/ ) | bridge |
| notifications/notifications-engine-1 | - | - | - | bridge |
| runtipi | ro | env: REDIS_PASSWORD, POSTGRES_PASSWORD, RABBITMQ_PASSWORD, JWT_SECRET | rw (/ ) | bridge |
| runtipi-db | - | env: POSTGRES_PASSWORD | - | bridge |
| runtipi-queue | - | env: RABBITMQ_PGP_KEY_ID | - | bridge |
| runtipi-reverse-proxy | ro | - | - | bridge |
| secret-drop/secret-drop-1 | - | env: GPG_KEY | - | bridge |
| secret-drop/secret-drop-engine-1 | - | app-data/wizardapps/secret-drop/data→/data rw<br>env: SECRET_DROP_PORT, SECRET_DROP_PUBLIC_URL, SECRET_DROP_API_TOKEN, SECRET_DROP_DATA_DIR, SECRET_DROP_BIND, GPG_KEY | - | bridge |
| sniper/sniper-1 | - | env: GPG_KEY | ro (/Reports/sniper ) | bridge |
| transcriber/transcriber-1 | - | env: GPG_KEY | ro (/ ) | bridge |
| transcriber/transcriber-engine-1 | - | - | - | bridge |
| wisdom/wisdom-1 | - | env: GPG_KEY | rw (/Wisdom ) | bridge |
| wizard-agent-service/wizard-agent-service-1 | - | ~/.hermes/cache/videos→~/.hermes/cache/videos ro<br>~/.hermes/state.db→/hermes/state.db ro<br>~/.hermes/state.db-wal→/hermes/state.db-wal ro<br>~/.hermes/state.db-shm→/hermes/state.db-shm ro<br>~/.hermes/cache/audio→~/.hermes/cache/audio ro<br>~/.hermes/cache/screenshots→~/.hermes/cache/screenshots ro<br>~/.hermes/cache/images→~/.hermes/cache/images ro<br>~/.wizard-os/hermes-view→/hermes ro<br>~/.hermes/cache/images→/hermes/cache/images ro<br>env: WIZARD_HERMES_API_KEY, WIZARD_MCP_TOKEN, WIZARD_ROUTER_KEY | rw (/ ) | host |
| wizard-calendar/wizard-calendar-1 | - | env: GPG_KEY | - | bridge |
| wizard-chatgpt/wizard-chatgpt-1 | - | env: UPSTREAM_PASSWORD, GPG_KEY | - | bridge |
| wizard-chatgpt/wizard-chatgpt-engine-1 | - | env: WIZARD_CHATGPT_HERMES_PASSWORD, WIZARD_CHATGPT_PASSWORD, GPG_KEY | - | bridge |
| wizard-claude/wizard-claude-1 | - | env: UPSTREAM_PASSWORD, GPG_KEY | - | bridge |
| wizard-claude/wizard-claude-engine-1 | - | ~/.claude→/claude rw<br>env: WIZARD_CLAUDE_HERMES_PASSWORD, WIZARD_CLAUDE_PASSWORD, GPG_KEY | - | bridge |
| wizard-cloudflare/wizard-cloudflare-1 | - | env: WIZARD_OWNER_LOGINS, WIZARD_OWNER_TOKEN, CF_ALLOW_TOKEN_CONNECT, WIZARD_ADMIN_TOKEN, GPG_KEY | ro (/ ) | bridge |
| wizard-local-registry | - | - | - | bridge |
| wizard-search/wizard-search-1 | - | env: TINFOIL_API_KEY, BRIGHTDATA_API_TOKEN, FIRECRAWL_CLOUD_API_KEY, GPG_KEY | - | bridge |
| wizard-shopping/wizard-shopping-1 | - | env: GPG_KEY | - | bridge |
| wizard-tinfoil/wizard-tinfoil-1 | - | env: HERMES_DASHBOARD_BASIC_AUTH_PASSWORD, GPG_KEY | - | bridge |
| wizard-ux-obsidian-preview | - | - | - | host |
| wizard-ux/wizard-ux-1 | - | - | - | host |

`GPG_KEY` is the official Python base image's signing-key ID, not a secret.

## 2. Findings

| # | Finding | Rule | Action |
|---|---|---|---|
| F1 | `wizard-claude-engine` mounts the **host's** `~/.claude` read-write. That folder is the host owner's Claude Code login, not an app-owned one. | OK for the connection app, but the login is shared with the host. | Decision #79/#80 moves it to the app's own `app-data` (wizard-app-manager#159, claude-connection#7). Re-check after those land. |
| F2 | `runtipi` and `runtipi-reverse-proxy` mount the Docker socket `:ro`. Read-only on a socket does **not** restrict the Docker API: either can start a privileged container. | Expected (they are the App Manager and its router), but they are effectively root. | Record as accepted. No app container has the socket. |
| F3 | The Agent Service runs on the host network with `media/` **read-write**, plus Hermes `state.db` read-only (decision #555, `--share-sessions`). | Expected: it is the agent's front door. | Accepted. Keep the Hermes mount read-only. |
| F4 | `wizard-search` holds three provider keys (Tinfoil, Bright Data, Firecrawl). | Keys, not sign-ins; it owns them. | Accepted. List them in its `wizard.md` secrets. |
| F5 | `wizard-cloudflare` receives `WIZARD_OWNER_LOGINS`, an owner token and an admin token (wizard-app-manager#158). | Owner-login app; matches the rule. | Accepted. The admin token is the widest grant on the box; review its scope before launch. |
| F6 | `browser-qa-*` and `wizard-ux-obsidian-preview` are dev containers, not part of the launch profile. | n/a | Not on tester boxes. |
| F7 | `media/` read-write: Files, DeFleur Video, Wisdom (`/Wisdom` only), Agent Service. Read-only: Transcriber, Notifications, Cloudflare, Sniper, Morning Report (their report folders). | Each matches the app's job. | Accepted. |

## 3. Design-level items (not yet on this box)

From the Architecture check-ins on #138. Each needs a row here once it ships.

| Item | What it grants | Status |
|---|---|---|
| Share grants (#80, PERMISSIONS "Share grants") | The Claude login folder becomes a bind mount into Hermes: a file path, not an API. | Within the rule (agent + its connection app). Ships with wizard-app-manager#159. |
| ChatGPT gateway (#79) | `wizard-chatgpt:8801/v1` injects the real token for **any caller holding the per-install local key**. | Who gets that key is the boundary. Before launch it must be only the agent. |
| Heavy relay (wizard-agent-service#87) | The worker drives a Docker daemon; job containers get open internet and no CPU quota. | Off by default. Must stay off on launch builds, or ship with egress limits. |
| Private-agent second ingress (#81, #147) | A private-only credential for `/wizard/standard-chats/mcp` (read-only standard chats). | Opt-in, per agent, checked per call (wizard-agent-service#84). |
| Per-app grant keys (PERMISSIONS v0.2, #129) | Key files mounted read-only into apps. | Ships with wizard-app-manager#8. |
| Post-Setup fetches (#158) | Background image prefetch and raw.githubusercontent.com recipe fetches with no owner action. | Supply-chain dependency; pinned by commit (#125). |
| Claude auto-renew (wizard-app-store#17) | One unattended Haiku turn when the login reads expired. | `WIZARD_CLAUDE_AUTO_RENEW=0` disables. |

## 4. Other #138 items

- **App Manager API lock:** done in code. `wam serve` binds `127.0.0.1` by default (`WAM_BIND`), and changes need the bearer token in `~/.wizard-os/api-token` (mode 0600 on this box). WORK_OUTSTANDING ticked.
- **`confirm_downgrade`:** no downgrade path is left. The Agent Service refuses `confirm_downgrade: true` on a private agent (`agent.private_sealed`, `server/agents.mjs`). The flag is only a refusal now; removing it is cosmetic.
- **Private-agent wording on alongside installs** ("API-level separation; host Hermes and host administrators can read its data"): **not found** in Wizard UX. Still open.
- **Store lists first-party apps only until #133:** not verified here. Still open.
